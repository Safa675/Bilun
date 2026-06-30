"""L4.4 Phase 1 pilot — §3.3.1 wound/dressing specialty prose (4 deontic clauses → 7 rules)."""

from __future__ import annotations

from typing import Any

# Strict §3.3.1 only (not 3.3.10+).
WOUND_331_PILOT_CLAUSE_IDS: frozenset[str] = frozenset(
    {"C002856", "C002856"}
)

WOUND_331_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.3.1.(10).wound_dressing_cover_no_pay",
        "sut_section": "3.3.1",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {
            "material_name_any": [
                "yara ort",
                "yara ört",
                "transparan film",
                "yara temas tabak",
                "yapisma",
                "yapışma",
                "temizlik urunu",
                "temizlik ürün",
                "bariyer krem",
                "bariyer sprey"]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Yara örtüsü / bakım yardımcısı — Kurumca karşılanmaz (§3.3.1(10))."
            ),
        },
    },
    {
        "rule_id": "3.3.1.(10).wound_hydrojel_additive_no_pay",
        "sut_section": "3.3.1",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {
            "material_name_any": [
                "hidrojel",
                "yara nemlendir",
                "kollagen",
                "kolajen",
                "buyume faktor",
                "büyüme faktör",
                "polisakkarid",
                "hyaluronik",
                "tibbi bal",
                "tıbbi bal"]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Hidrojel / katkılı yara ürünü — Kurumca karşılanmaz (§3.3.1(10))."
            ),
        },
    },
    {
        "rule_id": "3.3.1.(10).wound_debridman_no_pay",
        "sut_section": "3.3.1",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {
            "material_name_any": [
                "larva debridman",
                "ultrasonik debridman",
                "debridman sarf"]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": "Debridman sarf malzemesi — Kurumca karşılanmaz (§3.3.1(10)).",
        },
    },
    {
        "rule_id": "3.3.1.(10).wound_biostimulation_no_pay",
        "sut_section": "3.3.1",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {
            "material_name_any": [
                "biyostimul",
                "topikal oksijen",
                "wound biostim"]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Biyostimulasyon / topikal oksijen malzemesi — Kurumca karşılanmaz "
                "(§3.3.1(10))."
            ),
        },
    },
    {
        "rule_id": "3.3.1.(10).skin_substitute_non_burn_flag",
        "sut_section": "3.3.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002856", "C002856"],
        "condition": {"skin_substitute_non_burn_use": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Deri taklidi/yedeği yalnızca yanık tedavisinde ödenir — diğer "
                "endikasyonlarda karşılanmaz (§3.3.1(9)/(10))."
            ),
        },
    },
    {
        "rule_id": "3.3.1.(10).skin_substitute_keyword_no_pay",
        "sut_section": "3.3.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002856", "C002856"],
        "condition": {
            "material_name_any": [
                "deri esdeger",
                "deri eşdeğer",
                "deri taklit",
                "deri taklid",
                "skin substitute"]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Deri taklidi/yedeği — yanık dışı kullanım şüphesi; yalnızca yanık "
                "tedavisinde ödenir (§3.3.1(9)/(10))."
            ),
        },
    },
    {
        "rule_id": "3.3.1.(13).immunobullous_patient_dispensed",
        "sut_section": "3.3.1",
        "deontic": "MUST_BILL",
        "gate_b_sources": [],
        "condition": {"immunobullous_wound_care_patient_supply": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "İmmünobüllöz yara bakım malzemesi reçete karşılığı hastaya temin "
                "edilmiş — fatura tutarı mahsup/clawback (§3.3.1(13))."
            ),
        },
    },
    {
        "rule_id": "3.3.1.(13).immunobullous_non_moh_supply",
        "sut_section": "3.3.1",
        "deontic": "MUST_BILL",
        "gate_b_sources": [],
        "condition": {"immunobullous_wound_care_non_moh_facility": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "İmmünobüllöz yara bakım malzemesi yalnızca Sağlık Bakanlığı "
                "sunucusunca temin/uygulanmalı (§3.3.1(13))."
            ),
        },
    }]
