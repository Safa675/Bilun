# Plan: Scripts Dead-Code & Bug Audit Raporu

**Tarih:** 2026-06-19
**Kapsam:** `scripts/` (68 Python dosyası: sut/, synthetic/, bilun/, medula/, raw_data/)
**Yöntem:** 2 paralel Explore subagent, tüm bulgular `Grep`/`Read`/git blame ile kanıtlandı

---

## Goal

`scripts/` içindeki (1) dead code, (2) gerçek bug'ları envanterleyip öncelik sırasına koymak. Bu rapor tespit raporudur — fix'ler ayrı task'lerde.

## Out of Scope

- Backend (`src/bilun/`) — ayrı audit
- `__pycache__` artifact'leri (zaten gitignored)

---

## Özet

| Kategori | Sonuç |
|---|---|
| Toplam `.py` dosyası | 52 (+ 3 `__init__.py`) |
| **Dead code** | **Yok** — her dosya CLI/module/test grafiğinde canlı |
| **CRITICAL bug** | **1** (C1 — EK-2B kolon uyuşmazlığı) |
| **HIGH bug** | **3** |
| **MEDIUM bug** | **6** |
| **LOW bug** | **2** |

**En önemli bulgu:** `scripts/` temiz — dead code yok, silinebilecek tek dosya yok. Ama **C1 gizli bir pipeline-kırıcı bug** ve diskteki stale parquet yüzünden bugün çalışıyor gibi görünüyor.

---

## 1. DEAD CODE — YOK

Subagent her dosyayı trace etti. Sonuç:
- 25 standalone CLI entry point
- 24 module (imported by other scripts/tests)
- 3 `__init__.py`
- **0 orphaned**

**Silme önerisi yok.** İki "low-value one-shot" aday var ama ikisi de canlı data üretiyor:

1. `scripts/sut/catalogs/ek2c_prose_drg_locked_seed.py` — `CATALOG_SPECS`'te değil ama `data/gazette/prose_rules/ek2c_prose_drg_locked_codes.json` üretiyor, o JSON `src/bilun/domain/prose_rules/ek2c_prose_drg_locked.py:20` ve `tests/unit/scripts/test_sut_coverage.py:489`'da consumed. **Sakla.**

2. `scripts/sut/prose/merge_drug_indication_phase1.py` — external caller yok ama `batch_a.json`/`batch_b.json` golden file'ları yazıyor, `test_golden_phase1_samples` (`tests/unit/domain/prose_rules/test_drug_indication.py:263,267`) bunları yüklüyor. **Sakla** (golden fixture üreticisi).

**Deleted module import kontrolü:** Hiçbir script silinen `billing/strategy.py`, `pricing/drg.py`, `billing/lab.py`, `billing/copay.py`, `billing/materials.py` import etmiyor. `data/real`/`data/production` yolu referansı da yok.

---

## 2. BUGS

### 🔴 CRITICAL

**C1 — EK-2B kolon uyuşmazlığı (pipeline-kırıcı, stale artifact maskeli)**
- **Producer:** `scripts/sut/catalogs/price_history.py:83,96` — `extract_ek2b()` kolonu **`package_code`** olarak emit ediyor. `history_key` de `:168`'de `"package_code"`.
- **Consumer:** `scripts/synthetic/catalog.py:38` — `drop_duplicates(subset=["code"])`, `generators.py:2011` — `["code"]`, `generators.py:810` — `["code"]`.
- **Diskte:** `data/gazette/curated/ek2b_catalog_history.parquet` byte-inspection: kolon **`code`** (stale artifact).
- **Sonuç:** Bugün çalışıyor çünkü diskteki parquet stale (`code` kolonlu). Ama `build_curated_catalogs.py` tekrar çalışınca yeni parquet `package_code` yazar → `catalog.py:38` **`KeyError: "['code'] not in index"`** → sentetik data üretimi tamamen kırılır. git blame (`917f670`) `extract_ek2b`'in hep `package_code` yazdığını doğruluyor.
- **Not:** EK-2C tutarlı — `extract_ek2c` `package_code` yazar, `_ek2c_latest()` (`catalog.py:50`) doğru okur. Sadece EK-2B kırık.
- **Fix (önerilen, en küçük):** `extract_ek2b`'nin output kolonunu `code`'ya rename (mevcut disk schema + consumer ile uyumlu). Alternatif: 3 consumer'ı `package_code`'a çevir.

### 🟠 HIGH

