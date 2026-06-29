"""§2.4.4 treatment package pricing & coverage rules — wave-2b batch.

Gate-B encoded rules for SUT §2.4.4 (Bazı tetkik ve tedavi yöntemlerinin usul
ve esasları), part 2. This batch covers the §2.4.4 clauses NOT yet encoded in
treatment_pricing_2_4_batch1_rules.py (T1) or the wave-2a batch (W2A): the
private-provider physical-therapy provisions (F-3), ESWT (F-4), robotik
rehabilitasyon (F-5), spor hekimliği / tıbbi ekoloji (F-6), sitogenetik &
moleküler genetik tetkikler (G-1/G-2), yoğun bakım (H), göz hastalıkları
ayaktan sevk kontrolleri (I), kaplıca tedavileri (J) and palyatif bakım (K).

Modalities covered here: COVERAGE, MUST_BILL, MANDATORY, NO_PAY,
MUST_NOT_BILL, REGULATORY_ACTION, PERMISSION.

Merge target: data/gazette/prose_rules/treatment_pricing_2_4.json
"""

from __future__ import annotations

from typing import Any

WAVE2B_BATCH_RULES: list[dict[str, Any]] = [
    # ── §2.4.4.F-3 — Özel sunucularda fizik tedavi ve rehabilitasyon ─────────
    # (1) MANDATORY — özel sunucularda F-1/F-2 + aşağıdaki düzenlemelere uyulacak
    {
        "rule_id": "2.4.4.F-3.(1).private_provider_physio_compliance_with_F1_F2",
        "sut_section": "2.4.4.F-3",
        "condition": {
            "provider_type": "private",
            "procedure_category": "physiotherapy_rehab",
        },
        "action": {
            "billable": False,
            "enforcement": "compliance_review",
            "message_tr": (
                "özel sağlık hizmeti sunucularınca yapılacak fizik tedavi ve "
                "rehabilitasyon işlemlerinde SUT'un 2.4.4.F-1 ve 2.4.4.F-2 madde "
                "hükümleri ile birlikte F-3 maddesindeki düzenlemelere de uyulmalıdır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001055"],
        "encode_batch": "W2B",
    },
    # (a) PERMISSION — özel sunucu yatarak: EK-2/D-2 (D) hariç, yılda en fazla 60 seans;
    #     vazife/harp malullerinde (*) tanılarda seans sınırsız
    {
        "rule_id": "2.4.4.F-3.(a).private_inpatient_60_sessions_d_group_excluded",
        "sut_section": "2.4.4.F-3",
        "condition": {
            "provider_type": "private",
            "treatment_setting": "inpatient",
            "procedure_category": "physiotherapy_rehab",
            "diagnosis_in_ek2d2_d_group": False,
            "patient_category": "duty_or_war_veteran_or_disabled",
            "diagnosis_in": ["ek2d2_star_marked"],
        },
        "action": {
            "billable": True,
            "enforcement": "session_cap_override",
            "message_tr": (
                "özel sunucularda yatarak fizik tedavide EK-2/D-2 (D) grubu hariç diğer "
                "tanılarda yılda en fazla 60 seans; vazife/harp malullerine 2.4.4.F-2(3) "
                "raporlarına istinaden (*) tanılarda seans kısıtlaması olmaksızın fatura edilir"
            ),
            "annex_basis": "EK-2/D-2",
        },
        "gate_b_sources": ["C001056"],
        "encode_batch": "W2B",
    },
    # (c) COVERAGE — seans en az 60 dakika; tıbbi nedenle erken biterse puanın %50'si
    {
        "rule_id": "2.4.4.F-3.(c).physio_session_min_60min_50pct_on_early_end",
        "sut_section": "2.4.4.F-3",
        "condition": {
            "provider_type": "private",
            "procedure_category": "physiotherapy_rehab",
            "session_minutes": {"max": 59},
            "early_end_medically_accepted": True,
        },
        "action": {
            "billable": True,
            "enforcement": "partial_payment",
            "message_tr": (
                "fizik tedavi ve rehabilitasyon seansları en az 60 dakika uygulanır; "
                "tıbbi nedenlerle süreden önce bitmesi halinde, gerekçesi Kurumca kabul "
                "edilirse tedavi puanının %50'si ödenir"
            ),
        },
        "gate_b_sources": ["C001058"],
        "encode_batch": "W2B",
    },
    # (ç) REGULATORY_ACTION — özel sunucu PMR ayaktan günlük muayene sınırı = saat×6, en fazla 48/hekim
    {
        "rule_id": "2.4.4.F-3.(c2).private_pmr_outpatient_daily_exam_cap_48",
        "sut_section": "2.4.4.F-3",
        "condition": {
            "provider_type": "private",
            "procedure_category": "physiotherapy_rehab",
            "visit_type": "outpatient_non_emergency",
            "daily_exams_per_physician": {"min": 49},
        },
        "action": {
            "billable": False,
            "enforcement": "daily_exam_cap",
            "message_tr": (
                "özel sunucuda fiziksel tıp ve rehabilitasyon ayaktan başvurularda günlük "
                "muayene sınırı (acil hariç) çalışan hekimlerin saat×6 ile bulunur; her hekim "
                "için günlük muayene sayısı her halükârda 48'i geçemez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001059"],
        "encode_batch": "W2B",
    },
    # (d) REGULATORY_ACTION — özel sunucu ayaktan FTR: hekim günlük ≤8 saat; A/B/C/D grup hasta kapları
    {
        "rule_id": "2.4.4.F-3.(d).private_outpatient_physio_group_caps_8h",
        "sut_section": "2.4.4.F-3",
        "condition": {
            "provider_type": "private",
            "procedure_category": "physiotherapy_rehab",
            "visit_type": "outpatient",
            "daily_billing_hours_per_physician": {"min": 9},
        },
        "action": {
            "billable": False,
            "enforcement": "physician_hour_and_case_cap",
            "message_tr": (
                "özel sunucuda ayaktan fizik tedavi, hekim başına günlük en fazla 8 saat üzerinden "
                "fatura edilir; 1 uzman+1 fizyoterapist için (A) grubu günlük ≤8, (A)+(B) ≤16; "
                "1 uzman+2 fizyoterapist için (A)+(B) ≤16; ilave (C) ≤32, (C)+(D) ≤64 hasta; "
                "yatarak FTR'de bu sayılar dikkate alınmaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001060"],
        "encode_batch": "W2B",
    },

    # ── §2.4.4.F-4 — ESWT (Ekstrakorporeal şok dalga tedavisi) ───────────────
    # (2) COVERAGE — ESWT yalnızca epin calcanei/plantar fasiit/epikondilit/kalsifik tendinit
    {
        "rule_id": "2.4.4.F-4.(2).eswt_indication_limited",
        "sut_section": "2.4.4.F-4",
        "condition": {
            "procedure_category": "eswt_shock_wave",
            "diagnosis_category_not_in": [
                "epin_calcanei", "plantar_fasciitis", "epicondylitis", "calcific_tendinitis",
            ],
        },
        "action": {
            "billable": False,
            "enforcement": "indication_gate",
            "message_tr": (
                "ESWT tedavisi yalnızca epin calcanei, plantar fasiit, epikondilit ve "
                "kalsifik tendinit tanılarında uygulanması halinde Kurumca karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001063"],
        "encode_batch": "W2B",
    },
    # (3) COVERAGE — ESWT EK-2/C üzerinden; yılda en fazla 2 bölge, bölge başına en fazla 5 seans
    {
        "rule_id": "2.4.4.F-4.(3).eswt_ek2c_2_regions_5_sessions",
        "sut_section": "2.4.4.F-4",
        "condition": {
            "procedure_category": "eswt_shock_wave",
            "regions_within_year": {"min": 3},
        },
        "action": {
            "billable": False,
            "enforcement": "regional_session_cap",
            "message_tr": (
                "ESWT EK-2/C Listesi esas alınarak karşılanır; bir hasta için bir yılda en fazla "
                "2 farklı vücut bölgesi, bölge başına en fazla 5 seans ödenir; ekstremite sağ ve "
                "sol ayrı bölge sayılır; F-2(5) bölge/seans/rapor kontrolleri hesaba katılmaz"
            ),
            "annex_basis": "EK-2/C",
            "severity": "error",
        },
        "gate_b_sources": ["C001064"],
        "encode_batch": "W2B",
    },
    # (4) MUST_NOT_BILL — ESWT diğer FTR işlemleriyle birlikte faturalandırılamaz
    {
        "rule_id": "2.4.4.F-4.(4).eswt_not_with_other_physio",
        "sut_section": "2.4.4.F-4",
        "condition": {
            "procedure_category": "eswt_shock_wave",
            "billed_with_other_physiotherapy": True,
        },
        "action": {
            "billable": False,
            "enforcement": "bundling_prohibition",
            "message_tr": "ESWT işlemi diğer fizik tedavi ve rehabilitasyon işlemleri ile birlikte faturalandırılamaz",
            "severity": "error",
        },
        "gate_b_sources": ["C001065"],
        "encode_batch": "W2B",
    },

    # ── §2.4.4.F-5 — Robotik rehabilitasyon ──────────────────────────────────
    # (2) COVERAGE — robotik rehab yalnızca EK-2/D-2 (**) ICD-10 tanılarında
    {
        "rule_id": "2.4.4.F-5.(2).robotic_rehab_double_star_indications_only",
        "sut_section": "2.4.4.F-5",
        "condition": {
            "procedure_category": "robotic_rehabilitation",
            "diagnosis_in": ["ek2d2_double_star_marked"],
            "indication_in_ek2d2_double_star": False,
        },
        "action": {
            "billable": False,
            "enforcement": "indication_gate",
            "message_tr": (
                "robotik rehabilitasyon sistemi uygulaması EK-2/D-2 Listesinde yer alan "
                "(**) işaretli ICD-10 kodlarındaki tanılarda uygulanması halinde karşılanır"
            ),
            "annex_basis": "EK-2/D-2",
            "severity": "error",
        },
        "gate_b_sources": ["C001070"],
        "encode_batch": "W2B",
    },
    # (3) MUST_BILL — robotik rehab EK-2/D-2 grupları + EK-2/C puanları üzerinden
    {
        "rule_id": "2.4.4.F-5.(3).robotic_rehab_billed_ek2c_points",
        "sut_section": "2.4.4.F-5",
        "condition": {
            "procedure_category": "robotic_rehabilitation",
            "billing_basis": "other",
        },
        "action": {
            "billable": True,
            "enforcement": "pricing_basis",
            "message_tr": (
                "robotik rehabilitasyon sistemi uygulaması EK-2/D-2 grupları dikkate alınarak "
                "EK-2/C Listesindeki puanlar üzerinden faturalandırılır"
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001071"],
        "encode_batch": "W2B",
    },
    # (4) MUST_NOT_BILL — robotik rehab diğer FTR işlemleriyle birlikte faturalandırılamaz
    {
        "rule_id": "2.4.4.F-5.(4).robotic_rehab_not_with_other_physio",
        "sut_section": "2.4.4.F-5",
        "condition": {
            "procedure_category": "robotic_rehabilitation",
            "billed_with_other_physiotherapy": True,
        },
        "action": {
            "billable": False,
            "enforcement": "bundling_prohibition",
            "message_tr": "robotik rehabilitasyon sistemi uygulaması diğer fizik tedavi ve rehabilitasyon işlemleri ile birlikte faturalandırılamaz",
            "severity": "error",
        },
        "gate_b_sources": ["C001072"],
        "encode_batch": "W2B",
    },
    # (5) PERMISSION — hasta başına yılda en fazla 30 seans; sistem başına günlük 8 hasta (+6)
    {
        "rule_id": "2.4.4.F-5.(5).robotic_rehab_30_sessions_annual_8_daily_per_system",
        "sut_section": "2.4.4.F-5",
        "condition": {
            "procedure_category": "robotic_rehabilitation",
            "sessions_per_patient_per_year": {"min": 31},
        },
        "action": {
            "billable": False,
            "enforcement": "session_and_case_cap",
            "message_tr": (
                "bir hasta için yılda en fazla 30 seans robotik rehabilitasyon uygulanabilir; "
                "2./3. basamak sunucular her sistem başına günlük en fazla 8, 4+ tam zamanlı PMR "
                "uzmanı olan sunucular ilave 6 hasta için seans faturalandırabilir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001077"],
        "encode_batch": "W2B",
    },

    # ── §2.4.4.F-6 — Spor hekimliği / Tıbbi ekoloji ve hidroklimatoloji ──────
    # (1) MANDATORY — resmi sunucuda spor hekimi / tıbbi ekoloji uzmanınca sağlık raporu
    {
        "rule_id": "2.4.4.F-6.(1).sports_med_ecology_health_report_required",
        "sut_section": "2.4.4.F-6",
        "condition": {
            "procedure_category_any": ["sports_medicine", "medical_ecology_hydroclimatology"],
            "provider_type": "public",
            "health_report_present": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "resmi sunucularda spor hekimliği / tıbbi ekoloji ve hidroklimatoloji "
                "uygulamalarının karşılanabilmesi için ilgili hekim/uzman tarafından tedavi ve "
                "tedavi süresini belirten sağlık raporu düzenlenmelidir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001085"],
        "encode_batch": "W2B",
    },
    # (2) COVERAGE — yılda aynı bölge 30 / iki bölge 60 seans; F-2(5) kontrolleri dahil
    {
        "rule_id": "2.4.4.F-6.(2).sports_ecology_annual_region_session_caps",
        "sut_section": "2.4.4.F-6",
        "condition": {
            "procedure_category_any": ["sports_medicine", "medical_ecology_hydroclimatology"],
            "sessions_same_region_within_1y": {"min": 31},
        },
        "action": {
            "billable": False,
            "enforcement": "regional_session_cap",
            "message_tr": (
                "bir hasta için son bir yılda aynı bölgeden en fazla 30, iki farklı bölgeden en "
                "fazla 60 seans ödenir; aynı bölgeye yılda en fazla 2 sağlık raporu; "
                "kontrollerde 2.4.4.F-2(5) sayıları da hesaba katılır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001086"],
        "encode_batch": "W2B",
    },
    # (3) MUST_BILL — spor hekimliği / tıbbi ekoloji FTR, P915030 puanı üzerinden
    {
        "rule_id": "2.4.4.F-6.(3).sports_ecology_physio_billed_p915030",
        "sut_section": "2.4.4.F-6",
        "condition": {
            "procedure_category_any": ["sports_medicine", "medical_ecology_hydroclimatology"],
            "procedure_code_any": ["P915030"],
            "billing_basis": "other",
        },
        "action": {
            "billable": True,
            "enforcement": "pricing_basis",
            "message_tr": (
                "spor hekimliği ile tıbbi ekoloji ve hidroklimatoloji uzmanlarınca EK-2/D-2 "
                "tanılarında yapılan FTR uygulamaları EK-2/C'deki 'P915030' kodlu işlem puanı "
                "esas alınarak faturalandırılır"
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001087"],
        "encode_batch": "W2B",
    },

    # ── §2.4.4.G-1 — Sitogenetik tetkikler (EK-2/B 9.B, 9.B.1 hariç) ─────────
    # (1) REGULATORY_ACTION — kapsamdaki sitogenetik kodlarının faturalandırma kuralları
    {
        "rule_id": "2.4.4.G-1.(1).cytogenetic_tests_scope_header",
        "sut_section": "2.4.4.G-1",
        "condition": {
            "test_category": "cytogenetic",
            "annex_list": "EK-2/B",
            "in_molecular_cytogenetic_subheader_9B1": False,
        },
        "action": {
            "billable": True,
            "enforcement": "facility_routing",
            "message_tr": (
                "EK-2/B '9.B. Sitogenetik Tetkikler' kodları ('9.B.1. Moleküler Sitogenetik "
                "Tetkikler' hariç) aşağıdaki faturalandırma kurallarına tabidir"
            ),
        },
        "gate_b_sources": ["C001096"],
        "encode_batch": "W2B",
    },
    # (a/b for non-molecular) MUST_BILL — 3. basamak resmi; GHDM hizmet alımı; 2. basamak ruhsatlı GHDM
    {
        "rule_id": "2.4.4.G-1.(a_b).cytogenetic_3rd_step_public_or_licensed_ghdm",
        "sut_section": "2.4.4.G-1",
        "condition": {
            "test_category": "cytogenetic",
            "facility_not_in": [
                "contracted_3rd_step_public",
                "licensed_ghdm_2nd_step_public",
                "licensed_ghdm_3rd_step_private",
            ],
        },
        "action": {
            "billable": False,
            "enforcement": "facility_gate",
            "message_tr": (
                "sitogenetik tetkikler sözleşmeli 3. basamak resmi sunucularca; yapılamayan "
                "tetkikler ruhsatlı GHDM'den hizmet alımıyla; bünyesinde ruhsatlı GHDM bulunan "
                "2. basamak sunucu veya 3. basamak özel sunucularda faturalandırılır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001102"],
        "encode_batch": "W2B",
    },
    # (a moleküler-sitogenetik için sadeleştirilmiş) MUST_BILL — 3. basamak resmi / hizmet alımı
    {
        "rule_id": "2.4.4.G-1.(a).cytogenetic_molecular_3rd_step_public_service_procurement",
        "sut_section": "2.4.4.G-1",
        "condition": {
            "test_category": "cytogenetic_molecular",
            "facility_not_in": ["contracted_3rd_step_public"],
            "service_procurement_from_licensed": False,
        },
        "action": {
            "billable": False,
            "enforcement": "facility_gate",
            "message_tr": (
                "sözleşmeli 3. basamak resmi sunucular tarafından faturalandırılır; "
                "yapılamayan tetkikler hizmet alımı yöntemiyle sağlanarak faturalandırılabilir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001109"],
        "encode_batch": "W2B",
    },
    # (b moleküler-sitogenetik) MUST_BILL — ruhsatlı GHDM 2. basamak / 3. basamak özel
    {
        "rule_id": "2.4.4.G-1.(b).cytogenetic_molecular_licensed_ghdm_facilities",
        "sut_section": "2.4.4.G-1",
        "condition": {
            "test_category": "cytogenetic_molecular",
            "facility_not_in": [
                "licensed_ghdm_2nd_step_public",
                "licensed_ghdm_3rd_step_private",
            ],
        },
        "action": {
            "billable": False,
            "enforcement": "facility_gate",
            "message_tr": (
                "bünyelerinde Sağlık Bakanlığı ruhsatlı GHDM bulunan 2. basamak sunucuları ile "
                "3. basamak özel sağlık hizmeti sunucularında yapılması halinde faturalandırılır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001110"],
        "encode_batch": "W2B",
    },

    # ── §2.4.4.G-2 — Moleküler genetik tetkikler (EK-2/B 9.C, 9.C.1 hariç) ────
    # (1) REGULATORY_ACTION — moleküler genetik kodlarının faturalandırma kuralları
    {
        "rule_id": "2.4.4.G-2.(1).molecular_genetic_tests_scope_header",
        "sut_section": "2.4.4.G-2",
        "condition": {
            "test_category": "molecular_genetic",
            "annex_list": "EK-2/B",
            "in_oncologic_molecular_subheader_9C1": False,
        },
        "action": {
            "billable": True,
            "enforcement": "facility_routing",
            "message_tr": (
                "EK-2/B '9.C. Moleküler Genetik Tetkikler' kodları ('9.C.1. Onkolojik Moleküler "
                "Tetkikler' hariç) aşağıdaki faturalandırma kurallarına tabidir"
            ),
        },
        "gate_b_sources": ["C001113"],
        "encode_batch": "W2B",
    },
    # (a) MUST_BILL — moleküler genetik 3. basamak resmi / GHDM hizmet alımı (özel istisnalar dahil)
    {
        "rule_id": "2.4.4.G-2.(a).molecular_genetic_3rd_step_public_ghdm_procurement",
        "sut_section": "2.4.4.G-2",
        "condition": {
            "test_category": "molecular_genetic",
            "facility_not_in": ["contracted_3rd_step_public"],
            "service_procurement_from_licensed_ghdm": False,
        },
        "action": {
            "billable": False,
            "enforcement": "facility_gate",
            "message_tr": (
                "sözleşmeli 3. basamak resmi sunucular tarafından faturalandırılır; yapılamayan "
                "tetkikler ruhsatlı GHDM'den hizmet alımı yöntemiyle sağlanarak faturalandırılabilir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001119"],
        "encode_batch": "W2B",
    },
    # (b) MUST_BILL — moleküler genetik ruhsatlı GHDM 2. basamak / 3. basamak özel + istisnalar
    {
        "rule_id": "2.4.4.G-2.(b).molecular_genetic_licensed_ghdm_facilities_exceptions",
        "sut_section": "2.4.4.G-2",
        "condition": {
            "test_category": "molecular_genetic",
            "facility_not_in": [
                "licensed_ghdm_2nd_step_public",
                "licensed_ghdm_3rd_step_private",
            ],
            "is_exception_category": False,
        },
        "action": {
            "billable": False,
            "enforcement": "facility_gate",
            "message_tr": (
                "ruhsatlı GHDM bulunan 2. basamak sunucu veya 3. basamak özel sunucuda yapılması "
                "halinde faturalandırılır; preimplantasyon/prenatal/hematolojik malignite ve "
                "nakil alıcı-verici adayları için başka ruhsatlı GHDM'den hizmet alımıyla faturalandırılabilir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001120"],
        "encode_batch": "W2B",
    },
    # (a onkolojik-moleküler) MUST_BILL — 3. basamak resmi / hizmet alımı
    {
        "rule_id": "2.4.4.G-2.(a_onc).molecular_genetic_oncologic_3rd_step_public_procurement",
        "sut_section": "2.4.4.G-2",
        "condition": {
            "test_category": "molecular_genetic_oncologic",
            "facility_not_in": ["contracted_3rd_step_public"],
            "service_procurement_from_licensed": False,
        },
        "action": {
            "billable": False,
            "enforcement": "facility_gate",
            "message_tr": (
                "sözleşmeli 3. basamak resmi sunucular tarafından faturalandırılır; yapılamayan "
                "tetkikler hizmet alımı yöntemiyle sağlanarak faturalandırılabilir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001127"],
        "encode_batch": "W2B",
    },
    # (b onkolojik-moleküler) MUST_BILL — ruhsatlı GHDM 2. basamak / 3. basamak özel
    {
        "rule_id": "2.4.4.G-2.(b_onc).molecular_genetic_oncologic_licensed_ghdm",
        "sut_section": "2.4.4.G-2",
        "condition": {
            "test_category": "molecular_genetic_oncologic",
            "facility_not_in": [
                "licensed_ghdm_2nd_step_public",
                "licensed_ghdm_3rd_step_private",
            ],
        },
        "action": {
            "billable": False,
            "enforcement": "facility_gate",
            "message_tr": (
                "bünyelerinde Sağlık Bakanlığı ruhsatlı GHDM bulunan 2. basamak sunucuları ile "
                "3. basamak özel sağlık hizmeti sunucularında yapılması halinde faturalandırılır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001128"],
        "encode_batch": "W2B",
    },
    # (3) NO_PAY — adli/tıbbi endikasyon dışı kişi isteğine bağlı tetkikler Kurumca karşılanmaz
    {
        "rule_id": "2.4.4.G-2.(3).molecular_genetic_self_requested_not_covered",
        "sut_section": "2.4.4.G-2",
        "condition": {
            "test_category": "molecular_genetic",
            "indication_is_self_requested": True,
            "indication_is_forensic_or_medical": False,
        },
        "action": {
            "billable": False,
            "enforcement": "exclusion",
            "message_tr": (
                "adli veya tıbbi endikasyonlara bağlı zorunluluklar dışında kişinin kendi "
                "isteğine bağlı yapılan tetkikler Kurumca karşılanmaz; ayrıntılı rapor, imzalı "
                "orijinal cihaz çıktısı ve endikasyon belirten istem formu faturaya eklenmelidir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001129"],
        "encode_batch": "W2B",
    },

    # ── §2.4.4.H — Yoğun bakım ───────────────────────────────────────────────
    # (1) MUST_NOT_BILL — seviyelendirilmemiş yatak 1. basamak fiyatından; tescilsiz yatak yok
    {
        "rule_id": "2.4.4.H.(1).icu_unleveled_level1_unregistered_not_billable",
        "sut_section": "2.4.4.H",
        "condition": {
            "procedure_category": "intensive_care",
            "bed_registration_status": "unregistered",
        },
        "action": {
            "billable": False,
            "enforcement": "facility_registration_gate",
            "message_tr": (
                "Bakanlıkça seviyelendirilmemiş yoğun bakım yatakları 1. basamak yoğun bakım "
                "fiyatından; tescil edilmemiş yoğun bakım yataklarında verilen tedaviler "
                "faturalandırılamaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001206"],
        "encode_batch": "W2B",
    },
    # (2) MUST_NOT_BILL — D/E grubu işlemler yoğun bakım bedeline dahil; A/B/C günü ek fatura
    {
        "rule_id": "2.4.4.H.(2).icu_group_de_bundled_abc_addon_same_day",
        "sut_section": "2.4.4.H",
        "condition": {
            "procedure_category": "intensive_care",
            "concomitant_procedure_group_in": ["D", "E"],
        },
        "action": {
            "billable": False,
            "enforcement": "bundling_prohibition",
            "message_tr": (
                "yoğun bakım tedavisi sürerken uygulanan D ve E grubu işlemler yoğun bakım "
                "bedellerine dâhildir, ayrıca faturalandırılamaz; A/B/C grubu işlem yapılan gün "
                "tanıya dayalı yoğun bakım puanı + EK-2/B işlem puanı faturalandırılabilir"
            ),
            "annex_basis": "EK-2/C",
            "severity": "error",
        },
        "gate_b_sources": ["C001207"],
        "encode_batch": "W2B",
    },
    # (3) MUST_NOT_BILL — PACU (anestezi sonrası bakım) için yoğun bakım bedeli yok
    {
        "rule_id": "2.4.4.H.(3).icu_pacu_no_icu_fee",
        "sut_section": "2.4.4.H",
        "condition": {
            "procedure_category": "post_anesthesia_care",
        },
        "action": {
            "billable": False,
            "enforcement": "exclusion",
            "message_tr": "anestezi sonrası bakım hizmetleri (PACU) için yoğun bakım bedelleri faturalandırılamaz",
            "severity": "error",
        },
        "gate_b_sources": ["C001208"],
        "encode_batch": "W2B",
    },
    # (5) MUST_BILL — trombosit süspansiyonu/aferez trombosit + malzeme ayrıca faturalanır
    {
        "rule_id": "2.4.4.H.(5).icu_platelet_apheresis_and_material_billable",
        "sut_section": "2.4.4.H",
        "condition": {
            "procedure_category": "intensive_care",
            "procedure_code_any": [
                "705440", "705441", "705442", "705443",  # trombosit süspansiyonu
                "705371", "705430", "705372", "705373",   # kan bileşeni puan kesintileri
            ],
        },
        "action": {
            "billable": True,
            "enforcement": "add_on_billing",
            "message_tr": (
                "trombosit süspansiyonu (705440-705443) ve 'aferez trombosit' bedelleri ile ilgili "
                "tıbbi malzeme bedelleri ayrıca faturalandırılır; 705371/705430 için puanın %36'sı, "
                "705372/705373 için %24'ü sunucunca ayrıca faturalandırılır"
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001210"],
        "encode_batch": "W2B",
    },
    # (7) MUST_BILL — aynı gün birden fazla basamakta YB tedavisi için tek YB bedeli
    {
        "rule_id": "2.4.4.H.(7).icu_single_fee_multiple_levels_same_day",
        "sut_section": "2.4.4.H",
        "condition": {
            "procedure_category": "intensive_care",
            "icu_levels_same_day_same_provider": {"min": 2},
        },
        "action": {
            "billable": True,
            "enforcement": "single_fee_consolidation",
            "message_tr": (
                "aynı sunucuda aynı gün birden fazla basamakta yoğun bakım tedavisi gören hasta "
                "için bir yoğun bakım bedeli faturalandırılır; basamak değişikliği epikriz notunda belirtilir"
            ),
        },
        "gate_b_sources": ["C001215"],
        "encode_batch": "W2B",
    },
    # (8) MUST_BILL — yatış/çıkış/vefat/sevk günü hizmetleri hizmet başına ödeme
    {
        "rule_id": "2.4.4.H.(8).icu_admission_discharge_day_fee_for_service",
        "sut_section": "2.4.4.H",
        "condition": {
            "procedure_category": "intensive_care",
            "day_is_admission_or_discharge_or_death_or_transfer": True,
        },
        "action": {
            "billable": True,
            "enforcement": "fee_for_service",
            "message_tr": (
                "yoğun bakımda yatan hastanın yattığı ilk gün ile vefat ettiği, yoğun bakımdan "
                "çıkarıldığı veya başka sunucunun yoğun bakımına sevk edildiği gün verilen "
                "sağlık hizmetleri hizmet başına ödeme yöntemiyle faturalandırılır"
            ),
            "annex_basis": "fee_for_service",
        },
        "gate_b_sources": ["C001216"],
        "encode_batch": "W2B",
    },

    # ── §2.4.4.I — Göz hastalıkları ayaktan başvuru kontrolleri ───────────────
    # (2) REGULATORY_ACTION — göz 2./3. basamak özel ayaktan günlük muayene: saat×4,5, en fazla 45/hekim
    {
        "rule_id": "2.4.4.I.(2).ophthalmology_outpatient_daily_exam_cap_45",
        "sut_section": "2.4.4.I",
        "condition": {
            "specialty": "ophthalmology",
            "provider_type": "private",
            "visit_type": "outpatient_non_emergency",
            "daily_exams_per_physician": {"min": 46},
        },
        "action": {
            "billable": False,
            "enforcement": "daily_exam_cap_with_time_deduction",
            "message_tr": (
                "göz hastalıkları 2./3. basamak özel sunucularında ayaktan günlük muayene sınırı "
                "(acil hariç) hekim saat×4,5 ile bulunur, küsurat üste tamamlanır, her hekim için "
                "45'i geçemez; belirli işlem kodları için çalışma saatinden 30/60 dakika düşülür, "
                "hekim günlük ≤8, sunucu ≤16 adet bu işlemleri fatura edebilir"
            ),
            "annex_basis": "EK-2/C",
            "severity": "error",
        },
        "gate_b_sources": ["C001241"],
        "encode_batch": "W2B",
    },
    # (3) MUST_NOT_BILL — 15 gün içinde tekrar göz ayaktan: yalnızca EK-2/A-2, EK-2/A değil
    {
        "rule_id": "2.4.4.I.(3).ophthalmology_15day_revisit_ek2a2_only",
        "sut_section": "2.4.4.I",
        "condition": {
            "specialty": "ophthalmology",
            "provider_type": "private",
            "visit_type": "outpatient",
            "is_emergency": False,
            "revisit_within_15d_same_specialty": True,
            "procedure_list": "EK-2/A",
        },
        "action": {
            "billable": False,
            "enforcement": "revisit_scope_restriction",
            "message_tr": (
                "aynı özel sunucuya göz hastalıkları ayaktan başvuru günü dâhil 15 gün içindeki "
                "tekrar ayaktan başvurularda yalnızca EK-2/A-2 Listesindeki işlemler faturalandırılır; "
                "EK-2/A Listesindeki tutarlar faturalandırılamaz"
            ),
            "annex_basis": "EK-2/A-2",
            "severity": "error",
        },
        "gate_b_sources": ["C001242"],
        "encode_batch": "W2B",
    },

    # ── §2.4.4.J — Kaplıca tedavileri ────────────────────────────────────────
    # (1) MANDATORY — kaplıca için sağlık kurulu raporu (PMR veya tıbbi ekoloji uzmanı ile)
    {
        "rule_id": "2.4.4.J.(1).thermal_spa_board_report_required",
        "sut_section": "2.4.4.J",
        "condition": {
            "procedure_category": "thermal_spa_balneotherapy",
            "provider_type": "public",
            "health_board_report_present": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "kaplıca tedavileri için resmi sunucularca en az bir fiziksel tıp ve rehabilitasyon "
                "veya tıbbi ekoloji ve hidroklimatoloji uzmanının yer aldığı sağlık kurulu raporu "
                "düzenlenmelidir; raporda tanı, tedavi, seans ve gün sayısı zorunludur"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001329"],
        "encode_batch": "W2B",
    },
    # (2) MANDATORY — rapor tarihinden 6 ay içinde başlanmazsa yeniden rapor gerekir
    {
        "rule_id": "2.4.4.J.(2).thermal_spa_start_within_6_months_else_new_report",
        "sut_section": "2.4.4.J",
        "condition": {
            "procedure_category": "thermal_spa_balneotherapy",
            "months_from_report_to_treatment": {"min": 7},
        },
        "action": {
            "billable": False,
            "enforcement": "report_validity",
            "message_tr": (
                "sağlık kurulu raporunun düzenlendiği tarihten itibaren 6 ay içerisinde tedaviye "
                "başlanamaması halinde yeniden sağlık kurulu raporu düzenlenmesi gerekmektedir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001330"],
        "encode_batch": "W2B",
    },
    # (3) NO_PAY — Bakanlık izinli olmayan kaplıcalarda tedavi Kurumca karşılanmaz
    {
        "rule_id": "2.4.4.J.(3).thermal_spa_unlicensed_facility_not_covered",
        "sut_section": "2.4.4.J",
        "condition": {
            "procedure_category": "thermal_spa_balneotherapy",
            "facility_has_moh_operation_permit": False,
        },
        "action": {
            "billable": False,
            "enforcement": "facility_licensing_gate",
            "message_tr": (
                "Sağlık Bakanlığınca işletme izni verilmeyen kaplıcalarda tedavi görenlerin "
                "kaplıca tedavilerine ait bedeller Kurumca karşılanmaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001331"],
        "encode_batch": "W2B",
    },
    # (4) NO_PAY — sözleşme yapılmayan tesislerde yalnızca 702.020 'banyo-kaplıca' hastaya ödenir
    {
        "rule_id": "2.4.4.J.(4).thermal_spa_uncontracted_only_702020_per_day",
        "sut_section": "2.4.4.J",
        "condition": {
            "procedure_category": "thermal_spa_balneotherapy",
            "facility_contracted_with_institution": False,
            "procedure_code_not_any": ["702020"],
            "procedures_per_day": {"min": 2},
        },
        "action": {
            "billable": False,
            "enforcement": "patient_reimbursement_limit",
            "message_tr": (
                "Bakanlık izinli ancak sözleşmeli olmayan kaplıca tesislerinde hasta tarafından "
                "karşılanan giderler için fatura ve sağlık raporuna dayanılarak her gün için bir "
                "adet '702.020 banyo-kaplıca' bedeli hastaya ödenir; diğer işlemler karşılanmaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001332"],
        "encode_batch": "W2B",
    },
    # (5) COVERAGE — kaplıca yol/gündelik/refakatçi giderleri 2.6 hükümlerine göre
    {
        "rule_id": "2.4.4.J.(5).thermal_spa_travel_per diem_per_2_6",
        "sut_section": "2.4.4.J",
        "condition": {
            "procedure_category": "thermal_spa_balneotherapy",
            "expense_category_any": ["travel", "per_diem", "companion"],
        },
        "action": {
            "billable": True,
            "enforcement": "coverage_cross_reference",
            "message_tr": (
                "kaplıca tedavileri ile ilgili yol, gündelik ve refakatçi giderleri SUT'un "
                "2.6 maddesi hükümlerine göre karşılanır"
            ),
        },
        "gate_b_sources": ["C001333"],
        "encode_batch": "W2B",
    },

    # ── §2.4.4.K — Palyatif bakım ────────────────────────────────────────────
    # (1) MUST_BILL — palyatif bakım tescilli Bakanlık yataklı + tıp fakülteli üniversitelerce
    {
        "rule_id": "2.4.4.K.(1).palliative_care_certified_facilities_only",
        "sut_section": "2.4.4.K",
        "condition": {
            "procedure_category": "palliative_care",
            "facility_not_in": [
                "moh_certified_inpatient_palliative",
                "state_univ_med_faculty_hospital",
                "foundation_univ_med_faculty_hospital",
            ],
        },
        "action": {
            "billable": False,
            "enforcement": "facility_certification_gate",
            "message_tr": (
                "palyatif bakım tedavisi, Bakanlığınca palyatif bakım verme konusunda tescil "
                "edilmiş Bakanlığa bağlı yataklı sağlık tesislerince ve tıp fakültesi bulunan "
                "devlet/vakıf üniversiteleri SAUM'lerince faturalandırılır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001338"],
        "encode_batch": "W2B",
    },
    # (3) NO_PAY — tescilsiz palyatif yatak dışından gönderilen hizmetler karşılanmaz
    {
        "rule_id": "2.4.4.K.(3).palliative_care_unregistered_bed_not_covered",
        "sut_section": "2.4.4.K",
        "condition": {
            "procedure_category": "palliative_care",
            "bed_registration_status": "unregistered_palliative",
        },
        "action": {
            "billable": False,
            "enforcement": "exclusion",
            "message_tr": (
                "palyatif bakım vermeye yetkili sunucunun tescil edilmiş palyatif bakım yatakları "
                "dışındaki herhangi bir yataktan göndermesi durumunda bu hizmet bedelleri Kurumca karşılanmaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001340"],
        "encode_batch": "W2B",
    },
    # (5) MUST_BILL — palyatif bakım P560000'den günde en fazla 1 kez
    {
        "rule_id": "2.4.4.K.(5).palliative_care_p560000_once_per_day",
        "sut_section": "2.4.4.K",
        "condition": {
            "procedure_category": "palliative_care",
            "procedure_code_any": ["P560000"],
            "instances_per_day": {"min": 2},
        },
        "action": {
            "billable": False,
            "enforcement": "daily_frequency_cap",
            "message_tr": "palyatif bakım tedavisi EK-2/C'deki P560000 SUT kodundan günde en fazla 1 kez faturalandırılır",
            "annex_basis": "EK-2/C",
            "severity": "error",
        },
        "gate_b_sources": ["C001345"],
        "encode_batch": "W2B",
    },
    # (6) MUST_BILL — palyatif bakım altında EK-2/C işlem yapılırsa o gün palyatif bedeli yok
    {
        "rule_id": "2.4.4.K.(6).palliative_care_ek2c_procedure_no_palliative_fee",
        "sut_section": "2.4.4.K",
        "condition": {
            "procedure_category": "palliative_care",
            "concomitant_ek2c_procedure_on_same_day": True,
            "palliative_fee_billed_same_day": True,
        },
        "action": {
            "billable": False,
            "enforcement": "bundling_prohibition",
            "message_tr": (
                "palyatif bakım tedavisi gören hastaya EK-2/C işlemi yapılması durumunda işlem "
                "bedeli faturalandırılır; 2.2.2.B-1(3) sürelerinde palyatif bakım adı altında "
                "herhangi bir bedel ödenmez"
            ),
            "annex_basis": "EK-2/C",
            "severity": "error",
        },
        "gate_b_sources": ["C001346"],
        "encode_batch": "W2B",
    },
]
