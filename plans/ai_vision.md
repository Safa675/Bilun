# BILUN AI Vision

## Current State

### What we have

| Component | Status | Notes |
|-----------|--------|-------|
| `chatbot/llm.py` | Working | OpenRouter streaming SSE endpoint |
| `chatbot/prompts.py` | Working | ~70-line system prompt with SUT terminology, exactness rules, response rules |
| `chatbot/context.py` | Working | Four context builders: cohort, patient, billing, catalog |
| `chat/api/routes/chat.py` | Partially working | Fetches optimization + patient data. Billing context builder exists but is **never fed data** — `build_billing_context()` is called with empty dict |
| Frontend chat panel | Working | Always-on sidebar, has `active_tab` and `patient_id` params available |

### What's broken

`chat.py:177-202` — `_fetch_runtime_data()` fetches optimization summary and patient outcome/optimization, but never fetches the billing report. `build_billing_context()` in `context.py` has 114 lines of context formatting code that runs against an empty dict every time.

**Result:** The chatbot cannot answer "how much can we recover from patient 0039?" even though the billing report has `total_recoverable_try: 108,521.36`. It only knows optimization findings (copay exemptions, surcharge exposure), not actual billing savings.

### What's missing strategically

| Gap | Why it matters |
|-----|---------------|
| No MEDULA knowledge | The most common billing department question is "MEDULA rejected my claim, what do we do?" The chatbot knows SUT theory but not MEDULA error codes |
| Poor home/cohort patient disambiguation | Patient page chat already receives `patientId` from route state, but cohort/home pages have no active patient — the chat can't target a specific patient for billing queries without explicit selection |
| No tool-calling architecture | The LLM answers from context alone. It can't say "let me check the billing report for that" — the data must be pre-fetched |
| No SUT clause/law citation | Responses surface `exactness_status` (good) but do not cite specific SUT clauses, gazette dates, or legal sources that back each claim |

---

## Vision: Verified Intelligence for Reimbursement

### Principles

1. **Deterministic core is sacred.** All math, all SUT rules, all savings calculations stay in Python. The LLM never computes a number.
2. **LLM orchestrates, explains, and prioritizes.** It selects which verified outputs are relevant to the question and explains them in natural language.
3. **Every claim is traceable.** When the LLM says "patient 0039 has 108K TRY recoverable," it must be able to say "this comes from the billing strategy comparison on claim X, which compares package total Y against itemized total Z."

### Three-Layer Architecture

```
Layer 3: AI Communication (LLM)
         └─ Natural language, Turkish/English, context-aware
            └─ "Patient 0039 has 108,521 TRY in recoverable revenue.
               The biggest opportunity is copay strategy: they're exempt
               under EK-1A but being charged katılım payı on 14 procedures."

Layer 2: AI Orchestration (Tool-Calling LLM)
         └─ Routes questions to the right verified endpoint
            └─ "User asked about cost savings → call billing report endpoint"
            └─ "User asked about drug alternatives → call drug optimizer endpoint"
            └─ "User asked about MEDULA error → search MEDULA knowledge base"

Layer 1: Deterministic Core (Python)
         └─ All algorithms, rule engines, gazette lookups
            └─ Copay exemptions, surcharge, DRG unbundling, drug optimization,
               lab bundling, billing strategy, material pre-check
```

### What "AI replaces accountants" actually means (and doesn't)

**Does mean:** An AI that has read every SUT amendment, every MEDULA error code, and every EK-4A drug tier change, and can answer "what changed in the March 2026 SUT amendment that affects my cardiology department?" — a question no human can answer without 40 hours of reading gazettes.

**Does not mean:** An AI that invents reimbursement math, makes treatment decisions, or replaces the human who files the MEDULA claim.

The defensible moat is: **"The only Turkish-language AI that has actually read every SUT amendment and MEDULA error code."** That's not generic. That's not copyable without doing the same ingestion work.

