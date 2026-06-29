#!/usr/bin/env python3
"""Wave A1b — rheumatology/biologics/anti-VEGF (§4.2.1.C*, §4.2.13*, §4.2.33*, §4.2.34).

63 in-force deontic clauses encoded from
`tasks/encode_waves/A1b_rheum_biologics.csv`.

Rule shape follows the established `drug_indication_prose.json` pattern:
flat condition keys (drug_names, icd10_codes/ranges, report_required,
prescriber_specialties, pay, coverage_note) plus a nested `action` block
(message_tr + enforcement) for NO_PAY exclusions.  Bare coverage
statements use ``condition: {"coverage_note": True}``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# §4.2.1.C  —  anti-TNF / biologic DMARDs (rheumatology)
# ---------------------------------------------------------------------------

WAVE_BATCH_RULES: list[dict] = [

    # C003581 — anti-TNF / biologic combination across diagnoses = no pay
    {
        "rule_id": "4.2.1.C.anti_tnf_biologic_combo_nopay",
        "sut_section": "4.2.1.C",
        "gate_b_sources": ["C003581"],
        "drug_names": [
            "anti-tnf", "infliksimab", "etanersept", "adalimumab",
            "golimumab", "sertolizumab", "rituximab", "abatacept",
            "toksilizumab", "anakinra", "kanakinumab",
        ],
        "icd10_codes": ["M05", "M06", "M45", "M46", "M07", "M08"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: two different diagnoses + two different anti-TNF or two different non-anti-TNF biologic agents prescribed together for the same patient",
            "message_tr": "Aynı hasta için iki farklı tanı ile iki farklı anti-TNF veya anti-TNF dışındaki iki farklı biyolojik ajanın birlikte kullanılması halinde bedelleri Kurumca karşılanmaz (§4.2.1.C).",
        },
    },

    # C003604 — JRA (≥18) DAS28 activity scoring; ACR paediatric carry-over
    {
        "rule_id": "4.2.1.C.juvenile_ra_das28_activity_scoring",
        "sut_section": "4.2.1.C-1",
        "gate_b_sources": ["C003604"],
        "drug_names": ["anti-tnf", "biyolojik ajan"],
        "icd10_codes": ["M08.0"],
        "report_required": True,
        "report_specialties": ["romatoloji", "fiziksel tıp ve rehabilitasyon"],
        "action": {
            "enforcement": "≥18 yaş juvenil romatoid artrit (poliartiküler) — DAS28 skorlaması esastır; <18 yaş ACR pediatrik yanıt alınanlarda DAS28 aranmaz, alevlenmede erişkin koşulları geçerli",
            "message_tr": "18 yaş ve üzerinde juvenil romatoid artritli hastalarda DAS28 skoruna göre hastalık aktivite ölçümü esastır; <18 yaş ACR pediatrik yanıt alınan mevcut tedaviye devam edilebilir, alevlenmede erişkin (DAS28) koşulları geçerlidir (§4.2.1.C-1).",
        },
    },

    # C003605 — ankylosing spondylitis / axial SpA failure criteria + 3mo/6mo report
    {
        "rule_id": "4.2.1.C.ankylosing_spondylitis_nsaids_failure_report",
        "sut_section": "4.2.1.C-1",
        "gate_b_sources": ["C003605"],
        "drug_names": ["anti-tnf", "biyolojik ajan"],
        "icd10_codes": ["M45", "M46.0", "M46.1", "M46.8", "M46.9"],
        "report_required": True,
        "report_duration_months": 3,
        "report_specialties": ["romatoloji", "fiziksel tıp ve rehabilitasyon"],
        "action": {
            "enforcement": "aksiyel SpA/AS: ≥3 NSAİİ maksimum dozda yetersiz (BASDAİ>5) + ESH>28 veya CRP↑ veya MR/sintigrafi aktif sakroilit; başlangıç 3 ay, devam 6 ay rapor",
            "message_tr": "Aksiyel tutulumlu ankilozan spondilit/non-radyografik aksiyel spondilartrit: en az 3 NSAİİ maksimum dozda yetersiz (BASDAİ>5), ESH>28 mm/s veya CRP↑ veya MR/sintigrafi ile aktif sakroilit varsa 3 ay süreli sağlık kurulu raporuyla başlanır; 3. ay değerlendirmesinde yetersiz cevap (BASDAİ'de <2 düzelme) devamında bedeli ödenmez, cevap alınırsa 6 ay süreli rapor gerekir (§4.2.1.C-1).",
        },
    },

    # C003623 — IV/SC administration setting + local continuation 12-week doses
    {
        "rule_id": "4.2.1.C.biologic_administration_setting",
        "sut_section": "4.2.1.C-1",
        "gate_b_sources": ["C003623"],
        "drug_names": ["anti-tnf", "biyolojik ajan"],
        "report_required": True,
        "report_specialties": ["fiziksel tıp ve rehabilitasyon", "iç hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "action": {
            "enforcement": "IV formlar ilgili uzman bulunan kurumda; SC ilk dozlar uzman gözetiminde; eğitim + 'Mahallinde tedavisi sürdürülebilir' ibaresi ile 12 haftalık dozlar halinde reçete",
            "message_tr": "İntravenöz formlar fiziksel tıp/iç hastalıkları/çocuk sağlığı uzmanının bulunduğu kurumda uygulanır; subkütan ilk dozlar uzman gözetiminde yapılır, enjeksiyon eğitimi ve 'Mahallinde tedavisi sürdürülebilir' rapor ibaresiyle 12 haftalık dozlar halinde reçete edilebilir (§4.2.1.C-1).",
        },
    },

    # C003624 — anti-TNF may be combined with conventional DMARDs
    {
        "rule_id": "4.2.1.C.anti_tnf_dmard_combination",
        "sut_section": "4.2.1.C-1",
        "gate_b_sources": ["C003624"],
        "drug_names": ["anti-tnf", "metotreksat", "sulfasalazin", "leflunomid"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "permission: anti-TNF ilaçlar diğer antiromatizmal ilaçlarla kombine kullanılabilir",
            "message_tr": "Anti-TNF ilaçlar diğer antiromatizmal ilaçlar ile kombine olarak da kullanılabilir (§4.2.1.C-1).",
        },
    },

    # C003657 — rituximab maintenance IV infusion schedule (500 mg at 12/18 mo, then q6mo)
    {
        "rule_id": "4.2.1.C.rituximab_maintenance_schedule",
        "sut_section": "4.2.1.C-2",
        "gate_b_sources": ["C003657"],
        "drug_names": ["rituximab", "mabthera"],
        "icd10_codes": ["M05", "M06"],
        "report_required": True,
        "report_specialties": ["romatoloji"],
        "action": {
            "enforcement": "yanıt alınan hastalarda 500 mg IV idame 12. ve 18. aylarda, sonra klinik değerlendirmeye göre 6 ayda bir",
            "message_tr": "Yanıt alınan hastalarda tedavinin devamında 500 mg IV idame infüzyonu 12. ve 18. aylarda ve daha sonra gerekirse klinik değerlendirmeye göre 6 ayda bir uygulanabilir (§4.2.1.C-2).",
        },
    },

    # C003658 — rituximab relapse re-treatment (≥16 weeks, 1000 mg)
    {
        "rule_id": "4.2.1.C.rituximab_relapse_retreatment",
        "sut_section": "4.2.1.C-2",
        "gate_b_sources": ["C003658"],
        "drug_names": ["rituximab", "mabthera"],
        "icd10_codes": ["M05", "M06"],
        "report_required": True,
        "report_specialties": ["romatoloji"],
        "action": {
            "enforcement": "nüks gelişirse en erken 16 hafta olmak kaydıyla 1000 mg rituximab",
            "message_tr": "Nüks gelişmesi durumunda hastalara 16 haftadan daha erken olmamak kaydıyla 1000 mg rituximab daha verilebilir (§4.2.1.C-2).",
        },
    },

    # C003666 — DAS28 ≥1.2 improvement → continue with new 6-month report
    {
        "rule_id": "4.2.1.C.das28_1p2_improvement_continue",
        "sut_section": "4.2.1.C-3",
        "gate_b_sources": ["C003666"],
        "drug_names": ["anti-tnf", "biyolojik ajan"],
        "icd10_codes": ["M05", "M06"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["romatoloji", "fiziksel tıp ve rehabilitasyon"],
        "action": {
            "enforcement": "rapor süresi sonunda DAS28'de toplam >1,2 puan düşme varsa yeni 6 ay süreli raporla tedaviye devam",
            "message_tr": "Raporun süresi sonunda DAS28 skorunda toplam 1,2 puandan fazla düşme olması halinde bu durumun yeni düzenlenecek 6 ay süreli sağlık kurulu raporunda belirtilmesi koşuluyla tedaviye devam edilebilir (§4.2.1.C-3).",
        },
    },

    # C003676 — psoriasis: tertiary dermatology, 1-year report
    {
        "rule_id": "4.2.1.C.4210_psoriasis_tertiary_dermatology_1yr",
        "sut_section": "4.2.1.C-4",
        "gate_b_sources": ["C003676"],
        "drug_names": ["biyolojik ajan", "anti-tnf", "ustekinumab", "sekukinumab", "ipekizumab"],
        "icd10_codes": ["L40"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["dermatoloji"],
        "prescriber_specialties": ["dermatoloji"],
        "action": {
            "enforcement": "üçüncü basamak resmi sağlık hizmeti sunucusunda dermatoloji uzman hekiminin yer aldığı 1 yıl süreli rapor + dermatoloji reçetesi",
            "message_tr": "Üçüncü basamak resmi sağlık hizmeti sunucularında dermatoloji uzman hekiminin yer aldığı 1 yıl süreli sağlık kurulu raporuna dayanılarak dermatoloji uzman hekimlerince reçete edilebilir (§4.2.1.C-4).",
        },
    },

    # C003684 — rheum/PMR coverage, ≤6-month report
    {
        "rule_id": "4.2.1.C.rheum_pmr_coverage_6mo_report",
        "sut_section": "4.2.1.C-4",
        "gate_b_sources": ["C003684"],
        "drug_names": ["anti-tnf", "biyolojik ajan"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["romatoloji", "fizik tedavi ve rehabilitasyon"],
        "prescriber_specialties": ["romatoloji", "fizik tedavi ve rehabilitasyon"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "romatoloji veya fizik tedavi/rehabilitasyon uzmanının yer aldığı en fazla 6 ay süreli raporla reçete edilirse bedeli ödenir",
            "message_tr": "Bu durumların belirtildiği romatoloji veya fizik tedavi ve rehabilitasyon uzman hekiminin yer aldığı en fazla 6 ay süreli sağlık kurulu raporuna dayanılarak ilgili uzmanlarca reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.1.C-4).",
        },
    },

    # C003694 — DAS28 ≥1.2 improvement → continue (C-5 variant)
    {
        "rule_id": "4.2.1.C.das28_1p2_improvement_continue_c5",
        "sut_section": "4.2.1.C-5",
        "gate_b_sources": ["C003694"],
        "drug_names": ["anti-tnf", "biyolojik ajan"],
        "icd10_codes": ["M05", "M06"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["romatoloji", "fiziksel tıp ve rehabilitasyon"],
        "action": {
            "enforcement": "rapor süresi sonunda DAS28'de toplam >1,2 puan düşme varsa yeni 6 ay süreli raporla tedaviye devam",
            "message_tr": "Raporun süresi sonunda DAS28 skorunda toplam 1,2 puandan fazla düşme olması halinde bu durumun yeni düzenlenecek 6 ay süreli sağlık kurulu raporunda belirtilmesi koşuluyla tedaviye devam edilebilir (§4.2.1.C-5).",
        },
    },

    # C003743 — 6-month rheum report coverage (C-6 a)
    {
        "rule_id": "4.2.1.C.rheum_6mo_report_coverage_c6",
        "sut_section": "4.2.1.C-6",
        "gate_b_sources": ["C003743"],
        "drug_names": ["anti-tnf", "biyolojik ajan", "toksilizumab", "abatacept"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["romatoloji"],
        "prescriber_specialties": ["romatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "romatoloji uzman hekiminin yer aldığı 6 ay süreli raporla romatoloji uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Bu durumların belirtildiği romatoloji uzman hekiminin yer aldığı 6'şar ay süreli sağlık kurulu raporuna dayanılarak romatoloji uzman hekimleri tarafından reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.1.C-6).",
        },
    },

    # C003747 — tertiary immunology/PMR or rheum + internal medicine prescriber
    {
        "rule_id": "4.2.1.C.tertiary_immunology_rheum_internal_coverage_c6",
        "sut_section": "4.2.1.C-6",
        "gate_b_sources": ["C003747"],
        "drug_names": ["anti-tnf", "biyolojik ajan", "toksilizumab", "abatacept"],
        "report_required": True,
        "report_specialties": ["romatoloji", "klinik immunoloji", "fiziksel tıp ve rehabilitasyon", "iç hastalıkları"],
        "prescriber_specialties": ["romatoloji", "klinik immunoloji", "fiziksel tıp ve rehabilitasyon", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "tüm romatoloji uzmanları veya üçüncü basamakta klinik immunoloji/PMR uzmanı raporuyla bu uzmanlarca veya iç hastalıkları uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Tüm romatoloji uzman hekimleri veya üçüncü basamakta klinik immunoloji/fiziksel tıp ve rehabilitasyon uzmanlarından birinin yer aldığı sağlık kurulu raporuna dayanılarak bu uzmanlarca veya iç hastalıkları uzman hekimleri tarafından reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.1.C-6).",
        },
    },

    # C003750 — same as C003747, sub-paragraph (b) variant
    {
        "rule_id": "4.2.1.C.tertiary_immunology_rheum_internal_coverage_c6_b",
        "sut_section": "4.2.1.C-6",
        "gate_b_sources": ["C003750"],
        "drug_names": ["anti-tnf", "biyolojik ajan", "toksilizumab", "abatacept"],
        "report_required": True,
        "report_specialties": ["romatoloji", "klinik immunoloji", "fiziksel tıp ve rehabilitasyon", "iç hastalıkları"],
        "prescriber_specialties": ["romatoloji", "klinik immunoloji", "fiziksel tıp ve rehabilitasyon", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "tüm romatoloji uzmanları veya üçüncü basamakta klinik immunoloji/PMR uzmanı raporuyla bu uzmanlarca veya iç hastalıkları uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Tüm romatoloji uzman hekimleri veya üçüncü basamakta klinik immunoloji/fiziksel tıp ve rehabilitasyon uzmanlarından birinin yer aldığı sağlık kurulu raporuna dayanılarak bu uzmanlarca veya iç hastalıkları uzman hekimleri tarafından reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.1.C-6).",
        },
    },

    # C003758 — 12-week response criteria to continue therapy (C-6 b)
    {
        "rule_id": "4.2.1.C.12_week_response_criteria_continue_c6",
        "sut_section": "4.2.1.C-6",
        "gate_b_sources": ["C003758"],
        "drug_names": ["anti-tnf", "biyolojik ajan"],
        "report_required": True,
        "report_specialties": ["romatoloji", "klinik immunoloji", "fiziksel tıp ve rehabilitasyon"],
        "action": {
            "enforcement": "12 haftalık kullanım sonunda tedavi başlangıcına göre tanımlı kriterlerden en az biri sağlanırsa tedaviye devam",
            "message_tr": "12 haftalık ilaç kullanım süresi sonunda tedavi başlangıcına göre belirlenen kriterlerden en az birinin sağlanması durumunda tedaviye devam edilebilir (§4.2.1.C-6).",
        },
    },

    # C003773 — paediatric ACR30/ACR50 response → continue with 3mo/6mo reports
    {
        "rule_id": "4.2.1.C.paediatric_acr30_acr50_continue_c6",
        "sut_section": "4.2.1.C-6",
        "gate_b_sources": ["C003773"],
        "drug_names": ["anti-tnf", "biyolojik ajan", "anakinra", "kanakinumab", "toksilizumab"],
        "icd10_codes": ["M08"],
        "report_required": True,
        "report_specialties": ["romatoloji", "çocuk sağlığı ve hastalıkları"],
        "action": {
            "enforcement": "3. ay ACR pediatrik 30 → 3 aylık raporla devam; rapor sonunda ACR pediatrik ≥50 → 6 aylık raporla devam",
            "message_tr": "İlaca başlandıktan 3 ay sonra ACR pediatrik 30 yanıtı alınması halinde 3 ay süreli raporla; rapor süresi sonunda ACR pediatrik ≥50 olması halinde 6 ay süreli raporla tedaviye devam edilebilir (§4.2.1.C-6).",
        },
    },

    # C003814 — pre-effective-date starters satisfying continuation conditions
    {
        "rule_id": "4.2.1.C.pre_effective_date_starter_continuation",
        "sut_section": "4.2.1.C-7",
        "gate_b_sources": ["C003814"],
        "drug_names": ["anakinra", "kanakinumab"],
        "icd10_codes": ["M04"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yürürlük öncesi başlayan hasta devam şartlarını sağlıyorsa bedeli ödenir",
            "message_tr": "Maddenin yürürlük tarihi öncesi ilaca başlamış hastaların yukarıdaki devam şartlarını sağlaması durumunda bedelleri Kurumca karşılanır (§4.2.1.C-7).",
        },
    },

    # C003818 — anakinra→kanakinumab sequencing / dose flexibility
    {
        "rule_id": "4.2.1.C.anakinra_kanakinumab_sequencing",
        "sut_section": "4.2.1.C-7",
        "gate_b_sources": ["C003818"],
        "drug_names": ["anakinra", "kanakinumab"],
        "icd10_codes": ["M04"],
        "report_required": True,
        "report_specialties": ["romatoloji", "çocuk sağlığı ve hastalıkları"],
        "action": {
            "enforcement": "anakinra 3 ay sonrası / yanıtsızlık / yan etki sonrası dokümante konsültasyonla kanakinumaba geçiş; aynı/azaltık/açılmış dozla devam",
            "message_tr": "Anakinra ile 3 aylık tedavi sonrasında veya anakinraya yanıtsız/yan etki gelişenlerde dokümante konsültasyonla kanakinumaba başlanır; yanıt alınanlarda aynı/azaltılmış/aralığı açılmış dozla tedaviye devam edilebilir (§4.2.1.C-7).",
        },
    },

    # C003820 — coverage requires MoH off-label approval for both drugs
    {
        "rule_id": "4.2.1.C.moh_offlabel_approval_coverage_c7",
        "sut_section": "4.2.1.C-7",
        "gate_b_sources": ["C003820"],
        "drug_names": ["anakinra", "kanakinumab"],
        "icd10_codes": ["M04"],
        "report_required": True,
        "action": {
            "enforcement": "koşullar sağlanırsa ve her iki ilaç için Sağlık Bakanlığı endikasyon dışı onay belgesi alınırsa bedeli ödenir",
            "message_tr": "Tedavide yukarıdaki koşulların sağlandığı durumlarda her iki ilaç için ayrıca Sağlık Bakanlığı endikasyon dışı onay belgesinin alınması halinde bedelleri Kurumca ödenir (§4.2.1.C-7).",
        },
    },

    # C003831 — anakinra no-pay with biologic DMARD / JAK inhibitor combination
    {
        "rule_id": "4.2.1.C.anakinra_biologic_jak_combo_nopay",
        "sut_section": "4.2.1.C-7",
        "gate_b_sources": ["C003831"],
        "drug_names": ["anakinra"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: anakinra biyolojik DMARD veya JAK inhibitörü ile kombine kullanılırsa bedeli ödenmez; monoterapi veya konvansiyonel/sentetik DMARD kombinasyonuna izin var",
            "message_tr": "Anakinra monoterapi veya diğer anti-inflamatuvar/konvansiyonel-sentetik DMARD'larla kombine verilebilir; biyolojik DMARD ve JAK inhibitörleri ile kombine kullanılması halinde bedeli Kurumca karşılanmaz (§4.2.1.C-7).",
        },
    },

    # C003848 — start-of-therapy coverage if ≥1 finding documented in report (C-9)
    {
        "rule_id": "4.2.1.C.start_therapy_finding_coverage_c9",
        "sut_section": "4.2.1.C-9",
        "gate_b_sources": ["C003848"],
        "drug_names": ["anti-tnf", "biyolojik ajan", "ustekinumab", "sekukinumab"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "belirli bulgulardan en az biri sağlık kurulu raporunda belirtilerek tedaviye başlanılırsa ödenir",
            "message_tr": "İlgili bulgulardan en az birinin olduğu hastalarda bu durumların sağlık kurulu raporunda belirtilerek tedaviye başlanılması halinde bedelleri Kurumca karşılanır (§4.2.1.C-9).",
        },
    },

    # C003850 — tertiary immunology/PMR + internal, 6-month report; ≥6mo break re-eligibility
    {
        "rule_id": "4.2.1.C.tertiary_immunology_6mo_internal_coverage_c9",
        "sut_section": "4.2.1.C-9",
        "gate_b_sources": ["C003850"],
        "drug_names": ["anti-tnf", "biyolojik ajan", "ustekinumab", "sekukinumab"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["romatoloji", "klinik immunoloji", "fiziksel tıp ve rehabilitasyon", "iç hastalıkları"],
        "prescriber_specialties": ["romatoloji", "klinik immunoloji", "fiziksel tıp ve rehabilitasyon", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta klinik immunoloji/PMR uzmanı raporuyla 6 ay süreli; bu uzmanlarca veya iç hastalıklarınca reçete; cevap her raporda; ≥6 ay ara verilirse başlangıç kriterleri yeniden aranır",
            "message_tr": "Tüm romatoloji uzmanları veya üçüncü basamakta klinik immunoloji/fiziksel tıp ve rehabilitasyon uzmanı raporuyla 6 ay süreli olarak bu uzmanlarca veya iç hastalıkları uzmanlarınca reçete edilirse ödenir; cevap her raporda belirtilir, 6 ay ve üzeri ara verilirse başlangıç kriterleri yeniden aranır (§4.2.1.C-9).",
        },
    },

    # C003854 — tertiary dermatology 6-month report, PASI value (C-9)
    {
        "rule_id": "4.2.1.C.psoriasis_tertiary_dermatology_6mo_pasi_c9",
        "sut_section": "4.2.1.C-9",
        "gate_b_sources": ["C003854"],
        "drug_names": ["biyolojik ajan", "ustekinumab", "sekukinumab", "ipekizumab"],
        "icd10_codes": ["L40"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["dermatoloji"],
        "prescriber_specialties": ["dermatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta dermatoloji uzmanının yer aldığı 6 ay süreli rapor + dermatoloji reçetesi; PASI her raporda; cevap her raporda belirtilir",
            "message_tr": "Üçüncü basamakta dermatoloji uzman hekiminin yer aldığı 6 ay süreli sağlık kurulu raporuna dayanılarak dermatoloji uzmanlarınca reçete edilmesi halinde bedelleri Kurumca karşılanır; raporda PASI değeri ve tedaviye yanıt her raporda belirtilir (§4.2.1.C-9).",
        },
    },

    # C003858 — rheum/PMR coverage, 6-month report (C-9)
    {
        "rule_id": "4.2.1.C.rheum_pmr_6mo_coverage_c9",
        "sut_section": "4.2.1.C-9",
        "gate_b_sources": ["C003858"],
        "drug_names": ["anti-tnf", "biyolojik ajan", "ustekinumab", "sekukinumab"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["romatoloji", "fizik tedavi ve rehabilitasyon"],
        "prescriber_specialties": ["romatoloji", "fizik tedavi ve rehabilitasyon"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "romatoloji veya fizik tedavi/rehabilitasyon uzmanının yer aldığı 6 ay süreli raporla reçete edilirse ödenir",
            "message_tr": "Romatoloji veya fizik tedavi ve rehabilitasyon uzman hekiminin yer aldığı 6 ay süreli sağlık kurulu raporuna dayanılarak ilgili uzmanlarca reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.1.C-9).",
        },
    },

    # C003863 — 3 dermatologists at tertiary center report (C-9)
    {
        "rule_id": "4.2.1.C.three_dermatologists_tertiary_report_c9",
        "sut_section": "4.2.1.C-9",
        "gate_b_sources": ["C003863"],
        "drug_names": ["biyolojik ajan", "ustekinumab", "sekukinumab", "ipekizumab"],
        "icd10_codes": ["L40"],
        "report_required": True,
        "report_specialties": ["dermatoloji"],
        "prescriber_specialties": ["dermatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta üç dermatoloji uzmanı tarafından düzenlenen sağlık kurulu raporuna istinaden dermatoloji uzmanınca reçete edilirse ödenir",
            "message_tr": "Üçüncü basamak sağlık hizmeti sunucularında üç dermatoloji uzmanı tarafından düzenlenen sağlık kurulu raporuna istinaden dermatoloji uzmanınca reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.1.C-9).",
        },
    },

    # C003869 — psoriasis: tertiary dermatology, start 4mo then 6mo, PASI (C-10)
    {
        "rule_id": "4.2.1.C.psoriasis_tertiary_dermatology_4mo_6mo_pasi_c10",
        "sut_section": "4.2.1.C-10",
        "gate_b_sources": ["C003869"],
        "drug_names": ["biyolojik ajan", "ustekinumab", "sekukinumab", "ipekizumab", "guselkumab", "risankizumab"],
        "icd10_codes": ["L40"],
        "report_required": True,
        "report_specialties": ["dermatoloji"],
        "prescriber_specialties": ["dermatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta dermatoloji uzmanı; başlangıçta 4 ay, sonra 6 ay süreli rapor; PASI ve yanıt her raporda",
            "message_tr": "Üçüncü basamak resmi sağlık hizmeti sunucularında dermatoloji uzman hekiminin yer aldığı başlangıçta 4 ay, sonrasında 6'şar ay süreli sağlık kurulu raporuyla dermatoloji uzmanlarınca reçete edilirse bedelleri Kurumca karşılanır; raporda PASI değeri ve tedaviye yanıt her raporda belirtilir (§4.2.1.C-10).",
        },
    },

    # C003874 — rheum/PMR coverage, 6-month report (C-10)
    {
        "rule_id": "4.2.1.C.rheum_pmr_6mo_coverage_c10",
        "sut_section": "4.2.1.C-10",
        "gate_b_sources": ["C003874"],
        "drug_names": ["anti-tnf", "biyolojik ajan", "ustekinumab", "sekukinumab"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["romatoloji", "fizik tedavi ve rehabilitasyon"],
        "prescriber_specialties": ["romatoloji", "fizik tedavi ve rehabilitasyon"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "romatoloji veya fizik tedavi/rehabilitasyon uzmanının yer aldığı 6 ay süreli raporla reçete edilirse ödenir",
            "message_tr": "Romatoloji veya fizik tedavi ve rehabilitasyon uzman hekiminin yer aldığı 6 ay süreli sağlık kurulu raporuna dayanılarak ilgili uzmanlarca reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.1.C-10).",
        },
    },

    # C003880 — psoriasis: tertiary dermatology, 4mo/6mo, PASI (C-11)
    {
        "rule_id": "4.2.1.C.psoriasis_tertiary_dermatology_4mo_6mo_pasi_c11",
        "sut_section": "4.2.1.C-11",
        "gate_b_sources": ["C003880"],
        "drug_names": ["biyolojik ajan", "ustekinumab", "sekukinumab", "ipekizumab", "guselkumab", "risankizumab"],
        "icd10_codes": ["L40"],
        "report_required": True,
        "report_specialties": ["dermatoloji"],
        "prescriber_specialties": ["dermatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta dermatoloji uzmanı; başlangıçta 4 ay, sonra 6 ay süreli rapor; PASI ve yanıt her raporda",
            "message_tr": "Üçüncü basamak resmi sağlık hizmeti sunucularında dermatoloji uzman hekiminin yer aldığı başlangıçta 4 ay, sonrasında 6'şar ay süreli sağlık kurulu raporuyla dermatoloji uzmanlarınca reçete edilirse bedelleri Kurumca karşılanır; raporda PASI değeri ve tedaviye yanıt her raporda belirtilir (§4.2.1.C-11).",
        },
    },

    # C003885 — psoriasis: tertiary dermatology, 4mo/6mo, PASI (C-12)
    {
        "rule_id": "4.2.1.C.psoriasis_tertiary_dermatology_4mo_6mo_pasi_c12",
        "sut_section": "4.2.1.C-12",
        "gate_b_sources": ["C003885"],
        "drug_names": ["biyolojik ajan", "ustekinumab", "sekukinumab", "ipekizumab", "guselkumab", "risankizumab"],
        "icd10_codes": ["L40"],
        "report_required": True,
        "report_specialties": ["dermatoloji"],
        "prescriber_specialties": ["dermatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta dermatoloji uzmanı; başlangıçta 4 ay, sonra 6 ay süreli rapor; PASI ve yanıt her raporda",
            "message_tr": "Üçüncü basamak resmi sağlık hizmeti sunucularında dermatoloji uzman hekiminin yer aldığı başlangıçta 4 ay, sonrasında 6'şar ay süreli sağlık kurulu raporuyla dermatoloji uzmanlarınca reçete edilirse bedelleri Kurumca karşılanır; raporda PASI değeri ve tedaviye yanıt her raporda belirtilir (§4.2.1.C-12).",
        },
    },

    # C003896 — psoriasis: tertiary dermatology, 4mo/6mo, PASI (C-14)
    {
        "rule_id": "4.2.1.C.psoriasis_tertiary_dermatology_4mo_6mo_pasi_c14",
        "sut_section": "4.2.1.C-14",
        "gate_b_sources": ["C003896"],
        "drug_names": ["biyolojik ajan", "ustekinumab", "sekukinumab", "ipekizumab", "guselkumab", "risankizumab"],
        "icd10_codes": ["L40"],
        "report_required": True,
        "report_specialties": ["dermatoloji"],
        "prescriber_specialties": ["dermatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta dermatoloji uzmanı; başlangıçta 4 ay, sonra 6 ay süreli rapor; PASI ve yanıt her raporda",
            "message_tr": "Üçüncü basamak resmi sağlık hizmeti sunucularında dermatoloji uzman hekiminin yer aldığı başlangıçta 4 ay, sonrasında 6'şar ay süreli sağlık kurulu raporuyla dermatoloji uzmanlarınca reçete edilirse bedelleri Kurumca karşılanır; raporda PASI değeri ve tedaviye yanıt her raporda belirtilir (§4.2.1.C-14).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.13  —  antivirals (hepatitis B/C)
    # -----------------------------------------------------------------

    # C004509 — acute HBV severe: antiviral until 2x HBsAg negative (4 weeks apart)
    {
        "rule_id": "4.2.13.acute_hbv_severe_antiviral_coverage",
        "sut_section": "4.2.13",
        "gate_b_sources": ["C004509"],
        "drug_names": ["entekavir", "tenofovir", "lamivudin", "telbivudin", "adefovir"],
        "icd10_codes": ["B16", "B18.0", "B18.1"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "akut HBV ciddi klinik/lab (INR≥1,5 veya PT uzamış, sarılık >4 hafta): HBsAg iki kez (4 hafta arayla) negatiflenene kadar antiviral ödenir",
            "message_tr": "Akut hepatit B'de ciddi klinik/lab bulgusu (INR≥1,5 veya PT normalin üst sınırından >4 sn uzun, sarılık >4 hafta) olanlarda HBsAg iki kez 4 hafta arayla negatiflenene kadar onaylı antiviral ilaç bedeli Kurumca karşılanır (§4.2.13).",
        },
    },

    # C004551 — pegylated interferon adult HBV (≤48 wk); ALT/HBeAg/HBV-DNA criteria
    {
        "rule_id": "4.2.13.1.pegifn_adult_hbv_criteria",
        "sut_section": "4.2.13.1",
        "gate_b_sources": ["C004551"],
        "drug_names": ["pegile interferon", "peginterferon", "pegasys", "peg intron"],
        "icd10_codes": ["B18.0", "B18.1"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları"],
        "action": {
            "enforcement": "erişkin pegile interferon: ALT>2xÜS + (HBeAg neg ve DNA≤10^7) veya (HBeAg poz ve DNA≤10^9); kronik HBV'de en fazla 48 hafta",
            "message_tr": "Erişkinde pegile interferonlar; ALT değeri normalin üst sınırının 2 katını geçen, HBeAg negatif ve HBV DNA≤10^7 olan veya HBeAg pozitif ve HBV DNA≤10^9 olan hastalarda kullanılabilir; kronik hepatit B'de en fazla 48 hafta (§4.2.13.1).",
        },
    },

    # C004552 — paediatric pegIFN 24 wk; optional 2nd 24-wk course after ≥1 year
    {
        "rule_id": "4.2.13.1.pegifn_paediatric_24wk",
        "sut_section": "4.2.13.1",
        "gate_b_sources": ["C004552"],
        "drug_names": ["pegile interferon", "peginterferon"],
        "icd10_codes": ["B18.0", "B18.1"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "action": {
            "enforcement": "çocukta pegile interferon 24 hafta; ilk 24 haftanın bitiminden ≥1 yıl sonra koşulları taşıyanlara en fazla 24 haftalık ikinci kür",
            "message_tr": "Çocuklarda pegile interferon tedavi süresi 24 haftadır; 24 haftalık tedavinin bitiminden en az 1 yıl sonra koşulları yeniden taşıyan hastalara en fazla 24 haftalık ikinci bir pegile interferon tedavisi verilebilir (§4.2.13.1).",
        },
    },

    # C004579 — lamivudine/telbivudine HBV-DNA ≥50 IU/ml at wk24 → switch oral antiviral
    {
        "rule_id": "4.2.13.1.lamivudine_telbivudine_wk24_switch",
        "sut_section": "4.2.13.1",
        "gate_b_sources": ["C004579"],
        "drug_names": ["lamivudin", "telbivudin", "tenofovir", "entekavir"],
        "icd10_codes": ["B18.0", "B18.1"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları"],
        "action": {
            "enforcement": "lamivudin/telbivudin 24. hafta HBV DNA≥50 IU/ml ise diğer antivirale geçiş; <50 IU/ml ise geçiş/ekleme yok",
            "message_tr": "Lamivudin veya telbivudin alanlarda 24. haftada HBV DNA≥50 IU/ml ise diğer antiviraller kullanılabilir; ancak 24. haftada DNA<50 IU/ml ise başka oral antivirale geçilemez veya eklenemez (§4.2.13.1).",
        },
    },

    # C004581 — TDF/TAF/entecavir: switch/combine if HBV-DNA positive at year 1
    {
        "rule_id": "4.2.13.1.tdf_taf_entecavir_year1_switch",
        "sut_section": "4.2.13.1",
        "gate_b_sources": ["C004581"],
        "drug_names": ["tenofovir", "entekavir"],
        "icd10_codes": ["B18.0", "B18.1"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları"],
        "action": {
            "enforcement": "TDF/TAF/entekavir 1. yıl sonunda HBV DNA pozitifse bu antiviraller arasında geçiş veya TDF+entekavir / TAF+entekavir kombinasyonu",
            "message_tr": "Tenofovir disoproksil fumarat/tenofovir alafenamid fumarat/entekavir ile tedavide 1. yıl sonunda HBV DNA pozitifse bu antiviraller arasında geçiş veya TDF+entekavir/TAF+entekavir birlikte kullanılabilir (§4.2.13.1).",
        },
    },

    # C004589 — paediatric lamivudine wk24 switch to TDF/TAF/entecavir
    {
        "rule_id": "4.2.13.1.paediatric_lamivudine_wk24_switch",
        "sut_section": "4.2.13.1",
        "gate_b_sources": ["C004589"],
        "drug_names": ["lamivudin", "tenofovir", "entekavir"],
        "icd10_codes": ["B18.0", "B18.1"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "action": {
            "enforcement": "çocuk lamivudin 24. hafta DNA≥50 IU/ml → yaşa göre TDF/TAF/entekavir; <50 IU/ml ise geçiş/ekleme yok",
            "message_tr": "Lamivudin alan çocuk hastalarda 24. haftada HBV DNA≥50 IU/ml ise yaş grubu gözetilerek TDF/TAF/entekavir kullanılabilir; <50 IU/ml ise başka oral antivirale geçilemez/eklenemez (§4.2.13.1).",
        },
    },

    # C004591 — paediatric TDF/TAF/entecavir year-1 switch/combination
    {
        "rule_id": "4.2.13.1.paediatric_tdf_taf_entecavir_year1_switch",
        "sut_section": "4.2.13.1",
        "gate_b_sources": ["C004591"],
        "drug_names": ["tenofovir", "entekavir"],
        "icd10_codes": ["B18.0", "B18.1"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "action": {
            "enforcement": "çocuk TDF/TAF/entekavir 1. yıl sonunda DNA pozitifse yaşa göre geçiş veya TDF+entekavir/TAF+entekavir",
            "message_tr": "Çocuklarda TDF/TAF/entekavir ile tedavide 1. yıl sonunda HBV DNA pozitifse yaş grubu gözetilerek bu antiviraller arasında geçiş veya TDF+entekavir/TAF+entekavir birlikte kullanılabilir (§4.2.13.1).",
        },
    },

    # C004616 — immunosuppressed/chemo/anti-CD: occult HBV prophylaxis up to 12 mo after
    {
        "rule_id": "4.2.13.1.2.immunosuppressed_occult_hbv_prophylaxis",
        "sut_section": "4.2.13.1.2",
        "gate_b_sources": ["C004616"],
        "drug_names": ["lamivudin", "telbivudin", "tenofovir", "entekavir"],
        "icd10_codes": ["B18.0", "B18.1", "Z21"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları", "tıbbi onkoloji"],
        "action": {
            "enforcement": "HBsAg neg + HBV DNA ve/veya anti-HBc pozitif iken immünsupresif/sitotoksik/monoklonal tedavi alanlara biyopsi/ALT/DNA aranmadan lamivudin/telbivudin/TDF/TAF/entekavir; tedavi bitiminden sonra en fazla 12 ay",
            "message_tr": "HBsAg negatifken HBV DNA ve/veya anti-HBc pozitifliği ile immünsupresif/sitotoksik/monoklonal antikor tedavisi alan hastalara ALT/biyopsi aranmadan lamivudin/telbivudin/TDF/TAF/entekavir; bu tedavilerin bitiminden sonra en fazla 12 ay boyunca antiviral kullanılabilir (§4.2.13.1.2).",
        },
    },

    # C004620 — liver transplant / anti-HBc(+) graft: oral antiviral regardless of labs
    {
        "rule_id": "4.2.13.1.3.transplant_oral_antiviral_coverage",
        "sut_section": "4.2.13.1.3",
        "gate_b_sources": ["C004620"],
        "drug_names": ["lamivudin", "telbivudin", "tenofovir", "entekavir"],
        "icd10_codes": ["B18.0", "B18.1", "Z94.4"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "genel cerrahi"],
        "action": {
            "enforcement": "HBV'ye bağlı karaciğer hastalığından transplant veya anti-HBc(+) graft alanlara biyopsi/seroloji/ALT/DNA aranmadan oral antiviral",
            "message_tr": "HBV'ye bağlı karaciğer hastalığından dolayı karaciğer transplantasyonu yapılan veya anti-HBc(+) kişiden karaciğer alan hastalara biyopsi/viral seroloji/ALT/HBV DNA bakılmaksızın oral antiviral tedavi verilebilir (§4.2.13.1.3).",
        },
    },

    # C004911 — chronic HCV: IFN+RBV or PegIFN+RBV; monotherapy IFN/PegIFN if RBV contraindicated
    {
        "rule_id": "4.2.13.3.2.B.hcv_ifn_ribavirin_combination",
        "sut_section": "4.2.13.3.2.B",
        "gate_b_sources": ["C004911"],
        "drug_names": ["interferon", "peginterferon", "ribavirin"],
        "icd10_codes": ["B17.1", "B18.2"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları"],
        "action": {
            "enforcement": "kronik HCV: IFN+RBV veya PegIFN+RBV; RBV kontrendike ise tek başına IFN/PegIFN; tek başına RBV endikasyonu yok",
            "message_tr": "Kronik hepatit C tedavisinde İnterferon+Ribavirin veya Peginterferon+Ribavirin kullanılır; Ribavirin kontrendikasyonu olanlarda tek başına İnterferon/Peginterferon kullanılabilir; tek başına Ribavirin endikasyonu yoktur (§4.2.13.3.2.B).",
        },
    },

    # C004912 — genotype 1/4 duration 48 wk; response-guided stopping/extension rules
    {
        "rule_id": "4.2.13.3.2.B.hcv_geno1_4_rgtr_duration",
        "sut_section": "4.2.13.3.2.B",
        "gate_b_sources": ["C004912"],
        "drug_names": ["interferon", "peginterferon", "ribavirin"],
        "icd10_codes": ["B17.1", "B18.2"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları"],
        "action": {
            "enforcement": "genotip 1/4 toplam 48 hafta; 12. hafta HCV RNA <2 log düşme → ≤16 hafta; 24. hafta pozitif → en geç 28. hafta kesilir; RNA sonuçları raporda",
            "message_tr": "Genotip 1 ve 4 için tedavi 48 hafta; 12. haftada HCV RNA <2 log azalanlarda ≤16 hafta, 24. haftada pozitiflik devam edenlerde en geç 28. hafta kesilir; 16. haftada 2 log azalan ve 28. haftada RNA negatif olanlarda sonuç reçete/raporda belirtilir (§4.2.13.3.2.B).",
        },
    },

    # C004913 — paediatric HCV: ribavirin 15 mg/kg/day max 1200; PegIFN if naïve
    {
        "rule_id": "4.2.13.3.2.B.paediatric_hcv_ribavirin_pegifn",
        "sut_section": "4.2.13.3.2.B",
        "gate_b_sources": ["C004913"],
        "drug_names": ["ribavirin", "peginterferon"],
        "icd10_codes": ["B17.1", "B18.2"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "enfeksiyon hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "action": {
            "enforcement": "3-18 yaş: ribavirin 15 mg/kg/gün (maks 1200 mg/gün); peginterferon daha önce interferon almamış çocuklarda",
            "message_tr": "3-18 yaş çocuklarda ribavirin 15 mg/kg/gün (maksimum 1.200 mg/gün); peginterferon daha önce interferon tedavisi almamış hastalarda uygulanabilir (§4.2.13.3.2.B).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.33  —  anti-VEGF / intravitreal (ophthalmology)
    # -----------------------------------------------------------------

    # C006528 — maintenance: monthly supply, 1mo single/3-doctor report, response each report
    {
        "rule_id": "4.2.33.maintenance_monthly_supply_report",
        "sut_section": "4.2.33",
        "gate_b_sources": ["C006528"],
        "drug_names": ["bevacizumab", "ranibizumab", "aflibersept", "brolusizumab"],
        "icd10_codes": ["H35.3", "H35.0", "H34.8"],
        "report_required": True,
        "report_duration_months": 1,
        "report_specialties": ["göz hastalıkları"],
        "prescriber_specialties": ["göz hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "idame: bevacizumab tek hekim 1 aylık, diğerleri 3 göz uzmanı 1 aylık; ayakta/günübirlik aylık temin; yanıt her raporda",
            "message_tr": "İdame tedavide deksametazon intravitreal implant ve verteporfin hariç, yükleme dozu sonrası bevacizumab için göz hastalıkları uzmanınca 1 ay süreli tek hekim raporuyla günübirlik, diğerleri için 3 göz uzmanınca 1 aylık sağlık kurulu raporuyla ayakta tedavi kapsamında ve aylık teminle ödenir; yanıt her raporda belirtilir (§4.2.33).",
        },
    },

    # C006529 — loading dose mandatory; dose number stated on e-prescription/report
    {
        "rule_id": "4.2.33.loading_dose_mandatory_numbered",
        "sut_section": "4.2.33",
        "gate_b_sources": ["C006529"],
        "drug_names": ["bevacizumab", "ranibizumab", "aflibersept", "brolusizumab"],
        "icd10_codes": ["H35.3", "H35.0", "H34.8"],
        "report_required": True,
        "report_specialties": ["göz hastalıkları"],
        "action": {
            "enforcement": "ilk başlananlarda yükleme dozlarının tamamlanması esastır; e-reçete/raporda kaçıncı doz olduğu belirtilmeli",
            "message_tr": "İlk defa tedaviye başlanan hastalarda yükleme dozlarının tamamlanması esastır; düzenlenecek elektronik reçete/tek hekim veya sağlık kurulu raporunda yükleme dozunun kaçıncı doz olduğu belirtilmelidir (§4.2.33).",
        },
    },

    # C006530 — anti-VEGF combo in same eye same time = no pay; different eye OK
    {
        "rule_id": "4.2.33.same_eye_combo_nopay",
        "sut_section": "4.2.33",
        "gate_b_sources": ["C006530"],
        "drug_names": ["bevacizumab", "ranibizumab", "aflibersept", "brolusizumab", "dek sametazon intravitreal implant"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: aynı anda aynı gözde kombine anti-VEGF kullanımı; farklı göz kullanımları kombine sayılmaz",
            "message_tr": "Bu etkin maddeleri içeren ilaçların aynı anda aynı gözde kombine olarak kullanılması halinde bedelleri Kurumca karşılanmaz; farklı göze kullanımlar kombine kullanım olarak değerlendirilmez (§4.2.33).",
        },
    },

    # C006541 — eligibility: at least one of the listed criteria must be met
    {
        "rule_id": "4.2.33.eligibility_at_least_one_criterion_a",
        "sut_section": "4.2.33",
        "gate_b_sources": ["C006541"],
        "drug_names": ["bevacizumab", "ranibizumab", "aflibersept", "brolusizumab"],
        "icd10_codes": ["H35.3", "H35.0", "H34.8"],
        "report_required": True,
        "report_specialties": ["göz hastalıkları"],
        "action": {
            "enforcement": "tanımlı koşullardan en az birinin tespit edilmiş olması gerekir",
            "message_tr": "İlgili endikasyon koşullarından herhangi birinin tespit edilmiş olması gerekmektedir (§4.2.33).",
        },
    },

    # C006545 — eligibility: at least one criterion (duplicate paragraph variant)
    {
        "rule_id": "4.2.33.eligibility_at_least_one_criterion_b",
        "sut_section": "4.2.33",
        "gate_b_sources": ["C006545"],
        "drug_names": ["bevacizumab", "ranibizumab", "aflibersept", "brolusizumab"],
        "icd10_codes": ["H35.3", "H35.0", "H34.8"],
        "report_required": True,
        "report_specialties": ["göz hastalıkları"],
        "action": {
            "enforcement": "tanımlı koşullardan en az birinin tespit edilmiş olması gerekir",
            "message_tr": "İlgili endikasyon koşullarından herhangi birinin tespit edilmiş olması gerekmektedir (§4.2.33).",
        },
    },

    # C006550 — no-pay: switch to other agent without completing loading dose
    {
        "rule_id": "4.2.33.incomplete_loading_dose_switch_nopay",
        "sut_section": "4.2.33",
        "gate_b_sources": ["C006550"],
        "drug_names": ["bevacizumab", "ranibizumab", "aflibersept", "brolusizumab"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: yükleme dozu tamamlanmadan diğer etkin maddeli ilacın kullanımı",
            "message_tr": "Yükleme dozu aranan durumlarda yükleme dozu tamamlanmaksızın diğer etkin maddeli ilacın kullanımı halinde bu ilaç bedelleri Kurumca karşılanmaz (§4.2.33).",
        },
    },

    # C006556 — dexamethasone IVT implant: ≥1 mo after anti-VEGF, ≤4/yr, ≥3 mo apart
    {
        "rule_id": "4.2.33.dexamethasone_ivt_implant_frequency",
        "sut_section": "4.2.33",
        "gate_b_sources": ["C006556"],
        "drug_names": ["dek sametazon intravitreal implant", "ozurdex"],
        "icd10_codes": ["H35.3", "H35.0", "H34.8"],
        "report_required": True,
        "report_specialties": ["göz hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "anti-VEGF sonrası en erken 1 ay sonra; yılda en fazla 4 defa; ardışık uygulamada ≥3 ay aralık; bevacizumab yükleme sonrası 3. ayda hekim uygun görürse deksametazon devam veya beva/ranibi/aflibersept idameye geçiş",
            "message_tr": "Deksametazon intravitreal implant; anti-VEGF sonrası en erken 1 ay sonra olmak kaydıyla yılda en fazla 4 defa, aynı göze ardışık uygulamada iki doz arasında ≥3 ay olmalıdır; bevacizumab yükleme dozu sonrası deksametazon yapılan hastanın 3. ay kontrolünde hekim uygun görürse aynı ilaçla devam veya yükleme dozu zorunluluğu olmaksızın beva/ranibi/aflibersept idameye geçilebilir (§4.2.33).",
        },
    },

    # C006557 — RVO+glaucoma: bevacizumab loading inadequate → ranibizumab/aflibercept
    {
        "rule_id": "4.2.33.rvo_glaucoma_ranibizumab_aflibercept",
        "sut_section": "4.2.33",
        "gate_b_sources": ["C006557"],
        "drug_names": ["ranibizumab", "aflibersept"],
        "icd10_codes": ["H34.8", "H34.9", "H40"],
        "report_required": True,
        "report_specialties": ["göz hastalıkları"],
        "action": {
            "enforcement": "retinal ven tıkanıklığı + glokomda bevacizumab yükleme sonrası yetersiz cevap raporla dokümante edilirse deksametazon implant olmadan ranibizumab/aflibersepte geçiş",
            "message_tr": "Retinal ven tıkanıklığı tanılı glokomun eşlik ettiği hastalarda bevacizumab ile yükleme dozu sonrası yetersiz cevap alınması durumunda, bu durumun raporda belirtilmesi kaydıyla deksametazon intravitreal implant kullanılmaksızın ranibizumab veya aflibercept ile tedaviye devam edilebilir (§4.2.33).",
        },
    },

    # C006578 — artificial tears: ≤7 drops/day, ophthalmology report up to 1 yr
    {
        "rule_id": "4.2.33.D.artificial_tears_drops_report",
        "sut_section": "4.2.33.D",
        "gate_b_sources": ["C006578"],
        "drug_names": ["suni gözyaşı", "yapay gözyaşı"],
        "icd10_codes": ["H16.2", "H19.3", "M35.0"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["göz hastalıkları"],
        "prescriber_specialties": ["göz hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "keratoconjunktivitis sicca: göz hastalıkları uzmanınca veya 1 yıllık uzman raporuyla günde en fazla 7 damla; aile hekimi raporsuz yılda her reçetede ayda en fazla 1 kutu",
            "message_tr": "Keratitis sicca/kerato konjunktivitis sicca tedavisinde suni gözyaşları; göz hastalıkları uzmanlarınca veya 1 yıl süreli uzman raporuyla günde en fazla 7 damlaya kadar reçete edilirse ödenir; aile hekimlerince raporsuz olarak bir yıl süreyle her reçetede ayda en fazla bir kutu olacak şekilde reçete edilirse ödenir (§4.2.33.D).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.34  —  multiple sclerosis disease-modifying therapies
    # -----------------------------------------------------------------

    # C006627 — no-pay: MS DMTs used in clinically isolated syndrome
    {
        "rule_id": "4.2.34.cis_dmt_nopay",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006627"],
        "drug_names": [
            "fampiridin", "beta interferon", "glatiramer asetat",
            "teriflunomid", "dimetil fumarat", "fingolimod", "okrelizumab",
            "kladribin", "natalizumab", "alemtuzumab",
        ],
        "icd10_codes": ["G37.0", "G35"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: listelenen etken maddelerin Klinik İzole Sendrom tedavisinde kullanımı",
            "message_tr": "Fampiridin, beta interferon, glatiramer asetat, teriflunomid, dimetil fumarat, fingolimod, okrelizumab, kladribin, natalizumab ve alemtuzumab etken maddelerini içeren ilaçların Klinik İzole Sendrom tedavisinde kullanılması halinde bedelleri Kurumca karşılanmaz (§4.2.34).",
        },
    },

    # C006628 — no-pay: combination of MS DMTs (fampridine excluded from combo ban)
    {
        "rule_id": "4.2.34.dmt_combination_nopay",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006628"],
        "drug_names": [
            "beta interferon", "glatiramer asetat", "teriflunomid",
            "dimetil fumarat", "fingolimod", "okrelizumab", "kladribin",
            "natalizumab", "alemtuzumab",
        ],
        "icd10_codes": ["G35"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: fampiridin hariç MS DMT'lerinin kombine kullanımı",
            "message_tr": "Fampiridin hariç olmak üzere beta interferon, glatiramer asetat, teriflunomid, dimetil fumarat, fingolimod, okrelizumab, kladribin, natalizumab ve alemtuzumab etken maddelerini içeren ilaçların kombine kullanılması halinde bedelleri Kurumca karşılanmaz (§4.2.34).",
        },
    },

    # C006630 — RRMS high activity after ≥1 yr of platform Tx + ≥2 features
    {
        "rule_id": "4.2.34.rrms_high_activity_after_platform_a",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006630"],
        "drug_names": ["fingolimod", "natalizumab", "kladribin", "okrelizumab", "alemtuzumab"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yüksek aktiviteli RRMS: beta-IFN/glatiramer/teriflunomid/dimetil fumarattan biri/çoğu ≥1 yıl kullanıp yanıtsız + ≥2 yüksek aktivite özelliği",
            "message_tr": "Yüksek hastalık aktivitesi gösteren relaps/remisyon MS hastalarında beta interferonlar, glatiramer asetat, teriflunomid veya dimetil fumarat tedavilerinden birini/birkaçını toplam ≥1 yıl kullanıp yanıtsız kalan ve ≥2 yüksek aktivite özelliği taşıyanlarda kullanılması halinde bedelleri Kurumca karşılanır (§4.2.34).",
        },
    },

    # C006636 — RRMS high activity after platform (duplicate paragraph variant)
    {
        "rule_id": "4.2.34.rrms_high_activity_after_platform_b",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006636"],
        "drug_names": ["fingolimod", "natalizumab", "kladribin", "okrelizumab", "alemtuzumab"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yüksek aktiviteli RRMS: platform tedavilerinden ≥1 yıl kullanıp yanıtsız + ≥2 yüksek aktivite özelliği",
            "message_tr": "Yüksek hastalık aktivitesi gösteren relaps/remisyon MS hastalarında beta interferonlar, glatiramer asetat, teriflunomid veya dimetil fumarat tedavilerinden birini/birkaçını toplam ≥1 yıl kullanıp yanıtsız kalan ve ≥2 yüksek aktivite özelliği taşıyanlarda kullanılması halinde bedelleri Kurumca karşılanır (§4.2.34).",
        },
    },

    # C006642 — RRMS high activity after platform (current-criteria wording)
    {
        "rule_id": "4.2.34.rrms_high_activity_after_platform_c",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006642"],
        "drug_names": ["fingolimod", "natalizumab", "kladribin", "okrelizumab", "alemtuzumab"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yüksek aktiviteli relapsing remitting MS: platform tedavilerinden ≥1 yıl kullanıp yanıtsız + ≥2 yüksek aktivite özelliği",
            "message_tr": "Yüksek hastalık aktivitesi gösteren relapsing remitting multipl skleroz hastalarında beta interferonlar, glatiramer asetat, teriflunomid veya dimetil fumarat tedavilerinden birini/birkaçını toplam ≥1 yıl kullanıp yanıtsız kalan ve ≥2 yüksek aktivite özelliği taşıyanlarda kullanılması halinde bedelleri Kurumca karşılanır (§4.2.34).",
        },
    },

    # C006648 — primary progressive MS: criteria + EDSS≤7, tertiary neurology ≤1yr report
    {
        "rule_id": "4.2.34.primary_progressive_ms_tertiary_neurology",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006648"],
        "drug_names": ["okrelizumab"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "EDSS≤7 primer progresif MS, güncel MS kriterleri; üçüncü basamak nöroloji uzmanı ≤1 yıl rapor + nöroloji reçetesi",
            "message_tr": "Güncel MS tanı kriterlerini karşılayan ve EDSS 7 ve altında olan primer progresif MS hastalarında, üçüncü basamak sağlık hizmeti sunucusunda nöroloji uzmanınca düzenlenen en fazla 1 yıl süreli rapor ve nöroloji reçetesiyle bedelleri Kurumca karşılanır (§4.2.34).",
        },
    },

    # C006658 — RRMS high activity: EDSS≤5.5, ≥2 high-activity features (frontline escalation)
    {
        "rule_id": "4.2.34.rrms_edss5p5_high_activity",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006658"],
        "drug_names": ["fingolimod", "natalizumab", "kladribin", "okrelizumab", "alemtuzumab"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "EDSS≤5.5 RRMS + ≥2 yüksek aktivite özelliği",
            "message_tr": "EDSS 5,5 ve altında olan relaps ve remisyonla seyreden MS hastalarında, aşağıda belirtilen yüksek hastalık aktivitesi özelliklerinden en az ikisini taşıyanlarda kullanılması halinde bedelleri Kurumca karşılanır (§4.2.34).",
        },
    },

    # C006662 — RRMS EDSS≤7 high activity after platform ≥1 yr
    {
        "rule_id": "4.2.34.rrms_edss7_high_activity_after_platform",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006662"],
        "drug_names": ["fingolimod", "natalizumab", "kladribin", "okrelizumab", "alemtuzumab"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "EDSS≤7 RRMS: platform tedavilerinden ≥1 yıl kullanıp yanıtsız + ≥2 yüksek aktivite özelliği",
            "message_tr": "EDSS 7 ve altında, relaps ve remisyonla seyreden MS hastalarında beta interferonlar, glatiramer asetat, teriflunomid veya dimetil fumarat tedavilerinden birini/birkaçını toplam ≥1 yıl kullanıp yanıtsız kalan ve ≥2 yüksek aktivite özelliği taşıyanlarda kullanılması halinde bedelleri Kurumca karşılanır (§4.2.34).",
        },
    },

    # C006666 — tertiary neurology ≤1 yr report + neurology prescription
    {
        "rule_id": "4.2.34.tertiary_neurology_1yr_report_prescription",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006666"],
        "drug_names": ["fingolimod", "natalizumab", "kladribin", "okrelizumab", "alemtuzumab"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta nöroloji uzmanınca ≤1 yıl süreli rapor + nöroloji reçetesi",
            "message_tr": "Üçüncü basamak sağlık hizmeti sunucularında nöroloji uzman hekimi tarafından düzenlenen en fazla 1 yıl süreli raporda bu durumun belirtilmesi ve nöroloji uzman hekimleri tarafından reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.34).",
        },
    },

    # C006668 — cladribine: after 2 courses within 4 yr, additional course needs off-label approval
    {
        "rule_id": "4.2.34.cladribine_extra_course_offlabel_approval",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006668"],
        "drug_names": ["kladribin", "cladribine", "mavenclad"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kladribin başlangıcından itibaren 4 yıl içinde 2 kür sonrası ilave her kür için Sağlık Bakanlığı hasta bazlı endikasyon dışı onayı gerekir",
            "message_tr": "Kladribin tedavisi başlanmasından itibaren 4 yıllık süre içinde 2 kür tamamlanmasını takiben hekim tarafından gerekli görülmesi halinde ilave edilecek her bir kür kladribin için Sağlık Bakanlığından alınacak endikasyon dışı ilaç kullanım onayıyla bedeli Kurumca karşılanır (§4.2.34).",
        },
    },

    # C006672 — RRMS high activity after ≥1 yr of fingolimod/natalizumab/cladribin/ocrelizumab
    {
        "rule_id": "4.2.34.rrms_high_activity_after_advanced_dmt",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006672"],
        "drug_names": ["alemtuzumab", "lemtrada", "okrelizumab"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yüksek aktiviteli RRMS: fingolimod/natalizumab/kladribin/okrelizumab'tan biri/çoğu ≥1 yıl kullanıp yanıtsız + ≥2 yüksek aktivite özelliği",
            "message_tr": "Yüksek hastalık aktivitesi gösteren relaps/remisyon MS hastalarında fingolimod, natalizumab, kladribin veya okrelizumab tedavilerinden birini/birkaçını toplam ≥1 yıl kullanıp yanıtsız kalan ve ≥2 yüksek aktivite özelliği taşıyanlarda kullanılması halinde bedelleri Kurumca karşılanır (§4.2.34).",
        },
    },

    # C006679 — EDSS≥4 (SPMS): tertiary neurology ≤1 yr report + neurology Rx
    {
        "rule_id": "4.2.34.spms_edss4_tertiary_neurology_report",
        "sut_section": "4.2.34",
        "gate_b_sources": ["C006679"],
        "drug_names": ["siponimod", "okrelizumab"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "güncel MS kriterleri + EDSS≥4; üçüncü basamak nöroloji uzmanınca ≤1 yıl süreli rapor + nöroloji reçetesi",
            "message_tr": "Güncel MS tanı kriterlerini karşılayan EDSS 4 ve üzeri olan hastalarda, üçüncü basamak sağlık hizmeti sunucusunda nöroloji uzmanınca düzenlenen en fazla 1 yıl süreli raporda bu durumun belirtilmesi koşuluyla nöroloji uzmanlarınca reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.34).",
        },
    },
]


def all_gate_b_sources() -> list[str]:
    """Union of every gate_b_sources clause id in the batch (sorted)."""
    ids: set[str] = set()
    for rule in WAVE_BATCH_RULES:
        ids.update(str(c) for c in (rule.get("gate_b_sources") or []))
    return sorted(ids)


if __name__ == "__main__":
    sources = all_gate_b_sources()
    print(f"WAVE_BATCH_RULES: {len(WAVE_BATCH_RULES)} rules, "
          f"{len(sources)} distinct gate_b_sources")
