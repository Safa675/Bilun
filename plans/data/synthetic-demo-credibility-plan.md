## Task: Sentetik demo verisi — klinik/finansal inandırıcılık + bilinçli optimizasyon hataları

**Status:** Draft v2 (review feedback incorporated)  
**Priority:** P1 (showcase cohort + generator + UI) · P2 (registry scale-out)  
**Trigger:** `F-SENTETIK-HASTA-0003-011` — yanak tümörü kalemleri + `609270` safra fistülü paketi + `M23.2` tanı; paket satırı `billed=0` / `expected_payable=9000`; “Sunulan fatura” işlem ara toplamı paket **ve** kalem ödenecek tutarlarını üst üste topluyor (~₺11.900).

**Related plans:**

- `synthetic-data-v2.md` / `synthetic-data-v2-refactor.md`
- `payment-method-compliance-data-fix-plan.md`
- `patient-profile-per-bill-redesign-plan.md`
- `copay-ek1a-ek4d-scope-fix-plan.md`
- `sgk-uplift-roadmap.md`

---

## Problem (verified)

### İki ayrı hedef çakışıyor

| Hedef | Bugün ne oluyor |
|-------|------------------|
| Algoritmaların değerini göstermek | `billed_override`, çapraz EK kodları, çoklu hata aynı faturada |
| Demo / satış / güven | Klinik olarak saçma ICD+işlem+paket; finansal olarak çifte ödeme yolu |

### `0003-011` (`scenario_tag`: `sgk_optional_override_package_higher`)

| Kod | Faturalanan | Beklenen | Kategori |
|-----|-------------|----------|----------|
| 600150 | 1.100 | 1.100 | islem |
| 600160 | 1.800 | 1.800 | islem |
| 609270 | **0** | **9.000** | paket |

Üretici: `billed_override=0`, `payable_override=9000` (`generators.py` → `_pick_optional_override_demo_procedures`).

Algoritma doğru (strateji: kalem 2.700 vs paket 9.000 → `savings_try=6.300`). **Veri + UI kokusu:** hayalet paket satırı; çifte ödeme yolu toplamı; klinik uyumsuzluk.

### Kök neden

- Senaryo = rastgele kod pin’i; vignette yok.
- **`payable_override` alternatif yolu claim line’a yazıyor** — semantik karışıklığın özü.
- UI ham satırı gösteriyor; API/chatbot/export aynı parquet’i tüketiyor.

---

## Goal

1. **Tier A (showcase)** faturalar tıbbi ve finansal olarak bir bakışta anlaşılır.
2. **Optimizasyon hataları kalsın** — fatura başına tek birincil hikâye, MEDULA şeklinde.
3. **Kaynak veri düzelsin önce**; UI geçiş dönemi güvenlik ağı (Tier B/C legacy).
4. **CI:** `scenario_tag` + donmuş tutarlar; `claim_id` suffix değil.

**Out of scope:** Tam klinik pathway simülatörü; algoritma motoru değişikliği; tüm 50 hastayı Tier A yapmak.

---

## Claim line alan semantiği (zorunlu sözleşme)

> Bugün `payable_override` ile “alternatif paket/kalem yolu” claim line’a yazılıyor. **Bu plan bunu kaldırır.**

| Alan | Showcase anlamı | Nerede |
|------|-----------------|--------|
| `billed_amount_try` | MEDULA’ya **gerçekten sunulan** tutar | Claim line only |
| `expected_payable_try` | Bu sunuma göre SGK’nın **bu satır için** ödeyeceği tutar (`billed` ile tutarlı; red/katılım hariç) | Claim line only |
| Alternatif paket / kalem yolu | **Claim line değil** | `billing_strategy` → `package_total_try`, `itemized_total_try`, `savings_try` |
| Katalog referans fiyatı | Claim line değil (gerekirse `catalog_price_try` insight satırı — P2) | Strateji / repricing blokları |

**Hard rules (Tier A):**

- `billed=0` + `expected_payable>0` paket satırı **yasak**.
- Aynı faturada hem “tam paket payable” hem “tam kalem payable” satırları **sunulan** olarak **yasak**.
- `payable_override` yalnız `billed` ile uyumlu sunum için; alternatif yol için **kullanılmaz**.

**Tüketiciler (hepsi aynı parquet):** API `/patients/.../claims`, billing-report cache, OriginalBillView, optimizer export, chatbot context — **P1.2 UI tek başına yetmez**.

