## Task: Shared-password login gate + backend lock (Option A — full)

### Goal
Only people with a shared username/password can use the app. Frontend shows a login screen until authenticated; backend refuses unauthenticated requests; backend is unreachable from outside the server. Closes the `:8001` bypass entirely.

### Why three layers
Backend (`start.sh:180`) binds `0.0.0.0:8001` with zero auth → frontend-only gate is bypassable by `curl http://vps-ip:8001/api/patients`. So: (1) frontend gate, (2) backend session-token check, (3) bind backend to loopback. Defense in depth.

### Credentials model
- Env vars in `.env`: `BILUN_AUTH_USERNAME`, `BILUN_AUTH_PASSWORD` (PBKDF2 hash), `BILUN_SESSION_SECRET`.
- Login → backend issues HMAC token (username + expiry, keyed by secret) in httpOnly cookie `bilun:session` (7-day). Frontend middleware + backend both verify this same token.

### Subtasks
- [ ] Layer 1: auth.py (hash/verify/token helpers)
- [ ] Layer 1: routes/auth.py (login/logout/me)
- [ ] Layer 1: __init__.py register router + session middleware
- [ ] Layer 1: tests/unit/api/test_auth.py
- [ ] Layer 2: frontend middleware.ts session gate
- [ ] Layer 2: login page + AppTopBar logout + apiClient credentials
- [ ] Layer 2: i18n auth namespace (en+tr)
- [ ] Layer 3: start.sh loopback bind + generate_auth_env.py + .env.example
- [ ] Layer 4: verify (pytest, vitest, tsc, lint, manual)

### Out of scope
- Per-user accounts / user DB / roles (Option B, separate project).
- HTTPS/TLS (VPS reverse proxy — separate task).
- CI auto-deploy-on-push (separate task).

### Review
- **Three-layer defense in place:** (1) Next.js middleware redirects unauthenticated users to `/login`; (2) FastAPI `SessionGateMiddleware` rejects any `/api/*` request without a valid cookie (401); (3) backend binds to `127.0.0.1` by default (`BACKEND_HOST`, configurable) so `:8001` is unreachable from outside. The `:8001` bypass is closed.
- **Shared secret via env:** `BILUN_AUTH_USERNAME` + `BILUN_AUTH_PASSWORD` (PBKDF2-HMAC-SHA256, 310k iters) + `BILUN_SESSION_SECRET`. Login issues an HMAC-signed stateless token in an httpOnly `bilun:session` cookie (7-day TTL); both frontend middleware and backend verify the same token. Rotating the secret revokes everyone.
- **Fail-open for dev / fail-closed for prod:** when env vars are unset, the backend gate logs a warning and admits requests (local dev works with no `.env`); the `/login` endpoint returns 503 so a misconfigured prod deploy can't silently run open. When set, `/api/auth/*` and `/health` are exempt; everything else requires the cookie.
- **Frontend:** login page (`/login`) using existing `.sut-input`/`.sut-btn-primary` CSS; `apiClient` sends `credentials: "include"`; logout button added to `AppTopBar`; new `auth` i18n namespace (EN+TR).
- **Setup tooling:** `scripts/generate_auth_env.py <user> <pass>` prints ready-to-paste env lines; `.env.example` documents all vars (LLM + auth + bind).
- **Verification:** `pytest tests/unit/api` 105 passed (incl. 24 auth tests covering crypto, token tamper/expiry, login/logout/me, middleware gate, exempt paths, fail-open/503); full `tests/unit` 807 passed (5 failures are pre-existing drug-indication corpus work, untouched). Frontend `tsc --noEmit` clean, `vitest` 140/140, my files `eslint`-clean (the 10 repo lint errors are pre-existing in untouched files). Live end-to-end check against a running backend: no-cookie→401, wrong-pass→401, correct→200+cookie, with-cookie→200, `/me`→authenticated, `/health`→open. ALL E2E PASSED.
- **Pre-existing (NOT from this work):** 5 drug-indication tests unstable due to uncommitted anti-VEGF corpus work in the tree; 10 frontend lint errors in untouched files. Left alone.