**H1 — `subprocess.run` timeout yok (3 yerde, hang riski)**
- `scripts/sut/catalogs/ek4d_copay_exempt.py:80` — LibreOffice headless DOCX→PDF (font/profile takılırsa sonsuz asılır)
- `scripts/synthetic/generate_sut_synthetic_data_v2.py:80,84` — validator/assert subprocess, timeout yok

**H2 — Broad `except Exception` sessiz hata yutuyor (5 yerde)**
- `scripts/sut/catalogs/price_history.py:145` — **en kritik olan**: `load_prose_drg_locked_code_set()` exception yutuyor, `prose_drg_locked = False` bırakıyor. Import path kırılırsa DRG-locked flag sessizce yanlış → downstream pricing bozuluyor.
- `scripts/sut/convert_xlsx_to_parquet.py:340`, `build_curated_catalogs.py:186`, `build_clause_embeddings.py:81` — logged ama devam ediyor.
- `scripts/raw_data/generate_readmes.py:485` — `except Exception: return None`

**H3 — Non-atomic manifest write (read-modify-write race)**
- `scripts/sut/convert_xlsx_to_parquet.py:348-356` — manifest parquet oku+append+aynı path'e yaz. Temp+atomic rename yok, lock yok. Concurrent run veya crash → yarım yazılmış manifest → build corruption.

### 🟡 MEDIUM

| # | Yer | Sorun |
|---|---|---|
| M1 | `rebuild_baseline_metrics.py`, `export_material_bundling_clauses.py` | `Path("data/...")` relative default — repo root dışından çalışınca yanlış yer |
| M2 | `validate_sut_synthetic_data.py:88` | `pd.ExcelFile(workbook)` `with` kullanılmıyor — file handle leak |
| M4 | `raw_data/generate_readmes.py:12` | `TODAY = "2026-06-15"` hardcoded — stale (bugün 06-19) |
| M5 | `raw_data/generate_readmes.py:485` | `return None` loader hatasını gizliyor → kısmi datadan README |
| M6 | `synthetic/catalog.py:12` | `_GAZETTE_CACHE` modül-level dict — uzun yaşayan process'te stale |

### 🟢 LOW

- **L1** `generators.py:1731-1736` — `paket_kodu` nested ternary, precedence kafa karıştırıcı (şu an doğru ama kırılgan).
- **L2** `catalog.py:75-76` — `_money` `round()` banker's rounding kullanıyor; TRY currency için half-up değil.

---

## 3. Temiz bulunan alanlar (doğrulandı)

- **Hardcoded absolute path** — yok (synthetic/medula/bilun hepsi `Path(__file__)` çözümlüyor)
- **Mutable default arg** — yok (grep `def \w+\([^)]*=\s*(\[\]|\{\})` = 0 hit)
- **Determinism/seed** — temiz: `rng = np.random.default_rng(seed)` her yere thread ediliyor, reproducible
- **Geçersiz tarih** — yok: günler `rng.integers(1, 29)` ile 28'le capleniyor (Feb-30 yok)
- **Header/line toplam reconciliation** — `_reconcile_claim_header_totals` (generators.py ~1319) line sum'lardan header'ı recomput ediyor
- **Encoding (Türkçe)** — her `open`/`read_csv`/`to_parquet` `encoding="utf-8"` (medula `utf-8-sig` doğru kullanıyor)
- **DB connection lifecycle** — `cache/builder.py:run_build` `try/finally` ile `con.close()` + `fail_build`

---

## 4. Önerilen fix sırası

### Dalga A — C1 + H2-kritik (en yüksek ROI, pipeline bütünlüğü)
- [ ] **C1:** `extract_ek2b` output kolonunu `code`'ya rename (tek satır, schema-preserving)
- [ ] **H2-price_history:** `:145` broad except'i daralt veya en azından log warning ekle

### Dalga B — Timeout + atomicity (operasyonel sağlamlık)
- [ ] **H1:** 3 subprocess.run'a `timeout=` ekle (ek4d LibreOffice için 300s, validator için 600s)
- [ ] **H3:** manifest write'a temp+`os.replace` atomic pattern

### Dalga C — Path/yol + leakage (kalite)
- [ ] **M1:** 2 script'te `Path("data/...")` → `Path(__file__).resolve().parents[N]`
- [ ] **M2:** `pd.ExcelFile` → `with` context manager

### Dalga D — Kalan (cosmetic/drift)
- [ ] **M4:** hardcoded `TODAY` → `date.today().isoformat()`
- [ ] **L1, L2:** değerlendir (düşük öncelik)

## Out of Scope
- Backend `src/bilun/` audit
- `merge_drug_indication_phase1.py` supersession kararı (team onayı gerek)
