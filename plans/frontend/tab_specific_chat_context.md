# Tab-Specific Chat Context & Tab-Scoped Chat Sessions

Connect the AI chatbot to authentic, section-relevant runtime data for each workspace tab (e.g. SUT rule engine catalog, clause coverage, and algorithmic gap metrics on **Kural Veritabanı / Rule Database** rather than unrelated patient billing amounts), and scope workspace chat sessions per tab so each section maintains its own dedicated chat history and briefing.

## User Review Required

> [!IMPORTANT]
> - **Kural Veritabanı (`rule-database`)**: The chatbot will receive live SUT rule database metrics (3.250 numbered clauses, 47 registered rule engines, 622 algorithmic gaps, drug indication prose status, and audit verdicts) and will talk about rule coverage and engine architecture instead of 50-patient cohort billing amounts.
> - **Tab-Scoped Chat Sessions**: Navigating between tabs (e.g. `Hastalar` -> `Kural Veritabanı` -> `Uyumluluk`) will switch to that tab's dedicated chat history and trigger a context-accurate briefing for the tab.

## Proposed Changes

### 1. Backend Chat Data Fetching (`src/bilun/api/routes/chat.py`)

#### [MODIFY] `src/bilun/api/routes/chat.py`
- Normalize incoming `active_tab` (handling `"rule-database"`, `"Rule Database"`, `"SUT Kural Veritabanı"`, etc.).
- When `active_tab == "rule-database"`:
  - Fetch rule catalog data via `rules_catalog.coverage_summary()`, `rules_catalog.fact_check_summary()`, `rules_catalog.list_rules()`.
- When `active_tab == "reference-tools"`:
  - Fetch reference tools catalog metadata.
- When `active_tab == "operations"`:
  - Fetch MEDULA rejections queue and status.

---

### 2. Backend Context Formatter (`src/bilun/chatbot/context.py`)

#### [MODIFY] `src/bilun/chatbot/context.py`
- Implement `build_rule_database_context(data: dict[str, Any]) -> str`:
  - Formats:
    - Registered Rule Engines (total, implemented, partial, reference-only)
    - Live Clause Corpus (total in force, numbered rule clauses)
    - Algorithmic Gaps (gap count, percentage, top gap categories: drug indications, payment methods, pricing, packaging, etc.)
    - Partial Engine Breakdown (`drug_indication_prose` encoded vs deferred vs gaps)
    - Fact Check Audit Rollup (compliant, partial, heuristic counts)
- In `build_bilun_runtime_context`:
  - For `rule-database`: inject `rule_database_context` and omit `cohort_context` so the model focuses exclusively on the SUT Rule Database.

---

### 3. Frontend Tab-Scoped Chat Sessions (`frontend/src/app/page.tsx`, `frontend/src/lib/sutChatSession.ts`)

#### [MODIFY] `frontend/src/lib/sutChatSession.ts`
- Add `sutWorkspaceChatSessionKey(tab: string): string` helper returning `bilun:workspace:${tab}`.

#### [MODIFY] `frontend/src/app/page.tsx`
- Use `const chatSessionKey = sutWorkspaceChatSessionKey(activeTab);` instead of a static single key for all tabs.

---

## Verification Plan

### Automated Tests
- Backend pytest: `pytest tests/unit/api/test_sut_chat.py`
- Frontend vitest: `npx vitest run`

### Manual / Live Verification
- Call `POST /api/chat` with `active_tab: "rule-database"` and `intent: "auto_brief"` -> Verify the response speaks about the SUT Rule Database (3.250 clauses, 47 rule engines, 622 gaps).
- Navigate to `http://localhost:3000/?tab=rule-database` in the browser -> Verify the chat dock loads the Rule Database briefing.
