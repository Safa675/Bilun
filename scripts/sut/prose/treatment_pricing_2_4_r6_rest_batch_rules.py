"""§2.4 remaining (r6 rest) treatment-package pricing & coverage rules — batch.

Gate-B encoded rules for the remaining §2.4 clauses that were NOT already
encoded in the §2.4.4 wave-2 family. This batch covers §2.4.1 (diş tedavileri
/ ortodonti / protez / implant / özel sunucu diş üniteleri), §2.4.1.A/B/B-1/B-2/
B-3, §2.4.2.A (organ & doku nakli / kadavra donör temini / ABO uyumsuz böbrek
nakli), §2.4.2.B-1 (kemik iliği nakli HLA tarama / temin / nakliye), §2.4.2.B-2
(mezenkimal kök hücre nakli) and §2.4.3 (aşı bedelleri) clauses.

Modalities covered here: NO_PAY, MUST_BILL, COVERAGE, MUST_NOT_BILL,
REGULATORY_ACTION, MANDATORY.

Each rule's `gate_b_sources` carries exactly one clause_id from
tasks/encode_waves/REM_2_4.csv (42 clauses → 42 rules).

Merge target: data/gazette/prose_rules/treatment_pricing_2_4.json
"""

from __future__ import annotations

from typing import Any

