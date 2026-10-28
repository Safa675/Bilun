# Public billing and developer access: release runbook

This release opens only the existing synthetic billing workflow. The Python
engine remains on the server. Browser JavaScript is inspectable, including
developer UI chunks that have already been published; authorization protects
developer data and actions rather than concealing downloaded code.

## Configuration and cutover

`BILUN_PUBLIC_BILLING_ENABLED` defaults off. Do not enable `BILUN_AUTH_OPTIONAL`
in production. With public access off, billing requests require authentication;
engineering routes additionally require developer capability in either state.

The current app has one configured login. Reusing a previously shared password
as the developer password would grant developer access to its former holders.
Generate a new developer-only credential into a private file, never argv/logs:

```bash
python scripts/generate_developer_auth_env.py \
  --username bilun-developer --output /private/operator/path/developer.env
```

Create the owner-only parent directory beforehand. The script prompts for a
new password of at least 16 characters; `--password-stdin` is available for
trusted automation. It refuses to overwrite an existing path and creates a
0600 file. It generates:

| Variable | Purpose |
| --- | --- |
| `BILUN_AUTH_USERNAME`, `BILUN_AUTH_PASSWORD` | New configured developer login; password is stored as a PBKDF2 hash |
| `BILUN_DEV_USERNAMES` | Explicit developer allowlist containing that identity |
| `BILUN_SESSION_SECRET` | Fresh signing key; install consistently in the paired services |
| `BILUN_SESSION_TOKEN_PURPOSE` | `bilun-developer-v1`, records the target format for release probes |
| `BILUN_HEALTH_PROBE_TOKEN` | Independent random operator token for detailed health checks |
| `BILUN_COOKIE_SECURE` | `1` for production HTTPS; explicit `0` only for local HTTP verification |
| `BILUN_PUBLIC_BILLING_ENABLED` | Initially `0` |

New sessions use a purpose-bound format. The new backend refuses pre-cutover
session formats even if a signing key was mistakenly retained. Rotate the
signing key and password anyway; do not restore the former shared credentials
on rollback. Keep private files out of Git, artifacts, logs and browser assets.

Successful logout deletes this browser's cookie, verifies it is gone and clears
protected client state. The existing stateless model does not revoke a copied
token; such a token expires normally or is invalidated by signing-key rotation.

## Public compute limits

Public chat additionally requires both settings below. It fails closed if they
are absent or the budget ledger is unavailable; billing pages still work.

- `BILUN_PUBLIC_CHAT_DAILY_TOKEN_BUDGET`: positive integer selected for the demo's
  provider budget. This is a conservative reservation allowance, **not** exact
  token usage or a dollar budget. Reserve serialized input bytes plus maximum
  output before each provider call. There are no refunds for failed/cancelled
  requests. Set the provider account's own spending limit as appropriate.
- `BILUN_PUBLIC_CHAT_BUDGET_DB`: absolute path to a persistent SQLite file in a
  precreated, private, writable directory. Share it across workers and retain it
  across restarts/rollbacks; deleting it resets quota accounting. It is separate
  from the clinical billing cache and contains usage/admission metadata only.

The implementation bounds public chat at 15 requests/minute/client, two active
requests/client and four active requests overall, 90 seconds/stream, at most
three tool calls and four provider calls, 2,048 output tokens/call, and a
131,072-byte provider payload. Synchronous work has a bounded eight-worker pool;
timed-out workers retain their slot until their actual work ends. Public
validation has separate request/line/concurrency limits in the access boundary.

Rate limits use the ASGI client identity. Configure Uvicorn to trust forwarding
only from the actual loopback reverse proxy; never set forwarded allow-IPs to
`*`. The app does not trust arbitrary client-supplied forwarding headers.

## Health

Anonymous `/health` contains readiness fields only. Existing status codes remain
200/503 according to cache readiness. To inspect build/release identity, use a
verified developer session or `X-Bilun-Health-Token` with the configured operator
token. Source address alone never unlocks detail: public proxy traffic is also
forwarded from loopback. All variants use no-store caching. Export
`BILUN_HEALTH_PROBE_TOKEN` through the existing private environment mechanism; do
not paste it into a command line.

## Verification before public enablement

1. Run existing backend/frontend CI and permission/projection/browser tests.
   Auth tests must explicitly disable the test suite's default auth bypass.
   The reproducible frontend browser contract uses synthetic local identities
   and a stub API, alongside the real backend permission tests:

   ```bash
   cd frontend
   API_PROXY_TARGET=http://127.0.0.1:18281 npm run build
   npx playwright install chromium
   node scripts/test-access-browser.mjs
   ```

   Verify ports `18280`/`18281` are free first. The script starts and stops its
   own processes. Repeat billing smoke checks with the real staged backend as
   described below; the stub contract alone does not validate backend security.
2. Build the exact frontend artifact and check public assets:

   ```bash
   python -m scripts.ci.verify_public_assets --frontend frontend
   ```

   The verifier checks browser-served roots for private file types, source maps,
   private keys and literal configured secrets. It never prints matching
   content. This is a bounded gate, not a guarantee against every possible
   secret encoding or proprietary-logic leak. Inspect public HTML, RSC and API
   payloads too. Recheck retained prior assets; do not confuse availability
   verification with confidentiality verification. The CI frontend job runs
   the same check on every build.
3. Verify new developer login and retired credential/session rejection against
   the direct staged backend and the frontend proxy: forged-role denial,
   developer access, a retired session cookie refused and the former password
   refused, without calling the LLM. Keep a short-lived test developer cookie in
   an owner-only file, not in command-line arguments. The scripted probe that did
   this (`verify_public_billing_access.py`) was deleted with the strict release
   lane on 2026-10-28; the git tag `archive/strict-lane` holds it.
4. In the isolated candidate, enable the switch and configure the public chat
   ledger/budget; repeat these checks with public access on, and check public
   billing output before and after a developer warms the same cache. Use a
   fresh browser for billing, citations, evidence, reference tools and validation. Test chat
   with a controlled fake provider, plus bounded operational provider checks if
   authorized. Verify developer login, failed login/logout, logout/expiry,
   direct developer URLs, changed role cookies and another tab signing out.
5. A 401/403 from a developer API must stay an API denial, not a 200 login page.
   Check unknown routes/methods, encoded paths and stale clients as well.

## Activation and rollback

This PR does not deploy or rotate live secrets. Record the actual current live
pair and compatible rollback artifacts before release. At investigation time,
`3099`/`8002` were already live despite their candidate names; `/opt/bilun-frontend/current` was not the serving frontend.

Stage on verified unused loopback ports, with both the compiled frontend rewrite
and its server identity origin pointing to the staged backend.

Keep public access off while installing the new policy, projections, compatible
frontend, developer-only credential and coordinated signing configuration.
Verify the pair, developer access and detailed release health first. Enable
public billing only after the complete candidate passes the checks above.
Repeat them through the public proxy and monitor access failures, bounded
compute usage, errors and latency without logging credentials or chat bodies.

If protected fields leak, a permission check fails, officer workflows break or
compute load exceeds limits: disable the public switch on the backend first,
verify anonymous APIs are denied, and return the UI to login-gated operation.
Then diagnose or restore a compatible verified pair. Never put an old,
unfiltered backend behind an anonymously accessible frontend. Preserve rotated
developer credentials, signing keys and the persistent usage ledger. Verify
loaded/on-disk proxy routing, compiled rewrites, retained asset routes and exact
backend/frontend identities after either activation or rollback.
