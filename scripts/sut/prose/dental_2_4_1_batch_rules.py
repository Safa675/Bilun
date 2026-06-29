"""§2.4.1 dental treatment exclusion/pricing rules — batch 1.

Gate-B encoded rules for SUT §2.4.1 (Diş tedavileri). Covers precious-metal
NO_PAY, bone-implant NO_PAY + medical-necessity exception, fixed/removable
prosthetic 4-year renewal cap, orthodontic age-18 cutoff, EK-2/Ç pricing for
public facilities, and the 2x pricing for ≥40% disabled / special-needs
children under GA/sedation.

Each rule carries `gate_b_sources` pointing back to the source SUT clause ID
so every finding is auditable to the regulatory text.

Merge target: data/gazette/prose_rules/dental_2_4_1.json
"""

from __future__ import annotations

from typing import Any

BATCH1_RULES: list[dict[str, Any]] = [
    # ── §2.4.1 (1) — Kıymetli madenler NO_PAY ─────────────────────────────
    {
        "rule_id": "2.4.1.(1).precious_metal_no_pay",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "dental_restoration",
            "material_name_any": [
                "altın", "platin", "paladyum+platin", "iridyum+platin", "iropal",
                "argenco 23", "bego gold ewl", "polliag-m",
            ],
            "material_contains_precious_metal": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "diş tedavisinde altın, platin, paladyum+platin, iridyum+platin, "
                "iropal, argenco 23, bego gold EWL, polliag-M gibi kıymetli maden "
                "içeren maddelerin bedelleri ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000734"],
        "encode_batch": "D1",
    },

    # ── §2.4.1 (2) — Kemik içi implant NO_PAY (default) ───────────────────
    {
        "rule_id": "2.4.1.(2).bone_implant_no_pay_default",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "dental_implant",
            "medical_necessity_board_report": False,
        },
        "action": {
            "billable": False,
            "denial_tr": "kemik içi implantların bedelleri ödenmez (sağlık kurulu raporu yok)",
            "severity": "error",
        },
        "gate_b_sources": ["C000742"],
        "encode_batch": "D1",
    },

    # ── §2.4.1 (2-istisna) — İmplant istisnası (sağlık kurulu ile) ─────────
    {
        "rule_id": "2.4.1.(2).bone_implant_exception_board_report",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "dental_implant",
            "medical_necessity_board_report": True,
            "board_includes": ["surgery", "prosthodontics", "periodontology"],
            "board_from": "university_dental_faculty",
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "rutin protetik tedavi ile yapılamayacağı implant zorunlu olduğu; "
                "üniversite diş hekimliği fakültesi cerrahi/protez/periodontoloji "
                "anabilim dallarından ≥1 öğretim üyesi katılımlı sağlık kurulu ile "
                "belgelendirilmişse implant bedeli ödenir"
            ),
        },
        "gate_b_sources": ["C000747"],
        "encode_batch": "D1",
    },

    # ── §2.4.1 (3) — Protez 4 yıl yenileme cap ────────────────────────────
    {
        "rule_id": "2.4.1.(3).prosthesis_4yr_renewal_cap",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category_any": ["fixed_prosthesis", "removable_prosthesis"],
            "years_since_last_prosthesis": {"max": 4},
            "is_traffic_or_work_injury": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "hareketli ve sabit protez yenilenme süresi 4 yıl; bu süreden önce "
                "yapılan yenileme bedelleri ödenmez (trafik/iş kazası hariç)"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000748"],
        "encode_batch": "D1",
    },

    # ── §2.4.1 (4-a) — Ortodonti 18 yaş üstü NO_PAY ───────────────────────
    {
        "rule_id": "2.4.1.(4a).orthodontics_over_18_no_pay",
        "sut_section": "2.4.1",
        "condition": {
            "procedure_category": "orthodontics",
            "patient_age": {"min": 18},
            "treatment_started_before_18": False,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "18 yaşını doldurmuş kişilerin ortodontik diş tedavi giderleri "
                "ödenmez (18 öncesi başlamış ve devam ediyorsa hariç)"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000752"],
        "encode_batch": "D1",
    },

    # ── §2.4.1.A (1) — Resmi sunucuda EK-2/Ç ──────────────────────────────
    {
        "rule_id": "2.4.1.A.(1).public_facility_ek2c_pricing",
        "sut_section": "2.4.1.A",
        "condition": {
            "procedure_category": "dental_treatment",
            "facility_type": "public_contracted",
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "resmi sözleşmeli sunucuda diş tedavi bedelleri EK-2/Ç uygulanır; "
                "protezde döküm/işçilik ayrı ödenmez (malzeme+işçilik dahil)"
            ),
            "annex_basis": "EK-2/Ç",
        },
        "gate_b_sources": ["C000760"],
        "encode_batch": "D1",
    },

    # ── §2.4.1.A (2) — ≥%40 engelli / özel gereksinimli çocuk 2x ──────────
    {
        "rule_id": "2.4.1.A.(2).disabled_special_needs_2x_pricing",
        "sut_section": "2.4.1.A",
        "condition": {
            "procedure_category": "dental_treatment",
            "procedure_under_ga_or_sedoanalgesia": True,
            "patient_category_any": ["disabled_40_pct_or_more", "special_needs_child"],
            "facility_type": "public_contracted",
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "≥%40 engelli veya özel gereksinimli çocuklara GA/sedoanaljezi altında "
                "diş tedavisi EK-2/Ç puan bedellerinin 2 katı olarak faturalandırılır"
            ),
            "annex_basis": "EK-2/Ç",
            "multiplier": 2.0,
        },
        "gate_b_sources": ["C000762"],
        "encode_batch": "D1",
    },

    # ── §2.4.1.B-1 (1) — Özel/sözleşmesiz resmi NO_PAY (ortodonti/engelli hariç) ─
    {
        "rule_id": "2.4.1.B-1.(1).private_uncontracted_dental_no_pay",
        "sut_section": "2.4.1.B-1",
        "condition": {
            "procedure_category": "dental_treatment",
            "facility_type_any": ["private", "public_uncontracted"],
            "patient_category_not_in": ["orthodontics_excluded", "disabled_40_pct_or_more"],
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "ortodontik tedavi ve ≥%40 engelliler hariç; özel sunucular ve "
                "sözleşmesiz resmi sunucu diş ünitelerindeki diş tedavileri ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000791"],
        "encode_batch": "D1",
    },

    # ── §2.4.1.B-2 (4) — Özelde ≥%40 engelli/özel gereksinimli ────────────
    {
        "rule_id": "2.4.1.B-2.(4).private_disabled_2x_pricing",
        "sut_section": "2.4.1.B-2",
        "condition": {
            "procedure_category": "dental_treatment",
            "facility_type": "private",
            "patient_category_any": ["disabled_40_pct_or_more", "special_needs_child"],
            "procedure_under_ga_or_sedoanalgesia": True,
        },
        "action": {
            "billable": True,
            "payment_tr": (
                "özel sunucularda ≥%40 engelli veya özel gereksinimli çocuklara "
                "GA/sedoanaljezi altında diş tedavisi EK-2/Ç puanının 2 katı"
            ),
            "annex_basis": "EK-2/Ç",
            "multiplier": 2.0,
        },
        "gate_b_sources": ["C000807"],
        "encode_batch": "D1",
    },

    # ── §2.4.1.B-3 (1) — Tedaviyi üstlenen hekim sorumluluğu ─────────────
    {
        "rule_id": "2.4.1.B-3.(1).treating_physician_continuity",
        "sut_section": "2.4.1.B-3",
        "condition": {
            "procedure_category": "dental_treatment",
            "treating_physician_different_from_board_signatory": True,
            "patient_in_first_degree_relative_of_physician": True,
        },
        "action": {
            "billable": False,
            "denial_tr": (
                "sağlık kurulu raporunu düzenleyen hekim veya birinci derece "
                "yakını tarafından tedavi yapılıyorsa bedel ödenmez"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000812"],
        "encode_batch": "D1",
    },
]
