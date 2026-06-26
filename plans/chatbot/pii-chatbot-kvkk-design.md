# B-C1: PII / Chatbot — KVKK Design Decisions

**Date:** 2026-06-22  
**Status:** Design complete (questions answered) — implementation out of scope here  
**Source finding:** [backend-bug-audit.md](../billing/backend-bug-audit.md) § B-C1  
**Out of scope (this doc):** consent UI, role-matrix implementation, DPA legal paperwork

---

## Problem statement

When a patient is selected, BILUN assembles a JSON runtime context containing identifiers, diagnoses (ICD-10), and billing amounts, then appends it to the system prompt and POSTs to OpenRouter (`llm.py:34-37`, `context.py:895-909`). There is no consent check, no field-level redaction, no ZDR routing, and `user_role` is client-supplied (`chat.py:110`, `frontend/src/lib/userRole.ts`).

Under KVKK, health and billing data tied to an identifiable person is **special-category personal data** (Kişisel Sağlık Verileri). Sending it to a US-routed third-party LLM aggregator without a documented legal basis is a regulatory exposure — regardless of whether the current cohort is synthetic.

---

## Q1 — Should patient-data chat be fully disabled or gated by consent flag?

### Decision

**Two-tier policy:**

| Mode | When | Patient workspace chat |
|------|------|------------------------|
| **Deny (default until compliance pack)** | Production, or any env with real patient data | Block external LLM calls when `patient_id` is set. Return a structured “patient chat unavailable” response; cohort/SUT-only chat remains enabled. |
| **Allow (gated)** | Org has signed DPA + technical controls (see Q3) + recorded consent | Permit patient-context LLM only when **both** server flags are true: `BILUN_CHAT_PATIENT_DATA=allow` **and** `BILUN_CHAT_EXTERNAL_LLM_CONSENT=true` (org-level). Optional per-request `consent_acknowledged: true` later. |

**Not recommended:** leaving patient-data chat unconditionally enabled while “we only have synthetic data” — the code path is identical for real data; synthetic is a dataset property, not a safety control.

### Rationale (code evidence)

- Patient context is injected whenever `patient_id` is truthy — no gate:

```895:909:src/bilun/chatbot/context.py
    if patient_id:
        context["patient_context"] = build_patient_context(data)
        ...
        context["billing_context"] = build_billing_context(...)
        if user_role == "dev":
            ...
                context["billing_report_json"] = raw_report
```

- `_get_api_key()` only checks key presence, not authorization to export health data (`llm.py:41-46`).
- Weekly brief and cohort chat (`patient_id=None`) are lower risk — aggregate counts, no per-patient ICD-10 in cohort context (`build_cohort_context`, `context.py:80-124`).

### Implementation sketch (future task)

1. Env: `BILUN_CHAT_PATIENT_DATA` ∈ `{deny, allow}` default `deny`.
2. Early return in `bilun_chat` before `_fetch_runtime_data` when `patient_id` and policy is `deny`.
3. When `allow`, require org consent env + (later) audit log row per session.
4. Auto-brief on patient page: same gate — `intent=auto_brief` still sets `patient_id` from the route.

---

## Q2 — Which roles can see patient data in chat?

### Decision

| Surface | `billing_officer` | `dev` |
|---------|-------------------|-------|
| **UI / API read** (patient profile, billing report) | Yes — core product role | Yes |
| **Cohort chat** (no `patient_id`, SUT/MEDULA questions) | Yes | Yes |
| **Patient-context to external LLM** | **No** until consent gate (Q1) passes | **No** by default; **Yes** only under gated allow + synthetic-only dev deploy OR production consent pack |
| **Dev repo tools** (`read_repo_file`, `grep_repo`) | No (already excluded) | Yes — no patient payload in tool args |
| **Patient billing tools** (`get_billing_report`, etc.) | Disabled on patient page today (`chat.py:269-280`) | Enabled — tool results re-enter LLM context |

**Critical fix (future):** `user_role` must be **server-derived** (auth/session), not `BilunChatRequest.user_role` from the client. Today the frontend can send `"dev"` freely (`sutChat.ts:74`).

### Rationale

- Product intent: billing officers need patient workspace UI and summarized billing — that is local, not LLM export.
- Dev role already gets fuller billing JSON (`chat.py:555`, `context.py:906-909`) but that increases PII surface sent to OpenRouter, not decreases it.
- Rule Database is already dev-gated in the UI (`userRole.ts:3`); chat should follow the same **server-enforced** pattern.
- Officer + patient page today: tools off, but **pre-fetched patient context still ships to the LLM** — the role split does not protect PII.

---

## Q3 — OpenRouter DPA / data residency status?

### Decision

**Current BILUN posture: not compliant for KVKK health-data export.** Treat OpenRouter as **blocked for patient-context** until a compliance pack is in place.

### Verified facts (OpenRouter docs + our code)

