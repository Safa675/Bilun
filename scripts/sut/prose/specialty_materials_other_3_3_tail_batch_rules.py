"""L4.4 tail — remaining other_3_3 corpus rows (5 clauses → 2 rules)."""

from __future__ import annotations

from typing import Any

OTHER_3_3_TAIL_CLAUSE_IDS: frozenset[str] = frozenset(
    {"C003146", "C003159"}
)

OTHER_3_3_TAIL_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.3.12.(4).dental_prosthesis_adhesive_no_pay",
        "sut_section": "3.3.12",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C003146"],
        "condition": {
            "material_name_any": [
                "protez yapistirici",
                "protez yapıştırıcı",
                "protez temizleme",
                "ozel icerikli dis macun",
                "özel içerikli diş macun",
                "denture adhesive"]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Protez yapıştırıcı / temizleme tableti / özel diş macunu — "
                "Kurumca karşılanmaz (§3.3.11–12)."
            ),
        },
    },
    {
        "rule_id": "3.3.12.(4).dental_prosthesis_adhesive_flag",
        "sut_section": "3.3.12",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C003146"],
        "condition": {"dental_prosthesis_adhesive_claim": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Protez bakım/yapıştırıcı malzemesi — Kurumca karşılanmaz "
                "(§3.3.11–12)."
            ),
        },
    },
    {
        "rule_id": "3.3.16.(4).dual_mesh_primary_hernia_no_pay",
        "sut_section": "3.3.16",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C003159"],
        "condition": {"dual_mesh_primary_hernia_repair": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Primer inguinal/femoral/umbilikal/epigastrik fıtık onarımında "
                "çift yüzlü mesh — karşılanmaz (§3.3.14/16(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.16.(4).dual_mesh_primary_hernia_keyword",
        "sut_section": "3.3.16",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C003159"],
        "condition": {
            "material_name_any": [
                "cift yuzlu yama",
                "çift yüzlü yama",
                "dual mesh",
                "hernia mesh"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Çift yüzlü mesh — primer fıtık onarımı kapsamı dışı şüphesi "
                "(§3.3.14/16(4))."
            ),
        },
    }]
