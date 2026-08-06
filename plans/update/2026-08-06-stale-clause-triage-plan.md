# Plan: Stale SUT Clause Referansları — TIER-1 Triage ve Burn-Down

**Tarih:** 2026-08-06
**Kaynak sorun:** `stale_clause_refs.py` raporuna göre 2-3 SUT update boyunca triage edilmeyen bayat `gate_b_sources` referansları birikti. 2026-07-20 baseline'ında 116 olan TIER-1 bugün 158 (+42).
**Checker:** `scripts/agent/stale_clause_refs.py` (reporter, gate değil)

---

## Goal

TIER-1 backlog'unu (158 ref / 11 rule set) **sil / re-encode / zararsız** diye sınıflandırıp güvenli, testli, küçük PR'larla eritmek. TIER-2 ve TIER-4 için ayrı, örneklemeye dayalı workstream'ler kurmak.

**Done =** TIER-1 için makine-üretimi triage raporu + insan onaylı sınıflama; her rule-set için ayrı PR ile düzeltmeler uygulanmış; `stale_clause_refs` çıktısında T1 sayısı doğrulanmış şekilde düşmüş; `compile_rules --check` + `audit_manifest_parity` + tam pytest yeşil.

---

## Problem (doğrulanmış — 2026-08-06 fresh run)