---

## Architecture principles

1. **Vignette = klinik kabuk + tek faturalama hatası.**
2. **Bir fatura = bir headline optimizasyon hikâyesi.**
3. **Sunulan fatura = hastane ne yaptı; Optimizer = ne yapmalıydı / ne kaçırıldı.**
4. **P1.1 (generator) → P1.2 (UI) sırası merge gate; tersine izin yok.**

### Üç katmanlı kohort

| Tier | Adet | Amaç | Plausibility |
|------|------|------|--------------|
| **A – Showcase** | **10** | UI hero, demo, dokümantasyon | Yüksek klinik + finansal |
| **B – Regression** | ~15–20 | CI golden, algoritma kanıtı | Orta; etiketli hata |
| **C – Stress** | kalan | Edge case, legacy pattern | Düşük; hero’da yok |

---

## Sprint demo’ları — tier ataması (0012–0033 ve yakınları)

Son sprint’lerde bilinçli pin’lenen hastalar. **Billing hatası anlatısı net** olanlar Tier A/B; klinik zayıf ama hata net olanlar Tier B.

| Patient index | Demo / `scenario_tag` (özet) | Tier | Not |
|---------------|------------------------------|------|-----|
| 0002 | `sgk_optional_override_itemized_higher` | **A** | P1.1 rewrite (0003 ile çift) |
| 0003 | `sgk_optional_override_package_higher` | **A** | P1.1 pilot |
| 0004 | blood uplift | B | uplift demo |
| 0005 | DRG uplift | B | |
| 0006 | material uplift | B | malzeme paket dışı |
| 0007 | care setting review | B | |
| 0008 | procedure addon | B | |
| 0009 | procedure capture gap | B | |
| 0010 | package adequacy | **A** | vignette: onkoloji/GI paket ailesi |
| 0011 | gazette repricing | **A** | klinik tutarlı kalabilir |
| 0012–0021 | MEDULA rejection playbook (`_MEDULA_DEMO_SPECS`) | **B** | billing hatası net; klinik orta |
| 0013 | session uplift | B | |
| 0014–0020 | drug indication §4.2 demos | **B** | onkoloji ICD pin’li; klinik orta |
| 0022–0033 | material prose / KDV / bundling / readiness | **B** | sprint L4.4; hata net |
| 0038 | `payment_method_compliance_demo` | **A** | compliance vignette (mevcut plan) |
| 0039+ | copay / EK-1A demos | B | copay plan ile |

**Tier A = 10:** 0002, 0003, 0010, 0011, 0038 + 5 vignette (aşağıdaki tablo — 0006/0009/0013/0029/copay showcase gibi mevcut yüksek-trafik demolar manifest ile sabitlenir).

---

## P1 — Minimal vignette tablosu (P1 ile birlikte, P2 registry öncesi)

**Dosya:** `data/synthetic/demo_vignettes.json` (yeni, küçük — `vignettes.py` P2’ye kalır)

Her satır: hasta indeksi, `scenario_tag`, ICD, branş, işlem kodları, paket adayı (varsa), `fault` tipi.

| Index | `scenario_tag` | Branş / ICD | Sunulan hata (`fault`) | Paket kodu |
|-------|----------------|-------------|------------------------|------------|
| 0002 | `sgk_optional_override_itemized_higher` | Ortopedi `M23.x` | `package_when_itemized_higher` — paket sunulmuş, kalem daha yüksek | EK-2C DRG_OVERRIDABLE (vignette’den) |
| 0003 | `sgk_optional_override_package_higher` | Ortopedi `M23.x` | `itemized_when_package_higher` — **yalnız kalem** sunulmuş | aynı aileden |
| 0006 | material uplift | Cerrahi yatış | `package_materials_unbundled` | billed paket + sarf ayrı |
| 0010 | package adequacy | Onkoloji/GI | küçük paket + büyük aday | tutarlı kod seti |
| 0011 | gazette repricing | Poliklinik | tebliğ öncesi liste fiyatı | — |
| 0013 | session uplift | Cerrahi seans | under-billed secondary | — |
| 0038 | payment_method_compliance | Yatış | `compliance_mandatory_itemized` | zorunlu paket + DRG_MANDATORY kalem |
| 0029 | (copay / EK-1A showcase) | Kronik | copay scope demo | — |
| … | 2 slot | TBD manifest | Tier A tamamlayıcı | |

**Kurallar:**

