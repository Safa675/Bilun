## Task: 64 Unwired Runnable Rules (Checklist + ICU)

### Goal
`fatura_inceleme_checklist` (63) + `icu_bundled_leakage` (1) için ürün kararına göre wire; kullanıcı checklist’i belge listesi, ICU’yu denetim/çift-fatura riski olarak görsün. Plan: `plans/billing/2026-07-28-unwired-64-rules-plan.md`.

### Subtasks
- [x] D1/D3/D5 onay: Checklist=A, ICU=denetim riski (engine), yüzey=A1
- [x] Phase 0: registry honesty + `icu_bundled_leakage` entry
- [x] Phase 1: `icu_bundled_leakage` → `analyze_claim` + test
- [x] Phase 2: checklist → `claim_submission_checklist` A1 merge + test
- [x] Phase 4: ilgili pytest yeşil
- [ ] (İleride) Phase 3: belge presence → A→B — bu PR’da yok

### Out of Scope
- `definitions_2_6` (kasıtlı non_algorithmic)
- `schemas.py` refactor
- Belge/EMR ingestion
- Checklist’i violation yapmak
- ICU’yu “daha fazla faturala” fırsatına koymak

### Review
- **ICU:** `engine.py` içinde `detect_icu_bundled_leakage`; registry `implemented`; `analyze_claim` integration test.
- **Checklist:** `claim_submission_checklist.py` A1 merge (`checklist_kind=documentation_requirement`); sadece `procedure_lines` varken; engine’e eklenmedi.
- **Testler:** icu + claim_readiness + wired_orphan + synthetic demo (0704 filtresi) geçti.
- **Frontend (2.7):** mevcut checklist UI item dict’lerini gösterir; `required_documents` özel render ayrı iş.
