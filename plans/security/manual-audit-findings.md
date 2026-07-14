# Bilun Manual White-Box Security Audit — Findings

**Date:** 2026-07-13
**Target:** `/home/safa/Documents/Bilun` (local repo, synthetic data, authorized self-audit)
**Method:** Four parallel subagent audits (SQLi, API auth/authz/IDOR, parsers/SSRF, secrets/config), each with file:line citations. Consolidated below.
**Context:** Strix automated scan was blocked by a Z.ai coding-plan endpoint policy (429/1113 on agent payloads); manual audit completed instead.

---

## Executive summary

| Surface | Result |
|---|---|
| **SQL injection (DuckDB)** | ✅ **Clean** — 0 vulnerable across 85 query sites. All parameterized + identifier whitelisted. |
| **API authentication** | ✅ **Present and fail-closed** — HMAC-signed session cookie, PBKDF2, constant-time verify. |
| **API authorization / IDOR** | 🔴 **CRITICAL** — 0 of 34 endpoints do authz; all 13 patient-scoped routes are IDOR-exploitable. |
| **Client-controlled role escalation** | 🟠 **HIGH** — `user_role` is client-supplied; unlocks un-redacted data + source-code-read tools. |
| **Parsers (XXE / zip-slip / DoS)** | 🟡 **Low (latent)** — unsafe patterns exist but behind a CLI/trusted-input boundary. |
| **SSRF** | ✅ **Clean** — no user-controlled URL reaches an outbound request. |
| **Secrets / config** | ✅ **Clean** — 0 committed secrets; env-only; comprehensive `.gitignore`; CI uses `secrets.*`. |

**Top-line:** The data layer, secrets, and input-parsing trust boundaries are solid. **The application has no authorization model** — every authenticated user can read every patient's billing/claims data, and any user can self-elevate to `dev` to read source code. If Bilun is (or will be) multi-user or ever reachable beyond a single trusted operator, this is the priority work.

---

## 🔴 CRITICAL findings

### C1 — No authorization; single shared secret → full dataset exposure
**Files:** `src/bilun/api/auth.py:1-16` (design), `src/bilun/api/__init__.py:89-127` (session gate)

The auth model is intentionally a single shared username/password ("Option A"). The session token carries only `username` + `expires_at` — no user ID, tenant, facility, or role. `grep` for `current_user`, `tenant`, `owner`, `allowed_patients` across `src/bilun/` returns zero authorization concepts.

**Impact:** Anyone who can log in can read every patient's data. No mechanism to distinguish user A's patients from user B's. Blast radius = entire dataset if the shared password leaks.

**Fix (depends on intent):**
- If genuinely single-tenant/internal: document as accepted risk + rotate the secret + restrict network access to `:8001` + set `secure=True` on cookie behind TLS.
- If multi-user/tenant ever: add per-user identities, bind `owner_id`/`tenant_id` to patient rows, add `Depends(verify_patient_access)` to every patient-scoped route.

### C2 — IDOR on all 13 patient-scoped REST endpoints
**Files:** `routes/patients.py:232,286,314`; `routes/billing.py:116,183`; `routes/optimization.py:203,249`

Every handler accepts an arbitrary `patient_id` (and/or `claim_id`) from the path and looks it up directly with no ownership check. Changing `patient_id` from one value to another returns that other patient's full billing/claims data.

| Endpoint | Leaks |
|---|---|
| `GET /api/patient/{id}/outcome` | DRG summary, episodes, clinical features |
| `GET /api/patients/{id}/claims` | All claims: dates, ICD-10, billed/payable TRY |
| `GET /api/patients/{id}/claims/{claim_id}` | Full procedures, materials, drugs, denials |
| `GET /api/billing-report/{id}` | Full billing recommendations + savings |
| `GET /api/billing-report/{id}/bills/{claim_id}` | Bill-scoped audit/uplift findings |
| `GET /api/patient/{id}/optimization` | Copay exemptions, diagnoses, ICD-10 chapters |
| `GET /api/patient/{id}/bills/{claim_id}/optimization` | Bill-scoped findings |

**Exploit:** Auth → `GET /api/patients` (full ID list) → iterate `GET /api/billing-report/{id}`. Fully scriptable bulk exfiltration.

