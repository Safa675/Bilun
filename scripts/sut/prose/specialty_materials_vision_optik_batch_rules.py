"""L4.4 Phase 3 — vision/optik corpus batch (33 clauses → 13 consolidated rules)."""

from __future__ import annotations

from typing import Any

# All clause IDs in evidence export theme vision_optik (includes 3.3.3–3.3.37 mis-tagged by prefix).
VISION_OPTIK_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        "C001940",
        "C001945",
        "C001952",
        "C001962",
        "C001963",
        "C001966",
        "C001971",
        "C001978",
        "C001988",
        "C001989",
        "C002475",
        "C002480",
        "C002481",
        "C002590",
        "C002605",
        "C002626",
        "C002645",
        "C002666",
        "C002677",
        "C002888",
        "C002890",
        "C002893",
        "C002907",
        "C002917",
        "C002918",
        "C003279",
        "C003289",
        "C003302",
        "C003323",
        "C003346",
        "C003363",
        "C003384",
        "C003394",
    }
)

VISION_OPTIK_BATCH_RULES: list[dict[str, Any]] = [
    # ── §3.3.3 Gözlük / optik ─────────────────────────────────────────
    {
        "rule_id": "3.3.3.(2).optical_access_deadline_missed",
        "sut_section": "3.3.3",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001940", "C001966", "C002888"],
        "condition": {"optical_patient_access_deadline_missed": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Optik reçete/rapor — 10 işgünü müracaat veya sistem kayıt süresi "
                "aşıldı; karşılanmaz (§3.3.3(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.A.(1).emergency_poliklinik_glasses",
        "sut_section": "3.3.3.A",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002890"],
        "condition": {"emergency_poliklinik_glasses_claim": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Acil poliklinik gözlük cam/çerçeve reçetesi — Kurumca karşılanmaz "
                "(§3.3.3.A(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.A.(4).ek3d_lens_upgrade_difference",
        "sut_section": "3.3.3.A",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001945", "C001971", "C002893"],
        "condition": {"optical_lens_upgrade_difference_claim": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "EK-3/D listesi dışı cam özelliği fark ücreti — Kurum karşılamaz "
                "(§3.3.3.A(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.B.(4).teleskopik_with_cap_kep",
        "sut_section": "3.3.3.B",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001952", "C001978", "C002907"],
        "condition": {"optical_telescopic_with_cap_claim": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Kapak kep reçeteli hastada yakın teleskopik gözlük — ayrıca "
                "karşılanmaz (§3.3.3.B(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.B.(4).teleskopic_keyword_no_pay",
        "sut_section": "3.3.3.B",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001952", "C001978", "C002907"],
        "condition": {
            "material_name_any": [
                "teleskopik gozluk",
                "teleskopik gözlük",
                "yakin teleskopik",
                "yakın teleskopik",
            ]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "warning",
            "message_tr": (
                "Yakın teleskopik gözlük — kapak kep kapsamı dışında ayrı ödeme "
                "şüphesi (§3.3.3.B(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.C.(5).contact_lens_and_spectacles",
        "sut_section": "3.3.3.C",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001962", "C001988", "C002917"],
        "condition": {"contact_lens_with_spectacle_billing": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Kontakt lens kullanan hastada ayrıca gözlük cam/çerçeve "
                "(konjenital afak hariç) — karşılanmaz (§3.3.3.C(5))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.C.(6).contact_lens_solution",
        "sut_section": "3.3.3.C",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001963", "C001989", "C002918"],
        "condition": {
            "material_name_any": [
                "kontakt lens sol",
                "lens solusyon",
                "lens solüsyon",
            ]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": "Kontakt lens solüsyonu — Kurumca karşılanmaz (§3.3.3.C(6)).",
        },
    },
    # ── TV / işitme / implant / inkontinans (corpus theme rows) ───────
    {
        "rule_id": "3.3.34.(4).tv5680_combo_billing",
        "sut_section": "3.3.34",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002475", "C003279"],
        "condition": {"tv5680_with_tv1080_tv1090_combo": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "TV5680, TV1080/TV1090 ile birlikte faturalandırılamaz — "
                "karşılanmaz (§3.3.34(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.35.in_ear_hearing_aid_underage",
        "sut_section": "3.3.35",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002480", "C002481", "C002590", "C003289"],
        "condition": {"hearing_in_ear_under_age_limit": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Yaş sınırı altında kulak/kanal içi işitme cihazı — "
                "karşılanmaz (§3.3.35)."
            ),
        },
    },
    {
        "rule_id": "3.3.35.(6).hearing_ear_mold_first_fitting",
        "sut_section": "3.3.35",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002605", "C003302"],
        "condition": {"hearing_ear_mold_with_initial_device": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "İşitme cihazı ilk alımında kulak kalıbı — ayrıca karşılanmaz "
                "(§3.3.35(6))."
            ),
        },
    },
    {
        "rule_id": "3.3.36.B.(10).cochlear_implant_under_12_months",
        "sut_section": "3.3.36.B",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002626", "C003323", "C003346"],
        "condition": {"cochlear_implant_under_12_months": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "12 ay altı koklear implant — Kurumca karşılanmaz (§3.3.36.B(10))."
            ),
        },
    },
    {
        "rule_id": "3.3.36.C.(3).speech_processor_under_5_years",
        "sut_section": "3.3.36.C",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002645", "C003363"],
        "condition": {"speech_processor_under_5_years": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "5 yaş altı konuşma işlemcisi (kafa bandı istisnası hariç) — "
                "karşılanmaz (§3.3.36.C(3))."
            ),
        },
    },
    {
        "rule_id": "3.3.36.D.(4).brainstem_implant_under_12_months",
        "sut_section": "3.3.36.D",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002666", "C003384"],
        "condition": {"brainstem_implant_under_12_months": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "12 ay altı beyin sapı implantı — Kurumca karşılanmaz (§3.3.36.D(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.37.(4).hydrophilic_catheter_diaper_only",
        "sut_section": "3.3.37",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002677", "C003394"],
        "condition": {"incontinence_hydrophilic_catheter_diaper_only": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Yalnızca alt bez ödemesi alan hastada hidrofilik sonda — "
                "karşılanmaz (§3.3.37(4))."
            ),
        },
    },
]
