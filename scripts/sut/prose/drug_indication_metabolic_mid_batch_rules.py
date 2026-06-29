#!/usr/bin/env python3
"""Wave A1d — metabolic / mid-size §4.2 batches.

66 in-force deontic clauses encoded from
`tasks/encode_waves/A1d_metabolic_mid.csv` covering sub-sections
4.2.27 (haematology/coagulation), 4.2.15 (antiplatelet/antianginal),
4.2.8 (nutrition), 4.2.28 (lipid-lowering), 4.2.42 (fertility/gonadotropin),
4.2.2 (psychiatry) and 4.2.30 (pulmonary arterial hypertension).

Rule shape follows the established `drug_indication_prose.json` pattern:
flat condition keys (drug_names, icd10_codes/ranges, report_required,
prescriber_specialties, pay, coverage_note) plus a nested `action` block
(message_tr + enforcement) for NO_PAY exclusions.  Bare coverage
statements use ``condition: {"coverage_note": True}``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# §4.2.15  —  antiplatelet / antianginal (clopidogrel, ivabradine, ranolazine)
# ---------------------------------------------------------------------------

WAVE_BATCH_RULES: list[dict] = [

    # C005776 — coronary stent: pre-/post-stent clopidogrel report-free window
    {
        "rule_id": "4.2.15.A.coronary_stent_report_free_window",
        "sut_section": "4.2.15.A",
        "gate_b_sources": ["C005776"],
        "drug_names": [" klopidogrel", "clopidogrel", "prasugrel", "tikagrelor"],
        "report_required": False,
        "prescriber_specialties": ["kardiyoloji", "kalp damar cerrahisi"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "koroner stent öncesi kardiyoloji/KDC uzmanınca raporsuz 24 saat önceden başlanabilir; stent sonrası taburcu olunca raporsuz 4 haftalık doz",
            "message_tr": "Koroner artere stent uygulanacak hastalarda kardiyoloji veya kalp damar cerrahisi uzman hekimleri tarafından rapor aranmaksızın 24 saat öncesinden başlanabilir; stent takılan hastada taburcu olmasından itibaren rapor aranmaksızın 4 haftalık doz bu hekimler tarafından reçete edilebilir (§4.2.15.A).",
        },
    },

    # C005777 — ACS (NSTEMI/STEMI/unstable angina): report-free acute window then report ≤12 mo
    {
        "rule_id": "4.2.15.A.acs_report_free_then_12mo_report",
        "sut_section": "4.2.15.A",
        "gate_b_sources": ["C005777"],
        "drug_names": ["klopidogrel", "clopidogrel", "prasugrel", "tikagrelor"],
        "icd10_codes": ["I21", "I20.0"],
        "report_required": True,
        "report_duration_months": 12,
        "prescriber_specialties": ["kardiyoloji", "kalp damar cerrahisi", "iç hastalıkları", "acil tıp"],
        "action": {
            "enforcement": "akut koroner sendrom (ST yükselmeli/ST yükselmesiz MI, anstabil anjina): yatan/müşahede hastada kardiyoloji/KDC/iç hastalıkları/acil tıp uzmanınca raporsuz reçete; taburcu sonra ≤4 hafta raporsuz veya ≤12 ay süreli uzman raporuyla tüm hekimlerce",
            "message_tr": "Akut koroner sendrom tanısıyla yatırılan/müşahedeye alınan, EKG/troponin pozitif NSTEMI veya anstabil anjina ve STEMI hastalarında kardiyoloji, kalp damar cerrahisi, iç hastalıkları veya acil tıp uzmanlarınca rapor aranmaksızın reçete edilebilir; taburcu sonra 4 haftayı geçmemek üzere raporsuz veya bu uzmanların ≤12 ay süreli raporuyla tüm hekimlerce reçete edilebilir (§4.2.15.A).",
        },
    },

    # C005779 — bioprosthetic valve / documented CAD / PAD / ischaemic stroke: 12-mo report
    {
        "rule_id": "4.2.15.A.high_risk_vascular_12mo_report",
        "sut_section": "4.2.15.A",
        "gate_b_sources": ["C005779"],
        "drug_names": ["klopidogrel", "clopidogrel"],
        "icd10_codes": ["I25.1", "I70", "I63"],
        "report_required": True,
        "report_duration_months": 12,
        "prescriber_specialties": ["kardiyoloji", "iç hastalıkları", "nöroloji", "kalp damar cerrahisi", "acil tıp"],
        "action": {
            "enforcement": "kalp kapak biyoprotezi / anjiyografik KAH / tıkayıcı periferik arter hast. / serebral iskemik olay: ilgili uzmandan ≤12 ay süreli raporla tüm hekimlerce; ilk iki rapor (24 ay) sonrası aile hekimliği de rapor düzenleyebilir",
            "message_tr": "Kalp kapak biyoprotezi bulunan, anjiografik olarak belgelenmiş koroner arter hastalığı, tıkayıcı periferik arter hastalığı veya serebral iskemik olay (iskemik inme) saptananlarda kardiyoloji/iç hastalıkları/nöroloji/kalp damar cerrahisi/acil tıp uzmanlarından birinin ≤12 ay süreli raporuyla tüm hekimlerce reçete edilebilir; ilk iki rapor süresi (toplam 24 ay) sonunda sonraki raporlar en fazla 12 ay sürelerle aile hekimliği uzmanlarınca da düzenlenebilir (§4.2.15.A).",
        },
    },

    # C005780 — intravascular stent/graft/coil post-procedure: report-free 24h pre, 4wk post
    {
        "rule_id": "4.2.15.A.intravascular_device_report_free_window",
        "sut_section": "4.2.15.A",
        "gate_b_sources": ["C005780"],
        "drug_names": ["klopidogrel", "clopidogrel"],
        "icd10_codes": ["I70", "I63", "I65", "I66"],
        "report_required": False,
        "prescriber_specialties": [
            "kardiyoloji", "iç hastalıkları", "nöroloji",
            "kalp damar cerrahisi", "beyin cerrahi", "radyoloji",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "girişimsel periferik/serebral intravasküler stent/stentgraft/kaplı stent/cihaz (koil, trispan, onyx) sonrası: ilgili uzmanlarca raporsuz 24 saat önceden başlanır, stent takılan taburcu olunca raporsuz 4 haftalık doz",
            "message_tr": "Girişimsel periferik/serebral işlemler sonucu intrakraniyal dahil tüm intravasküler stent/stentgraft/kaplı stent veya cihaz (koil, trispan, onyx vb.) yerleştirilenlerde kardiyoloji/iç hastalıkları/nöroloji/kalp damar cerrahisi/beyin cerrahi veya girişimsel radyoloji yapan radyoloji uzmanınca rapor aranmaksızın 24 saat önceden başlanır; stent takılan hastanın taburcu olmasından itibaren rapor aranmaksızın 4 haftalık doz bu hekimlerce reçete edilir (§4.2.15.A).",
        },
    },

    # C005792 — ivabradine: chronic stable angina, BB/verapamil-diltiazem intolerant, 1-yr cardiology report
    {
        "rule_id": "4.2.15.C.ivabradine_chronic_angina_1yr_report",
        "sut_section": "4.2.15.C",
        "gate_b_sources": ["C005792"],
        "drug_names": ["ivabradin", "ivabradine"],
        "icd10_codes": ["I20.8"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["kardiyoloji"],
        "prescriber_specialties": ["kardiyoloji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "normal sinüs ritimli kronik stabil anjina pektorisli, beta blokör ve/veya verapamil-diltiazem intoleransı/kontrendikasyonu olan hastada kardiyoloji 1 yıl süreli raporu + kardiyoloji veya iç hastalıkları reçetesi",
            "message_tr": "Normal sinüs ritmi olan, kronik stabil angına pektorisli hastaların semptomatik tedavisinde beta blokör ve/veya verapamil-diltiazem intoleransı veya kontrendikasyonu olanlarda kardiyoloji uzmanınca düzenlenen 1 yıl süreli uzman raporuyla kardiyoloji veya iç hastalıkları uzmanınca reçete edilebilir (§4.2.15.C).",
        },
    },

    # C005793 — ivabradine: chronic heart failure NYHA II-IV, HR≥75, sinus rhythm, 1-yr cardiology report
    {
        "rule_id": "4.2.15.C.ivabradine_chf_hr75_1yr_report",
        "sut_section": "4.2.15.C",
        "gate_b_sources": ["C005793"],
        "drug_names": ["ivabradin", "ivabradine"],
        "icd10_codes": ["I50"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["kardiyoloji"],
        "prescriber_specialties": ["kardiyoloji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kronik kalp yetmezliği, sistolik disfonksiyon NYHA II-IV, sinüs ritminde, kalp hızı ≥75 yetişkin: kardiyoloji 1 yıl süreli raporu + kardiyoloji veya iç hastalıkları reçetesi",
            "message_tr": "Kronik kalp yetmezliği tedavisinde sistolik disfonksiyonlu NYHA II-IV, sinüs ritminde olan ve kalp hızı 75 vuru/dakika ve üzeri yetişkinlerde kardiyoloji uzmanınca düzenlenen 1 yıl süreli uzman raporuyla kardiyoloji veya iç hastalıkları uzmanlarınca reçete edilebilir (§4.2.15.C).",
        },
    },

    # C005835 — oral anticoagulants (NOAK etc.): 3-physician 1-yr report incl cardiology/neurology
    {
        "rule_id": "4.2.15.D_1.three_physician_1yr_report",
        "sut_section": "4.2.15.D-1",
        "gate_b_sources": ["C005835"],
        "drug_names": ["dabigatran", "rivaroksaban", "apiksaban", "edoksaban", "varfarin", "kumarin"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["kardiyoloji", "iç hastalıkları", "göğüs hastalıkları", "kalp damar cerrahisi", "nöroloji"],
        "prescriber_specialties": ["kardiyoloji", "iç hastalıkları", "göğüs hastalıkları", "kalp damar cerrahisi", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "tanımlı durumların olduğu; en az biri kardiyoloji veya nöroloji olmak üzere bu uzmanlıklardan ≥3 hekimin bulunduğu 1 yıl süreli sağlık kurulu raporuyla reçete edilirse ödenir; ilk iki rapor (24 ay) sonrası bu uzmanlarca veya aile hekimlerince de rapor düzenlenebilir",
            "message_tr": "Tanımlanan durumların belirtildiği; en az biri kardiyoloji veya nöroloji uzman hekimi olmak koşuluyla kardiyoloji, iç hastalıkları, göğüs hastalıkları, kalp damar cerrahisi ve nöroloji uzman hekimlerinden en az üçünün bulunduğu 1 yıl süreli sağlık kurulu raporuyla bu uzmanlarca reçete edilmesi halinde bedeli ödenir; ilk iki rapor süresi (toplam 24 ay) sonunda sonraki raporlar bu uzmanlarca ve aile hekimlerince düzenlenen rapora istinaden reçete edilebilir (§4.2.15.D-1).",
        },
    },

    # C005838 — NOAC combination (dabigatran/rivaroksaban/edoksaban/apiksaban) = no pay
    {
        "rule_id": "4.2.15.D_1.noac_combination_nopay",
        "sut_section": "4.2.15.D-1",
        "gate_b_sources": ["C005838"],
        "drug_names": ["dabigatran", "rivaroksaban", "edoksaban", "apiksaban"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: dabigatran, rivaroksaban, edoksaban ve apiksaban etken maddeli ilaçların kombine kullanımı",
            "message_tr": "Dabigatran, rivaroksaban, edoksaban ve apiksaban etken maddeli ilaçların kombine olarak kullanılması halinde bedelleri Kurumca karşılanmaz (§4.2.15.D-1).",
        },
    },

    # C005859 — antiplatelet/anticoagulant: 3-of-specialty 1-yr health board report
    {
        "rule_id": "4.2.15.D_2.three_specialty_1yr_report",
        "sut_section": "4.2.15.D-2",
        "gate_b_sources": ["C005859"],
        "drug_names": ["klopidogrel", "prasugrel", "tikagrelor"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["kardiyoloji", "iç hastalıkları", "göğüs hastalıkları", "kalp damar cerrahisi", "nöroloji"],
        "prescriber_specialties": ["kardiyoloji", "iç hastalıkları", "göğüs hastalıkları", "kalp damar cerrahisi", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "tanımlı durumların; aynı uzmanlıktan üçünün veya bu uzmanlıklardan herhangi üçünün bulunduğu 1 yıl süreli sağlık kurulu raporuyla reçete edilirse ödenir; ilk iki rapor (24 ay) sonrası aile hekimleri de rapor düzenleyebilir",
            "message_tr": "Tanımlanan durumların belirtildiği kardiyoloji, iç hastalıkları, göğüs hastalıkları, kalp damar cerrahisi uzman hekimlerinden aynı uzmanlık dalından üçünün veya bu uzmanlık dallarından herhangi üçünün bulunduğu 1 yıl süreli sağlık kurulu raporuyla bu uzmanlarca reçete edilmesi halinde bedeli ödenir; ilk iki rapor süresi (toplam 24 ay) sonunda sonraki raporlar bu uzmanlarca ve aile hekimlerince düzenlenen rapora istinaden reçete edilebilir (§4.2.15.D-2).",
        },
    },

    # C005860 — antiplatelet renewal: new report on report-period end to continue
    {
        "rule_id": "4.2.15.D_2.report_renewal_to_continue",
        "sut_section": "4.2.15.D-2",
        "gate_b_sources": ["C005860"],
        "drug_names": ["klopidogrel", "prasugrel", "tikagrelor"],
        "report_required": True,
        "action": {
            "enforcement": "rapor süresi bitiminde tedaviye devam kararı verilirse bu durumun belirtildiği yeni rapor düzenlenerek tedaviye devam",
            "message_tr": "Rapor süresinin bitiminde ilaç tedavisinin devamına karar verilmesi halinde, bu durumun belirtildiği yeni rapor düzenlenerek tedaviye devam edilebilir (§4.2.15.D-2).",
        },
    },

    # C005870 — ranolazine: chronic stable angina despite BB/verapamil-diltiazem, 2-yr cardiology report
    {
        "rule_id": "4.2.15.F.ranolazine_chronic_angina_2yr_report",
        "sut_section": "4.2.15.F",
        "gate_b_sources": ["C005870"],
        "drug_names": ["ranolazin", "ranolazine"],
        "icd10_codes": ["I20.8"],
        "report_required": True,
        "report_duration_months": 24,
        "report_specialties": ["kardiyoloji"],
        "prescriber_specialties": ["kardiyoloji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kronik stabil anjina pektorisli; beta blokör ve/veya verapamil-diltiazem'e rağmen anjinası devam eden veya intolerans/kontrendikasyonu olan: kardiyoloji 2 yıl süreli raporu + kardiyoloji veya iç hastalıkları reçetesi",
            "message_tr": "Ranolazin; kronik stabil angina pektorisli hastaların semptomatik tedavisinde beta blokör ve/veya verapamil-diltiazem tedavisine rağmen anjinası devam eden veya bu ilaçlara intoleransı ve/veya kontrendikasyonu olanlarda, kardiyoloji uzmanınca düzenlenen 2 yıl süreli uzman raporuna istinaden kardiyoloji veya iç hastalıkları uzmanınca reçete edilebilir (§4.2.15.F).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.2  —  psychiatry (antidepressants / antipsychotics / mood stabilisers)
    # -----------------------------------------------------------------

    # C003898 — tricyclic/tetracyclic/SSRI antidepressants: all physicians ≤1 yr; switch/longer use → psychiatry report
    {
        "rule_id": "4.2.2.antidepressants_1yr_all_physicians",
        "sut_section": "4.2.2",
        "gate_b_sources": ["C003898"],
        "drug_names": [
            "trisiklik antidepresan", "tetrasiklik antidepresan", "ssri",
            "seçici serotonin gerialım inhibitörü",
        ],
        "icd10_codes": ["F32", "F33"],
        "report_required": False,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "trisiklik/tetrasiklik/SSRI antidepresanlar tüm hekimlerce ≤1 yıl; gruplar arası geçiş veya >1 yıl kullanım gerektiğinde psikiyatri uzman raporuyla tüm hekimlerce",
            "message_tr": "Trisiklik, tetrasiklik ve SSRI grubu antidepresanlar tüm hekimlerce toplam 1 yıl süre ile reçete edilebilir; bu gruplar arasında ilaç değişimi gereken hallerde ve/veya bu ilaçların 1 yıldan uzun süre kullanılması gereken durumlarda psikiyatri uzmanlarınca veya psikiyatri uzmanınca düzenlenen rapora dayanılarak tüm hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.2).",
        },
    },

    # C003901 — atypical/typical antipsychotics: psychiatry report then all physicians
    {
        "rule_id": "4.2.2.antipsychotics_psychiatry_report",
        "sut_section": "4.2.2",
        "gate_b_sources": ["C003901"],
        "drug_names": [
            "klozapin", "olanzapin", "risperidon", "amisülpirid", "ketiapin",
            "ziprosidon", "aripiprazol", "zotepin", "sertindol", "brekspiprazol",
            "lurasidon", "kariprazin", "paliperidon",
        ],
        "icd10_codes": ["F20", "F29"],
        "report_required": True,
        "report_specialties": ["psikiyatri"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "klozapin/olanzapin/risperidon/amisülpirid/ketiapin/ziprosidon/aripiprazol/zotepin/sertindol/brekspiprazol/lurasidon/kariprazin/paliperidon: psikiyatri uzmanınca veya raporuyla tüm hekimlerce",
            "message_tr": "Klozapin, olanzapin, olanzapin kombinasyonları, risperidon, amisülpirid, ketiapin, ziprosidon, aripiprazol, zotepin, sertindol, brekspiprazol, lurasidon, kariprazin veya paliperidon içeren ürünlerin psikiyatri uzmanlarınca veya psikiyatri uzmanınca düzenlenecek rapora dayanılarak tüm hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.2).",
        },
    },

    # C003902 — parenteral atypical antipsychotics: psychiatry report; risperidon/aripiprazol/paliperidon depot per EK-4/F
    {
        "rule_id": "4.2.2.parenteral_atypical_antipsychotics",
        "sut_section": "4.2.2",
        "gate_b_sources": ["C003902"],
        "drug_names": [
            "atipik antipsikotik parenteral", "risperidon depo", "aripiprazol depo", "paliperidon depo",
        ],
        "icd10_codes": ["F20", "F29"],
        "report_required": True,
        "report_specialties": ["psikiyatri"],
        "action": {
            "enforcement": "yeni nesil (atipik) antipsikotik parenteraller psikiyatri uzmanı veya raporuyla tüm hekimlerce; risperidon/aripiprazol/paliperidon parenteral formları EK-4/F hükümlerine göre",
            "message_tr": "Yeni nesil (atipik) antipsikotiklerin parenteral formları psikiyatri uzmanı veya bu uzmanın düzenlediği rapora dayanılarak tüm hekimlerce reçete edilebilir; bu gruptan risperidon, aripiprazol ve paliperidonun parenteral formları EK-4/F hükümlerine göre reçete edilebilir (§4.2.2).",
        },
    },

    # C003903 — atypical-excluded (typical) antipsychotics: all physicians without restriction
    {
        "rule_id": "4.2.2.typical_antipsychotics_all_physicians",
        "sut_section": "4.2.2",
        "gate_b_sources": ["C003903"],
        "drug_names": ["tipik antipsikotik", "haloperidol", "klorpromazin"],
        "icd10_codes": ["F20", "F29"],
        "report_required": False,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "atipik dışındaki antipsikotikler tüm hekimlerce yukarıdaki kısıtlamalar olmaksızın",
            "message_tr": "Yeni nesil (atipik) antipsikotikler dışındaki antipsikotik ilaçlar tüm hekimlerce yukarıdaki kısıtlamalar olmaksızın reçete edilebilir (§4.2.2).",
        },
    },

    # C003904 — parenteral atypical antipsychotics in emergencies: single dose, ED, non-depot
    {
        "rule_id": "4.2.2.parenteral_atypical_emergency_single_dose",
        "sut_section": "4.2.2",
        "gate_b_sources": ["C003904"],
        "drug_names": ["atipik antipsikotik parenteral"],
        "icd10_codes": ["F20", "F29"],
        "report_required": False,
        "action": {
            "enforcement": "acil servislerde, uzun salınımlı/depo etkili formlar hariç, atipik antipsikotik parenteraller tek doz tüm hekimlerce",
            "message_tr": "Acil hallerde, acil servislerde, yeni nesil (atipik) antipsikotiklerin parenteral formları (uzun salınımlı/depo etkili formları hariç) klinik şartlarda tek doz olarak tüm hekimler tarafından reçete edilebilir (§4.2.2).",
        },
    },

    # C003905 — atypical antipsychotics in dementia: psychiatry/neurology/geriatrics report
    {
        "rule_id": "4.2.2.atypical_antipsychotics_dementia",
        "sut_section": "4.2.2",
        "gate_b_sources": ["C003905"],
        "drug_names": ["atipik antipsikotik"],
        "icd10_codes": ["F00", "F01", "F02", "F03"],
        "report_required": True,
        "report_specialties": ["psikiyatri", "nöroloji", "geriatri"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "demansta atipik antipsikotikler psikiyatri/nöroloji/geriatri uzmanı veya raporuyla tüm hekimlerce",
            "message_tr": "Atipik antipsikotik ilaçlar demansta; psikiyatri, nöroloji veya geriatri uzmanları tarafından veya bu hekimlerden biri tarafından düzenlenen uzman raporuna dayanılarak tüm hekimler tarafından reçete edilebilir (§4.2.2).",
        },
    },

    # C003906 — sodium valproate (incl. combinations) in bipolar disorder: psychiatry/neurology report
    {
        "rule_id": "4.2.2.valproate_bipolar_disorder",
        "sut_section": "4.2.2",
        "gate_b_sources": ["C003906"],
        "drug_names": ["sodyum valproat", "valproik asit", "valproat"],
        "icd10_codes": ["F31"],
        "report_required": True,
        "report_specialties": ["psikiyatri", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "sodyum valproat (kombinasyonları dahil) bipolar bozukluk endikasyonunda psikiyatri/nöroloji uzmanı veya raporuyla tüm hekimlerce",
            "message_tr": "Sodyum valproat (kombinasyonları dahil) bipolar bozukluk endikasyonunda psikiyatri ve nöroloji uzmanları tarafından veya bu hekimlerden birinin düzenlediği uzman raporuna dayanılarak tüm hekimlerce reçete edilebilir (§4.2.2).",
        },
    },

    # C003909 — lamotrigine in bipolar disorder: psychiatry report then all physicians
    {
        "rule_id": "4.2.2.lamotrigine_bipolar_disorder",
        "sut_section": "4.2.2",
        "gate_b_sources": ["C003909"],
        "drug_names": ["lamotrijin", "lamotrigine"],
        "icd10_codes": ["F31"],
        "report_required": True,
        "report_specialties": ["psikiyatri"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "lamotrijin bipolar bozukluk endikasyonunda psikiyatri uzmanı veya raporuyla tüm hekimlerce",
            "message_tr": "Lamotrijin bipolar bozukluk endikasyonunda psikiyatri uzmanları tarafından veya bu hekimlerce düzenlenen uzman raporuna dayanılarak tüm hekimlerce reçete edilebilir (§4.2.2).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.27  —  haematology / coagulation
    # -----------------------------------------------------------------

    # C006243 — life-threatening bleed from coumarin/NOAC: report-free 1-day inpatient/ED, ≤3-day haematology report
    {
        "rule_id": "4.2.27.A.coumarin_noac_bleed_report_free",
        "sut_section": "4.2.27.A",
        "gate_b_sources": ["C006243"],
        "drug_names": ["prothrombin complex", "pcc", "fresh frozen plasma", "ffp", "beriplex", "kanama durdurucu"],
        "report_required": True,
        "report_specialties": ["hematoloji", "iç hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kumarin/NOAK kaynaklı hayatı tehdit eden aktif kanama: INR/PT aranmadan kanama yeri belirtilerek yatan/ayaktan acilde tüm uzmanlarca raporsuz en fazla 1 günlük doz; >1 gün ise kanamanın devam ettiğini gösteren günlük dozlu ≤3 gün süreli hematoloji (yoksa dahiliye/çocuk sağlık dahil sağlık kurulu) raporu",
            "message_tr": "Kumarin türevleri ve NOAK kaynaklı hayatı tehdit eden aktif kanaması olanlarda INR/PT aranmadan kanama yeri belirtilerek yatan hastalarda acil durumlarda veya ayaktan acil müracaatta tüm uzmanlarca rapor şartı aranmaksızın en fazla bir günlük dozda reçete edilirse bedeli Kurumca karşılanır; bir günden uzun tedavide kanamanın devam ettiğini bildiren günlük dozlu en fazla üç gün süreli hematoloji uzmanı (yoksa dahiliye/çocuk sağlığı uzmanı içeren sağlık kurulu) raporuyla ödenir (§4.2.27.A).",
        },
    },

    # C006244 — acquired coagulopathy bleed (vit K deficiency/liver failure): same report-free scheme
    {
        "rule_id": "4.2.27.A.acquired_coagulopathy_bleed_report_free",
        "sut_section": "4.2.27.A",
        "gate_b_sources": ["C006244"],
        "drug_names": ["prothrombin complex", "pcc", "fresh frozen plasma", "ffp", "vitamin k", "k vitamini"],
        "report_required": True,
        "report_specialties": ["hematoloji", "iç hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kazanılmış koagülasyon bozukluğu (K vitamini yetersizliği, karaciğer yetmezliği) kanaması: kanama yeri belirtilerek acilde tüm uzmanlarca raporsuz en fazla 1 günlük doz; >1 gün ≤3 gün hematoloji (yoksa dahiliye/çocuk sağlık dahil) raporu; devamında hematoloji olan hastaneye sevk",
            "message_tr": "Kazanılmış (edinsel) koagülasyon bozukluklarında (K vitamini yetersizliği, karaciğer yetmezliği gibi) oluşan kanamalarda kanama yeri belirtilmek koşuluyla uzmanlarca yatan/acil müracaatta rapor aranmaksızın en fazla bir günlük dozda reçete edilirse bedeli Kurumca karşılanır; bir günden uzun tedavide ≤3 gün süreli hematoloji (yoksa dahiliye/çocuk sağlığı dahil) raporuyla ödenir, tedavinin devamı durumunda hematoloji uzmanı bulunan hastaneye sevk edilir (§4.2.27.A).",
        },
    },

    # C006253 — bypassing agent during ITT only for acute bleed/surgery; stop ITT after >10-day break
    {
        "rule_id": "4.2.27.A.itt_bypassing_agent_acute_only",
        "sut_section": "4.2.27.A",
        "gate_b_sources": ["C006253"],
        "drug_names": ["bypass edici ajan", "feiba", "rtpa", "rekombinan faktör viia"],
        "icd10_codes": ["D66", "D67", "D68"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "action": {
            "enforcement": "İTT esnasında akut kanama/cerrahi gereksiniminde mevcut bypass edici ajanlarla tedavi + İTT sürdürülür; İTT alanlara başka durumlarda bypass edici ajan kullanılmaz; >10 gün ara verilirse İTT'ye devam edilmez (§4.2.27 kapsamına geçilir)",
            "message_tr": "İTT tedavisi esnasında akut kanaması ve/veya cerrahi girişim gerekli olan hastalarda mevcut bypass edici ajanlar ile kanama tedavisi uygulanabilir ve aynı zamanda İTT tedavisi sürdürülür; İTT alan hastalara bu tedaviler dışında bypass edici ajanlar kullanılmaz, tedaviye 10 günden fazla ara verilirse İTT'ye devam edilmez (§4.2.27.A).",
        },
    },

    # C006261 — emicizumab prophylaxis: congenital haemophilia A <18, factor ≤1% or >3 bleeds/month
    {
        "rule_id": "4.2.27.A.emicizumab_paediatric_prophylaxis",
        "sut_section": "4.2.27.A",
        "gate_b_sources": ["C006261"],
        "drug_names": ["emicizumab", "hemlibra"],
        "icd10_codes": ["D66"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "faktör düzeyi ≤%1 ve/veya ayda >3 kanaması olan konjenital faktör VIII eksiklikli 18 yaş altı hemofili A'da rutin profilaksi",
            "message_tr": "Faktör düzeyi %1 veya altında ve/veya ayda üçten fazla kanaması olan konjenital faktör VIII eksikliği olan 18 yaş altı hemofili A hastalarının rutin profilaksi tedavisinde kullanılması halinde bedeli Kurumca karşılanır (§4.2.27.A).",
        },
    },

    # C006262 — emicizumab prophylaxis: all ages with factor VIII inhibitor >5 BU
    {
        "rule_id": "4.2.27.A.emicizumab_inhibitor_prophylaxis",
        "sut_section": "4.2.27.A",
        "gate_b_sources": ["C006262"],
        "drug_names": ["emicizumab", "hemlibra"],
        "icd10_codes": ["D66", "D68.31"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "faktör VIII'e karşı >5 BU inhibitör gelişmiş tüm yaş gruplarında konjenital hemofili A rutin profilaksi",
            "message_tr": "Faktör VIII'e karşı 5 Bethesda Ünitesi (BU) üzerinde inhibitör gelişmiş tüm yaş gruplarındaki konjenital hemofili A hastalarının rutin profilaksi tedavisinde kullanılması halinde bedeli Kurumca karşılanır (§4.2.27.A).",
        },
    },

    # C006265 — emicizumab dosing: 4-wk 3 mg/kg loading then maintenance; body weight on each Rx
    {
        "rule_id": "4.2.27.A.emicizumab_dosing_schedule",
        "sut_section": "4.2.27.A",
        "gate_b_sources": ["C006265"],
        "drug_names": ["emicizumab", "hemlibra"],
        "icd10_codes": ["D66"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "her reçetede güncel vücut ağırlığı; ilk 4 hafta haftada 1x3 mg/kg yükleme, 5. haftadan idame olarak haftada 1x1,5 mg/kg veya 2 haftada 1x3 mg/kg veya 4 haftada 1x6 mg/kg",
            "message_tr": "Her düzenlenen reçetede hastanın güncel vücut ağırlığı belirtilmelidir; emicizumab ilk 4 hafta haftada 1 kez 3 mg/kg yükleme dozuyla başlanır, 5. haftadan itibaren haftada 1 kez 1,5 mg/kg, 2 haftada 1 kez 3 mg/kg veya 4 haftada 1 kez 6 mg/kg idame dozlarında reçete edilirse bedeli Kurumca karşılanır (§4.2.27.A).",
        },
    },

    # C006269 — anti-D immunoglobulin IV in ITP: Rh+ non-splenectomy, haematology report
    {
        "rule_id": "4.2.27.B.anti_d_itp_iv_report",
        "sut_section": "4.2.27.B",
        "gate_b_sources": ["C006269"],
        "drug_names": ["anti-d immünglobulin", "rhogam", "anti-d"],
        "icd10_codes": ["D69.3"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "idiopatik (immün) trombositopenide (ITP) IV form Rh pozitif ve splenektomisiz hastalarda hematoloji uzmanınca doz ve süre belirten raporla reçete",
            "message_tr": "İdiopatik (immün) trombositopenide (ITP/primer immün trombositopeni); intravenöz formu Rh pozitif ve splenektomisiz hastalarda hematoloji uzmanınca doz ve kullanım süresi belirtilen uzman raporuna dayanılarak bu hekimlerce reçete edilebilir (§4.2.27.B).",
        },
    },

    # C006271 — recombinant factor VIIa: ≤3-day dose per haematology report
    {
        "rule_id": "4.2.27.C.factor_viia_3day_haematology_report",
        "sut_section": "4.2.27.C",
        "gate_b_sources": ["C006271"],
        "drug_names": ["rekombinan faktör viia", "rviia", "novoseven"],
        "icd10_codes": ["D66", "D67", "D68"],
        "report_required": True,
        "report_duration_months": 0,
        "report_specialties": ["hematoloji"],
        "action": {
            "enforcement": "günlük kullanım dozu ve süresini belirten hematoloji uzmanı raporuyla en fazla 3 günlük dozda reçete",
            "message_tr": "İlacın günlük kullanım dozu ve süresini belirten hematoloji uzmanınca düzenlenen uzman raporuna dayanılarak en fazla 3 günlük dozda reçete edilebilir (§4.2.27.C).",
        },
    },

    # C006272 — reuse of factor VIIa: prior dose documented in new haematology report
    {
        "rule_id": "4.2.27.C.factor_viia_reuse_documentation",
        "sut_section": "4.2.27.C",
        "gate_b_sources": ["C006272"],
        "drug_names": ["rekombinan faktör viia", "rviia", "novoseven"],
        "icd10_codes": ["D66", "D67", "D68"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "action": {
            "enforcement": "yeniden kullanımda bir önce verilen ilacın kullanıldığı ve günlük doz/süre yeni raporda kayıtlı olmalı",
            "message_tr": "Yeniden kullanımı gerektiğinde bir önce verilen ilacın kullanıldığının yeni düzenlenecek raporda belirtilmesi ve bu raporda günlük kullanım dozu ve süresinin kayıtlı olması gereklidir (§4.2.27.C).",
        },
    },

    # C006287 — eltrombopag dosing in ITP by age/platelet titration
    {
        "rule_id": "4.2.27.D.eltrombopag_dose_titration",
        "sut_section": "4.2.27.D",
        "gate_b_sources": ["C006287"],
        "drug_names": ["eltrombopag", "revolade"],
        "icd10_codes": ["D69.3", "D69.6"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "action": {
            "enforcement": "1-5 yaş başlangıç 25 mg/gün, 6-17/erişkin 50 mg/gün; 2 haftada trombosit <50.000 ise 75 mg; >150.000 ise 25 mg basamakla azaltım; 150-250 bin arası 12,5 mg/gün veya günaşırı 25 mg; her doz değişiminde trombosit sayısı raporda",
            "message_tr": "1-5 yaş başlangıç günde 25 mg, 6-17 yaş ve erişkin günde 50 mg'dır; 2 haftalık tedaviye rağmen trombosit <50.000 ise 75 mg'a çıkarılabilir, >150.000 ise 25 mg basamaklarla azaltılır; trombosit >150.000-≤250.000 iken 25 mg kullananlarda 12,5 mg/gün veya günaşırı 25 mg kullanılabilir; her doz değişikliğinde trombosit sayısı raporun açıklama bölümünde belirtilir (§4.2.27.D).",
        },
    },

    # C006293 — eltrombopag discontinuation criteria
    {
        "rule_id": "4.2.27.D.eltrombopag_discontinuation_criteria",
        "sut_section": "4.2.27.D",
        "gate_b_sources": ["C006293"],
        "drug_names": ["eltrombopag", "revolade"],
        "icd10_codes": ["D69.3", "D69.6"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "action": {
            "enforcement": "12. haftada etkin doza rağmen trombosit <20.000 ise ilaç kesilir; transfüzyonsuz ve >20.000 olanlara devam; transfüzyon bağımlılığı veya hematolojik yanıt kaybında kesilir",
            "message_tr": "Tedaviye başlandıktan sonra etkin dozu almasına rağmen 12 haftada trombosit <20.000 ise ilaç kesilir; transfüzyon ihtiyacı olmayan ve trombosit >20.000 olanlarda ilaca devam edilir; tedavi sırasında trombosit transfüzyonuna bağımlılık veya hematolojik yanıt kaybı olursa ilaç kesilir (§4.2.27.D).",
        },
    },

    # C006275 — human albumin inpatient: albumin ≤2.5 g/dl, ≤3-day dose, protocol + başhekimlik onayı
    {
        "rule_id": "4.2.27.C.albumin_inpatient_3day_report",
        "sut_section": "4.2.27.Ç",
        "gate_b_sources": ["C006275"],
        "drug_names": ["human albumin", "albumin"],
        "report_required": True,
        "report_specialties": ["iç hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yatarak tedavide temin edilemeyen; günlük doz/tedavi protokolü ve albümin ≤2.5 g/dl gösteren uzman raporuyla en fazla 3 günlük dozda 'Yatan/Günübirlik Hasta' + başhekimlik onayıyla reçete; ödenen kurum alacağından §4.1.2 kapsamında mahsup",
            "message_tr": "Yatarak tedavilerde Kurumla sözleşmeli resmi sağlık kurumunca temin edilememesi halinde, günlük doz ve tedavi protokolü ile kan albümin düzeyinin 2.5 g/dl ve altında olduğunu gösteren uzman raporuna dayanılarak en fazla 3 günlük dozda 'Yatan/Günübirlik Hasta' ibaresi ve başhekimlik onayıyla reçete düzenlenmesi kaydıyla karşılanır, ödenen tutar ilgili kurumun alacağından §4.1.2 kapsamında mahsup edilir (§4.2.27.Ç).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.28  —  lipid-lowering (statins / ezetimibe / PCSK9)
    # -----------------------------------------------------------------

    # C006316 — initial statin report: two elevated lipid panels ≥1 wk apart within 6 mo; re-check on ≥6 mo gap
    {
        "rule_id": "4.2.28.A_1.initial_report_two_lipid_panels",
        "sut_section": "4.2.28.A-1",
        "gate_b_sources": ["C006316"],
        "drug_names": ["statin", "atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "fluvastatin"],
        "icd10_codes": ["E78"],
        "report_required": True,
        "report_specialties": ["kardiyoloji", "kalp damar cerrahisi", "endokrinoloji", "iç hastalıkları", "nöroloji", "geriatri"],
        "action": {
            "enforcement": "ilk raporda son 6 ay içinde ≥1 hafta arayla iki kan lipid ölçümünün de yüksek olduğunu gösteren tetkik; rapor süresince tetkik değerlendirilmez, yenilemede lipid istenmez; ≥6 ay ara verilirse başlangıç kriterleri aranır",
            "message_tr": "Tedaviye başlamaya esas ilk uzman raporunda, rapor öncesi son 6 ay içinde (a/b/c bentleri için) en az bir hafta ara ile iki kez yapılmış kan lipid ölçümlerinin her ikisinin de yüksek olduğunu gösteren tetkik belirtilir; rapor süresince tetkikler değerlendirilmez, yenilemede lipid sonucu istenmez, ≥6 ay ara verilirse başlangıç kriterleri yeniden aranır (§4.2.28.A-1).",
        },
    },

    # C006317 — high-dose statin: specialist report, family medicine renewal after first 24 mo
    {
        "rule_id": "4.2.28.A_1.high_dose_statin_report",
        "sut_section": "4.2.28.A-1",
        "gate_b_sources": ["C006317"],
        "drug_names": [
            "rosuvastatin 20 mg ve üzeri", "atorvastatin 40 mg ve üzeri",
            "simvastatin 40 mg ve üzeri", "pravastatin 40 mg ve üzeri",
            "fluvastatin 80 mg ve üzeri",
        ],
        "icd10_codes": ["E78"],
        "report_required": True,
        "report_specialties": ["kardiyoloji", "kalp damar cerrahisi", "endokrinoloji", "geriatri", "nöroloji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "rosuvastatin ≥20 mg, atorvastatin/simvastatin/pravastatin ≥40 mg, fluvastatin ≥80 mg (kombinasyonları dahil): bu uzmanlarca düzenlenen raporla tüm hekimlerce; ilk rapor (24 ay) sonrası devam raporları aile hekimliğince de düzenlenebilir",
            "message_tr": "Rosuvastatinin 20 mg ve üzeri, atorvastatin/simvastatin/pravastatinin 40 mg ve üzeri, fluvastatinin 80 mg ve üzeri dozları (kombinasyonları dahil) kardiyoloji, kalp damar cerrahisi, endokrinoloji, geriatri, nöroloji veya iç hastalıkları uzmanlarınca düzenlenen rapora dayanılarak tüm hekimlerce reçete edilir; ilk rapor süresi (24 ay) sonunda devam raporlarının aile hekimliği uzmanlarınca da düzenlenmesi halinde bedelleri Kurumca karşılanır (§4.2.28.A-1).",
        },
    },

    # C006322 — paediatric statins: 6-mo paediatric metabolism/endocrinology/cardiology report
    {
        "rule_id": "4.2.28.A_2.paediatric_statin_6mo_report",
        "sut_section": "4.2.28.A-2",
        "gate_b_sources": ["C006322"],
        "drug_names": ["statin", "atorvastatin", "rosuvastatin", "simvastatin"],
        "icd10_codes": ["E78"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["çocuk metabolizma hastalıkları", "çocuk endokrinolojisi ve metabolizma hastalıkları", "çocuk kardiyolojisi"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "çocuklarda tanımlı koşullardan en az biri sağlanırsa çocuk metabolizma/çocuk endokrinoloji ve metabolizma/çocuk kardiyoloji uzmanınca 6 ay süreli raporla tüm hekimlerce",
            "message_tr": "Statinler; çocuklarda tanımlanan koşullardan en az birinin sağlanması durumunda çocuk metabolizma hastalıkları veya çocuk endokrinolojisi ve metabolizma hastalıkları veya çocuk kardiyolojisi uzmanınca düzenlenen 6 ay süreli uzman raporuna dayanılarak tüm hekimlerce reçete edilirse bedeli Kurumca karşılanır (§4.2.28.A-2).",
        },
    },

    # C006331 — paediatric statin LDL criteria: two measurements ≥1 wk apart within 6 mo
    {
        "rule_id": "4.2.28.A_2.paediatric_ldl_two_measurement",
        "sut_section": "4.2.28.A-2",
        "gate_b_sources": ["C006331"],
        "drug_names": ["statin", "atorvastatin", "rosuvastatin", "simvastatin"],
        "icd10_codes": ["E78"],
        "report_required": True,
        "report_specialties": ["çocuk metabolizma hastalıkları", "çocuk endokrinolojisi ve metabolizma hastalıkları", "çocuk kardiyolojisi"],
        "action": {
            "enforcement": "çocukta LDL tedavi öncesi son 6 ay içinde ≥1 hafta arayla iki ölçümde de başlangıç kriterlerini sağlamalı; devam raporlarda yeni LDL istenmez; ≥6 ay ara verilirse başlangıç kriterleri aranır",
            "message_tr": "LDL düzeyinin tedaviye başlanmadan önceki son 6 ay içinde en az bir hafta ara ile yapılmış iki ölçümde de başlama kriterlerini sağlaması ve tetkik sonuçlarının raporda belirtilmesi gerekir; devam eden raporlarda yeni LDL sonucu aranmaz, ≥6 ay ara verenlerde başlangıç kriterleri yeniden aranır (§4.2.28.A-2).",
        },
    },

    # C006340 — ezetimibe after ≥6 mo statin with LDL >100 mg/dL
    {
        "rule_id": "4.2.28.C.ezetimibe_ldl100_statin",
        "sut_section": "4.2.28.C",
        "gate_b_sources": ["C006340"],
        "drug_names": ["ezetimib", "ezetimibe"],
        "icd10_codes": ["E78"],
        "report_required": True,
        "report_specialties": ["kardiyoloji", "iç hastalıkları", "nöroloji", "kalp damar cerrahisi"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "≥6 ay statine rağmen LDL >100 mg/dL belgelenmişse; kardiyoloji/iç hastalıkları/nöroloji/kalp damar cerrahisi uzman raporuyla tüm hekimlerce",
            "message_tr": "En az 6 ay boyunca statinlerle tedavi edilmiş olmasına rağmen LDL düzeyi 100 mg/dL'nin üzerinde kalan hastalarda bu durumun belgelenmesi koşuluyla kardiyoloji, iç hastalıkları, nöroloji ya da kalp damar cerrahisi uzmanlarından birinin raporuna istinaden tüm hekimlerce reçete edilebilir (§4.2.28.C).",
        },
    },

    # C006341 — ezetimibe when statin contraindicated (AST/ALT >3xULN or CPK >2xULN)
    {
        "rule_id": "4.2.28.C.ezetimibe_statin_intolerance",
        "sut_section": "4.2.28.C",
        "gate_b_sources": ["C006341"],
        "drug_names": ["ezetimib", "ezetimibe"],
        "icd10_codes": ["E78"],
        "report_required": True,
        "report_specialties": ["kardiyoloji", "iç hastalıkları", "nöroloji", "kalp damar cerrahisi"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "AST/ALT ≥3xÜS veya CPK ≥2xÜS nedeniyle statin kullanılamadığı belgelenirse; kardiyoloji/iç hastalıkları/nöroloji/kalp damar cerrahisi uzman raporuyla tüm hekimlerce",
            "message_tr": "Karaciğer enzimlerinden (AST/SGOT veya ALT/SGPT) en az birinin normalin üst sınırının ≥3 katı üstüne çıkması veya kreatin fosfokinaz düzeylerinin ≥2 kat üzerine çıkması nedeniyle statin kullanılamadığının belgelenmesi koşuluyla kardiyoloji, iç hastalıkları, nöroloji ya da kalp damar cerrahisi uzmanlarından birinin raporuyla tüm hekimlerce reçete edilebilir (§4.2.28.C).",
        },
    },

    # C006343 — bile acid sequestrant in type-2 DM = no pay
    {
        "rule_id": "4.2.28.C.bile_acid_sequestrant_dm2_nopay",
        "sut_section": "4.2.28.C",
        "gate_b_sources": ["C006343"],
        "drug_names": ["kolesevelam", "safra asidi tutucu", "kolestiramin", "kolestipol"],
        "icd10_codes": ["E11"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: safra asidi tutucu ilaçların Tip-2 diyabetes mellitus tedavisinde kullanımı",
            "message_tr": "Safra asidi tutucu ilaçların Tip-2 diyabetes mellitus tedavisinde kullanılması halinde Kurumca bedelleri karşılanmaz (§4.2.28.C).",
        },
    },

    # C006357 — PCSK9 inhibitor: HoFH, LDL >190 despite max statin+ezetimibe; 6-mo board report
    {
        "rule_id": "4.2.28.E.pcsk9_hofh_max_statin_ezetimibe",
        "sut_section": "4.2.28.E",
        "gate_b_sources": ["C006357"],
        "drug_names": ["evolocumab", "alirocumab", "pcs k9 inhibitörü"],
        "icd10_codes": ["E78.01", "E78.0"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["kardiyoloji", "iç hastalıkları", "endokrinoloji ve metabolizma hastalıkları"],
        "prescriber_specialties": ["kardiyoloji", "iç hastalıkları", "endokrinoloji ve metabolizma hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yetişkin homozigot ailesel hiperkolesterolemi; ≥3 ay maks statin (80 mg atorvastatin/40 mg rosuvastatin)+ezetimib 10 mg rağmen LDL >190 mg/dL belgelenmişse; ≥1 uzman içeren 6 ay süreli sağlık kurulu raporuyla; 6 ay sonrası LDL ≥%30 düşerse 1 yıl süreli raporla devam; en fazla 1 hafta öncesi LDL rapor/reçete ekinde",
            "message_tr": "Diyete ek ≥3 ay maksimum statin (80 mg atorvastatin veya 40 mg rosuvastatin) ve maksimum ezetimib (10 mg) kombinasyonuna rağmen LDL >190 mg/dl olan yetişkin homozigot ailesel hiperkolesterolemide, kardiyoloji/iç hastalıkları ve/veya endokrinoloji ve metabolizma hastalıkları uzmanlarından en az birinin yer aldığı 6 ay süreli sağlık kurulu raporuyla bu uzmanlarca reçete edilirse bedeli Kurumca karşılanır; 6 ay sonra LDL başlangıca göre en az %30 düşerse 1 yıl süreli raporla devam edilir, en fazla 1 hafta öncesi LDL sonuçları ekte yer almalıdır (§4.2.28.E).",
        },
    },

    # C006348 — ezetimibe + statin combination: internal medicine / cardiology report
    {
        "rule_id": "4.2.28.C_c.ezetimibe_statin_combination",
        "sut_section": "4.2.28.Ç",
        "gate_b_sources": ["C006348"],
        "drug_names": ["ezetimib + statin", "ezetimib atorvastatin", "ezetimib rosuvastatin"],
        "icd10_codes": ["E78"],
        "report_required": True,
        "report_specialties": ["iç hastalıkları", "kardiyoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "iç hastalıkları veya kardiyoloji uzman hekim raporuyla tüm hekimlerce reçete",
            "message_tr": "İç hastalıkları veya kardiyoloji uzman hekimleri tarafından düzenlenen uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilebilir (§4.2.28.Ç).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.30  —  pulmonary arterial hypertension (PAH)
    # -----------------------------------------------------------------

    # C006405 — PAH general coverage (trailing bare clause)
    {
        "rule_id": "4.2.30.A.pah_general_coverage",
        "sut_section": "4.2.30.A",
        "gate_b_sources": ["C006405"],
        "drug_names": ["bosentan", "ambrisentan", "masitentan", "sildenafil", "tadalafil", "riociguat", "seleksipag", "iloprost", "epoprostenol", "treprostinil"],
        "icd10_codes": ["I27.0", "I27.2"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "tanımlı PAH koşullarının sağlanması halinde bedeli Kurumca karşılanır",
            "message_tr": "Pulmoner arteriyel hipertansiyon ilaçlarının tanımlı koşulların sağlanması halinde bedeli Kurumca karşılanır (§4.2.30.A).",
        },
    },

    # C006406 — PAH 3-month control: continue/escalate based on haemodynamics/PAB
    {
        "rule_id": "4.2.30.A.pah_3month_control_escalation",
        "sut_section": "4.2.30.A",
        "gate_b_sources": ["C006406"],
        "drug_names": ["bosentan", "ambrisentan", "masitentan", "sildenafil", "tadalafil", "riociguat", "seleksipag", "iloprost"],
        "icd10_codes": ["I27.0", "I27.2"],
        "report_required": True,
        "action": {
            "enforcement": "3. ay kontrolünde efor kapasitesi/hemodinami/ekokardiyografide düzelme/stabilite varsa tedaviye devam; PAB azalmaz veya fonksiyonel kapasite düzelmezse monodan ikiliye, ikiliden üçlü kombinasyona geçilir; kombineye geçilince başlangıç kriteri ve PAB azalması aranmaz",
            "message_tr": "Üç aylık tedavi sonrası kontrolde klinik efor kapasitesi (6 dakika yürüme/kardiyopulmoner egzersiz), hemodinami veya ekokardiyografik verilerde düzelme/stabilite varsa tedaviye devam edilir; üçüncü ayda PAB'da azalma olmaması veya fonksiyonel kapasite düzelmemesi halinde mono tedavide ikiliye, ikili kombinasyonda üçlüye geçilebilir; kombine tedaviye geçilince başlangıç kriterleri ve PAB azalması şartı aranmaz (§4.2.30.A).",
        },
    },

    # C006414 — selexipag: only as combination when ERA and/or PDE-5 inadequate (excl inhaled iloprost)
    {
        "rule_id": "4.2.30.A.selexipag_combination_only",
        "sut_section": "4.2.30.A",
        "gate_b_sources": ["C006414"],
        "drug_names": ["seleksipag", "selexipag", "uptravi"],
        "icd10_codes": ["I27.0", "I27.2"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "seleksipag yalnız ERA ve/veya PDE-5 inhibitörü ile tedavinin yetersiz olduğu hastalarda kombinasyon (inhaler iloprost trometamol ile birlikte kullanım hariç)",
            "message_tr": "Seleksipag yalnızca endotelin reseptör antagonisti (ERA) ve/veya fosfodiesteraz Tip 5 (PDE-5) inhibitörü ile tedavinin yetersiz olduğu hastalarda kombinasyon tedavisi şeklinde (inhaler iloprost trometamol ile birlikte kullanımı hariç) kullanılması halinde bedeli Kurumca karşılanır (§4.2.30.A).",
        },
    },

    # C006415 — bosentan/masitentan/ambrisentan (ERAs) cannot be combined = no pay
    {
        "rule_id": "4.2.30.A.era_combination_prohibited",
        "sut_section": "4.2.30.A",
        "gate_b_sources": ["C006415"],
        "drug_names": ["bosentan", "masitentan", "ambrisentan"],
        "icd10_codes": ["I27.0", "I27.2"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: bosentan, masitentan ve ambrisentan kombine kullanılamaz",
            "message_tr": "Bosentan, masitentan ve ambrisentan kombine kullanılamaz (§4.2.30.A).",
        },
    },

    # C006416 — sildenafil/riociguat/tadalafil (PDE-5/sGC) cannot be combined = no pay
    {
        "rule_id": "4.2.30.A.pde5_sgc_combination_prohibited",
        "sut_section": "4.2.30.A",
        "gate_b_sources": ["C006416"],
        "drug_names": ["sildenafil", "riociguat", "tadalafil"],
        "icd10_codes": ["I27.0", "I27.2"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: sildenafil, riociguat ve tadalafil kombine kullanılamaz",
            "message_tr": "Sildenafil, riociguat ve tadalafil kombine kullanılamaz (§4.2.30.A).",
        },
    },

    # C006418 — inhaled iloprost / epoprostenol / treprostinil / selexipag cannot be combined = no pay
    {
        "rule_id": "4.2.30.A.prostacyclin_selexipag_combination_prohibited",
        "sut_section": "4.2.30.A",
        "gate_b_sources": ["C006418"],
        "drug_names": ["iloprost trometamol", "epoprostenol", "treprostinil sodyum", "seleksipag"],
        "icd10_codes": ["I27.0", "I27.2"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: inhaler iloprost trometamol, epoprostenol, treprostinil sodyum ve seleksipag kombine kullanılamaz",
            "message_tr": "İloprost trometamol (inhaler formu), epoprostenol, treprostinil sodyum ve seleksipag kombine kullanılamaz (§4.2.30.A).",
        },
    },

    # C006420 — epoprostenol in renal dialysis = no pay
    {
        "rule_id": "4.2.30.A.epoprostenol_dialysis_nopay",
        "sut_section": "4.2.30.A",
        "gate_b_sources": ["C006420"],
        "drug_names": ["epoprostenol"],
        "icd10_codes": ["Z99.2", "N18"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: epoprostenol etken maddeli ilacın böbrek diyalizi endikasyonunda kullanımı",
            "message_tr": "Epoprostenol etken maddeli ilacın böbrek diyalizi endikasyonunda bedeli Kurumca karşılanmaz (§4.2.30.A).",
        },
    },

    # C006422 — bosentan 32 mg: paediatric <30 kg or swallowing-difficulty PAH patients
    {
        "rule_id": "4.2.30.A.bosentan_32mg_paediatric_dysphagia",
        "sut_section": "4.2.30.A",
        "gate_b_sources": ["C006422"],
        "drug_names": ["bosentan 32 mg"],
        "icd10_codes": ["I27.0", "I27.2"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "bosentan 32 mg; PAH'da koşulları sağlayan 30 kg altı pediatrik veya kilo sınırı aranmaksızın yutma güçlüğü olan (yoğun bakım/entübe/ağızdan beslenemeyen/nazogastrik) hastalarda",
            "message_tr": "Bosentan etkin maddesini 32 mg dozunda içeren ilaçlar pulmoner arteriyel hipertansiyonda yukarıdaki koşulları sağlayan 30 kg altı pediatrik hastalar veya kilo sınırı aranmaksızın yutma güçlüğü olan (yoğun bakımda/entübe/ağızdan beslenemeyen/nazogastrik beslenme zorunluluğu olan) hastalarda reçetelenirse bedeli Kurumca karşılanır (§4.2.30.A).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.42  —  fertility (OI/IUI/IVF gonadotropin)
    # -----------------------------------------------------------------

    # C006774 — OI/IUI eligibility for childless GHS woman / dependent wife
    {
        "rule_id": "4.2.42.A.oi_iui_eligibility_general",
        "sut_section": "4.2.42.A",
        "gate_b_sources": ["C006774"],
        "drug_names": ["gonadotropin", "fsh", "lh", "hmg"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "evli, evlat edinilmiş çocukları hariç çocuk sahibi olmayan GSS'li kadına veya erkeğin bakmakla yükümlü olduğu karısına uygulanan OI ve/veya IUI tedavi giderlerinin ödenebilmesi için tanımlı şartlar",
            "message_tr": "Evli olmakla birlikte evlat edinilmiş çocukları hariç çocuk sahibi olmayan genel sağlık sigortalısı kadın ise kendisine, erkek ise bakmakla yükümlü olduğu karısına uygulanan 'OI ve/veya IUI' tedavilerine ilişkin giderlerin Kurumca ödenebilmesi için tanımlı koşullar (§4.2.42.A).",
        },
    },

    # C006777 — OI/IUI conditions must be met together (trailing bare clause)
    {
        "rule_id": "4.2.42.A.oi_iui_conditions_cumulative",
        "sut_section": "4.2.42.A",
        "gate_b_sources": ["C006777"],
        "drug_names": ["gonadotropin", "fsh", "lh", "hmg"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "OI/IUI koşullarının birlikte sağlanmış olması gerekmektedir",
            "message_tr": "OI ve/veya IUI tedavilerine ilişkin ödeme koşullarının birlikte sağlanmış olması gerekmektedir (§4.2.42.A).",
        },
    },

    # C006779 — treatment must start within 6 mo of health board report
    {
        "rule_id": "4.2.42.A.treatment_within_6mo_report",
        "sut_section": "4.2.42.A",
        "gate_b_sources": ["C006779"],
        "drug_names": ["gonadotropin", "fsh", "lh", "hmg"],
        "report_required": True,
        "action": {
            "enforcement": "sağlık kurulu raporunun düzenlendiği tarihten itibaren 6 ay içinde tedaviye başlanmazsa yeniden sağlık kurulu raporu gerekir",
            "message_tr": "Sağlık kurulu raporunun düzenlendiği tarihten itibaren 6 ay içinde tedaviye başlanmaması halinde yeniden sağlık kurulu raporu düzenlenmesi gereklidir (§4.2.42.A).",
        },
    },

    # C006780 — each OI/IUI application after the first requires a new health board report
    {
        "rule_id": "4.2.42.A.repeat_application_new_report",
        "sut_section": "4.2.42.A",
        "gate_b_sources": ["C006780"],
        "drug_names": ["gonadotropin", "fsh", "lh", "hmg"],
        "report_required": True,
        "action": {
            "enforcement": "birinci uygulamadan sonraki OI ve/veya IUI tedavisi için de yeniden sağlık kurulu raporu düzenlenmesi gerekir",
            "message_tr": "Birinci uygulamadan sonraki 'OI ve/veya IUI' tedavisi için de yeniden sağlık kurulu raporu düzenlenmesi gereklidir (§4.2.42.A).",
        },
    },

    # C006783 — standard group OI/IUI: 1000 IU/cycle, total 3 cycles (3000 IU) gonadotropin
    {
        "rule_id": "4.2.42.A.standard_group_oi_iui_quota",
        "sut_section": "4.2.42.A",
        "gate_b_sources": ["C006783"],
        "drug_names": ["gonadotropin", "fsh", "lh", "hmg"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "standart hasta grubunda (açıklanamayan infertilite/erkek infertilitesi/endometriyozis) siklus başı toplam 1000 IU, toplam 3 siklus (3000 IU) gonadotropin ödenir",
            "message_tr": "Standart hasta grubunda (açıklanamayan infertilite veya erkek infertilitesi veya endometriyozis olgularında) uygulama (siklus) başına toplam 1000 IU, toplam 3 siklus (3000 IU) gonadotropin ödenir (§4.2.42.A).",
        },
    },

    # C006785 — PCOS group OI/IUI: after 3-6 clomifene cycles, total 6 applications, 10000 IU
    {
        "rule_id": "4.2.42.A.pcos_group_oi_iui_quota",
        "sut_section": "4.2.42.A",
        "gate_b_sources": ["C006785"],
        "drug_names": ["gonadotropin", "fsh", "lh", "hmg"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "PCOS; en az 3 en fazla 6 siklus klomifen sitrata yanıt alınamayanlarda toplam 6 uygulama, toplam 10000 IU gonadotropin ödenir",
            "message_tr": "Polikistik Over Sendromu (PCOS); en az 3, en fazla 6 siklus klomifen sitrat tedavisine yanıt alınamayan (ovulasyon sağlanamayan veya gebelik elde edilemeyen) hastalarda toplam 6 uygulama, toplam 10000 IU gonadotropin ödenir (§4.2.42.A).",
        },
    },

    # C006788 — hypogonadotropic hypogonadism OI/IUI: 3-6 applications, 10000 IU
    {
        "rule_id": "4.2.42.A.hypogonadotropic_oi_iui_quota",
        "sut_section": "4.2.42.A",
        "gate_b_sources": ["C006788"],
        "drug_names": ["gonadotropin", "fsh", "lh", "hmg"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "hipogonadotropik hipogonadizm; OI ve/veya IUI için en az 3 en fazla 6 uygulama, toplam 10000 IU gonadotropin (FSH+LH veya HMG) ödenir",
            "message_tr": "Hipogonadotropik hipogonadizm; hastalarda OI ve/veya IUI işlemi için en az 3 en fazla 6 uygulama, toplam 10000 IU gonadotropin (FSH + LH veya HMG) ödenir (§4.2.42.A).",
        },
    },

    # C006792 — IVF normal ovarian response: ≤3 applications, ≤3000 IU/cycle, total 9000 IU; IUI precondition
    {
        "rule_id": "4.2.42.B.ivf_normal_response_quota",
        "sut_section": "4.2.42.B",
        "gate_b_sources": ["C006792"],
        "drug_names": ["gonadotropin", "fsh", "lh", "hmg"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "normal ovaryan yanıtlı grupta en fazla 3 uygulama, siklus başı 3000 IU'ye kadar, toplam 9000 IU gonadotropin; IVF öncesi IUI işlemi yapılmış olması şartı aranır (2.4.4.İ-1-2'deki istisnalar hariç)",
            "message_tr": "Normal ovaryan yanıtlı hasta grubunda en fazla 3 uygulama, siklus başı 3000 IU'ye kadar, toplam 9000 IU gonadotropin ödenir; bu grupta IVF tedavisi öncesi IUI işlemi yapılmış olması şartı aranır (SUT '2.4.4.İ-1-2-IVF sağlık kurulu raporu' maddesinde IUI işlemi aranmayacak hastalar belirtilmiştir) (§4.2.42.B).",
        },
    },

    # C006793 — IVF poor/low ovarian response: ≤3 applications, ≤4500 IU/cycle, total 13500 IU
    {
        "rule_id": "4.2.42.B.ivf_poor_response_quota",
        "sut_section": "4.2.42.B",
        "gate_b_sources": ["C006793"],
        "drug_names": ["gonadotropin", "fsh", "lh", "hmg"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kötü ovaryan yanıtlı/düşük ovaryan rezervli grupta en fazla 3 uygulama, siklus başı 4500 IU'ye kadar, toplam 13500 IU gonadotropin; bu grupta IVF öncesi OI+IUI işlemi yapılmış olması şartı aranmaz",
            "message_tr": "Kötü ovaryan yanıtlı veya düşük ovaryan rezervli hasta grubunda en fazla 3 uygulama, siklus başı 4500 IU'ye kadar toplam 13500 IU gonadotropin ödenir; bu grupta IVF tedavisi öncesi OI+IUI işlemi yapılmış olması şartı aranmaz (§4.2.42.B).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.8  —  enteral / parenteral nutrition
    # -----------------------------------------------------------------

    # C004096 — paediatric malnutrition enteral: ≤6-mo paediatric report then renew
    {
        "rule_id": "4.2.8.A.paediatric_malnutrition_enteral_6mo_report",
        "sut_section": "4.2.8.A",
        "gate_b_sources": ["C004096"],
        "drug_names": ["enteral beslenme ürünü", "çocuk enteral beslenme"],
        "icd10_codes": ["E40", "E41", "E42", "E43", "E44", "E46"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["çocuk hastalıkları", "çocuk cerrahi", "çocuk gastroenteroloji", "çocuk nöroloji", "çocuk metabolizma", "çocuk endokrinoloji", "çocuk endokrinoloji ve metabolizma"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "malnütrisyon gelişmiş çocukta çocuk hastalıkları/çocuk cerrahi uzmanlarınca en fazla 6 ay süreli raporla başlanır; süre sonunda koşullar devam ederse çocuk gastroenteroloji/nöroloji/metabolizma/cerrahi/endokrinoloji uzmanınca en fazla 6 ay süreli raporla tüm hekimlerce",
            "message_tr": "Malnütrisyon gelişmiş çocuklarda bu durumların belirtildiği çocuk hastalıkları ve çocuk cerrahi uzmanlarınca düzenlenen en fazla 6 ay süreli raporla başlanır; bu sürenin sonunda malnütrisyon koşulları devam ederse çocuk gastroenteroloji, çocuk nöroloji, çocuk metabolizma, çocuk cerrahisi, çocuk endokrinoloji veya çocuk endokrinoloji ve metabolizma uzmanlarınca düzenlenen en fazla 6 ay süreli raporla tüm hekimlerce reçete edilirse bedeli Kurumca ödenir (§4.2.8.A).",
        },
    },

    # C004097 — malnutrition criteria waived for inborn errors, cancer, CF, Crohn, burns, tube-fed
    {
        "rule_id": "4.2.8.A.malnutrition_waived_conditions_6mo_report",
        "sut_section": "4.2.8.A",
        "gate_b_sources": ["C004097"],
        "drug_names": ["enteral beslenme ürünü"],
        "icd10_codes": ["E40", "E41", "E42", "E43", "E44", "E46", "C00", "K50"],
        "report_required": True,
        "report_duration_months": 6,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yatan, doğuştan metabolik hastalık, kanser, kistik fibrozis, crohn, yanık veya orogastrik/nazogastrik/nazoenterik sonda/gastrostomi/jejunostomi ile beslenenlerde malnütrisyon koşulları aranmaz; yatan dışında 6 ay süreli sağlık kurulu raporuyla tüm hekimlerce",
            "message_tr": "Yatan hastalarda, doğuştan metabolik hastalığı olanlarda, kanser, kistikfibrozis, crohn, yanık hastalarında veya sonda/gastrostomi/jejunostomi ile beslenenlerde malnütrisyon koşulları aranmaz; yatan hastalar dışında bu durumların belirtildiği uzman hekimlerce düzenlenen 6 ay süreli sağlık kurulu raporuyla tüm hekimlerce reçete edilirse bedeli Kurumca ödenir (§4.2.8.A).",
        },
    },

    # C004098 — enteral report fields: product name, daily kcal, weight, daily amount; ≤30-day dose
    {
        "rule_id": "4.2.8.A.enteral_report_fields_30day_dose",
        "sut_section": "4.2.8.A",
        "gate_b_sources": ["C004098"],
        "drug_names": ["enteral beslenme ürünü"],
        "icd10_codes": ["E40", "E41", "E42", "E43", "E44", "E46"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "raporda ürün adı, günlük kalori ihtiyacı, hasta vücut ağırlığı/boyu ve DSÖ referanslarına göre SD/VKİ ile belirlenen günlük kullanım miktarı açıkça belirtilerek en fazla 30 günlük dozda reçete edilirse ödenir",
            "message_tr": "Raporlarda beslenme ürününün adı, günlük kalori ihtiyacı, hastanın vücut ağırlığı, boyu ve yaşa göre ağırlık DSÖ referans değerlerine göre hesaplanan SD veya VKİ değerlerine göre belirlenen günlük kullanım miktarı açıkça belirtilerek en fazla 30 günlük dozda reçete edilirse Kurumca bedeli ödenir (§4.2.8.A).",
        },
    },

    # C004104 — adult malnutrition (excluding diet/bariatric loss): 3-mo report, ≤1200 kcal/day
    {
        "rule_id": "4.2.8.A.adult_malnutrition_1200kcal_3mo_report",
        "sut_section": "4.2.8.A",
        "gate_b_sources": ["C004104"],
        "drug_names": ["enteral beslenme ürünü"],
        "icd10_codes": ["E40", "E41", "E42", "E43", "E44", "E46"],
        "report_required": True,
        "report_duration_months": 3,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "diyetetik tedavi/obezite cerrahisi kilo kayıpları malnütrisyon sayılmaz; bu durumların belirtildiği 3 ay süreli sağlık kurulu raporuyla tüm hekimlerce günlük en fazla 1200 kcal dozda reçete edilirse ödenir",
            "message_tr": "Diyetetik tedaviler ve/veya obezite cerrahisi sonucu oluşan kilo kayıpları malnütrisyon olarak değerlendirilmez; tanımlanan malnütrisyon durumlarının belirtildiği 3 ay süreli sağlık kurulu raporuna dayanılarak tüm hekimlerce günlük en fazla 1200 kcal dozda reçete edilirse bedeli Kurumca ödenir (§4.2.8.A).",
        },
    },

    # C004105 — adult malnutrition criteria waived for inpatient/cancer/tube-fed; 6-mo report
    {
        "rule_id": "4.2.8.A.adult_malnutrition_waived_6mo_report",
        "sut_section": "4.2.8.A",
        "gate_b_sources": ["C004105"],
        "drug_names": ["enteral beslenme ürünü"],
        "icd10_codes": ["E40", "E41", "E42", "E43", "E44", "E46"],
        "report_required": True,
        "report_duration_months": 6,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yatan, kanser veya tüp ile (sonda/gastrostomi/jejunostomi/gastrojejunostomi) beslenenlerde malnütrisyon koşulları aranmaz; yatan dışında 6 ay süreli sağlık kurulu raporuyla tüm hekimlerce",
            "message_tr": "Yatan hastalar, kanser hastaları veya tüp ile beslenen hastalarda (orogastrik/nazogastrik/nazoenterik sonda veya gastrostomi/jejunostomi/gastrojejunostomi) yukarıdaki malnütrisyon koşulları aranmaz; yatan hastalar dışında bu durumların belirtildiği 6 ay süreli sağlık kurulu raporuyla tüm hekimlerce reçete edilirse bedeli Kurumca ödenir (§4.2.8.A).",
        },
    },

    # C004108 — paediatric dysphagia (>1 yr) special enteral: ≥1 specialist report, ≤2 boxes
    {
        "rule_id": "4.2.8.A.paediatric_dysphagia_special_enteral_2boxes",
        "sut_section": "4.2.8.A",
        "gate_b_sources": ["C004108"],
        "drug_names": ["özel tıbbi amaçlı beslenme ürünü", "çocuk enteral beslenme"],
        "report_required": True,
        "report_specialties": ["çocuk gastroenteroloji", "çocuk metabolizma", "çocuk endokrinolojisi ve metabolizma hastalıkları", "çocuk yoğun bakım", "çocuk sağlığı ve hastalıkları"],
        "prescriber_specialties": ["çocuk gastroenteroloji", "çocuk metabolizma", "çocuk endokrinolojisi ve metabolizma hastalıkları", "çocuk yoğun bakım", "çocuk sağlığı ve hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "1 yaş üzeri yutma/yutkunma bozukluklu çocukta bu uzmanlardan en az birinin bulunduğu sağlık kurulu raporuyla bu hekimler ve çocuk sağlığı uzmanlarınca reçete; raporda ürün adı ve günlük kullanım miktarı, en fazla iki kutu",
            "message_tr": "1 yaş üzeri yutma/yutkunma bozukluğu olan çocuklarda bu durumun belirtildiği çocuk gastroenteroloji, çocuk metabolizma, çocuk endokrinolojisi ve metabolizma hastalıkları ve çocuk yoğun bakım uzmanlarından en az birinin bulunduğu sağlık kurulu raporuna dayanılarak bu hekimler ve çocuk sağlığı ve hastalıkları uzmanlarınca reçete edilebilir; raporda ürünün adı ve günlük kullanım miktarı belirtilerek en fazla iki kutu yazılır (§4.2.8.A).",
        },
    },

    # C004109 — adult dysphagia special enteral: ≥1 specialist report, ≤2 boxes/month
    {
        "rule_id": "4.2.8.A.adult_dysphagia_special_enteral_2boxes",
        "sut_section": "4.2.8.A",
        "gate_b_sources": ["C004109"],
        "drug_names": ["özel tıbbi amaçlı beslenme ürünü", "enteral beslenme ürünü"],
        "report_required": True,
        "report_specialties": ["nöroloji", "kulak burun boğaz", "genel cerrahi", "beyin cerrahi", "anestezi ve yoğun bakım", "geriatri", "tıbbi onkoloji", "radyasyon onkolojisi"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "inme, kronik nörolojik bozukluk, baş-boyun kanseri/cerrahi rezeksiyon sonucu yutma güçlüğü çeken yetişkinlerde; bu uzmanlardan en az birinin bulunduğu sağlık kurulu raporuyla tüm uzman hekimlerce; raporda ürün adı/günlük miktar, aylık en fazla iki kutu",
            "message_tr": "İnme, kronik nörolojik bozukluklar ve baş boyun kanserleri ve cerrahi rezeksiyonda görülen yutma güçlüğü çeken yetişkin hastalarda; bu durumun belirtildiği nöroloji, kulak burun boğaz, genel cerrahi, beyin cerrahi, anestezi ve yoğun bakım, geriatri, tıbbi onkoloji, radyasyon onkolojisi uzmanlarından en az birinin bulunduğu sağlık kurulu raporuna istinaden tüm uzman hekimlerce reçete edilebilir; raporda ürünün adı ve günlük kullanım miktarı belirtilerek aylık en fazla iki kutu yazılır (§4.2.8.A).",
        },
    },

    # C004110 — BCAA-enriched enteral in hepatic encephalopathy stage ≥2, no malnutrition criteria
    {
        "rule_id": "4.2.8.A.bcaa_enriched_hepatic_encephalopathy",
        "sut_section": "4.2.8.A",
        "gate_b_sources": ["C004110"],
        "drug_names": ["dallı zincirli aminoasit", "bcaa", "dallı zincirli aminoasitlerden zengin enteral beslenme"],
        "icd10_codes": ["K72", "K70"],
        "report_required": True,
        "report_specialties": ["gastroenteroloji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "karaciğer yetmezliği olan orta/ağır (evre 2 ve üzeri) ensefalopatili hastalarda malnütrisyon kriterleri aranmaz; gastroenteroloji veya iç hastalıkları uzman raporuyla tüm hekimlerce",
            "message_tr": "Dallı zincirli aminoasitlerden zengin enteral beslenme ürünleri; karaciğer yetmezliği olan orta ve ağır (evre 2 ve üzeri) ensefalopati gelişmiş hastalarda kullanılabilir, malnütrisyon kriterleri aranmaz; gastroenteroloji veya iç hastalıkları uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilebilir (§4.2.8.A).",
        },
    },

    # C004112 — parenteral nutrition: non-inpatient oral/tube-failure, ≤30-day dose, report
    {
        "rule_id": "4.2.8.B.parenteral_nutrition_30day_report",
        "sut_section": "4.2.8.B",
        "gate_b_sources": ["C004112"],
        "drug_names": ["parenteral beslenme ürünü", "parenteral nutrition"],
        "icd10_codes": ["E43", "E44", "E46"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yatan hastalar dışında oral ve tüple beslenemeyenlere bu durumun sağlık kurulu raporunda belirtilmesi koşuluyla uzman hekimce en fazla 30 günlük dozda reçete edilirse ödenir",
            "message_tr": "Yatan hastalar dışında, oral ve tüple beslenemeyen hastalara bu durumun sağlık kurulu raporunda belirtilmesi kaydıyla uzman hekim tarafından en fazla 30 günlük dozda reçete edilmesi halinde parenteral beslenme ürünlerinin bedeli ödenir (§4.2.8.B).",
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
