## Task: Fix Local Test Failures (Auth Bypass)

### Goal
Fix 24 local test failures (10 smoke + 14 API) caused by local `.env` credentials overriding the `BILUN_AUTH_OPTIONAL` test bypass.

### Subtasks
- [x] Clear `BILUN_AUTH_USERNAME`, `BILUN_AUTH_PASSWORD`, and `BILUN_SESSION_SECRET` from `os.environ` at the top of `tests/conftest.py`.
- [x] Verify that tests now pass locally.

### Out of Scope
- Modifying actual authentication logic or API endpoints.

### Out of Scope
- Code changes outside of tests and pipeline script fixes.