---

## Implementation Plan

### Phase 1: Fix the Chat Context Gap (1-2 days)

**Goal:** Chat can answer billing questions with real numbers.

**What to do:**
1. Add billing report fetch to `_fetch_runtime_data()` in `chat.py` — when `patient_id` is present, fetch `/api/billing-report/{patient_id}`
2. Add a `_summarize_billing_report()` function alongside the existing summarizers
3. The billing context already exists in `context.py:269` — it just needs data fed to it

**Before:**
```
User: "What can we recover from patient 0039?"
Chat: "I don't have the billing report for this patient right now..."
```

**After:**
```
User: "What can we recover from patient 0039?"
Chat: "Patient 0039 has 108,521 TRY in recoverable revenue.
       Breakdown: 37 strategy actions (80,731 TRY from package vs itemized),
       14 copay corrections (27,790 TRY from missed EK-1A exemption).
       This patient is high priority. [exactness: exact]"
```

**Acceptance criteria:**
- [ ] `_fetch_runtime_data()` includes billing block when `patient_id` is present
- [ ] Chat response contains billing values with `exactness_status` from the API
- [ ] Chat response gracefully marks billing as unavailable when patient has no billing report
- [ ] Existing non-patient chat flows (cohort, analytics) are unaffected

**Files to touch:**
- `src/bilun/api/routes/chat.py` — add billing fetch + summarizer
- `src/bilun/chatbot/context.py` — already built, no changes needed

### Phase 2: Ingest MEDULA Manual into Chat Context (3-5 days)

**Goal:** Chat can answer "MEDULA rejected my claim, what does error X mean?"

**Scope:** Start with the top 20 MEDULA rejection codes and most common claim workflows first. Full manual ingestion can follow incrementally.

**What to do:**
1. Extract and chunk the top 20 rejection codes + their resolution procedures from the MEDULA manual (383 pages, already extracted to `/tmp/medula_full.txt`)
2. Build a `build_medula_context()` function that selects relevant MEDULA chunks based on the user's question
3. Either: embed the full manual in the system prompt (if it fits in context window), or implement simple keyword-based retrieval (error code → relevant section)
4. Add MEDULA terminology to `prompts.py`: error codes, DTO names, rejection reasons

**Approach:** Start simple. For v1, keyword-match the user's question against MEDULA section headers and include the top 3 matching sections in context. Don't over-engineer with vector DBs.

**Files to touch:**
- New: `src/bilun/chatbot/medula_kb.py` — MEDULA knowledge base loader + retriever
- `src/bilun/chatbot/context.py` — add `build_medula_context()`
- `src/bilun/chatbot/prompts.py` — add MEDULA terminology section
- `src/bilun/api/routes/chat.py` — include MEDULA context in runtime assembly

### Phase 3: Improve Patient Targeting and Active-Entity Disambiguation (1-2 days)

**Goal:** The chat panel provides useful context on every page — patient-specific context when a patient is active, cohort-level context otherwise.

**What to do:**
1. Patient page (`/patient/[id]`) already sends `patient_id` from route state — ensure the full context pipeline (optimization + billing + outcome) activates automatically
2. On cohort/home pages where no patient is active, surface cohort-level context (optimization summary, revenue recovery, top alerts) and prompt the user to select a patient for billing detail
3. Add a subtle indicator: "BILUN has context for patient 0039" vs "No patient selected — showing cohort overview"

**Files to touch:**
- Frontend: Chat panel component — watch route, auto-set context

### Phase 4: Verified Tool-Using Assistant (5-7 days)

**Goal:** LLM can call BILUN endpoints as "tools" rather than relying entirely on pre-fetched context.