**Note:** `optimization.py:282-289` verifies `claim_id` belongs to `patient_id` — but that's a consistency check, not authz (doesn't verify the requester may see either).

**Fix:** Add `Depends(assert_patient_accessible)` resolving the principal from the token + checking an access-control map. At minimum (single-tenant), add per-read audit logging so mass enumeration is detectable.

### C3 — IDOR via chatbot `/api/chat`
**File:** `routes/chat.py:518`

`bilun_chat` accepts `patient_id` in the request body and fetches the full billing report for it (`_fetch_billing_report_for_chat`, `chat.py:301-314`). No access check. This is an alternate, equally-ungated path to the same sensitive data — and because it returns an LLM narrative, it's even more attractive for bulk exfiltration (one request = a readable summary of a patient's finances).

**Fix:** Apply the same access-control dependency as C2, keyed on `req.patient_id`.

---

## 🟠 HIGH findings

### H1 — Client-controlled `user_role` enables privilege escalation + source disclosure
**Files:** `routes/chat.py:93-96,110,308-313,555`; `chatbot/tools.py:640-685,712,774-783,822-826`; `frontend/src/lib/userRole.ts:11`

The chat request body includes `user_role: Literal["dev","billing_officer"]`, parsed server-side with no binding to the authenticated identity:

```python
def _parse_user_role(value: str | None) -> UserRole:
    if value == "dev":
        return "dev"
    return "billing_officer"
```

Two consequences:
1. **Data redaction bypass:** when `dev`, `/api/chat` returns the *full* billing report payload instead of the summarized one (`billing_detail = "full"` at `chat.py:555`). Any user sends `"user_role":"dev"` → un-redacted data.
2. **Source-code disclosure:** `dev` advertises `read_repo_file` + `grep_repo` tools to the LLM (`tools.py:822-826`), which read repository source files. A user claiming `dev` can ask the chatbot to dump source (including `auth.py`, env-loading, any embedded comments/secrets).

**Secondary weakness:** `execute_tool_call` (`tools.py:640-685`) checks the tool allowlist + circuit breaker but **does not re-check `user_role`** before running dev tools — the gate is advisory (schema filtering), not enforced. If an LLM emits a `read_repo_file` call in a non-dev session (prompt injection, cached sequence), execution is not blocked.

The frontend stores role in `localStorage` (`userRole.ts:3,23-32`) and **defaults to `"dev"`** when unset (`userRole.ts:11`) — trivially editable in DevTools.

**Fix:**
1. Derive `user_role` server-side from the authenticated identity, not the request body.
2. Enforce the dev-tool boundary inside `execute_tool_call`: reject `_DEV_TOOL_NAMES` unless a server-derived principal is authorized.
3. Change the frontend default role to `billing_officer`.

---

## 🟡 LOW findings (latent — behind CLI/trusted-input boundary)

### L1 — XXE in docx parser (latent)
**File:** `scripts/sut/prose/extractor.py:44,323`

`from xml.etree import ElementTree as ET` then `ET.fromstring(document_xml)` on docx XML. `defusedxml` is not a dependency. CPython ≥3.7.1 disables external-entity resolution by default, so classic XXE exfiltration isn't currently exploitable — but inline DTD/entity-expansion ("billion laughs") DoS is. Input is operator-supplied (CLI script, not reachable from API).

**Fix:** `pip install defusedxml` and swap the import — drop-in compatible, explicitly forbids DTD/entity expansion.

### L2 — Zip-slip + zip-bomb in archive extraction
**File:** `scripts/sut/sut_fetch.py:96-98`

`zf.extractall(target_dir)` with no `..`/absolute-path sanitization and no uncompressed-size cap. A crafted zip could write outside `target_dir` or exhaust disk. Input is a CLI-argv URL (operator-supplied).

**Fix:** Iterate `zf.infolist()`, validate `(target_dir / name).resolve().is_relative_to(target_dir.resolve())`, cap `info.file_size` per entry + total.

### L3 — Unbounded memory in xlsx/parquet loaders
**Files:** `scripts/sut/convert_xlsx_to_parquet.py:234,239`; `src/bilun/domain/loaders/gazette.py:222`; `src/bilun/domain/claims/parquet_reader.py:42,54` + ~20 `read_parquet` sites

