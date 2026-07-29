# Plan: FI Documentation Checklist — Relevance Gates + Dayanak UX

**Tarih:** 2026-07-29  
**Kaynak sorun:** PR #49 (D1=A, D5=A1) sonrası `claim_submission_checklist` içinde ORTAK/kodsuz FI doc kuralları her proc claim’e spam; “SUT dayanağı” kolonu FI için yanlış adlı ve boş (`sut_anchor` map edilmemiş).  
**Önceki plan:** `plans/billing/2026-07-28-unwired-64-rules-plan.md` (D2: uzun vadeli iyileştirme — bu PR o borcun bir parçası)

---

## Goal

Gönderim öncesi checklist’te FI doküman hatırlatmaları **yalnızca claim sinyaliyle ilgili** görünsün; dayanak kolonu **FI/SUT bölüm etiketi** göstersin (corpus `F000xxx` / `gate_b_sources` / `C000xxx` **değil**); kolon adı SUT’a kilitli olmasın.

**Done =** sentetik `F-SENTETIK-HASTA-0003-011` üzerinde alakasız ORTAK spam yok (veya belirgin azalmış); ilgili claim’de dayanak dolu ve okunabilir; testler yeşil; label i18n güncel.

---

## Problem (doğrulanmış)

1. **Relevans:** `procedure_code_any=[]` + `branch=null` → kod kapısı her zaman true, ORTAK her claim’e basılıyor (`fatura_inceleme_checklist.py` `_condition_matches`). 6 ORTAK kodsuz + 16 branş-kodsuz kural geniş spam.
2. **Dayanak boş:** Adapter `fatura_inceleme_ref` yazıyor ama UI `item.sut_anchor` okuyor → `—`.
3. **Yanlış label:** `billing.claimChecklist.sutAnchor` = “SUT dayanağı”; FI satırları SUT değil.
4. **Yanlış dayanak adayı:** `gate_b_sources` (`F000029` vb.) ve algorithmic `sut_cross_ref` (`C000702` vb.) **UI dayanağı olmamalı** — bunlar iç corpus id. Kullanıcı isteği: **ilgili FI/SUT section** (örn. `Fatura İnceleme ORTAK-24`, gerekirse `SUT EK-2/C` / `SUT §2.2.2.A(5)` gibi insan-okur bölüm).

---

## Ürün kararları (bu plan)

| # | Karar | Seçim |
|---|---|---|
| R1 | ORTAK/kodsuz gösterim | **Sinyal gate** — eşleşmeden gösterme |
| R2 | Dayanak içeriği | **`fatura_inceleme_ref` → `Fatura İnceleme {ref}`**; kural metni/SUT’a açık atıf varsa opsiyonel SUT section ekle. **ASLA** `gate_b_sources` / `F000*` / `C000*` |
| R3 | Kolon adı | **Dayanak** (TR) / **Basis** (EN) — SUT-only değil |
| R4 | MEDULA readiness satırları | Mevcut playbook `sut_anchor` aynı kalsın (gerçek SUT dayanağı) |
| R5 | Kod-listeli kurallar (41) | Davranış aynı: kod overlap → göster; dayanak yine FI section ref |
| R6 | Kodsuz branş (~15) | **Option B (kilitli 2026-07-29):** `relevance_signals` yoksa **gösterme**; ORTOPEDİ-6 (+ ORTAK-6) sinyalli |

---

## Dayanak formatı (UI)

Tek string `sut_anchor` (alan adı geriye uyumluluk için kalabilir) veya yeni `basis_label` — tercihen mevcut `sut_anchor` doldurulsun ki FE tek kolon okusun.

| Satır türü | Örnek değer |
|---|---|
| FI doc | `Fatura İnceleme ORTAK-24` |
| FI doc + açık SUT ek/atıf (opsiyonel, kurala özel) | `Fatura İnceleme ORTAK-17 · SUT EK-2/C` |
| MEDULA readiness | Playbook’taki mevcut SUT anchor (değişmez) |

**Yasak UI değerleri:** `F000029`, `["F000029"]`, `C000702`, ham `gate_b_sources`.

İsteğe bağlı (aynı PR veya hemen sonraki): satırda `basis_kind`: `fatura_inceleme` | `sut` — FE ikon/etiket için; zorunlu değil.

---

## Relevans gate — ORTAK kodsuz (6)

Claim context’ten türetilen sinyaller (mevcut `PatientClaimContext` + katalog membership; yeni EMR belgesi yok):

| Ref | Mesaj özeti | Gate (hepsi AND/OR net) |
|---|---|---|
| **ORTAK-5** | Ayaktan muayene ↔ tanı | `care_setting` outpatient / ayaktan **veya** poliklinik department sinyali |
| **ORTAK-17** | EK-2/C yeterli bilgi | Billed proc’ta **en az bir EK-2/C** üyelik (`procedure_annex_membership` / catalog) |
| **ORTAK-21** | Cerrahi biyopsi → patoloji | Cerrahi/package kod **veya** biyopsi-ish kod heuristiği (kod listesi veya name token: biyopsi/eksizyon/rezeksiyon — plan Phase 1’de sabit allowlist) |
| **ORTAK-24** | TPN günleri | TPN-related procedure/drug code allowlist (EK-2/B TPN kodları; katalog name `TPN` / parenteral nütrisyon) |
| **ORTAK-27** | Detaylı epikriz / ameliyat notu | Günübirlik **veya** yatan **veya** YBÜ (care_setting / department / 510090\|P5520xx) |
| **ORTAK-29** | Taburcu günü EK-2/B | Discharge date == service date (veya claim discharge-day flag) **ve** en az bir EK-2/B itemized satır |

