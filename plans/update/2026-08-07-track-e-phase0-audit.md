# Track E — Phase 0 Audit: C* Envanteri + Collision + Baseline

**Tarih:** 2026-08-07
**Plan:** `plans/update/2026-08-07-stable-clause-identity-track-e-plan.md` — Phase 0
**Durum:** TAMAM (read-only audit; kod değişikliği yok)

---

## 1. C* referans envanteri — load-bearing vs türetilmiş

Repo geneli tarama (parquet/pyc/git hariç). Kritik bulgu: `C*` ayak izi tek dosya değil; **authored (load-bearing) ve türetilmiş olarak ikiye ayrılıyor.**

### 🔴 LOAD-BEARING (authored/config — re-extract'ta kırılır, migrate edilmeli)

| Kaynak | C* sayısı | Not |
|---|---:|---|
| `data/gazette/prose_rule_sources/**/*.yaml` → `gate_b_sources` | **1172** | 141 dosya. Bunlar migration'ın coordinate'e taşıyamadığı **collision** vakaları (unique olanlar zaten migrate) |
| `data/gazette/prose_rules/deferral_table.yaml` → `clause_id` | **1541** | 1541 unique clause_id ama sadece **806 unique coordinate** → collision. Her entry'de `clause_coordinate` zaten var (NULL yok) |
| `scripts/sut/gate_b_wave_config.py` | ~199 | Hardcoded C* listesi (wave config) |
| `scripts/sut/prose/gate_b_sections.py` | 20 | Hardcoded C* |
| **TOPLAM load-bearing** | **~2930** | |

**Zaten migrate edilmiş (referans değil, başarı ölçüsü):** `gate_b_sources`'ta **1612 coordinate** referansı var (757cae1 migration'ı, unique vakalar).

### 🟢 TÜRETİLMİŞ (regenere edilir — load-bearing değil)

| Kaynak | C* sayısı | Tür |
|---|---:|---|
| `data/gazette/prose_manifests/*.json` → `encoded_clause_ids` | çok (623+354+346+282+…) | `compile_rules` çıktısı; kurallardan türetilir |
| `data/gazette/rule_interaction_graph.json` (`id`/`source`/`target`) | 1491 | `build_rule_interaction_graph.py` çıktısı (manifest'lerden) |
| `data/gazette/prose_rules/drug_indication_prose.json` | 710 | Derlenmiş prose artifact |
| `data/gazette/prose_corpus/*.json` | 513+338+113 | Analiz/özet dosyaları |
| `reports/agent/reimbursement/stale_clause_refs.md` | 692 | Reporter çıktısı |
| `data/synthetic/sut/claims/ilay_validation/rule_compliance.csv` | 110 | Gerçek ILAY reçetelerinden türetilmiş özet (sentetik değil); 2026-10-15'te KVKK gereği repodan çıkarıldı |

### Çıkarım
Kalan load-bearing `C*` (~2930), **tam olarak content-hash'in çözeceği collision kümesi**. Unique coordinate'ler zaten migrate (1612); geriye yalnız coordinate'in benzersiz olmadığı vakalar kalmış. Bu, Track E tasarımını doğruluyor.

---

## 2. clause_coordinate durumu + özdeş-collision listesi

- **coordinate NULL:** 16 / 8295 (**%0.19**) — ihmal edilebilir.
- **Özdeş-collision** `(clause_coordinate, in_force_text)`, in-force: **82 grup**. Bunlar aynı coordinate + aynı içerik = **semantik özdeş** → ordinal gerekmez, content-hash aynı olur.

En kötü 15 özdeş-collision:
```
4.2.34.(1)  x6      4.2.34.(3)  x6
2.4.4.Ğ     x5      2.4.4.Ğ     x5      2.4.4.Ğ   x4
3.3.6.B     x4      4.2.14.C.(4) x4     4.2.34.(2) x4
1.9.1       x3      2.4.2.A     x3      2.4.4.Ğ   x3
3.3.6.A-1   x3      5.3.1.Ç.i   x3      1.5.1.A-2 x2  (x2 tekrar)
```

### Neden composite key yetmez (ölçülmüş)
| Anahtar | Çakışan grup |
|---|---:|
| `(cc, is_in_force)` | 1218 |
| `(cc, is_in_force, clause_type)` | **1065** → ❌ yetersiz |
| `(cc, in_force_text)` in-force | **82** → ✅ content-hash yeterli |

Kök neden: bir section altında çok sayıda bağımsız `1)` maddesi (ör. `4.2.14.C.(1)` farklı ilaçlar). `is_in_force`/`clause_type` ayırt etmez; **içerik ayırt eder**.

---

## 3. Baseline (değişiklik öncesi referans)

| Kontrol | Sonuç |
|---|---|
| `pytest -q` (tam) | **24 failed, 2398 passed, 20 skipped** (173.9s). 24'ü **pre-existing** (auth/server + smoke; corpus planının beklediği sayı) |
| `compile_rules.py --check` | ✅ 136 rule/manifest artifact **byte-identical** |
| `audit_manifest_parity.py --drug-only` | ✅ 0 issue (23 manifest) |

Pre-existing 24 failure: `tests/smoke/test_sut.py` (live-server), `tests/unit/api/test_sut_chat.py`, `tests/unit/api/test_sut_patient_claims_api.py`. Bunlar Phase 0'dan bağımsız, değişiklik sonrası karşılaştırma referansı olarak kaydedildi.

---

## 4. Sonraki fazlara girdi

- **Phase 1 (normalizasyon kilidi):** hash `in_force_text` üzerinden; 82 özdeş-collision'da key çakışması **beklenen** (semantik özdeş).
- **Phase 3 (migrate) kapsamı:** ~2930 load-bearing C* → `coordinate#hash`. Önce authored `gate_b_sources` (1172), sonra `deferral_table` (1541, coordinate zaten mevcut → hash ekle, clause_id düşür), en son config script'leri (~219).
- **Türetilmiş artifact'lar** (manifest, graph, rapor) migrate edilmez; re-extract + recompile ile kendiliğinden yenilenir.
- **Deferral table özel:** 1541 entry / 806 unique coord → collision'lar content-hash ile ayırt edilecek; `clause_coordinate` zaten dolu olduğundan migration düşük riskli.

## Doğrulama
- Ölçümler DuckDB ile `data/gazette/sut_clauses.parquet` üzerinde (2026-08-07).
- C* sayımları `grep -ohE "\bC0[0-9]{5}\b" | sort -u` ile dosya bazında.
- Baseline kontrolleri temiz worktree'de koşuldu.
