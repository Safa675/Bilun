"""§2.4.1 / §2.4.2 / §2.4.3 treatment-pricing & coverage rules — 'rest' batch.

Gate-B encoded rules for the remaining in-force deontic clauses of SUT §2.4
that are NOT in §2.4.4 (which was already covered by wave-2a/2b/2c). This batch
covers the 42 clauses of §2.4.1 (dental/orthodontic), §2.4.2 (organ / tissue /
bone-marrow / stem-cell transplant) and §2.4.3 (vaccines).

Modalities covered here: COVERAGE, MUST_BILL, MUST_NOT_BILL, MANDATORY,
NO_PAY, REGULATORY_ACTION.

Merge target: data/gazette/prose_rules/treatment_pricing_2_4.json
"""

from __future__ import annotations

from typing import Any

REST_BATCH_RULES: list[dict[str, Any]] = [
    # ── §2.4.1 — Diş tedavileri ─────────────────────────────────────────────
    # (1) NO_PAY — kıymetli maden / bileşiminde kıymetli maden bulunan maddeler ödenmez
    {
        "rule_id": "2.4.1.(1).precious_metal_dental_no_pay",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "dental_restorative",
            "material_category_in": [
                "gold", "platinum", "palladium+platinum",
                "iridium+platinum", "iropal",
                "argenco_23", "bego_gold_ewl", "polliag_m",
            ],
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "diş tedavileri sırasında; altın, platin, paladyum+platin, "
                "irrudyum+platin, iropal gibi kıymetli madenler ile argenco 23, "
                "bego gold EWL ve polliag-M gibi bileşiminde kıymetli maden "
                "bulunan maddelerin bedelleri ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000734"],
        "encode_batch": "REST",
    },
    # (2) NO_PAY — kemik içi implantlar ödenmez (başlangıç kuralı)
    {
        "rule_id": "2.4.1.(2).dental_implant_no_pay",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "dental_implant",
            "board_report_with_radiographs_present": False,
        },
        "action": {
            "billable": False,
            "denial_tr": "kemik içi implantların bedelleri ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C000742"],
        "encode_batch": "REST",
    },
    # (2) MUST_BILL — sağlık kurulu + her çene en fazla 4 implant, 750/2500 TL sınırları
    {
        "rule_id": "2.4.1.(2).dental_implant_board_report_max4_per_jaw",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "dental_implant",
            "board_report_with_radiographs_present": True,
            "implants_per_jaw": {"min": 5},
            "patient_category": "standard_beneficiary",
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "her bir çene için en fazla 4 adet EK-2/Ç kemik içi implant "
                "uygulaması işlem bedeli ile her implant için 750 TL üzerinden "
                "faturalandırılabilir; vazife/harp malullerinde her implant için "
                "en fazla 2500 TL"
            ),
            "annex_basis": "EK-2/Ç",
            "severity": "error",
        },
        "gate_b_sources": ["C000747"],
        "encode_batch": "REST",
    },
    # (3) NO_PAY — protez yenileme süresi 4 yıl; bu süreden önce yenilenen ödenmez
    {
        "rule_id": "2.4.1.(3).prosthesis_renewal_4yr_no_pay",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category_any": ["removable_prosthesis", "fixed_prosthesis"],
            "years_since_prior_prosthesis": {"max": 3.99},
            "exception_in": [
                "traffic_accident", "work_accident_oral_jaw_trauma",
                "neoplastic_jaw_loss", "cancer_weight_loss_with_board_report",
            ],
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "hareketli ve sabit protezlerin yenilenme süresi 4 yıldır; bu "
                "süreden önce yenilenen protez bedelleri Kurumca ödenmez; trafik "
                "kazası/iş kazası ağız-çene travması, neoplazi veya kansere bağlı "
                "kil kaybında 3 diş hekimi sağlık kurulu raporuyla süre aranmaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000748"],
        "encode_batch": "REST",
    },
    # a) NO_PAY — 18 yaşını doldurmuş kişilerin ortodontik tedavisi ödenmez
    {
        "rule_id": "2.4.1.(a).adult_orthodontics_18plus_no_pay",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "orthodontics",
            "patient_age_years": {"min": 18},
            "treatment_started_before_age_18": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "18 yaşını doldurmuş kişilerin ortodontik diş tedavilerine ilişkin "
                "giderler Kurumca ödenmez; 18 yaşından önce başlayıp devam edenler "
                "karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000752"],
        "encode_batch": "REST",
    },
    # b) COVERAGE — süt/karma dişlenme erken ortodontik tedavi (P407321/P407322)
    {
        "rule_id": "2.4.1.(b).early_orthodontics_mixed_dentition_coverage",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_code_any": ["P407321", "P407322"],
            "patient_age_years": {"min": 6, "max": 14},
            "prescriber_specialty_any": ["orthodontics_specialist", "orthodontics_phd"],
            "treatment_documented_complete": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "süt ve karma dişlenme döneminde dental/iskeletsel maloklüzyon için "
                "erken ortodontik tedavi (P407321/P407322) 6-14 yaş, ortodonti "
                "uzmanı/doktoralı hekim tarafından yapıldığı ve belgelendiği halde "
                "Karşılanır; başlangıç ve bitiş aşamaları arasında en az 3 ay olmalı"
            ),
            "annex_basis": "EK-2/Ç",
            "severity": "error",
        },
        "gate_b_sources": ["C000753"],
        "encode_batch": "REST",
    },
    # c) COVERAGE — Sınıf I/II/III ve ortognatik cerrahi sabit ortodontik tedavi
    {
        "rule_id": "2.4.1.(c).fixed_orthodontics_class_1_2_3_coverage",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "fixed_orthodontics",
            "malocclusion_class_any": ["class_I", "class_II", "class_III", "orthognathic_surgery"],
            "prescriber_specialty_any": ["orthodontics_specialist", "orthodontics_phd"],
            "min_months_start_to_treatment": 6,
            "min_months_treatment_to_retention": 4,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "Sınıf I, II, III ve ortognatik cerrahide sabit ortodontik tedaviler "
                "EK-2/Ç işlem kodları üzerinden, tedavi tamamlandığı belgelenmek ve "
                "ortodonti uzmanı/doktoralı hekim tarafından yapılması halinde Kurumca "
                "karşılanır; başlangıç-tedavi arası en az 6 ay, tedavi-pekiştirme arası "
                "en az 4 ay olmalı"
            ),
            "annex_basis": "EK-2/Ç",
        },
        "gate_b_sources": ["C000754"],
        "encode_batch": "REST",
    },
    # ç) COVERAGE — yarık dudak-damak / yarık damak ortodontik tedavileri
    {
        "rule_id": "2.4.1.(c2).cleft_lip_palate_orthodontics_coverage",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_code_any": ["P407342", "P407343", "P407344"],
            "diagnosis_category": "cleft_lip_palate",
            "facility_in": ["university_dental_faculty"],
            "prescriber_specialty_any": ["orthodontics_specialist", "orthodontics_phd"],
            "documented_with_photographs": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "yarık dudak-damak / yarık damak ortodontik tedavileri EK-2/Ç "
                "(P407342/P407343/P407344) üzerinden, üniversite diş hekimliği "
                "fakültelerinde operasyon öncesi/sonrası fotoğrafla belgelendiğinde "
                "ortodonti uzmanı/doktoralı hekimi tarafından Kurumca karşılanır"
            ),
            "annex_basis": "EK-2/Ç",
            "severity": "error",
        },
        "gate_b_sources": ["C000755"],
        "encode_batch": "REST",
    },

    # ── §2.4.1.A — Diş tedavi bedelleri (ödenme esasları) ─────────────────────
    # (1) MUST_BILL — resmi sunucuda EK-2/Ç; üniversite %50 ilave (istisna kodlar hariç)
    {
        "rule_id": "2.4.1.A.(1).public_dental_ek2c_university_50pct_uplift",
        "sut_section": "2.4.1.A",
        "condition": {
            "procedure_category": "dental",
            "facility_in": ["contracted_public"],
            "procedure_code_not_in": [
                "401051", "401060", "401070", "401080", "401090",
                "401100", "401110", "401120", "401130", "401135", "401150", "401170",
            ],
            "facility_is_university_dental_faculty": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "resmi sunucularda diş tedavi bedellerinde EK-2/Ç uygulanır; protez "
                "ücretine döküm/işçilik dâhildir ayrıca ödenmez; üniversite diş "
                "hekimliği fakülteleri (istisna kodlar hariç) EK-2/Ç puanlara %50 "
                "oranında ilave edilerek faturalandırılır"
            ),
            "annex_basis": "EK-2/Ç",
        },
        "gate_b_sources": ["C000760"],
        "encode_batch": "REST",
    },
    # (2) MUST_BILL — %40+ engelli / özel gereksinimli çocukta GA/sedo 2 katı
    {
        "rule_id": "2.4.1.A.(2).disabled_or_special_needs_dental_ga_2x",
        "sut_section": "2.4.1.A",
        "condition": {
            "procedure_category": "dental",
            "facility_in": ["contracted_public"],
            "patient_category_any": ["disabled_40pct_or_more", "special_needs_child_mild_or_above"],
            "anesthesia_type_any": ["general_anesthesia", "sedoanalgesia"],
            "disability_report_attached": False,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "resmi sunucuda %40 ve üzeri engelli veya hafif düzey ve üstü özel "
                "gereksinimli çocuk hastalarda genel anestezi/sedo-analjezi altındaki "
                "diş tedavileri EK-2/Ç işlem puanı bedellerinin iki katı olarak "
                "faturalandırılır; 5378 sayılı Kanun Yönetmeliğine uygun rapor faturaya eklenir"
            ),
            "annex_basis": "EK-2/Ç",
        },
        "gate_b_sources": ["C000762"],
        "encode_batch": "REST",
    },

    # ── §2.4.1.B — Özel/Kurumsuz resmi sunucu diş hizmetleri (genel) ─────────
    # (1) REGULATORY_ACTION — kapsamdaki diğer kişilerin özel/kurumsuz resmi sunucu diş hizmeti
    {
        "rule_id": "2.4.1.B.(1).private_or_noncontract_public_dental_scoping",
        "sut_section": "2.4.1.B",
        "condition": {
            "procedure_category": "dental",
            "facility_category_any": ["private", "non_contracted_public"],
            "patient_category_not_in": ["5510_60_c1_c3", "5510_gss_general_health_insured"],
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "5510 sayılı Kanunun 60/c-1, 60/c-3 bentleri ile 12/13/14 fıkraları "
                "kapsamı dışındaki kişilerin özel sunucu ve Kurumla sözleşmesi olmayan "
                "resmi sunucu diş ünitelerindeki ağız ve diş sağlığı hizmetleri "
                "aşağıdaki şekilde yapılır"
            ),
        },
        "gate_b_sources": ["C000787"],
        "encode_batch": "REST",
    },

    # ── §2.4.1.B-1 — Ödeme koşulları (özel/kurumsuz resmi) ───────────────────
    # (1) NO_PAY — ortodontik ve %40+ engelli hariç diş tedavileri Kurumca ödenmez
    {
        "rule_id": "2.4.1.B-1.(1).private_dental_orthodontics_disabled_excepted_no_pay",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "procedure_category": "dental",
            "facility_category_any": ["private", "non_contracted_public"],
            "procedure_category_not_in": ["orthodontics"],
            "patient_category_not_in": ["disabled_40pct_or_more", "special_needs_child_mild_or_above"],
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "ortodontik diş tedavileri ile %40 ve üzerinde engelli kişiler hariç "
                "kapsamdaki kişilerin özel/Kurumla sözleşmesi olmayan resmi sunucu "
                "diş ünitelerinde yapılan ağız ve diş sağlığı tedavileri Kurumca ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000791"],
        "encode_batch": "REST",
    },
    # (2) MANDATORY — engelli/özel gereksinim durumunun belgelendirilmesi + 10 iş günü başlangıç
    {
        "rule_id": "2.4.1.B-1.(2).disabled_dental_documentation_10bizday_start",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "procedure_category": "dental",
            "facility_category_any": ["private", "non_contracted_public"],
            "patient_category_any": ["disabled_40pct_or_more", "special_needs_child_mild_or_above"],
            "disability_or_special_needs_documented": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "%40+ engelli veya özel gereksinimli çocuğun diş tedavisinin "
                "ödenmesi için engellilik/özel gereksinim durumu belgelendirilmeli; "
                "ADSM/ağız-diş sağlığı hastanesi/üniversite diş hekimliği fakültesince "
                "sağlık raporu düzenlenmiş olmalı; rapor tarihinden itibaren 10 iş günü "
                "içinde tedaviye başlanmalı"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000794"],
        "encode_batch": "REST",
    },
    # (3) MANDATORY — iletişim kurulamayan özürlü GA; anesteziyoloji+reanimasyon sorumluluğu
    {
        "rule_id": "2.4.1.B-1.(3).communication_impaired_ga_facility_requirement",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "procedure_category": "dental",
            "patient_category": "communication_impaired_cognitively_disabled",
            "anesthesia_type_any": ["general_anesthesia", "sedoanalgesia"],
            "facility_has_ga_unit_under_anesthesiology_reanimasyon": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "iletişim kurulamayan/algılama güçlüğü yaşanan özürlü kişilerin diş "
                "tedavisinde GA/sedo-analjezi bedelinin ödenebilmesi için tedavinin "
                "anesteziyoloji ve reanimasyon uzmanı sorumluluğunda GA uygulanabilen, "
                "asgari tıbbi malzeme/ilaç bulunan ünitelerde (ADSM/tıp merkezi/hastane "
                "ameliyathane/GA ünitesi) yapıldığı belgelendirilmelidir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000795"],
        "encode_batch": "REST",
    },
    # (5) MANDATORY — ortodontik tedavi için 3 diş hekimi sağlık kurulu raporu (6 ay)
    {
        "rule_id": "2.4.1.B-1.(5).orthodontics_3dentist_board_report_6mo",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "procedure_category": "orthodontics",
            "facility_category_any": ["private", "non_contracted_public"],
            "board_report_with_orthodontist_present": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "ortodontik tedavi gereksinimi olan hastalar için ADSM/ağız-diş sağlığı "
                "hastanesi/üniversite diş hekimliği fakültesince en az bir ortodonti "
                "uzmanının/doktoralı hekimin yer aldığı üç diş hekimi sağlık kurulu "
                "raporu düzenlenmeli; tedavinin estetik olmadığı ve maloklüzyon tipi "
                "belirtilmeli; rapor tarihinden itibaren 6 ay içinde tedaviye başlanmalı"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000799"],
        "encode_batch": "REST",
    },
    # (6) MANDATORY — tedavi sonrası kontrol formu onayı (sözleşmeli resmi sunucu)
    {
        "rule_id": "2.4.1.B-1.(6).dental_control_form_approval_required",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "procedure_category_any": ["dental", "orthodontics"],
            "facility_category_any": ["private", "non_contracted_public"],
            "control_form_approved_by_contracted_public_dentist": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "özel/Kurumla sözleşmesi olmayan resmi sunucuca yapılan diş tedavisi "
                "sonrasında EK-2/Ç-2 Diş Tedavileri Kontrol Formu ve/veya EK-2/Ç-3 "
                "ortodontik tedavi kontrol formu, diş ünitesi bulunan protokollü "
                "sözleşmeli resmi sunucuda görevli diş hekimi tarafından onaylanmalı"
            ),
            "annex_basis": "EK-2/Ç-2",
            "severity": "error",
        },
        "gate_b_sources": ["C000800"],
        "encode_batch": "REST",
    },

    # ── §2.4.1.B-2 — Ödeme esasları (özel/kurumsuz resmi) ────────────────────
    # (1) COVERAGE — %40+ engelli/özel gereksinimli çocuk diş hizmeti EK-2/Ç
    {
        "rule_id": "2.4.1.B-2.(1).disabled_dental_services_ek2c_coverage",
        "sut_section": "2.4.1.B-2",
        "condition": {
            "procedure_category": "dental",
            "facility_category_any": ["private", "non_contracted_public"],
            "patient_category_any": ["disabled_40pct_or_more", "special_needs_child_mild_or_above"],
            "procedure_in_ek2c": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "özel/Kurumla sözleşmesi olmayan resmi sunucudan %40+ engelli/özel "
                "gereksinimli çocuk hastaya verilen ağız ve diş sağlığı hizmeti "
                "bedelleri EK-2/Ç listesinde yer alması şartıyla işlem bedelleri "
                "üzerinden ödenir"
            ),
            "annex_basis": "EK-2/Ç",
            "severity": "error",
        },
        "gate_b_sources": ["C000804"],
        "encode_batch": "REST",
    },
    # (2) COVERAGE — özel/kurumsuz resmi sunucu ortodontik tedavi 2.4.1(4)'e göre ödenir
    {
        "rule_id": "2.4.1.B-2.(2).private_orthodontics_per_2_4_1_4_coverage",
        "sut_section": "2.4.1.B-2",
        "condition": {
            "procedure_category": "orthodontics",
            "facility_category_any": ["private", "non_contracted_public"],
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "özel/Kurumla sözleşmesi olmayan resmi sunucu diş ünitelerinde "
                "uygulanan ortodontik tedavi bedelleri SUT'un 2.4.1(4) fıkrasına göre ödenir"
            ),
        },
        "gate_b_sources": ["C000805"],
        "encode_batch": "REST",
    },
    # (4) NO_PAY — engelli/özel gereksinimli protez tedavisinde döküm/işçilik ödenmez
    {
        "rule_id": "2.4.1.B-2.(4).disabled_prosthesis_casting_labor_no_pay",
        "sut_section": "2.4.1.B-2",
        "condition": {
            "procedure_category": "dental_prosthesis",
            "facility_category_any": ["private", "non_contracted_public"],
            "patient_category_any": ["disabled_40pct_or_more", "special_needs_child_mild_or_above"],
            "charge_type_in": ["casting_fee", "labor_fee"],
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "engelli/özel gereksinimli çocuk hastalara verilen ağız ve diş sağlığı "
                "hizmeti kapsamındaki protez tedavileri için malzeme dâhil döküm ve "
                "işçilik ücreti ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000807"],
        "encode_batch": "REST",
    },
    # (5) COVERAGE — ortodontik faturalar her aşama tamamlandığında EK-2/Ç-3 üzerinden ödenir
    {
        "rule_id": "2.4.1.B-2.(5).orthodontics_payment_per_stage_ek2c3",
        "sut_section": "2.4.1.B-2",
        "condition": {
            "procedure_category": "orthodontics",
            "stage_completed": False,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "ortodontik tedavi uygulanan kişilere ait faturaların ödemeleri "
                "EK-2/Ç-3 listesinde yer alan formlar üzerinden her bir aşama "
                "tamamlandığında bedelleri ödenir"
            ),
            "annex_basis": "EK-2/Ç-3",
        },
        "gate_b_sources": ["C000810"],
        "encode_batch": "REST",
    },

    # ── §2.4.1.B-3 — Çıkar çatışması / uzmanlık belgelendirme ────────────────
    # (1) NO_PAY — sağlık kurulu raporu imzası bulunan hekim/kendisi/yakını tedavi edemez
    {
        "rule_id": "2.4.1.B-3.(1).board_signer_self_dealing_no_pay",
        "sut_section": "2.4.1.B-3",
        "condition": {
            "procedure_category_any": ["dental", "orthodontics"],
            "treating_provider_is_board_signer_or_relative_or_partner": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "sağlık kurulu raporunda imzası bulunan hekimin kendisinin, birinci "
                "derece yakınının veya bunların ortaklarının özel muayenehane/özel "
                "sunucu tarafından tedavi ettiği hastaların giderleri ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000812"],
        "encode_batch": "REST",
    },
    # (2) MANDATORY — (*) işaretli ve 7.1 ortodontik tedavilerde uzman/doktoralı belgelendirme
    {
        "rule_id": "2.4.1.B-3.(2).star_marked_or_orthodontics_specialist_required",
        "sut_section": "2.4.1.B-3",
        "condition": {
            "procedure_in_ek2c_star_marked": True,
            "procedure_section": "7.1_diagnosis_based_orthodontics",
            "performed_by_specialist_or_phd_dentist": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "EK-2/Ç listesinde (*) işaretli tedaviler ile '7.1 Tanıya dayalı "
                "ortodontik tedavi işlemleri' başlığı altındaki tedavilerin "
                "karşılanabilmesi için konularında uzman veya doktoralı diş hekimi "
                "tarafından yapıldığının belgelendirilmesi gerekmektedir"
            ),
            "annex_basis": "EK-2/Ç",
            "severity": "error",
        },
        "gate_b_sources": ["C000813"],
        "encode_batch": "REST",
    },

    # ── §2.4.2.A — Organ/doku nakli ──────────────────────────────────────────
    # (1) COVERAGE — organ/doku nakli tedavi ve verici giderleri Kurumca karşılanır
    {
        "rule_id": "2.4.2.A.(1).organ_tissue_transplant_coverage",
        "sut_section": "2.4.2.A",
        "condition": {
            "procedure_category": "organ_tissue_transplant",
            "subject_any": ["recipient", "donor"],
            "compliant_with_law_2238": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "2238 sayılı Kanun hükümleri dikkate alınmak şartıyla organ/doku "
                "nakli tedavilerine ilişkin giderler ile verici durumundaki kişinin "
                "bu tedaviye ilişkin giderleri Kurum tarafından karşılanır"
            ),
        },
        "gate_b_sources": ["C000816"],
        "encode_batch": "REST",
    },
    # (4) COVERAGE — organ transferi nakliye masrafı SUT 2.6 doğrultusunda
    {
        "rule_id": "2.4.2.A.(4).organ_transport_transfer_cost_coverage",
        "sut_section": "2.4.2.A",
        "condition": {
            "procedure_category": "organ_tissue_transplant",
            "organ_located_in_country": True,
            "expense_type": "recipient_organ_transport_round_trip",
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "yurt içinde organın bulunması halinde hastanın/organın bulunduğu "
                "yer arasındaki gidiş-dönüş nakliye/transfer masrafları SUT'un 2.6 "
                "maddesi doğrultusunda Kurumca karşılanır"
            ),
        },
        "gate_b_sources": ["C000821"],
        "encode_batch": "REST",
    },
    # (5) COVERAGE — kadavra donör temini P911146 EK-2/C
    {
        "rule_id": "2.4.2.A.(5).cadaver_donor_procurement_p911146",
        "sut_section": "2.4.2.A",
        "condition": {
            "procedure_code_any": ["P911146"],
            "donor_type": "cadaver",
            "notified_by_national_coordination_center": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "Ulusal Organ ve Doku Nakli Koordinasyon Merkezince bildirilen her "
                "kadavra donör için donörü temin eden sunucuya EK-2/C 'P911146 "
                "Kadavra donör temini' bedeli karşılanır; bu bedele kadavra organ "
                "alım işlemleri dâhildir"
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C000824"],
        "encode_batch": "REST",
    },
    # (6) MUST_NOT_BILL — ABO uyumsuz böbrek nakli aferez/malzeme ayrıca faturalanamaz
    {
        "rule_id": "2.4.2.A.(6).abo_incompatible_kidney_transplant_apheresis_no_bill",
        "sut_section": "2.4.2.A",
        "condition": {
            "procedure_category": "kidney_transplant",
            "abo_blood_group_compatible": False,
            "exception_no_dialysis_option_with_tier3_board_report": False,
            "charge_type_in": ["apheresis", "medical_material_for_apheresis"],
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "herhangi bir diyalizle tedavisi mümkün olmayan (3. basamak sağlık "
                "kurulu raporuyla belgelenen) hastalar hariç ABO uyumsuz böbrek "
                "nakli giderleri Kurumca karşılanmaz; yapılacak aferez ve tıbbi "
                "malzeme bedelleri ayrıca faturalandırılamaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000827"],
        "encode_batch": "REST",
    },

    # ── §2.4.2.B-1 — Kemik iliği nakli / doku tipleme ────────────────────────
    # (1) COVERAGE — HLA doku uyumluluk testleri (akraba, 30 aday sınıra kadar)
    {
        "rule_id": "2.4.2.B-1.(1).hla_typing_relative_donor_coverage",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_transplant",
            "test_type_any": ["molecular_typing", "serological_typing"],
            "donor_candidate_is_relative": True,
            "relative_candidates_tested": {"min": 1},
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "kemik iliği naklinde hastaların anne/baba/kardeş/çocuğundan HLA "
                "uyumlu verici bulmak için yapılan doku uyumluluk testleri ile uygun "
                "verici bulunamayanlarda 30 adayı geçmemek üzere HLA doku grubu "
                "belirleme testleri Kurum tarafından karşılanır"
            ),
        },
        "gate_b_sources": ["C000830"],
        "encode_batch": "REST",
    },
    # (3) MANDATORY — kemik iliği doku bilgi bankası işlem kodları (705.090/110/100/120)
    {
        "rule_id": "2.4.2.B-1.(3).bone_marrow_bank_billing_codes_mandatory",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_donor_typing",
            "stage": "first_phase_typing",
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "kemik iliği doku bilgi bankalarınca birinci aşama işlemler EK-2/B "
                "'705.090' ve '705.110', adres/serolojik doğrulama ve onay işlemleri "
                "'705.100' ve '705.120' işlem kodları üzerinden faturalandırılmalı"
            ),
            "annex_basis": "EK-2/B",
        },
        "gate_b_sources": ["C000832"],
        "encode_batch": "REST",
    },
    # (4) COVERAGE — yüksek çözünürlük DNA/HLA doğrulama (toplam 25 adayı geçmemek)
    {
        "rule_id": "2.4.2.B-1.(4).high_res_dna_hla_confirmation_domestic_25_cap",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_transplant",
            "test_type": "high_resolution_dna_hla_confirmation",
            "laboratory_licensed_by_moh": True,
            "total_candidates": {"min": 26},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "yurt içi ön taramada belirlenen verici adaylarının Bakanlıkça "
                "ruhsatlandırılmış doku tipleme laboratuvarlarında yüksek çözünürlük "
                "DNA ve HLA doğrulama testleri toplam 25 adayı geçmemek üzere Kurumca "
                "karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000833"],
        "encode_batch": "REST",
    },
    # (5) COVERAGE — akraba dışı kemik iliği/kordon kanı temini EK-2/C
    {
        "rule_id": "2.4.2.B-1.(5).unrelated_marrow_cord_blood_procurement_ek2c",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_transplant",
            "donor_type": "unrelated_domestic",
            "procedure_in_ek2c": False,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "akraba dışı kemik iliği vericisinin yurt içinde bulunması halinde "
                "'yurt içi kemik iliği/kordon kanı temini' bedeli EK-2/C üzerinden "
                "kemik iliği doku bilgi bankasına fatura bedelini aşmamak üzere karşılanır"
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C000834"],
        "encode_batch": "REST",
    },
    # (6) COVERAGE — yurt dışı kan örnekleri DNA/HLA (10 tek seferde, 25 toplam, 7/8 uyum)
    {
        "rule_id": "2.4.2.B-1.(6).foreign_marrow_samples_dna_hla_coverage",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_transplant",
            "domestic_match_found": False,
            "hla_match_degree": {"min": 7, "of": 8},
            "samples_per_batch": {"max": 10},
            "total_samples": {"max": 25},
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "yurt içinde uygun verici bulunmayan hastalar için yurt dışı kemik "
                "iliği bankaları aracılığıyla en az 7/8 doku uyumu gösteren kan "
                "örnekleri (tek seferde en fazla 10, toplamda 25'i geçmemek) yurt içi "
                "doku bankası/ruhsatlı laboratuvarda yüksek çözünürlük DNA ile HLA "
                "analizine tabi tutulur; bedelleri Kurumca karşılanır"
            ),
        },
        "gate_b_sources": ["C000835"],
        "encode_batch": "REST",
    },
    # (9) COVERAGE — kemik iliği/kordon kanı nakliye bedeli (Euro sınırları)
    {
        "rule_id": "2.4.2.B-1.(9).marrow_cord_transport_euro_caps",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_transplant",
            "expense_type": "marrow_cord_transport_to_turkey",
            "origin_continent_in": ["americas", "australia"],
            "transport_eur": {"min": 4500.01},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "kemik iliğinin Türkiye'deki nakil merkezine getirilmesi; Amerika/Avustralya "
                "için 4.500 Euro, diğer ülkeler için 2.000 Euro, kordon kanı tankı nakli "
                "için 5.000 Euro karşılığı TL'yi geçmemek üzere fatura karşılığı Kurumca ödenir; "
                "organizasyon, kurye taşıma ve konaklama dâhildir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000838"],
        "encode_batch": "REST",
    },
    # (10) COVERAGE — yurt dışı tarama/ileri test/erteleme/saklama bedelleri (WMDA üye)
    {
        "rule_id": "2.4.2.B-1.(10).foreign_marrow_screening_advance_payment_coverage",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_transplant",
            "expense_type_any": [
                "foreign_donor_screening", "advanced_donor_tests", "health_check",
                "sample_transport", "stem_cell_collection", "cancellation_fee",
                "deferral_fee", "cord_blood_storage_2yr", "activation_fee",
            ],
            "bank_is_wmda_member": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "yurt dışı kemik iliği/kordon kanı sürecinde tarama, ileri test, sağlık "
                "kontrol, kan örneği transfer, kök hücre toplama, iptal/erteleme/saklama "
                "ve aktivasyon bedelleri WMDA üye bankalarca belirlenen ücretler üzerinden "
                "Kurumca (İstanbul Sosyal Güvenlik İl Müdürlüğü) avans/havale ile ödenir; "
                "kişiye fatura düzenlenmişse kişiye ödenir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000839"],
        "encode_batch": "REST",
    },
    # (11) COVERAGE — kemik iliği nakli ruhsatlı merkez + EK-2/C işlem puanları
    {
        "rule_id": "2.4.2.B-1.(11).bone_marrow_transplant_licensed_center_ek2c",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_transplant",
            "facility_licensed_for_bone_marrow_transplant": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "kemik iliği nakli (hematopoietik kök hücre nakli) tedavisi Bakanlıkça "
                "ruhsatlandırılmış ve çalışma izni almış kemik iliği nakli merkezlerince "
                "uygulanır; bedelleri EK-2/C 'Kemik İliği Nakli' işlem puanları üzerinden "
                "Kurumca karşılanır"
            ),
            "annex_basis": "EK-2/C",
            "severity": "error",
        },
        "gate_b_sources": ["C000840"],
        "encode_batch": "REST",
    },
    # (12) COVERAGE — 1/5/2013 öncesi yurt dışı tarama/temin faturaları Kurumca karşılanır
    {
        "rule_id": "2.4.2.B-1.(12).pre_2013_foreign_marrow_invoice_coverage",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_transplant",
            "invoice_date_before": "2013-05-01",
            "previously_unpaid_under_prior_sut": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "1/5/2013 öncesi SUT kuralları gereği karşılanamayan yurt dışı kemik "
                "iliği/kordon kanı tarama ve temin fatura bedelleri yukarıdaki hükümler "
                "doğrultusunda Kurumca karşılanır"
            ),
        },
        "gate_b_sources": ["C000842"],
        "encode_batch": "REST",
    },

    # ── §2.4.2.B-2 — Mezenkimal kök hücre nakli ──────────────────────────────
    # (2) COVERAGE — mezenkimal kök hücre nakli sağlık kurulu + Bakanlık onayı
    {
        "rule_id": "2.4.2.B-2.(2).mesenchymal_stem_cell_board_moh_approval_coverage",
        "sut_section": "2.4.2.B-2",
        "condition": {
            "procedure_category": "mesenchymal_stem_cell_transplant",
            "indication_in_board_report": False,
            "moh_approval_per_patient": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "yapılan mezenkimal kök hücre nakli tedavi bedeli; durumun sağlık "
                "kurulu raporunda belirtilmesi ve raporun Sağlık Bakanlığı tarafından "
                "her hasta için ayrı onaylanarak izin verilmesi halinde Kurumca karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000847"],
        "encode_batch": "REST",
    },
    # (3) MANDATORY — mezenkimal kök hücre üretimi Kök Hücre Üretim Merkezinde (704.981)
    {
        "rule_id": "2.4.2.B-2.(3).mesenchymal_stem_cell_production_center_mandatory",
        "sut_section": "2.4.2.B-2",
        "condition": {
            "procedure_code_any": ["704.981"],
            "stem_cell_production_in_moh_designated_center": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "'mezenkimal kök hücre nakli (üretim dâhil)' EK-2/B '704.981' işlemi "
                "için üretimin Bakanlıkça tanımlanan Kök Hücre Üretim Merkezinde "
                "yapılmış olması şarttır"
            ),
            "annex_basis": "EK-2/B",
            "severity": "error",
        },
        "gate_b_sources": ["C000849"],
        "encode_batch": "REST",
    },
    # (4) MUST_NOT_BILL — allojenik KİN ±15g/±90g içinde mesenkimal dahil, ayrıca faturalanamaz
    {
        "rule_id": "2.4.2.B-2.(4).mesenchymal_within_allo_bmt_window_no_bill",
        "sut_section": "2.4.2.B-2",
        "condition": {
            "procedure_code_any": ["704.981"],
            "days_from_allogeneic_bmt": {"min": -15, "max": 90},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "mezenkimal kök hücre nakli allojenik kemik iliği nakli öncesi 15 gün "
                "ve/veya sonrası 90 gün içinde uygulandığında kemik iliği nakli "
                "bedeline dâhil olur, ayrıca faturalandırılmaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000850"],
        "encode_batch": "REST",
    },

    # ── §2.4.3 — Aşı bedelleri ───────────────────────────────────────────────
    # 2.4.3-A COVERAGE — GBKP dışı aşılar yüksek riskli sağlık raporuyla
    {
        "rule_id": "2.4.3.A.non_gbep_vaccine_high_risk_coverage",
        "sut_section": "2.4.3",
        "condition": {
            "procedure_category": "vaccine",
            "in_gbep_program": False,
            "patient_high_risk_category": True,
            "health_report_present": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "Genişletilmiş Bağışıklama Programı kapsamında olmayan aşı bedelleri; "
                "kronik böbrek yetmezliği, kistik fibrozis, KOAH, kanser, HIV/AIDS, "
                "splenektomi ve immünsupresif tedaviye bağlı bağışıklık durumu olumsuz "
                "etkilenen yüksek riskli kişilerin bu durumunu belirten sağlık "
                "raporuna istinaden karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000852"],
        "encode_batch": "REST",
    },
    # 2.4.3-B COVERAGE — grip aşısı yılda bir kez Eylül-Mart, risk grupları
    {
        "rule_id": "2.4.3.B.influenza_vaccine_annual_sept_mar_coverage",
        "sut_section": "2.4.3",
        "condition": {
            "procedure_category": "influenza_vaccine",
            "patient_category_any": [
                "age_65_plus", "nursing_home_resident", "pregnant_2nd_3rd_trimester",
                "chronic_pulmonary_cardiovascular", "chronic_metabolic_diabetes",
                "chronic_renal_dysfunction", "hemoglobinopathy", "immune_deficiency",
                "immunosuppressive_therapy", "child_6mo_18yr_long_term_asa",
            ],
            "season_window_sep_to_mar": False,
            "prior_dose_in_same_year": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "grip aşısı bedeli; 65 yaş ve üzeri ile huzurevinde kalanlar rapor "
                "aranmaksızın, diğer risk grupları sağlık raporuyla Eylül-Mart döneminde "
                "tüm hekimlerce reçete edildiğinde yılda bir defaya mahsus karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000855"],
        "encode_batch": "REST",
    },
    # 2.4.3-C COVERAGE — pnömokok aşısı 5 yılda bir, risk grupları / 65+ raporsuz
    {
        "rule_id": "2.4.3.C.pneumococcal_vaccine_5yr_coverage",
        "sut_section": "2.4.3",
        "condition": {
            "procedure_category": "pneumococcal_polysaccharide_vaccine",
            "patient_category_any": [
                "asplenia_splenectomy_sickle_cell", "immunosuppression",
                "chronic_renal_nephrotic", "chronic_heart", "chronic_lung_asthma",
                "chronic_liver_cirrhosis", "chronic_metabolic_diabetes",
                "hemoglobinopathy", "csf_leak_cranial_defect", "age_65_plus",
            ],
            "years_since_prior_dose": {"max": 4.99},
            "health_report_present_or_age_65_plus": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "pnömokok aşısı (polisakkarit) bedeli; 2 yaş üstü risk gruplarında "
                "sağlık raporuyla, 65 yaş ve üzeri rapor aranmaksızın beş yılda bir "
                "kez karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000856"],
        "encode_batch": "REST",
    },
    # 2.4.3-D COVERAGE — hepatit A aşısı yılda en fazla 2 kez, risk grupları
    {
        "rule_id": "2.4.3.D.hepatitis_a_vaccine_annual_2x_coverage",
        "sut_section": "2.4.3",
        "condition": {
            "procedure_category": "hepatitis_a_vaccine",
            "patient_category_any": [
                "chronic_liver_disease", "clotting_factor_concentrate_recipient",
            ],
            "hepatitis_a_seronegative": True,
            "patient_age_years": {"min": 1},
            "doses_within_year": {"min": 3},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "hepatit A aşısı bedeli; kronik karaciğer hastalığı olan veya "
                "pıhtılaşma faktörü konsantresi alan Hepatit A seronegatif 1 yaş "
                "üstü çocuk ve erişkinlerde sağlık raporuyla tüm hekimlerce "
                "reçete edilmesi halinde en fazla yılda iki kez karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000857"],
        "encode_batch": "REST",
    },
]
