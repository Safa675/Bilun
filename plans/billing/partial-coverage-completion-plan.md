## Task: Partial kural kapsamını tamamlama — coverage honesty + pilot corpus genişletme

**Status:** Wave 1 complete (2026-06-17); Wave 2 complete (2026-06-17)  
**Priority:** P1 (Wave 1 billing pilotları) → P2 (classify düzeltme) → P3 (drug indication ayrı epic)  
**Trigger:** Madde 8 kapatma değerlendirmesi — `gazette_repricing` motor hazır ama registry `partial`, 7 primary gap; diğer billing pilotları benzer durumda.

---

### Goal

1. **Dashboard gap sayısını dürüstçe düşürmek** — yanlış primary routing’i düzelt; gerçekten encode edilemeyen maddeleri `non_algorithmic` veya doğru kurala yönlendir.
2. **Billing pilotlarının ürün değerini artırmak** — gazette / procedure / material pairing corpus’unu genişlet; golden + sentetik demo koru.
3. **Registry `coverage_status` kararlarını netleştirmek** — “seed done” vs “implemented” ayrımını dokümante et.

**Out of scope:** `drug_indication_prose` Tier C tam encode (3863 gap — ayrı epic; bu planda yalnızca honesty sınırı).

---

## Mevcut durum (2026-06-17, `build_sut_coverage` canlı)

| rule_id | registry | primary gap | JSON / motor | Sorun özeti |
|---------|----------|-------------|--------------|-------------|
| `gazette_repricing` | partial | **7** | 2 kural seed; motor **tüm** fiyat geçmişi satırlarında çalışır | 7 gap = §2.6/§4.3/§6.x tebliğ meta metni; repricing değil |
| `procedure_pairing` | partial | **7** | 3 pilot kural | 7 gap = §1.9 sözleşme/ek ücret prose; add-on değil |
| `material_pairing` | partial | **15** | 7 pilot kural | 15 gap = §3.1 genel idari (firma, liste tanımı) |
| `medula_rejection_playbook` | partial | **48** | 1 şablon | 48 gap = tüm §1.7 provizyon maddeleri primary |
| `provizyon_medula` | partial | 0 primary | modül yok | `medula_rejection` ile çakışma |
| `lab_billing` | partial | **0** primary | hemogram + capture gap | registry partial ama gap yok |
| `drug_indication_prose` | partial | **3863** | 103 INN + manifest | Tier C deferred — bilinçli partial |

**Önemli bulgu:** Madde 8’deki “7 gap → 5–10 kod ekle” yaklaşımı **dashboard gap’lerini kapatmaz**. Gap’ler prosedür kodu eksikliği değil; **classify.py primary routing hatası**. Corpus genişletme billing fırsatını artırır; gap kapanması için classify + manifest/non_algorithmic gerekir.

---

## Mimari prensipler

1. **İki ayrı metrik:**
   - `registry.coverage_status` — motor + corpus olgunluğu
   - `has_algorithmic_gap` — SUT maddesi primary olarak partial/missing rule’a düşüyor mu
2. **Pilot JSON ≠ clause encode:** `gazette_repricing_prose.json` içindeki `procedure_codes` şu an runtime’da filtre **değil** (`detect_gazette_repricing_opportunities` tüm geçmişi tarar). Corpus genişletme ya dokümantasyon ya da bilinçli whitelist eklenmesi demek.
3. **Drug indication modeli:** `encode manifest` + registry `partial` kalır; dashboard’da “engine partial / clause encoded” ayrı gösterilir.

---

## Wave 1 — Billing pilot corpus (ürün, ~½–1 gün)

### W1.1 — Gazette repricing corpus

- [ ] Fiyat geçmişinden aday madenciliği: `get_price_history()` ile 2024–2026 arası **artış görmüş** EK-2B + EK-2C kodları (min 8–10 adet, demo 600150/609270 hariç).
- [ ] `gazette_repricing_prose.json` → 8–12 `rules[]` satırı (kod, catalog, `message_tr`, `sut_section`).
- [ ] **Karar:** Motor whitelist kullanacak mı?
  - **A (önerilen):** JSON yalnızca dokümantasyon + test seed; motor evrensel kalır.
  - **B:** `detect_*` içinde JSON’daki kod birleşimine filtre ekle (performans + scope kontrolü).
- [ ] Golden: `data/gazette/prose_rules/golden/gazette_repricing_batch_a.json` + `test_gazette_repricing_golden.py` (en az 3 kod, 90 gün penceresi, SGK headline hariç assert).
- [ ] Sentetik: Hasta 0011 korunur; isteğe bağlı 2. demo (609270 paket yatış, eski liste fiyatı).
- [ ] `test_sgk_uplift_synthetic_demos.py` — mevcut 0011 testleri yeşil.

