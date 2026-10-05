# Erişkin somatropin: kapalı epifiz tanı/stimülasyon draft kaynak incelemesi

Verified main `3d29a1fefa2b89f9a8d38e2dccab6fe2285c861e` tabanında bağımsız kaynak incelemesi yapıldı. Bu rapor ve yeni candidate kanıt dosyası source-date admission veya klinik yorum release sağlamaz. Durum: `verification_status=ai_generated_pending_review`, `source_date_admission=false`, `independent_clinical_interpretation_released=false`, `runtime_branch_eligibility_implemented=false`, `clinical_eligibility_complete=false`.

Mevcut `data/gazette/source_evidence/adult_gh_closed_epiphysis_context.json` baytları korunur; SHA256 `990915b34ed0c9d6b5afee1cb1b9fb12d626c8a2b7e7caea759d50fabe50eba7`. Dosya bugün source-only, boş predicate listesi ve kapalı runtime branch bildirir (satır 14–17); epifiz kapanmasının erişkin yaştan çıkarılmayacağını açıkça belirtir (satır 9–12).

Ham DOCX kanıtı doğrudan ZIP içindeki `word/document.xml` body paragraflarından kontrol edildi. Her belgenin 10 sabitlenmiş paragrafı için tam metin SHA256, etkin metin ve tek tek çizili run ayrımı kaynak JSON'uyla birebir eşleşti: toplam **20/20**, uyuşmazlık **0**. İki belgedeki etkin bağlam aynı. Eski “Erişkinlerde” başlığı tamamen çizilmiş; etkin başlık somatropin kullanım ilkeleridir (context satır 261–319).

| Belge | Tam DOCX SHA256 | Zero-based context paragrafları |
|---|---|---|
| `sut-aug29.docx` / ham 29.08.2026 SUT | `e6697a42cb24e20335c0a59ef9f9b7554d95a2db9a0280a90617564df9538821` | 4261–4270 |
| `2026-10-02-SGK-consolidated.docx` / ham 02.10.2026 SUT | `227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573` | 4269–4278 |

Tam ham dosya yolları:
- `raw data/2026.08.29-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/2026.08.29-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/29.08.2026 - Değişiklik Tebliği İşlenmiş Güncel 2013 SUT.docx`
- `raw data/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/02.10.2026 - Değişiklik Tebliği İşlenmiş Güncel 2013 SUT.docx`