BATCH_RULES: list[dict[str, Any]] = [
    # ── §2.4.1 — Diş tedavileri (genel) ──────────────────────────────────────
    # C000734 NO_PAY — kıymetli madenli diş tedavi malzemeleri ödenmez
    {
        "rule_id": "2.4.1.(1).precious_metal_dental_materials_no_pay",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "dental_treatment",
            "material_is_precious_metal": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "diş tedavileri sırasında; altın, platin, paladyum+platin, "
                "irrudyum+platin, iropal gibi kıymetli madenler ile argenco 23, "
                "bego gold EWL ve polliag-M gibi bileşiminde kıymetli maden bulunan "
                "maddelerin bedelleri ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000734"],
        "encode_batch": "R6_REST",
    },
    # C000742 NO_PAY — kemik içi implant bedelleri ödenmez (ancak istisnası var)
    {
        "rule_id": "2.4.1.(2).endosseous_implant_base_no_pay",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "dental_implant_endosseous",
            "implant_exception_conditions_met": False,
        },
        "action": {
            "billable": False,
            "denial_tr": "kemik içi implantların bedelleri ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C000742"],
        "encode_batch": "R6_REST",
    },
    # C000747 MUST_BILL — implant istisnası: 4 adet/sayı + 750/2500 TL faturalandırma
    {
        "rule_id": "2.4.1.(2).implant_exception_4_per_jaw_750tl",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "dental_implant_endosseous",
            "university_board_report_with_surgery_prosthesis_periodontology": True,
            "radiographic_evidence_attached": True,
            "implant_count_per_jaw": {"min": 1, "max": 4},
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "rutin protetik tedavi ile tedavi edilemeyeceği implantın zorunlu "
                "olduğu üniversite diş hekimliği fakültesi sağlık kurulu raporuyla "
                "belgelendirilmek şartıyla her bir çene için en fazla 4 adet EK-2/Ç "
                "“kemik içi implant uygulaması” bedeli ile her implant için 750 TL, "
                "vazife/harp malullerinde en fazla 2500 TL üzerinden faturalandırılır"
            ),
            "billing_method": "procedure_package",
            "annex_basis": "EK-2/Ç",
        },
        "gate_b_sources": ["C000747"],
        "encode_batch": "R6_REST",
    },
    # C000748 NO_PAY — sabit/hareketli protez yenilenme 4 yıl içinde
    {
        "rule_id": "2.4.1.(3).prosthesis_renewal_within_4_years_no_pay",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "dental_prosthesis_replacement",
            "years_since_last_prosthesis": {"max": 3.99},
            "exception_traffic_work_accident_or_neoplasm_or_weight_loss": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "hareketli ve sabit protezlerin yenilenme süresi 4 yıldır; bu süreden "
                "önce yenilenen protez bedelleri Kurumca ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000748"],
        "encode_batch": "R6_REST",
    },
    # C000752 NO_PAY — 18 yaş üstü ortodontik diş tedavisi (devam eden/5510 öncesi hariç)
    {
        "rule_id": "2.4.1.(a).adult_orthodontics_18plus_no_pay",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "orthodontic_treatment",
            "patient_age": {"min": 18},
            "treatment_started_before_age_18_and_ongoing": False,
            "started_before_gss_effective_date": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "18 yaşını doldurmuş kişilerin ortodontik diş tedavilerine ilişkin "
                "giderler Kurumca ödenmez; ancak tedavi 18 yaşından önce başlamış ve "
                "devam ediyorsa karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000752"],
        "encode_batch": "R6_REST",
    },
    # C000753 COVERAGE — erken ortodontik tedavi (P407321/P407322) 6-14 yaş
    {
        "rule_id": "2.4.1.(b).early_orthodontic_p407321_p407322",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_code_any": ["P407321", "P407322"],
            "patient_age": {"min": 6, "max": 14},
            "performed_by_orthodontist_or_doctor": True,
            "min_3_months_between_start_and_end_phase": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "dental ve iskeletsel malokluzyonu düzeltmek için yapılan erken "
                "ortodontik uygulamalar P407321/P407322 işlem kodları üzerinden, "
                "6-14 yaş, ortodonti uzmanı/doktoralı hekim ve başlangıç-bitiş "
                "aşamaları arası en az 3 ay olması şartıyla Kurumca karşılanır"
            ),
            "procedure_package": "EK-2/Ç-7.1",
            "annex_basis": "EK-2/Ç",
        },
        "gate_b_sources": ["C000753"],
        "encode_batch": "R6_REST",
    },
    # C000754 COVERAGE — sabit ortodontik (Sınıf I/II/III + ortognatik) minimum aralıklar
    {
        "rule_id": "2.4.1.(c).fixed_orthodontics_class1_2_3_min_intervals",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "fixed_orthodontic_treatment",
            "malocclusion_class_any": ["class_I", "class_II", "class_III", "orthognathic"],
            "performed_by_orthodontist_or_doctor": True,
            "months_between_start_and_treatment_phase": {"min": 6},
            "months_between_treatment_and_retention_phase": {"min": 4},
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "sınıf I/II/III ve ortognatik cerrahide sabit ortodontik tedaviler "
                "EK-2/Ç 7.1 işlem kodları üzerinden; başlangıç ile tedavi aşamaları "
                "arası en az 6 ay, tedavi ile pekiştirme aşamaları arası en az 4 ay "
                "olması ve ortodonti uzmanı/doktoralı hekim tarafından yapılması şartıyla "
                "Kurumca karşılanır"
            ),
            "procedure_package": "EK-2/Ç-7.1",
            "annex_basis": "EK-2/Ç",
        },
        "gate_b_sources": ["C000754"],
        "encode_batch": "R6_REST",
    },
    # C000755 COVERAGE — yarık dudak-damak ortodonti (P407342/343/344) yaş aralıkları
    {
        "rule_id": "2.4.1.(c_cleft).cleft_lip_palate_orthodontics_age_windows",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_code_any": ["P407342", "P407343", "P407344"],
            "facility_is_university_dental_faculty": True,
            "performed_by_orthodontist_or_doctor": True,
            "pre_post_op_photos_documented": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "yarık dudak-damak/damak şekillendirme ve ortodontik tedaviler "
                "P407342/P407343/P407344 kodları üzerinden; doğum sonrası şekillendirme "
                "60 ay öncesi, karışık dişlenme 6-12 yaş, daimi dişlenme 12 yaş sonrası, "
                "üniversite diş hekimliği fakültesinde fotoğrafla belgelendirmek ve "
                "ortodonti uzmanı/doktoralı hekim tarafından yapılması şartıyla karşılanır"
            ),
            "procedure_package": "EK-2/Ç-7.1",
            "annex_basis": "EK-2/Ç",
        },
        "gate_b_sources": ["C000755"],
        "encode_batch": "R6_REST",
    },

    # ── §2.4.1.A — Sözleşmeli resmi sunucuda diş tedavi bedelleri ────────────
    # C000760 MUST_BILL — resmi sunucuda EK-2/Ç uygulanır; protezde döküm/işçilik ayrı yok
    {
        "rule_id": "2.4.1.A.(1).contracted_public_dental_ek2c_prosthesis_inclusive",
        "sut_section": "2.4.1.A",
        "condition": {
            "facility_type": "contracted_public_health_provider",
            "procedure_category": "dental_treatment_prosthesis",
            "separate_casting_or_labor_fee_charged": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "sözleşmeli resmi sunucularda diş tedavi bedelleri EK-2/Ç Listesi "
                "uygulanır; protez tedavilerinde ayrıca döküm ve işçilik ücreti "
                "ödenmez (malzeme/döküm/işçilik protez ücretine dahildir)"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000760"],
        "encode_batch": "R6_REST",
    },
    # C000762 MUST_BILL — %40+ engelli/özel gereksinim çocuk GA/sedo altında 2 kat
    {
        "rule_id": "2.4.1.A.(2).disabled_or_special_need_child_ga_sedo_2x",
        "sut_section": "2.4.1.A",
        "condition": {
            "facility_type": "contracted_public_health_provider",
            "procedure_category": "dental_treatment_under_anesthesia",
            "patient_disabled_40pct_or_special_need_child": True,
            "anesthesia_or_sedo_analgesia": True,
            "disability_report_attached_to_invoice": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "sözleşmeli resmi sunucularda %40 ve üzeri engelli kişiler ile "
                "hafif düzey ve üstü özel gereksinimli çocuk hastalarda genel anestezi "
                "veya sedo-analjezi altında verilen diş tedavileri EK-2/Ç işlem puanı "
                "bedellerinin iki katı olarak faturalandırılır"
            ),
            "billing_method": "multiplier_2x",
            "annex_basis": "EK-2/Ç",
        },
        "gate_b_sources": ["C000762"],
        "encode_batch": "R6_REST",
    },

    # ── §2.4.1.B — Özel/sözleşmesiz resmi sunucu diş üniteleri kapsamı ───────
    # C000787 REGULATORY_ACTION — kapsamdaki kişilerin özel/sözleşmesiz sunucu diş üniteleri
    {
        "rule_id": "2.4.1.B.(1).private_uncontracted_dental_units_scope",
        "sut_section": "2.4.1.B",
        "condition": {
            "facility_type_any": ["private_provider", "uncontracted_public_provider"],
            "patient_in_general_scope_not_in_5510_excluded_groups": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "5510 sayılı Kanun 60/c-1 veya 60/c-3 bentleri ile 12/13/14. fıkra "
                "kapsamı hariç diğer kişilerin özel sağlık hizmeti sunucuları ile "
                "Kurumla sözleşmesi olmayan resmi sunucular diş ünitelerindeki ağız "
                "ve diş sağlığı hizmetleri aşağıdaki şekilde yapılır"
            ),
            "billing_method": "procedure_package",
        },
        "gate_b_sources": ["C000787"],
        "encode_batch": "R6_REST",
    },

    # ── §2.4.1.B-1 — Özel/sözleşmesiz sunucuda diş tedavisi koşulları ────────
    # C000791 NO_PAY — ortodontik + %40 altı engelli dışındakilerin özel/sözleşmesiz tedavisi
    {
        "rule_id": "2.4.1.B-1.(1).private_uncontracted_dental_default_no_pay",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "facility_type_any": ["private_provider", "uncontracted_public_provider"],
            "procedure_category_any": ["orthodontic_treatment", "dental_treatment"],
            "patient_disabled_40pct_or_above": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "ortodontik diş tedavileri ile %40 ve üzerinde engelli kişiler hariç, "
                "kapsamdaki kişilerin özel sağlık hizmeti sunucuları ile Kurumla "
                "sözleşmesi olmayan resmi sunucularındaki diş ünitelerinde yapılan "
                "ağız ve diş sağlığına ilişkin tedaviler Kurumca ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000791"],
        "encode_batch": "R6_REST",
    },
    # C000794 MANDATORY — %40+ engelli/özel gereksinim çocuk için belge + rapor + 10 işgünü başlangıç
    {
        "rule_id": "2.4.1.B-1.(2).disabled_child_private_dental_report_10_biz_days",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "patient_disabled_40pct_or_special_need_child": True,
            "facility_type_any": ["private_provider", "uncontracted_public_provider"],
            "disability_or_special_need_documented": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "%40 ve üzeri engelli veya hafif düzey ve üstü özel gereksinimli "
                "çocukların özel/sözleşmesiz sunuculardaki diş tedavilerinin "
                "ödenebilmesi için engellilik/özel gereksinim durumu belgelendirilmeli; "
                "ADSM/ADSH/üniversite diş hekimliği tarafından sağlık raporu düzenlenmeli "
                "ve rapor tarihinden itibaren 10 iş günü içinde tedaviye başlanmalıdır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000794"],
        "encode_batch": "R6_REST",
    },
    # C000795 MANDATORY — iletişim kurulamayan engelli GA/sedo için uygun birim belgesi
    {
        "rule_id": "2.4.1.B-1.(3).non_communicative_disabled_ga_unit_documentation",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "patient_communication_impaired_disabled": True,
            "procedure_category": "dental_treatment_under_anesthesia",
            "limited_sedation_not_feasible": True,
            "ga_or_sedo_analgesia_unit_documented": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "iletişim kurulamayan/algılama güçlüğü yaşanan engelli kişilerin diş "
                "tedavilerinde sınırlı uyuşturma mümkün değilse genel anestezi veya "
                "sedo-analjezi bedelinin ödenebilmesi için anesteziyoloji ve reanimasyon "
                "uzmanı sorumluluğunda, ADSM/tıp merkezi/hastane ameliyathane ve genel "
                "anestezi ünitelerinde yapıldığının belgelendirilmesi gerekmektedir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000795"],
        "encode_batch": "R6_REST",
    },
    # C000799 MANDATORY — ortodontik tedavi gereksinimi için 3 diş hekimi sağlık kurulu raporu
    {
        "rule_id": "2.4.1.B-1.(5).orthodontics_3_dentist_board_report_6mo",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "procedure_category": "orthodontic_treatment",
            "facility_type_any": ["private_provider", "uncontracted_public_provider"],
            "health_board_report_by_3_dentists": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "ortodontik tedavi gereksinimi olan hastalar ADSM/ADSH/üniversite diş "
                "hekimliği fakültelerince (ortodonti uzmanı/doktoralı hekim katılımlı) "
                "üç diş hekimi tarafından düzenlenen sağlık kurulu raporu ile özel/"
                "sözleşmesiz sunuculara başvurabilir; raporda estetik olmadığı ve "
                "maloklüzyon tipi belirtilmeli ve rapor tarihinden 6 ay içinde başlanmalıdır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000799"],
        "encode_batch": "R6_REST",
    },
    # C000800 MANDATORY — tedavi sonrası kontrol formu sözleşmeli resmi sunucu onayı
    {
        "rule_id": "2.4.1.B-1.(6).post_treatment_control_form_public_dentist_approval",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "facility_type_any": ["private_provider", "uncontracted_public_provider"],
            "procedure_category_any": ["dental_treatment", "orthodontic_treatment"],
            "control_form_approved_by_contracted_public_dentist": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "özel/sözleşmesiz sunucularca yapılan diş tedavileri sonrasında "
                "EK-2/Ç-2 “Diş Tedavileri Kontrol Formu” ve/veya EK-2/Ç-3 “Tanıya "
                "Dayalı Ortodontik Tedavi Kontrol Formu”ndaki tedavinin yapıldığına "
                "dair bölümün sözleşmeli resmi sunucuda görevli diş hekimi tarafından "
                "onaylanması gerekmektedir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000800"],
        "encode_batch": "R6_REST",
    },

    # ── §2.4.1.B-2 — Özel/sözleşmesiz sunucu %40+ engelli diş tedavisi ödeme ─
    # C000804 COVERAGE — %40+ engelli/özel gereksinim çocuk EK-2/Ç bedeli üzerinden
    {
        "rule_id": "2.4.1.B-2.(1).disabled_or_special_need_child_ek2c_fee",
        "sut_section": "2.4.1.B-2",
        "condition": {
            "patient_disabled_40pct_or_special_need_child": True,
            "facility_type_any": ["private_provider", "uncontracted_public_provider"],
            "procedure_in_ek2c_list": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "özel/sözleşmesiz sunuculardan %40 ve üzeri engelli kişilere veya "
                "hafif düzey ve üstü özel gereksinimli çocuk hastalara verilen ağız "
                "ve diş sağlığı hizmetlerinin ücretleri EK-2/Ç listesinde yer alması "
                "şartıyla işlem bedelleri üzerinden ödenir"
            ),
            "billing_method": "procedure_package",
            "annex_basis": "EK-2/Ç",
        },
        "gate_b_sources": ["C000804"],
        "encode_batch": "R6_REST",
    },
    # C000805 COVERAGE — özel/sözleşmesiz sunucu ortodontik tedavi 2.4.1(4)’e göre
    {
        "rule_id": "2.4.1.B-2.(2).private_uncontracted_orthodontics_per_2_4_1_4",
        "sut_section": "2.4.1.B-2",
        "condition": {
            "procedure_category": "orthodontic_treatment",
            "facility_type_any": ["private_provider", "uncontracted_public_provider"],
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "özel/sözleşmesiz sunucu diş ünitelerinde uygulanan ortodontik tedavi "
                "bedelleri SUT’un 2.4.1(4) fıkrasına göre ödenir"
            ),
            "billing_method": "procedure_package",
        },
        "gate_b_sources": ["C000805"],
        "encode_batch": "R6_REST",
    },
    # C000807 NO_PAY — %40+ engelli/özel gereksinim protezinde malzeme+döküm+işçilik ayrı yok
    {
        "rule_id": "2.4.1.B-2.(4).disabled_prosthesis_no_separate_material_casting_labor",
        "sut_section": "2.4.1.B-2",
        "condition": {
            "patient_disabled_40pct_or_special_need_child": True,
            "procedure_category": "dental_prosthesis",
            "facility_type_any": ["private_provider", "uncontracted_public_provider"],
            "separate_material_casting_labor_fee_charged": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "%40 ve üzeri engelli/özel gereksinimli çocuk hastalara verilen ağız "
                "ve diş sağlığı hizmetleri kapsamında uygulanan protez tedavileri için "
                "malzeme dahil döküm ve işçilik ücreti ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000807"],
        "encode_batch": "R6_REST",
    },
    # C000810 COVERAGE — ortodontik faturalar EK-2/Ç-3 formları üzerinden aşama aşama
    {
        "rule_id": "2.4.1.B-2.(5).orthodontic_invoices_ek2c3_stage_payment",
        "sut_section": "2.4.1.B-2",
        "condition": {
            "procedure_category": "orthodontic_treatment",
            "stage_completed": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "ortodontik tedavi uygulanan kişilere ait faturaların ödemeleri EK-2/Ç-3 "
                "Listesinde yer alan formlar üzerinden her bir aşama tamamlandığında "
                "bedelleri ödenir"
            ),
            "billing_method": "procedure_package",
            "annex_basis": "EK-2/Ç-3",
        },
        "gate_b_sources": ["C000810"],
        "encode_batch": "R6_REST",
    },

    # ── §2.4.1.B-3 — Kendi hekimi/yakınına tedavi yasağı + uzmanlık ──────────
    # C000812 NO_PAY — raporu düzenleyen hekim/kendisi/eşi/ortağı tedavi ederse ödenmez
    {
        "rule_id": "2.4.1.B-3.(1).self_referral_board_signer_treatment_no_pay",
        "sut_section": "2.4.1.B-3",
        "condition": {
            "treating_provider_is_board_signer_or_first_degree_relative_or_partner": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "sağlık kurulu raporunda imzası bulunan hekimin kendisinin, birinci "
                "derece yakınının veya bunların ortaklarının özel muayenehanelerince/"
                "özel sunucularınca tedavi edilmesi halinde söz konusu tedavi giderleri "
                "ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000812"],
        "encode_batch": "R6_REST",
    },
    # C000813 MANDATORY — (*) işaretli ve 7.1 ortodontik tedaviler uzman/doktora zorunlu
    {
        "rule_id": "2.4.1.B-3.(2).star_and_7_1_orthodontics_specialist_required",
        "sut_section": "2.4.1.B-3",
        "condition": {
            "procedure_in_ek2c_star_marked_or_section_7_1": True,
            "performed_by_specialist_or_doctor_dentist": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "EK-2/Ç Listesinde (*) işaretli tedaviler ile “7.1 Tanıya dayalı "
                "ortodontik tedavi işlemleri” bölümündeki tedavilerin karşılanabilmesi "
                "için tedavinin konularında uzman veya doktoralı diş hekimleri tarafından "
                "yapıldığının belgelendirilmesi gerekmektedir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000813"],
        "encode_batch": "R6_REST",
    },

    # ── §2.4.2.A — Organ & doku nakli ────────────────────────────────────────
    # C000816 COVERAGE — organ/doku nakli tedavi + verici giderleri karşılanır (2238 sayılı Kanun)
    {
        "rule_id": "2.4.2.A.(1).organ_tissue_transplant_recipient_donor_covered",
        "sut_section": "2.4.2.A",
        "condition": {
            "procedure_category_any": ["organ_transplant", "tissue_transplant"],
            "compliant_with_2238_law": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "organ veya doku nakline gerek görülmesi halinde 2238 sayılı Kanun "
                "hükümleri dikkate alınmak şartıyla organ/doku nakli tedavilerine "
                "ilişkin giderler ile verici durumundaki kişinin bu tedaviye ilişkin "
                "giderleri Kurum tarafından karşılanır"
            ),
            "billing_method": "procedure_package",
        },
        "gate_b_sources": ["C000816"],
        "encode_batch": "R6_REST",
    },
    # C000821 COVERAGE — yurt içi organ bulunması halinde nakliye/transfer (SUT 2.6)
    {
        "rule_id": "2.4.2.A.(4).domestic_organ_transfer_per_2_6",
        "sut_section": "2.4.2.A",
        "condition": {
            "organ_found_in_country": True,
            "service_category": "patient_transfer_for_transplant",
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "yurt içinde organın bulunması halinde hastanın organın bulunduğu "
                "yere veya organ nakli yapılacak merkezin bulunduğu yere getirilmesine "
                "ilişkin gidiş-dönüş nakliye/transfer masrafları SUT’un 2.6 maddesi "
                "doğrultusunda Kurumca karşılanır"
            ),
            "billing_method": "fee_for_service",
        },
        "gate_b_sources": ["C000821"],
        "encode_batch": "R6_REST",
    },
    # C000824 COVERAGE — kadavra donör temini P911146 bedeli (EK-2/C)
    {
        "rule_id": "2.4.2.A.(5).cadaver_donor_procurement_p911146_ek2c",
        "sut_section": "2.4.2.A",
        "condition": {
            "procedure_code_any": ["P911146"],
            "donor_reported_by_national_coordination_center": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "Ulusal Organ ve Doku Nakli Koordinasyon Merkezince bildirilen her bir "
                "kadavra donör için donörü temin eden sunucuya EK-2/C “P911146 Kadavra "
                "donör temini” bedeli karşılanır; bedele kadavra organ alım işlemleri dahildir"
            ),
            "billing_method": "fee_for_service",
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C000824"],
        "encode_batch": "R6_REST",
    },
    # C000827 MUST_NOT_BILL — ABO uyumsuz böbrek nakli (istisna hariç) + aferez ayrı fatura yok
    {
        "rule_id": "2.4.2.A.(6).abo_incompatible_kidney_transplant_no_pay",
        "sut_section": "2.4.2.A",
        "condition": {
            "procedure_category": "abo_incompatible_kidney_transplant",
            "patient_unable_for_any_dialysis_with_tier3_board_report": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "herhangi bir diyaliz yöntemiyle tedavisi mümkün olmayan (sözleşmeli "
                "3. basamak sunucu sağlık kurulu raporuyla belgelenen) hastalar hariç, "
                "ABO kan grubu uyumsuz böbrek nakline ilişkin giderler Kurumca karşılanmaz; "
                "ABO uyumsuz nakilde uygulanacak aferez işlemi ve tıbbi malzeme bedelleri "
                "ayrıca faturalandırılamaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000827"],
        "encode_batch": "R6_REST",
    },

    # ── §2.4.2.B-1 — Kemik iliği nakli (HLA tarama / temin / nakliye) ────────
    # C000830 COVERAGE — HLA doku uyum testleri (anne/baba/kardeş/çocuk + 30 aday)
    {
        "rule_id": "2.4.2.B-1.(1).hla_compatibility_tests_relatives_max30",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_transplant",
            "test_type": "hla_compatibility_typing",
            "candidate_count": {"max": 30},
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "kemik iliği nakli tedavilerinde hastanın anne/baba/kardeş/çocuğundan "
                "HLA uyumlu verici bulmak için yapılan doku uyumluluk testleri ile uygun "
                "vericisi bulunamayan hastaların 30 adayı geçmemek üzere HLA doku grubu "
                "belirleme testleri Kurum tarafından karşılanır"
            ),
            "billing_method": "fee_for_service",
        },
        "gate_b_sources": ["C000830"],
        "encode_batch": "R6_REST",
    },
    # C000832 MANDATORY — kemik iliği doku bilgi bankası 1. aşama 705.090/110, doğrulama 705.100/120
    {
        "rule_id": "2.4.2.B-1.(3).marrow_bank_stage1_705090_110_verify_705100_120",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_donor_typing",
            "billing_outside_codes": ["705.090", "705.110", "705.100", "705.120"],
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "kemik iliği doku bilgi bankalarınca birinci aşama işlemler EK-2/B "
                "“705.090” ve “705.110” kodları üzerinden, adres/serolojik doku tipi "
                "doğrulama ve onay alma işlemleri “705.100” ve “705.120” kodları üzerinden "
                "faturalandırılması gerekmektedir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000832"],
        "encode_batch": "R6_REST",
    },
    # C000833 COVERAGE — yüksek çözünürlük DNA/HLA doğrulama testleri toplam 25 aday
    {
        "rule_id": "2.4.2.B-1.(4).high_res_dna_hla_confirmation_max25",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_donor_confirmation",
            "lab_licensed_by_moh": True,
            "candidate_count": {"max": 25},
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "yurt içi ön taramalarda belirlenen verici adaylarının Bakanlıkça "
                "ruhsatlandırılmış doku tipleme laboratuvarlarında yapılan yüksek "
                "çözünürlük DNA testi ile HLA doku grubu doğrulama testleri giderleri "
                "toplam 25 adayı geçmemek üzere Kurum tarafından karşılanır"
            ),
            "billing_method": "fee_for_service",
        },
        "gate_b_sources": ["C000833"],
        "encode_batch": "R6_REST",
    },
    # C000834 COVERAGE — yurt içi akraba dışı kemik iliği/kordon kanı temini (EK-2/C)
    {
        "rule_id": "2.4.2.B-1.(5).domestic_unrelated_marrow_cord_procurement_ek2c",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "unrelated_marrow_or_cord_procurement_domestic",
            "donor_found_in_country": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "akraba dışı kemik iliği vericisinin ülkemizde bulunması halinde “yurt "
                "içi kemik iliği temini/kordon kanı temini” bedeli EK-2/C Listesi "
                "üzerinden fatura bedelini aşmamak üzere karşılanır"
            ),
            "billing_method": "fee_for_service",
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C000834"],
        "encode_batch": "R6_REST",
    },
    # C000835 COVERAGE — yurt dışı HLA doğrulama 7/8 uyum (≤10 sefer/25 kişi)
    {
        "rule_id": "2.4.2.B-1.(6).foreign_hla_confirmation_7of8_max10x25",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_donor_confirmation_foreign",
            "hla_match_7_of_8_or_better": True,
            "samples_per_batch": {"max": 10},
            "total_candidates": {"max": 25},
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "yurt içinde uygun vericisi bulunmayan hastalar için yurt dışı "
                "kemik iliği bankaları aracılığıyla en az 7/8 doku tipi uyumu gösteren "
                "kan örnekleri (bir defada en fazla 10, toplamda 25 kişiyi geçmemek "
                "üzere) yüksek çözünürlük DNA yöntemi ile HLA doku grubu analizine "
                "tabi tutulur; test bedelleri Kurum tarafından karşılanır"
            ),
            "billing_method": "fee_for_service",
        },
        "gate_b_sources": ["C000835"],
        "encode_batch": "R6_REST",
    },
    # C000838 COVERAGE — kemik iliği/kordon kanı nakliye masrafı (Euro cap)
    {
        "rule_id": "2.4.2.B-1.(9).marrow_cord_transport_euro_caps",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "service_category": "foreign_marrow_or_cord_transport",
            "transport_amount_within_euro_caps": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "kemik iliğinin Türkiye’deki nakil merkezine getirilmesi Amerika/Avustralya "
                "için 4.500 Euro, diğer ülkeler için 2.000 Euro; kordon kanının taşıma "
                "tankıyla getirilip geri iletilmesi 5.000 Euro’yu geçmemek şartıyla "
                "fatura karşılığı Kurumca ödenir"
            ),
            "billing_method": "fee_for_service",
        },
        "gate_b_sources": ["C000838"],
        "encode_batch": "R6_REST",
    },
    # C000839 COVERAGE — yurt dışı kaynaklı tarama/test/aktivasyon/iptal/erteleme bedelleri
    {
        "rule_id": "2.4.2.B-1.(10).foreign_sourcing_activation_cancellation_fees",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "service_category_any": [
                "foreign_donor_screening",
                "donor_advanced_tests",
                "health_check_costs",
                "stem_cell_collection",
                "process_cancellation_fee",
                "postponement_fee",
                "cord_blood_storage_2y",
                "activation_fee",
            ],
            "bank_is_wmda_member": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "yurt dışından kemik iliği/kordon kanı getirtilme sürecindeki verici "
                "taraması, ileri testler, sağlık kontrolü, kök hücre toplama, işlem iptal "
                "bedeli, erteleme ücreti, kordon kanı saklama (2 yıla kadar) ve aktivasyon "
                "ücretleri Kurumca avans/havale veya kişiye ödenir"
            ),
            "billing_method": "fee_for_service",
        },
        "gate_b_sources": ["C000839"],
        "encode_batch": "R6_REST",
    },
    # C000840 COVERAGE — kemik iliği nakli (EK-2/C) ruhsatlı nakil merkezince
    {
        "rule_id": "2.4.2.B-1.(11).bone_marrow_transplant_ek2c_licensed_center",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "bone_marrow_transplant",
            "facility_is_moh_licensed_transplant_center": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "kemik iliği nakli (hematopoietik kök hücre nakli) tedavisi Bakanlıkça "
                "ruhsatlandırılmış ve çalışma izni almış nakil merkezlerince uygulanır; "
                "tedavi bedelleri EK-2/C “Kemik İliği Nakli” başlığı altındaki işlem "
                "puanları esas alınarak Kurumca karşılanır"
            ),
            "billing_method": "procedure_package",
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C000840"],
        "encode_batch": "R6_REST",
    },
    # C000842 COVERAGE — 1/5/2013 öncesi yurt dışı tarama/temin faturaları geçmişe dönük
    {
        "rule_id": "2.4.2.B-1.(12).pre_2013_foreign_marrow_screening_retroactive",
        "sut_section": "2.4.2.B-1",
        "condition": {
            "procedure_category": "foreign_marrow_screening_procurement",
            "invoice_date_before_2013_05_01": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "1/5/2013 tarihinden önceki SUT kuralları gereği karşılanamayan yurt "
                "dışındaki kemik iliği bankaları aracılığıyla yapılan kemik iliği/kordon "
                "kanı tarama ve teminine ilişkin fatura bedelleri yukarıdaki hükümler "
                "doğrultusunda Kurumca karşılanır"
            ),
            "billing_method": "fee_for_service",
        },
        "gate_b_sources": ["C000842"],
        "encode_batch": "R6_REST",
    },

    # ── §2.4.2.B-2 — Mezenkimal kök hücre nakli ──────────────────────────────
    # C000847 COVERAGE — mezenkimal kök hücre nakli (Bakanlık onayı + sağlık kurulu raporu)
    {
        "rule_id": "2.4.2.B-2.(1).mesenchymal_stem_cell_transplant_moh_approval",
        "sut_section": "2.4.2.B-2",
        "condition": {
            "procedure_category": "mesenchymal_stem_cell_transplant",
            "condition_specified_in_board_report": True,
            "moh_approval_per_patient": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "mezenkimal kök hücre nakli tedavi bedeli, durumların sağlık kurulu "
                "raporunda belirtilmesi ve raporun Sağlık Bakanlığınca her hasta için "
                "ayrı ayrı onaylanarak izin verilmesi halinde Kurumca karşılanır"
            ),
            "billing_method": "procedure_package",
        },
        "gate_b_sources": ["C000847"],
        "encode_batch": "R6_REST",
    },
    # C000849 MANDATORY — mezenkimal kök hücre üretimi 704.981 (Kök Hücre Üretim Merkezi)
    {
        "rule_id": "2.4.2.B-2.(3).mesenchymal_704_981_production_center_required",
        "sut_section": "2.4.2.B-2",
        "condition": {
            "procedure_code_any": ["704.981"],
            "production_in_moh_defined_stem_cell_center": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "“mezenkimal kök hücre nakli (üretimi dahil)” EK-2/B “704.981” kodu ile "
                "yer almakta olup bedelinin faturalandırılabilmesi için üretimin "
                "Sağlık Bakanlığınca Kök Hücre Üretim Merkezi olarak tanımlanan "
                "merkezlerde yapılmış olması şarttır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000849"],
        "encode_batch": "R6_REST",
    },
    # C000850 MUST_NOT_BILL — mezenkimal kök hücre nakli allojenik KİN ±15/90 gün içinde ayrı yok
    {
        "rule_id": "2.4.2.B-2.(4).mesenchymal_within_allo_15d_before_90d_after_bundle",
        "sut_section": "2.4.2.B-2",
        "condition": {
            "procedure_category": "mesenchymal_stem_cell_transplant",
            "applied_within_allo_15d_before_or_90d_after": True,
            "separately_billed": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "mezenkimal kök hücre nakli tedavisi kemik iliği nakil bedellerine dahil "
                "olmayıp ayrıca faturalandırılabilir; ancak allojenik kemik iliği nakli "
                "öncesi 15 gün ve/veya sonrası 90 gün içerisinde uygulandığı takdirde "
                "kemik iliği nakli bedeline dahil olup ayrıca faturalandırılmaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000850"],
        "encode_batch": "R6_REST",
    },

    # ── §2.4.3 — Aşı bedelleri ───────────────────────────────────────────────
    # C000852 COVERAGE — Genişletilmiş Bağışıklama dışı aşılar (yüksek risk + sağlık raporu)
    {
        "rule_id": "2.4.3.(A).non_eip_vaccines_high_risk_report",
        "sut_section": "2.4.3",
        "condition": {
            "vaccine_not_in_expanded_immunization_program": True,
            "patient_high_risk_category": True,
            "health_report_present": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "Bakanlık “Genişletilmiş Bağışıklama Programı” kapsamında olmayan aşı "
                "bedelleri; kronik böbrek yetmezliği, kistik fibrozis, KOAH, kanser, "
                "HIV/AIDS, splenektomi olanlar ile immünsupresif tedaviye bağlı yüksek "
                "riskli kişilerin sağlık raporuna istinaden karşılanır"
            ),
            "billing_method": "procedure_package",
        },
        "gate_b_sources": ["C000852"],
        "encode_batch": "R6_REST",
    },
    # C000855 COVERAGE — Grip aşısı (yıl/dönem bazlı, risk grupları + Eylül-Mart)
    {
        "rule_id": "2.4.3.(B).influenza_vaccine_annual_risk_groups_sep_mar",
        "sut_section": "2.4.3",
        "condition": {
            "procedure_category": "influenza_vaccine",
            "patient_in_risk_group_or_65plus_or_care_home": True,
            "prescribed_between_september_and_march": True,
            "already_administered_this_year": False,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "grip aşısı bedeli; 65 yaş ve üzeri ile yaşlı bakımevi/huzurevinde "
                "kalanlara rapor aranmaksızın; gebeliğin 2./3. trimesterindeki gebeler, "
                "kronik pulmoner/kardiyovasküler/metabolik/renal hastalığı veya immün "
                "yetmezliği olanlar ile uzun süreli asetil salisilik asit alan çocuklara "
                "sağlık raporuna dayanılarak her Eylül-Mart döneminde bir defaya mahsus "
                "karşılanır"
            ),
            "billing_method": "procedure_package",
        },
        "gate_b_sources": ["C000855"],
        "encode_batch": "R6_REST",
    },
    # C000856 COVERAGE — Pnömokok (polisakkarit) aşısı (risk grupları, 5 yılda bir)
    {
        "rule_id": "2.4.3.(C).pneumococcal_vaccine_5_year_risk_groups",
        "sut_section": "2.4.3",
        "condition": {
            "procedure_category": "pneumococcal_polysaccharide_vaccine",
            "patient_in_risk_group_or_65plus": True,
            "years_since_last_pneumococcal": {"min": 5},
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "pnömokok aşısı (polisakkarit) bedeli; aspleni/dalak disfonksiyonu/"
                "splenektomi, orak hücre, immün yetmezlik/baskılanma, kronik renal/"
                "kalp/akciğer/karaciğer/metabolik hastalık, hemoglobinopati, beyin "
                "omurilik sıvısı sızıntısı bulunan risk gruplarına sağlık raporuyla "
                "5 yılda bir, 65 yaş ve üzeri kişilere rapor aranmaksızın beş yılda bir "
                "karşılanır"
            ),
            "billing_method": "procedure_package",
        },
        "gate_b_sources": ["C000856"],
        "encode_batch": "R6_REST",
    },
    # C000857 COVERAGE — Hepatit A aşısı (seronegatif risk, yılda en fazla 2 kez)
    {
        "rule_id": "2.4.3.(D).hepatitis_a_vaccine_max_2_yearly_seronegative",
        "sut_section": "2.4.3",
        "condition": {
            "procedure_category": "hepatitis_a_vaccine",
            "patient_seronegative": True,
            "patient_has_chronic_liver_disease_or_clotting_factor_concentrate": True,
            "patient_age": {"min": 1},
            "doses_within_year": {"max": 2},
            "health_report_present": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "hepatit A aşısı bedeli; kronik karaciğer hastalığı olan veya "
                "pıhtılaşma faktörü konsantresi alan ve hepatit A seronegatif olan "
                "1 yaş üzeri çocuk/erişkinlere sağlık raporuna dayanılarak tüm "
                "hekimlerce reçete edilmesi halinde en fazla yılda iki kez karşılanır"
            ),
            "billing_method": "procedure_package",
        },
        "gate_b_sources": ["C000857"],
        "encode_batch": "R6_REST",
    },
]
