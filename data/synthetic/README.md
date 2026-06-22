# Synthetic demo data — credibility cohort

Sentetik SUT veri seti (`data/synthetic/sut/`) üretimi, showcase kohortu ve alan
semantiği. Üretim pipeline’ı ve Tier A/B ayrımı için tek giriş noktası.

**İlgili planlar**

- [Sentetik demo inandırıcılık planı](../../plans/data/synthetic-demo-credibility-plan.md) — Tier A/B/C, P1–P3
- [Synthetic Data v2](../../plans/data/synthetic-data-v2.md) — genel üretici ölçeği ve parquet şeması
- [Synthetic Data v2 refactor](../../plans/data/synthetic-data-v2-refactor.md) — modül yapısı
- [Billing bugfixes](../../plans/billing/billing_bugfixes.md) — algoritma / cache notları

---

## Dosya yapısı

| Dosya / dizin | Amaç |
|---------------|------|
| `demo_manifest.json` | Tier A/B hasta indeksleri, `default_landing_index`, `scenario_by_index` |
| `demo_vignettes.json` | Hasta başına vignette: `fault`, klinik kabuk, golden bantlar |
| `demo_cohort_tiers.json` | **Regen sonrası** Tier A/B/C hasta listesi (JSON; demo cheat sheet kaynağı) |
| `DEMO_COHORT.md` | **Regen sonrası** insan-okur demo rehberi (senaryo + fault tabloları) |
| `sut/` | Üretilmiş workbook, `clean/*.parquet`, `claims/*.parquet` |
| `scripts/synthetic/vignettes.py` | Typed `BillingVignette` registry (JSON kaynak) |
| `scripts/synthetic/fault_injection.py` | Ortak fault / optional-override üretim yardımcıları |

---

## Kohort tier’ları

| Tier | Amaç | Plausibility | Hero / UI |
|------|------|--------------|-----------|
| **A – Showcase** | Demo, dokümantasyon, default landing | Yüksek klinik + finansal | Evet |
| **B – Regression** | CI golden, algoritma kanıtı (MEDULA, ilaç, malzeme sprint’leri) | Orta; etiketli hata | Hayır |
| **C – Stress** | Legacy pattern, edge case | Düşük | Hayır |

Tier listeleri `demo_manifest.json` içinde. Vignette `tier` alanı `demo_vignettes.json` ile senkron olmalı.

### Tier A (showcase) — `default_landing_index: 0003`

| Index | `scenario_tag` | `fault` (özet) |
|-------|----------------|----------------|
| 0002 | `sgk_optional_override_itemized_higher` | Paket sunulmuş; kalem daha yüksek |
| 0003 | `sgk_optional_override_package_higher` | Yalnız kalem sunulmuş; paket daha yüksek |
| 0006 | `sgk_material_uplift_yatis` | Paket dışı malzeme |
| 0009 | `sgk_procedure_capture_kolonoskopi` | Capture gap |
| 0010 | `sgk_package_adequacy_undercoded` | Küçük paket |
| 0011 | `sgk_gazette_repricing_600150` | Eski liste fiyatı |
| 0013 | `sgk_session_uplift_cerrahi` | Seans under-billed |
| 0029 | `medula_rejection_0704_uts_barcode_missing` | MEDULA playbook |
| 0038 | `payment_method_compliance_demo` | Zorunlu paket + DRG_MANDATORY kalem |

### Tier B (regression) — özet

0004–0008 uplift/review demoları; 0012–0033 sprint pin’leri (MEDULA 0012/0018/0025–0032, ilaç 0014–0020, malzeme 0021–0024, readiness 0033). Tam liste `demo_manifest.json` → `tier_b_patient_indices` ve `scenario_by_index`.

---

## Claim line alan semantiği (showcase)

| Alan | Anlam | Nerede |
|------|--------|--------|
| `billed_amount_try` | MEDULA’ya **gerçekten sunulan** tutar | Claim line |
| `expected_payable_try` | Bu sunuma göre SGK **bu satır** ödemesi | Claim line |
| Alternatif paket / kalem | Claim line **değil** | `billing_strategy` → `package_total_try`, `itemized_total_try`, `savings_try` |

**Tier A hard rules**

- `billed=0` + `expected_payable>0` paket satırı yasak (hayalet paket).
- Aynı faturada hem tam paket hem tam kalem **sunulan** payable yolu yasak (optional-override showcase hariç strateji tarafında alternatif).
- `payable_override` ile alternatif yol claim line’a yazılmaz (`billed_override=0` + full payable deprecated).

Tüketiciler (aynı parquet): API `/patients/.../claims`, billing-report cache, OriginalBillView, optimizer export, chatbot context.

---

## Üretim ve doğrulama

```bash
# 1. Veri üret (seed sabit: constants.SEED)
python scripts/synthetic/generate_sut_synthetic_data_v2.py

# 2. Workbook + parquet şema / kohort doğrulama
python scripts/synthetic/validate_sut_synthetic_data.py

# 3. Tier A showcase P1.1 + golden bantlar (post-regen)
python scripts/synthetic/assert_tier_a_post_regen.py

# 4. İsteğe bağlı: analytics cache yenile (billing yüzeyleri)
python scripts/bilun/build_cache.py --activate
```

`generate_sut_synthetic_data_v2.py` adım 2–3’ü varsayılan olarak çalıştırır (`--skip-checks` ile atlanır).

**Demo hazırlığı:** Her regen sonrası `data/synthetic/DEMO_COHORT.md` ve `demo_cohort_tiers.json` güncellenir — Tier A/B/C hasta listesi ve default landing (0003) burada.

### CI / golden testler

```bash
pytest tests/unit/synthetic/ -q
pytest tests/unit/domain/billing/test_sgk_uplift_synthetic_demos.py -q
```

Golden pin’ler `scenario_tag` + donmuş `savings_try` bantları (`demo_vignettes.json` → `golden`); claim_id suffix kullanılmaz.

---

## Cache hygiene

Sentetik parquet değişince:

1. `validate_sut_synthetic_data.py` ve `assert_tier_a_post_regen.py` geçmeli.
2. Billing / optimizer cache eski satırları tutabilir → `build_cache.py --activate`.
3. Tier A hero path: manifest `default_landing_index` (**0003**) + `sgk_optional_override_package_higher` spot-check.

Frontend “Sunulan fatura” ara toplamı yalnızca `billed>0` satırları toplar; legacy ghost satırlar (Tier B/C) footnote ile gösterilir.

---

## Vignette registry (P2)

Python API (`scripts/synthetic/`):

```python
from vignettes import get_vignette_registry
from demo_config import vignette_for_patient_id, vignette_for_scenario_tag

v = vignette_for_patient_id("SENTETIK-HASTA-0003")
assert v.scenario_tag == "sgk_optional_override_package_higher"
```

Yeni sprint demo pin’i: `demo_vignettes.json` + `demo_manifest.json` → `validate` + gerekirse `tests/unit/synthetic/test_vignette_golden.py` golden satırı.
