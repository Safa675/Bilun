# Plan: Bill-Aware, Tool-First BILUN Chat

**Status:** Draft  
**Target:** Fix patient-workspace chat blindness (e.g. `audit_exposure_try` visible in UI but denied by assistant)  
**Principle:** *Cursor-style = on-demand reads via tools + what’s on screen — not hand-maintained summarizers per field.*

---

## 1. Problem statement

### Repro (SENTETIK-HASTA-0023)

User on **patient workspace**, bill **F-SENTETIK-HASTA-0023-048** selected, UI shows:

| KPI | Value |
|-----|-------|
| SGK artışı | ₺0,00 |
| Denetim riski (aşırı faturalama) | ₺41.103,79 |
| Muafiyet farkı | ₺18.065,08 |

User asks chat: *"Denetim riski ₺41.103,79 bu ne demek?"*

Assistant answers: data not in context; patient recoverable ₺0; suggests another page.

### Root causes (verified in code)

| # | Gap | Location |
|---|-----|----------|
| R1 | Patient chat **disables tools** | `chat.py` `_should_use_chat_tools` → `patient_id is None` only |
| R2 | Chat fetches **patient-level** report only | `_fetch_billing_report` → `get_patient_billing_report(patient_id)` |
| R3 | Ignores **selected bill** even when UI has it | `page_context` has no `claim_id`; server never calls `get_bill_billing_report` |
| R4 | `_summarize_billing_report` drops KPIs | No `audit_exposure_try`, `sgk_uplift_try`, `compliance_adjustment_try`, uplift blocks |
| R5 | `buildPatientWorkspacePageContext` sends 4 fields | Only `total_recoverable_try`, `priority`, `exactness_status` |
| R6 | `context.py` formatter omits audit / dual totals | `_append_billing_sections` = lab + copay + strategy + materials only |
| R7 | Tool schema stale | `get_billing_report` description says “4 algorithms” |
| R8 | Semantic confusion | `total_recoverable_try` == SGK uplift; model treats as “everything” |

---

## 2. Goals

1. Chat answers questions about **any KPI visible on the patient/bill billing summary**.
2. Chat respects **bill scope** when user has a claim selected.
3. **New billing fields** appear in chat without editing 3 summarizers — via page snapshot and/or full-report tools.
4. Keep **read-only**, **auditable**, **exactness-safe** behavior (no repo access, no Medula writes).
5. Latency budget: p95 chat first token &lt; 8s with ≤3 tool calls.

## 3. Non-goals

- Giving production chat **codebase / filesystem** access (Cursor dev agent model).
- Replacing deterministic billing engine with LLM reasoning.
- Auto-submitting Medula or changing claims.
- Removing cohort pre-fetch entirely (cohort context stays useful).
- Full 14-block narrative in every request (tools fetch detail on demand).

---

## 4. Target architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (patient workspace)                                    │
│  React state: activeBillingReport, selectedClaimId, optimization │
│       │                                                          │
│       ▼  page_context.visible_billing (full KPI slice or report) │
└───────┼─────────────────────────────────────────────────────────┘
        │
        ▼ POST /api/chat
┌─────────────────────────────────────────────────────────────────┐
│  chat.py                                                         │
│  • Resolve scope: patient | bill (from page_context)             │
│  • Fetch billing: get_bill_billing_report OR patient report      │
│  • Tools ON for patient workspace (allowlisted subset)           │
│  • Slim runtime context (policy + page_view + cohort)            │
└───────┼─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  LLM (stream_chat_response_with_tools)                           │
│  • Prompt: money semantics + exactness rules                     │
│  • Optional tool calls: get_bill_billing_report, search_sut_…    │
└─────────────────────────────────────────────────────────────────┘
```

### Design rules (maintenance contract)

| Rule | Meaning |
|------|---------|
| **D1** | UI-visible billing KPIs live in **one typed shape** shared by UI + `page_context` |
| **D2** | Server **never** strips fields the UI already shows for `visible_billing` |
| **D3** | Tools return **same JSON** as REST APIs (no parallel summarizer) |
| **D4** | Prompt carries **semantics**, not field lists |
| **D5** | New `BillingActionReport` scalar → auto in snapshot if UI uses `BillingSummary` helper |

---

## 5. Data model: `VisibleBillingSnapshot`

Add a small shared contract (TypeScript + Pydantic mirror).

### 5.1 Fields (minimum)

```typescript
interface VisibleBillingSnapshot {
  scope: "patient" | "bill";
  patient_id: string;
  claim_id?: string;
  exactness_status?: string;
  priority?: string;
  action_count?: number;

