## Task: Chatbot context + MEDULA refactor

### Goal
Dedup billing formatters, externalize MEDULA KB data to JSON, add formatter and search tests.

### Subtasks
- [x] Dedup `_append_billing_sections` in `context.py`
- [x] Split MEDULA data → `data/medula/*.json`; slim `medula_kb.py`
- [x] Add `test_medula_kb.py` and formatter snapshot tests
- [x] Run pytest on chatbot tests (15 pass; 1 pre-existing async tools failure)

### Out of Scope
- Splitting `context.py` into multiple files

### Review
- `context.py`: 723 → 642 LOC; billing logic unified via `_append_billing_sections(detail_level=...)`.
- `medula_kb.py`: 574 → 103 LOC; editorial content in `data/medula/*.json`.
- New tests: `test_medula_kb.py` (5), `test_context_formatters.py` (3).
