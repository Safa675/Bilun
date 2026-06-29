"""§2.4.4 treatment pricing & exclusion rules — batch 1.

Gate-B encoded rules for SUT §2.4.4 (Bazı tetkik ve tedavi yöntemlerinin usul
ve esasları). Each rule carries `gate_b_sources` pointing at the source SUT
clause ID(s) in data/gazette/sut_clauses.parquet so every finding is auditable
back to the regulatory text.

Coverage: hemodiyaliz (D-1/D-2), IVF (İ-1), yoğun bakım (H), palyatif (K),
fizik tedavi (F-2..F-6), moleküler/genetik (G-1/G-2), ESWL (A), anjiyo (E),
radyocerrahi (C), fotoferez (Ç), kaplıca (J), göz 15-gün (I),
epidermolizis (N).

Merge target: data/gazette/prose_rules/treatment_pricing_2_4.json
"""

from __future__ import annotations

from typing import Any

BATCH1_RULES: list[dict[str, Any]] = [
    # ── §2.4.4.A — ESWL ( taş kırma) ──────────────────────────────────────
    {
        "rule_id": "2.4.4.A.(3).eswl_session_cap_6mo",
        "sut_section": "2.4.4.A",
        "condition": {
            "procedure_code_any": ["P2125301", "P2125302"],  # ESWL codes
            "same_side_kidney_ureter": True,
            "sessions_within_6mo": {"min": 4},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "6 aylık dönemde aynı taraf böbrek/üreter taşı için 3 seanstan "
                "fazlası ödenmez; 2-3. seans için radyolojik/sonografik belge zorunlu"
            ),
            "annex_basis": "EK-2/C",
            "severity": "error",
        },
        "gate_b_sources": ["C000864"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.B — Ani işitme kaybı ───────────────────────────────────────
    {
        "rule_id": "2.4.4.B.(8).sudden_hearing_loss_20session_cap",
        "sut_section": "2.4.4.B",
        "condition": {
            "diagnosis_any": ["H911", "H912"],  # sudden idiopathic hearing loss
            "sessions_after_20th": True,
            "improvement_less_than_20db": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "20. seans sonunda saf ses ortalamasında 20 dB düzelme yoksa "
                "sonraki seanslar ödenmez; son 30 gün odyolojik test zorunlu"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000876"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.C — Radyocerrahi (Gamma Knife vb.) ─────────────────────────
    {
        "rule_id": "2.4.4.C.(2).radiosurgery_ek2c_conditional",
        "sut_section": "2.4.4.C",
        "condition": {
            "procedure_category": "radiosurgery",
            "indication_met": False,  # cerrahi/medikal/radyoterapiye cevapsız veya uygun değil
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "radyocerrahi; cerrahi/medikal/klasik radyoterapiye cevap vermeyen "
                "veya uygun olmayan olgularda endikasyon karşılanmazsa ödenmez"
            ),
            "annex_basis": "EK-2/C",
            "severity": "warning",
        },
        "gate_b_sources": ["C000884"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.D-1 — Hemodiyaliz ──────────────────────────────────────────
    {
        "rule_id": "2.4.4.D-1.(7).hemodialysis_ek2c_pricing",
        "sut_section": "2.4.4.D-1",
        "condition": {
            "procedure_code_any": ["P5010046", "P5010047"],  # hemodiyaliz session
            "diagnosis_any": ["N18", "N19"],  # chronic renal failure
        },
        "action": {
            "billable": True,
            "payment_tr": "hemodiyaliz EK-2/C işlem puanı üzerinden faturalandırılır",
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C000938"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.D-1.(8).hemodialysis_consumables_reuse_prohibited",
        "sut_section": "2.4.4.D-1",
        "condition": {
            "procedure_code_any": ["P5010046", "P5010047"],
            "consumable_reuse_claimed": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "hemodiyaliz sarf malzemeleri hiçbir surette tekrar kullanılamaz (reuse)",
            "severity": "error",
        },
        "gate_b_sources": ["C000939"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.D-1.(9).private_dialysis_session_cap_excess",
        "sut_section": "2.4.4.D-1",
        "condition": {
            "provider_type": "private_dialysis_center",
            "sessions_exceed_weekly_reported": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "özel diyaliz merkezlerinde sağlık raporundaki haftalık seans "
                "sayısının üstündeki ek diyaliz tedavi bedelleri ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000940"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.D-1.(11).hemodialysis_bundled_tests_no_separate_bill",
        "sut_section": "2.4.4.D-1",
        "condition": {
            "procedure_code_any": ["P5010046", "P5010047"],
            "bundled_test_separately_billed": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "Diyaliz Merkezleri Yönetmeliği kapsamındaki rutin/acil/sık tekrar "
                "tetkikler hemodiyaliz seansına dahildir; ayrı faturalanamaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000944"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.D-1.(6).home_hemodialysis_ek2c_pricing",
        "sut_section": "2.4.4.D-1",
        "condition": {
            "procedure_code_any": ["P5010050"],  # ev hemodiyalizi
            "diagnosis_any": ["N18", "N19"],
        },
        "action": {
            "billable": True,
            "payment_tr": "ev hemodiyalizi EK-2/C 'ev hemodiyalizi' puanı üzerinden faturalandırılır",
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C000953"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.D-1.(7ev).home_hemodialysis_device_no_pay",
        "sut_section": "2.4.4.D-1",
        "condition": {
            "procedure_code_any": ["P5010050"],
            "device_maintenance_spare_part_billed": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "ev hemodiyalizi için hastaya kurulan cihaz bedeli ile bakım/onarım/"
                "yedek parça bedelleri ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000954"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.D-1.(8ev).home_hemodialysis_session_cap_excess",
        "sut_section": "2.4.4.D-1",
        "condition": {
            "procedure_code_any": ["P5010050"],
            "sessions_exceed_weekly_reported": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "ev hemodiyalizinde rapordaki haftalık seans üstü ek tedavi bedelleri ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C000955"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.D-2 — Periton diyalizi (APD) ───────────────────────────────
    {
        "rule_id": "2.4.4.D-2.(2).apd_device_no_pay",
        "sut_section": "2.4.4.D-2",
        "condition": {
            "procedure_code_any": ["P5010060"],  # APD
            "device_maintenance_spare_part_billed": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "APD cihaz bedeli ve bakım/onarım/yedek parça bedelleri ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C000964"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.E — Anjiyo + PTCA aynı seans ───────────────────────────────
    {
        "rule_id": "2.4.4.E.(2).angio_ptca_same_session_25pct",
        "sut_section": "2.4.4.E",
        "condition": {
            "same_session_procedures": ["PTCA_or_stent", "coronary_angiography"],
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "aynı seansta PTCA/stent + anjiografi ise PTCA/stent tam, "
                "anjiografi %25'i EK-2/C üzerinden faturalandırılır"
            ),
            "annex_basis": "EK-2/C",
            "fraction_applied_to_secondary": 0.25,
        },
        "gate_b_sources": ["C000968"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.F-2 — Fizik tedavi (ayakta/yatarak) ────────────────────────
    {
        "rule_id": "2.4.4.F-2.(4).physio_session_cap_per_day",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "sessions_per_day": {"min": 2},
            "diagnosis_not_in": ["G80"],  # G80 ve (*) hariç
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "ayakta fizik tedavide günde en fazla 1 seans; yatarak G80 ve (*) "
                "tanılarda günde 1, diğer tanılarda aynı bölge için 1 seans ödenir"
            ),
            "annex_basis": "EK-2/D-2",
            "severity": "error",
        },
        "gate_b_sources": ["C001014"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.F-2.(7).physio_start_within_15d",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "days_from_report_to_treatment": {"min": 16},
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "fizik tedavi; sağlık raporu tarihinden itibaren 15 gün içinde "
                "tedaviye başlanmamışsa ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001017"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.F-2.(8).physio_report_modification_5d",
        "sut_section": "2.4.4.F-2",
        "condition": {
            "procedure_category": "physiotherapy_rehab",
            "diagnosis_not_in": ["G80"],
            "report_modified_after_5_biz_days": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "G80 ve (*) dışındaki tanılarda tedavi başlandıktan 5 iş günü sonra "
                "rapor değişikliği ile yapılan fizik tedavi ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001018"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.F-4 — ESWT ─────────────────────────────────────────────────
    {
        "rule_id": "2.4.4.F-4.(4).eswt_no_combo_with_physio",
        "sut_section": "2.4.4.F-4",
        "condition": {
            "procedure_code_any": ["P915010"],  # ESWT
            "same_day_physio_rehab": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "ESWT işlemi diğer fizik tedavi/rehab işlemleriyle aynı gün faturalanamaz",
            "severity": "error",
        },
        "gate_b_sources": ["C001065"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.F-5 — Robotik rehabilitasyon ───────────────────────────────
    {
        "rule_id": "2.4.4.F-5.(3).robotic_rehab_ek2c_pricing",
        "sut_section": "2.4.4.F-5",
        "condition": {
            "procedure_category": "robotic_rehab",
        },
        "action": {
            "billable": True,
            "payment_tr": "robotik rehabilitasyon EK-2/D-2 grupları + EK-2/C puan üzerinden",
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001071"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.F-5.(4).robotic_rehab_no_combo",
        "sut_section": "2.4.4.F-5",
        "condition": {
            "procedure_category": "robotic_rehab",
            "same_day_physio_rehab": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "robotik rehabilitasyon diğer fizik tedavi/rehab ile birlikte faturalanamaz",
            "severity": "error",
        },
        "gate_b_sources": ["C001072"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.F-6 — Spor hekimliği / hidroklimatoloji ────────────────────
    {
        "rule_id": "2.4.4.F-6.(3).sport_hydro_physio_p915030",
        "sut_section": "2.4.4.F-6",
        "condition": {
            "procedure_code_any": ["P915030"],
            "prescriber_specialty_any": ["sport_medicine", "medical_ecology_hydroclimatology"],
        },
        "action": {
            "billable": True,
            "payment_tr": "spor hekimi/hidroklimatoloji uzmanınca EK-2/D-2 tanı + P915030 puanı",
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001087"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.G-1/G-2 — Moleküler / genetik tetkikler ────────────────────
    {
        "rule_id": "2.4.4.G-1.tier3_public_facility_only",
        "sut_section": "2.4.4.G-1",
        "condition": {
            "procedure_category": "genetic_metabolic_test",
            "facility_tier_not_in": ["third_step_public", "ghdm_licensed_2nd_private"],
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "genetik/metabolik tetkikler sözleşmeli 3. basamak resmi veya ruhsatlı "
                "GHDM'li 2. basamak/3. basamak özel sunucularca yapılmalı; otherwise ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001102", "C001109", "C001110"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.G-2.tier3_public_facility_only",
        "sut_section": "2.4.4.G-2",
        "condition": {
            "procedure_category": "molecular_genetic_test",
            "facility_tier_not_in": ["third_step_public", "ghdm_licensed_2nd_private"],
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "moleküler/genetik tetkikler sözleşmeli 3. basamak resmi veya ruhsatlı "
                "GHDM'li sunucularca yapılmalı (preimplantasyon/prenatal/hematolojik/"
                "organ doku nakli eşleri hariç yönetmelik kapsamında)"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001119", "C001120", "C001127", "C001128"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.G-2.(3).elective_genetic_test_no_pay",
        "sut_section": "2.4.4.G-2",
        "condition": {
            "procedure_category": "molecular_genetic_test",
            "elective_non_medical_indication": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "adli/tıbbi endikasyon dışında kişinin isteğine bağlı genetik tetkikler ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C001129"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.H — Yoğun bakım ────────────────────────────────────────────
    {
        "rule_id": "2.4.4.H.(3).pacu_no_icu_bill",
        "sut_section": "2.4.4.H",
        "condition": {
            "procedure_category": "post_anesthesia_care_pacu",
            "icu_fee_billed": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "anestezi sonrası bakım (PACU) için yoğun bakım bedelleri faturalandırılamaz",
            "severity": "error",
        },
        "gate_b_sources": ["C001208"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.H.(7).same_day_multi_level_one_icu_fee",
        "sut_section": "2.4.4.H",
        "condition": {
            "same_day_multi_level_icu": True,
            "patient_transferred_between_levels": False,
        },
        "action": {
            "billable": True,
            "payment_tr": "aynı gün birden fazla basamakta yoğun bakım için tek yoğun bakım bedeli",
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001215"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.H.(8).icu_admission_discharge_fee_for_service",
        "sut_section": "2.4.4.H",
        "condition": {
            "icu_day_is": ["admission_day", "discharge_or_death_day", "transfer_out_day"],
        },
        "action": {
            "billable": True,
            "payment_tr": "yoğun bakıma giriş/çıkış/vefat/sevk günü hizmet başına ödeme yöntemiyle",
            "annex_basis": "EK-2/B",
        },
        "gate_b_sources": ["C001216"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.I — Göz (15-gün pencere) ───────────────────────────────────
    {
        "rule_id": "2.4.4.I.(3).ophthalmology_15d_same_specialty_bundle",
        "sut_section": "2.4.4.I",
        "condition": {
            "provider_type": "private_2nd_3rd_step",
            "specialty": "ophthalmology",
            "same_specialty_visit_within_15d": True,
            "is_emergency": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "göz hastalıklarında özel 2/3. basamak ayaktan başvuru dahil 15 gün "
                "içinde aynı uzmanlık tekrar başvuru pakete dahildir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001242"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.İ-1 — IVF ──────────────────────────────────────────────────
    {
        "rule_id": "2.4.4.I-1.(1).ivf_ek2c_package_price",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf",
        },
        "action": {
            "billable": True,
            "payment_tr": "IVF EK-2/C bedel üzerinden (ovulasyon takibi, oosit aspirasyonu, ICSI vb. dahil)",
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001296"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.I-1.(2).ivf_age40_no_pay",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf",
            "patient_age_at_embryo_transfer": {"min": 40},
            "valid_report_before_age40": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "embriyo transferi tarihinde kadının 40 yaşından büyük olması ve "
                "40'tan küçükken geçerli rapor yoksa IVF bedelleri ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001261"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.I-1.(2).ivf_freezing_ek2b",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf_embryo_freezing",
            "attempt_number": {"min": 1, "max": 2},
        },
        "action": {
            "billable": True,
            "payment_tr": "embriyo freezing 1. veya 2. denemeden sonra EK-2/B üzerinden",
            "annex_basis": "EK-2/B",
        },
        "gate_b_sources": ["C001297"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.I-1.(3).ivf_cancellation_10pct_discount",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf",
            "ivf_not_completed": True,
        },
        "action": {
            "billable": True,
            "payment_tr": "IVF uygulanamazsa kadar yapılan işlemler EK-2/B üzerinden %10 indirimli",
            "annex_basis": "EK-2/B",
            "discount_fraction": 0.10,
        },
        "gate_b_sources": ["C001298"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.I-1.(5).ivf_multi_embryo_multi_birth_no_pay",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf",
            "multiple_embryos_transferred_without_medical_necessity": True,
            "multiple_births_resulted": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "tıbbi zorunluluk olmadan birden fazla embriyo transferi ile oluşan "
                "çoklu doğumlarda bebeklere ait taburcuğı kadar bedeller ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001300"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.J — Kaplıca ────────────────────────────────────────────────
    {
        "rule_id": "2.4.4.J.(3).thermal_unlicensed_no_pay",
        "sut_section": "2.4.4.J",
        "condition": {
            "procedure_category": "thermal_spa",
            "facility_not_ministry_licensed": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "Sağlık Bakanlığı işletme izni verilmeyen kaplıcalarda tedavi bedelleri ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C001331"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.K — Palyatif bakım ─────────────────────────────────────────
    {
        "rule_id": "2.4.4.K.(1).palliative_accreditation_required",
        "sut_section": "2.4.4.K",
        "condition": {
            "procedure_code_any": ["P560000"],
            "facility_not_palliative_accredited": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "palyatif bakım; Bakanlıkça tescilli yataklı tesis veya tıp fakülteli "
                "üniversite ARA-M'den yapılmazsa ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001338"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.K.(3).palliative_non_accredited_bed_no_pay",
        "sut_section": "2.4.4.K",
        "condition": {
            "procedure_code_any": ["P560000"],
            "bed_not_palliative_certified": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "tescil dışı yataktan palyatif bakım hizmeti gönderilirse bedeller ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C001340"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.K.(5).palliative_p560000_once_per_day",
        "sut_section": "2.4.4.K",
        "condition": {
            "procedure_code_any": ["P560000"],
            "p560000_per_day_count": {"min": 2},
        },
        "action": {
            "billable": False,
            "denial_tr": "P560000 palyatif bakım günde en fazla 1 kez faturalandırılır",
            "severity": "error",
        },
        "gate_b_sources": ["C001345"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.K.(6).palliative_ek2c_procedure_same_day_no_double",
        "sut_section": "2.4.4.K",
        "condition": {
            "procedure_code_any": ["P560000"],
            "same_day_ek2c_procedure": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "palyatif bakım altında EK-2/C işlem yapılırsa işlem bedeli alınır, "
                "2.2.2.B-1(3) sürelerinde palyatif bedel ödenmez"
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001346"],
        "encode_batch": "T1",
    },
    {
        "rule_id": "2.4.4.K.(7).palliative_bundled_no_separate_bill",
        "sut_section": "2.4.4.K",
        "condition": {
            "procedure_code_any": ["P560000"],
            "diagnostic_procedure_separately_billed_within_palliative": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "palyatif bakımda tanı/tedavi işlemleri 2.2.2.B-1(e) kapsamında "
                "ayrı faturalanamaz (işlem dahil)"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001349"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.N — Epidermolizis bülloza yara bakımı ──────────────────────
    {
        "rule_id": "2.4.4.N.(1).eb_wound_care_3rd_step_public",
        "sut_section": "2.4.4.N",
        "condition": {
            "diagnosis_any": ["Q810", "Q811", "Q812", "Q813"],  # epidermolysis bullosa
            "procedure_category": "wound_care",
            "facility_tier_not_in": ["third_step_public"],
        },
        "action": {
            "billable": False,
            "denial_tr": "epidermolizis bülloza yara bakımı 3. basamak resmi sunucularca yapılmalı",
            "severity": "error",
        },
        "gate_b_sources": ["C001366"],
        "encode_batch": "T1",
    },

    # ── §2.4.4.Ç — Fotoferez ──────────────────────────────────────────────
    {
        "rule_id": "2.4.4.C-c.(5).photopheresis_ek2b_pricing",
        "sut_section": "2.4.4.Ç",
        "condition": {
            "procedure_code_any": ["P704941", "P704940"],
        },
        "action": {
            "billable": True,
            "payment_tr": "ekstrakorporeal fotoferez her seans EK-2/B 704941 veya 704940 üzerinden",
            "annex_basis": "EK-2/B",
        },
        "gate_b_sources": ["C000927"],
        "encode_batch": "T1",
    },
]