| Control | OpenRouter capability | BILUN today |
|---------|----------------------|-------------|
| DPA | Available for organizational/enterprise accounts (incorporated in ToS; third-party model providers may have separate terms) | **Not documented / not verified** in repo |
| BAA (HIPAA) | Not a standard offering for healthcare PHI routing | **N/A for SGK/KVKK but signals risk class** |
| Data residency | EU in-region routing (`https://eu.openrouter.ai`) — **enterprise by request** | Default endpoint `openrouter.ai` (`llm.py:36`) |
| Zero Data Retention | Account guardrail + per-request `zdr: true` + `provider.data_collection: deny` | **Not set** in `stream_chat_response` / `stream_chat_response_with_tools` payloads |
| Training opt-out | Account privacy settings + provider routing | **Not configured** in code |
| Sub-processors | Prompts route to upstream model providers (e.g. DeepSeek default `llm.py:38`) | Each provider needs separate legal review |

### Minimum compliance pack (before `BILUN_CHAT_PATIENT_DATA=allow`)

1. Signed OpenRouter DPA + inventory of enabled model providers and their retention/training policies.
2. Per-request ZDR + `data_collection: deny` in LLM payload; account-level ZDR guardrail enabled.
3. EU routing if processing must stay in EEA (KVKK cross-border transfer assessment).
4. Written KVKK legal basis (typically explicit consent or explicit contract with hospital data controller).
5. Audit log: patient_id hash, timestamp, model, byte-size of context, consent flag — no prompt content in logs.

**Status label for stakeholders:** *OpenRouter integration is suitable for SUT/regulatory text and aggregate cohort analytics chat; it is **not** cleared for identifiable patient health/billing payloads in the current configuration.*

---

## Q4 — Is anonymization (`patient_id` → "Patient A") sufficient?

### Decision

**No.** Replacing `patient_id` with a pseudonym is **necessary but not sufficient** for KVKK or for safe OpenRouter export.

### What still leaks after ID pseudonymization

| Field | Location | Why it matters |
|-------|----------|----------------|
| ICD-10 + disease names | `build_patient_context` qualifying_diagnoses (`context.py:319-323`) | Direct health data — special category |
| TRY amounts, claim lines, materials, procedures | `build_billing_context` / `billing_report_json` | Financial + clinical procedure fingerprint |
| `claim_id` (e.g. `F-SENTETIK-HASTA-0023-048`) | `page_context`, tools | Often re-identifies patient + encounter |
| User free-text | `messages[]` | Users paste names, TC fragments, ward notes |
| Tool round-trips | `get_billing_report(patient_id)` | Full report re-enters LLM context |

Pseudonymization under KVKK/GDPR requires that the person **cannot be identified** by reasonable means given available auxiliary data. Billing line items + diagnoses + dates for a hospital cohort rarely meet that bar.

### What would be required instead (if patient chat is ever allowed)

1. **Tiered context classes:** `sut_only` | `aggregate` | `patient_redacted` | `patient_full` — external LLM capped at `patient_redacted` or lower.
2. **Field allowlist** for external LLM: exactness flags, rule citations, category counts — not ICD-10 strings, not line-level amounts.
3. **Stable session pseudonym** (HMAC of patient_id + daily salt) so the model can refer to “this case” without reversible ID.
4. **User-message scrubber** before LLM (TC kimlik pattern, phone, email).
5. **Synthetic demo carve-out:** `PIPELINE_MODE=synthetic` may relax to pseudonym + redacted summary for internal demos only — still not a substitute for production controls.

---

## Recommended rollout sequence

1. **Immediate (B-C1 implementation task):** `BILUN_CHAT_PATIENT_DATA=deny` default; block patient-context LLM; keep cohort/SUT chat.
2. **Short:** Server-side role from auth; remove client `user_role` trust.
3. **Medium:** ZDR + `data_collection: deny` on all OpenRouter calls (even cohort — defense in depth).
4. **Before production patient chat:** DPA pack (Q3) + redaction tier `patient_redacted` (Q4) + consent UI (out of scope here).

---

## Success criteria (design done)

- [x] Q1 answered: default deny, gated allow with org consent + env flags
- [x] Q2 answered: billing_officer gets UI not LLM export; dev not exempt; server role required
- [x] Q3 answered: current OpenRouter wiring not KVKK-cleared; compliance pack enumerated
- [x] Q4 answered: pseudonym alone insufficient; redaction tier defined

---

## References

- Audit: `plans/billing/backend-bug-audit.md` — B-C1
- Context assembly: `src/bilun/chatbot/context.py`
- LLM transport: `src/bilun/chatbot/llm.py`
- Chat route: `src/bilun/api/routes/chat.py`
- OpenRouter ZDR: https://openrouter.ai/docs/guides/features/zdr
- OpenRouter privacy/logging: https://openrouter.ai/docs/features/privacy-and-logging
