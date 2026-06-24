## Task: Frontend Türkçe lokalizasyon düzeltme — gömülmüş İngilizce jargonu temizle

### Goal
Frontend'deki Türkçe metne gömülmüş İngilizce teknik jargonu (uplift, pipeline, manifest, prose, Tier C, dispense, corpus, prospektif, vs, ingest, triyaj, Aksiyon, profil, analitik, varyant) saf Türkçeye çevir; 2 tamamen çevrilmemiş string'i düzelt (DRG uplift, Malzeme uplift); configContext.tsx'teki hardcoded İngilizce fallback label'ları boş/neutral'a çevir. Co-author yok.

### Subtasks
- [x] Plan: 2 paralel Explore audit + terminoloji sözlüğü + kullanıcı onayı (purist Türkçe)
- [x] Faz 1a — billing.ts: uplift→artış, dispense→dağıtılmış, ingest→içe aktarım, corpus→derlem, prospektif→öngörüsel, vs→–
- [x] Faz 1b — sections.ts: fact-check→denetim, pipeline→işlem hattı, manifest→bildirim, Tier C→C kademesi, prose→düz metin, optimizer→optimizasyon, Non-algorithmic→Algoritmik olmayan
- [x] Faz 1c — optimizer.ts (KPI→performans göstergesi, prose, vs, prospektif), api.ts (dispense), operations.ts (triyaj→acil ayıklama, ingest, Aksiyon→Eylem), patient.ts (vs, profil→durum), common.ts (analitik→çözümleme), designSystem.ts (varyant→değişken)
- [x] Faz 1 ek — optimizer.ts:86 + sections.ts:235 analitik→çözümleme (tutarlılık)
- [x] Faz 2 — configContext.tsx: FALLBACK_CONFIG label/notice İngilizce'sini boş string'e çevir (dead code olduğu kanıtlandı: AppTopBar sadece mode==='synthetic_demo' render ediyor, fallback mode==='unavailable' → null döner; risk_tiers/directions hiçbir bileşende render edilmiyor)
- [x] Faz 3 — tsc clean, vitest 140 passed, build succeeded

### Out of Scope
- Backend /api/frontend-config lokalizasyonu (production label'ları backend'den geliyor)
- EN dosyaları (zaten İngilizce)
- Test assertion metinleri
- Marka/kısaltmalar (BILUN, SUT, SGK, MEDULA, DRG, EK-, ICD-10, INN, KDV)

---

## Task: Fix claim validator missing SUT code input + diagnose katsayı display

### Issue A — Katsayı shows "1" (NO CODE CHANGE REQUIRED)

**Verified facts (direct backend calls, not assumptions):**
- `data/gazette/sut_checkup_pricing.json` meta.katsayi == 0.593 (committed 1e253e0, working tree clean)
- `catalog.get_katsayi()` returns 0.593
- `pricing.get_checkup_pricing()` returns katsayi: 0.593
- Frontend `CheckupPricingSection` displays `fmtNum(data.katsayi)` — pure passthrough, no hardcode
- No "1" literal exists anywhere in the checkup path

**Root cause:** Stale backend process in memory (lessons.md 2026-06-19 pattern). Right now
NO backend is on :8000; dev server proxies to :8001 (next.config.ts:4). A backend started
against an older JSON held katsayi=1 in its module-level `_checkup_cache` (checkup.py:15).

**Action:** Clean backend restart. Do NOT hardcode 0.593 in frontend — that masks future
gazette updates and violates the "no fabricated numbers" rule. Report this to the user.

### Issue B — Claim validator has no SUT code input (REAL BUG, frontend fix)

**Verified facts:**
- Backend `price_material_lines` (materials.py:64-65): material with no `code` ->
  notes="material code required for exact EK-3 pricing", source="missing_code",
  exactness_status=missing_exact_inputs. This is the error the user sees.
- `materials.py:55-56`: name drives bundling/exclusion rules; code drives exact EK-3 pricing.
  Both are meaningful; they are complementary, not redundant.
- `SutMaterialItem` (sut.ts:36-41) already has optional `code?` — wired in API client.
- `EMPTY_MATERIAL` (shared.tsx:191) omits code.
- `ClaimValidatorSection.tsx:206-227` material row: inputs for name/unit_price/qty only.
- `ClaimValidatorSection.tsx:100`: `validMaterials = filter(name !== "")` — currently
  requires a name to even submit.

**Fix:**
- Add a `code` input to the material row (SUT/EK-3 material code).
- Update `EMPTY_MATERIAL` to include `code: ""`.
- Loosen validity gate: a material is submittable if it has a name OR a code.
- Adjust the row grid template (4 cols -> 5 cols) so the new field fits.
- Add i18n keys: `code` label + placeholder, TR + EN.

### Subtasks
- [ ] shared.tsx: add `code: ""` to EMPTY_MATERIAL
- [ ] ClaimValidatorSection.tsx: add code input to material row; widen grid template
- [ ] ClaimValidatorSection.tsx: relax validity filter to name OR code
- [ ] messages/tr/sections.ts + messages/en/sections.ts: add `code` + `codePlaceholder`
- [ ] tsc --noEmit + eslint + vitest green

### Out of scope
- Katsayı code (backend + data are already 0.593; restart fixes the display)
- Backend rule engine / materials.py (correct by design)
- Procedure-code lookup (already works)

### Verification
- Manual: enter a material with name + EK-3 code -> no "material code required" note,
  priced from ek3_code source. Enter code only -> still submittable.
- tsc + lint + 140 vitest green.
