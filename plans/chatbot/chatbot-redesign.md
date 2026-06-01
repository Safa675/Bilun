# Chatbot Redesign Plan — IHP → Reimbursement

## Goal

Transform the BILUN chatbot from IHP clinical risk intelligence to a SUT reimbursement/SGK optimization assistant. The LLM must reason about copay exemptions, surcharge compliance, DRG pricing, billing optimization, claim validation, and gazette catalog lookups — not adverse-event risk scores.

## Current State Assessment

| Component | Lines | Status | IHP Contamination |
|-----------|-------|--------|-------------------|
| `prompts.py` | 65 | **LIVE** | System prompt says "clinical risk intelligence", has IHP INTERPRETATION section, references `ihp_probability`, `risk_contrib_*`, and ML model artifacts |
| `metadata.py` | 104 | **LIVE** | `get_chat_model_context()` returns dummy ML model metadata (training_auc, n_features, subscores — irrelevant for reimbursement) |
| `context.py` | 520 | **DEAD CODE** | Entire file unused, filled with IHP cohort/patient context builders, IHP trajectory, risk contributions. Zero importers. |
| `llm.py` | 170 | **LIVE** | Generic streaming client, no domain logic. Minor: logger named `ilay.chatbot`, HTTP-Referer hardcoded to `ilay.app` |
| `__init__.py` | 39 | **LIVE** | Exports `get_missing_context_blocks` (dead function), wraps `build_system_prompt` with dummy model context |
| `chat.py` | 266 | **LIVE** | `_build_bilun_runtime_context()` is inline, hardcoded, and limited to optimization + patient outcome — missing billing and claim validation context |
| `SutInlineAIPanel.tsx` | 420 | **LIVE** | Already SUT-branded, no changes needed |

## Design

### New Architecture

```
chat.py:bilun_chat()
  │
  ├─ _build_bilun_runtime_context()
  │   ├─ context.py:build_cohort_context()       ← NEW (SUT, not IHP)
  │   ├─ context.py:build_patient_context()      ← NEW (SUT, not IHP)
  │   ├─ context.py:build_billing_context()      ← NEW
  │   ├─ context.py:build_validation_context()   ← NEW
  │   └─ context.py:build_catalog_context()      ← NEW
  │
  └─ llm.py:stream_chat_response()
      └─ prompts.py:build_system_prompt()
          └─ metadata.py:get_chat_model_context()  ← SUT metadata now
```

### Subtasks

---

### 1. Rewrite `prompts.py` — SUT System Prompt

**File:** `src/bilun/chatbot/prompts.py`

Replace the entire system prompt. The new prompt must:

**Identity**
> "You are BILUN, the AI reimbursement optimization assistant for Turkish SGK/SUT healthcare billing. You help hospitals maximize legitimate reimbursement revenue by applying SUT rules."

**Data source awareness**
- Explain that each request includes runtime context built from BILUN's cache: optimization summaries, patient outcome data, billing reports, claim validation, and gazette catalog lookups.
- No mention of IHP, EBM artifacts, or ML model features.

**SUT terminology reference** (replaces IHP INTERPRETATION)
- Explain EK annex codes:
  - EK-1A: chronic disease copayment exemptions (98 ranges)
  - EK-2G: surcharge prohibition list (213 procedures)
  - EK-2C-1: gazette-mandated copay rates (465 procedures)
  - EK-2B: fee-for-service procedure pricing
  - EK-2C: DRG diagnosis-based package pricing
  - EK-3B-1: bundled consumables (54 categories included in procedure fee)
  - EK-3B-2: non-reimbursable materials (13 exclusion categories)
  - EK-4A: drug equivalence groups and discount tiers
- Explain `exactness_status`:
  - "exact" — real gazette data or exact claim lines
  - "partial_exact" — some data real, some estimated
  - "missing_exact_inputs" — unavailable, cite the `required_inputs_missing` and `unavailable_reason`
- Explain key terms: hemogram bundling, generic substitution, passivated drugs, DRG unbundling, copay exemptions, surcharges, MIAT restrictions, sağlık kurulu pre-auth

**Scope rules** (replaces IHP scope rules)
- SUT Analytics workspace → cohort exposure, patient outcomes, exactness caveats
- SUT Optimizer workspace → copay exemptions, recovery potential, exactness limitations
- SUT Patient Workspace → per-patient optimization findings
- SUT Billing Review → lab/drug/copay/strategy/material analysis

**Response rules**
- Write like a knowledgeable healthcare billing specialist speaking to a colleague
- Always cite `exactness_status` when amounts appear
- Never fabricate savings or claim lines
- When inputs are missing, explain what claim data is needed
- Do not give medical or treatment advice

