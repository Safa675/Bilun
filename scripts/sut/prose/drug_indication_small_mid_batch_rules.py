#!/usr/bin/env python3
"""Wave A1e — small/mid drug-indication clauses
(§4.2.3, §4.2.6.A*, §4.2.7, §4.2.10.A-3 / B* / C-1, §4.2.16, §4.2.17.A-B-D,
§4.2.23, §4.2.25, §4.2.32, §4.2.35.A-B, §4.2.46.A-B-C, §4.2.57, §4.2.70.A-B).

70 in-force deontic clauses encoded from
`tasks/encode_waves/A1e_small_mid.csv`.

Rule shape follows the established `drug_indication_prose.json` pattern:
flat condition keys (drug_names, icd10_codes, report_required,
report_specialties, prescriber_specialties, pay) plus a nested `action`
block (message_tr + enforcement) for coverage/permission/NO_PAY clauses.
Bare coverage statements use ``condition: {"coverage_note": True}``.
"""

from __future__ import annotations

WAVE_BATCH_RULES: list[dict] = [

    # -----------------------------------------------------------------
    # §4.2.3  —  allergen immunotherapy / antidotes
    # -----------------------------------------------------------------

    # C003914 — immunotherapy: max 2 different groups paid
    {
        "rule_id": "4.2.3.immunotherapy_max_2_groups",
        "sut_section": "4.2.3",
        "gate_b_sources": ["C003914"],
        "drug_names": ["immünoterapi", "alerji aşısı", "alergoid immünoterapi"],
        "icd10_codes": ["Z88", "J30"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "en fazla 2 farklı grup solunum yolu alerjeni (polenler, ev tozu akarları, küf mantarları, hayvan epiteli) için immunoterapi ödenir",
            "message_tr": "En fazla 2 farklı grup solunum yolu alerjeni için immunoterapi ödenir. Bu gruplar; polenler, ev tozu akarları, küf mantarları ve hayvan epitelidir (§4.2.3).",
        },
    },

    # C003915 — therapy break ≥6mo → restart initial doses with report
    {
        "rule_id": "4.2.3.immunotherapy_break_restart_initial_dose",
        "sut_section": "4.2.3",
        "gate_b_sources": ["C003915"],
        "drug_names": ["immünoterapi", "aşı tedavisi", "alergoid immünoterapi"],
        "report_required": True,
        "action": {
            "enforcement": "mevsim öncesi alergoid hariç aşı tedavisine ≥6 ay ara verilirse, çocukluk/erişkin her dönem için birer kez, tedavi başlangıç tarihi ve başlangıç kriterleri yeni raporda belirtilerek başlangıç dozlarında yeniden başlanır",
            "message_tr": "Mevsim öncesi alergoid immünoterapi hariç, aşı tedavisine 6 ay ya da daha fazla ara verilmesi halinde, çocukluk ve erişkin dönemlerine ait her bir dönem için birer defaya mahsus olmak üzere bu durum ile hastanın tedaviye başladığı tarih ve o tarihteki başlangıç kriterlerinin yeni düzenlenecek raporda belirtilmesi koşuluyla başlangıç dozlarında tedaviye yeniden başlanabilir; ilk reçetelendirme bu uzman hekimlerce yapılır (§4.2.3).",
        },
    },

    # C003916 — continuation prescriptions by listed specialists
    {
        "rule_id": "4.2.3.immunotherapy_continuation_prescribers",
        "sut_section": "4.2.3",
        "gate_b_sources": ["C003916"],
        "drug_names": ["immünoterapi", "alerji aşısı"],
        "report_required": True,
        "prescriber_specialties": [
            "çocuk sağlığı ve hastalıkları", "kulak burun boğaz",
            "göz sağlığı ve hastalıkları", "göğüs hastalıkları",
            "dermatoloji", "iç hastalıkları", "aile hekimliği",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "sağlık kurulu raporuna dayalı tedavi devamı niteliğindeki reçeteler tanısal hekimlerin yanı sıra belirli uzman hekimler/aile hekimi tarafından da yazılabilir",
            "message_tr": "Sağlık kurulu raporuna dayanılarak yapılan tedavinin devamı niteliğindeki diğer reçetelendirmeler, bu hekimlerin yanı sıra çocuk sağlığı ve hastalıkları, kulak burun boğaz, göz sağlığı ve hastalıkları, göğüs hastalıkları, dermatoloji, iç hastalıkları veya aile hekimliği uzman hekimi tarafından da yapılabilir (§4.2.3).",
        },
    },

    # C003918 — no-pay: oral allergy vaccine forms
    {
        "rule_id": "4.2.3.allergy_vaccine_oral_forms_nopay",
        "sut_section": "4.2.3",
        "gate_b_sources": ["C003918"],
        "drug_names": ["alerji aşısı", "immünoterapi"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: alerji aşılarının oral formları ödenmez",
            "message_tr": "Alerji aşılarının oral formları ödenmez (§4.2.3).",
        },
    },

    # C003920 — therapy duration ≤5 years; seasonal pre-season allergoid max 5 lifetime
    {
        "rule_id": "4.2.3.immunotherapy_duration_5yr_seasonal",
        "sut_section": "4.2.3",
        "gate_b_sources": ["C003920"],
        "drug_names": ["aşı tedavisi", "alergoid immünoterapi", "arı venom alerjisi"],
        "report_required": True,
        "action": {
            "enforcement": "arı venom alerjisi hariç aşı tedavileri toplamda 5 yılı geçemez; mevsim öncesi alergoid immünoterapi her yıl polen mevsimi öncesi ömür boyu en fazla 5 defa",
            "message_tr": "Aşı tedavileri, arı venom alerjisi hariç, toplamda 5 yılı geçemez. Mevsim öncesi allergoid immünoterapi her yıl polen mevsimi öncesi dönemde ömür boyu en fazla 5 defaya mahsus olarak yapılabilir (§4.2.3).",
        },
    },

    # C003921 — antidotes for poisoning: paid in full without report
    {
        "rule_id": "4.2.3.poisoning_antidote_full_coverage_no_report",
        "sut_section": "4.2.3",
        "gate_b_sources": ["C003921"],
        "drug_names": ["antidot", "panzehir"],
        "icd10_codes": ["T36", "T37", "T38", "T39", "T40", "T41", "T42", "T43", "T44", "T45", "T50", "T51", "T52", "T53", "T54", "T55", "T56", "T57", "T58", "T59", "T60", "T62", "T65"],
        "report_required": False,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "zehirlenmelerde kullanılan antidotların bedelinin tamamı sağlık raporu aranmaksızın ödenir",
            "message_tr": "Zehirlenmelerde kullanılan antidotların bedelinin tamamı sağlık raporu aranmaksızın ödenir (§4.2.3).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.6.A  —  growth hormone / endocrine (somatropin)
    # -----------------------------------------------------------------

    # C003942 — daily dose stated, max 3-month supply per prescription
    {
        "rule_id": "4.2.6.A.max_3_month_supply_daily_dose",
        "sut_section": "4.2.6.A",
        "gate_b_sources": ["C003942"],
        "drug_names": ["büyüme hormonu", "somatropin"],
        "report_required": True,
        "action": {
            "enforcement": "ilaçların günlük doz miktarı belirtilerek en fazla üçer aylık dozlar halinde reçete edilebilir",
            "message_tr": "İlaçların günlük doz miktarı belirtilmek suretiyle en fazla üçer aylık dozlar halinde reçete edilebilir (§4.2.6.A).",
        },
    },

    # C003977 — neurosecretory dysfunction / bioinactive GH (somatropin only)
    {
        "rule_id": "4.2.6.A1.neurosecretory_bioinactive_gh_somatropin",
        "sut_section": "4.2.6.A-1",
        "gate_b_sources": ["C003977"],
        "drug_names": ["somatropin", "büyüme hormonu"],
        "report_required": True,
        "action": {
            "enforcement": "boy sapması <-2 SD + yıllık uzama hızı yetersiz + kemik yaşı takvim yaşından >2 yıl geri (4 yaş altı/puberte hariç); 2 GH uyarı testine yanıt alınanlarda uyku GH profili; nörosekretuar disfonksiyon veya IGF-1 <-2 SD ise IGF-1 jenerasyon testi ile biyoinaktif GH; yalnızca somatropin",
            "message_tr": "Boy sapması patolojik olan <-2 SD ve yıllık uzama hızı yetersiz kalan, kemik yaşı takvim yaşına göre 2 yıldan daha fazla geri olan (4 yaş altı veya puberte dönemi hariç), yapılan 2 büyüme hormonu uyarı testine yeterli yanıt alınan hastalara uyku esnasında büyüme hormonu profili çıkartılmalı; nörosekretuar disfonksiyon veya serum IGF-1 <-2 SD olması koşuluyla yapılacak IGF-1 jenerasyon testi ile biyoinaktif büyüme hormonu saptanması halinde (yalnızca somatropin) kullanılabilir (§4.2.6.A-1).",
        },
    },

    # C003979 — somatropin use without further condition in listed cases
    {
        "rule_id": "4.2.6.A1.somatropin_listed_cases_no_condition",
        "sut_section": "4.2.6.A-1",
        "gate_b_sources": ["C003979"],
        "drug_names": ["somatropin", "büyüme hormonu"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "bu bendin uygulanmasında başkaca şart aranmaksızın belirtilen hallerde yalnızca somatropin kullanılabilir",
            "message_tr": "Bu bendin uygulanmasında başkaca şart aranmaksızın aşağıdaki hallerde yalnızca somatropin etkin maddeli ilaçlar kullanılabilir (§4.2.6.A-1).",
        },
    },

    # C003997 — insulin tolerance test peak GH <3 mcg/L must be in report
    {
        "rule_id": "4.2.6.A2.insulin_tolerance_test_peak_gh_report",
        "sut_section": "4.2.6.A-2",
        "gate_b_sources": ["C003997"],
        "drug_names": ["somatropin", "büyüme hormonu"],
        "report_required": True,
        "action": {
            "enforcement": "insülin tolerans testine göre GH eksikliği tanısı için pik GH cevabının <3 mcg/L olduğunun raporda belirtilmesi gereklidir",
            "message_tr": "İnsülin tolerans testine göre büyüme hormonu eksikliği tanısı için pik büyüme hormonu cevabının 3 mcg/L'den küçük olduğunun raporda belirtilmesi gereklidir (§4.2.6.A-2).",
        },
    },

    # C004013 — Prader-Willi syndrome: GH without stimulation test
    {
        "rule_id": "4.2.6.A4.prader_willi_gh_no_stimulation_test",
        "sut_section": "4.2.6.A-4",
        "gate_b_sources": ["C004013"],
        "drug_names": ["somatropin", "büyüme hormonu"],
        "icd10_codes": ["Q87.1"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "genetik Prader-Willi tanılı epifiz hatları açık çocuklarda GH uyarı testi aranmaksızın koşullar sağlanırsa GH ödenir",
            "message_tr": "Genetik olarak Prader-Willi sendromu tanısı almış epifiz hatları açık olan çocuklarda büyüme hormonu uyarı testi yapılması koşulu aranmaksızın aşağıdaki durumlarda büyüme hormonu tedavisine başlanması halinde bedelleri Kurumca karşılanır (§4.2.6.A-4).",
        },
    },

    # C004024 — chronic kidney disease stage III-V / dialysis children GH
    {
        "rule_id": "4.2.6.A5.ckd_dialysis_children_gh_coverage",
        "sut_section": "4.2.6.A-5",
        "gate_b_sources": ["C004024"],
        "drug_names": ["somatropin", "büyüme hormonu"],
        "icd10_codes": ["N18", "N18.3", "N18.4", "N18.5", "Z99.2"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "KBY evre III-V veya >6 ay diyaliz, epifiz hatları açık, PTH<500 pg/ml; malnutrisyon/asidoz/sıvı-elektrolit dengesizliği/anemi yoksa koşullar sağlandığında GH ödenir",
            "message_tr": "KBY evresi evre III, IV, V olan veya 6 aydan fazla süredir diyalizde olan, epifiz hatları açık olan, paratiroid hormonu 500 pikogram(pg)/ml altında olan çocuk hastalarda; malnutrisyonu, metabolik asidozu, sıvı elektrolit dengesizliği, anemisi olmaması ve aşağıdaki koşulların sağlanması durumunda büyüme hormonu tedavisine başlanması halinde bedelleri Kurumca karşılanır (§4.2.6.A-5).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.7  —  heparins / LMWH
    # -----------------------------------------------------------------

    # C004053 — LMWH up to 6mo single report; >6mo health-board; pregnancy 10mo
    {
        "rule_id": "4.2.7.lmwh_6mo_report_extended_pregnancy",
        "sut_section": "4.2.7",
        "gate_b_sources": ["C004053"],
        "drug_names": ["düşük molekül ağırlıklı heparin", "heparin"],
        "report_required": True,
        "report_duration_months": 6,
        "prescriber_specialties": [
            "onkoloji", "hematoloji", "kalp damar cerrahisi", "kardiyoloji",
            "göğüs hastalıkları", "iç hastalıkları", "genel cerrahi",
            "nöroloji", "kadın hastalıkları ve doğum",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "≤6 ay süreli ilaç dozunu gösteren uzman hekim raporuyla başlanır, tüm hekimlerce reçete; >6 ay kullanımda listede uzmanı bulunan sağlık kurulu raporu; gebelerde kadın doğum uzmanınca 10 ay süreli uzman raporu",
            "message_tr": "Uzman hekim tarafından düzenlenen en fazla 6 ay süreli kullanılacak ilacın dozunu gösteren uzman hekim raporuna dayanılarak tedaviye başlanır ve tüm hekimler tarafından reçete edilebilir. Düşük molekül ağırlıklı heparinlerin 6 aydan daha uzun sürede kullanımında ilgili uzman hekimlerin bulunduğu sağlık kurulu raporu gereklidir; gebelerde kadın hastalıkları ve doğum uzman hekimince düzenlenen 10 ay süreli uzman hekim raporuyla reçete edilirse bedeli Kurumca karşılanır (§4.2.7).",
        },
    },

    # C004054 — inpatients / emergencies: report not required
    {
        "rule_id": "4.2.7.inpatient_emergency_no_report",
        "sut_section": "4.2.7",
        "gate_b_sources": ["C004054"],
        "drug_names": ["düşük molekül ağırlıklı heparin", "heparin"],
        "report_required": False,
        "action": {
            "enforcement": "yatan hastalarda veya acil müdahale gerektiren durumlarda acil servislerde rapor aranmaksızın tüm hekimler tarafından reçete edilebilir",
            "message_tr": "Yatan hastalarda veya acil müdahale gerektiren durumlarda acil servislerde rapor aranmaksızın tüm hekimler tarafından reçete edilebilir (§4.2.7).",
        },
    },

    # C004055 — no-pay: hemodialysis heparins bundled in procedure
    {
        "rule_id": "4.2.7.hemodialysis_heparin_nopay",
        "sut_section": "4.2.7",
        "gate_b_sources": ["C004055"],
        "drug_names": ["heparin", "düşük molekül ağırlıklı heparin"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: hemodiyaliz tedavilerinde heparinler tanıya dayalı işlem puanına dahil olduğu için reçete edilse dahi ödenmez",
            "message_tr": "Hemodiyaliz tedavilerinde, heparinler tanıya dayalı işlem puanına dahil olduğundan reçete edilse dahi bedeli ödenmez (§4.2.7).",
        },
    },

    # C004057 — no-pay: combination of different LMWH active substances
    {
        "rule_id": "4.2.7.lmwh_different_active_combo_nopay",
        "sut_section": "4.2.7",
        "gate_b_sources": ["C004057"],
        "drug_names": ["düşük molekül ağırlıklı heparin"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: farklı etken maddeli düşük molekül ağırlıklı heparinlerin birlikte kullanımı",
            "message_tr": "Farklı etken maddeli düşük molekül ağırlıklı heparinlerin birlikte kullanılması halinde bedelleri Kurumca karşılanmaz (§4.2.7).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.10.A-3 / 4.2.10.B  —  Fabry / lysosomal storage (migalastat etc.)
    # -----------------------------------------------------------------

    # C004254 — therapy continuation: improvement documented, break re-eligibility
    {
        "rule_id": "4.2.10.A3.continuation_improvement_break_reeligibility",
        "sut_section": "4.2.10.A-3",
        "gate_b_sources": ["C004254"],
        "report_required": True,
        "action": {
            "enforcement": "düzelmeye devam kararı verilenlerde yeni raporda başlangıç kriterlerinden birinde düzelme belirtilirse tedaviye devam; ≥1 yıl ara verilirse başlangıç kriterleri yeniden aranır; <1 yıl ara verilirse başlangıç kriterleri aranmaksızın devam",
            "message_tr": "Tedavide düzelme sağlanan ve ilacın kullanımına devam edilmesine karar verilen hastalarda; düzenlenecek yeni raporlarda başlangıç kriterlerinden herhangi birinde düzelme olduğu belirtilirse tedaviye devam edilebilir. Bir yıl veya daha uzun süreyle ara verilirse başlangıç kriterleri aranır; bir yıldan kısa süreyle ara verilirse başlangıç kriterleri aranmaksızın tedaviye devam edilebilir (§4.2.10.A-3).",
        },
    },

    # C004296 — only MoH-approved KÜB mutations are evaluated
    {
        "rule_id": "4.2.10.B2.moh_kub_mutations_evaluated",
        "sut_section": "4.2.10.B-2",
        "gate_b_sources": ["C004296"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "sağlık bakanlığınca onaylı kısa ürün bilgisinde uygunluğu kabul edilen mutasyonlar değerlendirmeye alınır",
            "message_tr": "Sağlık Bakanlığınca onaylı kısa ürün bilgisinde uygunluğu kabul edilen mutasyonlar değerlendirmeye alınır (§4.2.10.B-2).",
        },
    },

    # C004303 — prohibited: therapy change within <6 months unless medical reason
    {
        "rule_id": "4.2.10.B3.no_change_within_6mo",
        "sut_section": "4.2.10.B-3",
        "gate_b_sources": ["C004303"],
        "report_required": True,
        "action": {
            "enforcement": "tedavi seçenekleri arasında 6 aydan kısa sürede değişim yapılamaz; 6 aydan kısa geçişte (anaflaksi/ilaç reaksiyonu gibi) tıbbi gerekçe yeni raporda belirtilmelidir",
            "message_tr": "Tedavi seçenekleri arasında 6 aydan daha kısa sürede değişim yapılamaz. 6 aydan daha kısa sürede tedavi seçenekleri arasında geçiş yapılması halinde yeni düzenlenecek raporda tıbbi gerekçenin (anaflaksi veya ilaç reaksiyonu gibi) belirtilmesi gerekmektedir (§4.2.10.B-3).",
        },
    },

    # C004304 — prohibited: enzyme therapy + oral migalastat combination
    {
        "rule_id": "4.2.10.B3.enzyme_migalastat_combo_nopay",
        "sut_section": "4.2.10.B-3",
        "gate_b_sources": ["C004304"],
        "drug_names": ["enzim tedavisi", "migalastat", "agalsidaz"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: enzim tedavisi ile oral migalastat tedavisinin kombine kullanımı",
            "message_tr": "Enzim tedavisi ile oral migalastat tedavisi kombine olarak kullanılamaz (§4.2.10.B-3).",
        },
    },

    # C004348 — mandatory: ≥2 compatible analyses + MS exclusion in report
    {
        "rule_id": "4.2.10.C1.two_compatible_analyses_ms_exclusion",
        "sut_section": "4.2.10.C-1",
        "gate_b_sources": ["C004348"],
        "report_required": True,
        "action": {
            "enforcement": "analiz sonuçlarından en az ikisi hastalıkla uyumlu olmalı ve raporda belirtilmeli; Tip II, IVA, VI hastalarında multiple sülfataz eksikliği enzimatik/moleküler genetik ile dışlanmış olmalıdır",
            "message_tr": "Belirtilen analiz sonuçlarından en az ikisinin hastalıkla uyumlu olması ve ilaç raporunda sonuçların belirtilmesi gerekmektedir. Tip II, IVA ve VI hastalarında multiple sülfataz eksikliği enzimatik ya da moleküler genetik analiz sonuçları ile dışlanmış olmalıdır (§4.2.10.C-1).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.16  —  metabolic / endocrine / nutritional products
    # -----------------------------------------------------------------

    # C005984 — 3-year endocrinology/metabolism/gastro report, all physicians prescribe
    {
        "rule_id": "4.2.16.adult_metabolic_3yr_report_all_prescribe",
        "sut_section": "4.2.16",
        "gate_b_sources": ["C005984"],
        "report_required": True,
        "report_duration_months": 36,
        "report_specialties": ["endokrinoloji ve metabolizma hastalıkları", "gastroenteroloji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "erişkin endokrinoloji/metabolizma veya gastroenteroloji uzmanınca (yoksa iç hastalıkları) düzenlenen 3 yıl süreli uzman raporuyla tüm hekimlerce reçete edilebilir",
            "message_tr": "Erişkin endokrinoloji ve metabolizma hastalıkları ya da erişkin gastroenteroloji uzman hekimi tarafından, bu uzman hekimlerin bulunmadığı hastanelerde iç hastalıkları uzman hekimlerince düzenlenen 3 yıl süreli uzman hekim raporuna dayanılarak tüm hekimler tarafından reçete edilebilir (§4.2.16).",
        },
    },

    # C005985 — glycoprotein starch products ≥2yr, max 4 boxes/month
    {
        "rule_id": "4.2.16.glycogen_starch_products_2yr_4boxes",
        "sut_section": "4.2.16",
        "gate_b_sources": ["C005985"],
        "drug_names": ["yüksek amilopektin içeren nişastalı ürün"],
        "report_required": True,
        "report_specialties": ["çocuk metabolizma hastalıkları", "gastroenteroloji", "çocuk sağlığı ve hastalıkları"],
        "prescriber_specialties": ["çocuk metabolizma hastalıkları", "çocuk sağlığı ve hastalıkları", "gastroenteroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "glikojen depo hastalığı diyetinde yüksek amilopektinli nişasta ürünleri; ≥2 yaş, ilgili uzman raporuyla reçete; raporda ürün adı/günlük miktar, aylık en fazla 4 kutu",
            "message_tr": "Glikojen depo hastalığının diyet yönetiminde kullanılan yüksek amilopektin içeren nişastalı ürünler; 2 yaş ve üzerindeki hastalarda ilgili uzmanın bulunduğu sağlık kurulu raporuna dayanılarak ilgili uzmanlarca reçete edilebilir; raporda ürünün adı, günlük kullanım miktarı belirtilerek aylık en fazla dört kutu yazılır (§4.2.16).",
        },
    },

    # C005998 — coverage: amount paid
    {
        "rule_id": "4.2.16.amount_paid_coverage_a",
        "sut_section": "4.2.16",
        "gate_b_sources": ["C005998"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "tutar Kurumca ödenir",
            "message_tr": "Tutar Kurumca ödenir (§4.2.16).",
        },
    },

    # C006011 — coverage: amount paid
    {
        "rule_id": "4.2.16.amount_paid_coverage_b",
        "sut_section": "4.2.16",
        "gate_b_sources": ["C006011"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "tutar Kurumca ödenir",
            "message_tr": "Tutar Kurumca ödenir (§4.2.16).",
        },
    },

    # C006012 — CKD stage 2-5 children, height/weight SDS ≤-1; stop if height SDS→0
    {
        "rule_id": "4.2.16.ckd_children_growth_sds_3bottles",
        "sut_section": "4.2.16",
        "gate_b_sources": ["C006012"],
        "icd10_codes": ["N18", "N18.2", "N18.3", "N18.4", "N18.5"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["pediyatrik nefroloji"],
        "prescriber_specialties": ["pediyatrik nefroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "KBY evre 2-5, ≥3 yaş, boy/kilo SDS ≤-1; 6 ay süreli pediyatrik nefroloji raporuyla günlük en fazla 3 şişe; boy SDS sıfıra yükselip 6 ay bu düzeyde seyrederse tedavi kesilir",
            "message_tr": "Kronik böbrek hastalığı (evre 2-5) tanısı olan 3 yaş ve üzeri ve boy SDS ve/veya kilo SDS -1 ve altında olan çocuklarda; 6 ay süreli pediyatrik nefroloji uzman hekim raporuna istinaden pediyatrik nefroloji uzman hekimi tarafından günlük en fazla 3 şişe reçete edilmesi halinde bedeli Kurumca karşılanır. Boy SDS değeri sıfıra yükselip altı ay süre bu düzeyde seyretmesi halinde tedavi kesilir (§4.2.16).",
        },
    },

    # C006013 — no-pay: products not on EK-4/B list
    {
        "rule_id": "4.2.16.ek4b_unlisted_products_nopay",
        "sut_section": "4.2.16",
        "gate_b_sources": ["C006013"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: ilgili hastalıklarda EK-4/B listesinde yer almayan ürün bedelleri ödenmez",
            "message_tr": "Yukarıda belirtilen hastalıklarda kullanılan ürünler EK-4/B Listesinde belirtilmiş olup bu listede yer almayan ürün bedelleri Kurumca karşılanmaz (§4.2.16).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.17.A  —  osteoporosis
    # -----------------------------------------------------------------

    # C006018 — bisphosphonates/osteoporosis drugs: 2-yr report, combo only one paid
    {
        "rule_id": "4.2.17.A.osteoporosis_2yr_report_combo_one_paid",
        "sut_section": "4.2.17.A",
        "gate_b_sources": ["C006018"],
        "drug_names": ["bifosfonat", "raloksifen", "calcitonin", "stronsiyum ranelat", "denosumab"],
        "icd10_codes": ["M80", "M81"],
        "report_required": True,
        "report_duration_months": 24,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "bifosfonatlar ve diğer osteoporoz ilaçları tanımlı koşullarda ödenir; tedavi süresinin belirtildiği 2 yıllık sağlık raporu gerekir; kombine kullanımda yalnızca birinin bedeli ödenir",
            "message_tr": "Osteoporoz tedavisinde bifosfonatlar (kombinasyonları dahil) ve diğer osteoporoz ilaçları (raloksifen, calcitonin, stronsiyum ranelat, denosumab) belirtilen koşullarda ödenir. Bu ilaçlar tedavi süresinin belirtildiği sağlık raporuna dayanılarak reçete edilir; rapor süresi 2 yıldır. Bu grup ilaçların kombine kullanımında sadece birinin bedeli ödenir (§4.2.17.A).",
        },
    },

    # C006035 — hormone-ablation/prostate-breast cancer high-fracture osteoporosis
    {
        "rule_id": "4.2.17.A.hormone_ablation_cancer_high_fracture",
        "sut_section": "4.2.17.A",
        "gate_b_sources": ["C006035"],
        "drug_names": ["bifosfonat", "denosumab", "raloksifen"],
        "icd10_codes": ["M80", "M81", "C50", "C61"],
        "report_required": True,
        "report_specialties": ["tıbbi onkoloji"],
        "prescriber_specialties": ["tüm uzman hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "hormon ablasyonu uygulanmış nonmetastatik prostat kanserli veya meme kanseri nedeniyle adjuvan aromataz inhibitörü alan yüksek kırk riskli hastalarda osteoporoz; en az bir tıbbi onkoloji uzmanı yer alan sağlık kurulu raporuyla tüm uzman hekimlerce reçete",
            "message_tr": "Hormon ablasyonu uygulanmış olan nonmetastatik prostat kanserli veya meme kanseri nedeniyle adjuvan aromataz inhibitörü tedavisi gören yüksek kırık riskine sahip hastalardaki osteoporoz tedavisinde; bu durumun belirtildiği en az bir tıbbi onkoloji uzman hekiminin yer aldığı sağlık kurulu raporuna dayanılarak tüm uzman hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.17.A).",
        },
    },

    # C006042 — no-pay: active vitamin D (calcitriol/alfacalcidol) in osteoporosis
    {
        "rule_id": "4.2.17.A.active_vitamin_d_osteoporosis_nopay",
        "sut_section": "4.2.17.A",
        "gate_b_sources": ["C006042"],
        "drug_names": ["kalsitriol", "alfakalsidol"],
        "icd10_codes": ["M80", "M81"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: aktif D vitaminleri (kalsitriol ve alfakalsidol) osteoporoz tedavisinde ödenmez (EK-4/D düzenlemeleri hariç)",
            "message_tr": "Aktif D vitaminleri (kalsitriol ve alfakalsidol) osteoporoz tedavisinde ödenmez (EK-4/D Listesindeki düzenlemeler hariç) (§4.2.17.A).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.17.B / 4.2.17.D
    # -----------------------------------------------------------------

    # C006044 — calcitonin first 6mo after diagnosis, then no-pay
    {
        "rule_id": "4.2.17.B.calcitonin_first_6mo_only",
        "sut_section": "4.2.17.B",
        "gate_b_sources": ["C006044"],
        "drug_names": ["kalsitonin", "calcitonin"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["fiziksel tıp ve rehabilitasyon", "ortopedi ve travmatoloji", "romatoloji"],
        "prescriber_specialties": ["fiziksel tıp ve rehabilitasyon", "ortopedi ve travmatoloji", "romatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kalsitonin tanı sonrası ilk 6 ay ilgili uzman raporuyla ödenir; bu sürenin üstündeki kullanım ödenmez",
            "message_tr": "Kalsitonin bu endikasyonda tanı konulduktan sonraki ilk altı ay süresince fiziksel tıp ve rehabilitasyon veya ortopedi ve travmatoloji veya romatoloji uzman hekim raporuna dayanılarak bu uzman hekimlerce reçete edilir. Bu sürenin üstündeki kullanımı ödenmez (§4.2.17.B).",
        },
    },

    # C006054 — 24-week response: teriparatide 52wk/romosozumab 6mo; lifetime caps
    {
        "rule_id": "4.2.17.D.week24_response_teriparatide_romosozumab",
        "sut_section": "4.2.17.D",
        "gate_b_sources": ["C006054"],
        "drug_names": ["teriparatid", "romosozumab"],
        "icd10_codes": ["M80", "M81"],
        "report_required": True,
        "action": {
            "enforcement": "24. hafta yanıt değerlendirmesi; yanıt verene teriparatid için 52 haftalık, romosozumab için 6 aylık yeni raporla devam; teriparatid ömür boyu toplam 76 hafta, romosozumab 12 ay sınırını geçemez",
            "message_tr": "24 hafta sonunda yanıt değerlendirmesi yapılır. Tedaviye yanıt veren hastalarda bu durumun kanıtlandığı raporla teriparatid için 52 hafta, romosozumab için 6 ay süreli yeni bir sağlık kurulu raporu düzenlenmesi halinde tedaviye devam edilebilir. Teriparatid ile toplam tedavi süresi ömür boyu 76 haftayı, romosozumab ile 12 ayı geçmeyecektir (§4.2.17.D).",
        },
    },

    # C006055 — BMD measurement max twice yearly on teriparatide/romosozumab
    {
        "rule_id": "4.2.17.D.bmd_measurement_twice_yearly",
        "sut_section": "4.2.17.D",
        "gate_b_sources": ["C006055"],
        "drug_names": ["teriparatid", "romosozumab"],
        "icd10_codes": ["M80", "M81"],
        "action": {
            "enforcement": "teriparatid veya romosozumab kullananlarda kemik mineral yoğunluğu ölçümü yılda 2 kez yapılabilir",
            "message_tr": "Teriparatid veya romosozumab kullanan hastalarda kemik mineral yoğunluğu ölçümü yılda 2 kez yapılabilir (§4.2.17.D).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.23  —  systemic antifungals (azoles)
    # -----------------------------------------------------------------

    # C006090 — coverage: systemic fungal infection treatment paid
    {
        "rule_id": "4.2.23.systemic_fungal_infection_coverage",
        "sut_section": "4.2.23",
        "gate_b_sources": ["C006090"],
        "drug_names": ["itrakonazol", "posakonazol", "vorikonazol", "flukonazol", "kasopofungin", "anidulafungin", "mikafungin"],
        "icd10_codes": ["B37", "B44", "B45", "B49", "B40", "B43"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "bu maddedeki etken maddeli ilaçların sistemik mantar enfeksiyonları tedavisinde kullanımı bedelleri Kurumca karşılanır",
            "message_tr": "Bu maddede belirtilen etken maddeli ilaçların sistemik mantar enfeksiyonları tedavisinde kullanılması halinde bedelleri Kurumca karşılanır (§4.2.23).",
        },
    },

    # C006094 — itraconazole oral forms per EK-4/E 10.5
    {
        "rule_id": "4.2.23.itraconazole_oral_ek4e_105",
        "sut_section": "4.2.23",
        "gate_b_sources": ["C006094"],
        "drug_names": ["itrakonazol"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "itrakonazol'ün oral formları (solüsyon hariç) SUT eki EK-4/E 10.5 maddesinde belirtildiği şekilde reçetelenir",
            "message_tr": "Itrakonazol'ün oral formları (solüsyon formları hariç), SUT eki Sistemik Antimikrobik ve Diğer İlaçların Reçeteleme Kuralları Listesi'nin (EK-4/E) 10.5 maddesinde belirtildiği şekilde reçetelenebilecektir (§4.2.23).",
        },
    },

    # C006096 — posaconazole parenteral only if oral cannot be used
    {
        "rule_id": "4.2.23.posaconazole_parenteral_oral_unable",
        "sut_section": "4.2.23",
        "gate_b_sources": ["C006096"],
        "drug_names": ["posakonazol"],
        "report_required": True,
        "action": {
            "enforcement": "posakonazol'ün parenteral formları yalnızca oral formlarını kullanamayan hastalarda kullanılabilir; invazif mantar enfeksiyonu profilaksisi endikasyonu",
            "message_tr": "Belirtilen hastalardaki invazif mantar enfeksiyonlarının profilaksisinde kullanılır. Posakonazol'ün parenteral formları yalnızca oral formlarını kullanamayan hastalarda kullanılabilir (§4.2.23).",
        },
    },

    # C006116 — no-pay: aspergillosis/candida prophylaxis in expected ≥10-day neutropenia
    {
        "rule_id": "4.2.23.neutropenia_prophylaxis_nopay",
        "sut_section": "4.2.23",
        "gate_b_sources": ["C006116"],
        "drug_names": ["posakonazol", "itrakonazol", "vorikonazol", "flukonazol"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: 10 gün veya daha uzun süreyle nötropeni olması beklenen diğer hastalarda aspergilloz ve candida enfeksiyonlarının profilaksisi endikasyonunda ödenmez",
            "message_tr": "10 gün veya daha uzun süreyle nötropeni olması beklenen diğer hastalarda aspergilloz ve candida enfeksiyonlarının profilaksisi endikasyonunda ödenmez (§4.2.23).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.25  —  antiepileptics
    # -----------------------------------------------------------------

    # C006198 — new-gen antiepileptics (lamotrigine etc.) neurology/neurosurgery
    {
        "rule_id": "4.2.25.new_gen_antiepileptics_coverage",
        "sut_section": "4.2.25",
        "gate_b_sources": ["C006198"],
        "drug_names": ["lamotrigin", "topiramat", "vigabatrin", "levatirasetam", "levetirasetam"],
        "icd10_codes": ["G40"],
        "report_required": True,
        "report_specialties": ["nöroloji", "beyin cerrahisi"],
        "prescriber_specialties": ["tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yeni nesil antiepileptikler nöroloji/beyin cerrahisi uzmanınca veya bu uzmanlardan birinin düzenlediği uzman raporuyla tüm hekimlerce reçete edilirse ödenir",
            "message_tr": "Yeni nesil antiepileptiklerin (lamotrigin, topiramat, vigabatrin, levatirasetam) nöroloji veya beyin cerrahisi uzman hekimleri tarafından veya bu uzman hekimlerden biri tarafından düzenlenen uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.25).",
        },
    },

    # C006199 — zonisamide: neurology 1-yr report
    {
        "rule_id": "4.2.25.zonisamide_neurology_1yr_report",
        "sut_section": "4.2.25",
        "gate_b_sources": ["C006199"],
        "drug_names": ["zonisamit", "zonisamid"],
        "icd10_codes": ["G40"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "zonisamit nöroloji uzmanlarınca veya nöroloji uzmanınca düzenlenen 1 yıl süreli raporla tüm hekimlerce reçete edilirse ödenir",
            "message_tr": "Zonisamit etken maddeli ilaçların nöroloji uzman hekimleri tarafından veya bu uzman hekimler tarafından düzenlenen 1 yıl süreli uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.25).",
        },
    },

    # C006200 — pregabalin: 1-yr report, no generalized anxiety disorder pay
    {
        "rule_id": "4.2.25.pregabalin_1yr_report_no_gad",
        "sut_section": "4.2.25",
        "gate_b_sources": ["C006200"],
        "drug_names": ["pregabalin"],
        "icd10_codes": ["G40"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "pregabalin mono/sabit doz kombinasyonları 2/3. basamakta en az bir nöroloji uzmanı içeren 1 yıllık sağlık kurulu raporuyla nöroloji uzmanlarınca reçete edilirse ödenir; yaygın anksiyete bozukluğu endikasyonunda ödenmez",
            "message_tr": "Pregabalin etken maddeli ilaçların mono veya sabit doz kombinasyonlarının ikinci veya üçüncü basamak sağlık hizmeti sunucularında düzenlenen en az bir nöroloji uzman hekiminin yer aldığı 1 yıl süreli sağlık kurulu raporuna istinaden nöroloji uzman hekimlerince reçete edilmesi halinde bedelleri Kurumca karşılanır; yaygın anksiyete bozukluğu endikasyonunda ödenmez (§4.2.25).",
        },
    },

    # C006202 — lacosamide: ≥16yr partial epilepsy after ≥2 AEDs 6mo
    {
        "rule_id": "4.2.25.lacosamide_16yr_partial_2aed_6mo",
        "sut_section": "4.2.25",
        "gate_b_sources": ["C006202"],
        "drug_names": ["lakozamid", "lacosamide"],
        "icd10_codes": ["G40"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "16 yaş ve üzeri parsiyel başlangıçlı epilepside (ikincil jeneralize olan/olmayan) en az 2 antiepileptik tek/kombine 6 ay kullanıp yanıtsız olana ek tedavi/monoterapi; nöroloji uzman raporuyla tüm uzmanlarca reçete",
            "message_tr": "Lakozamid; 16 yaş ve üzerindeki parsiyel başlangıçlı epilepsi hastalarında ikincil jeneralize olan veya olmayan nöbetlerin tedavisinde, en az iki antiepileptik ilacın en az 6 ay süreyle tek başına veya kombine kullanımından sonra tedaviye yanıt alınamayan hastalarda ek tedavi veya monoterapi olarak, bu durumların belirtildiği nöroloji uzman hekim raporuna dayanılarak tüm uzman hekimlerce reçete edilebilir (§4.2.25).",
        },
    },

    # C006204 — gabapentin 1-yr report; pregabalin+gabapentin combo no-pay
    {
        "rule_id": "4.2.25.gabapentin_1yr_report_combo_nopay",
        "sut_section": "4.2.25",
        "gate_b_sources": ["C006204"],
        "drug_names": ["gabapentin", "pregabalin"],
        "icd10_codes": ["G40"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "gabapentin 2/3. basamakta en az bir nöroloji uzmanı içeren 1 yıllık sağlık kurulu raporuyla nöroloji uzmanlarınca reçete edilirse ödenir; pregabalin ve gabapentin kombine kullanılamaz",
            "message_tr": "Gabapentin etken maddeli ilaçların ikinci veya üçüncü basamak sağlık hizmeti sunucularında düzenlenen en az bir nöroloji uzman hekiminin yer aldığı 1 yıl süreli sağlık kurulu raporuna istinaden nöroloji uzman hekimlerince reçete edilmesi halinde bedelleri Kurumca karşılanır. Pregabalin ve gabapentin kombine olarak kullanılamaz (§4.2.25).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.32  —  contrast media
    # -----------------------------------------------------------------

    # C006449 — non-ionic iodinated contrast: 1 box coverage / >1 box criteria
    {
        "rule_id": "4.2.32.nonionic_iodinated_contrast_coverage",
        "sut_section": "4.2.32",
        "gate_b_sources": ["C006449"],
        "drug_names": ["non-iyonik iyotlu kontrast madde", "non-iyonik radyo-opak madde"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "ayakta İVP/HSG/nonvasküler girişimsel/üretral/sistografi gibi tetkiklerde 1 kutu non-iyonik radyo-opak madde ödenir; BT/BT anjiyo/DSA/anjiyo veya aşırı kilolularda 1 kutuyu aşan dozda gerekçe reçetede belirtilirse ödenir",
            "message_tr": "Non-iyonik iyotlu kontrast maddelerin; ayakta yapılan İVP ve HSG, nonvasküler girişimsel işlemler, üretrografi, sistografi, voiding sistoüretrograki gibi tetkiklerde bir kutu kullanılması halinde bedelleri Kurumca karşılanır. BT, BT anjiyografi, DSA, anjiografi tetkiklerinde veya aşırı kilolu hastalarda bir kutuyu aşan dozda gerekmesi halinde gerekçesi reçeteye yazılır (§4.2.32).",
        },
    },

    # C006450 — gadoxetate: liver/biliary MR cholangiography max 1 box
    {
        "rule_id": "4.2.32.gadoxetate_liver_mr_max_1box",
        "sut_section": "4.2.32",
        "gate_b_sources": ["C006450"],
        "drug_names": ["gadoksetat", "gadoxetat"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "gadoksetat yalnızca karaciğer ve safra yolları MR kolanjiografi (kontrastlı) incelemelerinde; reçeteye en fazla 1 kutu yazılırsa ödenir",
            "message_tr": "Gadoksetat; sadece karaciğer ve safra yolları manyetik rezonans kolanjiografi (kontrastlı) incelemelerinde kullanılır. Reçeteye en fazla 1 kutu yazılması halinde bedeli Kurumca karşılanır (§4.2.32).",
        },
    },

    # C006451 — gadobutrol >15 ml: reason on prescription
    {
        "rule_id": "4.2.32.gadobutrol_over_15ml_reason",
        "sut_section": "4.2.32",
        "gate_b_sources": ["C006451"],
        "drug_names": ["gadobutrol"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "gadobutrol 15 ml'yi aşan (aşırı kilo, MR, MR anjiyografi gibi) durumlarda gerekçe reçeteye yazılırsa ödenir",
            "message_tr": "Gadobutrol 15 ml'yi aşan durumlarda (aşırı kilo, Manyetik Rezonans, MR anjiyografi gibi) gerekçesinin reçeteye yazılması halinde bedeli Kurumca karşılanır (§4.2.32).",
        },
    },

    # C006452 — gadoteric acid 0.1 mmol/kg standard; >standard max 2 boxes
    {
        "rule_id": "4.2.32.gadoteric_acid_standard_overdose_2boxes",
        "sut_section": "4.2.32",
        "gate_b_sources": ["C006452"],
        "drug_names": ["gadoterik asit"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "gadoterik asit standart 0,1 mmol/kg (0,2 ml/kg) dozda 1 kutu; standart dozu aşan durumlarda gerekçe reçetede, en fazla 2 kutu yazılırsa ödenir",
            "message_tr": "Gadoterik asit standart 0,1 mmol/kg (0,2 ml/kg) uygun dozda 1 kutu reçete edilir. Standart dozu aşan durumlarda gerekçesinin reçeteye yazılması halinde en fazla 2 kutu yazılması halinde bedeli Kurumca karşılanır (§4.2.32).",
        },
    },

    # C006453 — iodized fatty acid esters: lymphography / adult HCC TACE
    {
        "rule_id": "4.2.32.iodized_fatty_acid_lymphography_tace",
        "sut_section": "4.2.32",
        "gate_b_sources": ["C006453"],
        "drug_names": ["iyodize yağ asitleri etil esterleri", "lipiodol"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "iyodize yağ asitleri etil esterleri tanısal radyolojide yalnızca lenfografide, girişimsel radyolojide yalnızca erişkin orta evre HCC'de TAKE sırasında vasküler embolizasyon endikasyonunda ödenir",
            "message_tr": "İyodize yağ asitleri etil esterleri; tanısal radyolojide yalnızca lenfografide, girişimsel radyolojide ise yalnızca erişkinlerde orta evredeki hepatoselüler karsinomun Trans Arteriyel Kemo Embolizasyonu sırasında vektorizasyon ve cerrahi yapıştırıcılar ile birlikte vasküler embolizasyon endikasyonlarında kullanılması halinde bedeli Kurumca karşılanır (§4.2.32).",
        },
    },

    # C006454 — iodized fatty acid esters: interventional radiology prescriber
    {
        "rule_id": "4.2.32.iodized_fatty_acid_interventional_radiology",
        "sut_section": "4.2.32",
        "gate_b_sources": ["C006454"],
        "drug_names": ["iyodize yağ asitleri etil esterleri", "lipiodol"],
        "report_required": True,
        "prescriber_specialties": ["radyoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "reçeteye ön tanı/tetkik isteyen uzman veya radyoloji uzmanınca yazılırsa ödenir; iyodize yağ asitleri etil esterleri yalnızca girişimsel radyoloji işlemini yapan radyoloji uzmanlarınca reçete edilebilir",
            "message_tr": "Reçeteye ön tanı ve istenilen tetkik, tetkiki isteyen uzman hekim veya radyoloji uzman hekimi tarafından yazılması halinde bedeli Kurumca karşılanır. İyodize yağ asitleri etil esterleri yalnızca girişimsel radyoloji işlemini yapan radyoloji uzman hekimlerince reçete edilebilir (§4.2.32).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.35.A  —  neuropathic pain (gabapentin/pregabalin/capsaicin)
    # -----------------------------------------------------------------

    # C006692 — gabapentin 6-mo report; pregabalin+gabapentin combo no-pay
    {
        "rule_id": "4.2.35.A.gabapentin_6mo_report_combo_nopay",
        "sut_section": "4.2.35.A",
        "gate_b_sources": ["C006692"],
        "drug_names": ["gabapentin", "pregabalin"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": [
            "nöroloji", "beyin cerrahisi", "fiziksel tıp ve rehabilitasyon",
            "algoloji", "deri ve zührevi hastalıkları", "romatoloji",
            "ortopedi ve travmatoloji", "geriatri",
            "endokrinoloji ve metabolizma hastalıkları",
        ],
        "prescriber_specialties": [
            "nöroloji", "beyin cerrahisi", "fiziksel tıp ve rehabilitasyon",
            "algoloji", "deri ve zührevi hastalıkları", "romatoloji",
            "ortopedi ve travmatoloji", "geriatri",
            "endokrinoloji ve metabolizma hastalıkları",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "gabapentin 2/3. basamakta ilgili uzmanlardan en az birinin yer aldığı 6 ay süreli sağlık kurulu raporuyla bu hekimlerce reçete edilirse ödenir; pregabalin ve gabapentin kombine kullanılamaz",
            "message_tr": "Gabapentin etken maddeli ilaçların ilgili uzman hekimlerden en az birinin yer aldığı ikinci veya üçüncü basamak sağlık hizmeti sunucularında düzenlenen 6 ay süreli sağlık kurulu raporuna istinaden bu hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır. Pregabalin ve gabapentin kombine olarak kullanılamaz (§4.2.35.A).",
        },
    },

    # C006693 — pregabalin 6-mo report; pregabalin+gabapentin combo no-pay
    {
        "rule_id": "4.2.35.A.pregabalin_6mo_report_combo_nopay",
        "sut_section": "4.2.35.A",
        "gate_b_sources": ["C006693"],
        "drug_names": ["pregabalin", "gabapentin"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": [
            "romatoloji", "algoloji", "deri ve zührevi hastalıkları",
            "endokrinoloji ve metabolizma hastalıkları", "nöroloji",
            "fiziksel tıp ve rehabilitasyon", "nefroloji",
            "ortopedi ve travmatoloji", "geriatri", "beyin cerrahisi",
        ],
        "prescriber_specialties": [
            "romatoloji", "algoloji", "deri ve zührevi hastalıkları",
            "endokrinoloji ve metabolizma hastalıkları", "nöroloji",
            "fiziksel tıp ve rehabilitasyon", "nefroloji",
            "ortopedi ve travmatoloji", "geriatri", "beyin cerrahisi",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "pregabalin mono/sabit doz kombinasyonları 2/3. basamakta ilgili uzmanlardan en az birinin yer aldığı 6 ay süreli sağlık kurulu raporuyla bu hekimlerce reçete edilirse ödenir; pregabalin ve gabapentin kombine kullanılamaz",
            "message_tr": "Pregabalin etken maddeli ilaçların mono veya sabit doz kombinasyonlarının ilgili uzman hekimlerden en az birinin yer aldığı ikinci veya üçüncü basamak sağlık hizmeti sunucularında düzenlenen 6 ay süreli sağlık kurulu raporuna istinaden bu hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır. Pregabalin ve gabapentin kombine olarak kullanılamaz (§4.2.35.A).",
        },
    },

    # C006696 — diabetic neuropathic pain: listed specialists report
    {
        "rule_id": "4.2.35.A.diabetic_neuropathic_pain_specialists",
        "sut_section": "4.2.35.A",
        "gate_b_sources": ["C006696"],
        "drug_names": ["gabapentin", "pregabalin", "duloksetin"],
        "icd10_codes": ["E10", "E11", "G63.2", "G63.9"],
        "report_required": True,
        "prescriber_specialties": ["tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "diyabetik nöropatik ağrı/periferal diyabetik polinöropati tedavisinde ilgili uzman hekimce veya uzman raporuyla tüm hekimlerce reçete edilebilir",
            "message_tr": "Diyabetik nöropatik ağrı ve periferal diyabetik polinöropati semptomlarının tedavisinde; nöroloji, beyin cerrahisi, fiziksel tıp ve rehabilitasyon, anestezi ve reanimasyon, immünoloji, romatoloji, iç hastalıkları veya endokrinoloji ve metabolizma hastalıkları uzman hekimi tarafından veya bu uzman hekimlerden birinin düzenlediği uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilebilir (§4.2.35.A).",
        },
    },

    # C006699 — capsaicin cream postherpetic neuralgia/diabetic neuropathy; no-pay arthritis
    {
        "rule_id": "4.2.35.A.capsaicin_phn_dpn_arthritis_nopay",
        "sut_section": "4.2.35.A",
        "gate_b_sources": ["C006699"],
        "drug_names": ["kapsaisin"],
        "icd10_codes": ["B02", "G63.2", "M13", "M15", "M79"],
        "report_required": True,
        "prescriber_specialties": ["tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kapsaisin mono krem yalnızca açık deri lezyonları iyileştikten sonra postherpetik nevralji/ağrılı diyabetik periferik polinöropati semptomatik tedavisinde ilgili uzman/uzman raporuyla ödenir; artrit/osteoartrit/kas-eklem ağrısında reçete edilirse ödenmez",
            "message_tr": "Kapsaisin etken maddesini mono olarak krem formunda içeren ürünlerin yalnızca açık deri lezyonlarının iyileşmesinden sonra herpes zoster enfeksiyonlarına eşlik veya takip eden nevraljinin (postherpetik nevralji) veya ağrılı diyabetik periferik polinöropatinin semptomatik tedavisinde ilgili uzman hekimce/uzman raporuyla tüm hekimlerce reçete edilmesi halinde bedeli ödenir; artrit, osteoartrit, kas ve eklem ağrılarının semptomatik tedavisinde reçete edilmesi halinde bedeli Kurumca karşılanmaz (§4.2.35.A).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.35.B  —  chronic musculoskeletal pain / fibromyalgia
    # -----------------------------------------------------------------

    # C006703 — chronic MSK pain/fibromyalgia drugs: listed specialists
    {
        "rule_id": "4.2.35.B.chronic_msk_fibromyalgia_specialists",
        "sut_section": "4.2.35.B",
        "gate_b_sources": ["C006703"],
        "icd10_codes": ["M79.7", "M79.0"],
        "report_required": True,
        "report_specialties": ["romatoloji", "ortopedi", "fizik tedavi ve rehabilitasyon", "algoloji"],
        "prescriber_specialties": ["romatoloji", "ortopedi", "fizik tedavi ve rehabilitasyon", "algoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "prospektüsünde kronik kas iskelet ağrısı ve/veya fibromiyalji endikasyonu olan ilaçlar romatoloji/ortopedi/fizik tedavi/rehabilitasyon ve algoloji uzmanlarınca veya bu hekimlerden birinin raporuyla yine bu hekimlerce reçete edilebilir",
            "message_tr": "Prospektüsünde kronik kas iskelet ağrısı ve/veya fibromiyalji endikasyonu olan ilaçlar; romatoloji, ortopedi, fizik tedavi ve rehabilitasyon ve algoloji uzmanları tarafından veya bu hekimlerden birinin düzenlediği uzman hekim raporuna dayanılarak yine bu hekimlerce reçete edilebilir (§4.2.35.B).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.46.A / 4.2.46.B / 4.2.46.C  —  idiopathic pulmonary fibrosis / SSc-ILD
    # -----------------------------------------------------------------

    # C006840 — §4.2.46.A — IPF coverage (see §4.2.46 pulmonary fibrosis)
    {
        "rule_id": "4.2.46.A.ipf_coverage",
        "sut_section": "4.2.46.A",
        "gate_b_sources": ["C006840"],
        "drug_names": ["pirfenidon", "nintedanib"],
        "icd10_codes": ["J84.1"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "idiopatik pulmoner fibroziste tanımlı koşullar sağlandığında pirfenidon/nintedanib bedeli Kurumca karşılanır",
            "message_tr": "İdiopatik pulmoner fibrozis tanılı hastalarda tanımlı koşulların sağlanması durumunda ilgili ilaç bedelleri Kurumca karşılanır (§4.2.46.A).",
        },
    },

    # C006852 — §4.2.46.B — IPF report criteria (specialists / duration)
    {
        "rule_id": "4.2.46.B.ipf_report_criteria_a",
        "sut_section": "4.2.46.B",
        "gate_b_sources": ["C006852"],
        "drug_names": ["pirfenidon", "nintedanib"],
        "icd10_codes": ["J84.1"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "idiopatik pulmoner fibrozis tedavisinde ilgili koşulların belirtildiği sağlık kurulu raporuna dayanılarak göğüs hastalıkları uzmanlarınca reçete edilirse ödenir",
            "message_tr": "İdiopatik pulmoner fibrozis tedavisinde ilgili koşulların belirtildiği sağlık kurulu raporuna dayanılarak göğüs hastalıkları uzmanlarınca reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.46.B).",
        },
    },

    # C006855 — §4.2.46.B — IPF report criteria variant
    {
        "rule_id": "4.2.46.B.ipf_report_criteria_b",
        "sut_section": "4.2.46.B",
        "gate_b_sources": ["C006855"],
        "drug_names": ["pirfenidon", "nintedanib"],
        "icd10_codes": ["J84.1"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "idiopatik pulmoner fibrozis tedavisinde ilgili koşulların belirtildiği sağlık kurulu raporuna dayanılarak ilgili uzmanlarca reçete edilirse ödenir",
            "message_tr": "İdiopatik pulmoner fibrozis tedavisinde ilgili koşulların belirtildiği sağlık kurulu raporuna dayanılarak ilgili uzmanlarca reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.46.B).",
        },
    },

    # C006862 — §4.2.46.B — IPF continuation/evaluation
    {
        "rule_id": "4.2.46.B.ipf_continuation_criteria",
        "sut_section": "4.2.46.B",
        "gate_b_sources": ["C006862"],
        "drug_names": ["pirfenidon", "nintedanib"],
        "icd10_codes": ["J84.1"],
        "report_required": True,
        "action": {
            "enforcement": "idame tedavide tanımlı klinik değerlendirme kriterleri her raporda belirtilerek tedaviye devam edilir",
            "message_tr": "İdame tedavide tanımlı klinik değerlendirme kriterleri her raporda belirtilmek kaydıyla tedaviye devam edilebilir (§4.2.46.B).",
        },
    },

    # C006867 — systemic sclerosis-ILD: nintedanib coverage (DLCO/FVC/HRCT criteria)
    {
        "rule_id": "4.2.46.C.ssc_ild_nintedanib_criteria",
        "sut_section": "4.2.46.C",
        "gate_b_sources": ["C006867"],
        "drug_names": ["nintedanib"],
        "icd10_codes": ["M34", "J84.1", "J84.9"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "sistemik skleroza bağlı interstisyel akciğer hastalarında DLCO≥%30, FVC≥%50 ve HRCT ile >%10 fibrozis varsa nintedanib başlanırsa ödenir",
            "message_tr": "Karbonmonoksit difüzyon kapasitesi (DLCO) ≥%30, Forced Vital Kapasitesi (FVC) ≥%50 ve toraks yüksek çözünürlüklü bilgisayarlı tomografi (HRCT) ile %10'dan fazla fibrozis alanı varlığı gösteren sistemik skleroza bağlı interstisyel akciğer hastalarında nintedanib ile tedaviye başlanması halinde bedeli Kurumca karşılanır (§4.2.46.C).",
        },
    },

    # C006868 — SSc-ILD: tertiary rheum+pulmonology 1-yr report
    {
        "rule_id": "4.2.46.C.ssc_ild_tertiary_rheum_pulmonology_1yr",
        "sut_section": "4.2.46.C",
        "gate_b_sources": ["C006868"],
        "drug_names": ["nintedanib"],
        "icd10_codes": ["M34", "J84.1", "J84.9"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["romatoloji", "göğüs hastalıkları"],
        "prescriber_specialties": ["göğüs hastalıkları", "romatoloji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basmakta en az bir romatoloji ve bir göğüs hastalıkları uzmanı içeren 1 yıl süreli sağlık kurulu raporuyla göğüs hastalıkları/romatoloji/iç hastalıkları uzmanlarınca reçete; raporda DLCO, FVC ve HRCT tarihleri belirtilmeli",
            "message_tr": "Bu durumların belirtildiği üçüncü basamak sağlık kurumlarında en az bir romatoloji uzman hekimi ve en az bir göğüs hastalıkları uzman hekiminin yer aldığı 1 yıl süreli sağlık kurulu raporuna dayanılarak göğüs hastalıkları, romatoloji veya iç hastalıkları uzman hekimlerince reçetelenir. Sağlık kurulu raporunda DLCO, FVC değerlerinin tarihi ile HRCT görüntüleme raporunun tarihi belirtilmesi gerekmektedir (§4.2.46.C).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.57  —  atopic dermatitis (JAK inhibitors / dupilumab)
    # -----------------------------------------------------------------

    # C007085 — abrocitinib/baricitinib/upadacitinib after 12-week failure
    {
        "rule_id": "4.2.57.atopic_dermatitis_jak_after_12wk",
        "sut_section": "4.2.57",
        "gate_b_sources": ["C007085"],
        "drug_names": ["abrositinib", "barisitinib", "upadasitinib"],
        "icd10_codes": ["L20"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "abrositinib/baricitinib/upadacitinib'ten en az birini 12 hafta kullanıp yanıtsız/tolere edemeyen/kontrendike 18 yaş ve üzeri orta-şiddetli atopik dermatit; koşullar sağlık kurulu raporunda belirtilirse ödenir",
            "message_tr": "Abrositinib, baricitinib veya upadasitinib tedavilerinden en az birini 12 hafta süre ile kullanmış olmasına rağmen yanıt vermeyen veya bu tedavileri tolere edemeyen veya bu ilaçların kontrendike olduğu 18 yaş ve üzeri orta ve şiddetli atopik dermatitli hastalarda, bu durumların sağlık kurulu raporunda belirtilmesi koşuluyla tedaviye başlanması halinde bedelleri Kurumca karşılanır (§4.2.57).",
        },
    },

    # C007086 — dupilumab after >2mo steroid/cyclosporine + risk factor
    {
        "rule_id": "4.2.57.atopic_dermatitis_dupilumab_risk_factor",
        "sut_section": "4.2.57",
        "gate_b_sources": ["C007086"],
        "drug_names": ["dupilumab"],
        "icd10_codes": ["L20"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": ">2 ay sistemik kortikosteroid/siklosporin yanıtsız/tolere edemeyen/kontrendike + risk faktörlerinden en az biri olan 18 yaş ve üzeri orta-şiddetli atopik dermatitte dupilumab başlanması koşullar raporda belirtilirse ödenir",
            "message_tr": "İki aydan uzun süreli sistemik kortikosteroid ve siklosporin kullanımından yarar görmeyen veya bu ilaçları tolere edemeyen veya bu ilaçların kontrendike olduğu ve belirtilen risk faktörlerinden en az birine sahip olan 18 yaş ve üzeri orta ve şiddetli atopik dermatitli hastalarda bu durumların sağlık kurulu raporunda belirtilmesi koşuluyla tedaviye Dupilumab ile başlanması halinde bedelleri Kurumca karşılanır (§4.2.57).",
        },
    },

    # C007089 — malignancy history (5yr) / increased cancer risk exclusion
    {
        "rule_id": "4.2.57.atopic_dermatitis_malignancy_risk",
        "sut_section": "4.2.57",
        "gate_b_sources": ["C007089"],
        "drug_names": ["abrositinib", "barisitinib", "upadasitinib", "dupilumab"],
        "icd10_codes": ["L20"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "son 5 yılda malignite hikayesi (non melanom deri kanseri hariç) veya artmış kanser riski değerlendirme kriteri olarak alınır",
            "message_tr": "Son 5 yılda malignite hikayesi (non melanom deri kanseri hariç) veya artmış kanser riski değerlendirme kriteri olarak alınır (§4.2.57).",
        },
    },

    # C007095 — 16-week response criteria to continue therapy
    {
        "rule_id": "4.2.57.atopic_dermatitis_16wk_response_continue",
        "sut_section": "4.2.57",
        "gate_b_sources": ["C007095"],
        "drug_names": ["abrositinib", "barisitinib", "upadasitinib", "dupilumab"],
        "icd10_codes": ["L20"],
        "report_required": True,
        "action": {
            "enforcement": "16 haftalık kullanım sonunda tedavi başlangıcına göre tanımlı kriterlerden en az biri sağlanırsa tedaviye devam edilebilir",
            "message_tr": "16 haftalık ilaç kullanım süresi sonunda tedavi başlangıcına göre belirlenen kriterlerden en az birinin sağlanması durumunda tedaviye devam edilebilir (§4.2.57).",
        },
    },

    # C007100 — tertiary 3-dermatology 4-mo report; JAK+dupilumab combo no-pay
    {
        "rule_id": "4.2.57.tertiary_3derm_4mo_report_combo_nopay",
        "sut_section": "4.2.57",
        "gate_b_sources": ["C007100"],
        "drug_names": ["upadasitinib", "abrositinib", "barisitinib", "dupilumab"],
        "icd10_codes": ["L20"],
        "report_required": True,
        "report_duration_months": 4,
        "report_specialties": ["deri ve zührevi hastalıkları"],
        "prescriber_specialties": ["deri ve zührevi hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basmakta üç deri ve zührevi hastalıkları uzmanının yer aldığı 4 ay süreli sağlık kurulu raporuyla deri uzmanlarınca reçete edilirse ödenir; upadasitinib/abrositinib/barisitinib ve dupilumab birlikte kullanılamaz",
            "message_tr": "Üçüncü basamak resmi sağlık hizmet sunucularında üç deri ve zührevi hastalıkları uzman hekiminin yer aldığı 4 ay süreli sağlık kurulu raporuna dayanılarak deri ve zührevi hastalıkları uzman hekimlerince reçete edilmesi halinde bedelleri Kurumca karşılanır. Upadasitinib, abrositinib, barisitinib ve dupilumab birlikte kullanılamaz (§4.2.57).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.70.A / 4.2.70.B  —  amyloidosis (TTR) / ALS
    # -----------------------------------------------------------------

    # C007186 — mandatory: TTR cardiac amyloid on scintigraphy → mutation analysis
    {
        "rule_id": "4.2.70.A.ttr_sintigraphy_mutation_analysis",
        "sut_section": "4.2.70.A",
        "gate_b_sources": ["C007186"],
        "drug_names": ["tafamidis", "akoramidis"],
        "icd10_codes": ["E85"],
        "report_required": True,
        "action": {
            "enforcement": "nükleer sintigrafide tipik TTR kardiyak amiloid tutulumu varsa TTR genetik mutasyon analizi yapılmalıdır; mutasyon yoksa vahşi tip, varsa herediter kabul edilir",
            "message_tr": "Nükleer sintigrafide tipik TTR kardiyak amiloid tutulumu olması halinde TTR genetik mutasyon analizinin yapılması gereklidir. Analizde mutasyon saptanmaması halinde vahşi tip TTR kardiyak amiloidoz kabul edilir, mutasyon saptanması halinde herediter kabul edilir (§4.2.70.A).",
        },
    },

    # C007197 — tertiary 3-cardiology 3-mo report coverage
    {
        "rule_id": "4.2.70.A.tertiary_3cardiology_3mo_report",
        "sut_section": "4.2.70.A",
        "gate_b_sources": ["C007197"],
        "drug_names": ["tafamidis", "akoramidis"],
        "icd10_codes": ["E85"],
        "report_required": True,
        "report_duration_months": 3,
        "report_specialties": ["kardiyoloji"],
        "prescriber_specialties": ["kardiyoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basmakta tanı ve ilaca başlama kriterlerini sağlayan üç kardiyoloji uzmanından oluşan 3 ay süreli sağlık kurulu raporuyla kardiyoloji uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Üçüncü basamak resmi sağlık hizmeti sunucularında hastalığın tanı kriterleri ile ilaca başlama kriterlerini sağlayan ve bu durumların belirtildiği üç kardiyoloji uzman hekiminden oluşan 3 ay süreli sağlık kurulu raporuna istinaden kardiyoloji uzman hekimlerince reçetelenmesi halinde bedeli Kurumca karşılanır (§4.2.70.A).",
        },
    },

    # C007198 — continuation: GFR>30, no severe hepatic failure, 6MWT>100m, NYHA I-III
    {
        "rule_id": "4.2.70.A.continuation_gfr_6mwt_nyha_criteria",
        "sut_section": "4.2.70.A",
        "gate_b_sources": ["C007198"],
        "drug_names": ["tafamidis", "akoramidis"],
        "icd10_codes": ["E85"],
        "report_required": True,
        "report_duration_months": 3,
        "action": {
            "enforcement": "her 3 ayda bir değerlendirmede tahmini GFR>30 ml/dk/1,72m², ciddi karaciğer yetmezliği gelişmemiş, 6 dakika yürüme >100 m ve NYHA I-III korunursa 3 aylık raporlarla devam",
            "message_tr": "İlaca başlanan hastalarda her üç ayda bir yapılan değerlendirmede tahmini GFR'nin 30 ml/dk/1,72m²'nin üzerinde olması, ciddi karaciğer yetmezliğinin gelişmemiş olması ve altı dakika yürüme mesafesinin 100 m'nin üzerinde olması ve NYHA fonksiyonel kapasite I-III olmasının korunması halinde bu durumların raporda belirtilmesi koşuluyla 3 aylık raporlarla ilaca devam edilebilir (§4.2.70.A).",
        },
    },

    # C007199 — 15-month continuation: no HF hospitalization/IV diuretic ER
    {
        "rule_id": "4.2.70.A.continuation_15mo_no_hf_admission",
        "sut_section": "4.2.70.A",
        "gate_b_sources": ["C007199"],
        "drug_names": ["tafamidis", "akoramidis"],
        "icd10_codes": ["E85"],
        "report_required": True,
        "action": {
            "enforcement": "15. ay değerlendirmesinde son 6 ayda kalp yetersizliği nedeniyle ≥1 hastaneye yatış veya IV diüretik ile ≥1 acil başvuru olmaması koşuluyla tedaviye devam; kriter sağlanmazsa tedavi sonlandırılır",
            "message_tr": "On beşinci ayın sonunda yapılan değerlendirmede son altı ayda kalp yetersizliği nedeniyle bir ve üzeri hastaneye yatışının veya son altı ayda intravenöz diüretik ihtiyacı ile bir veya üzeri acil servis başvurusu olmaması ve bu durumların raporda belirtilmesi koşuluyla tedaviye devam edilebilir. İlaç devam kriterlerinin karşılanamadığı durumlarda tedaviye son verilir (§4.2.70.A).",
        },
    },

    # C007203 — ALS: stable stage at 3mo → 6-mo maintenance, stop at stage 2
    {
        "rule_id": "4.2.70.B.als_stable_stage_3mo_6mo_maintenance",
        "sut_section": "4.2.70.B",
        "gate_b_sources": ["C007203"],
        "drug_names": ["edaravon", "riluzol"],
        "icd10_codes": ["G12.21"],
        "report_required": True,
        "report_duration_months": 6,
        "action": {
            "enforcement": "3 ay sonra hastalık evresi değişmedi (ev dışında desteksiz yürüme devam) raporda belirtilirse 6 aylık idame raporuyla devam; her raporda bu durum belirtilmeli; evre 2'ye geçişte (yürümede destek gereksinimi) tedavi sonlandırılır",
            "message_tr": "3 ay sonra yapılan değerlendirmede klinik olarak hastalık evresinin değişmediğinin (hastanın ev dışında desteksiz yürümeye devam ettiği) raporda belirtilmesi halinde 6 aylık idame rapor ile tedaviye devam edilebilir. Rapor süresinin sonunda her raporda hastalık evresinin değişmediği belirtilmelidir. Tedavi, hastalığın evre 2'ye geçmesi (yürüme için desteğe ihtiyaç duyulması) halinde sonlandırılır (§4.2.70.B).",
        },
    },

    # C007204 — ALS: tertiary 3-neurology health-board report coverage
    {
        "rule_id": "4.2.70.B.als_tertiary_3neurology_report",
        "sut_section": "4.2.70.B",
        "gate_b_sources": ["C007204"],
        "drug_names": ["edaravon", "riluzol"],
        "icd10_codes": ["G12.21"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basmakta durumların belirtildiği üç nöroloji uzmanının bulunduğu sağlık kurulu raporuyla nöroloji uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Üçüncü basamak resmi sağlık hizmeti sunucularında yukarıdaki durumların belirtildiği üç nöroloji uzman hekiminin bulunduğu sağlık kurulu raporuna dayanılarak nöroloji uzman hekimleri tarafından reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.70.B).",
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
