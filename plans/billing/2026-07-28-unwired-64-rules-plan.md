# Plan: 64 Unwired Runnable Rules — Checklist + ICU Leakage

**Tarih:** 2026-07-28  
**Kapsam:** `fatura_inceleme_checklist` (63) + `icu_bundled_leakage` (1)  
**Dil:** Ürün kararı + wiring; encode/compile değil  
**İlgili notlar:** “64 Unwired rules”; önceki orphan-wire planlarından ayrı (bu aileler loader’ı hazır)

---

## Goal

Ürün motoruna bağlı olmayan ama **çalıştırılabilir** 64 kuralı ya (a) doğru yüzeye bağlamak, ya da (b) coverage etiketini dürüstleştirmek — böylece “implemented ama runtime’da yok” yalanı bitsin. Kullanıcı, checklist’i belge listesi olarak; ICU çift-faturalama riskini denetim/ihlal yüzeyi olarak görsün.

**Done =** her iki aile için ürün kararı uygulanmış + test yeşil + registry/coverage etiketi runtime gerçeğiyle uyumlu.

---

## Problem (doğrulanmış)

| Aile | Kural | Artifact | Registry | Runtime | Gerçek anlam |
|---|---:|---|---|---|---|
| `icu_bundled_leakage` | 1 | `prose_rules/icu_bundled_leakage.py` | ❌ yok | ❌ | 510090 gününde paket-içi hizmetin **ayrı** faturalanması → çift fatura / **denetim riski** |
| `fatura_inceleme_checklist` | 63 | JSON + wrapper hazır | `implemented` | ❌ (`billing/engine` / report’ta yok) | “Bu işlem için SGK şunu ister” **doküman listesi**; belge var/yok bilmiyor |
| `definitions_2_6` | 63 | loader + `non_algorithmic` | kasıtlı | ❌ (beklenen) | Unutulmuş kablo **değil** — bu plana dahil değil |

**Sayı:** bağlanmamış çalıştırılabilir = **1 + 63 = 64**.  
`definitions_2_6` eklenirse 127 olur; o yanlış sayaç.

### Kritik nüanslar

1. **Checklist ≠ bugün ihlal üretemez.** Motor sadece `procedure_code_any` + branş’a bakıyor; EMR’de epikriz/patoloji/ameliyat notu var mı bilmiyor. İhlal diye wire edilirse neredeyse her eşleşmede kırmızı yanar (false positive).
2. **ICU “leakage” = kaçırılmış ciro değil.** Kod `SAVINGS_CATEGORY_AUDIT_EXPOSURE` + `severity=error` üretiyor: hastane fazla faturalamış olabilir. “Şunu daha faturala” fırsatına koymak yanlış yön.
3. **Mevcut sibling’ler:** `fatura_inceleme` zaten `engine.py` violation path’inde; `claim_submission_checklist` zaten report’ta advisory yüzey; `icu_puani` report’ta wired ama bundling çift-fatura yakalamıyor.

---

## Ürün kararları — KİLİTLİ (2026-07-28)

| # | Karar | Seçim |
|---|---|---|
| D1 | Checklist çıktı tipi | **A — advisory checklist / uyarı** (faturayı engellemez) |
| D2 | Checklist uzun vadeli | A→B belgelenir; bu PR’da yok |
| D3 | ICU yüzey | **Denetim riski** → `engine.py` violations |
| D4 | `definitions_2_6` | Dokunma |
| D5 | Checklist yüzeyi | **A1** — `claim_submission_checklist` items’a merge (`checklist_kind=documentation_requirement`) |

Onay: Safa — “D1: a d3:denetim riski D5:a1”

---

## Architecture — nereye bağlanır

### Checklist (A yolu)

```
fatura_inceleme_checklist.check_*_for_context(ctx)
        ↓
billing adapter (yeni veya mevcut checklist’e merge)
        ↓
patient_report → ClaimSubmissionChecklist / yeni doc-checklist alanı
        ↓
billing_actions surface = claim_checklist (veya doc_checklist)
```

- **`billing/engine.py` violations listesine EKLEME** (A varsayımında).
- Tercih A1: mevcut `claim_submission_checklist` items’a SGK doc-requirement item’ları ekle (`checklist_kind` ile ayır).
- Tercih A2: ayrı `fatura_inceleme_documentation` report alanı + block_registry kaydı (daha net UX, biraz daha iş).

**Karar noktası D5 (implement öncesi):** A1 mi A2 mi? Tavsiye: **A1** (hızlı, mevcut UI yüzeyi var) — item shape’e `required_documents` + `fatura_inceleme_ref` ekle.

### ICU leakage (audit-wire)

```
detect_icu_bundled_leakage(claims, procedure_lines, ...)
        ↓
(a) engine.py → violations.extend(...)   // tercih: gerçek ihlal
  veya
(b) patient_report + audit_exposure / medula playbook bucket
        ↓
registry entry ekle (coverage_status dürüst)
```

**Tavsiye:** **(a) `engine.py` violation path** — çünkü detector zaten violation dict üretiyor (`severity=error`, audit_exposure). `icu_puani` fırsat raporunda kalsın; leakage ihlal tarafında.