**Remove all of:**
- IHP INTERPRETATION section
- ML model reference section (engine, target, feature count, subscores)
- "Causal wording" references
- `ihp_probability`, `risk_contrib_*` explanations
- "Clinical risk intelligence" identity

**Handle `model_context` gracefully:**
- The function still receives `model_context: dict` for backward compatibility
- If `build_id` is populated, include it as a reference
- Ignore ML-model fields that may still be in the dict

---

### 2. Repurpose `metadata.py` — SUT Metadata

**File:** `src/bilun/chatbot/metadata.py`

**`get_chat_model_context()`** — Replace dummy ML metadata with SUT-relevant metadata:
```python
def get_chat_model_context(active_build_id: str | None = None) -> dict:
    return {
        "product": "BILUN",
        "build_id": active_build_id,
        "gazette_version": None,        # to be populated from cache
        "claim_dataset": "synthetic_demo",
        "rule_engines": ["copay_exemptions", "temporal_price_validation"],
        "gated_engines": ["surcharge_eligibility", "copay_rate_eligibility", 
                          "drg_unbundling", "drug_discount_validation"],
        "billing_algorithms": ["lab", "drug", "copay", "strategy", "materials"],
    }
```

**Remove:**
- `has_active_model()` — ML-model concept, no SUT equivalent
- `has_performance_metrics()` — ML-model concept, no SUT equivalent
- `build_smart_notes_cache_fingerprint()` — dead code, zero importers

**`get_missing_context_blocks()`** — Rewrite for SUT workspace tabs:
- "analytics" → checks for `optimization_summary`, `patient_outcome`
- "optimizer" → checks for `optimization_summary`, `recovery_summary`
- "patient" → checks for per-patient data
- "billing" → checks for billing report
- Remove "causal", "performance", "validation" tab checks

---

### 3. Rewrite `context.py` — SUT Context Builders (Pure Formatters)

**File:** `src/bilun/chatbot/context.py`

Delete all 520 lines of dead IHP code. Build new SUT context builders that are **pure text formatters** — they receive pre-fetched data dicts, never import from `api/routes/`. This avoids all circular import risk.

**Data flow (dependency inversion):**
```
chat.py                         context.py (pure formatters)
  │                               │
  ├─ fetch data from              ├─ build_cohort_context(data: dict) → str
  │  optimization.py              ├─ build_patient_context(data: dict) → str
  │  patients.py                  ├─ build_billing_context(data: dict) → str
  │  billing.py                   ├─ build_validation_context(data: dict) → str
  │  validation.py                └─ build_catalog_context(data: dict) → str
  │
  ├─ gather into one dict
  └─ pass to build_bilun_runtime_context(data, active_tab, patient_id)
```

**`build_cohort_context(data: dict) → str`**
- Input: pre-fetched `data["optimization_summary"]`, `data["temporal_audit"]`
- Formats cohort-level plain text: copay exemption rate, top diseases, temporal price changes, surcharge/copay-rate status

**`build_patient_context(data: dict) → str`**
- Input: pre-fetched `data["patient_outcome"]`, `data["patient_optimization"]`
- Formats per-patient text: diagnoses, DRG summary, exemption status, optimization findings, exactness warnings

**`build_billing_context(data: dict) → str`**
- Input: pre-fetched `data["billing_report"]`
- Formats billing text: lab bundling savings, drug generic substitution, copay exemptions, material pre-checks, total recoverable

**`build_validation_context(data: dict) → str`**
- Input: pre-fetched `data["claim_validation"]`
- Formats claim validation text: bundling violations, exclusion violations, risk/savings amounts

**`build_catalog_context(data: dict) → str`**
- Input: pre-fetched `data["catalog_info"]` (gazette version, katsayi, catalog counts)
- Formats catalog reference text

**`build_bilun_runtime_context(data: dict, active_tab: str, patient_id: str | None) → str`**
- Orchestrates all builders above, assembles into JSON string
- `data` is the dict assembled by `chat.py`

**`_format_sut_section(header, value, exactness) → str`** — Helper:
- Always includes `[exactness: {status}]` badge
- If unavailable, renders `required_inputs_missing` and `unavailable_reason`

---

### 4. Refactor `chat.py` — Fetch Data, Delegate Formatting

**File:** `src/bilun/api/routes/chat.py`

Keep `_summarize_optimization()`, `_summarize_patient_outcome()`, `_summarize_patient_optimization()`, `_safe_context_block()` in `chat.py` — they call the API route functions (`get_optimization_summary()`, etc.) which have the actual cache access.