Gate başarısız → kural checklist’e **eklenmez**.

---

## Relevans gate — branş kodsuz (16)

Bugün: sadece branş keyword → geniş.

**Minimum bu PR:** branş match **ve** (claim’de o branşla uyumlu en az bir proc **veya** mevcut `procedure_code_any` dolu kurallar zaten kod gate’li).

Kodsuz branş kuralları için:

| Yaklaşım | Seçim |
|---|---|
| A — Branş keyword yeter (status quo) | Reddedildi (spam) |
| B — Branş + “any surgical/proc in claim” | Hâlâ geniş |
| **C — Branş + kurala özel sinyal** (tercih) | ORTOPEDİ-6 → ortopedi **ve** ortopedik cerrahi kod allowlist / name tokens; diğer 15 için Phase 1’de ya allowlist ya “show only if branch match **and** claim has ≥1 code in that branch’s high-risk set” |

**Pratik Phase 1 split:**

1. **ORTAK-6** (yukarıdaki tablo) — zorunlu.  
2. **ORTOPEDİ-6** — ortopedi keyword + (cerrahi kod / grafi-relevant proc allowlist).  
3. Diğer 15 kodsuz branş — **aynı PR’da:** branş match kalır **ama** claim’de `procedure_lines` boşsa zaten yok; ek sıkılaştırma: `procedure_code_any` boş branş kurallarını **varsayılan gizle**, yalnız `relevance_signals` JSON alanı eklenince aç (opt-in metadata). Böylece spam kesilir; eksik sinyal sonra doldurulur.

Alternatif (daha agresif, tek PR): 15’i de geçici suppress + TODO. **Tavsiye: opt-in `relevance_signals` metadata** — boşsa gösterme.

---

## Architecture

```
fatura_inceleme_checklist.json
  (+ optional relevance_signals per rule)
        ↓
check_fatura_inceleme_checklist / _condition_matches
  + new _relevance_matches(rule, context)   // code-less ORTAK/branch
        ↓
claim_submission_checklist._documentation_requirement_items
  sets sut_anchor = format_fi_basis(fatura_inceleme_ref [, sut_section_label])
  NEVER gate_b_sources
        ↓
FE: label "Dayanak"; still reads sut_anchor
```

Context enrichment in `_build_fatura_inceleme_checklist_context`:
- `annex_flags`: has_ek2c, has_ek2b  
- `care_setting` / inpatient|outpatient|day_case|icu hints  
- `discharge_day_itemized` bool  
- `has_tpn`, `has_surgery_or_biopsy` bools (allowlist)

---

## Phases / Subtasks

### Phase 0 — Plan lock

- [x] Bu plan onaylandı (dayanak = FI/SUT **section**, not F/C ids); **Option B** kilitli
- [x] `tasks/todo.md` bu task ile güncellendi

### Phase 1 — Backend relevans + dayanak map

- [x] `_relevance_matches` + ORTAK-6 sinyal tablosu
- [x] Kodsuz branş: `relevance_signals` yoksa **gösterme** (ORTOPEDİ-6 sinyalli)
- [x] Context builder: EK-2/B/C, care setting, TPN, cerrahi/biyopsi, taburcu-günü
- [x] Adapter: `sut_anchor = "Fatura İnceleme {fatura_inceleme_ref}"` (+ opsiyonel SUT ek etiketi)
- [x] Unit tests (spam / TPN / dayanak / 0003-011)

### Phase 2 — Frontend i18n

- [x] TR: **Dayanak**
- [x] EN: **Basis**
- [x] Footnote FI+SUT

### Phase 3 — Verify

- [x] Unit testler yeşil

---

## Implementation review (2026-07-29)

Option B landed. Code-less rules without `relevance_signals` stay hidden. Wired signals: ORTAK-5/17/21/24/27/29 + ORTOPEDİ-6. UI dayanak = `Fatura İnceleme {ref}` (± `sut_section_label`); never gate_b F/C ids.

---

## Out of Scope

- FI algorithmic (`fatura_inceleme`) violation path değişikliği  
- Belge var/yok EMR entegrasyonu (hâlâ advisory)  
- A2 ayrı UI bloğu (istersen sonraki PR)  
- 15 branş kodsuz için mükemmel klinik NLP  
- `gate_b_sources` alanını JSON’dan silmek (registry/provenance için kalabilir; **UI’ya çıkmaz**)

---

## Riskler

| Risk | Mitigasyon |
|---|---|
| Gate fazla sıkı → gerçekten ilgili uyarı kaçırılır | Allowlist’leri FI metin + katalog name ile geniş tut; test + 1–2 sentetik senaryo |
| `care_setting` eksik sentetikte | Department/token fallback; test fixture net |
| `sut_anchor` adı kafa karıştırır | FE label “Dayanak”; gerekirse sonraki PR’da `basis_label` alias |

---

## Success criteria

1. Proc’lu ama TPN/EK-2/C/cerrahi/taburcu-günü olmayan claim’de 6 ORTAK kodsuz **toplanmaz**.  
2. FI checklist satırlarında dayanak = `Fatura İnceleme …` (section ref), asla F/C corpus id.  
3. UI kolon başlığı SUT’a kilitli değil.  
4. Kod-eşleşen FI doc kuralları + MEDULA readiness bozulmaz.
