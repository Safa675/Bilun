## Task: Remove check-up pricing (UI + API + JSON)

### Goal
Check-up pricing yüzeyini uçtan uca sil; `get_katsayi()` için kaynağı `sut_katsayi_history.json`’a taşı. Plan: `plans/billing/2026-07-28-remove-checkup-pricing-plan.md`.

### Subtasks
- [x] Onay: Phase 0 + full remove
- [x] Phase 0: `get_katsayi()` → `sut_katsayi_history.json` (`loaders/katsayi.py`)
- [x] Phase 1: backend route/schema/loader/catalog/tests/docs
- [x] Phase 2: frontend chip + section + i18n + API client
- [x] Phase 3: delete `data/gazette/sut_checkup_pricing.json`
- [x] Phase 4: pytest loaders + anestezi/refakatçi; `get_katsayi()==0.593`; route yok

### Out of Scope
- Synthetic cohort adı `"checkup"`
- ICD/keyword `"checkup"` sinyalleri
- Gap-closing control-checkup kuralı
- Lab prices section

### Review
- Katsayı: `resolve_current_katsayi()` history’den open-ended satır; fallback 0.593
- Silinen: checkup loader, `/api/checkup-pricing`, `CheckupPricingResponse`, FE section/chip/i18n, JSON
- Bilinçli bırakılan: synthetic kohort / diagnosis keyword `"checkup"`