No size/row guards; `read_parquet(...).to_dicts()` fully materializes the table. Latent capacity risk for large claims exports. All inputs trusted today (operator SGK files / Bilun-generated artifacts).

**Fix:** Use `pl.scan_parquet(...).collect(streaming=True)` or `.head(N)` guards; for xlsx use `openpyxl(read_only=True)` + row ceiling.

---

## ✅ Surfaces verified clean

- **SQL injection** — 85 query sites reviewed; every value bound via `?`, every identifier gated by the `_validate_table_name` frozenset whitelist (`db/_internal.py:86-92`). The `api/` layer has only 2 raw SQL calls (`__init__.py:180`, `routes/patients.py:108`) — both parameterized. No SQL in `domain/`, `chatbot/`, or `scripts/`.
- **SSRF** — All outbound HTTP (`chatbot/llm.py`, `sut/embeddings.py`, `sut_fetch.py`, `sut_monitor.py`) targets hardcoded URLs or env-var-derived endpoints. No request-parameter reaches an outbound client.
- **Secrets** — 0 committed secrets (verified via `git log -S` pickaxe on all live fragments across `--all`). All secrets env-only. `.gitignore` comprehensive. CI uses `${{ secrets.* }}` throughout.
- **Auth integrity** — HMAC verify is constant-time; tokens can't be forged without `BILUN_SESSION_SECRET`. `BILUN_AUTH_OPTIONAL=0` in `.env` (gate active).
- **CORS** — restricted to `localhost:3000`, not `*`.
- **No `verify=False`/`ssl=False`/`DEBUG=True`** anywhere.

---

## Prioritized fix list

| # | Severity | Finding | Effort |
|---|---|---|---|
| 1 | 🔴 CRITICAL | C2 — Add authz to 13 patient-scoped routes (or accept single-tenant risk with audit logging) | Medium |
| 2 | 🔴 CRITICAL | C3 — Apply same authz to `/api/chat` body `patient_id` | Small |
| 3 | 🟠 HIGH | H1.3 — Frontend default role `"dev"` → `"billing_officer"` | Trivial |
| 4 | 🟠 HIGH | H1.1/H1.2 — Derive `user_role` server-side + enforce dev-tool gate in `execute_tool_call` | Medium |
| 5 | 🟡 LOW | L1 — `defusedxml` swap (one import) | Trivial |
| 6 | 🟡 LOW | L2 — zip-slip sanitization in `sut_fetch.py` | Small |
| 7 | 🟡 LOW | L3 — streaming/row-cap on parquet loaders | Small-Medium |

**Recommendation:** Treat C1/C2/C3 as a single authorization-model decision (what is Bilun's deployment/trust model?) rather than three independent patches — the fix shape depends on whether this is single-tenant internal or headed toward multi-user SaaS.

---

## Note on Strix (automated scan, not completed)

Strix setup was fully completed and verified end-to-end:
- Docker Engine installed, `ghcr.io/usestrix/strix-sandbox:1.0.0` (11 GB) cached.
- Z.ai coding-plan endpoint found (`api.z.ai/api/coding/paas/v4`, from `.github/workflows/pr-agent.yml`).
- SDK incompatibility patched (`openai.types.responses.response_usage.InputTokensDetails` — made `cache_write_tokens` optional; verified resolves the `ValidationError`).
- **Blocker:** Z.ai coding-plan endpoint rejects Strix's agent payloads (tool schemas, multi-turn function calling) with 429/1113 "insufficient balance," while accepting simple completions with the same key. This is a server-side policy on the plan endpoint, not a client-side bug.

If you later want to run Strix, the path is: a non-Z.ai provider key (OpenRouter/Gemini/OpenAI) → rewire `~/.strix/cli-config.json` → relaunch. The image is cached and the SDK patch is in place, so it would be a ~2-minute change. The manual audit above likely catches more than Strix would have on the IDOR/authz side (LLM scanners are weak on business-logic flaws), but Strix would add value on dynamic validation and classes this static audit didn't deeply probe (e.g., deserialization gadgets, header injection).