- 609270 **showcase’de pinlenmez**; EK-2C’den vignette’e uygun DRG_OVERRIDABLE seçilir. **609270 Tier C / regression stress olarak kalabilir.**
- İlk pilot anatomi: **ortopedi** (0002/0003); 600150/600160 diz/eklem vignette’ine map veya tam GI’ye taşı + kod seti değiştir.

---

## İnandırıcı billing hata kataloğu

| Kötü (bugün) | İyi (hedef) |
|--------------|-------------|
| 0 faturalanmış, 9000 beklenen paket satırı | Sunulan: yalnız kalem; optimizasyon: “paketle ₺X daha alırsın” |
| Paket + kalem payable toplamı | Tek sunulan yol; alternatif öneri |
| Rastgele kod + rastgele tanı | Aynı branş/anatomi |
| `billed_override=0` kısayolu | Aşağıdaki `fault` tipleri |

| `fault` | Sunulan claim shape | Optimizer bloğu |
|---------|---------------------|-----------------|
| `itemized_when_package_higher` | Kalem satırları, `billed=payable>0`; paket satırı yok | `optional_override` → paket |
| `package_when_itemized_higher` | Paket satırı gerçek tutarla; kalem yok veya paket içi | `optional_override` → kalem |
| `package_underbilled` | Paket `billed < catalog`, kalem yok | strateji / repricing |
| `compliance_mandatory_itemized` | Paket + DRG_MANDATORY kalem | `compliance_violation` |
| `package_materials_unbundled` | Paket + malzeme yüksek billed / 0 payable | material uplift |
| `gazette_stale_price` | Eski liste ile faturalanmış işlem | gazette repricing |
| `medula_rejection_*` | Playbook’a uygun satır + red olayı | medula playbook |
| `drug_indication_*` / `material_kdv_*` | Sprint demo pin (Tier B) | ilgili review blokları |

`billed_override=0` + `payable_override=full_catalog` → **deprecated** (Tier C / legacy test only).

---

## Phase P1 — Implementation (strict order)

### P1.1 — Generator rewrite (BLOCKER — before any UI)

**Dosyalar:** `generators.py` (`_pick_optional_override_demo_procedures`, `package_higher` / `itemized_higher`), `demo_vignettes.json`

**`package_higher` (0003 class):**

1. Ortopedi vignette; EK-2C’den uygun DRG_OVERRIDABLE paket kodu.
2. Sunulan: **yalnız kalem** satırları (`billed = payable > 0`, `category=islem`).
3. **Paket claim line üretme** (hayalet satır yok).
4. Strateji motoru paket vs kalem karşılaştırmasını üretir (`package_total_try`, `itemized_total_try`, `savings_try`).

**`itemized_higher` (0002):** simetrik — sunulan paket, optimizasyon kalem.

**Header / expected output senkronu (zorunlu):**

- `_reconcile_claim_header_totals()` (`generators.py` ~1376) paket satırı kaldırılınca **yeniden çalışmalı**.
- `beklenen_toplam_fatura_tutari_try` / `beklenen_toplam_odenebilir_tutar_try` = line sum ile uyumlu.
- `expected_rule_outputs` fatura düzeyi satırı (`satir_tipi=fatura`) güncellenmeli; eski “paket ici satirlar” assert’leri yeni hikâyeye map.

**Kabul (P1.1):**

- [ ] Tier A override faturasında `procedure_category=paket` satırı **yok** (veya billed>0 gerçek paket sunumu — `itemized_higher` için).
- [ ] Hiçbir Tier A satırında `billed=0` && `expected_payable>0`.
- [ ] Claim header toplamları = procedure+material+drug line toplamları.
- [ ] `expected_rule_outputs` fatura satırı header ile uyumlu.
- [ ] Billing strategy hâlâ `optional_override` + pozitif `savings_try`.
- [ ] API `/patients/.../claims` aynı temiz satırları döner (UI’den bağımsız test).

### P1.2 — OriginalBillView (safety net — after P1.1 only)

**Dosya:** `frontend/src/components/patient/OriginalBillView.tsx`

- İşlem ara toplamı: yalnız **sunulan** `billed` / `payable` (karşılıklı dışlayan yolları toplama).
- Tier B/C legacy: `billed=0` paket → insight + footnote.
- Sentetik etiketi: **yalnız** `scenario_tag` / manifest Tier A faturalarda (her zaman değil).

