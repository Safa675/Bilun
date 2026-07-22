# Plan: SUT Raporu Frontend Düzeltmeleri — Motor Tipi Rozeti, Tablo Birleştirme, Etiket Doğruluğu

**Date:** 2026-07-22
**Status:** Approved — implementing
**Scope:** 3 somut düzeltme (revize edilmiş)
**Öncül:** Kod incelemesi + plan değerlendirmesi (container motor-ayrımı iddiası yanlış çıktı; Fix 1 map ve Fix 2 şema düzeltildi).

## Goal
Kullanıcının raporu okurken üç sorusu net cevaplanır hale gelsin:
1. **"Bu bulgu uyumluluk riski mi, gelir fırsatı mı?"**
   → `RecommendedActionsPanel` satırlarında tip rozeti (compliance / opportunity / informational)
2. **"Hangi prosedürlerde sorun var, hangilerinde yok?"**
   → Claim-level + ihlal satırları tek tabloda, status sütunuyla (heuristic tablo ayrı kalır)
3. **"Bu 'paket-bileşeni' etiketi gerçekten EK-3B-1 mi?"**
   → Option A: `is_bundled` vs `is_ek3b1_bundled` için dürüst etiketler; backend davranışı aynı

## Locked decisions (eski open questions)
1. **Fix 3:** Option A (etiket netleştir) — Option B ayrı görev.
2. **Fix 2 sıralama:** İhlaller üstte.
3. **Fix 1 kapsam:** Yalnızca `RecommendedActionsPanel` satır rozetleri — container etiketleri yok (gruplar motor-temiz değil: MaterialsPreCheck opportunities’ta, drug_indication reference’ta).

## Context (doğrulanmış)

### Bileşen yapısı
- Paylaşılan `<FindingCard>` YOK — bölümler `SutBillingReportSections.tsx` içinde kendi satırlarını çiziyor.
- `RecommendedActionsPanel` (`:152-258`) tek karışık liste; `surface` Chip zaten var (`:221-223`).
- `BillingReportGroup` (`page.tsx:630-693`) `compliance | opportunities | reference` — **motor ayrımı değil**; lab/copay compliance’ta, materials opportunities’ta, drug_indication reference’ta.

### Zaten doğru
- `copayShowsIlavaColumn` — tüm satırlar null/0 ise sütunu gizliyor. Dokunma.

### Motor ayrımı (backend)
- Validasyon / optimizasyon paketleri ayrı. Bu plan yalnızca sunum.

## Subtasks

### Fix 1: Tip rozeti — RecommendedActionsPanel

**Labels (dürüst, “SGK reddi” değil):**
- `compliance` → TR "Uyumluluk riski" / EN "Compliance risk" → Chip `danger`
- `opportunity` → TR "Gelir fırsatı" / EN "Revenue opportunity" → Chip `success`
- `informational` → TR "Bilgi" / EN "Informational" → Chip `neutral`

**Map — surface-primary (gerçek `billing_actions.py` değerleri):**
| Surface / kind | Type |
|---|---|
| `materials`, `drug_indication`, `lab` | compliance |
| `billing_strategy` + `compliance_violation` \| `mandatory_compliance` | compliance |
| `billing_strategy` + `optional_override` | opportunity |
| `*_uplift`, `procedure_capture_gap`, `drg_package_adequacy`, `gazette_repricing`, `care_setting_review`, `copay`, `yatak_puani` | opportunity |
| `medula_playbook`, `claim_checklist` | informational |
| unknown surface/kind | informational (fallback) |

- [ ] 1.1 Mesaj anahtarları — `findingTypes` in `billing.ts` tr/en
- [ ] 1.2 `getFindingType` + Chip variant helper in `recommendedActions.ts`
- [ ] 1.3 Render beside surface Chip in `RecommendedActionsPanel`
- [ ] 1.4 Unit tests for every surface in `collect_billing_actions`
- [ ] 1.5 Visual: synthetic patient report rows show badge

### Fix 2: Claim-level + ihlal tek tablo

**Şema:** claim-level sütunları **koru** (package/itemized/savings kaybolmasın). Status sütunu ekle. Violation satırları aynı şemaya map; eksik para alanları `—`.

| Sütun | Claim-level | Violation |
|---|---|---|
| Durum | Uyumlu / İncele | İhlal |
| Talep | claim_id | claim_id |
| Öneri | package/itemized chip | procedure name+code |
| Kural türü | recommendation_kind | — |
| SUT | badge | section |
| Yöntem | payment_method_kind | mandated_method |
| Paket / Kalem / Tasarruf | totals | — |
| Not | detail (secondary) | detail |

- Heuristic chapter table **ayrı kalır** (farklı şekil).
- Kırmızı "Ödeme yöntemi ihlali" alt-başlığı kalkar.
- Sıra: ihlaller → claim-level.

- [ ] 2.1 Status message keys + merge helpers
- [ ] 2.2 Rewrite `BillingStrategySection` claim+violation → one TableWrap
- [ ] 2.3 Empty-state: claim rows only still renders
- [ ] 2.4 Update `SutBillingReportSections.test.tsx`

### Fix 3: Option A — dürüst `is_bundled` etiketleri

- [ ] 3.1 `claim_materials.py`: note + `sut_section_id` by `is_ek3b1_bundled`
  - ek3b1: note mentions EK-3B-1; section `EK-3B-1`
  - flag-only: note says invoice/package flag, not regulatory annex; section omit EK-3B-1 (use empty → enricher needs explicit non-EK section or pass `sut_section_id` override like `"package_flag"`)
- [ ] 3.2 Frontend `bundledSeparate` header: remove unconditional "(EK-3B-1)"; optional split keys if two buckets preferred — **keep one section**, honest per-row notes + neutral header
- [ ] 3.3 Update scopeNotice if it overclaims for this list
- [ ] 3.4 Tests: both flag combinations produce correct notes/sections
- [ ] 3.5 `billing_actions` still prefers row `sut_section_id` — no hardcode override needed if row sets it

## Out of Scope
- Backend motor ayrımını değiştirme
- Her bölüme rozet / iki sekme UX
- `is_bundled` mimarisini yeniden düzenleme (Option B)
- Container group relabel / regroup
- İlave ücret sütunu

## Risks
- `getFindingType` wrong → mitigate with surface inventory tests
- Merge loses money columns → mitigated by keeping claim-level schema
- Label change translation load → tr/en parallel keys

## Verification criteria
1. Recommended actions: every row has type Chip (danger/success/neutral)
2. Strategy: one claim+violation table; no separate violation subheading; violations first
3. Bundled rows: no misleading EK-3B-1 when only `is_bundled`
4. `vitest` + relevant pytest green; `npm run build` if time
5. TR/EN messages updated in parallel

## Review
- Applied all three fixes per locked decisions (Option A, violations-first, panel-only badges).
- Fix 1: `getFindingType` uses real surfaces from `billing_actions.py`; Chip variants danger/success/neutral.
- Fix 2: Claim-level schema preserved + status + note; separate red violation subheading removed.
- Fix 3: Flag-only rows get `package_flag` section + non-annex note; EK-3B-1 only when `is_ek3b1_bundled`.
- Verification: vitest 55 pass, pytest claim_materials 8 pass, frontend `tsc --noEmit` clean.