  // Three money columns (UI BillingSummary)
  sgk_uplift_try: number;
  audit_exposure_try: number;
  compliance_adjustment_try: number;
  exemption_gap_try: number;          // derived like UI
  total_recoverable_try: number;      // alias sgk headline; document in prompt

  // Optional review metrics (show when > 0 in UI)
  capture_gap_try?: number;
  package_adequacy_review_try?: number;
  gazette_repricing_try?: number;
  medula_playbook_entry_count?: number;
}
```

### 5.2 Implementation source

Extract from existing `BillingSummary` logic in  
`frontend/src/components/patient/SutBillingReportSections.tsx` (lines ~150–170):

- `sgkUplift`, `auditExposure`, `complianceAdjustment`, `exemptionGapTotal`, etc.

New file: `frontend/src/lib/billing/visibleBillingSnapshot.ts`  
Export: `buildVisibleBillingSnapshot(report: BillingActionReport): VisibleBillingSnapshot`

### 5.3 `page_context` shape

```typescript
sections: {
  visible_billing: VisibleBillingSnapshot;
  workspace_header: { patient_id; description };
  // keep lightweight flags for outcome/optimization loaded
}
```

Deprecate fat-fingered `billing_report: { total_recoverable_try only }` — replace with `visible_billing`.

---

## 6. Backend changes

### Phase A — Bill-aware fetch (no tool change yet)

**File:** `src/bilun/api/routes/chat.py`

1. Add `_resolve_billing_scope(page_context, patient_id) -> tuple[Literal["patient","bill"], str | None]`  
   - `claim_id` from `page_context.sections.visible_billing.claim_id` or legacy `billing_report.claim_id`.

2. Replace `_fetch_billing_report`:

```python
def _fetch_billing_report(patient_id, page_context):
    scope, claim_id = _resolve_billing_scope(page_context, patient_id)
    if scope == "bill" and claim_id:
        payload = get_bill_billing_report(patient_id, claim_id)
    else:
        payload = get_patient_billing_report(patient_id)
    return _safe_context_block("Billing report", lambda: payload)  # Phase B removes summarize
```

3. Pass `page_context` into `_fetch_runtime_data` jobs (already done).

**Verify:** Unit test with mocked `get_bill_billing_report` — when `claim_id` in context, patient endpoint not called.

---

### Phase B — Stop stripping billing for patient chat

**Option B1 (recommended):** Pass **full serialized report** to context when `intent=user_question`.

- Remove `_summarize_billing_report` call for patient billing fetch; use API payload as-is (already JSON-safe).
- Keep `_summarize_billing_report` only for `auto_brief` if token budget requires it.

**Option B2 (lighter):** Extend `_summarize_billing_report` with all `VisibleBillingSnapshot` fields + top-level scalars from `BillingActionReport`.

Prefer **B1** for D3/D5 compliance.

**File:** `src/bilun/chatbot/context.py`

1. Add `_append_billing_headline_kpis(lines, report)` before block sections:

   - SGK artışı → `sgk_uplift_try` / `total_recoverable_try`
   - Denetim riski → `audit_exposure_try`
   - Uyumluluk düzeltmesi → `compliance_adjustment_try`
   - Muafiyet farkı → copay waiver total (same formula as UI)
   - Footnote text from `billing.dualTotalsFootnote` (static in prompt)

2. Extend `_append_billing_sections` **only** for detail lists user might ask about:

   - Phase B2-minimal: headline KPIs only (answers 90% of “what does X mean?”)
   - Phase C: add session_uplift, capture_gap, medula playbook **summary lines** when `> 0` (not full opportunity arrays unless tool called)

3. Update `slim_page_context` / `_PAGE_SECTION_SUMMARY_KEYS`:

```python
"billing_report" → "visible_billing"  # all snapshot fields pass through
```

---

### Phase C — Patient workspace tools

**File:** `src/bilun/chatbot/tools.py`

1. Add tool `get_bill_billing_report`:

```json
{
  "name": "get_bill_billing_report",
  "parameters": { "patient_id", "claim_id" },
  "description": "Full billing report for one bill (claim). Use when page_view shows scope=bill or user asks about a specific fatura."
}
```

2. Map to `api.routes.billing.get_bill_billing_report`.

3. Update `get_billing_report` description:

   - Patient-level aggregate across all claims.
   - List all normative blocks (lab, copay, strategy, materials, SGK uplifts, capture gap, audit exposure, Medula playbook).
   - Remove “4 algorithms”.

**File:** `src/bilun/api/routes/chat.py`

4. Change `_should_use_chat_tools`:

```python
def _should_use_chat_tools(*, patient_id, intent) -> bool:
    if intent == "auto_brief":
        return False
    return True  # cohort AND patient
