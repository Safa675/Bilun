#!/usr/bin/env python3
"""Wave REM_4_2_tail_a — §4.2 long-tail sub-sections (first half).

28 in-force deontic clauses encoded from
`tasks/encode_waves/REM_4_2_tail_a.csv`, spanning the heterogeneous
long-tail §4.2 sub-sections: 4.2.5 (botulinum toksini), 4.2.19 (migren),
4.2.20 (palivizumab/RSV), 4.2.22 (ağır sepsis), 4.2.29 (hormonlar),
4.2.37.A (akromegali), 4.2.38 (diyabet DPP-4/SGLT2/GLP-1), 4.2.39 (güneş
koruyucu), 4.2.43 (bosentan), 4.2.48 (safra asidi/Zellweger),
4.2.50 (CTX), 4.2.51 (droxidopa), 4.2.52 (febuxostat/gut),
4.2.53 (beslenme ürünü) and 4.2.54 (leishmaniasis).

Rule shape follows the established `drug_indication_rheum_biologics_batch_rules`
pattern: flat condition keys (drug_names, icd10_codes/ranges, report_required,
report_duration_months, report_specialties, prescriber_specialties, pay) plus a
nested `action` block (message_tr + enforcement) for NO_PAY exclusions.  Bare
coverage statements use ``condition: {"coverage_note": True}``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# §4.2.5  —  botulinum toksini (BOTOX / DYSPORT)
# ---------------------------------------------------------------------------

BATCH_RULES: list[dict] = [

    # C003930 — pediatrik serebral palsi: 3. basamak/FTR dal hk, ≤18 yaş, ≤2 adale
    {
        "rule_id": "4.2.5.botox.paediatric_cerebral_palsy_tertiary_coverage",
        "sut_section": "4.2.5",
        "gate_b_sources": ["C003930"],
        "drug_names": ["botulinum toksini", "botox", "dysport", "onabotulinumtoksin", "abobotulinumtoksin"],
        "icd10_codes": ["G80"],
        "report_required": True,
        "report_specialties": ["ortopedi", "fiziksel tıp ve rehabilitasyon", "çocuk nörolojisi", "çocuk sağlığı ve hastalıkları"],
        "prescriber_specialties": ["ortopedi", "fiziksel tıp ve rehabilitasyon", "çocuk nörolojisi", "çocuk sağlığı ve hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "pediatrik serebral palsi: 3. basamak (üniversite/eğitim-araştırma) veya FTR dal hastanesinde ortopedi/PMR/çocuk nörolojisi/çocuk sağlığı uzmanının yer aldığı sağlık kurulu raporuyla bu uzmanlardan biri tarafından reçete; ≤18 yaş, sistemik hastalık/kemik deformitesi/kanama diyatezi/fikst kontraktür olmayanlarda en fazla iki adaleye",
            "message_tr": "Pediatrik serebral palsi endikasyonunda üçüncü basamak resmi sağlık hizmeti sunucularında ile fizik tedavi ve rehabilitasyon dal hastanelerinde; ortopedi, fiziksel tıp ve rehabilitasyon, çocuk nörolojisi veya çocuk sağlığı ve hastalıkları uzman hekimlerinin yer aldığı sağlık kurulu raporuna dayanılarak belirtilen uzman hekimlerden biri tarafından reçete edilmesi halinde bedeli ödenir; 18 yaşa kadar sistemik hastalığı, kemiksel deformite, kanama diyatezi, fikst kontraktür olmayan hastalarda en fazla iki adaleye uygulanır (§4.2.5).",
        },
    },

    # C003935 — aksiller primer hiperhidroz: 3. basamak endokrin/göğüs cerr./derm, ≤6 ay
    {
        "rule_id": "4.2.5.botox.axillary_hyperhidrosis_tertiary_coverage",
        "sut_section": "4.2.5",
        "gate_b_sources": ["C003935"],
        "drug_names": ["botulinum toksini", "botox", "dysport", "onabotulinumtoksin", "abobotulinumtoksin"],
        "icd10_codes": ["L74.5", "R61"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["endokrinoloji ve metabolizma", "göğüs cerrahisi", "dermatoloji"],
        "prescriber_specialties": ["endokrinoloji ve metabolizma", "göğüs cerrahisi", "dermatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "inatçı şiddetli aksiller primer hiperhidroz: 1 yıl topikal tedaviye dirençli erişkinlerde; altta yatan metabolik/endokrin bozukluk olmadığı belirtilmeli; 3. basamakta endokrinoloji+göğüs cerr.+dermatoloji birlikte ≤1 yıl rapor, ≤6 ayda bir; tedavi ≤2 yıl; botox ≤50 ünite/koltuk altı, dysport ≤100 ünite/koltuk altı",
            "message_tr": "Bir yıl süre ile topikal tedavi alan ve bu tedaviye dirençli olan, inatçı şiddetli aksiller primer hiperhidroz tedavisinde erişkin hastalarda botulinum toksini kullanımı için altta yatabilecek metabolik ve endokrin bir bozukluğu olmadığının belirtildiği, üçüncü basamak resmi sağlık hizmeti sunucularında endokrinoloji ve metabolizma, göğüs cerrahisi ve dermatoloji uzman hekimlerinin birlikte yer aldığı en fazla bir yıl süreli sağlık kurulu raporu ile en fazla 6 ayda bir uygulanması halinde bedelleri Kurumca karşılanır; tedavi süresi en fazla 2 yıldır, tek seansta her bir koltuk altı için botox 50 üniteyi, dysport ise 100 üniteyi aşmamak üzere yapılabilir (§4.2.5).",
        },
    },

    # C003936 — tekrar uygulama: 6 aylık periyotlarda yeni rapor, ≤2 uygulama, doz limiti
    {
        "rule_id": "4.2.5.botox.repeat_application_6mo_report_permission",
        "sut_section": "4.2.5",
        "gate_b_sources": ["C003936"],
        "drug_names": ["botulinum toksini", "botox", "dysport", "onabotulinumtoksin", "abobotulinumtoksin"],
        "report_required": True,
        "report_specialties": ["uzman hekimler"],
        "action": {
            "enforcement": "tedaviden yarar görüp tekrarı düşünülenlerde 6 aylık periyotlarda her defasında yeni sağlık kurulu raporuyla en fazla iki uygulama; tek seansta botox ≤300 ünite, dysport ≤1.000 ünite; bu endikasyonlar dışında ödenmez",
            "message_tr": "Yukarıda a ve b bentlerinde sıralanan endikasyonlar için tedaviden yarar görüp tekrarı düşünülen hastalarda 6 aylık periyotlarda her defasında yeni bir sağlık kurulu raporu düzenlenerek en fazla iki uygulama ve tek seansta botoks için toplam 300 üniteyi, dysport için 1.000 üniteyi aşmamak üzere yapılabilir (§4.2.5).",
        },
    },

    # C003938 — bu endikasyonlar dışında bedeli ödenmez
    {
        "rule_id": "4.2.5.botox.outside_indications_nopay",
        "sut_section": "4.2.5",
        "gate_b_sources": ["C003938"],
        "drug_names": ["botulinum toksini", "botox", "dysport", "onabotulinumtoksin", "abobotulinumtoksin"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: tanımlı endikasyonlar (a/b bentleri) dışında botulinum toksini kullanımı",
            "message_tr": "Bu endikasyonlar dışında bedeli ödenmez (§4.2.5).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.19  —  migren ilaçları (topiramat / triptanlar)
    # -----------------------------------------------------------------

    # C006064 — migren: 1 yıllık uzman raporu, nöroloji reçetesiyle diğer hekimler ≤1 aylık doz
    {
        "rule_id": "4.2.19.migraine.neurology_1yr_report_monthly_dose_coverage",
        "sut_section": "4.2.19",
        "gate_b_sources": ["C006064"],
        "drug_names": ["topiramat", "topiramate", "triptan", "sumatriptan", "zolmitriptan", "rizatriptan", "eletriptan", "naratriptan", "almotriptan", "frovatriptan"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "migren: uzman hekim raporu 1 yıl geçerli; nöroloji uzmanınca düzenlenen uzman hekim raporuna dayanılarak diğer hekimlerce en fazla birer aylık dozda reçete edilirse ödenir",
            "message_tr": "Uzman hekim raporu 1 yıl süreyle geçerlidir ve nöroloji uzman hekimince düzenlenen uzman hekim raporuna dayanılarak diğer hekimler tarafından en fazla birer aylık dozda reçete edilmesi halinde bedeli ödenir (§4.2.19).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.20  —  palivizumab (RSV profilaksisi)
    # -----------------------------------------------------------------

    # C006075 — palivizumab: RSV sezonu, ilgili çocuk uzmanı 1 yıllık rapor, ≤5 doz, ≤2 yaş
    {
        "rule_id": "4.2.20.palivizumab.rsv_season_paediatric_coverage",
        "sut_section": "4.2.20",
        "gate_b_sources": ["C006075"],
        "drug_names": ["palivizumab", "synagis"],
        "icd10_codes": ["B97.4", "J12.1", "J21.0", "P23"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["çocuk alerjisi", "çocuk immünolojisi ve alerji hastalıkları", "çocuk enfeksiyon hastalıkları", "çocuk göğüs hastalıkları", "çocuk kardiyolojisi", "neonatoloji", "çocuk sağlığı ve hastalıkları"],
        "prescriber_specialties": ["çocuk alerjisi", "çocuk immünolojisi ve alerji hastalıkları", "çocuk enfeksiyon hastalıkları", "çocuk göğüs hastalıkları", "çocuk kardiyolojisi", "neonatoloji", "çocuk sağlığı ve hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "palivizumab RSV sezonu (Ekim–Mart) içinde ilgili çocuk uzmanlarından birinin 1 yıllık uzman raporuyla bu uzmanlar veya çocuk sağlığı uzmanlarınca en fazla 5 doz ve maksimum 2 yaşa kadar reçete edilirse ödenir",
            "message_tr": "Palivizumab etken maddeli ilaç; Respiratuar Sinsitiyal Virüs (RSV) sezonu boyunca (Ekim ile Mart ayları arasında) çocuk alerjisi, çocuk immünolojisi ve alerji hastalıkları, çocuk enfeksiyon hastalıkları, çocuk göğüs hastalıkları, çocuk kardiyolojisi veya neonatoloji uzman hekimlerinden biri tarafından düzenlenen 1 yıl süreli uzman hekim raporuna dayanılarak bu uzman hekimler veya çocuk sağlığı ve hastalıkları uzman hekimlerince en fazla 5 doz ve maksimum 2 yaşa kadar reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.20).",
        },
    },

    # C006081 — kullanılması halinde bedelleri Kurumca karşılanır (closing clause)
    {
        "rule_id": "4.2.20.palivizumab.coverage_closing_clause",
        "sut_section": "4.2.20",
        "gate_b_sources": ["C006081"],
        "drug_names": ["palivizumab", "synagis"],
        "icd10_codes": ["B97.4", "J12.1", "J21.0", "P23"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "koşulları sağlanarak kullanılması halinde bedelleri Kurumca karşılanır",
            "message_tr": "Kullanılması halinde bedelleri Kurumca karşılanır (§4.2.20).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.22  —  ağır sepsis (drotrecogin alfa / aktiv protein C)
    # -----------------------------------------------------------------

    # C006085 — yoğun bakım ağır sepsis: ≥3 hekim onayı, ≥2 organ yetmezliği, 48s epikriz, 24 μg/kg/s x 96s
    {
        "rule_id": "4.2.22.sepsis.icu_three_consents_two_organ_failure_coverage",
        "sut_section": "4.2.22",
        "gate_b_sources": ["C006085"],
        "drug_names": ["drotrecogin alfa", "aktiv protein c", "xigris"],
        "icd10_codes": ["A41", "R65"],
        "report_required": True,
        "report_specialties": ["anestezi ve reanimasyon", "enfeksiyon hastalıkları", "iç hastalıkları", "göğüs hastalıkları", "genel cerrahi"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yoğun bakımda anestezi-reanimasyon/enfeksiyon/iç hastalıkları/göğüs/genel cerrahi hekimlerinden en az üçünün onayıyla, ≥2 organ yetmezliği gelişmiş ağır sepsiste ilk 48 saatte teşhis+günlük doz/süre (24 μg/kg/saat IV x 96 saat) içeren onaylı epikriz raporuyla reçete edilirse ödenir; yeniden kullanımda en az üç hekince sağlık kurulu raporu",
            "message_tr": "Yoğun bakım ünitelerinde, anestezi ve reanimasyon, enfeksiyon hastalıkları, iç hastalıkları, göğüs hastalıkları, genel cerrahi hekimlerinden en az üçünün onayının bulunduğu, en az iki organ yetmezliği gelişmiş ağır sepsis hastalarının tedavisinde, ilk 48 saat içerisinde, hastalığın teşhisi, günlük kullanım dozu ve süresini (24 μg/kg/saat IV x 96 saat) belirten onaylı epikriz raporuna dayanılarak reçete edilmesi halinde bedeli ödenir; yeniden kullanım gerektiğinde belirtilen hekimlerden en az üçü tarafından sağlık kurulu raporu düzenlenir, raporda günlük doz/süre ve epikrise dayanılarak kullanıldığı belirtilmelidir (§4.2.22).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.29  —  hormonlar (östrojen / progestojen / dienogest / progesteron)
    # -----------------------------------------------------------------

    # C006359 — östrojenler/HRT/progestojenler: belirli uzmanlarca veya raporuyla tüm hekimler
    {
        "rule_id": "4.2.29.hormones.estrogen_hrt_progestogen_prescription_permission",
        "sut_section": "4.2.29",
        "gate_b_sources": ["C006359"],
        "drug_names": ["östradiol", "konjüge östrojen", "tibolon", "progestojen", "östrojen", "hormon replasman tedavisi"],
        "action": {
            "enforcement": "östrojenler ve hormon replasman tedavisi ilaçları (östradiol/konjüge östrojen+progestojen, yalnız östrojen, tibolon) ile progestojenler endokrinoloji/KDİ/iç hastalıkları/ortopedi/FTR/aile hekimliği uzmanlarınca veya bu uzmanların raporuyla tüm hekimlerce reçete edilebilir",
            "message_tr": "Bu grup ilaçların bütün formlarından; östrojenler ve hormon replasman tedavisinde kullanılanlar (östradiol ya da konjüge östrojen ve progestojen kombinasyonları, yalnız östrojen içerenler ve tibolon içerenler) ile progestojenler; endokrinoloji, kadın hastalıkları ve doğum, iç hastalıkları, ortopedi ve travmatoloji, fiziksel tıp ve rehabilitasyon ve aile hekimliği uzman hekimlerince veya bu uzman hekimler tarafından düzenlenen uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilebilir (§4.2.29).",
        },
    },

    # C006361 — tek başına dienogest: KDİ uzmanlarınca veya raporuyla tüm hekimler
    {
        "rule_id": "4.2.29.hormones.dienogest_monocomponent_coverage",
        "sut_section": "4.2.29",
        "gate_b_sources": ["C006361"],
        "drug_names": ["dienogest"],
        "report_specialties": ["kadın hastalıkları ve doğum"],
        "prescriber_specialties": ["tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "tek başına dienogest etken maddeli ilaçlar kadın hastalıkları ve doğum uzmanlarınca veya bu uzmanların raporuyla tüm hekimlerce reçete edilirse ödenir",
            "message_tr": "Tek başına dienogest etkin maddesi içeren ilaçlar kadın hastalıkları ve doğum uzman hekimlerince veya bu uzman hekimler tarafından düzenlenen uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.29).",
        },
    },

    # C006362 — tek başına progesteron (infertilite, topikal): KDİ uzman prospektüs uyumlu raporuyla
    {
        "rule_id": "4.2.29.hormones.progesteron_topical_infertility_coverage",
        "sut_section": "4.2.29",
        "gate_b_sources": ["C006362"],
        "drug_names": ["progesteron", "progesterone"],
        "icd10_codes": ["N97", "N46"],
        "report_specialties": ["kadın hastalıkları ve doğum"],
        "prescriber_specialties": ["tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "tek başına progesteron etken maddeli ve infertilite endikasyonlu topikal ilaçlar kadın hastalıkları ve doğum uzmanlarınca veya bu hekimlerin prospektüs endikasyonlarıyla uyumlu raporuyla diğer hekimlerce reçete edilirse ödenir",
            "message_tr": "Tek başına progesteron etkin maddesi içeren ve infertilite tedavisi endikasyonu olan topikal ilaçlar kadın hastalıkları ve doğum uzman hekimlerince veya bu hekimlerce düzenlenen prospektüs endikasyonlarıyla uyumlu uzman hekim raporuna istinaden diğer hekimlerce reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.29).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.37.A  —  pegvisomant (akromegali)
    # -----------------------------------------------------------------

    # C006714 — pegvisomant: cerrahi/radyoterapi sonrası aktif akromegali, ≥12 ay somatostatin analogu tam doz yanıtsız, 3. basamak endokrin
    {
        "rule_id": "4.2.37.A.acromegaly.pegvisomant_somatostatin_failure_permission",
        "sut_section": "4.2.37.A",
        "gate_b_sources": ["C006714"],
        "drug_names": ["pegvisomant", "somavert"],
        "icd10_codes": ["E22.0", "E15"],
        "report_required": True,
        "report_specialties": ["endokrinoloji ve metabolizma"],
        "prescriber_specialties": ["endokrinoloji ve metabolizma"],
        "action": {
            "enforcement": "aktif akromegali (cerrahi/radyoterapi sonrası veya uygun olmayan), ≥12 ay tam doz uzun etkili somatostatin analoguna rağmen IGF-1 yüksek olanlarda pegvisomant; 3. basamak (üniversite/eğitim-araştırma) içinde en az bir endokrinoloji ve metabolizma uzmanı yer alan sağlık kurulu raporu",
            "message_tr": "Cerrahi ve/veya radyasyon terapisine rağmen veya genel durumu operasyon ve/veya radyasyon terapisine uygun olmayan aktif akromegalisi olan ve en az 12 aylık süre ile ve tam dozda uzun etkili somatostatin analogları ile tedaviye rağmen IGF-1 düzeyleri yaşa göre belirlenen normal değerlerin üstünde kalan hastalarda kullanılabilir; bu hastalar için eğitim ve araştırma ile üniversite hastanelerinde üçüncü basamak resmi sağlık hizmeti sunucularında içinde en az bir endokrinoloji ve metabolizma uzmanının yer aldığı sağlık kurulu raporu düzenlenir (§4.2.37.A).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.38  —  empagliflozin / linagliptin kombine (diyabet)
    # -----------------------------------------------------------------

    # C006740 — bazal insülin+metformin/pioglitazon yetersiz: empagliflozin/linagliptin eklenebilir
    {
        "rule_id": "4.2.38.diab.empagliflozin_linagliptin_basal_insulin_permission",
        "sut_section": "4.2.38",
        "gate_b_sources": ["C006740"],
        "drug_names": ["empagliflozin", "linagliptin", "sglt2 inhibitörü", "dpp-4 antagonisti"],
        "icd10_codes": ["E11"],
        "action": {
            "enforcement": "metformin ve/veya pioglitazon ile kombine ya da tek başına bazal insülin ile yeterli glisemik kontrol sağlanamamış hastalarda bazal insüline ek olarak empagliflozin/linagliptin kombine preparatı kullanılabilir",
            "message_tr": "Metformin ve/veya pioglitazon ile kombine ya da tek başına bazal insülin ile yeterli glisemik kontrol sağlanamamış hastalarda bazal insüline ek olarak kullanılabilir (§4.2.38).",
        },
    },

    # C006743 — DPP-4 antagonisti ile birlikte kullanım ödenmez
    {
        "rule_id": "4.2.38.diab.dpp4_antagonist_combo_nopay",
        "sut_section": "4.2.38",
        "gate_b_sources": ["C006743"],
        "drug_names": ["empagliflozin", "linagliptin", "sglt2 inhibitörü", "dpp-4 antagonisti"],
        "icd10_codes": ["E11"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: empagliflozin/linagliptin kombine preparatının DPP-4 antagonistleri ile birlikte kullanımı",
            "message_tr": "DPP-4 antagonistleri ile birlikte kullanılması halinde bedelleri Kurumca karşılanmaz (§4.2.38).",
        },
    },

    # C006749 — empagliflozin+linagliptin: endokrin/iç hastalıkları veya raporuyla tüm hekimler; diğer DPP-4/SGLT2/GLP-1 ile combo ödenmez
    {
        "rule_id": "4.2.38.diab.empagliflozin_linagliptin_specialty_combo_nopay",
        "sut_section": "4.2.38",
        "gate_b_sources": ["C006749"],
        "drug_names": ["empagliflozin", "linagliptin", "sodyum-glukoz ko-transporter 2 inhibitörü", "sglt2 inhibitörü", "dpp-4 antagonisti", "gLP-1 analogu"],
        "icd10_codes": ["E11"],
        "pay": False,
        "action": {
            "enforcement": "empagliflozin (SGLT2)+linagliptin (DPP-4) kombine; metformin ve/veya sülfonilüre + empagliflozin veya linagliptin ile yetersiz kontrolde endokrinoloji/iç hastalıkları uzmanlarınca veya raporlarıyla tüm hekimlerce reçete; ancak linagliptin+empagliflozin kombinasyonu diğer DPP-4 antagonistleri, SGLT2 inhibitörleri ve GLP-1 analoglarıyla birlikte kullanılırsa ödenmez",
            "message_tr": "Empagliflozin (SGLT2 inhibitörü) ve linagliptin (DPP-4 antagonisti) kombine preperatları; metformin ve/veya sülfonilüre ve empagliflozin veya linagliptinden biri ile birlikte kullanılmasına rağmen yeterli glisemik kontrol sağlanamamış hastalarda, endokrinoloji uzman hekimleri ile iç hastalıkları uzman hekimlerince veya bu hekimlerce düzenlenen uzman hekim raporu ile tüm hekimlerce reçete edilebilir; linagliptin ve empagliflozin kombinasyonu diğer DPP-4 antagonistleri, SGLT2 inhibitörleri ve GLP-1 analogları ile birlikte kullanılması halinde bedelleri Kurumca karşılanmaz (§4.2.38).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.39  —  güneşten koruyucu kremler (XP / okülokütanöz albinizm)
    # -----------------------------------------------------------------

    # C006751 — XP + okülokütanöz albinizm: aylık ≤249,48 TL, sağlık kurulu raporu/reçete/fatura, şahıs bazında
    {
        "rule_id": "4.2.39.derm.sunscreen_xp_albinism_monthly_coverage",
        "sut_section": "4.2.39",
        "gate_b_sources": ["C006751"],
        "drug_names": ["güneşten koruyucu krem", "güneş koruyucu", "sunscreen", "fotoprotektif"],
        "icd10_codes": ["Q82.1", "E70.3"],
        "report_required": True,
        "report_specialties": ["dermatoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kseroderma pigmentosum ve okülokütanöz albinizmde kullanılan güneşten koruyucu kremlerin aylık bedeli ≤249,48 TL'yi geçmemek kaydıyla sağlık kurulu raporu, reçete ve faturaya dayanılarak sağlık sosyal güvenlik merkezlerince şahıs bazında ödenir",
            "message_tr": "Kseroderma pigmentosum ve albinizm (okülokütanöz) tedavisinde kullanılan güneşten koruyucu kremlerin bedelleri aylık 249,48 (iki yüz kırk dokuz virgül kırk sekiz) TL'yi geçmemek kaydıyla sağlık kurulu raporu, reçete ve faturaya dayanılarak sağlık sosyal güvenlik merkezleri tarafından şahıs bazında ödenir (§4.2.39).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.43  —  bosentan (sistemik skleroz, dijital ülser)
    # -----------------------------------------------------------------

    # C006805 — bosentan: CCB+IV iloprost ≥3 ay yanıtsız, ≥4 dijital ülser (≥1 ağır kardinal), 3. basamak; 32 mg form yutma güçlüğü
    {
        "rule_id": "4.2.43.bosentan.digital_ulcer_scleroderma_coverage",
        "sut_section": "4.2.43",
        "gate_b_sources": ["C006805"],
        "drug_names": ["bosentan", "tracleer"],
        "icd10_codes": ["M34", "L94.0"],
        "report_required": True,
        "report_specialties": ["romatoloji", "dermatoloji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kalsiyum kanal blokerleri ve IV iloprost ile ≥3 ay tedavi görmüş ve yanıt alınamamış, en az biri 2 mm'den fazla çapı ve görünebilir derinliği olan ağrılı kardinal ülser olmak üzere multiple (≥4) dijital ülseri olanlarda başlanır; bosentan 32 mg dozu bu durumları karşılayan ve yutma güçlüğü çeken (yoğun bakım/entübe/ağızdan beslenemeyen/nazogastrik) erişkinlerde raporda belirtilmesi koşuluyla ödenir",
            "message_tr": "Kalsiyum kanal blokerleri ve intravenöz iloprost ile en az 3 ay süreyle tedavi görmüş ve yanıt alınamamış ve en az biri 2 mm'den fazla çapı ve görünebilir derinliği olan ağrılı kardinal ülser olmak üzere multiple (≥4 adet) dijital ülseri olan hastalarda tedaviye başlanır; bosentan etkin maddesini 32 mg dozunda içeren ilaçlar ise bu durumları karşılayan ve yutma güçlüğü çeken (yoğun bakımda tedavi gören veya entübe veya ağızdan beslenemeyen veya nazogastrik beslenme zorunluluğu olan) erişkin hastalarda raporda belirtilmesi koşulu ile reçetelenmesi halinde bedeli Kurumca karşılanır (§4.2.43).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.48  —  cholic acid (kalıtsal safra asidi / Zellweger spektrum)
    # -----------------------------------------------------------------

    # C006912 — cholic acid: 3. basamak, ≥2 ilgili uzman, 6 aylık rapor, genetik doğrulama zorunlu
    {
        "rule_id": "4.2.48.metabolic.bile_acid_zellweger_mandatory_report",
        "sut_section": "4.2.48",
        "gate_b_sources": ["C006912"],
        "drug_names": ["kolsik asit", "cholic acid", "cholbam"],
        "icd10_codes": ["E78.8", "Q87", "E88"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["çocuk endokrinolojisi ve metabolizma hastalıkları", "çocuk metabolizma hastalıkları", "erişkin endokrinoloji ve metabolizma hastalıkları", "çocuk gastroenterolojisi", "gastroenteroloji"],
        "prescriber_specialties": ["çocuk endokrinolojisi ve metabolizma hastalıkları", "çocuk metabolizma hastalıkları", "erişkin endokrinoloji ve metabolizma hastalıkları", "çocuk gastroenterolojisi", "gastroenteroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kalıtsal safra asidi metabolizması bozuklukları veya Zellweger spektrum bozukluğu; 3. basamakta çocuk endokrinoloji/çocuk endokrin+metabolizma/çocuk metabolizma/erişkin endokrin+metabolizma/çocuk-erişkin gastroenteroloji uzmanlarından en az ikisinin yer aldığı 6 ay süreli sağlık kurulu raporuyla bu uzmanlarca reçete; mevcut enzim eksikliğinin genetik doğrulaması raporda belirtilmeli",
            "message_tr": "Kalıtsal safra asidi metabolizması bozuklukları veya Zellweger spektrum bozukluğu tanılı hastalarda; üçüncü basamak resmi sağlık hizmet sunucularında çocuk endokrinoloji, çocuk endokrinolojisi ve metabolizma hastalıkları, çocuk metabolizma hastalıkları, erişkin endokrinoloji ve metabolizma hastalıkları, çocuk ve erişkin gastroenteroloji uzman hekimlerinden en az ikisinin yer aldığı 6 ay süreli sağlık kurulu raporuna dayanılarak bu uzman hekimlerce reçetelenir; mevcut enzim eksikliğinin genetik olarak doğrulandığı test sonucunun raporda belirtilmesi gerekmektedir (§4.2.48).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.50  —  chenodeoxycholic acid (CTX / Cerebrotendinous Xanthomatosis)
    # -----------------------------------------------------------------

    # C007055 — CTX: CYP27A1 mutasyonu, 3. basamak ≥1 çocuk metabolizma/endo, 1 yıllık rapor, ilgili uzmanlarca
    {
        "rule_id": "4.2.50.metabolic.ctx_chenodeoxycholic_acid_coverage",
        "sut_section": "4.2.50",
        "gate_b_sources": ["C007055"],
        "drug_names": ["kenodeoksikolik asit", "chenodeoxycholic acid", "chenodiol"],
        "icd10_codes": ["E75.5", "E78"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["çocuk metabolizma hastalıkları", "çocuk endokrinolojisi ve metabolizma hastalıkları"],
        "prescriber_specialties": ["çocuk metabolizma hastalıkları", "çocuk endokrinolojisi ve metabolizma hastalıkları", "nöroloji", "çocuk nörolojisi"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yalnızca Cerebrotendinous Xanthomatosis tedavisinde; CYP27A1 genindeki mutasyon belgelenmiş ve 3. basamakta en az bir çocuk metabolizma veya çocuk endokrin+metabolizma uzmanının yer aldığı 1 yıllık sağlık kurulu raporuyla çocuk metabolizma/çocuk endokrin+metabolizma veya çocuk/erişkin nöroloji uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Yalnızca Cerebrotendinous Xanthomatosis hastalığının tedavisinde CYP27A1 genindeki mutasyonun belgelendirilmesi ve üçüncü basamak resmi sağlık hizmeti sunucusunda en az bir çocuk metabolizma veya çocuk endokrinoloji ve metabolizma hastalıkları uzman hekiminin yer aldığı 1 yıl süreli sağlık kurulu raporuna dayanılarak çocuk metabolizma, çocuk endokrinoloji ve metabolizma veya çocuk/erişkin nöroloji uzman hekimleri tarafından reçete edilmesi halinde bedeli ödenir (§4.2.50).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.51  —  droxidopa (dopamin beta hidroksilaz eksikliği)
    # -----------------------------------------------------------------

    # C007058 — droxidopa: DBH eksikliği (enzim/moleküler), diğer tedaviye yanıtsız semptomatik nörojenik ortostatik hipotansiyon
    {
        "rule_id": "4.2.51.neuro.droxidopa_dbh_deficiency_coverage",
        "sut_section": "4.2.51",
        "gate_b_sources": ["C007058"],
        "drug_names": ["droxidopa", "northera", "dihidroksifenilserin", "L-DOPS"],
        "icd10_codes": ["G90.3", "I95.1"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "enzim düzeyi ve/veya moleküler tetkikle dopamin beta hidroksilaz eksikliği tespit edilen ve diğer tedavi seçeneklerine yanıt alınamayan semptomatik nörojenik ortostatik hipotansiyon tedavisinde ödenir",
            "message_tr": "Enzim düzeyi ölçülmek suretiyle ve/veya moleküler tetkik ile dopamin beta hidroksilaz eksikliğinin tespit edildiği ve diğer tedavi seçeneklerine yanıt alınamayan semptomatik nörojenik ortostatik hipotansiyon hastalığının tedavisinde kullanılması halinde bedelleri Kurumca karşılanır (§4.2.51).",
        },
    },

    # C007059 — droxidopa: 3. basamak metabolizma/endokrin/kardiyoloji raporu + bu uzmanlarca reçete
    {
        "rule_id": "4.2.51.neuro.droxidopa_tertiary_metabolism_cardiology_coverage",
        "sut_section": "4.2.51",
        "gate_b_sources": ["C007059"],
        "drug_names": ["droxidopa", "northera", "dihidroksifenilserin", "L-DOPS"],
        "icd10_codes": ["G90.3", "I95.1"],
        "report_required": True,
        "report_specialties": ["metabolizma hastalıkları", "endokrinoloji", "kardiyoloji"],
        "prescriber_specialties": ["metabolizma hastalıkları", "endokrinoloji", "kardiyoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamak resmi sağlık hizmet sunucusunda metabolizma hastalıkları, endokrinoloji ve kardiyoloji uzmanının yer aldığı sağlık kurulu raporuyla bu uzmanlarca reçete edilirse ödenir",
            "message_tr": "Üçüncü basamak resmi sağlık hizmet sunucularında düzenlenen metabolizma hastalıkları, endokrinoloji ve kardiyoloji uzmanının yer aldığı sağlık kurulu raporuna dayanılarak metabolizma hastalıkları, endokrinoloji ve kardiyoloji uzman hekimleri tarafından reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.51).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.52  —  febuxostat (kronik hiperürisemi / gut / tümör lizis)
    # -----------------------------------------------------------------

    # C007064 — febuxostat: kronik hiperürisemi, allopurinol ≥3 ay yanıtsız/intolerans/kontrendike; UA<3,5 sonlanır; >6 ay ara kriter
    {
        "rule_id": "4.2.52.gout.febuxostat_hyperuricemia_allopurinol_failure_coverage",
        "sut_section": "4.2.52",
        "gate_b_sources": ["C007064"],
        "drug_names": ["febuxostat", "febuxostat", "urik asit düşürücü"],
        "icd10_codes": ["M10", "E79.0"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "kronik hiperürisemi (gut atağında ÜA>6 mg/dl, atak yoksa >8 mg/dl); allopurinol ile 3 ay tedaviye rağmen ÜA<6'ya düşmeyen veya allopurinol intolerans/kontrendikasyonu olanlarda başlanır; ÜA<3,5 olunca sonlanır; >6 ay ara verilirse başlangıç kriterleri yeniden aranır",
            "message_tr": "Serum ürik asit düzeylerinin gut artriti atağı bulunması durumunda 6 mg/dl'nin üzerinde, gut artriti atağı bulunmaması durumunda ise 8 mg/dl'nin üzerinde olduğu kronik hiperürisemi hastalarında, allopurinol ile 3 ay süreli tedaviye rağmen serum ürik asit düzeyi 6 mg/dl'nin altına düşmeyen veya allopurinol intoleransı olan ve/veya kontrendikasyonu olan hastalarda tedaviye başlanması halinde bedelleri Kurumca karşılanır; serum ürik asit düzeyleri 3,5 mg/dl'nin altına düşen hastalarda tedavi sonlandırılır, 6 aydan uzun süre ara verildiğinde başlangıç kriterleri aranır (§4.2.52).",
        },
    },

    # C007065 — febuxostat: iç/nefroloji/romatoloji/FTR uzmanından 1 yıllık lab'lı rapor, tüm uzmanlarca
    {
        "rule_id": "4.2.52.gout.febuxostat_1yr_report_specialty_coverage",
        "sut_section": "4.2.52",
        "gate_b_sources": ["C007065"],
        "drug_names": ["febuxostat"],
        "icd10_codes": ["M10", "E79.0"],
        "report_required": True,
        "report_duration_months": 12,
        "report_specialties": ["iç hastalıkları", "nefroloji", "romatoloji", "fizik tedavi ve rehabilitasyon"],
        "prescriber_specialties": ["tüm uzman hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "iç hastalıkları/nefroloji/romatoloji/FTR uzmanlarından birinin laboratuvar sonuçlarını da içeren 1 yıllık uzman raporuyla tüm uzman hekimlerce reçete edilirse ödenir",
            "message_tr": "İç hastalıkları, nefroloji, romatoloji veya fizik tedavi ve rehabilitasyon uzman hekimlerinden biri tarafından düzenlenen, laboratuvar sonuçlarının da yer aldığı 1 yıl süreli uzman hekim raporuna dayanılarak tüm uzman hekimler tarafından reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.52).",
        },
    },

    # C007067 — febuxostat: hematolojik malignite kemoterapisi + TLS orta/yüksek risk + allopurinol intolerans/kontrendike
    {
        "rule_id": "4.2.52.gout.febuxostat_tumor_lysis_hematologic_coverage",
        "sut_section": "4.2.52",
        "gate_b_sources": ["C007067"],
        "drug_names": ["febuxostat"],
        "icd10_codes": ["C81", "C82", "C83", "C84", "C85", "C91", "C92", "C88", "N14", "E79.0"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "hematolojik malignite için kemoterapi alan ve tümör lizis sendromu açısından orta veya yüksek riskli olup allopurinol intoleransı/kontrendikasyonu olanlarda hiperüriseminin önlenmesi ve tedavisinde ödenir",
            "message_tr": "Hematolojik maligniteler için kemoterapi alan ve tümör lizis sendromu açısından orta veya yüksek dereceye kadar riski olan allopurinol intoleransı ve/veya kontrendikasyonu olan hastalarda hiperüriseminin önlenmesi ve tedavisi için kullanılması halinde bedelleri Kurumca karşılanır (§4.2.52).",
        },
    },

    # C007068 — febuxostat: ≥1 hematoloji uzmanı yer alan ≤3 aylık rapor + hematoloji reçetesi
    {
        "rule_id": "4.2.52.gout.febuxostat_hematology_3mo_report_coverage",
        "sut_section": "4.2.52",
        "gate_b_sources": ["C007068"],
        "drug_names": ["febuxostat"],
        "icd10_codes": ["C81", "C82", "C83", "C84", "C85", "C91", "C92", "C88", "N14", "E79.0"],
        "report_required": True,
        "report_duration_months": 3,
        "report_specialties": ["hematoloji"],
        "prescriber_specialties": ["hematoloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "en az bir hematoloji uzmanının yer aldığı en fazla 3 ay süreli sağlık kurulu raporuyla hematoloji uzmanlarınca reçete edilirse ödenir",
            "message_tr": "En az bir hematoloji uzman hekiminin yer aldığı en fazla 3 ay süreli sağlık kurulu raporuna istinaden hematoloji uzman hekimlerince reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.52).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.53  —  beslenme ürünü (yağ asidi oksidasyon / kolestatik / lipoprotein)
    # -----------------------------------------------------------------

    # C007071 — beslenme ürünü: çoklu açil CoA dehidrogenaz eksikliği hariç, çocuk metabolizma/endo veya çocuk sağlığı raporu/reçete
    {
        "rule_id": "4.2.53.metabolic.nutrition_supplement_fatty_acid_coverage",
        "sut_section": "4.2.53",
        "gate_b_sources": ["C007071"],
        "drug_names": ["beslenme ürünü", "medical food", "diyete ek beslenme", "lipid emülsiyon"],
        "icd10_codes": ["E71.3", "E71.4", "K76", "E78"],
        "report_required": True,
        "report_specialties": ["çocuk metabolizma hastalıkları", "çocuk endokrinolojisi ve metabolizma hastalıkları"],
        "prescriber_specialties": ["çocuk metabolizma hastalıkları", "çocuk endokrinolojisi ve metabolizma hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "çoklu açil CoA dehidrogenaz eksikliği hariç; yağ asidi oksidasyon bozuklukları, kolestatik karaciğer hastalıkları veya lipoprotein metabolizması bozukluklarında diyete ek beslenme ürünü olarak çocuk metabolizma/çocuk endokrin+metabolizma uzmanlarından en az birinin yer aldığı raporla bu hekimlerce veya çocuk sağlığı uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Multiple açil CoA dehidrogenaz eksikliği hariç olmak üzere yağ asidi oksidasyon bozuklukları, kolestatik karaciğer hastalıkları veya lipoprotein metabolizması bozukluklarında diyete ek beslenme ürünü olarak çocuk metabolizma hastalıkları veya çocuk endokrinolojisi endokrinoloji ve metabolizma hastalıkları uzmanlarından en az birinin yer aldığı sağlık kurulu raporu ile bu hekimlerce veya çocuk sağlığı ve hastalıkları uzman hekimlerince reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.53).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.54  —  leishmaniasis (visseral / kutanöz)
    # -----------------------------------------------------------------

    # C007074 — visseral leishmaniasis: L. donovani, amfoterisin B yanıtsız/kontrendike veya HIV+ kombine, 3. basamak enf/çocuk enf
    {
        "rule_id": "4.2.54.inf.visceral_leishmaniasis_amphotericin_coverage",
        "sut_section": "4.2.54",
        "gate_b_sources": ["C007074"],
        "drug_names": ["miltefosin", "liposomal amfoterisin b", "amfoterisin b", "amphotericin b"],
        "icd10_codes": ["B55.0", "B55.2", "B21"],
        "report_required": True,
        "report_specialties": ["enfeksiyon hastalıkları ve klinik mikrobiyoloji", "çocuk enfeksiyon hastalıkları"],
        "prescriber_specialties": ["enfeksiyon hastalıkları ve klinik mikrobiyoloji", "çocuk enfeksiyon hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "Leishmania donovani kaynaklı visseral leishmaniasis; amfoterisin B'ye yanıtsızlık/ciddi yan etki ile kontrendike olduğu veya HIV pozitif hastalarda amfoterisin B ile kombine olarak; 3. basamak resmi sağlık hizmet sunucusunda enfeksiyon ve klinik mikrobiyoloji veya çocuk enfeksiyon uzmanınca düzenlenen rapora istinaden bu uzmanlarca reçete edilirse ödenir",
            "message_tr": "Leishmania donovani'nin neden olduğu visseral leishmaniasis tanısı almış hastaların tedavisinde; amphoterisin B tedavisine yanıtsızlık ya da ciddi yan etki nedeniyle amphoterisin B tedavisinin kontrendike olduğu durumlarda veya HIV pozitif hastalarda amphoterisin B ile kombine olarak üçüncü basamak resmi sağlık hizmet sunucularında, enfeksiyon hastalıkları ve klinik mikrobiyoloji veya çocuk enfeksiyon hastalıkları uzman hekimince düzenlenen sağlık raporuna istinaden enfeksiyon hastalıkları ve klinik mikrobiyoloji veya çocuk enfeksiyon hastalıkları uzman hekimi tarafından reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.54).",
        },
    },

    # C007075 — kutanöz leishmaniasis: L. braziliensis/guyanensis/panamensis, antimon/amfo kontrendike veya immünsupresif nüks, 3 ay rapor
    {
        "rule_id": "4.2.54.inf.cutaneous_leishmaniasis_3mo_report_coverage",
        "sut_section": "4.2.54",
        "gate_b_sources": ["C007075"],
        "drug_names": ["miltefosin", "liposomal amfoterisin b", "amfoterisin b", "amphotericin b"],
        "icd10_codes": ["B55.1", "B55.2", "B21"],
        "report_required": True,
        "report_duration_months": 3,
        "report_specialties": ["enfeksiyon hastalıkları ve klinik mikrobiyoloji", "çocuk enfeksiyon hastalıkları", "deri ve zührevi hastalıkları"],
        "prescriber_specialties": ["enfeksiyon hastalıkları ve klinik mikrobiyoloji", "çocuk enfeksiyon hastalıkları", "deri ve zührevi hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "Leishmania braziliensis/guyanensis/panamensis kaynaklı kutanöz leishmaniasis; antimon bileşiklerine veya amfoterisin B'ye yanıtsızlık/ciddi yan etki ile kontrendike veya bağışıklık sistemi baskılanmışda nüks; 3. basamakta ≥1 enfeksiyon/çocuk enfeksiyon uzmanı + ≥1 deri ve zührevi hastalıkları uzmanının yer aldığı 3 ay süreli raporla bu uzmanlardan biri tarafından reçete edilirse ödenir",
            "message_tr": "Leishmania braziliensis, leishmania guyanensis veya leishmania panamensis'in neden olduğu kutanöz leishmaniasis tanısı almış hastaların tedavisinde; antimon bileşiklerine veya amphoterisin B tedavisine yanıtsızlık ya da ciddi yan etki nedeniyle bu ilaçların kontrendike olduğu durumlarda veya bağışıklık sistemi baskılanmış hastalarda nüks gelişmesi durumunda üçüncü basamak resmi sağlık hizmet sunucularında, en az bir enfeksiyon hastalıkları ve klinik mikrobiyoloji veya çocuk enfeksiyon hastalıkları uzman hekimi ile en az bir deri ve zührevi hastalıkları uzman hekiminin yer aldığı üç ay süreli sağlık kurulu raporuna istinaden enfeksiyon hastalıkları ve klinik mikrobiyoloji veya çocuk enfeksiyon hastalıkları veya deri ve zührevi hastalıkları uzman hekimi tarafından reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.54).",
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