The new `bilun_chat()` endpoint flow:

```python
def _fetch_runtime_data(active_tab: str, patient_id: str | None) -> dict:
    """Fetch all data needed for context assembly. Lives in chat.py — this is
    the only place we import from sibling route modules."""
    data = {
        "optimization_summary": _safe_context_block(
            "Optimization summary",
            lambda: _summarize_optimization(get_optimization_summary()),
        ),
    }
    if patient_id:
        data["patient_outcome"] = _safe_context_block(
            "Patient outcome",
            lambda: _summarize_patient_outcome(
                get_bilun_patient_outcome(patient_id, include_expensive=True)
            ),
        )
        data["patient_optimization"] = _safe_context_block(
            "Patient optimization",
            lambda: _summarize_patient_optimization(
                get_patient_optimization(patient_id)
            ),
        )
    return data


async def bilun_chat(req, request):
    raw_data = await asyncio.to_thread(
        _fetch_runtime_data,
        req.active_tab,
        req.patient_id,
    )
    runtime_context = build_bilun_runtime_context(
        raw_data, req.active_tab, req.patient_id
    )
    # ... SSE streaming same as before
```

**Import change:** `chat.py` imports `build_bilun_runtime_context` from `src.bilun.chatbot.context` — a one-way dependency, no circular import risk.

---

### 5. Update `__init__.py` — New Public API

**File:** `src/bilun/chatbot/__init__.py`

New public surface:
```python
from .llm import stream_chat_response
from .prompts import build_system_prompt
from .metadata import get_chat_model_context
from .context import build_bilun_runtime_context

__all__ = [
    "stream_chat_response",
    "build_system_prompt",
    "get_chat_model_context",
    "build_bilun_runtime_context",
]
```

Remove: `CHAT_CONTEXT_SCHEMA_VERSION`, `_build_messages`, `get_missing_context_blocks` (no longer exported externally).

---

### 6. Minor `llm.py` Cleanup

**File:** `src/bilun/chatbot/llm.py`

- Change logger name: `ilay.chatbot` → `bilun.chatbot` (line 17)
- Change `HTTP-Referer`: `https://ilay.app` → `https://bilun.app` (line 100)
- No other changes needed — it's domain-agnostic

---

### 7. Update `chat.py` to Use New Context Builders

**File:** `src/bilun/api/routes/chat.py`

- Rename `_build_bilun_runtime_context()` → `_fetch_runtime_data()` — this now ONLY fetches data (calls `get_optimization_summary()`, etc.) and returns a dict
- Import `build_bilun_runtime_context` from `src.bilun.chatbot.context`
- Assemble runtime context: `build_bilun_runtime_context(raw_data, active_tab, patient_id)`
- The summarizer functions (`_summarize_*`, `_safe_context_block`) stay in `chat.py` since they need the route imports

---

### 8. Verify & Test

- Run `pytest tests/unit/ -q --ignore=tests/unit/api/test_sut_schema_exactness.py --ignore=tests/unit/api/test_sut_cache_concurrency.py`
- Run `cd frontend && npx vitest run`
- Verify zero IHP references in chatbot module with `grep -r "ihp_probability\|risk_contrib\|clinical risk\|IHP build\|model artifacts\|causal driver" src/bilun/chatbot/`
- Manual test: start server, send a chat message, verify the LLM responds with SUT/reimbursement domain knowledge

## Out of Scope

- No changes to `SutInlineAIPanel.tsx` — already SUT-branded
- No changes to `sutChat.ts` — generic SSE client
- No changes to billing/optimization/analytics domain logic
- No new API endpoints
- No LLM fine-tuning or model changes
- No integration of claim validation into chat flow (requires exact claim lines upload — separate feature)

## Circular Import Analysis

**Verified safe.** The dependency chain after refactoring:

```
chatbot/context.py       →  nothing (pure formatters, stdlib+json only)
chatbot/prompts.py       →  nothing (strings only)
chatbot/metadata.py      →  nothing (stdlib only)
chatbot/llm.py           →  chatbot.prompts, chatbot.metadata

api/routes/chat.py       →  chatbot.context, chatbot.llm,
                             api/routes.optimization, api/routes.patients

api/routes/optimization.py  →  src.bilun.domain.optimization
api/routes/patients.py      →  src.bilun.domain.analytics
```

No module in `chatbot/` imports from `api/`. No module in `api/routes/optimization` or `api/routes/patients` imports from `chat.py`. The `context.py` formatters are pure functions of their dict inputs — they never touch the cache, routes, or domain layer directly.
