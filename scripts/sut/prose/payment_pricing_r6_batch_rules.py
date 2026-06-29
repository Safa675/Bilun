"""SUT §2.2 / §2.3 / §2.5 — payment-method & pricing rules (r6 batch).

59 in-force deontic clauses encoded from
`tasks/encode_waves/REM_2_5_2_2_2_3.csv` spanning:
  * §2.2 / §2.2.1 / §2.2.2 — Kurumca finansman yöntemleri, ayakta ve yatarak
    ödeme esasları (ödemeye esas katsayı, ayakta ödeme EK-2/A, tanıya dayalı
    işlem paket kapsamı, hizmet başı ödeme);
  * §2.3 / §2.3.1 — acil hal tanımı ile sözleşmesiz sunuculardan acil hizmet
    bedellerinin karşılanması / faturalandırılması;
  * §2.5 / §2.5.1 / §2.5.2 / §2.5.3 — yurt dışı sağlık hizmetleri (geçici
    görev, yurt dışında bulunan sigortalılar, yurt dışı tedavi/tetkik/sevk,
    yol-gündelik-refakatçi).

Rule shape follows the established wave-2a / r6 prose pattern: a flat
``condition`` block plus a nested ``action`` block (``enforcement`` +
``message_tr``) for each deontic modality (COVERAGE / MANDATORY /
MUST_BILL / MUST_NOT_BILL / NO_PAY / PERMISSION / REGULATORY_ACTION).
Each rule maps exactly one ``gate_b_sources`` clause_id; ``message_tr`` is
sourced from the clause's in_force_text (condensed, Turkish).
"""

from __future__ import annotations

from typing import Any