**Kabul:** Geçiş döneminde Tier B hâlâ uyarı gösterir; Tier A’da çifte sayım yok.

### P1.3 — `demo_manifest.json` + Tier A listesi

**Dosya:** `data/synthetic/demo_manifest.json`

```json
{
  "tier_a_patient_indices": ["0002", "0003", "0010", "0011", "0038", "..."],
  "default_landing_index": "0003",
  "scenario_by_index": { "0003": "sgk_optional_override_package_higher" }
}
```

- UI default landing manifest’ten; `claim_id` suffix’ine bağlı değil.
- Validator: Tier A için hayalet paket / çifte yol assert.

### P1.4 — Minimal vignette uygulaması (0002/0003 pilot + tablo genişletme)

- `demo_vignettes.json` → `_pick_*_demo` fonksiyonları okur (inline pin azalır).
- P2 `vignettes.py` registry’ye geçişte aynı JSON kaynak olabilir.

---

## Phase P2 — Scale-out (after P1 merge)

- `scripts/synthetic/vignettes.py` — typed `BillingVignette` dataclass.
- `scripts/synthetic/fault_injection.py` — shared fault helpers.
- `tests/unit/synthetic/test_vignette_golden.py` — `scenario_tag` golden; `test_tier_a_no_ghost_package_lines`.
- Kalan sprint demo’ları (0012–0033) vignette tablosuna incremental taşıma.

---

## Phase P3 — Docs + cache hygiene

- [x] `data/synthetic/README.md`: tier tablosu, alan semantiği, manifest.
- [x] Post-regen script: `scripts/synthetic/assert_tier_a_post_regen.py` (manifest Tier A → P1.1 kabul maddeleri).
- [x] Cross-link: `synthetic-data-v2.md`, `billing_bugfixes.md`.

---

## Implementation order (merge gate)

| Sıra | Ne | Neden |
|------|-----|-------|
| **1** | P1.1 generator + header/expected sync | Kaynak veri; API/chatbot/export |
| **2** | P1.4 `demo_vignettes.json` + 0002/0003 | En büyük fake algısı |
| **3** | P1.3 manifest | Hero path sabit |
| **4** | P1.2 UI | Tier B/C güvenlik ağı |
| **5** | P2 registry + golden | Ölçek |

**P1.2, P1.1 merge edilmeden açılamaz.**

---

## Acceptance (P1 merge gate — full)

- [ ] P1.1 tüm maddeler (hayalet satır, header sync, expected_rule_outputs, API parity).
- [ ] `demo_vignettes.json` + manifest: 10 Tier A index tanımlı.
- [ ] 0002 + 0003 override demosu vignette tablosuna uygun.
- [ ] P1.2: Tier A’da çifte sayım yok; Tier B legacy uyarı.
- [ ] Golden: `scenario_tag` + frozen `savings_try` band; claim id yok.
- [ ] `validate_sut_synthetic_data.py`: Tier A assert’leri eklendi.
- [ ] Regen + cache; manifest `default_landing_index` spot-check.

---

## Resolved defaults (v2)

| # | Karar |
|---|--------|
| 1 | Generator önce, UI sonra — **sıkı merge gate** |
| 2 | Claim line = sunulan only; alternatif yol = `billing_strategy` |
| 3 | Tier A = **10** hasta; manifest ile sabitlenir |
| 4 | İlk pilot: **ortopedi**; 609270 showcase’de pin yok |
| 5 | Sentetik etiketi: yalnız `scenario_tag` / Tier A manifest faturalarda |
| 6 | Sprint MEDULA/drug/material demo’ları: **Tier B** (hata net, klinik orta) |
| 7 | `billed_override=0` deprecated except Tier C |

---

## Manual test plan

1. Regen synthetic + `validate_sut_synthetic_data.py`.  
2. Manifest Tier A → Sunulan fatura + strateji; API claim JSON.  
3. Optimizer kohort — kurtarılabilir anlamlı.  
4. Tier B MEDULA 0012 — playbook çalışır; hero’da değil.

---

## Open questions (kalan)

1. 0002/0003 ortopedi vignette: mevcut 600150/600160 mi kalır yoksa diz-spesifik kod seti mi seçilir?  
2. Tier A’daki 2 boş slot: hangi mevcut demo’lar (0029 copay, 0009 capture, …)?  
3. `package_when_itemized_higher` (0002) sunumunda paket satırı `billed` = tam paket fiyatı mı, yoksa kısmi mi?