```

5. **Patient allowlist** (optional safety): filter `get_tool_schemas()` when `patient_id` set:

   - Allow: `get_bill_billing_report`, `get_billing_report`, `search_sut_clauses`, `search_medula_playbook`, `get_patient_optimization`
   - Deny on patient page: `get_revenue_recovery`, `list_patients` (noise)

   Implement via `get_tool_schemas(scope: Literal["cohort","patient"])` in `llm.py`.

**File:** `src/bilun/chatbot/llm.py`

6. Ensure tool loop works with patient context (already generic).

7. Increase `RESPONSE_SIZE_CAP` for billing tools only (optional): 16KB for `get_bill_billing_report` or truncate with `truncation_hint` field listing omitted block names.

---

### Phase D — Prompt semantics (stable policy)

**File:** `src/bilun/chatbot/prompts.py`

Add section **BILLING MONEY COLUMNS** (TR + EN examples):

```text
- total_recoverable_try and sgk_uplift_try = legitimate Kurum ödemesi uplift only (recoverable SGK increase).
- audit_exposure_try = denetim riski / over-billing exposure — NOT recoverable; clawback risk if non-compliant.
- compliance_adjustment_try = uyumluluk düzeltmesi (e.g. lab over-billing correction) — separate from SGK uplift.
- exemption_gap_try / copay waiver = muafiyet farkı — patient katılım correction; not SGK uplift.
- Never say a KPI is "not in context" when page_view.visible_billing or a tool result contains it.
- When page_view.visible_billing.scope is "bill", answer about THAT bill; do not substitute patient-level totals.
```

Update SCOPE RULES line for Billing Review to mention bill-scoped reports and audit exposure.

**File:** `src/bilun/chatbot/context.py` `assistant_rules`

Add: *"Prefer page_view.visible_billing for KPI labels the user sees; call get_bill_billing_report for line-level detail."*

---

## 7. Frontend changes

### Phase E — Page snapshot

**File:** `frontend/src/lib/billing/visibleBillingSnapshot.ts` (new)  
**File:** `frontend/src/lib/sutChatPageContext.ts`

```typescript
export function buildPatientWorkspacePageContext({
  patientId,
  outcome,
  optimization,
  billingReport,  // activeBillingReport ?? billingReport from page.tsx
}) {
  sections.visible_billing = billingReport
    ? buildVisibleBillingSnapshot(billingReport)
    : { scope: "patient", patient_id: patientId, ...zeros, loaded: false };
  // keep optimization_snapshot / outcome loaded flags
}
```

**File:** `frontend/src/app/patient/[id]/page.tsx`  
Already passes `activeBillingReport ?? billingReport` — no change except typed snapshot.

**Tests:** `visibleBillingSnapshot.test.ts`, extend `sutChatPageContext.test.ts` for bill scope + audit field.

---

## 8. Testing plan

### 8.1 Unit — backend

| Test | File |
|------|------|
| Bill scope selects `get_bill_billing_report` | `tests/unit/api/test_sut_chat.py` (new or extend) |
| `visible_billing` fields appear in `build_bilun_runtime_context` | `tests/unit/chatbot/test_context_formatters.py` |
| `get_bill_billing_report` tool routes correctly | `tests/unit/chatbot/test_tools.py` |
| Patient chat tools enabled | `tests/unit/api/test_sut_chat.py` |
| Prompt contains money column section | `tests/unit/chatbot/test_prompts.py` (new) |

### 8.2 Golden scenario (integration)

Fixture: patient `SENTETIK-HASTA-0023`, bill `F-SENTETIK-HASTA-0023-048`.

Assert runtime context JSON contains:

```json
"visible_billing": {
  "audit_exposure_try": 41103.79,
  "sgk_uplift_try": 0,
  "exemption_gap_try": 18065.08,
  "scope": "bill",
  "claim_id": "F-SENTETIK-HASTA-0023-048"
}
```

Mock LLM or snapshot-only test — no live API key required.

### 8.3 Manual QA script

1. Open patient workspace, select bill with audit exposure &gt; 0.  
2. Ask (TR): `Denetim riski ₺41.103,79 ne demek?`  
3. Expect: explains audit exposure, cites not SGK uplift, mentions unbundling/bundling risk, exactness if present.  
4. Ask: `Neden toplam kurtarılabilir ₺0?`  
5. Expect: SGK uplift zero but exemption gap / audit exposure separate.  
6. Deselect bill (patient aggregate) — chat should switch to patient-level totals.  
7. Cohort home — tools still work; `get_revenue_recovery` available.

---

## 9. Rollout

| Step | Flag | Behavior |
|------|------|----------|
| 1 | `BILUN_CHAT_VISIBLE_BILLING=1` | Frontend sends `visible_billing`; backend reads it |
| 2 | `BILUN_CHAT_BILL_FETCH=1` | Server bill-aware fetch |
| 3 | `BILUN_CHAT_PATIENT_TOOLS=1` | Tools on patient workspace |
| 4 | Remove flags | Default on |

Log in `chat.py` (existing): `scope`, `claim_id`, `audit_exposure_try` from snapshot, `tools_enabled`.

---

## 10. PR sequence

| PR | Title | Scope | Risk |
|----|-------|-------|------|
| PR-1 | `visible_billing` snapshot (FE + types) | Phase E | Low |
| PR-2 | Bill-aware billing fetch + full report in context | Phase A + B1 | Medium |
| PR-3 | Context formatters: headline KPIs + footnote | Phase B context | Low |
| PR-4 | Prompt money semantics | Phase D | Low |
| PR-5 | Patient tools + `get_bill_billing_report` | Phase C | Medium |
| PR-6 | Golden tests + docs | §8, README | Low |

Deploy PR-1+2+3 together for minimum fix of the reported bug. PR-5 adds Cursor-like on-demand depth.

---

## 11. Success criteria

- [ ] User question on audit exposure KPI answered correctly without “not in my context”.
- [ ] Bill-selected chat uses bill report `claim_id` in logs and context.
- [ ] `total_recoverable_try=0` no longer implies “no financial findings”.
- [ ] Adding a new scalar to `BillingSummary` + API requires **zero** `chat.py` summarizer edits if exposed via `buildVisibleBillingSnapshot`.
- [ ] `pytest tests/unit/chatbot/ tests/unit/api/test_sut_chat.py` green.
- [ ] No regression: cohort weekly brief (`auto_brief`) still tools-off and token-bounded.

---

## 12. Future (out of scope for this plan)

- **Generic page snapshot**: `page_context.sections` = serialized React section props for DRG table, invoice lines (heavy; use tools instead).
- **Tool registry from OpenAPI**: auto-register new GET routes tagged `chat-tool`.
- **explain_visible_kpis** single tool returning `VisibleBillingSnapshot` + i18n labels from `messages/tr/billing.ts`.
- **Agent loop** with planning for multi-step rebill workflows (human approval gate).

---

## 13. Files touched (checklist)

| File | Change |
|------|--------|
| `frontend/src/lib/billing/visibleBillingSnapshot.ts` | **new** |
| `frontend/src/lib/sutChatPageContext.ts` | visible_billing |
| `frontend/src/app/patient/[id]/page.tsx` | wire snapshot |
| `src/bilun/api/routes/chat.py` | bill fetch, tools gate, logging |
| `src/bilun/chatbot/context.py` | KPI headlines, slim_page_context keys |
| `src/bilun/chatbot/tools.py` | new tool, schema updates |
| `src/bilun/chatbot/llm.py` | optional patient tool filter |
| `src/bilun/chatbot/prompts.py` | money semantics |
| `tests/unit/chatbot/*` | new cases |
| `plans/chatbot/chatbot-redesign.md` | link to this plan |

---

## 14. Answer template (for QA / prompt examples)

When user asks about **Denetim riski (aşırı faturalama)**:

> Bu tutar **SGK artışı değil**; `audit_exposure_try` alanıdır. Seçili fatura ({claim_id}) için SUT uyumluluk denetiminde **aşırı faturalama / paketleme riski** olarak işaretlenen kalemlerin toplam TRY karşılığıdır (oturum, kan bileşeni, ödeme yöntemi, paketleme ihlalleri). Kurumun geri kazanabileceği meşru SGK artışı bu faturada ₺{sgk_uplift_try}. Muafiyet farkı (₺{exemption_gap_try}) ayrı bir düzeltici kalemdir.

This text should be producible from `visible_billing` alone without tools.