| Tier | Anlam | Ref | Not |
|---|---|---|---|
| TIER 1 | Clause metninde superseded/mülga marker'ı | **158** | 11 rule set |
| TIER 2 | Clause tamamen yürürlükte değil (`is_in_force=false`) | **687** | 12 rule set; %71'i 3 sette |
| TIER 3 | Üstü çizili tarihçe (checker'a göre çoğu zararsız) | 241 | düşük öncelik |
| TIER 4 | Dangling — clause extract'te hiç yok | **154** | ayrı bug sınıfı |
| OK | Temiz | 2,011 | toplam 3,251 ref / 1,913 kural |

TIER-1 yoğunlaşma: `drug_indication_prose` 65, `treatment_pricing_2_4` 31, `specialty_materials_prose` 31, `material_bundling_prose` 13.

### Kritik doğrulama (bu plan için yeni yapıldı)

1. **TIER-1 clause'ları ölü DEĞİL.** Doğrudan C/F-id ile çözülen 49 T1 ref'inin **49/49'u `is_in_force=true`** clause'lara işaret ediyor. Marker, clause'un **içinde** bir alt ifadenin mülga/değişik olduğunu söylüyor. Örnek: `C006549` (4.2.33.(7)) yürürlükte, ama metnindeki bir cümle `(Mülga:RG-16/06/2020-31157/19-c md.)` ile silinmiş.
2. **Otomasyon imkânı:** `sut_clauses.parquet`'te hem `text_tr` (tarihçeli tam metin) hem `in_force_text` (silinmiş içerik atılmış güncel metin) var. **Diff = mülga içerik.** Kuralın mantığı bu diff'e dokunuyor mu → otomatik skorlanabilir.
3. **Somut risk örneği:** `anti_vegf_prose` → `4.2.33.general_switch_to_bevacizumab` kuralı `loading_dose_count: 3` taşıyor; clause'un mülga cümlesi tam da switch durumunda "yükleme dozu" ile ilgili. Yani kural gerçekten mülga içeriğe dokunuyor olabilir → A-sınıfı adayı.
4. `amendment_refs` doğrudan-id alt kümesinin 38/49'unda dolu (ör. `RG-19/10/2023/32344` ×8, `RG-16/03/2023/32134` ×7) → aynı RG ile bayatlayan kurallar birlikte triage edilebilir.

### Triage sınıflaması (üçlü)

| Sınıf | Tanım | Aksiyon |
|---|---|---|
| **A — Mülga içeriğe bağımlı** | Kural mantığı (drug name, koşul, mesaj) `text_tr` − `in_force_text` diff'indeki içeriğe dokunuyor | Re-encode (güncel metne karşı) veya kural artık geçersizse sil |
| **B — Zararsız** | Kural yalnızca hâlâ yürürlükteki içeriğe dokunuyor | Dokunma; raporda "verified benign" olarak işaretle |
| **C — Tamamen mülga (TIER-2)** | Clause'un tamamı `is_in_force=false` | Ayrı track (Phase 4); önce örnekleme |

---

## Ürün kararları (onay bekleyen)

| # | Karar | Önerilen seçim |
|---|---|---|
| K1 | Triage otomasyon derecesi | Script sınıflama **önerisi** üretir; son karar insan (Safa) onayıyla. Otomatik JSON düzenlemesi YOK |
| K2 | Zararsız (B) kurallara annotasyon | JSON'a `staleness_note` eklemek YOK — provenance kirlenmesin; yalnız triage raporunda kayda geçsin |
| K3 | PR bölme | Rule-set başına ayrı PR (en büyükten: drug_indication → treatment_pricing → specialty_materials → material_bundling → kalan 7 set tek PR) |
| K4 | TIER-2/TIER-4 kapsamı | Bu planda yalnız **örnekleme + politika kararı**; toplu düzeltme ayrı plan |
| K5 | Gate'leştirme | Backlog eriyene kadar reporter kalır; T1 sayısı CI **uyarısı** (fail değil) Phase 6'da opsiyonel |

---

## Phases / Subtasks

### Phase 0 — Plan lock

- [ ] Bu plan onaylandı (K1-K5 kararları)
- [ ] `tasks/todo.md` güncellendi

### Phase 1 — Triage script'i (read-only, rapor üretir)

- [ ] Yeni script: `scripts/sut/triage_stale_refs.py`
  - Girdi: `stale_clause_refs` sınıflaması + `sut_clauses.parquet` (`text_tr`, `in_force_text`, `amendment_refs`) + prose rule JSON'ları
  - Her T1 ref'i için: mülga diff = `text_tr` − `in_force_text`; kuralın yapısal alanları (`drug_names`, `message_tr`, koşul metinleri, `procedure_codes`) ile diff'in token/keyword overlap skoru
  - Öneri sınıf: A (overlap ≥ eşik) / B (overlap ~0) / REVIEW (ara bölge)
  - Aynı `amendment_refs` RG'sine sahip kuralları grupla
- [ ] Çıktı: `reports/agent/reimbursement/tier1-triage-<date>.md` + `.parquet`
- [ ] Unit test: diff hesaplama + sınıflama mantığı (C006549/loading-dose örneği A-adayı olarak fixture)

### Phase 2 — İnsan review

- [x] Safa triage raporunu inceler; her kural için A/B kararı kesinleşir (3 paralel analiz: 12 RE-ENCODE, 21 KEEP, 0 DELETE — `plans/update/2026-08-06-tier1-phase2-decisions.md`)
- [x] A-sınıfı kurallar için aksiyon belirlenir: re-encode mu, sil mi (onaylandı 2026-08-06)

### Phase 3 — Düzeltme PR'ları (rule-set başına)

- [x] 12 RE-ENCODE tek PR'da (hepsi drug_indication_prose): PR #54 — YAML kaynaklar düzenlendi, JSON+manifest compile edildi
- [x] Her PR'da doğrulama: `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, `stale_clause_refs.py` diff (T1 158→155; A=23→5 skorlayıcı iyileştirmesiyle), tam `pytest -q`
- [x] Silinen kural yoktu (0 DELETE) — orphan referans kontrolü gerekmedi

### Phase 4 — TIER-2 örnekleme

- [ ] 687 T2 ref'inden ~30 rastgele örnek: gerçekten ölü mü, yoksa extractor flag gürültüsü mü?
- [ ] Gürültü oranı ölçülür → toplu politika kararı (ayrı plan)

### Phase 5 — TIER-4 dangling (ayrı workstream)

- [ ] 154 dangling ref: koordinat yazım hatası mı, extractor eksikliği mi? Sınıfla ve düzelt (tipo → JSON fix; extractor açığı → ayrı issue)

### Phase 6 — Opsiyonel: CI uyarısı

- [ ] T1 count için non-blocking CI adımı (eşik: mevcut 158'den yukarı çıkarsa uyar)

---

## Out of Scope

- TIER-3 (checker'a göre intentionally low-priority; ~%48 clause'da struck tarihçe var)
- Reporter'ı gate'e çevirmek (backlog erimeden her şeyi bloklar)
- TIER-2/TIER-4 toplu düzeltmesi (bu planda sadece örnekleme + politika)
- Kural metinlerinin hukuki yorumu — script önerir, insan kararır

## Riskler

| Risk | Mitigasyon |
|---|---|
| Overlap skoru yanlış sınıflar (false B → mülga hukuk uygulanmaya devam eder) | Eşik konservatif; REVIEW bandı geniş; A/REVIEW hepsi insan gözüyle |
| Re-encode sırasında kural semantiği kayar | Her PR tek rule-set; diff review + mevcut motor testleri |
| `in_force_text` extractor hatası içeriyorsa diff yanıltır | Phase 1 testleri bilinen örneklerle (C006549); şüpheli diff'ler REVIEW'ya düşer |
| T1 sayısı düzeltme sırasında yeni encode'larla tekrar artar | Phase 6 CI uyarısı; encode workflow'una "in-force clause'a referans ver" notu |

## Success criteria

1. Triage raporu 158 T1 ref'inin tamamını A/B/REVIEW'dan birine atar; hiçbir ref sınıflamasız kalmaz.
2. İnsan onayı sonrası uygulanan PR'larla T1 sayısı ölçülebilir şekilde düşer (hedef: A-sınıfının tamamı temiz).
3. Hiçbir PR `compile_rules --check` / `audit_manifest_parity` / tam pytest'i bozmaz.
4. T2/T4 için örnekleme sonucu + politika kararı yazılı olarak mevcut.