**Kabul:** Demo 0011 + ≥3 golden; `gazette_repricing_try` SGK toplamına dahil değil.

### W1.2 — Procedure pairing (3 → 5–6 kural)

- [ ] §2.2.2.A.(5) adayları: mevcut 701450/701540/701530 dışında 2–3 yüksek hacimli trigger/add-on çifti (kolonoskopi/ÖGD ailesi).
- [ ] `procedure_pairing_prose.json` genişlet; Hasta 0008 demo güncelle veya 2. demo ekle.
- [ ] Unit: `test_procedure_addon_uplift.py` golden.

### W1.3 — Material pairing (7 → 10–12 kural)

- [ ] EK-3/C + EK-3/H/I mevcut 7 kurala 3–5 yüksek değerli procedure→material çifti.
- [ ] Hasta 0006 material uplift demo ile uyum kontrolü.

**Wave 1 kapatma:** Registry hâlâ `partial` olabilir; ürün demosu ve golden set tamamlanmış sayılır (“seed done + corpus v2”).

---

## Wave 2 — Coverage honesty / gap kapanışı (~1 gün)

Amaç: Wave 1’den bağımsız olarak dashboard **pricing 7 + procedure_pairing 7 + material_pairing 15 + medula 48** gap’lerini düşürmek.

### W2.1 — Classify primary routing düzeltmeleri (`classify.py`)

| Gap kaynağı | Düzeltme |
|-------------|----------|
| `gazette_repricing` ← §2.6, §4.3, §6.3–6.4 | `sut_section_prefixes` ekle: yalnızca `2.2`, `1.1` (liste fiyat); §6.x → `definitions` veya yeni `sut_amendment_meta` non_algorithmic |
| `gazette_repricing` keyword | “tebliğ” tek başına yetmesin; `("yeniden faturalandır", "liste fiyat", "ek-2")` AND benzeri sıkılaştır |
| `procedure_pairing` ← §1.9 | `_fallback_rule_id`: `1.9` → `surcharge_general` (zaten var); keyword skorunda §1.9 maddelerine procedure_pairing bonusunu kaldır |
| `material_pairing` ← §3.1 idari | Bent (3)(16) firma/duyuru metni → `non_algorithmic` veya `material_bundling_prose` (MUST_NOT değilse admin) |
| `medula_rejection_playbook` ← §1.7 tamamı | §1.7 fikra/bent → primary `provizyon_medula` + `non_algorithmic`; yalnızca keyword “red”, “hata kodu”, “fatura kayıt red” → playbook |
| `provizyon_medula` | `coverage_status` → `non_algorithmic` veya birleştir; modül yok |

- [ ] Her düzeltme için `tests/unit/scripts/test_sut_coverage.py` regression: gap count hedefleri (aşağı).

### W2.2 — Encode manifest (gazette + pairing)

Drug indication modelinin hafif versiyonu:

- [ ] `data/gazette/prose_manifests/L2.2_gazette_repricing_encoded_manifest.json` — kapsam: §2.2 liste fiyat / tebliğ sonrası yeniden fatura maddeleri (classify sonrası kalan gerçek primary’ler).
- [ ] `coverage.py`: `has_rule_encoding` — `gazette_repricing`, `procedure_pairing`, `material_pairing` için manifest clause_id seti.
- [ ] Dashboard / fact-check: “encoded clause” vs “registry partial” ayrı KPI.

### W2.3 — Registry status kararları

| rule_id | Hedef status | Koşul |
|---------|--------------|-------|
| `gazette_repricing` | **implemented** veya **partial + manifest** | Classify fix sonrası primary gap ≤2 veya manifest ile encoded işaretle |
| `procedure_pairing` | **partial** (pilot) | Gap ≤3; açıklama “§2.2.2.A add-on pilot” |
| `material_pairing` | **partial** (pilot) | Gap ≤5 |
| `medula_rejection_playbook` | **partial** (event-driven) | §1.7 admin primary kalktı; gap ≤5 (yalnızca gerçek red playbook maddeleri) |
| `lab_billing` | **implemented** | 0 primary gap zaten |
| `provizyon_medula` | **non_algorithmic** | Playbook ayrı |

- [ ] `rule_registry.py` + `docs/gazette/partial-coverage-scope.md` (1 sayfa honesty tablosu).

### W2.4 — Coverage rebuild

```bash
PYTHONPATH=. .venv/bin/python -c "
from pathlib import Path
from scripts.sut.prose.coverage import write_sut_coverage
write_sut_coverage(Path('data/gazette/sut_clauses.parquet'), Path('data/gazette/coverage'))
"
```

