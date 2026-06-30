"""L4.4 Phase 3c — §3.3.4 orthobiologic / greft corpus batch (29 clauses → 12 rules)."""

from __future__ import annotations

from typing import Any

SPECIALTY_334_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
    {
       
       
       
       
        "C002934",
       
        "C002970",
        "C002970",
       
       
        "C002936",
        "C002937",
        "C002939",
        "C002953",
        "C002962",
        "C002964",
        "C002966",
        "C002967",
        "C002970",
        "C002934",
        "C002936",
        "C002937",
        "C002939",
        "C002953",
        "C002962",
        "C002964",
        "C002966",
        "C002967",
        "C002970",
    }
)

SPECIALTY_334_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.3.4.(2).tissue_bank_unauthorized_product",
        "sut_section": "3.3.4",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {"tissue_bank_unauthorized_product": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Onaylı doku bankası/tek dağıtıcı kapsamı dışı ürün — "
                "Kurumca karşılanmaz (§3.3.4(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.(4).dermis_allograft_no_pay",
        "sut_section": "3.3.4",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002934"],
        "condition": {
            "material_name_any": [
                "dermis allogreft",
                "epidermis allogreft",
                "dermis xenogreft",
                "sentetik greft dermis",
                "allogreft dermis"]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Dermis/epidermis allogreft-xenogreft-sentetik greft — "
                "Kurumca karşılanmaz (§3.3.4(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(1).bone_stimulator_combined_use",
        "sut_section": "3.3.4.A",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002964", "C002964"],
        "condition": {"bone_stimulator_combined_use": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Kemik yapımını uyaran materyallerin kombine kullanımı — "
                "karşılanmaz (§3.3.4.A(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(2).bone_stimulator_hypertrophic_nonunion",
        "sut_section": "3.3.4.A",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002966", "C002966"],
        "condition": {"bone_stimulator_hypertrophic_nonunion": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Hipertrofik nonunion/pseudoartrozda kemik uyarıcı malzeme — "
                "karşılanmaz (§3.3.4.A(2)/(3))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(3).bone_stimulator_with_autograft",
        "sut_section": "3.3.4.A",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002934", "C002967", "C002967"],
        "condition": {"bone_stimulator_with_autograft": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Otojen greft ile birlikte kemik uyarıcı malzeme — "
                "karşılanmaz (§3.3.4.A(3)/(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(4).bone_stimulator_benign_tumor",
        "sut_section": "3.3.4.A",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {"bone_stimulator_benign_tumor_use": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Agresif olmayan benign kemik tümöründe kemik uyarıcı — "
                "karşılanmaz (§3.3.4.A(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.(8).open_physis_primary_fracture_graft",
        "sut_section": "3.3.4",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002970", "C002936", "C002936"],
        "condition": {"open_physis_primary_fracture_graft": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Açık epifiz hattı — patolojik olmayan primer kırıkta greft — "
                "karşılanmaz (§3.3.4(8))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.(9).adult_primary_fracture_bone_stimulator",
        "sut_section": "3.3.4",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002970", "C002970", "C002970"],
        "condition": {"adult_primary_fracture_bone_stimulator": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Yetişkin primer kırıkta kemik uyarıcı malzeme — "
                "karşılanmaz (§3.3.4(9)/(7))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.(6).hip_arthroplasty_graft_no_pay",
        "sut_section": "3.3.4",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002937", "C002937"],
        "condition": {"hip_arthroplasty_graft_claim": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Tümör dışı kalça kırığı artroplastisinde greft — "
                "karşılanmaz (§3.3.4(6)/(9))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.(11).graft_allograft_xenograft_combined",
        "sut_section": "3.3.4",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002939", "C002939"],
        "condition": {"graft_allograft_xenograft_combined": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Sentetik/allogreft/xenogreft kombine kullanım — "
                "karşılanmaz (§3.3.4(11)/(8))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(17).synthetic_tendon_graft",
        "sut_section": "3.3.4.A",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002953", "C002953"],
        "condition": {
            "material_name_any": [
                "sentetik tendon",
                "tendon greft",
                "tendon yerine"]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Tendon yerine sentetik greft — Kurumca karşılanmaz "
                "(§3.3.4.A(17)/(14))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.B.c.primary_ligament_tendon_graft",
        "sut_section": "3.3.4.B",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002962", "C002962"],
        "condition": {"primary_ligament_tendon_injury_graft": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Primer tekli bağ tendon yaralanmasında greft — "
                "hiçbir durumda karşılanmaz (§3.3.4.B(c))."
            ),
        },
    }]