**Architecture:**
```
User: "Which patients in the cohort have the highest lab savings?"

LLM decides: "I need to query the revenue recovery endpoint"
→ Calls: GET /api/revenue-recovery
→ Parses: savings_by_category.lab = 23,450 TRY
→ Explains: "The cohort has 23,450 TRY in lab savings across all patients..."

LLM decides: "I should check the top patients for detail"
→ Calls: GET /api/billing-report/{top_patient_id}
→ Explains: "Patient 0039 alone has 14,200 TRY in hemogram bundling savings..."
```

**Safety constraints:**
- LLM can ONLY call read-only GET endpoints. Never POST/PUT/DELETE.
- **Endpoint allowlist:** Only explicitly listed endpoints are callable. Unknown endpoints are rejected before execution.
- **Input validation:** Tool arguments must pass JSON schema validation before the request is made.
- **Circuit breaker:** If an endpoint returns errors 3 consecutive times, it's disabled for the conversation.
- **Per-call timeout:** Each tool call has a 5-second timeout. Slow calls are aborted, not retried silently.
- **Response size cap:** Tool responses are truncated to 8KB to prevent context window overflow.
- LLM must always report exactness_status from the response.
- LLM must cite which endpoint it called and what it returned.
- Numbers must be quoted directly from API responses, never computed.

**What to do:**
1. Define a tool schema for each BILUN endpoint the LLM can call (OpenAI function-calling format or equivalent)
2. Implement the tool-calling loop in `chatbot/llm.py` — if the LLM responds with a tool call, execute it server-side, feed the result back into context, continue
3. Keep the pre-fetched context as a fallback — tools are for dynamic follow-up questions
4. Add a rate limit on tool calls per conversation turn (max 3 tools per user message)

**Files to touch:**
- `src/bilun/chatbot/llm.py` — tool-calling loop
- New: `src/bilun/chatbot/tools.py` — tool definitions + execution
- `src/bilun/chatbot/prompts.py` — tool usage instructions

### Phase 5: Evidence-Linked Answers + Narrative Automation (future)

**Goal:** Every claim is traceable to its source. Auto-generate weekly briefs.

**What to do:**
1. Add SUT clause references to all algorithm outputs (e.g., `rule_source: "EK-1A, RG 15.02.2023"`)
2. Make the LLM cite these sources in responses: "Patient 0039 qualifies for copay exemption under EK-1A (RG 15.02.2023, clause 1.8.1) due to ICD-10 diagnosis E11.9."
3. Implement `POST /api/sut/weekly-brief` — auto-generate a natural-language summary of the week's recovery opportunities from the cohort data
4. Add a "human in the loop" mode: LLM drafts an action plan, user must approve before it's marked actionable

---

## Summary: What Changes When

| Phase | Timeline | Files Changed | User-Visible Impact |
|-------|----------|---------------|---------------------|
| 1. Fix chat context | 1-2 days | `chat.py` + summarizer | Chat can answer billing questions with real TRY amounts |
| 2. MEDULA ingestion | 3-5 days | New `medula_kb.py`, `context.py`, `prompts.py` | Chat can explain MEDULA error codes and rejection reasons |
| 3. Patient targeting | 1-2 days | Frontend chat panel | Chat automatically provides patient or cohort context based on active page |
| 4. Tool-using assistant | 5-7 days | `llm.py`, new `tools.py`, `prompts.py` | Chat can dynamically query endpoints, not just read pre-fetched data |
| 5. Evidence + briefs | Future | Multiple | Every claim traceable to SUT source; auto-generated weekly reports |

**Total Phase 1-4: ~14-21 days of work, ~6-8 files touched, no new infrastructure.**

---

## What We Don't Build

- **"AI that writes MEDULA claims"** — dangerous, legally risky, not the right problem
- **"AI that diagnoses patients"** — medical liability minefield, outside scope
- **"AI that invents SUT rules"** — violates the deterministic core principle
- **"Vector database for SUT"** — over-engineering for a 383-page document; keyword retrieval is sufficient
- **"Fine-tuned Turkish healthcare LLM"** — unnecessary cost; OpenRouter with good prompting already works
