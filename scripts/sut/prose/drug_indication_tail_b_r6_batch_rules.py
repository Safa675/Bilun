#!/usr/bin/env python3
"""Wave REM_4_2_tail_b — §4.2 long-tail sub-sections (second half):
§4.2.55, §4.2.56, §4.2.58-4.2.66, §4.2.67-4.2.69, §4.2.71-4.2.75.

28 in-force deontic clauses encoded from
`tasks/encode_waves/REM_4_2_tail_b.csv` (second half of the §4.2 long-tail wave).

Rule shape follows the established `drug_indication_rheum_biologics_batch_rules`
pattern: flat condition keys (drug_names, icd10_codes/ranges, report_required,
report_duration_months, report_specialties, prescriber_specialties, pay) plus a
nested `action` block (message_tr + enforcement) for NO_PAY/PROHIBITED
exclusions.  Bare coverage statements use ``condition: {"coverage_note": True}``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# §4.2.55  —  sodium fluoride (cochlear / non-surgical otosclerosis)
# ---------------------------------------------------------------------------

BATCH_RULES: list[dict] = [

    # C007077 — koklear otoskleroz / cerrahiye uygun olmayan otoskleroz: üçüncü basamak KBB raporuyla ödenir
    {
        "rule_id": "4.2.55.ent.otosclerosis_cochlear_kbb_coverage",
        "sut_section": "4.2.55",
        "gate_b_sources": ["C007077"],
        "drug_names": ["sodyum florür", "sodyum florür + kalsiyum + etidronat"],
        "icd10_codes": ["H80.0", "H80.1", "H80.2", "H80.8", "H80.9"],
        "report_required": True,
        "report_specialties": ["kulak burun boğaz"],
        "prescriber_specialties": ["kulak burun boğaz"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "koklear otoskleroz veya erken tanı almış/cerrahi tedavi için uygun olmayan diğer otoskleroz: üçüncü basamakta kulak burun boğaz uzmanının raporuyla kulak burun boğaz uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Koklear otoskleroz veya erken tanı almış ve cerrahi tedavi için uygun olmayan diğer otoskleroz hastalarında üçüncü basamak resmi sağlık hizmet sunucularında kulak burun boğaz uzman hekimi tarafından düzenlenen uzman hekim raporuna dayanılarak kulak burun boğaz uzman hekimlerince reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.55).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.56  —  sapropterin (classical PKU, ≥8 yr, diet/medical-food failure)
    # -----------------------------------------------------------------

    # C007079 — klasik fenilketonüri (≥8 yaş, diyete uyumsuz/tıbbi mama kullanamayan): çocuk metabolizma/endokrin raporuyla ödenir
    {
        "rule_id": "4.2.56.meta.classic_pku_sapropterin_metabolic_coverage",
        "sut_section": "4.2.56",
        "gate_b_sources": ["C007079"],
        "drug_names": ["sapropterin", "sapropterin dihidroklorür"],
        "icd10_codes": ["E70.0"],
        "report_required": True,
        "report_specialties": ["çocuk metabolizma hastalıkları", "çocuk endokrinolojisi ve metabolizma hastalıkları"],
        "prescriber_specialties": [
            "çocuk metabolizma hastalıkları",
            "çocuk endokrinolojisi ve metabolizma hastalıkları",
            "çocuk sağlığı ve hastalıkları",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "8 yaş ve üzerinde, diyete uyum gösteremeyen ve tıbbi mama kullanamayan klasik fenilketonüri: çocuk metabolizma hastalıkları veya çocuk endokrinolojisi ve metabolizma hastalıkları uzmanının raporuyla bu hekimlerce veya çocuk sağlığı ve hastalıkları uzmanlarınca reçete edilirse ödenir",
            "message_tr": "8 yaş ve üzerinde, diyete uyum gösteremeyen ve tıbbi mama kullanamayan klasik fenilketonüri hastalığında, çocuk metabolizma hastalıkları veya çocuk endokrinolojisi ve metabolizma hastalıkları uzman hekimi tarafından düzenlenen uzman hekim raporuna dayanılarak bu hekimlerce veya çocuk sağlığı ve hastalıkları uzman hekimlerince reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.56).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.58  —  topical minoxidil / hair-loss preparations (outpatient 2-box / 10-box tiers)
    # -----------------------------------------------------------------

    # C007104 — ayakta tedavide aynı reçetede 2 kutuya kadar tüm hekimler, 2 kutu üzeri dermatoloji; 1 yıllık dermatoloji raporuyla 10 kutuya kadar tüm hekimler, üzeri dermatoloji
    {
        "rule_id": "4.2.58.derm.topical_hair_loss_2box_10box_tiers_coverage",
        "sut_section": "4.2.58",
        "gate_b_sources": ["C007104"],
        "drug_names": ["minoksidil (topikal)", "topikal saç dökülmesi ilaçları"],
        "icd10_codes": ["L63", "L64", "L65"],
        "prescriber_specialties": ["tüm hekimler", "dermatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "ayakta tedavide aynı reçetede 2 kutuya kadar tüm hekimlerce, 2 kutu üzeri dermatoloji uzmanınca; dermatoloji uzmanınca düzenlenen 1 yıl süreli rapora istinaden aynı reçetede 10 kutuya kadar tüm hekimlerce, 10 kutu üzeri dermatoloji uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Ayakta tedavilerde aynı reçetede 2 kutuya kadar tüm hekimlerce, 2 kutu üzeri kullanım gereken hallerde dermatoloji uzman hekimlerince reçete edilmesi halinde bedelleri Kurumca karşılanır. Dermatoloji uzman hekimlerince düzenlenen 1 yıl süreli rapora istinaden aynı reçetede 10 kutuya kadar tüm hekimlerce, 10 kutu üzeri kullanım gereken hallerde dermatoloji uzman hekimlerince reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.58).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.59  —  belinostat / pralatrexate (relapsed refractory peripheral T-cell lymphoma)
    # -----------------------------------------------------------------

    # C007107 — relaps refrakter periferik T hücreli lenfoma: üçüncü basamak, hematoloji/hematoloji-onkoloji 3 ay raporuyla ödenir
    {
        "rule_id": "4.2.59.onco.relapsed_ptcl_hematology_3mo_coverage",
        "sut_section": "4.2.59",
        "gate_b_sources": ["C007107"],
        "drug_names": ["pralatreksat", "belinostat"],
        "icd10_codes": ["C84.0", "C84.1", "C84.2", "C84.3", "C84.4", "C84.5", "C84.6", "C84.7", "C84.8", "C84.9"],
        "report_required": True,
        "report_duration_months": 3,
        "report_specialties": ["hematoloji", "hematoloji-onkoloji"],
        "prescriber_specialties": ["hematoloji", "hematoloji-onkoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "relaps refrakter periferik T hücreli lenfoma tedavisinde uygundur; üçüncü basamakta en az bir hematoloji veya hematoloji-onkoloji uzmanının yer aldığı 3 ay süreli sağlık kurulu raporuyla ilgili uzmanlarca reçete edilirse ödenir",
            "message_tr": "Relaps Refrakter Periferik T Hücreli Lenfoma hastalarında tedavi olarak kullanımı uygundur. Üçüncü basamak resmi sağlık hizmet sunucularında düzenlenen en az bir hematoloji veya hematoloji-onkoloji uzmanının yer aldığı 3 (üç) ay süreli sağlık kurulu raporuna dayanılarak ilgili uzman hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.59).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.60  —  (bare coverage continuation)
    # -----------------------------------------------------------------

    # C007125 — bedeli Kurumca karşılanır (bare coverage continuation clause)
    {
        "rule_id": "4.2.60.misc.bare_coverage_continuation",
        "sut_section": "4.2.60",
        "gate_b_sources": ["C007125"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "ilgili kullanım koşulları sağlandığında bedeli Kurumca karşılanır",
            "message_tr": "Bedelleri Kurumca karşılanır (§4.2.60).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.61  —  carmustine / off-label BMT conditioning (Hodgkin / Non-Hodgkin lymphoma)
    # -----------------------------------------------------------------

    # C007128 — karmustin: hasta bazlı endikasyon dışı onay + çocuk hematoloji-onkoloji veya erişkin hematoloji 6 aylık raporuyla ödenir; kemik iliği nakli hazırlık rejiminde karmustin kontrendike ise ödenir
    {
        "rule_id": "4.2.61.onco.carmustine_offlabel_bmt_conditioning_coverage",
        "sut_section": "4.2.61",
        "gate_b_sources": ["C007128"],
        "drug_names": ["karmustin"],
        "icd10_codes": ["C81", "C82", "C83", "C84", "C85"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["çocuk hematoloji ve onkoloji", "erişkin hematoloji", "hematoloji"],
        "prescriber_specialties": ["çocuk hematoloji ve onkoloji", "erişkin hematoloji", "hematoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "Sağlık Bakanlığından hasta bazında alınacak endikasyon dışı onaya dayanılarak üçüncü basamakta çocuk hematoloji ve onkoloji veya erişkin hematoloji uzmanının yer aldığı 6 aylık sağlık kurulu raporuyla adı geçen hekimlerce reçete edilirse ödenir; primer MSK lenfoması ve MSK tutulumu olan lenfomalar hariç Hodgkin/Non-Hodgkin lenfomada kemik iliği nakli hazırlık rejiminde karmustin kontrendike ise raporda belirtilmesiyle ödenir; endikasyon dışı onay tarihi ve süresi raporda belirtilir",
            "message_tr": "Sağlık Bakanlığından hasta bazında alınacak endikasyon dışı onaya dayanılarak, üçüncü basamak resmi sağlık hizmet sunucularında çocuk hematoloji ve onkoloji uzman hekiminin veya erişkin hematoloji uzman hekiminin yer aldığı 6 aylık sağlık kurulu raporuna istinaden adı geçen hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır. Sağlık Bakanlığından hasta bazında alınacak endikasyon dışı onaya dayanılarak, primer merkezi sinir sistemi lenfoması ve merkezi sinir sistemi tutulumu olan lenfomalar hariç olmak üzere Hodgkin Lenfoma ve Non-Hodgkin Lenfoma hastalarındaki kemik iliği nakli hazırlık rejimi kullanımında ise; söz konusu raporda karmustin kullanımının kontrendike olduğu durumların belirtilmesi halinde bedelleri Kurumca karşılanır. Endikasyon dışı onay tarihi ve süresi sağlık kurulu raporunda belirtilir (§4.2.61).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.62  —  propranolol (infantile haemangioma, 5 wk-5 mo, morbidity/systemic Tx)
    # -----------------------------------------------------------------

    # C007130 — infantil hemanjiyom (5 hafta-5 ay, morbiditeye yol açan/hızla çoğalan/sistemik tedavi gerektiren): en az bir özelliği taşıyanda ödenir (başlangıç)
    {
        "rule_id": "4.2.62.peds.infantile_haemangioma_systemic_initiation_coverage",
        "sut_section": "4.2.62",
        "gate_b_sources": ["C007130"],
        "drug_names": ["propranolol"],
        "icd10_codes": ["D18.0", "D21", "Q82.5"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "5 hafta-5 ay arası bebeklerde yutma güçlüğü, kanama/bası bulguları veya solunum güçlüğü vb. morbiditeyi önemli derecede olumsuz etkileyecek durumlara sebep olan ve sistemik tedavi gerektirerek hızla çoğalan çocukluk çağı hemanjiyomlarında tanımlı özelliklerden en az birini taşıyanda kullanılırsa bedeli ödenir",
            "message_tr": "5 hafta-5 ay yaş aralığında olan bebeklerde yutma güçlüğü, kanama/bası bulguları veya solunum güçlüğü vb. morbiditeyi önemli derecede olumsuz etkileyecek durumlara sebep olan ve sistemik tedavi gerektirerek hızla çoğalan çocukluk çağı hemanjiyomlarının tedavisinde aşağıda belirtilen özelliklerden en az birini taşıyan hastalarda kullanılması halinde bedelleri Kurumca karşılanır (§4.2.62).",
        },
    },

    # C007134 — devam: çocuk hematoloji-onkoloji/çocuk hematoloji/çocuk onkoloji/çocuk kardiyoloji/neonatoloji uzmanı ≤6 ay raporu; 6. ayın sonunda tedavi sonlandırılır
    {
        "rule_id": "4.2.62.peds.infantile_haemangioma_peds_specialty_6mo_terminate",
        "sut_section": "4.2.62",
        "gate_b_sources": ["C007134"],
        "drug_names": ["propranolol"],
        "icd10_codes": ["D18.0", "D21", "Q82.5"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": [
            "çocuk hematolojisi ve onkolojisi", "çocuk hematolojisi",
            "çocuk onkolojisi", "çocuk kardiyolojisi", "neonatoloji",
        ],
        "prescriber_specialties": [
            "çocuk hematolojisi ve onkolojisi", "çocuk hematolojisi",
            "çocuk onkolojisi", "çocuk kardiyolojisi", "neonatoloji",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "bu durumların belirtildiği, çocuk hematolojisi ve onkolojisi/çocuk hematolojisi/çocuk onkolojisi/çocuk kardiyolojisi veya neonatoloji uzmanlarından birinin ≤6 ay süreli raporuyla bu uzmanlarca reçete edilirse ödenir; tedavinin başlangıcından itibaren 6. ayın sonunda sonlandırılır",
            "message_tr": "Bu durumların belirtildiği, çocuk hematolojisi ve onkolojisi, çocuk hematolojisi, çocuk onkolojisi, çocuk kardiyolojisi veya neonatoloji uzman hekimlerinden biri tarafından düzenlenen en fazla 6 ay süreli uzman hekim raporuna dayanılarak bu uzman hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır. Tedavinin başlangıcından itibaren 6 ncı ayın sonunda tedavi sonlandırılır (§4.2.62).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.63  —  trientine (Wilson, D-penicillamine intolerant)
    # -----------------------------------------------------------------

    # C007137 — D-penisilamine tolere edemeyen Wilson: en az biri gastroenteroloji olmak üzere gastroenteroloji ve/veya nöroloji 6 ay raporuyla ödenir
    {
        "rule_id": "4.2.63.gi.wilson_dpenicillamine_intolerant_trientine_coverage",
        "sut_section": "4.2.63",
        "gate_b_sources": ["C007137"],
        "drug_names": ["trientin", "trientin hidroklorür"],
        "icd10_codes": ["E83.0"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["gastroenteroloji", "nöroloji"],
        "prescriber_specialties": ["gastroenteroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "enfeksiyon dışı ateş, lenfadenopati, proteinüri, döküntü, lupus benzeri etkiler, kemik iliği baskılanması yan etkileri (anemi/nötropeni/trombositopeni), nörolojik semptom kötüleşmesinden biri/birkaçıyla D-penisilamine tolere edemeyen Wilson'da; en az biri gastroenteroloji olmak üzere gastroenteroloji ve/veya nöroloji uzmanlarının 6 ay süreli raporuyla uzmanlarca reçete edilirse ödenir",
            "message_tr": "Enfeksiyona bağlı olmayan ateş, lenfadenopati, proteinüri, ciltte döküntü, lupus benzeri etkiler, kemik iliği baskılanmasıyla oluşan yan etkiler (anemi, nötropeni veya trombositopeni), nörolojik semptomlarda kötüleşme durumlarından bir veya birkaçını göstererek D-Penisilamin etken maddeli ilacı tolere edemeyen Wilson hastalarının tedavisinde, en az biri gastroenteroloji uzman hekimi olmak kaydıyla; gastroenteroloji ve/veya nöroloji uzman hekimlerinin yer aldığı 6 ay süreli sağlık kurulu raporuna istinaden uzman hekimlerce reçete edilmesi halinde Kurumca bedelleri karşılanır (§4.2.63).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.64  —  zinc (Wilson disease, maintenance)
    # -----------------------------------------------------------------

    # C007139 — Wilson hastalığı idame: üçüncü basamak nöroloji/çocuk nöroloji/gastroenteroloji/çocuk gastroenteroloji raporuyla tüm hekimlerce reçete edilirse ödenir
    {
        "rule_id": "4.2.64.gi.wilson_zinc_maintenance_tertiary_coverage",
        "sut_section": "4.2.64",
        "gate_b_sources": ["C007139"],
        "drug_names": ["çinko sülfat", "çinko asetat", "çinko"],
        "icd10_codes": ["E83.0"],
        "report_required": True,
        "report_specialties": ["nöroloji", "çocuk nörolojisi", "gastroenteroloji", "çocuk gastroenterolojisi"],
        "prescriber_specialties": ["tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "Wilson hastalığı tanılı hastaların tedavisinde; üçüncü basamakta nöroloji/çocuk nörolojisi/gastroenteroloji/çocuk gastroenterolojisi uzmanlarından birinin raporuna istinaden tüm hekimlerce reçete edilirse ödenir",
            "message_tr": "Wilson hastalığı tanılı hastaların tedavisinde, üçüncü basamak resmi sağlık hizmet sunucularında nöroloji, çocuk nörolojisi, gastroenteroloji, çocuk gastroenterolojisi uzman hekimlerinden biri tarafından düzenlenen sağlık raporuna istinaden, tüm hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.64).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.65  —  topical EGF (Wagner 1/2 neuropathic diabetic foot ulcer)
    # -----------------------------------------------------------------

    # C007142 — Wagner 1/2 nöropatik diyabetik ayak ülseri: 2./3. basamakta ilgili uzmanların 4 hafta süreli raporuyla 4 haftalık dozda reçete edilirse ödenir
    {
        "rule_id": "4.2.65.derm.diabetic_foot_wagner12_4wk_specialty_coverage",
        "sut_section": "4.2.65",
        "gate_b_sources": ["C007142"],
        "drug_names": ["epidermal büyüme faktörü (topikal)"],
        "icd10_codes": ["E10.5", "E11.5", "E12.5", "E13.5", "E14.5", "L97"],
        "report_required": True,
        "report_duration_months": 1,
        "report_specialties": [
            "enfeksiyon hastalıkları ve klinik mikrobiyoloji", "kalp ve damar cerrahisi",
            "ortopedi ve travmatoloji", "plastik, rekonstrüktif ve estetik cerrahi",
            "endokrinoloji ve metabolizma hastalıkları", "genel cerrahi",
        ],
        "prescriber_specialties": [
            "enfeksiyon hastalıkları ve klinik mikrobiyoloji", "kalp ve damar cerrahisi",
            "ortopedi ve travmatoloji", "plastik, rekonstrüktif ve estetik cerrahi",
            "endokrinoloji ve metabolizma hastalıkları", "genel cerrahi",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "konvansiyonel yara tedavisine rağmen iyileşmeyen kuru/yaş gangrensiz, osteomiyeliti ve enfeksiyonu tedavi olmuş Wagner 1 veya 2 nöropatik diyabetik ayak ülserinde; 2./3. basamakta ilgili uzmanlardan üçünün yer aldığı 4 hafta süreli uzman hekim raporuyla yine bu uzmanlarca 4 haftalık dozda reçete edilirse ödenir",
            "message_tr": "Konvansiyonel yara tedavi prensiplerinin uygulanmasına rağmen yarada iyileşmenin izlenmediği kuru veya yaş gangrensiz, osteomiyeliti ve enfeksiyonu tedavi olmuş, Wagner 1 veya 2 nöropatik diyabetik ayak ülserleri olan hastalarda, ikinci basamak ya da üçüncü basamak resmi sağlık hizmeti sunucularında enfeksiyon hastalıkları ve klinik mikrobiyoloji, kalp ve damar cerrahisi, ortopedi ve travmatoloji, plastik, rekonstrüktif ve estetik cerrahi, endokrinoloji ve metabolizma hastalıkları veya genel cerrahi uzman hekimlerince 4 (dört) hafta süreli uzman hekim raporuna istinaden yine bu uzman hekimler tarafından 4 (dört) haftalık dozda reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.65).",
        },
    },

    # C007143 — devam: 4 haftalık tedavi sonrası yanıt alınanlarda; 2./3. basamakta ilgili uzmanların 4 hafta süreli raporuyla 4 haftalık dozda reçete edilirse ödenir
    {
        "rule_id": "4.2.65.derm.diabetic_foot_4wk_response_continue_coverage",
        "sut_section": "4.2.65",
        "gate_b_sources": ["C007143"],
        "drug_names": ["epidermal büyüme faktörü (topikal)"],
        "icd10_codes": ["E10.5", "E11.5", "E12.5", "E13.5", "E14.5", "L97"],
        "report_required": True,
        "report_duration_months": 1,
        "report_specialties": [
            "enfeksiyon hastalıkları ve klinik mikrobiyoloji", "kalp ve damar cerrahisi",
            "ortopedi ve travmatoloji", "plastik, rekonstrüktif ve estetik cerrahi",
            "endokrinoloji ve metabolizma hastalıkları", "genel cerrahi",
        ],
        "prescriber_specialties": [
            "enfeksiyon hastalıkları ve klinik mikrobiyoloji", "kalp ve damar cerrahisi",
            "ortopedi ve travmatoloji", "plastik, rekonstrüktif ve estetik cerrahi",
            "endokrinoloji ve metabolizma hastalıkları", "genel cerrahi",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "4 haftalık tedavi sonrası yanıt alınan ve tedavinin devamı gereken hastalarda; 2./3. basamakta ilgili uzmanlardan üçünün yer aldığı 4 hafta süreli uzman hekim raporuyla yine bu uzmanlarca 4 haftalık dozda reçete edilirse ödenir",
            "message_tr": "4 (dört) haftalık tedavi sonrasında yanıt alınan hastalarda tedavinin devamının gerekmesi halinde; ikinci basamak ya da üçüncü basamak resmi sağlık hizmeti sunucularında enfeksiyon hastalıkları ve klinik mikrobiyoloji, kalp ve damar cerrahisi, ortopedi ve travmatoloji, plastik, rekonstrüktif ve estetik cerrahi, endokrinoloji ve metabolizma hastalıkları veya genel cerrahi uzman hekimlerince düzenlenen 4 (dört) hafta süreli uzman hekim raporuna istinaden yine bu uzman hekimler tarafından 4 (dört) haftalık dozda reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.65).",
        },
    },

    # C007145 — mandatory: topikal EGF öncesi uygulanan konvansiyonel tedaviler ve süreleri raporda belirtilmelidir
    {
        "rule_id": "4.2.65.derm.diabetic_foot_prior_conventional_tx_report_mandatory",
        "sut_section": "4.2.65",
        "gate_b_sources": ["C007145"],
        "drug_names": ["epidermal büyüme faktörü (topikal)"],
        "icd10_codes": ["E10.5", "E11.5", "E12.5", "E13.5", "E14.5", "L97"],
        "report_required": True,
        "action": {
            "enforcement": "mandatory: topikal epidermal büyüme faktörü tedavisinden önce uygulanan konvansiyonel tedaviler ve uygulama süreleri sağlık kurulu raporunda belirtilmelidir",
            "message_tr": "Epidermal büyüme faktörü (topikal formu) tedavisi öncesinde uygulanan konvansiyonel tedaviler ve uygulama sürelerinin sağlık kurulu raporunda belirtilmesi gerekmektedir (§4.2.65).",
        },
    },

    # C007146 — mandatory: osteomyelit yok/tedavi edilmiş (ortopedi) ve yumuşak doku enfeksiyonu kontrol altında (enfeksiyon hastalıkları) raporda belirtilmelidir
    {
        "rule_id": "4.2.65.derm.diabetic_foot_osteomyelitis_softtissue_report_mandatory",
        "sut_section": "4.2.65",
        "gate_b_sources": ["C007146"],
        "drug_names": ["epidermal büyüme faktörü (topikal)"],
        "icd10_codes": ["E10.5", "E11.5", "E12.5", "E13.5", "E14.5", "L97"],
        "report_required": True,
        "report_specialties": ["ortopedi ve travmatoloji", "enfeksiyon hastalıkları ve klinik mikrobiyoloji"],
        "action": {
            "enforcement": "mandatory: osteomyelite bağlı ülserlerde osteomyelitin olmadığının/tedavi edilmiş olduğunun ortopedi ve travmatoloji uzmanınca, yumuşak doku enfeksiyonuna bağlı ülserlerde yumuşak doku enfeksiyonunun kontrol altına alındığının enfeksiyon hastalıkları ve klinik mikrobiyoloji uzmanınca raporda belirtilmesi gerekir",
            "message_tr": "Osteomyelite bağlı ülserlerde osteomyelitin olmadığının/tedavi edilmiş olduğunun ortopedi ve travmatoloji uzman hekimi tarafından, yumuşak doku enfeksiyonuna bağlı ülserlerde yumuşak doku enfeksiyonunun kontrol altına alındığının enfeksiyon hastalıkları ve klinik mikrobiyoloji hastalıkları uzman hekimi tarafından raporda belirtilmesi gerekmektedir (§4.2.65).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.66  —  gonadotropins (FSH-LH combo / corifollitropin alfa) + dose caps / combination no-pay
    # -----------------------------------------------------------------

    # C007150 — kombine FSH-LH ≤750 IU/hafta, koryogonadotropin alfa ≤500 mcg/hafta; üroloji uzmanınca reçete; birlikte kullanım no-pay
    {
        "rule_id": "4.2.66.gyn.gonadotropin_fsh_lh_corifollitropin_dosecap_combo_nopay",
        "sut_section": "4.2.66",
        "gate_b_sources": ["C007150"],
        "drug_names": ["kombine fsh-lh preparatları", "koryogonadotropin alfa"],
        "prescriber_specialties": ["üroloji"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: kombine FSH-LH preparatları ile koryogonadotropin alfa etkin maddeli ilaçların birlikte kullanımı halinde Kurumca bedeli ödenmez; kombine FSH-LH en fazla 750 IU/hafta, koryogonadotropin alfa en fazla 500 mcg/hafta dozda kullanılabilir; üroloji uzmanınca reçete edilmesi halinde bedeli ödenir",
            "message_tr": "Kombine FSH-LH preparatları ile koryogonadotropin alfa etkin maddeli ilaçların birlikte kullanımı halinde Kurumca bedeli ödenmez. Kombine FSH-LH preparatları en fazla 750 IU/hafta dozda, koryogonadotropin alfa etkin maddeli ilaçlar en fazla 500 mcg/hafta dozda kullanılabilir (§4.2.66).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.67  —  tolvaptan (ADPKD, age 18-55, GFR>25)
    # -----------------------------------------------------------------

    # C007152 — başlangıç kriterleri: 18-55 yaş (55 hariç), GFR>25 ml/dk, ADPKD tanısı (regulatory action)
    {
        "rule_id": "4.2.67.renal.adpkd_tolvaptan_initiation_criteria_regulatory",
        "sut_section": "4.2.67",
        "gate_b_sources": ["C007152"],
        "drug_names": ["tolvaptan"],
        "icd10_codes": ["Q61.2", "Q61.3"],
        "report_required": True,
        "report_specialties": ["nefroloji"],
        "action": {
            "enforcement": "regulatory action: aşağıdaki kriterlerin tümünü karşılayan 18 (18,0)-55 (55,0 hariç) yaş arası, GFR'i 25 ml/dk'nın üzerinde ADPKD tanısı almış hastalarda tedaviye başlanır",
            "message_tr": "Aşağıdaki kriterlerin tümünü karşılayan 18 (18,0) - 55 (55,0 hariç) yaş arası, GFR'si 25ml/dk'nın üzerinde ADPKD tanısı almış hastalarda tedaviye başlanır (§4.2.67).",
        },
    },

    # C007162 — devam: üçüncü basamak nefroloji raporu (≤1 yıl) ile nefroloji uzmanlarınca reçete; maksimum 120 mg/gün; GFR<25'te sonlandırılır
    {
        "rule_id": "4.2.67.renal.adpkd_tolvaptan_tertiary_nephrology_1yr_coverage",
        "sut_section": "4.2.67",
        "gate_b_sources": ["C007162"],
        "drug_names": ["tolvaptan"],
        "icd10_codes": ["Q61.2", "Q61.3"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["nefroloji"],
        "prescriber_specialties": ["nefroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta en az bir nefroloji uzmanının yer aldığı sağlık kurulu raporuyla nefroloji uzmanlarınca reçete edilirse ödenir; rapor en fazla 1 yıl geçerli olup başlangıç kriterleri raporda belirtilir; maksimum doz günde 120 mg'yi aşmamalı; GFR<25 ml/dk olduğunda ilaç sonlandırılır",
            "message_tr": "Üçüncü basamak resmi sağlık hizmeti sunucularında en az bir nefroloji uzman hekiminin yer aldığı sağlık kurulu raporuna dayanılarak nefroloji uzmanlarınca reçete edilmesi halinde bedeli ödenir. Rapor en fazla 1 yıl süreyle geçerli olup, yukarıda yer alan kriterler belirtilir. Maksimum doz günde 120 mg'yi aşmamalıdır. GFR<25 ml/dk olduğunda ilaç sonlandırılır (§4.2.67).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.68  —  amifampridine (LEMS / congenital myasthenic syndrome)
    # -----------------------------------------------------------------

    # C007165 — LEMS (elektrofizyolojik/klinik) veya konjenital miyastenik sendrom (genetik): üçüncü basamak çocuk nöroloji/nöroloji raporuyla bu uzmanlarca reçete edilirse ödenir
    {
        "rule_id": "4.2.68.neuro.lems_congenital_myasthenic_amifampridine_coverage",
        "sut_section": "4.2.68",
        "gate_b_sources": ["C007165"],
        "drug_names": ["amifampridin", "amifampridin fosfat"],
        "icd10_codes": ["G70.0", "G70.1", "G73.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "prescriber_specialties": ["çocuk nöroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "elektrofizyolojik test ve/veya klinik değerlendirmeyle tanı konulmuş Lambert-Eaton Miyastenik Sendromlu (LEMS) veya genetik analizle tanı konulmuş konjenital miyastenik sendromlu hastaların tedavisinde; üçüncü basamakta tanı kriterlerinin belirtildiği, en az bir çocuk nöroloji ve/veya nöroloji uzmanının yer aldığı sağlık kurulu raporuyla bu uzmanlarca reçete edilirse ödenir",
            "message_tr": "Elektrofizyolojik test ve/veya klinik değerlendirmeyle tanı konulmuş Lambert Eaton Miyastenik Sendromlu (LEMS) veya genetik analiz ile tanı konulmuş konjenital miyastenik sendromlu hastaların tedavisi için, üçüncü basamak resmi sağlık hizmet sunucularında düzenlenen ve yukarıda yer alan tanı kriterlerinin belirtildiği, en az bir çocuk nöroloji ve/veya nöroloji uzman hekiminin yer aldığı sağlık kurulu raporuna dayanılarak bu uzman hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.68).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.69  —  (bare coverage continuation)
    # -----------------------------------------------------------------

    # C007171 — bedeli Kurumca karşılanır (bare coverage continuation clause)
    {
        "rule_id": "4.2.69.misc.bare_coverage_continuation",
        "sut_section": "4.2.69",
        "gate_b_sources": ["C007171"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "ilgili kullanım koşulları sağlandığında bedeli Kurumca karşılanır",
            "message_tr": "Bedeli Kurumca karşılanır (§4.2.69).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.71  —  daratumumab SC (AL amyloidosis, CyBorD combo, progressive)
    # -----------------------------------------------------------------

    # C007207 — daratumumab SC: AL amiloidoz (yeni tanı, biyopsi ile) siklofosfamid+bortezomib+deksametazon ile progresyona kadar kombine; ödenir
    {
        "rule_id": "4.2.71.onco.al_amyloidosis_daratumumab_cyborg_combo_coverage",
        "sut_section": "4.2.71",
        "gate_b_sources": ["C007207"],
        "drug_names": ["daratumumab"],
        "icd10_codes": ["E85.0", "E85.4", "E85.9"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "prescriber_specialties": ["hematoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "daratumumabın yalnızca SC formu; biyopsi ile AL tipi amiloid varlığı tespit edilmiş yeni teşhis sistemik hafif zincir (AL) amiloidozlu yetişkinlerde siklofosfamid, bortezomib ve deksametazon ile kombine olarak progresyona kadar kullanılırsa ödenir",
            "message_tr": "Daratumumabın yalnızca sc formu; biyopsi ile AL tipi amiloid varlığı tespit edilmiş yeni teşhis edilmiş sistemik hafif zincir (AL) amiloidozlu yetişkin hastaların tedavisinde siklofosfamid, bortezomib ve deksametazon ile kombine olarak progresyona kadar kullanılması halinde bedelleri Kurumca karşılanır (§4.2.71).",
        },
    },

    # C007208 — devam: 3. kür sonunda ≥minör yanıt, 6. ve her 6 kürde ≥kısmi yanıt; hematoloji uzmanı ≤3 ay raporuyla hematoloji uzmanlarınca reçete
    {
        "rule_id": "4.2.71.onco.al_amyloidosis_daratumumab_response_hematology_3mo_coverage",
        "sut_section": "4.2.71",
        "gate_b_sources": ["C007208"],
        "drug_names": ["daratumumab"],
        "icd10_codes": ["E85.0", "E85.4", "E85.9"],
        "report_required": True,
        "report_duration_months": 3,
        "report_specialties": ["hematoloji"],
        "prescriber_specialties": ["hematoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "3. kür sonunda en az minör yanıt, 6. kür sonunda ve devam eden her 6 kür sonunda en az kısmi yanıt olduğu belirtilen, hematoloji uzmanının yer aldığı en fazla 3 ay süreli sağlık kurulu raporuyla hematoloji uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Üçüncü kür sonunda en az minör yanıt, altıncı kür sonunda ve devam eden her 6 kür sonunda ise en az kısmi yanıt olduğunun belirtildiği, hematoloji uzman hekiminin yer aldığı, en fazla 3 ay süreli sağlık kurulu raporuna istinaden hematoloji uzman hekimlerince reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.71).",
        },
    },

    # C007209 — no-pay: NYHA Sınıf IIIB/IV kalp hastalığı veya Mayo Evre IIIB AL amiloidozda ödenmez
    {
        "rule_id": "4.2.71.onco.al_amyloidosis_daratumumab_cardiac_mayo_iiib_nopay",
        "sut_section": "4.2.71",
        "gate_b_sources": ["C007209"],
        "drug_names": ["daratumumab"],
        "icd10_codes": ["E85.0", "E85.4", "E85.9", "I50"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: NYHA Sınıf IIIB veya Sınıf IV kalp hastalığı olan veya Mayo Evre IIIB hafif zincir (AL) amiloidozu olan hastalarda ödenmez",
            "message_tr": "NYHA Sınıf IIIB veya Sınıf IV kalp hastalığı olan veya Mayo Evre IIIB hafif zincir (AL) amiloidozu olan hastalarda ödenmez (§4.2.71).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.72  —  supplementary foods (mitochondrial cytopathy), monthly cash 880 TL
    # -----------------------------------------------------------------

    # C007221 — mitokondriyal sitopati: takviye edici gıdalar aylık nakden 880 TL sağlık kurulu raporuyla şahıs bazında ödenir
    {
        "rule_id": "4.2.72.meta.mitochondrial_cytopathy_supplementary_foods_880tl_coverage",
        "sut_section": "4.2.72",
        "gate_b_sources": ["C007221"],
        "drug_names": ["takviye edici gıdalar (mitokondriyal sitopati)"],
        "icd10_codes": ["E88.8", "G71.3"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "mitokondriyal sitopati hastalığında tedaviye yardımcı olarak kullanılan takviye edici gıdaların bedelleri aylık nakden 880,00 TL olarak sağlık kurulu raporu ile şahıs bazında ödenir",
            "message_tr": "Mitokondriyal sitopati hastalığında tedaviye yardımcı olarak kullanılan takviye edici gıdaların bedelleri aylık nakden 880,00 (sekiz yüz seksen) TL olarak sağlık kurulu raporu ile şahıs bazında ödenir (§4.2.72).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.73  —  CFTR modulators (elexacaftor/tezacaftor/ivacaftor + ivacaftor)
    # -----------------------------------------------------------------

    # C007260 — mandatory: daha önce KFTR modülatörü kullananlarda ilk raporda başlangıç tarihi ve uygunluğu gösteren test sonuçları; devamda fayda belirtilirse devam; ≥6 ay ara verilirse başlangıç kriterleri
    {
        "rule_id": "4.2.73.pulm.cftr_prior_modulator_report_criteria_mandatory",
        "sut_section": "4.2.73",
        "gate_b_sources": ["C007260"],
        "drug_names": [
            "elexakaftor/tezakaftor/ivakaftor ve ivakaftor",
            "ivakaftor", "tezakaftor", "lumakaftor", "elexakaftor",
        ],
        "icd10_codes": ["E84.0", "E84.1", "E84.8", "E84.9"],
        "report_required": True,
        "action": {
            "enforcement": "mandatory: daha önce KFTR modülatörü kullanan 24 ay ve üzeri hastalarda ilk raporda kullanmakta olduğu KFTR modülatörüne başlangıç tarihinin ve başlangıç kriterlerine uygunluğunu gösteren test sonuçlarının tarihleriyle yer alması gerekir; devam raporunda tedaviden fayda sağlandığı belirtilirse devam edilir; tedaviye başlama tarihinden önceki son 6 ay ve daha uzun ara verenlerde başlangıç kriterleri aranır",
            "message_tr": "Daha önce KFTR Modülatörü kullanan hastalarda \"Elexacaftor/ Tezacaftor /Ivacaftor and Ivacaftor\" kullanım kriterleri: Daha önce KFTR Modülatörü (ivacaftor, tezacaftor, lumacaftor ve elexacaftor'un tek başına veya kombinasyon formları) başlanan, 24 aylık ve üzeri hastalarda düzenlenecek ilk raporda kullanmakta olduğu KFTR Modülatörüne başlangıç tarihinin ve başlangıç kriterlerine uygun olduğunu gösterir test sonuçlarının tarihleriyle birlikte raporda yer alması gerekmektedir. Bu hastalarda devam raporunda tedaviden fayda sağlandığının belirtilmesi koşuluyla tedaviye devam edilir. Elexacaftor/ Tezacaftor /Ivacaftor and Ivacaftor tedavisine başlama tarihinden önceki son 6 ay ve daha uzun süre ile KFTR Modülatörü tedavisine ara veren hastalarda başlangıç kriterleri aranır (§4.2.73).",
        },
    },

    # C007262 — rapor/reçeteleme: üçüncü basamak göğüs hastalıkları 6 ay raporuyla göğüs hastalıkları uzmanlarınca reçete edilirse ödenir
    {
        "rule_id": "4.2.73.pulm.cftr_tertiary_pulmonology_6mo_coverage",
        "sut_section": "4.2.73",
        "gate_b_sources": ["C007262"],
        "drug_names": [
            "elexakaftor/tezakaftor/ivakaftor ve ivakaftor",
            "ivakaftor", "tezakaftor", "lumakaftor", "elexakaftor",
        ],
        "icd10_codes": ["E84.0", "E84.1", "E84.8", "E84.9"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["göğüs hastalıkları"],
        "prescriber_specialties": ["göğüs hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "rapor ve reçeteleme koşulları: üçüncü basamakta en az bir göğüs hastalıkları uzmanının yer aldığı 6 ay süreli sağlık kurulu raporuyla göğüs hastalıkları uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Rapor ve reçeteleme koşulları: Üçüncü basamak resmi sağlık hizmeti sunucularında düzenlenen en az bir göğüs hastalıkları uzman hekiminin yer aldığı 6 ay süreli sağlık kurulu raporuna istinaden göğüs hastalıkları uzman hekimlerince reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.73).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.74  —  dapagliflozin / empagliflozin (HFrEF / CKD with proteinuria)
    # -----------------------------------------------------------------

    # C007265 — dapagliflozin/empagliflozin: HFrEF (EF≤%40, NYHA II-IV) standart tedaviye ilave; kardiyoloji 1 yıl raporuyla tüm hekimlerce reçete
    {
        "rule_id": "4.2.74.card.sgli_hfref_dapagliflozin_empagliflozin_cardiology_1yr_coverage",
        "sut_section": "4.2.74",
        "gate_b_sources": ["C007265"],
        "drug_names": ["dapagliflozin", "empagliflozin"],
        "icd10_codes": ["I50.0", "I50.1", "I50.2", "I50.3", "I50.4", "I50.8", "I50.9"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["kardiyoloji"],
        "prescriber_specialties": ["tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "dapagliflozin veya empagliflozin; standart kalp yetmezliği tedavisini (ACEi/ARB'den birini + beta blokör + aldosteron antagonisti) kullanıyor (veya kullanamıyorsa gerekçesi raporda) olması koşuluyla; düşük ejeksiyon fraksiyonlu (sol ventrikül EF≤%40) semptomatik (NYHA II-IV) kronik kalp yetersizliği ve eGFR uygun (empagliflozin ≥20, dapagliflozin ≥25 mL/dk/1,73 m²) hastalarda standart tedaviye ilave kullanılırsa başlanır; kardiyoloji uzmanının yer aldığı 1 yıl süreli raporla tüm hekimlerce reçete edilirse ödenir",
            "message_tr": "Dapagliflozin veya empagliflozin; standart kalp yetmezliği tedavisini (anjiyotensin dönüştürücü enzim inhibitörleri veya anjiyotensin reseptör blokörleri grubundan birini ve beta blokör ve aldosteron antagonistleri) kullanıyor olması veya kullanamıyorsa, her birinin kullanılamama gerekçesinin raporda belirtilmesi koşuluyla; düşük ejeksiyon fraksiyonlu (sol ventrikül EF değeri ≤ %40) semptomatik (NHYA sınıf II-IV) kronik kalp yetersizliği bulunan ve eGFR düzeyi uygun olan (empagliflozin için eGFR ≥20 mL/dak /1,73 m², dapagliflozin için eGFR ≥ 25 mL/dak /1,73 m²) hastalarda, standart tedaviye ilave olarak kullanılması halinde tedaviye başlanır. Bu durumların belirtildiği en az bir kardiyoloji uzman hekiminin yer aldığı 1 yıl süreli sağlık kurulu raporuna istinaden tüm hekimler tarafından reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.74).",
        },
    },

    # C007266 — dapagliflozin/empagliflozin: KBH (RAAS inhibitörü alan + ≥3 ay persistan proteinüri) ve eGFR uygun; nefroloji raporuyla tüm hekimlerce reçete
    {
        "rule_id": "4.2.74.renal.sgli_ckd_proteinuria_dapagliflozin_empagliflozin_nephrology_coverage",
        "sut_section": "4.2.74",
        "gate_b_sources": ["C007266"],
        "drug_names": ["dapagliflozin", "empagliflozin"],
        "icd10_codes": ["N18.3", "N18.4", "N18.5", "N18.6"],
        "report_required": True,
        "report_specialties": ["nefroloji"],
        "prescriber_specialties": ["tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "dapagliflozin veya empagliflozin; kronik böbrek hastalığında RAAS inhibitörü alan ve en az 3 ay persistan proteinürisi olan (idrar ACR≥200 mg/g veya PCR>300 mg/g) ve eGFR uygun (empagliflozin ≥20, dapagliflozin ≥25 mL/dk/1,73 m²) hastalarda başlanır; nefroloji uzmanının yer aldığı sağlık kurulu raporuyla tüm hekimlerce reçete edilirse ödenir",
            "message_tr": "Dapagliflozin veya empagliflozin, kronik böbrek hastalığının tedavisinde; renin-anjiyotensin-aldosteron sistemi inhibitörü alan ve en az 3 ay süreli persistan proteinürisi olan (idrar ACR (Albumin/Kreatinin oranı) ≥ 200mg/g veya PCR (Protein/Kreatinin oranı) >300mg/g) ve eGFR düzeyi uygun olan (empagliflozin için eGFR ≥ 20 mL/dak /1,73 m², dapagliflozin için eGFR ≥ 25 mL/dak /1,73 m²) hastalarda tedaviye başlanır. Bu durumların belirtildiği en az bir nefroloji uzman hekiminin yer aldığı sağlık kurulu raporuna istinaden tüm hekimler tarafından reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.74).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.75  —  paediatric endocrine (child endocrinology/metabolism, ≤1 yr report)
    # -----------------------------------------------------------------

    # C007286 — çocuk endokrinolojisi/metabolizma: üçüncü basamakta ilgili uzmanın 1 yıl süreli raporuyla bu uzmanlarca reçete edilirse ödenir
    {
        "rule_id": "4.2.75.peds.child_endocrinology_metabolism_1yr_coverage",
        "sut_section": "4.2.75",
        "gate_b_sources": ["C007286"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["çocuk endokrinolojisi", "çocuk endokrinolojisi ve metabolizma hastalıkları"],
        "prescriber_specialties": ["çocuk endokrinolojisi", "çocuk endokrinolojisi ve metabolizma hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta en az bir çocuk endokrinolojisi veya çocuk endokrinolojisi ve metabolizma hastalıkları uzmanının yer aldığı 1 yıl süreli sağlık kurulu raporuyla çocuk endokrinolojisi veya çocuk endokrinolojisi ve metabolizma uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Üçüncü basamak resmi sağlık hizmet sunucularında düzenlenen en az bir çocuk endokrinolojisi veya çocuk endokrinolojisi ve metabolizma hastalıkları uzman hekiminin yer aldığı 1 yıl süreli sağlık kurulu raporuna istinaden çocuk endokrinolojisi veya çocuk endokrinolojisi ve metabolizma uzman hekimlerince reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.75).",
        },
    },
]


def all_gate_b_sources() -> list[str]:
    """Union of every gate_b_sources clause id in the batch (sorted)."""
    ids: set[str] = set()
    for rule in BATCH_RULES:
        ids.update(str(c) for c in (rule.get("gate_b_sources") or []))
    return sorted(ids)


if __name__ == "__main__":
    sources = all_gate_b_sources()
    print(f"BATCH_RULES: {len(BATCH_RULES)} rules, "
          f"{len(sources)} distinct gate_b_sources")