**Hedef metrikler (Wave 2 sonu):**

| rule_id | primary gap (bugün → hedef) |
|---------|----------------------------|
| gazette_repricing | 7 → **0–2** |
| procedure_pairing | 7 → **0–3** |
| material_pairing | 15 → **0–5** |
| medula_rejection_playbook | 48 → **0–5** |
| Toplam algorithmic_gaps | 4090 → **~3900** (drug indication domine) |

---

## Wave 3 — MEDULA playbook operasyonel genişletme (opsiyonel, ~1 gün)

Gap kapanışından ayrı; ürün değeri.

- [x] Hastane feedback / bilinen top-10 MEDULA `sonuc_kodu` → `rejection_playbook.json`
- [x] Sentetik: 1–2 ek demo red (`payment_method` planındaki pattern)
- [x] Kuyruk tablosu filtresi testleri

**Kabul:** ≥5 şablon; en az 2 sentetik red olayı.

---

## Wave 4 — Drug indication (ayrı epic — bu planda yalnızca sınır)

- Registry **`partial` kalır** (Tier C 549 deferred).
- [x] Dashboard footnote: gap’lerin ~%94’ü bilinçli `drug_indication_prose` → Sprint 0 `gap_composition` panel (~99.6% canlı).
- [x] Malzeme partial engines panel: `material_bundling_prose` + `specialty_materials_prose` encoded vs manifest KPI.
- [x] §5 / RG amendment / provizyon scope closure: NaN-safe actionable signal + classify §5/§6 routing.
- [x] Phase 6 Sprint 1 (28 Tier A + 11 Tier B pending): **131 rules**, manifest tier A/B pending **0** — `drug-indication-4.2.14.C-expansion-plan.md`
- [x] Sprint 2 material demos: **0021–0024** (§3.3 optik/ortopedi + §3.1 ihale + KDV ceiling) + billing report E2E tests
- [x] Sprint 3 MEDULA playbook: **10 templates** + synthetic demos **0012, 0018, 0025–0032** (1 per `sonuc_kodu`)
- [x] Sprint 4 claim readiness: **known_codes sync** (10 playbook codes) + CSV draft ingest + proactive checklist (**0033** demo)

---

## Madde 7 / 8 kapatma kararı (bu plan sonrası)

| Madde | Karar |
|-------|-------|
| 7 — copay | ✅ Kapat (tamamlandı) |
| 8 — ek2c DRG locked | ✅ Kapat (51 kod, implemented) |
| 8 — gazette repricing | Wave 1 bitince **“corpus v2 done”**; Wave 2 bitince **kapat** veya **partial + manifest** (honesty doc ile) |

---

## Test planı

```bash
pytest tests/unit/domain/prose_rules/test_gazette_repricing.py \
       tests/unit/domain/billing/test_gazette_repricing_wiring.py \
       tests/unit/domain/billing/test_sgk_uplift_synthetic_demos.py \
       tests/unit/scripts/test_sut_coverage.py -q
```

Manuel:
1. Hasta 0011 — gazette bölümü, SGK headline’da 0.
2. Rule Database — gazette_repricing satırı: status + matched clause sayısı.
3. Coverage dashboard — pricing gap 7→hedef.

---

## Dosyalar

| Alan | Path |
|------|------|
| Classify | `scripts/sut/prose/classify.py` |
| Coverage | `scripts/sut/prose/coverage.py` |
| Registry | `src/bilun/domain/sut/rule_registry.py` |
| Gazette motor | `src/bilun/domain/prose_rules/gazette_repricing.py` |
| Corpus | `data/gazette/prose_rules/gazette_repricing_prose.json` |
| Manifest | `data/gazette/prose_manifests/L2.2_gazette_repricing_encoded_manifest.json` (yeni) |
| Sentetik | `scripts/synthetic/generators.py` |
| Plan | `plans/billing/partial-coverage-completion-plan.md` |

---

## Riskler

| Risk | Azaltma |
|------|---------|
| Classify sıkılaştırma gerçek repricing maddelerini kaçırır | Manifest ile encode listesi; §2.2 explicit prefix |
| Gazette whitelist (B) demo 0011’i kırar | Golden + sentetik test önce |
| Gap düşüşü “implemented” sanılır | `docs/gazette/partial-coverage-scope.md` + registry notları |

---

## Done when

- [ ] Wave 1: gazette ≥8 kod seed + golden; procedure/material +2–3 kural
- [ ] Wave 2: classify fix + coverage rebuild; gazette primary gap ≤2
- [ ] Registry + honesty doc güncel
- [ ] Madde 8 gazette: **kapat** veya **partial+manifest** kararı PR açıklamasında
