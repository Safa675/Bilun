"""§2.4.4 treatment package pricing & coverage rules — wave-2a batch.

Gate-B encoded rules for SUT §2.4.4 (Bazı tetkik ve tedavi yöntemlerinin usul
ve esasları), part 2. This batch covers the §2.4.4 clauses that were NOT
already encoded in treatment_pricing_2_4_batch1_rules.py: HBO (B) coverage /
session-caps / start-windows, radiosurgery board report (C), hemodialysis &
peritoneal dialysis facility/prescription rules (D-1/D-2), angio per-physician
cap (E), and the §2.4.4.F-1/F-2 physical-therapy report / session-cap /
coverage rules.

Modalities covered here: COVERAGE, MUST_BILL, MANDATORY, NO_PAY,
MUST_NOT_BILL, REGULATORY_ACTION, PERMISSION, PROHIBITED.

Merge target: data/gazette/prose_rules/treatment_pricing_2_4.json
"""

from __future__ import annotations

from typing import Any

WAVE2A_BATCH_RULES: list[dict[str, Any]] = [
    # ── §2.4.4.B — Hiperbarik oksijen (HBO) tedavisi ──────────────────────
    # (1) COVERAGE — HBO yalnızca hiperbarik merkezli/açıklı 2./3. basamak sunucuda
    {
        "rule_id": "2.4.4.B.(1).hbo_facility_coverage",
        "sut_section": "2.4.4.B",
        "condition": {
            "procedure_category": "hyperbaric_oxygen",
            "facility_not_in": [
                "contracted_public_with_hbo_center",
                "licensed_private_2nd_3rd_step_hbo",
            ],
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "HBO bedelleri bünyesinde hiperbarik oksijen tedavi merkezi "
                "bulunan sözleşmeli resmi sunucuda veya Yönetmelik kapsamında "
                "faaliyet süren sözleşmeli özel 2./3. basamak sunucuda "
                "yapılması halinde Kurumca karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000869"],
        "encode_batch": "W2A",
    },
    # (2) REGULATORY_ACTION — acil hariç sağlık kurulu raporu (tanı + seans sayısı)
    {
        "rule_id": "2.4.4.B.(2).hbo_health_board_report",
        "sut_section": "2.4.4.B",
        "condition": {
            "procedure_category": "hyperbaric_oxygen",
            "is_emergency": False,
            "health_board_report_present": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "acil durumlar hariç HBO için 2./3. basamak sunucularca tanı ve "
                "uygulanması istenilen seans sayısını içeren sağlık kurulu raporu düzenlenmelidir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000870"],
        "encode_batch": "W2A",
    },
    # (6) PERMISSION — rapor sonrası 10 gün içinde başlanmalı; ara ≤7 iş günü
    {
        "rule_id": "2.4.4.B.(6).hbo_start_10d_gap_7_biz_days",
        "sut_section": "2.4.4.B",
        "condition": {
            "procedure_category": "hyperbaric_oxygen",
            "days_from_report_to_treatment": {"min": 11},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "HBO tedavisine rapor tarihinden en geç 10 gün içinde başlanmalı; "
                "uzman onayıyla en fazla 7 iş günü kesintisiz ara verilebilir, daha "
                "uzun arada yeni rapor düzenlenir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000874"],
        "encode_batch": "W2A",
    },
    # (7) COVERAGE — günde en fazla 1 seans; ani işitme kaybı/acilde ilk 7 gün ≥2
    {
        "rule_id": "2.4.4.B.(7).hbo_one_session_per_day",
        "sut_section": "2.4.4.B",
        "condition": {
            "procedure_category": "hyperbaric_oxygen",
            "sessions_per_day": {"min": 2},
            "sudden_hearing_loss_or_emergency_first_7d": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "günde en fazla 1 seans HBO ödenir; ani işitme kaybı ve acil "
                "hastalarda tedavinin başladığı gün dahil ilk 7 günde günde birden "
                "fazla seans ödenir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000875"],
        "encode_batch": "W2A",
    },
    # (9) MANDATORY — santral retinal arter tıkanıklığında tanı+5 gün içinde başlanmalı
    {
        "rule_id": "2.4.4.B.(9).hbo_crao_start_within_5d",
        "sut_section": "2.4.4.B",
        "condition": {
            "diagnosis_any": ["H341"],  # central retinal artery occlusion
            "procedure_category": "hyperbaric_oxygen",
            "days_from_diagnosis_to_treatment": {"min": 6},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "santral retinal arter tıkanıklığında HBO ödenebilmesi için tanıyı "
                "takiben 5 gün içinde tedaviye başlanmış olmalı"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000877"],
        "encode_batch": "W2A",
    },
    # (10) MANDATORY — hipoksik/anoksik ensefalopatide tanı+5 gün içinde başlanmalı
    {
        "rule_id": "2.4.4.B.(10).hbo_anoxic_encephalopathy_start_5d",
        "sut_section": "2.4.4.B",
        "condition": {
            "diagnosis_any": ["G931"],  # anoxic brain damage / encephalopathy
            "procedure_category": "hyperbaric_oxygen",
            "days_from_diagnosis_to_treatment": {"min": 6},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "hipoksik/anoksik ensefalopati tanısında HBO ödenebilmesi için tanıyı "
                "takiben ilk 5 gün içinde tedaviye başlanmış olmalı"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000878"],
        "encode_batch": "W2A",
    },
    # (12) COVERAGE — HBO yalnızca EK-2/D-3 endikasyon+ICD-10 ile EK-2/C bedeli üzerinden
    {
        "rule_id": "2.4.4.B.(12).hbo_ek2d3_indications_only",
        "sut_section": "2.4.4.B",
        "condition": {
            "procedure_category": "hyperbaric_oxygen",
            "indication_in_ek2d3": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "HBO bedelleri yalnızca SUT eki EK-2/D-3 endikasyonları ve ICD-10 "
                "tanı kodları esas alınarak EK-2/C bedelleri üzerinden karşılanır"
            ),
            "annex_basis": "EK-2/C",
            "severity": "error",
        },
        "gate_b_sources": ["C000880"],
        "encode_batch": "W2A",
    },
    # (13) REGULATORY_ACTION — trafik kazası sonrası EK-2/D-3 seans sınırları uygulanmaz
    {
        "rule_id": "2.4.4.B.(13).hbo_traffic_accident_no_session_limit",
        "sut_section": "2.4.4.B",
        "condition": {
            "procedure_category": "hyperbaric_oxygen",
            "origin_is_traffic_accident": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "trafik kazası sonrası gerekli görülen HBO uygulamalarında "
                "EK-2/D-3 seans sayısı sınırlamaları dikkate alınmaz"
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C000881"],
        "encode_batch": "W2A",
    },

    # ── §2.4.4.C — Radyo cerrahi yöntemleri ────────────────────────────────
    # (1) MANDATORY — radyocerrahi için gerekli uzmanlık içeren sağlık kurulu raporu
    {
        "rule_id": "2.4.4.C.(1).radiosurgery_board_report_required",
        "sut_section": "2.4.4.C",
        "condition": {
            "procedure_category": "radiosurgery",
            "health_board_report_present": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "radyocerrahi bedelleri için; robotik lineer akselaratör "
                "(CyberKnife) işleminde radyasyon onkolojisi uzmanının yer aldığı, "
                "Kobalt-60 (GammaKnife) işleminde en az 2 beyin cerrahi + 1 radyasyon "
                "onkolojisi uzmanının yer aldığı sağlık kurulu raporu düzenlenmelidir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000883"],
        "encode_batch": "W2A",
    },

    # ── §2.4.4.D-1 — Hemodiyaliz (merkez/ev) ───────────────────────────────
    # (3) REGULATORY_ACTION — diyaliz merkezinde görevli hekimce reçete (tanıya dayalı ilaç hariç)
    {
        "rule_id": "2.4.4.D-1.(3).dialysis_prescription_by_center_physician",
        "sut_section": "2.4.4.D-1",
        "condition": {
            "procedure_category": "hemodialysis",
            "non_diagnosis_based_drug_prescribed_outside_center": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "tanıya dayalı işlem kapsamı dışındaki hastaya gerekli ilaçlar, "
                "merkezde görevli hekimlerce SUT/esaslarına uygun reçete edilir"
            ),
        },
        "gate_b_sources": ["C000934"],
        "encode_batch": "W2A",
    },
    # (10) REGULATORY_ACTION — her hemodiyaliz seansı en az 4 saat (tıbbi zorunluluk hariç)
    {
        "rule_id": "2.4.4.D-1.(10).hemodialysis_min_4_hours",
        "sut_section": "2.4.4.D-1",
        "condition": {
            "procedure_code_any": ["P5010046", "P5010047"],
            "session_hours": {"max": 3.99},
            "medical_necessity_exception": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "hemodiyaliz tedavisinin her bir seansı tıbbi zorunluluklar hariç "
                "en az 4 saat olarak uygulanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000941"],
        "encode_batch": "W2A",
    },
    # (3) REGULATORY_ACTION — takip/tedavi merkezinde görevli hekimce reçete (ev hemodiyalizi)
    {
        "rule_id": "2.4.4.D-1.(3ev).home_dialysis_prescription_by_followup_center",
        "sut_section": "2.4.4.D-1",
        "condition": {
            "procedure_code_any": ["P5010050"],
            "non_diagnosis_based_drug_prescribed_outside_followup_center": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "ev hemodiyalizi hastasına gerekli ilaçlar (tanıya dayalı işlem hariç), "
                "hastanın takip ve tedavisini yapan merkezde görevli hekimlerce reçete edilir"
            ),
        },
        "gate_b_sources": ["C000950"],
        "encode_batch": "W2A",
    },

    # ── §2.4.4.D-2 — Periton diyalizi ──────────────────────────────────────
    # (1) COVERAGE — böbrek yetmezliği periton diyalizi/hemofiltrasyon/plazmaferez hizmet başı
    {
        "rule_id": "2.4.4.D-2.(1).peritoneal_hemofiltration_plasmapheresis_fee_for_service",
        "sut_section": "2.4.4.D-2",
        "condition": {
            "procedure_category_any": ["peritoneal_dialysis", "hemofiltration", "plasmapheresis"],
            "diagnosis_any": ["N18", "N19"],
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "böbrek yetmezliği periton diyalizi, hemofiltrasyon ve plazmaferez ile "
                "tetkik/tahlil ve diyalize ilişkin diğer tedaviler hizmet başı ödeme yöntemiyle karşılanır"
            ),
            "annex_basis": "fee_for_service",
        },
        "gate_b_sources": ["C000957"],
        "encode_batch": "W2A",
    },
    # (1) COVERAGE — SAPD izleme/ay/çocuk, değişim sıvısı torba sınırları
    {
        "rule_id": "2.4.4.D-2.(1).sapd_monitoring_and_fluid_limits",
        "sut_section": "2.4.4.D-2",
        "condition": {
            "procedure_category": "continuous_ambulatory_peritoneal_dialysis",
            "report_by_nephrology_specialist": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "SAPD raporu erişkin/çocuk nefroloji uzmanınca düzenlenir; izleme bedeli "
                "erişkin ayda en fazla 2, çocuk ayda en fazla 3; değişim sıvısı ayda en "
                "fazla 150 torba; aminoasit/iCODEKSTRİN günde en fazla 1 kez karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000959"],
        "encode_batch": "W2A",
    },
    # (1) MANDATORY — aletli periton diyalizi sağlık kurulu raporu (nefroloji uzmanı zorunlu)
    {
        "rule_id": "2.4.4.D-2.(1).apd_board_report_nephrology",
        "sut_section": "2.4.4.D-2",
        "condition": {
            "procedure_category": "automated_peritoneal_dialysis",
            "facility_has_peritoneal_dialysis_unit": False,
            "nephrology_specialist_on_board": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "aletli periton diyalizi tedavilerine yönelik sağlık kurulu raporları, "
                "bünyesinde periton diyalizi ünitesi bulunan sunucu sağlık kurullarınca, "
                "kurulda nefroloji uzman hekimi yer almak üzere düzenlenmelidir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000963"],
        "encode_batch": "W2A",
    },

    # ── §2.4.4.E — Anjiografi & PKG ────────────────────────────────────────
    # (4) COVERAGE — anjiografi/PKG her hekim için günlük en fazla 15 hasta
    {
        "rule_id": "2.4.4.E.(4).angio_pcı_per_physician_daily_cap_15",
        "sut_section": "2.4.4.E",
        "condition": {
            "procedure_category_any": ["coronary_angiography", "percutaneous_coronary_intervention"],
            "cases_per_physician_per_day": {"min": 16},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "anjiografi ve perkütan koroner girişim için işlemi yapan sunucuda "
                "görevli ilgili hekim sayısı esas alınarak her hekim için günlük en "
                "fazla 15 hastaya yapılan işlem bedeli karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000970"],
        "encode_batch": "W2A",
    },

    # ── §2.4.4.F-1 — Fizik tedavi raporu (kim düzenler) ────────────────────
    # (a) REGULATORY_ACTION — 30 seansa kadar fiziksel tıp ve rehab. uzmanınca
    {
        "rule_id": "2.4.4.F-1.(a).physio_up_to_30_sessions_specialist_or_3rd_step",
        "sut_section": "2.4.4.F-1",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "sessions": {"min": 1, "max": 30},
            "prescriber_specialty_any": ["physical_medicine_rehabilitation"],
            "diagnosis_in_ek2d2_plexus_excluding_congenital": True,
            "facility_tier_in": ["third_step_public", "moh_2nd_step_public"],
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "30 seansa kadar fizik tedavi ve rehabilitasyon fiziksel tıp ve "
                "rehabilitasyon uzmanınca; EK-2/D-2 pleksus bozukluklarında (doğumsal "
                "hariç) 3. basamak veya Sağlık Bakanlığı 2. basamak fiziksel tıp ve "
                "rehabilitasyon uzmanınca düzenlenir"
            ),
        },
        "gate_b_sources": ["C000984"],
        "encode_batch": "W2A",
    },
    # sağlık raporu düzenlenmesi gerekmektedir (MANDATORY)
    {
        "rule_id": "2.4.4.F-1.health_report_required",
        "sut_section": "2.4.4.F-1",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "health_report_present": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "fizik tedavi ve rehabilitasyon için SUT 2.4.4.F-1 maddesine uygun "
                "sağlık raporu düzenlenmesi gerekmektedir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000991"],
        "encode_batch": "W2A",
    },

    # ── §2.4.4.F-2 — Fizik tedavi (uygulama) ───────────────────────────────
    # (1) MANDATORY — fizik tedavi ancak F-1 raporuyla faturalandırılabilir
    {
        "rule_id": "2.4.4.F-2.(1).physio_billing_requires_f1_report",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "report_per_2_4_4_F1_present": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "fizik tedavi ve rehabilitasyon işlemlerinin faturalandırılabilmesi "
                "için SUT 2.4.4.F-1 maddesinde tanımlanan sağlık raporunun düzenlenmesi gerekir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001007"],
        "encode_batch": "W2A",
    },
    # (3) COVERAGE — vazife/harp malulleri tüm EK-2/D-2 tanılarında bölge kontrolü yok
    {
        "rule_id": "2.4.4.F-2.(3).duty_war_veterans_physio_all_diagnoses",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "patient_category": "duty_or_war_veteran_or_disabled",
            "report_tier": "third_step_public_with_pmnr_specialist",
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "3713/5434/2330 kapsamı vazife ve harp malulleri ile yaralananlara "
                "EK-2/D-2 tüm tanılarında bölge kontrolü olmaksızın, raporlu sağlık "
                "kurullarınca (30'ar seanslık rapor koşuluyla) fizik tedavi karşılanır"
            ),
            "annex_basis": "EK-2/D-2",
        },
        "gate_b_sources": ["C001011"],
        "encode_batch": "W2A",
    },
    # (5) COVERAGE — son bir yıl aynı bölge 30 / iki bölge 60 seans; bölge için 2 rapor
    {
        "rule_id": "2.4.4.F-2.(5).physio_annual_region_session_caps",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "diagnosis_not_in": ["G80", "ek2d2_star_marked"],
            "sessions_same_region_within_1y": {"min": 31},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "son bir yılda aynı bölgeden en fazla 30 seans, iki farklı bölgeden en "
                "fazla 60 seans ödenir; aynı bölge için yılda en fazla 2 sağlık raporu; "
                "EK-2/D-2 (*) ve G80 tanılarında bölge kontrolü yapılmaz"
            ),
            "annex_basis": "EK-2/D-2",
            "severity": "error",
        },
        "gate_b_sources": ["C001015"],
        "encode_batch": "W2A",
    },
    # (6) COVERAGE — bölge başına 30 seans; (*) tanılarda ilk rapor yılı içinde sınırsız
    {
        "rule_id": "2.4.4.F-2.(6).physio_star_diagnosis_annual_window",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "diagnosis_in": ["ek2d2_star_marked"],
            "treatment_outside_first_report_year_window": True,
            "report_per_2_4_4_F1_present": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "EK-2/D-2 (*) tanılar hariç bölge başına en fazla 30 seans; (*) tanılarda "
                "ilk rapor tarihi itibarıyla bir yıl içinde uygulanan tedavi ödenir, "
                "devam yıllarında 0-30 ve 31-60 seans için F-1 raporu, 61+ için 3. basamak raporu gerekir"
            ),
            "annex_basis": "EK-2/D-2",
            "severity": "error",
        },
        "gate_b_sources": ["C001016"],
        "encode_batch": "W2A",
    },
    # (9) COVERAGE — yatarak fizik tedavide diğer hizmetler (yatak/tetkik/ilaç) hizmet başı
    {
        "rule_id": "2.4.4.F-2.(9).inpatient_physio_concomitant_services_fee_for_service",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "procedure_category": "physiotherapy_rehab_inpatient",
            "concomitant_service": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "yatarak fizik tedavide; fizik tedavi dışındaki hizmetler (yatak bedeli, "
                "tetkik, ilaç, tıbbi malzeme) SUT hükümlerine uyulmak koşuluyla hizmet "
                "başına ödeme yöntemiyle karşılanır"
            ),
            "annex_basis": "fee_for_service",
        },
        "gate_b_sources": ["C001019"],
        "encode_batch": "W2A",
    },
    # (10) REGULATORY_ACTION — trafik kazası fizik tedavisinde süre/seans/bölge kontrolleri ayrı
    {
        "rule_id": "2.4.4.F-2.(10).traffic_accident_physio_controls_isolated",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "origin_is_traffic_accident": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "trafik kazası sonrası fizik tedavinin süre, seans ve bölge "
                "kontrollerinde kazayla ilişkisiz fizik tedavi uygulamaları dikkate alınmaz"
            ),
        },
        "gate_b_sources": ["C001020"],
        "encode_batch": "W2A",
    },
    # (a) COVERAGE — (*) tanılarda yıl içinde en fazla 90 seans (F-1 raporu)
    {
        "rule_id": "2.4.4.F-2.(a).physio_star_diagnosis_90_sessions_annual",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "diagnosis_in": ["ek2d2_star_marked"],
            "report_per_2_4_4_F1_present": True,
            "sessions_within_year": {"min": 91},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "F-1 raporlarına istinaden yıl içinde en fazla 90 seans fizik tedavi "
                "ödenir; 16 yaş üstü 31-60 ve 61-90 seans resmi sunucuca uygulanmalı, "
                "61+ seans Bakanlık sunucusunda PMR uzmanlı sağlık kurulu raporuyla"
            ),
            "annex_basis": "EK-2/D-2",
            "severity": "error",
        },
        "gate_b_sources": ["C001025"],
        "encode_batch": "W2A",
    },
    # (b) COVERAGE — G80 cerrahi/botulinium sonrası yılda en fazla 2 kez ilave 30 seans
    {
        "rule_id": "2.4.4.F-2.(b).g80_post_surgery_additional_30_sessions",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "diagnosis_any": ["G80"],
            "procedure_category": "physiotherapy_rehab",
            "prior_surgery_or_botulinum_for_mobility": True,
            "additional_sessions_per_year": {"min": 61},  # >2x30
            "report_tier": "third_step_public_with_pmnr_specialist",
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "G80 tanısında cerrahi/botulinium sonrası mobilitenin korunması için "
                "3. basamak sağlık kurulu raporuyla yılda en fazla iki kez ilave 30 seans "
                "fizik tedavi karşılanır"
            ),
            "annex_basis": "EK-2/D-2",
            "severity": "error",
        },
        "gate_b_sources": ["C001028"],
        "encode_batch": "W2A",
    },
    # (12) COVERAGE — doğal afet provizyonu, ampütasyon/kırık/sinir/tendon yaralanması +30 seans
    {
        "rule_id": "2.4.4.F-2.(12).disaster_provision_amputation_fracture_additional_30",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "diagnosis_category_any": ["amputation", "fracture", "peripheral_nerve_injury",
                                       "lumbosacral_plexus_injury", "tendon_injury"],
            "procedure_category": "physiotherapy_rehab",
            "provision_is_natural_disaster": True,
            "additional_sessions_beyond_30": True,
            "report_tier": "third_step_public_with_pmnr_specialist",
            "already_used_one_time_additional": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "5510 md.75 afet yaralanmalarında 'doğal afet' provizyonuyla EK-2/D-2 "
                "ampütasyon/kırık/periferik sinir/lumbosakral pleksus/tendon yaralanması "
                "tanılarında 3. basamak sağlık kurulu raporuyla bir defaya mahsus ilave 30 seans ödenir"
            ),
            "annex_basis": "EK-2/D-2",
            "severity": "error",
        },
        "gate_b_sources": ["C001032"],
        "encode_batch": "W2A",
    },
]