BATCH_RULES: list[dict[str, Any]] = [

    # ────────────────────────────────────────────────────────────────────────
    # §2.2 — Kurumca finansmanı sağlanan sağlık hizmetleri (genel esaslar)
    # ────────────────────────────────────────────────────────────────────────

    # C000519 — MANDATORY: SUT/eki listelerde olmayan yöntem için Kurum onayı + Fiyatlandırma Komisyonu bedeli
    {
        "rule_id": "2.X.sut_disi_yontem_kurum_onayi_fiyatlandirma",
        "sut_section": "2.2",
        "condition": {
            "method_in_sut_or_annex_lists": False,
        },
        "action": {
            "enforcement": "mandatory: methods not listed in SUT/annexes require Kurum acceptance and a Health Services Pricing Commission price before payment",
            "message_tr": (
                "Kurumca finansmanı sağlanan sağlık hizmetlerinin teşhis ve tedavi yöntemleri SUT ve eki listelerde "
                "belirtilmiştir. SUT ve eki listelerde yer almayan teşhis ve tedavi yöntemlerinin bedellerinin "
                "Kurumca karşılanabilmesi için Kurum tarafından uygun olduğunun kabul edilmesi ve Sağlık Hizmetleri "
                "Fiyatlandırma Komisyonu tarafından Kurumca ödenecek bedellerinin belirlenmesi gerekmektedir."
            ),
        },
        "gate_b_sources": ["C000519"],
        "encode_batch": "R6",
    },
    # C000522 — COVERAGE: finansman, Kurumla satın alma sözleşmesiyle; sözleşmesizden yalnız acil
    {
        "rule_id": "2.X.finansman_sozlesmesi_ve_sozlesmesiz_acil",
        "sut_section": "2.2",
        "condition": {
            "service_via_purchase_contract": True,
            "uncontracted_provider_non_emergency": True,
        },
        "action": {
            "enforcement": "coverage: financed health services are met via Kurum–provider purchase contracts; uncontracted providers are paid only for emergencies",
            "message_tr": (
                "Finansmanı sağlanan sağlık hizmetleri, Kurumla sağlık hizmeti sunucuları arasında sağlık hizmeti "
                "satın alımı sözleşmeleri yapılması suretiyle karşılanır. Sözleşmesiz sağlık hizmeti sunucularından "
                "ise acil hallerde alınan sağlık hizmetlerinin bedelleri Kurumca karşılanır."
            ),
        },
        "gate_b_sources": ["C000522"],
        "encode_batch": "R6",
    },
    # C000525 — COVERAGE: Bakanlık dışı 1. basamak/kamu kurum hekimliğinden ücret talep edilmez; reçeteler Kurumca
    {
        "rule_id": "2.X.bakanlik_disi_birinci_basamak_ucretsiz_reçete",
        "sut_section": "2.2",
        "condition": {
            "provider_category": "non_moh_first_step_public_or_public_agency_physician",
        },
        "action": {
            "enforcement": "coverage: no fee demanded from the Institution for non-MoH 1st-step public/agency physician services; compliant drugs & medical goods are reimbursed",
            "message_tr": (
                "Sağlık Bakanlığı dışındaki birinci basamak resmi sağlık kuruluşları ile kamu idareleri bünyesindeki "
                "kurum hekimlikleri tarafından verilen sağlık hizmetleri için Kurumdan herhangi bir ücret talep "
                "edilemez. Bu birimlerde görevli hekimler tarafından SUT ve eki listelerde yer alan usul ve esaslar "
                "dâhilinde reçete edilmiş ilaç ve tıbbi malzeme bedelleri Kurumca karşılanır."
            ),
        },
        "gate_b_sources": ["C000525"],
        "encode_batch": "R6",
    },
    # C000527 — COVERAGE: kişice ibraz edilen tetkik/tahlil faturası sevk belgesine dayanılarak kişiye ödenir, mahsup
    {
        "rule_id": "2.X.kisi_tetkik_faturasi_sevk_uzerine_odeme_mahsup",
        "sut_section": "2.2",
        "condition": {
            "patient_submits_lab_invoice_with_referral": True,
        },
        "action": {
            "enforcement": "coverage: lab invoices submitted by patients are paid to the patient based on the referral/order and offset against the ordering contracted provider; MoH via global budget",
            "message_tr": (
                "Sözleşmeli sağlık hizmeti sunucularındaki tedaviler ile ilgili olarak kişilerce Kuruma ibraz edilen "
                "tetkik ve/veya tahlile ilişkin fatura bedelleri sevk/istem belgesine dayanılarak kişilere ödenir ve "
                "sevk/istem belgesini düzenleyen sözleşmeli sağlık hizmeti sunucusunun alacağından mahsup edilir. "
                "Sağlık Bakanlığına bağlı sağlık hizmeti sunucuları için Bakanlığa yapılan global bütçe ödemesinden "
                "mahsup edilir."
            ),
        },
        "gate_b_sources": ["C000527"],
        "encode_batch": "R6",
    },
    # C000533 — REGULATORY_ACTION: ödemeye esas puan × katsayı (0,593); virgülden sonra 2 basamak
    {
        "rule_id": "2.X.ek2b_ek2c_puan_x_katsayi_0593_iki_basamak",
        "sut_section": "2.2",
        "condition": {
            "annex_basis_any": ["EK-2/B", "EK-2/C", "EK-2/Ç"],
        },
        "action": {
            "enforcement": "regulatory-action: EK-2/B, EK-2/C, EK-2/Ç procedure fee = points × coefficient (0,593); 2 decimals, no rounding",
            "message_tr": (
                "Komisyonca SUT eki EK-2/B, EK-2/C ve EK-2/Ç listelerinde yer alan işlemler için ödemeye esas puanlar "
                "ile katsayı (0,593) belirlenmiş olup işlem bedeli ilgili puan ile katsayının çarpımı sonucu "
                "bulunacak tutardır. Puanın katsayı ile çarpımı sonucu bulunan tutar yuvarlama yapılmaksızın "
                "virgülden sonra iki basamak olacak şekilde alınır."
            ),
            "annex_basis": "EK-2/B",
            "coefficient": 0.593,
            "decimal_places": 2,
        },
        "gate_b_sources": ["C000533"],
        "encode_batch": "R6",
    },
    # C000535 — COVERAGE: laparoskopik/perkütan/endoskopik/vb. yöntemlerde işlem puanı esas; ayrı kod varsa kendi puanı
    {
        "rule_id": "2.X.minimal_invaziv_yontem_islem_puani_esas",
        "sut_section": "2.2",
        "condition": {
            "method_any": ["laparoscopic", "percutaneous", "endoscopic", "endosonographic",
                           "microsurgery", "robotic_surgery"],
            "separate_code_exists": False,
        },
        "action": {
            "enforcement": "coverage: lap/endoscopic/percutaneous/micro/robotic methods are paid at the SUT procedure point; if a separate code exists the method's own point applies",
            "message_tr": (
                "SUT eki EK-2/B ve EK-2/C listelerinde yer alan işlemlerin laparoskopik, perkütan, endoskopik, "
                "endosonografik, mikrocerrahi, robotik cerrahi gibi yöntemlerle yapılması halinde SUT’ta yer alan "
                "işlem puanı esas alınarak Kurumca karşılanır. Ancak ayrı kodu bulunan bu yöntemlerle yapılan "
                "işlemler kendi puanı esas alınarak Kurumca karşılanır."
            ),
            "annex_basis": "EK-2/B",
        },
        "gate_b_sources": ["C000535"],
        "encode_batch": "R6",
    },
    # C000536 — COVERAGE: trafik kazası sözleşmesiz ilk müdahale; devam tedavisi SUT'la, 6 ayı geçemez
    {
        "rule_id": "2.X.trafik_kazasi_sozlesmesiz_devam_6ay",
        "sut_section": "2.2",
        "condition": {
            "origin_is_traffic_accident": True,
            "initial_care_at_uncontracted_provider": True,
            "months_from_accident": {"min": 7},
        },
        "action": {
            "enforcement": "coverage: traffic-accident continuation care at the uncontracted initial-care provider is covered per SUT, not exceeding 6 months from the accident",
            "message_tr": (
                "Trafik kazası nedeniyle ilk müdahalenin sözleşmesiz sağlık hizmeti sunucularında sağlanması halinde "
                "bu sunucuda trafik kazası nedeniyle sunulan sağlık hizmetinin devamı niteliğindeki tedaviler SUT ve "
                "ekleri esas alınarak Kurumca karşılanır; bu süre trafik kazasının oluştuğu tarihten itibaren 6 ayı "
                "geçemez."
            ),
        },
        "gate_b_sources": ["C000536"],
        "encode_batch": "R6",
    },
    # C000537 — MANDATORY: geri ödeme kuralı olmayan hizmetlerde güncel bilimsel klinik uygunluk
    {
        "rule_id": "2.X.kural_yok_guncel_klinik_uygunluk",
        "sut_section": "2.2",
        "condition": {
            "no_reimbursement_rule_or_criteria": True,
        },
        "action": {
            "enforcement": "mandatory: for services lacking reimbursement rules/criteria, current scientific clinical appropriateness is required",
            "message_tr": (
                "Kurumca finansmanı sağlanan sağlık hizmetlerinde geri ödeme kural ve/veya kriterleri belirlenmemiş "
                "sağlık hizmetleri için güncel bilimsel klinik uygunluğun bulunması gerekir."
            ),
        },
        "gate_b_sources": ["C000537"],
        "encode_batch": "R6",
    },

    # ── §2.2.1.B-1 — Ayakta tedavilerde ödeme (EK-2/A) ──────────────────────

    # C000561 — COVERAGE: ayaktan her başvuru için EK-2/A sınıf tutarı; dolu branşta mesai dışı 2 kat; EK-2/A-2 ilave
    {
        "rule_id": "2.X.ek2a_ayakta_basvuru_sinif_tutar_2kat_ek2a2",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "outpatient_visit": True,
        },
        "action": {
            "enforcement": "coverage: outpatient visits are paid per EK-2/A-1 class via the EK-2/A tariff; after-hours full-booked MoH 2nd/3rd-step specialty visits at 2× EK-2/A; EK-2/A-2 items additionally billable",
            "message_tr": (
                "“Ayakta tedavilerde ödeme” kapsamında her bir başvuru için EK-2/A-1 sınıfına göre belirlenen EK-2/A "
                "tutarları esas alınır; Bakanlığa bildirilen mesai saatlerinde aynı gün randevusu dolu branşlarda "
                "Bakanlığa bağlı 2./3. basamak sunucularında uzman hekimlerce mesai dışı sunulan poliklinik "
                "hizmetleri için EK-2/A tutarlarının iki katı esas alınır; EK-2/A-2 ilave işlemleri ayrıca "
                "karşılanır."
            ),
            "annex_basis": "EK-2/A",
        },
        "gate_b_sources": ["C000561"],
        "encode_batch": "R6",
    },
    # C000569 — COVERAGE: 2./3. basamaktan başka sunucuya sevk halinde sevk edene EK-2/A'nın %75'i
    {
        "rule_id": "2.X.ek2a_sevk_eden_sunucuya_yuzde75",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "referral_from_tier_any": ["second_step", "third_step"],
            "to_different_provider": True,
        },
        "action": {
            "enforcement": "coverage: when a patient is referred from a 2nd/3rd-step provider to another provider, 75% of the EK-2/A tariff is paid to the referring provider",
            "message_tr": (
                "Hastanın ikinci veya üçüncü basamak sağlık hizmeti sunucusundan başka bir sağlık hizmeti sunucusuna "
                "sevk edilmesi halinde sevk eden sağlık hizmeti sunucusuna EK-2/A Listesinde yer alan tutarın "
                "%75’i ödenir."
            ),
            "annex_basis": "EK-2/A",
            "referral_payment_fraction": 0.75,
        },
        "gate_b_sources": ["C000569"],
        "encode_batch": "R6",
    },

    # ── §2.2.1.B-2 — Ayaktan ilave faturalandırma (enjeksiyon/pansuman) ─────

    # C000590 — COVERAGE: başka sunucuda tedavi gören hastaya sadece enjeksiyon bedeli
    {
        "rule_id": "2.X.dis_sunucu_hasta_sadece_enjeksiyon_bedeli",
        "sut_section": "2.2.1.B-2",
        "condition": {
            "patient_treated_elsewhere": True,
            "service_rendered": "injection_only",
        },
        "action": {
            "enforcement": "coverage: for patients treated at another provider, only the injection fee is covered",
            "message_tr": (
                "Başka bir sağlık hizmeti sunucusunda hizmet almış hastaların yapılan enjeksiyonları için sadece "
                "enjeksiyonun bedeli karşılanır."
            ),
            "annex_basis": "EK-2/A-2",
        },
        "gate_b_sources": ["C000590"],
        "encode_batch": "R6",
    },
    # C000603 — COVERAGE: sadece enjeksiyon/pansuman amacıyla gelen için sadece bu bedel
    {
        "rule_id": "2.X.sadece_enjeksiyon_pansuman_amaci_bedel",
        "sut_section": "2.2.1.B-2",
        "condition": {
            "visit_purpose": "injection_or_dressing_only",
        },
        "action": {
            "enforcement": "coverage: patients presenting solely for injection/dressing are reimbursed only for the injection/dressing fee",
            "message_tr": (
                "Sadece enjeksiyon/pansuman amacıyla gelen hasta için sadece enjeksiyon/pansuman bedeli "
                "karşılanır."
            ),
            "annex_basis": "EK-2/A-2",
        },
        "gate_b_sources": ["C000603"],
        "encode_batch": "R6",
    },

    # ── §2.2.1.B-3 — Tıbbi malzeme temini ───────────────────────────────────

    # C000620 — MUST_BILL: tıbbi malzeme sunucuca temin zorunlu; faturalandırılabilir olan ilaveten; ilaç eczane
    {
        "rule_id": "2.X.tibbi_malzeme_sunucuca_temin_ilave_fatura",
        "sut_section": "2.2.1.B-3",
        "condition": {
            "medical_material_used": True,
        },
        "action": {
            "enforcement": "must-bill: all medical materials must be provided by the provider; billable ones are additionally invoiced (non-reimbursed excluded); drugs dispensed from contracted pharmacies when prescribed",
            "message_tr": (
                "Hastaya kullanılan her türlü tıbbi malzemenin sağlık hizmeti sunucusu tarafından temini "
                "zorunludur. Kurumca bedeli karşılanmayanlar hariç, temin edilen faturalandırılabilir tıbbi "
                "malzeme bedelleri ilaveten faturalandırılır. Reçete edilmesi halinde ilaçlar sözleşmeli "
                "eczanelerden temin edilir."
            ),
        },
        "gate_b_sources": ["C000620"],
        "encode_batch": "R6",
    },

    # ── §2.2.1.B-4 — Uzaktan hasta değerlendirme ────────────────────────────

    # C000626 — REGULATORY_ACTION: uzaktan değerlendirme başvurusu acil hariç tüm branşlar toplamının %15'ini geçemez
    {
        "rule_id": "2.X.uzaktan_degerlendirme_yuzde15_siniri",
        "sut_section": "2.2.1.B-4",
        "condition": {
            "service_category": "remote_patient_assessment",
            "telemedicine_visits_share_of_outpatient": {"min": 0.16},
        },
        "action": {
            "enforcement": "regulatory-action: billed remote-assessment visits (excluding same-day emergency visits) may not exceed 15% of total outpatient visits across all branches",
            "message_tr": (
                "Uzaktan hasta değerlendirmeye yönelik sağlık hizmetlerinde başvuru sayısı, gün içindeki acil "
                "servis başvuruları hariç tüm branşlarda ayaktan başvuru sayısı toplamının %15’ini geçemez."
            ),
            "share_cap": 0.15,
        },
        "gate_b_sources": ["C000626"],
        "encode_batch": "R6",
    },

    # ── §2.2.2.B — Yatarak tanıya dayalı işlem kapsamı ──────────────────────

    # C000662 — MUST_NOT_BILL: göğüs bölgesi planlı ameliyatlarda kapalı göğüs drenajı/tüpü ayrıca faturalanmaz
    {
        "rule_id": "2.X.gogus_ameliyati_drenaj_tupu_dahil",
        "sut_section": "2.2.2.B",
        "condition": {
            "surgery_region": "thoracic",
            "procedure_any": ["closed_chest_drainage", "chest_tube"],
            "is_planned_surgery": True,
        },
        "action": {
            "enforcement": "must-not-bill: closed chest drainage / chest tube insertion is not separately billed for planned thoracic-region surgeries",
            "message_tr": (
                "Anatomik olarak göğüs bölgesinde yapılacak planlı ameliyatlarda, kapalı göğüs drenajı veya göğüs "
                "tüpü takılması ayrıca faturalandırılmayacaktır."
            ),
        },
        "gate_b_sources": ["C000662"],
        "encode_batch": "R6",
    },
    # C000665 — MUST_BILL: eğitim-araştırma/üniversite SUIAM'larında EK-2/C (*) işlemlerine %30 ilave
    {
        "rule_id": "2.X.egitim_arastirma_universite_ek2c_yildiz_yuzde30",
        "sut_section": "2.2.2.B",
        "condition": {
            "provider_category_any": [
                "moh_training_research_hospital",
                "state_university_with_medical_faculty",
                "foundation_university_with_medical_faculty",
            ],
            "procedure_has_ek2c_star_marker": True,
        },
        "action": {
            "enforcement": "must-bill: EK-2/C (*) procedures performed by training-research/university SUIAMs are billed at listed points + 30%",
            "message_tr": (
                "Sağlık Bakanlığına bağlı eğitim ve araştırma hastaneleri ile Tıp Fakültesi Bulunan Devlet/Vakıf "
                "Üniversiteleri Sağlık Uygulama ve Araştırma Merkezlerince yapılan EK-2/C Listesinde yanında (*) "
                "işareti olan işlemler, listede belirtilen puanlara %30 ilave edilerek faturalandırılır."
            ),
            "annex_basis": "EK-2/C",
            "point_uplift_fraction": 0.30,
        },
        "gate_b_sources": ["C000665"],
        "encode_batch": "R6",
    },

    # ── §2.2.2.B-1 — Tanıya dayalı işlem kapsamı (ek bileşenler) ────────────

    # C000677 — MUST_BILL: yatış dönemi ilaçları dahil; kan ürünleri ayrıca (kanama durdurma/yapıştırıcı hariç)
    {
        "rule_id": "2.X.yatis_donemi_ilaclari_dahil_kan_urunu_ayri",
        "sut_section": "2.2.2.B-1",
        "condition": {
            "inpatient_stay": True,
            "service_category": "inpatient_drugs",
        },
        "action": {
            "enforcement": "must-bill: inpatient-period drugs are included; blood products billed separately (hemostatic/sealant/tissue-adhesive drugs are not in this scope)",
            "message_tr": (
                "Yatış dönemindeki ilaçlar tanıya dayalı işlem kapsamındadır; kan ürünleri ayrıca "
                "faturalandırılır; ancak kanama durdurma, sızdırmazlık sağlama ve doku yapıştırmada kullanılan "
                "ilaçlar bu kapsamda değerlendirilmez."
            ),
        },
        "gate_b_sources": ["C000677"],
        "encode_batch": "R6",
    },
    # C000681 — MUST_BILL: tanıya dayalı işlemde kullanılan kan bileşenlerine kod bazında %'li fatura; MEDULA zorunlu
    {
        "rule_id": "2.X.kan_bilesenleri_kod_bazinda_yuzdeli_fatura_medula",
        "sut_section": "2.2.2.B-1",
        "condition": {
            "service_category": "blood_components_within_diagnosis_based_procedure",
            "blood_component_code_any": ["705371", "705430", "705440", "705372", "705373",
                                         "705441", "705442", "705443"],
        },
        "action": {
            "enforcement": "must-bill: blood components used within a diagnosis-based procedure are billed at code-specific fractions (36/24/20/28%); all blood components must be recorded in MEDULA",
            "message_tr": (
                "Tanıya dayalı işlem kapsamında kullanılan kan bileşenleri için; 705371, 705430 ve 705440 kodlu "
                "olanlar %36’sı, 705372 ve 705373 kodlu olanlar %24’ü, 705441 kodlu olan %20’si, 705442 ve 705443 "
                "kodlu olanlar %28’i oranında sunucunca ayrıca faturalandırılır. Tüm kan bileşenlerinin MEDULA "
                "sistemine kaydedilmesi zorunludur."
            ),
            "fraction_by_code": {
                "705371": 0.36, "705430": 0.36, "705440": 0.36,
                "705372": 0.24, "705373": 0.24,
                "705441": 0.20,
                "705442": 0.28, "705443": 0.28,
            },
        },
        "gate_b_sources": ["C000681"],
        "encode_batch": "R6",
    },
    # C000686 — MUST_NOT_BILL: tanı/tedavi kapsamındaki tüm işlemler dahil, ayrıca faturalanamaz
    {
        "rule_id": "2.X.tani_tedavi_kapsami_tum_islemler_dahil",
        "sut_section": "2.2.2.B-1",
        "condition": {
            "procedure_within_diagnosis_based_treatment_scope": True,
        },
        "action": {
            "enforcement": "must-not-bill: all procedures within the diagnosis-and-treatment scope are included and may not be separately billed",
            "message_tr": (
                "Tanı ve tedavi kapsamında yapılan tüm işlemler dahil olup ayrıca faturalandırılamaz."
            ),
        },
        "gate_b_sources": ["C000686"],
        "encode_batch": "R6",
    },
    # C000687 — REGULATORY_ACTION: EK-2/C "Açıklama" bölümündeki istisnalar dikkate alınır
    {
        "rule_id": "2.X.ek2c_aciklama_istisnalari_dikkate_alinir",
        "sut_section": "2.2.2.B-1",
        "condition": {
            "annex_basis": "EK-2/C",
            "procedure_has_aciklama_exception": True,
        },
        "action": {
            "enforcement": "regulatory-action: exceptions stated in the EK-2/C 'Açıklama' section must be observed",
            "message_tr": (
                "SUT eki EK-2/C Listesi “Açıklama” bölümünde belirtilen istisnalar dikkate alınacaktır."
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C000687"],
        "encode_batch": "R6",
    },
    # C000694 — MUST_BILL: üçüncü fıkradaki sürelerin aşılması halinde verilen hizmetler ayrıca faturalanır
    {
        "rule_id": "2.X.ucuncu_fikra_suresi_asimi_hizmet_basi_fatura",
        "sut_section": "2.2.2.B-1",
        "condition": {
            "diagnosis_based_procedure_time_limit_exceeded": True,
        },
        "action": {
            "enforcement": "must-bill: services delivered beyond the time limits in the third paragraph are additionally billed",
            "message_tr": (
                "Üçüncü fıkrada belirtilen sürelerin aşılması halinde verilen sağlık hizmetlerinin bedelleri "
                "ayrıca faturalandırılır."
            ),
            "annex_basis": "fee_for_service",
        },
        "gate_b_sources": ["C000694"],
        "encode_batch": "R6",
    },
    # C000695 — COVERAGE: tanıya dayalı ilaç/malzeme hastaca ödenmişse fatura kişiye; Kurum ödemesi mahsup; iade yok
    {
        "rule_id": "2.X.taniya_dayali_ilac_hastaca_odendi_kisiye_odeme_mahsup",
        "sut_section": "2.2.2.B-1",
        "condition": {
            "patient_paid_drug_or_material_within_diagnosis_based_procedure": True,
        },
        "action": {
            "enforcement": "coverage: if diagnosis-based drugs/materials were paid by the patient, the invoice is paid to the patient and offset against the provider (MoH via global budget); offset amount is never refunded",
            "message_tr": (
                "Tanıya dayalı işlem kapsamındaki ilaç ve/veya tıbbi malzeme bedellerinin hasta tarafından "
                "ödendiğinin tespiti halinde fatura tutarları hastaya ödenir; Kurumca ödenen tutar ilgili sağlık "
                "hizmeti sunucusundan (Bakanlık sunucuları için global bütçeden) mahsup edilir ve hiçbir surette "
                "iade edilmez."
            ),
        },
        "gate_b_sources": ["C000695"],
        "encode_batch": "R6",
    },

    # ── §2.2.2.B-2 / B-3 — Tamamlanmayan işlem & taburcu sonrası ────────────

    # C000697 — MUST_NOT_BILL: tanıya dayalı işlem tamamlanamazsa hizmet başı; EK-2/B %10 indirimli; kullanılmayan malzeme yok
    {
        "rule_id": "2.X.tamamlanamayan_islem_hizmet_basi_ek2b_yuzde10_indirim",
        "sut_section": "2.2.2.B-2",
        "condition": {
            "diagnosis_based_procedure_incomplete": True,
        },
        "action": {
            "enforcement": "must-not-bill (full): if a diagnosis-based procedure cannot be completed (death/complication/abandonment/stoppage), services are billed fee-for-service with EK-2/B at a 10% discount; unused materials are not billed",
            "message_tr": (
                "Tanıya dayalı işlemin yapılamaması, tedaviden vazgeçilmesi veya herhangi bir aşamada kalması "
                "halinde o zamana kadar verilen hizmetler hizmet başına ödeme yöntemiyle faturalandırılır; bu "
                "durumda EK-2/B işlem bedelleri %10 indirimli olarak faturalandırılır ve kullanılmayan "
                "malzemeler faturalandırılmaz."
            ),
            "annex_basis": "EK-2/B",
            "incomplete_procedure_discount_fraction": 0.10,
        },
        "gate_b_sources": ["C000697"],
        "encode_batch": "R6",
    },
    # C000701 — MUST_NOT_BILL: taburcu sonrası aynı sunucu/uzmanlıkta 10 gün içindeki muayene+rutin tetkikler dahil
    {
        "rule_id": "2.X.taburcu_sonrasi_10gun_muayene_rutin_tetkik_dahil",
        "sut_section": "2.2.2.B-3",
        "condition": {
            "post_discharge": True,
            "same_provider_same_specialty_outpatient": True,
            "days_within": {"max": 10},
        },
        "action": {
            "enforcement": "must-not-bill: outpatient exams and routine biochemical/bacteriological/haematological/cardiological (ECG/ECHO/effort)/radiological tests within 10 days post-discharge at the same provider/specialty are included (EK-2/A-2 excepted)",
            "message_tr": (
                "Taburcu olduktan sonraki, aynı sağlık hizmeti sunucusundaki aynı uzmanlık dalında ayaktan "
                "tedavilerinde 10 gün içerisinde EK-2/A-2 işlemleri hariç yapılan muayeneler ve bu muayene "
                "sonucunda gerekli görülen rutin biyokimyasal, bakteriyolojik, hematolojik, kardiyolojik "
                "(EKG, EKO, efor) ve radyolojik tetkikler tanıya dayalı ödeme işlem puanına dahil olup ayrıca "
                "faturalandırılamaz."
            ),
        },
        "gate_b_sources": ["C000701"],
        "encode_batch": "R6",
    },

    # ────────────────────────────────────────────────────────────────────────
    # §2.3 / §2.3.1 — Acil hal ve sözleşmesiz sunuculardan acil hizmet
    # ────────────────────────────────────────────────────────────────────────

    # C000714 — NO_PAY: acil değilken yeşil alan olarak değerlendirilen hizmet bedelleri karşılanmaz
    {
        "rule_id": "2.X.acil_servis_yesil_alan_olarak_degerlendirilen_nopay",
        "sut_section": "2.3",
        "condition": {
            "emergency_service_billed_as_emergency": True,
            "review_classified_as_green_area": True,
        },
        "action": {
            "enforcement": "no-pay: emergency-department services billed as emergency but classified by Kurum review as 'green area' are not covered; green-area exams are paid at EK-2/B 520.021; true emergencies per 2.2.1.B-2",
            "message_tr": (
                "Acil hal; ani gelişen hastalık/kaza/yaralanma sonrası ilk 24 saatte tıbbi müdahale gerektiren "
                "veya müdahale/nakil yapılmazsa hayat/sağlık bütünlüğü riski doğan durumları kapsar. Acil olmadığı "
                "tespit edilenlerin tedavi giderleri EK-2/B 520.021 “Yeşil alan muayenesi” bedeli üzerinden "
                "karşılanır; acil servislerde faturalandırılıp Kurum incelemesinde yeşil alan muayenesi olarak "
                "değerlendirilen hizmetlerin bedelleri karşılanmaz."
            ),
            "annex_basis": "EK-2/B",
            "green_area_code": "520.021",
        },
        "gate_b_sources": ["C000714"],
        "encode_batch": "R6",
    },
    # C000723 — COVERAGE: sözleşmesiz sunucuya acil müracaat; hekim imzalı belge + Kurum kabulü şartıyla
    {
        "rule_id": "2.X.sozlesmesiz_acil_hekim_imzali_belge_kabul",
        "sut_section": "2.3.1",
        "condition": {
            "provider_contracted": False,
            "emergency_as_per_sut_1_7": True,
            "physician_signed_emergency_document": False,
        },
        "action": {
            "enforcement": "coverage: uncontracted-provider emergency costs are covered only if the emergency-intervention necessity is documented by the treating physician's signed statement and accepted by the Institution",
            "message_tr": (
                "Kurum sağlık yardımlarından yararlandırılan kişilerin sözleşmesiz sağlık hizmeti sunucularına "
                "SUT’un 1.7 maddesinde tanımlanan acil haller nedeniyle müracaatı sonucu oluşan sağlık giderleri; "
                "acil tıbbi müdahale yapılmasını zorunlu kılan durumun müdahaleyi yapan hekim tarafından imzalanmış "
                "bir belge ile belgelendirilmesi ve Kurumca kabul edilmesi şartıyla karşılanır."
            ),
        },
        "gate_b_sources": ["C000723"],
        "encode_batch": "R6",
    },
    # C000724 — COVERAGE: sözleşmesiz yatarak tedavide refakatçi yatak/yemek (bir kişi; 18 yaş altı şartsız)
    {
        "rule_id": "2.X.sozlesmesiz_yatarak_refakatci_yatak_yemek",
        "sut_section": "2.3.1",
        "condition": {
            "provider_contracted": False,
            "inpatient_emergency_care": True,
        },
        "action": {
            "enforcement": "coverage: for uncontracted-provider inpatient emergency care, one companion's bed/meal costs are covered on physician's medical-necessity statement (under-18 does not require the statement)",
            "message_tr": (
                "Sözleşmesiz sağlık hizmeti sunucularındaki yatarak tedavileri Kurumca karşılanan kişiler için, "
                "hekim/diş hekimi tarafından refakatçi kalınması gerektiğini belirten belgeye dayanılarak "
                "refakatçinin yatak ve yemek giderleri bir kişi ile sınırlı olmak üzere Kurumca karşılanır. 18 "
                "yaşını doldurmamış çocuklar için refakatçi kalınmasının tıbben lüzum görülmesi şartı aranmaz."
            ),
        },
        "gate_b_sources": ["C000724"],
        "encode_batch": "R6",
    },
    # C000725 — MANDATORY: sözleşmesiz sunucularca acil tedavi bilgilerinin kaydı ve ibrazı zorunlu
    {
        "rule_id": "2.X.sozlesmesiz_acil_bilgi_kaydi_ve_ibzazi",
        "sut_section": "2.3.1",
        "condition": {
            "provider_contracted": False,
            "emergency_treatment": True,
        },
        "action": {
            "enforcement": "mandatory: uncontracted providers must record emergency-treatment data medically and produce it to the Institution on request",
            "message_tr": (
                "Sözleşmesiz sağlık hizmeti sunucularınca acil tedavilere ilişkin bilgilerin tıbbi açıdan "
                "kaydedilmesi ve Kurumca gerek görüldüğünde ibraz edilmesi zorunludur."
            ),
        },
        "gate_b_sources": ["C000725"],
        "encode_batch": "R6",
    },
    # C000726 — MUST_BILL: sözleşmesiz sunucudaki ilk acil başvuru hizmet başına ödeme yöntemiyle
    {
        "rule_id": "2.X.sozlesmesiz_ilk_acil_basvuru_hizmet_basi",
        "sut_section": "2.3.1",
        "condition": {
            "provider_contracted": False,
            "first_contact_is_emergency": True,
        },
        "action": {
            "enforcement": "must-bill: uncontracted-provider services for a first emergency contact are billed on a fee-for-service basis",
            "message_tr": (
                "Sözleşmesiz sağlık hizmeti sunucuları tarafından kişilerin ilk başvurusunun acil servislere acil "
                "hal kapsamında olması halinde sunulan sağlık hizmetleri “hizmet başına ödeme yöntemi” esas "
                "alınarak faturalandırılır."
            ),
            "annex_basis": "fee_for_service",
        },
        "gate_b_sources": ["C000726"],
        "encode_batch": "R6",
    },
    # C000727 — MUST_BILL: 24 saatte stabilize edilemeyip yatarak verilen hizmet EK-2/C varsa tanıya dayalı, yoksa hizmet başı
    {
        "rule_id": "2.X.stabilize_edilemeyen_yatarak_ek2c_taniya_dayali_hizmet_basi",
        "sut_section": "2.3.1",
        "condition": {
            "not_stabilized_within_24h": True,
            "inpatient_care_delivered": True,
            "physician_documented_and_kurum_accepted": True,
        },
        "action": {
            "enforcement": "must-bill: inpatient services when not stabilized within 24h (documented & accepted) are billed via EK-2/C diagnosis-based method if listed, otherwise fee-for-service; diagnosis-based-period services remain emergency-bundled",
            "message_tr": (
                "Hastanın acil servise başvurusundan itibaren 24 saat içinde stabilize edilememesi halinde durumunun "
                "hekimce belirtilmesi ve Kurumca kabulü şartıyla yatarak sunulan hizmetler; EK-2/C’de yer alması "
                "halinde tanıya dayalı işlem, yer almaması halinde hizmet başına ödeme yöntemiyle "
                "faturalandırılır. EK-2/C işlemi yapılması halinde tanıya dayalı işlem süresinde verilen hizmetler "
                "de acil hal kapsamında olup ayrıca faturalandırılmaz."
            ),
            "annex_basis_any": ["EK-2/C", "fee_for_service"],
        },
        "gate_b_sources": ["C000727"],
        "encode_batch": "R6",
    },
    # C000730 — COVERAGE: kişi sunucuya ödeme talebi halinde yazılı muvafakat + MEDULA; tek fatura; 2 ay içinde gönderim
    {
        "rule_id": "2.X.sozlesmesiz_acil_muafakat_medula_tek_fatura_2ay",
        "sut_section": "2.3.1",
        "condition": {
            "provider_contracted": False,
            "patient_claims_kurum_payment_to_provider": True,
        },
        "action": {
            "enforcement": "coverage: on a patient's request for the Institution to pay an uncontracted provider, written consent is taken and a single MEDULA invoice issued (contracted-provider tariffs); unbillable services must be submitted within 2 months of the next billing period",
            "message_tr": (
                "Kişilerin yazılı muvafakatı alınarak sözleşmesiz sunucularca Kuruma MEDULA üzerinden fatura "
                "edilir; kişilerce ödenen bedeller için fatura MEDULA üzerinden gönderilir. Sözleşmeli sunucu "
                "bedelleri esas alınarak tek fatura düzenlenir; döneminde faturalandırılamayan hizmet, işlem "
                "bittiği tarih itibarıyla faturalandırma dönemini takip eden en geç 2 ay içerisinde Kuruma "
                "gönderilir."
            ),
        },
        "gate_b_sources": ["C000730"],
        "encode_batch": "R6",
    },
    # C000731 — MANDATORY: kişi ödeyince EK-1/E bilgilendirme formu ile imza karşılığı bilgi verilir
    {
        "rule_id": "2.X.kisi_odedi_ek1e_bilgilendirme_formu_imza",
        "sut_section": "2.3.1",
        "condition": {
            "service_paid_by_patient": True,
            "provider_contracted": False,
        },
        "action": {
            "enforcement": "mandatory: when the service is paid by the patient, written information per EK-1/E 'Bilgilendirme Formu' must be given against signature",
            "message_tr": (
                "Sunulan sağlık hizmetinin kişilerce karşılanması halinde SUT’taki bedeller üzerinden Kurumca "
                "yapılacak inceleme sonrasında ödenecek tutara ilişkin EK-1/E “Bilgilendirme Formu” kullanılarak "
                "yazılı bilginin imza karşılığı verilmesi zorunludur."
            ),
            "form_basis": "EK-1/E",
        },
        "gate_b_sources": ["C000731"],
        "encode_batch": "R6",
    },

    # ────────────────────────────────────────────────────────────────────────
    # §2.5.1 — Yurt dışına geçici/sürekli görevle gönderilenler
    # ────────────────────────────────────────────────────────────────────────

    # C001399 — COVERAGE: yurt içi sözleşmeliye ödenen en yüksek tutarı aşmamak kaydıyla
    {
        "rule_id": "2.X.yurt_disi_gecici_gorev_ici_en_yuksek_tutar_siniri",
        "sut_section": "2.5.1",
        "condition": {
            "patient_temporarily_or_permanently_posted_abroad": True,
        },
        "action": {
            "enforcement": "coverage: services for posted personnel are covered up to the highest amount paid to a domestic contracted provider on the treatment date",
            "message_tr": (
                "Yurt dışına geçici veya sürekli görevle gönderilenlere sağlanan sağlık hizmetleri bedelleri, "
                "yurt içinde sözleşmeli sağlık hizmeti sunucularına tedavinin yapıldığı tarihte ödenen en yüksek "
                "tutarı aşmamak kaydıyla Kurumca karşılanır."
            ),
        },
        "gate_b_sources": ["C001399"],
        "encode_batch": "R6",
    },
    # C001400 — COVERAGE: giderler önce işverence; konsolosluk tasdikli belgelerle; CB döviz satış kuru; aşan işverence
    {
        "rule_id": "2.X.gecici_gorev_isveren_once_konsolosluk_cb_kuru",
        "sut_section": "2.5.1",
        "condition": {
            "patient_temporarily_or_permanently_posted_abroad": True,
            "consular_certified_documents_present": False,
        },
        "action": {
            "enforcement": "coverage: expenses are first met by the employer and claimed from the Institution with consular-certified documents; payments in TRY at CB foreign-exchange selling rate on payment date; excess borne by employer",
            "message_tr": (
                "Sağlık hizmeti giderleri öncelikle işverenler tarafından ödenir ve yurt dışında görevli olunduğuna "
                "dair belge ile birlikte mahalli konsolosluktan (KKTC’deki TSK personeli için konsolosluk/yetki "
                "devredeceği kurum) tasdikli rapor, fatura ve sair belgelere dayanılarak Kurumdan talep edilir. "
                "Ödemeler ödeme tarihindeki TCMB döviz satış kuru esas alınarak TL üzerinden yapılır; Kurumun "
                "ödediğini aşan kısım işverence karşılanır."
            ),
        },
        "gate_b_sources": ["C001400"],
        "encode_batch": "R6",
    },
    # C001401 — NO_PAY: Kurumca ilgili ülkede sigorta yaptırılmışsa giderler ödenmez
    {
        "rule_id": "2.X.gecici_gorev_sigorta_yaptirildi_nopay",
        "sut_section": "2.5.1",
        "condition": {
            "patient_posted_abroad": True,
            "kurum_arranged_health_insurance_in_host_country": True,
        },
        "action": {
            "enforcement": "no-pay: when the Institution arranges health insurance in the host country for posted personnel, service expenses are not paid",
            "message_tr": (
                "Yurt dışına geçici veya sürekli görevle gönderilen kişilerin sağlık hizmetlerinin, Kurumca "
                "ilgili ülkede sağlık sigortası yaptırmak suretiyle sağlanması halinde sağlık hizmeti giderleri "
                "ödenmez."
            ),
        },
        "gate_b_sources": ["C001401"],
        "encode_batch": "R6",
    },
    # C001402 — COVERAGE: bulunduğu ülkede sözleşmeli sunucu varsa sözleşme hükümlerine göre
    {
        "rule_id": "2.X.gecici_gorev_sozlesmeli_sunucu_var_sozlesme_hukmu",
        "sut_section": "2.5.1",
        "condition": {
            "patient_posted_abroad": True,
            "contracted_provider_present_in_host_country": True,
        },
        "action": {
            "enforcement": "coverage: if a contracted provider exists in the host country, treatment expenses are paid per the contract terms",
            "message_tr": (
                "Yurt dışına geçici veya sürekli görevle gönderilenlerin bulunduğu ülkede sözleşmeli sağlık "
                "hizmeti sunucusu bulunması halinde tedavi giderleri sözleşme hükümlerine göre ödenir."
            ),
        },
        "gate_b_sources": ["C001402"],
        "encode_batch": "R6",
    },
    # C001403 — NO_PAY: yol/gündelik/refakatçi/cenaze giderleri ödenmez (geçici-sürekli görev)
    {
        "rule_id": "2.X.gecici_gorev_yol_gundelik_refakatci_cenaze_nopay",
        "sut_section": "2.5.1",
        "condition": {
            "patient_posted_abroad": True,
            "expense_category_any": ["travel", "per_diem", "companion", "funeral"],
        },
        "action": {
            "enforcement": "no-pay: travel/per-diem/companion/funeral expenses are not paid for posted personnel and their dependants",
            "message_tr": (
                "Yurt dışına geçici veya sürekli görevle gönderilen kişiler ile bakmakla yükümlü olduğu kişiler "
                "için yol gideri, gündelik, refakatçi ve cenaze giderleri ödenmez."
            ),
        },
        "gate_b_sources": ["C001403"],
        "encode_batch": "R6",
    },
    # C001405 — NO_PAY: KKTC'de sözleşmeli sunucu varken acil hariç sözleşmesizden alınan ödenmez
    {
        "rule_id": "2.X.kktc_sozlesmeli_varken_acil_haric_sozlesmesiz_nopay",
        "sut_section": "2.5.1",
        "condition": {
            "host_country": "KKTC",
            "patient_posted_abroad": True,
            "contracted_provider_present": True,
            "provider_contracted": False,
            "is_emergency": False,
        },
        "action": {
            "enforcement": "no-pay: in KKTC where a contracted provider exists, services taken from an uncontracted provider (except emergencies) are not covered for posted personnel and dependants",
            "message_tr": (
                "KKTC’de Kurumla sözleşmeli sağlık hizmeti sunucusu bulunması halinde, geçici ya da sürekli "
                "görevle bu ülkede bulunanlar ile bakmakla yükümlü olduğu kişilerin acil haller hariç "
                "sözleşmesiz sunuculardan alınan sağlık hizmeti bedelleri Kurumca karşılanmaz."
            ),
        },
        "gate_b_sources": ["C001405"],
        "encode_batch": "R6",
    },
    # C001407 — COVERAGE: 5510/60-12 kapsamı görevle gönderilenlerde acil olup olmadığına bakılmaksızın en yüksek tutar
    {
        "rule_id": "2.X.5510_60_12_gorev_gonderilen_acil_bakis_maksizin_en_yuksek",
        "sut_section": "2.5.1",
        "condition": {
            "insurant_scope": "5510_md60_fikra12",
            "posted_abroad_per_special_legislation": True,
        },
        "action": {
            "enforcement": "coverage: for 5510 art.60(12) personnel posted abroad per special legislation, services are covered up to the highest domestic contracted amount regardless of emergency status",
            "message_tr": (
                "5510 sayılı Kanunun 60 ıncı maddesinin on ikinci fıkrası kapsamında genel sağlık sigortalısı "
                "sayılanlardan özel mevzuatlarında belirtilen usule uygun olarak sürekli veya geçici görevle "
                "yurtdışına gönderilenlere acil hal olup olmadığına bakılmaksızın, sağlanan sağlık hizmeti "
                "bedelleri yurt içinde sözleşmeli sunuculara ödenen en yüksek tutarı aşmamak kaydıyla Kurumca "
                "karşılanır."
            ),
        },
        "gate_b_sources": ["C001407"],
        "encode_batch": "R6",
    },

    # ── §2.5.2 — Yurt dışında bulunan genel sağlık sigortalıları ────────────

    # C001409 — NO_PAY: sosyal güvenlik sözleşmesi yoksa hizmet/yol/gündelik/refakatçi ödenmez
    {
        "rule_id": "2.X.sozlesme_yok_yurt_disinda_hizmet_yol_gundelik_nopay",
        "sut_section": "2.5.2",
        "condition": {
            "insurant_abroad": True,
            "social_security_agreement_with_turkey": False,
        },
        "action": {
            "enforcement": "no-pay: absent a social-security agreement covering health aid with Turkey, service/travel/per-diem/companion expenses are not paid",
            "message_tr": (
                "Genel sağlık sigortalısı veya bakmakla yükümlü olduğu kişilerin yurt dışında bulundukları sırada "
                "sağlanan sağlık hizmetleri bedellerinin ödenmesinde, bulundukları ülke ile Türkiye arasında "
                "sağlık yardımlarını kapsayan sosyal güvenlik sözleşmesi olması halinde sözleşme hükümleri "
                "uygulanır; sözleşme olmaması halinde sağlık hizmetleri giderleri ile yol, gündelik ve refakatçi "
                "vb. giderler ödenmez."
            ),
        },
        "gate_b_sources": ["C001409"],
        "encode_batch": "R6",
    },
    # C001410 — NO_PAY: KKTC'de sözleşmeli varken acil hariç sözleşmesiz ödenmez; yol/gündelik ayrıca yok
    {
        "rule_id": "2.X.kktc_turk_vatandasi_en_yuksek_sinir_sozlesmesiz_nopay",
        "sut_section": "2.5.2",
        "condition": {
            "host_country": "KKTC",
            "patient_is_turkish_citizen_ghs": True,
            "provider_contracted": False,
            "is_emergency": False,
        },
        "action": {
            "enforcement": "no-pay: Turkish-citizen GHS abroad in KKTC are covered up to the highest domestic amount; with a contracted provider present, non-emergency uncontracted services are not paid and no travel/per-diem",
            "message_tr": (
                "Türk vatandaşı olan genel sağlık sigortalılarının ve bakmakla yükümlü olduğu kişilerin KKTC’de "
                "sağlanan sağlık hizmeti bedelleri yurt içinde ödenen en yüksek tutarı geçmemek üzere Kurumca "
                "karşılanır. Bu ülkede sözleşmeli sunucu bulunması halinde acil haller hariç sözleşmesiz "
                "sunuculardan alınan bedeller karşılanmaz ve yol ile gündelik gideri ödenmez."
            ),
        },
        "gate_b_sources": ["C001410"],
        "encode_batch": "R6",
    },

    # ────────────────────────────────────────────────────────────────────────
    # §2.5.3.A / A-2 — Yurt dışı tedavi (yurt içinde sağlanamayanlar)
    # ────────────────────────────────────────────────────────────────────────

    # C001413 — MANDATORY: yurt içinde sağlanamayan hizmetin yurt dışında sağlanması için düzenlemelere uyulacak
    {
        "rule_id": "2.X.yurt_disi_tedavi_duzenlemelere_uyum",
        "sut_section": "2.5.3.A",
        "condition": {
            "service_unavailable_in_country": True,
            "overseas_treatment_sought": True,
        },
        "action": {
            "enforcement": "mandatory: services unavailable domestically may be provided overseas only in compliance with the §2.5.3 provisions",
            "message_tr": (
                "Yurt içi sağlık hizmeti sunucularında sağlanamayan sağlık hizmetlerinin yurt dışı sağlık "
                "hizmeti sunucularında sağlanabilmesi için aşağıdaki düzenlemelere uyulacaktır."
            ),
        },
        "gate_b_sources": ["C001413"],
        "encode_batch": "R6",
    },
    # C001430 — MANDATORY: Bakanlık onayından 3 ay içinde çıkılmazsa rapor yenilenmeli
    {
        "rule_id": "2.X.yurt_disi_rapor_onay_3ay_icinde_cikilmazsa_yenileme",
        "sut_section": "2.5.3.A-2",
        "condition": {
            "overseas_treatment_report": True,
            "months_since_moh_approval_without_departure": {"min": 3},
        },
        "action": {
            "enforcement": "mandatory: overseas-treatment reports not acted on (departure) within 3 months of MoH approval must be renewed",
            "message_tr": (
                "Yurt dışı tedaviye ilişkin raporların Sağlık Bakanlığınca onaylanmasından itibaren üç ay içinde "
                "yurt dışına çıkılmaması nedeniyle işlem yapılmayan raporların yenilenmesi gerekir."
            ),
        },
        "gate_b_sources": ["C001430"],
        "encode_batch": "R6",
    },
    # C001431 — NO_PAY: tedavi süresi/uzatma aşılırsa aşan süreye ait gider, gündelik ve refakatçi ödenmez
    {
        "rule_id": "2.X.yurt_disi_sure_asimi_gider_gundelik_refakatci_nopay",
        "sut_section": "2.5.3.A-2",
        "condition": {
            "overseas_treatment": True,
            "duration_exceeds_reported_or_extended_period": True,
        },
        "action": {
            "enforcement": "no-pay: treatment may not exceed the reported period; extensions (≤6-month tranches, via Ankara Şehir/authorised hospital opinion) beyond the period mean the excess treatment/per-diem/companion costs are not paid",
            "message_tr": (
                "Yurt dışı tedavi süresi raporda belirtilen süreyi geçemez. Tıbbi nedenlerle uzama halinde gerekçe "
                "misyon şefliklerince gönderilir; Ankara Şehir Hastanesi/yetkili hastane görüşü alınarak altı ayı "
                "geçmeyen dönemler halinde Kurum onayıyla süre uzatılabilir. Belirlenen/uzatılan sürenin aşılması "
                "halinde aşılan süreye ait tedavi giderleri ile gündelik ve refakatçi giderleri ödenmez."
            ),
        },
        "gate_b_sources": ["C001431"],
        "encode_batch": "R6",
    },
    # C001432 — MANDATORY: organ nakli bekleme süresi 5 yılı geçerse 2.5.3.A-1 doğrultusunda rapor yenilenmeli
    {
        "rule_id": "2.X.organ_nakli_5yil_bekleme_rapor_yenileme",
        "sut_section": "2.5.3.A-2",
        "condition": {
            "overseas_organ_transplant": True,
            "waiting_years_since_listing": {"min": 5},
        },
        "action": {
            "enforcement": "mandatory: initial workup is domestic until organ availability; after organ listing wait exceeds 5 years the overseas-transfer report must be renewed per 2.5.3.A-1",
            "message_tr": (
                "Organ nakli bekleme süresi uzundur; uygun organ teminine kadar geçen süredeki tetkik ve "
                "tedaviler yurt içinde yapılır, organ temini üzerine hasta yeni rapora ihtiyaç duyulmadan nakil "
                "için yurt dışına gönderilir. Bekleme süresinin beş yılı geçmesi halinde yurt dışına gönderilmeye "
                "ilişkin sağlık kurulu raporu SUT’un 2.5.3.A-1 maddesi doğrultusunda yenilenmeli ve onaylar "
                "yapılmış olmalıdır."
            ),
        },
        "gate_b_sources": ["C001432"],
        "encode_batch": "R6",
    },
    # C001433 — NO_PAY: organ nakli bekleme süresi yurt dışında 2 yılı geçemez; aşılırsa gider/gündelik/refakatçi ödenmez
    {
        "rule_id": "2.X.organ_nakli_yurt_disi_bekleme_2yil_sinir_asim_nopay",
        "sut_section": "2.5.3.A-2",
        "condition": {
            "overseas_organ_transplant": True,
            "total_overseas_waiting_years": {"min": 2},
        },
        "action": {
            "enforcement": "no-pay: GSS Directorate may approve overseas waiting (with MoH opinion) in ≤6-month tranches; total overseas waiting may not exceed 2 years; excess treatment/per-diem/companion costs are not paid",
            "message_tr": (
                "Organ nakli için beklemenin yurt dışında geçirilmesi zorunlu olduğunun belgelendirilmesi ve "
                "Sağlık Bakanlığı görüşü alınmasıyla GSS Genel Müdürlüğü yurt dışında bekleme süresine karar "
                "verebilir; bu süre 6 ayı geçmeyen dönemler halinde uzatılabilir, yurt dışında toplam bekleme iki "
                "yılı geçemez. Belirlenen/uzatılan sürenin aşılması halinde aşılan süreye ait tedavi, gündelik ve "
                "refakatçi giderleri ödenmez."
            ),
        },
        "gate_b_sources": ["C001433"],
        "encode_batch": "R6",
    },
    # C001435 — MANDATORY: kontrol tedavisi yurt içinde esastır; yurt dışı için şartlar aranır
    {
        "rule_id": "2.X.kontrol_tedavisi_yurt_ici_esas_yurt_disi_sartlari",
        "sut_section": "2.5.3.A-2",
        "condition": {
            "overseas_treatment_patient": True,
            "follow_up_treatment": True,
        },
        "action": {
            "enforcement": "mandatory: follow-up treatment of overseas-treated patients is primarily domestic; overseas follow-up requires the listed conditions",
            "message_tr": (
                "Yurt dışına tedavi amacıyla gönderilen hastaların kontrol tedavilerinin yurt içindeki sağlık "
                "hizmeti sunucularında yapılması esastır. Ancak kontrol tedavisi amacıyla yurt dışına "
                "gönderilebilmesi için ilgili şartlar aranır."
            ),
        },
        "gate_b_sources": ["C001435"],
        "encode_batch": "R6",
    },
    # C001439 — MANDATORY: (kontrol tedavisi yurt dışı şartlarının tamamı) gerekir
    {
        "rule_id": "2.X.kontrol_tedavisi_yurt_disi_sartlarin_tamami_gerekir",
        "sut_section": "2.5.3.A-2",
        "condition": {
            "overseas_follow_up_requested": True,
            "all_follow_up_conditions_met": False,
        },
        "action": {
            "enforcement": "mandatory: overseas follow-up requires all the listed conditions to be met",
            "message_tr": (
                "Kontrol tedavisi amacıyla hastanın yurt dışına gönderilebilmesi için öngörülen şartların tamamının "
                "sağlanması gerekir."
            ),
        },
        "gate_b_sources": ["C001439"],
        "encode_batch": "R6",
    },

    # ── §2.5.3.A-3 — Yurt dışı tedavi bedelleri / avans / istisnalar ────────

    # C001441 — COVERAGE: sevke konu sözleşmeli sunucu varsa giderlerin tümü; kişi gitmezse sözleşmeli tutarı geçmez
    {
        "rule_id": "2.X.yurt_disi_sevk_sozlesmeli_tum_gider_tercih_fark_kisi",
        "sut_section": "2.5.3.A-3",
        "condition": {
            "overseas_treatment_patient": True,
        },
        "action": {
            "enforcement": "coverage: the patient is referred to an overseas contracted provider and all expenses covered; if the patient chooses a non-contracted provider, payment is capped at the contracted amount and any difference is borne by the patient",
            "message_tr": (
                "Yurt dışında tedavi edilecek kişi, var ise sözleşmeli sağlık hizmeti sunucusuna sevk edilir ve "
                "giderlerin tümü karşılanır. Sözleşmeli sunucu yokluğunda da sevk edilen sunucudaki tedavi "
                "giderlerinin tamamı Kurumca ödenir. Kişinin tercihiyle sözleşmeli sunucuya gitmemesi halinde, "
                "sözleşmeli yere ödenebilecek tutarı geçmemek üzere ödeme yapılır, fark kişi tarafından "
                "karşılanır."
            ),
        },
        "gate_b_sources": ["C001441"],
        "encode_batch": "R6",
    },
    # C001443 — COVERAGE: yurt dışı tedavi bedeli sunucu banka hesabına havale veya kişiye belge karşılığı
    {
        "rule_id": "2.X.yurt_disi_tedavi_bedeli_havale_veya_kisiye_belge",
        "sut_section": "2.5.3.A-3",
        "condition": {
            "overseas_treatment_invoice": True,
        },
        "action": {
            "enforcement": "coverage: overseas treatment fees are met by wire to the provider's bank account or reimbursement to the patient against documents",
            "message_tr": (
                "Yurt dışında yapılan tedavi bedelleri, Kurum tarafından yurt dışı sağlık hizmeti sunucusu banka "
                "hesabına havale edilmesi veya kişilerce ödenen tutarın belge karşılığı kendilerine ödenmesi "
                "suretiyle karşılanır."
            ),
        },
        "gate_b_sources": ["C001443"],
        "encode_batch": "R6",
    },
    # C001444 — PERMISSION: yurt dışı tedavi için oluşacak giderlere mahsuben kişiye/sunucuya avans (misyon şefliği de)
    {
        "rule_id": "2.X.yurt_disi_tedavi_avans_mahsuben_izin",
        "sut_section": "2.5.3.A-3",
        "condition": {
            "overseas_treatment_imminent": True,
            "advance_requested": True,
        },
        "action": {
            "enforcement": "permission: an advance may be paid to the patient/provider against upcoming overseas-treatment costs, on request; advance may be routed via the mission chancellery",
            "message_tr": (
                "Kurumca, yurt dışında yapılacak tedaviler için oluşacak giderlere mahsuben talep edilmesi halinde, "
                "kişilere veya sağlık hizmeti sunucusuna avans ödenebilir. Avans ödemesi misyon şefliği "
                "aracılığıyla da yapılabilir."
            ),
        },
        "gate_b_sources": ["C001444"],
        "encode_batch": "R6",
    },
    # C001446 — NO_PAY: sevke konu hastalık dışındaki tedavi giderleri (acil/komplikasyon/ilişkili hariç) ödenmez
    {
        "rule_id": "2.X.sevk_disi_tedavi_giderleri_nopay",
        "sut_section": "2.5.3.A-3",
        "condition": {
            "overseas_treatment_patient": True,
            "treatment_unrelated_to_referred_condition": True,
            "is_emergency_or_complication_or_related": False,
        },
        "action": {
            "enforcement": "no-pay: treatment unrelated to the referred condition is not paid overseas (except emergencies, complications of the referred condition, and related treatment); ambiguity resolved by the treating hospital's opinion",
            "message_tr": (
                "Acil müdahaleyi gerektiren durumlar, sevke konu hastalığın komplikasyonuna bağlı yapılan "
                "tedaviler ile ilişkili tedaviler hariç olmak üzere yurt dışına sevke konu hastalık dışındaki "
                "tedavi giderleri Kurumca ödenmez. İlişkili olup olmadığının tespit edilemediği durumlarda yurt "
                "dışı tedavi raporunu teyit eden hastanenin görüşü alınarak işlem yapılır."
            ),
        },
        "gate_b_sources": ["C001446"],
        "encode_batch": "R6",
    },
    # C001449 — NO_PAY: farklı tedavi için 2.5.3.A-1 rapor/onay yoksa yeni tedavi bedeli + yol/gündelik ödenmez
    {
        "rule_id": "2.X.yeni_farkli_tedavi_rapor_onay_yoksa_nopay",
        "sut_section": "2.5.3.A-3",
        "condition": {
            "overseas_treatment_patient": True,
            "additional_different_treatment_proposed": True,
            "report_and_approvals_per_2_5_3_A_1_for_new_treatment": False,
        },
        "action": {
            "enforcement": "no-pay: a different treatment proposed overseas is covered only if 2.5.3.A-1 reports/approvals are also obtained for it; otherwise the new treatment fee plus its travel/per-diem are not paid",
            "message_tr": (
                "Yurt dışına gönderilen hastaya sunucu tarafından sevke konu tedavi dışında farklı bir tedavi "
                "öngörülürse, SUT’un 2.5.3.A-1 maddesinde belirtilen rapor ve onayların yeni tedavi için de alınmış "
                "olması halinde tedavi giderleri karşılanır; aksi halde yeni tedavi bedeli ile bu tedaviye ilişkin "
                "yol ve gündelik gideri Kurumca karşılanmaz."
            ),
        },
        "gate_b_sources": ["C001449"],
        "encode_batch": "R6",
    },

    # ────────────────────────────────────────────────────────────────────────
    # §2.5.3.B / B-2 — Yurt dışı tetkik/tahlil (numune gönderimi)
    # ────────────────────────────────────────────────────────────────────────

    # C001451 — MANDATORY: yurt içi yapılamayan tetkik/tahlilin numune gönderimiyle yaptırılması düzenlemeleri
    {
        "rule_id": "2.X.yurt_disi_tetkik_numune_gonderimi_duzenlemeler",
        "sut_section": "2.5.3.B",
        "condition": {
            "test_unavailable_in_country": True,
            "overseas_lab_via_sample_dispatch": True,
        },
        "action": {
            "enforcement": "mandatory: domestically unavailable tests/analyses may be performed overseas by sending samples, subject to the listed provisions (patient dispatch follows 2.5.3.A)",
            "message_tr": (
                "Yurt içinde yapılamayan tetkik ve/veya tahlillerin, numunenin gönderilmesi suretiyle yurt dışı "
                "sağlık hizmeti sunucularında yaptırılabilmesi için aşağıdaki düzenlemelere uyulacaktır. "
                "Tetkik/tahlillerin kişilerin yurt dışına gönderilmesi suretiyle yaptırılması SUT’un 2.5.3.A "
                "maddesi doğrultusunda yürütülecektir."
            ),
        },
        "gate_b_sources": ["C001451"],
        "encode_batch": "R6",
    },
    # C001457 — COVERAGE: yurt dışı tetkik/tahlil bedeli fatura tutarı üzerinden havale veya kişiye belge karşılığı
    {
        "rule_id": "2.X.yurt_disi_tetkik_bedeli_havale_veya_kisiye_belge",
        "sut_section": "2.5.3.B-2",
        "condition": {
            "overseas_lab_invoice": True,
        },
        "action": {
            "enforcement": "coverage: overseas lab fees are covered at the invoiced amount via wire to the provider or reimbursement to the patient against documents",
            "message_tr": (
                "Numunenin/hastanın gönderilmesiyle yurt dışında yapılan tetkik ve/veya tahlil bedeli, sunucu "
                "faturasında/fatura yerine geçen belgede belirtilen tutar üzerinden Kurum tarafından yurt dışı "
                "sunucu banka hesabına havale veya kişilerce ödenen tutarın belge karşılığı kendilerine ödenmesi "
                "suretiyle karşılanır."
            ),
        },
        "gate_b_sources": ["C001457"],
        "encode_batch": "R6",
    },
    # C001458 — PERMISSION: yurt dışı tetkik/tahlil için oluşacak giderlere mahsuben avans izni
    {
        "rule_id": "2.X.yurt_disi_tetkik_avans_mahsuben_izin",
        "sut_section": "2.5.3.B-2",
        "condition": {
            "overseas_lab_imminent": True,
            "advance_requested": True,
        },
        "action": {
            "enforcement": "permission: an advance may be paid against upcoming overseas lab costs to the patient/provider on request; advance may be routed via the mission chancellery",
            "message_tr": (
                "Kurumca, yurt dışında yapılacak tetkikler/tahliller için oluşacak giderlere mahsuben talep "
                "edilmesi halinde kişilere veya sağlık hizmeti sunucusuna avans ödenebilir. Avans ödemesi misyon "
                "şefliği aracılığıyla da yapılabilir."
            ),
        },
        "gate_b_sources": ["C001458"],
        "encode_batch": "R6",
    },

    # ── §2.5.3.C-1 / C-2 — Yurt dışı yol / gündelik / refakatçi giderleri ───

    # C001463 — COVERAGE: hasta + refakatçi (bir kişi) yol gideri fatura/bilet üzerinden; tarifeli dışı hava taşıtı belgeli
    {
        "rule_id": "2.X.yurt_disi_hasta_refakatci_yol_gideri_fatura_bilet",
        "sut_section": "2.5.3.C-1",
        "condition": {
            "overseas_treatment_patient": True,
        },
        "action": {
            "enforcement": "coverage: the patient and one companion's (if report-required; under-18 unconditional) travel costs are paid at the transport invoice/ticket; non-scheduled aircraft (ambulance/private) covered on documented medical need for outbound and return",
            "message_tr": (
                "Yurt dışına gönderilen hasta ile raporda öngörülmesi halinde bir kişiyle sınırlı refakatçisinin "
                "(18 yaş altı için şart aranmaz) yol gideri ulaşım aracına ilişkin fatura/bilet tutarı üzerinden "
                "Kurumca ödenir. Rapor/açıkça belge ile tarifeli hava taşıtı dışındaki taşıtla (ambulans uçak, "
                "özel uçak vb.) naklinin gerektiği belirtilirse gidiş ve belgelendirilen dönüş için taşıt bedelleri "
                "fatura/belge tutarı üzerinden ödenir."
            ),
        },
        "gate_b_sources": ["C001463"],
        "encode_batch": "R6",
    },
    # C001464 — COVERAGE: yurt dışında tedavi/tetkik sırasında ölüm halinde cenaze nakli + refakatçi dönüş yolu
    {
        "rule_id": "2.X.yurt_disinda_vefat_cenaze_nakli_refakatci_donus_yolu",
        "sut_section": "2.5.3.C-1",
        "condition": {
            "patient_deceased_during_overseas_treatment": True,
        },
        "action": {
            "enforcement": "coverage: on the patient's death during overseas treatment/t testing, the body's transport costs and any companion's return travel are covered",
            "message_tr": (
                "Tedavi/tetkik için yurt dışına gönderilen kişinin tedavi/tetkik sırasında ölümü hâlinde, "
                "cenazesinin nakil gideri ile varsa refakatçisinin yurda dönüş yol giderleri de Kurumca "
                "karşılanır."
            ),
        },
        "gate_b_sources": ["C001464"],
        "encode_batch": "R6",
    },
    # C001467 — COVERAGE: ayaktan her gün için hasta+refakatçi gündelik; yatakta kalınmayan günler için yemek/yatak; cetvel VI
    {
        "rule_id": "2.X.yurt_disi_gundelik_ve_yemek_yatak_cetvel_vi",
        "sut_section": "2.5.3.C-2",
        "condition": {
            "overseas_treatment_patient": True,
        },
        "action": {
            "enforcement": "coverage: outpatient-treatment days earn per-diem for the patient and one companion; for days not stayed during inpatient care the companion earns meal/bed costs, per the 6245 Harcırah table column (VI: salary/cadre grade 5-15) for the country",
            "message_tr": (
                "Ayakta tedavinin sağlandığı her gün için hasta ve refakatçinin her birine “gündelik”, yatarak "
                "tedavide ise yatarak tedavi süresi ile sınırlı olmak üzere sunucuda kalınmayan her gün için "
                "refakatçisine yemek ve yatak gideri ödenir. Ödemelerde 6245 sayılı Harcırah Kanunu gereği "
                "Bakanlar Kurulunca belirlenen ilgili yıl “Yurtdışı Gündeliklerinin Hesaplanmasında Esas Alınacak "
                "Cetvel” (Aylık/kadro derecesi 5-15 olanlar) sütununda gönderilen ülke için belirlenen bedel esas "
                "alınır."
            ),
        },
        "gate_b_sources": ["C001467"],
        "encode_batch": "R6",
    },
]