[SGK'nin 2 Ekim 2026 konsolide SUT duyurusu](https://www.sgk.gov.tr/duyuru/detay/02102026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-10-02-02-50-06) yayın sayfası da salt okunur açıldı. Sayfanın erişilebilir olması veya yerel DOCX hash eşitliği yeni aile için hizmet tarihine göre admission anlamına gelmez.

Beş operative canonical anahtar mevcut `data/gazette/sut_clauses.parquet` içinde `is_in_force=true` olarak doğrulandı. Tam etkin paragraf metinleri, tam SHA256'ları ve iki DOCX'teki indeksleri yeni `data/gazette/source_evidence/adult_gh_closed_epiphysis_candidate.json` içindedir:

| Canonical kaynak | Source context satırı | Dar anlam |
|---|---:|---|
| `4.2.6.A-2.(2)#5589013c` | 335 | Kapalı epifiz dalını tanımlar; tek başına tanı/uygunluk predicate'i değildir. |
| `4.2.6.A-2.a#80b6dded` | 347 | Çocukluk GH eksikliği tanısı + önceki GH tedavisi + epifiz kapanması nedeniyle kesilme + tekrarlanan iki yetersiz uyarı testi. |
| `4.2.6.A-2.b#9b0bad75` | 359 | Hipotalamohipofizer hastalığa bağlı erişkin GH eksikliği şüphesi + iki yetersiz uyarı testi. |
| `4.2.6.A-2.(3)#3c094940` | 379 | Prolaktin/GH dışındaki en az bir ek ön hipofiz hormonu eksikliği gerekli test sayısını bire indirir. |
| `4.2.6.A-2.(4)#e9d92dba` | 391 | Yalnız ITT için pik GH <3 mcg/L ve bunun raporda belirtilmesi. |

Candidate dış bağlamı açık `gh_patient_group=adult`, `epiphyses_closed=true`, `gh_treatment_phase=initiation` gerektirir. Yaş/ICD/reçete uzmanlığından epifiz kapanması veya tanı yolu türetilmez. Açık epifiz/pediatrik çapraz atıf, devam tedavisi, somatrogon, kimliği belirsiz genel GH ifadeleri ve diğer ilaçlar bu paket dışındadır (context satır 17; mevcut somatropin rule kaynakları `data/gazette/prose_rule_sources/drug_indication/4.2.6.A-2.yaml:12–22,23–54`).

Dar typed sözleşmede `diagnosis_pathway` yalnız `childhood_onset_retest` veya `adult_hypothalamic_pituitary` olabilir. Çocukluk yolu üç ayrı belgelenmiş boolean taşır: `childhood_gh_deficiency_diagnosed`, `childhood_gh_treatment_received`, `gh_stopped_due_to_epiphyseal_closure`. Diğer yol `adult_hypothalamic_pituitary_gh_deficiency_suspected` taşır. `additional_anterior_pituitary_deficiency_confirmed`, **PRL ve GH hariç** en az bir ek ön hipofiz eksikliğinin belgelenmiş klinik doğrulamasıdır; genel “hipofiz eksikliği” alias'ı yeterli değildir. Bu istisna tanı yolu önkoşullarını kaldırmaz. Typed hazırlık: `src/bilun/domain/claims/adult_gh.py:19–44,99–135`.

Her stimulation kaydı ayrı `test_id`, `performed_on`, açık `kind=itt|other`, `inadequate_response_documented`, ITT için `peak_gh_mcg_l` ve `peak_gh_documented_in_report`, çocukluk yolu için `retest_after_epiphyseal_closure_stop` taşır. Eksik/invalid boolean, sayı, tarih veya koleksiyon unknown/review kalır. Geçersiz ya da çelişkili testler başarılı bir altküme oluşturmak için atılmaz. `applies_on` ve `assessment_date` açık belgesel tarihlerdir; gerçek `drug_claim_date` yerine bugün kullanılmaz.

Kaynak iki farklı test türü veya maksimum iki test şartı koymaz. İkiden fazla kayıt tek başına klinik ret nedeni olamaz; fazla/çelişkili kayıtların seçimi bağımsız klinik yorum gerektirir. Kontrendikasyon yokken ITT “tercih edilmelidir”; bu ifade otomatik no-pay şartına çevrilmez. ITT yok ve kontrendikasyon yok/belirsiz durumunda review gerekir. Diğer testlerin yetersiz yanıtı belgelenmiş klinik yorumdur; <3 eşiği diğer testlere uygulanmaz. Yeni test güncellik sınırı, başka test eşiği veya kontrendikasyon listesi eklenmez.

Mevcut source-authority yenilemesi yalnız 12 isimli aileyi kapsar; adult GH diagnosis/stimulation ailesi listede yoktur (`data/gazette/source_authority/review_receipt_2026_10_05.json:7–20`). Mevcut non-mecasermin GH legacy kapsamının değiştirilmediği katalogda açıktır (`data/gazette/source_authority/clinical_versions.json:5–7`). `2024-05-17` başlık sınırı ilk tarihî yürürlük veya eksik tarih penceresi kanıtı değildir; yeni history window eklenmez. Source authority resolver da yalnız listelenmiş aile/pencereyi admit eder (`src/bilun/domain/prose_rules/_drug_indication/source_authority.py:311–352`).

İzole API/UI dosyaları ayrı owner tarafından hazırlanmıştır: `src/bilun/api/adult_gh_clinical_draft.py:1–4`, `frontend/src/lib/api/adultGhEvidence.ts:1–39`, `frontend/src/components/tabs/sut/sections/AdultGhClinicalDraft.tsx:74–80`. API helper router içermez; component kayıtlı claim formuna bağlı değildir. Bu kaynak incelemesi API/UI fonksiyonel testlerinin tamamlandığını iddia etmez. Ortak model/adapter/parsing/validation, `clinical.py`, app/router/form kaydı ve ortak clinicalEvidence/clinicalFields/SUT/messages entegrasyonu parent/MDS sahiplik koordinasyonunu bekler (`tasks/todo.md:11–21`). Bu rapor çalışan aktif routing iddiası veya ortak dosya yazma yetkisi sağlamaz.

Kaydı yapılmamış candidate evaluator `src/bilun/domain/prose_rules/adult_gh_draft.py` yoluna taşınır; bu yalnız izole hazırlık yerleşimidir ve aktif `_drug_indication` paketine runtime/coverage kaydı değildir. Beş coverage artifact (`sut_clause_coverage.parquet`, `sut_coverage_by_rule.parquet`, `sut_coverage_by_section.parquet`, `sut_registry_coverage.parquet`, `sut_coverage_evidence.json`) verified main tabanıyla byte düzeyinde aynıdır; coverage sayıları ve kayıtlı kapsam baseline kalır. Gelecekte aktif entegrasyon yapan owner, yeni evaluator dependency'sini açıkça envantere almalı ve canonical dependency/hash pinlerini ortak sahiplik koordinasyonuyla yenilemelidir. Bu taşıma source-date admission, bağımsız klinik yorum release veya ödeme clear yetkisi sağlamaz.

Yeni source-date admission ve bağımsız clinical-interpretation release tamamlanmadan sonuç **gated draft / unknown / review** kalmalı. Candidate gerekli olguları ayrı değerlendirebilir; board report varlığı veya candidate pass yeni ödeme clear sonucu oluşturmaz. Tam klinik veya ödeme uygunluğu ilan edilmez. Bu owner yalnız yeni rapor/evidence dosyalarını yazar; compiler/generated artifact, ortak kod/test, deployment, main/VPS ve tarih kabulü değişikliği yapmaz. Bu rapor için full suite çalıştırılmadı; raw/hash/corpus eşitliği salt okunur assertion ile doğrulandı.
