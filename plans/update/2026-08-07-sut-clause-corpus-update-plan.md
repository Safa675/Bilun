# Plan: 01.07.2026 SUT Clause Corpus Güncellemesi (Branch B)

**Tarih:** 2026-08-07
**Durum:** BEKLEMEDE — `plans/update/2026-08-06-stale-clause-triage-plan.md` bitmeden başlanmayacak (Safa kararı 2026-08-07).
**Bağlam:** Copay freshness açığı (Phase-4 bulgusu: kural JSON'ları 01/07/2026 tutarlarıyla 50/90/100 TL, clause store 23.05'te 26/60 TL) araştırılırken bulundu.

---

## Goal

`data/gazette/sut_clauses.parquet`'i `raw data/2026.07.01-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/` konsolide docx'inden yeniden üret; downstream'i rejenere et; clause store copay tutarları kural JSON'larıyla hizalansın; tek `chore(data)` PR'ı.

**Done =** `sut_clauses.parquet` source_effective_date=2026-07-01; 1.8.1 in-force tutarları 50/90/100 TL; `compile_rules --check` + `audit_manifest_parity` OK; tam pytest yeşil (kırıklar re-audit edilip bilinçli güncellenmiş); stale reporter diff'i raporlanmış.

---

## Problem (doğrulanmış)

- **Branch A (xlsx ekler → raw/curated parquet) GÜNCEL:** `ingest_state.json` last_ingested=2026-07-01 (07-12'de koşulmuş), version_manifest 326 satır, ek2b history valid_from max 2026-07-07.
- **Branch B (docx → clause corpus) BAYAT:** `sut_clauses.parquet` source_effective_date=2026-05-23. `extract_sut_prose.py` 01.07 docx'iyle hiç yeniden koşulmamış.
- Copay tutarları docx **gövdesinde** (xlsx eklerde değil) → açık tam olarak Branch B'nin eksik koşması.
- Paket konsolide (lessons.md kuralı: `YYYY.MM.DD-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/` + EK alt klasörleri = konsolide): ana docx `01.07.2026 - Değişiklik Tebliği İşlenmiş Güncel 2013 SUT.docx` + EK-1/2/3/4 LİSTELERİ.

---

## Subtasks

### Phase 0 — Baseline
- [ ] Clause sayısı, T1/T2/T4 sayaçları, tam pytest sonucu (24 pre-existing auth hatası), `compile_rules --check` OK kaydı

### Phase 1 — Docx extract
- [ ] `scripts/sut/extract_sut_prose.py` çalıştır (önce yeni branch: `chore/sut-0107-clause-corpus`)
- [ ] Failures satırını oku (2026-06-19 dersi: xlrd/odfpy dependency gap'leri burada çıkar)
- [ ] Doğrula: source_effective_date=2026-07-01; clause sayısı delta'sı makul; 1.8.1.(a-f) in-force tutarları 50/90/100 TL

### Phase 2 — Downstream rejenere
- [ ] `scripts/sut/build_sut_coverage.py` (coverage parquet'leri)
- [ ] `scripts/sut/compile_rules.py` (manifestler) + `audit_manifest_parity.py --drug-only`

### Phase 3 — Test triage
- [ ] Tam `pytest -q`; kırılanları sınıfla: bilinçli değişim (yeni clause id'leri, taşınan hükümler) vs gerçek kırık
- [ ] Golden sabit güncellemeleri YALNIZCA re-audit sonrası (2026-06-22 dersi: committed artifact okuyan test vs rebuild eden test ayrımı)

### Phase 4 — Reporter diff
- [ ] `stale_clause_refs.py` + `triage_stale_refs.py` yeniden çalıştır; T1/T2/T4 önce-sonra tablosu
- [ ] Copay `1.8.1.(1).muayene_copay_schedule` T2 bayrağının temizlendiğini doğrula

### Phase 5 — PR
- [ ] `chore(data): ingest 01.07.2026 SUT clause corpus` — delta özeti + Phase 3 triage notlarıyla

---

## Out of Scope

- Branch A re-ingest (zaten güncel)
- Yeni prose kural yazımı (docx değişimi yeni kural gerektirirse ayrı plan)
- Git LFS / sut-monitor / sut-fetch pipeline işleri (plans/update/sut-update-pipeline.md'nin kendi fazları)
- Katsayı değişimi kontrolü (01/07 tebliğinde katsayı maddesi varsa ayrı iş)

## Riskler

| Risk | Mitigasyon |
|---|---|
| Corpus yenilenince gate_b koordinat çözümleri kayar (yeni clause id'leri) | Phase 3 triage + `compile_rules`'ın `_assert_gate_b_cites_resolvable` zaten fail eder |
| Golden manifest testleri kırılır (4224 `_PILOT_SOURCES` deseni) | Re-audit sonrası bilinçli güncelleme; sessiz gevşetme yok |
| Extractor 01.07 docx formatında takılır | Failures satırı + 2026-06-19 full-chain dersi |