---

## Phases / Subtasks

### Phase 0 — Status honesty (wiring’den önce veya wiring ile aynı PR’da)

Wire gecikse bile yalan etiket kalmamalı.

- [x] **0.1** `fatura_inceleme_checklist` — A1 wire ile `implemented` + `claim_submission_checklist.py` domain_modules; description dürüstleştirildi (violation değil)
- [x] **0.2** `icu_bundled_leakage` registry entry eklendi (`implemented`, engine wire)
- [x] **0.3** Registry assertion testleri (`test_wired_orphan_engines`)
- [x] **0.4** `definitions_2_6` bu planda dokunulmadı (kasıtlı non_algorithmic)

### Phase 1 — `icu_bundled_leakage` wire (1 kural, ucuz)

Varsayım: D3 = audit-wire. **Kilitli.**

- [x] **1.1** Registry entry
- [x] **1.2** `billing/engine.py` → `detect_icu_bundled_leakage`
- [x] **1.3** Adapter yok (engine doğrudan çağırıyor — diğer El Kitabı detect_* ile aynı)
- [x] **1.4–1.6** Unit + `analyze_claim` integration test yeşil

### Phase 2 — `fatura_inceleme_checklist` advisory wire (63 kural)

Varsayım: D1 = A, D5 = A1. **Kilitli.**

- [x] **2.1** D5 = A1
- [x] **2.2–2.3** `claim_submission_checklist` merge (`checklist_kind=documentation_requirement`); sadece `procedure_lines` varken
- [x] **2.4** Engine violations’a eklenmedi
- [x] **2.5–2.6** Test + registry
- [ ] **2.7** Frontend smoke (opsiyonel — mevcut checklist UI item dict render eder)

### Phase 3 — A→B hazırlığı (şimdi implement etme; kapıyı aç)

Sadece D2 = A→B onaylanırsa planlanır; **bu PR’da kod yok.**

- [ ] **3.1** Belge presence için veri modeli ihtiyacı yaz (hangi claim/EMR alanları: epikriz, patoloji, ameliyat notu, fotoğraf, …)
- [ ] **3.2** Checklist kuralındaki `required_documents` ↔ presence flag mapping tasarımı
- [ ] **3.3** Presence datası gelince: eksik belge → violation; var → sessiz (veya satisfied checklist)
- [ ] **3.4** Feature flag / coverage: B’ye geçmeden false-positive ölçümü

### Phase 4 — Doğrulama

- [ ] **4.1** `pytest` ilgili unit + billing integration yeşil
- [ ] **4.2** Sentetik claim: checklist item görünür; ICU çift-fatura violation görünür
- [ ] **4.3** Coverage/inventory: “64 unwired runnable” → 0 (definitions hariç)
- [ ] **4.4** `tasks/todo.md` review bölümü + bu plan checkbox’ları güncel

---

## Out of Scope

- `definitions_2_6` wiring veya `non_algorithmic` değiştirme
- `schemas.py` split / god-file refactor
- Belge/EMR presence ingestion (Phase 3 tasarım notu hariç)
- Checklist’i hemen violation yapmak (D1=B seçilmedikçe)
- ICU’yu “kaçırılmış gelir / daha fazla faturala” fırsat raporuna koymak
- Orphan JSON ailelerinin genel wire epic’i (`dental_2_4_1` vb. — ayrı planlar)

---

## Riskler

| Risk | Mitigasyon |
|---|---|
| Checklist’i violation sanmak → alarm yorgunluğu | A hard rule; engine’e ekleme; test ile assert |
| ICU’yu fırsat bucket’ına koymak → yanlış UX | engine violation / audit_exposure; `icu_puani` ile karıştırma |
| Registry `implemented` yalanı | Phase 0 önce veya aynı PR |
| Checklist UI shape uyumsuzluğu | A1’de `checklist_kind` ile ayır; frontend smoke |
| Circular import / god wiring | İnce adapter; `patient_report` pattern’ini kopyala |

---

## Definition of Done

1. D1–D3 (ve D5) yazılı onaylandı.
2. ICU: 510090 + paket-içi ayrı satır → kullanıcı/report’ta **denetim/ihlal** olarak görünüyor.
3. Checklist: eşleşen işlemlerde **required documents listesi** görünüyor; violation sayılmıyor.
4. Registry/coverage: iki aile için etiket runtime ile uyumlu; `definitions_2_6` hâlâ kasıtlı non_algorithmic.
5. Testler yeşil; staff engineer sentetik claim ile iki davranışı da görebiliyor.

---

## Onay kapısı

**Kilitli (2026-07-28):** D1=A, D3=denetim riski, D5=A1 — implement edildi.

### Implementasyon özeti
- `rule_registry.py` — checklist description + `icu_bundled_leakage` entry
- `billing/engine.py` — ICU leakage → violations
- `billing/claim_submission_checklist.py` — doc requirements merge (proc-only)
- Testler: icu / claim_readiness / wired_orphan / synthetic demo
