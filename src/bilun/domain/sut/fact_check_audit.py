"""
2026-06 SUT algorithm fact-check audit — frozen rollup migrated from
``docs/core-system/fact-check/MASTER.md``.

The audit program is **closed**. This module is the canonical home for:
- 28 audit unit verdicts (P0.* / L*.* IDs from the fact-check project)
- Per-rule fact-check metadata derived for :data:`RULE_REGISTRY`
- Aggregate verdict counts for the Rule Database API / UI

Ongoing implementation status lives in each rule's ``coverage_status`` field;
``fact_check_verdict`` captures the June 2026 audit outcome (may differ).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

FactCheckVerdict = Literal[
    "COMPLIANT",
    "PARTIAL",
    "HEURISTIC",
    "NEEDS_CLAIM_LINES",
    "WRONG",
    "OUT_OF_SCOPE",
]

MedulaOverlap = Literal[
    "ADDITIVE",
    "PARTIAL_OVERLAP",
    "MEDULA_DUPLICATE",
    "NOT_APPLICABLE",
]

AUDIT_CLOSED = "2026-06"
AUDIT_TOTAL_UNITS = 28

# Post-audit rules (e.g. §4.2.14.C expansion) — do not mutate FACT_CHECK_AUDIT_UNITS counts.
SUPPLEMENTAL_FACT_CHECK_RULES: dict[str, dict[str, Any]] = {
    "drug_indication_prose": {
        "fact_check_verdict": "PARTIAL",
        "medula_overlap": "ADDITIVE",
        "fact_check_units": ("SUT-4.2.14.C",),
        "fact_check_note": (
            "SUT-4.2.14.C: partial INN+ICD+report corpus; §4.2 motor-bound encode "
            "~25% of 2,369 classified clauses (599 manifest-encoded; pilots 4.2.14.C, "
            "4.2.13/16, 4.2.33, 4.2.17). "
            "Not to be confused with audit unit L4.2 (EK-2C DRG pricing)."
        ),
    },
}


@dataclass(frozen=True)
class FactCheckAuditUnit:
    unit_id: str
    title: str
    verdict: FactCheckVerdict
    medula_overlap: MedulaOverlap
    linked_rule_ids: tuple[str, ...] = ()
    note: str = ""


# Frozen audit table — source: MASTER.md Full Verdict Table (28 units).
FACT_CHECK_AUDIT_UNITS: tuple[FactCheckAuditUnit, ...] = (
    FactCheckAuditUnit(
        "P0.1",
        "Payment method",
        "PARTIAL",
        "ADDITIVE",
        ("payment_method_package", "payment_method_itemized", "payment_method_tier_override"),
        note=(
            "§2.2 Gate B: 42 JSON rules / 41 manifest clause IDs (~33% of §2.2 coverage rows encoded); "
            "§2.2.2.B session-fraction PARTIAL (session_pricing_2_2_2_B manifest cross-ref)."
        ),
    ),
    FactCheckAuditUnit(
        "P0.2",
        "Session pricing",
        "PARTIAL",
        "PARTIAL_OVERLAP",
        ("drg_unbundling",),
    ),
    FactCheckAuditUnit(
        "P0.3",
        "Copay general §1.8",
        "COMPLIANT",
        "ADDITIVE",
        ("copay_rate_general",),
        "copay_general_1_8.json — 4 rules wired (drug, material, IVF, Rx flat fee)",
    ),
    FactCheckAuditUnit(
        "P0.4",
        "DRG unbundling prose",
        "PARTIAL",
        "ADDITIVE",
        ("drg_unbundling",),
        note=(
            "UI-facing potential_savings_try is sourced-only; heuristic_savings_try "
            "retained in chapter_analysis audit fields only (2026-06)."
        ),
    ),
    FactCheckAuditUnit(
        "P0.5",
        "Facility tier",
        "COMPLIANT",
        "ADDITIVE",
        ("payment_method_tier_override",),
    ),
    FactCheckAuditUnit(
        "P0.6",
        "Catalog membership",
        "COMPLIANT",
        "ADDITIVE",
        (
            "payment_method_package",
            "payment_method_itemized",
            "pricing_ek2b",
            "pricing_ek2c",
        ),
        "Cross-cutting catalog_membership infrastructure",
    ),
    FactCheckAuditUnit(
        "L1.1",
        "EK-3B-1 bundling",
        "PARTIAL",
        "ADDITIVE",
        ("bundling_ek3b1",),
    ),
    FactCheckAuditUnit(
        "L1.2",
        "EK-3B-2 exclusion",
        "PARTIAL",
        "ADDITIVE",
        ("exclusion_ek3b2",),
    ),
    FactCheckAuditUnit(
        "L1.3",
        "validate_claim()",
        "PARTIAL",
        "ADDITIVE",
        ("claim_validation",),
        note=(
            "Material lines priced via price_material_lines (billed amount or exact EK-3 code); "
            "fuzzy name-match removed 2026-06. Bundling/exclusion rules still name-based."
        ),
    ),
    FactCheckAuditUnit(
        "L1.4",
        "§3 prose bundling",
        "PARTIAL",
        "ADDITIVE",
        ("material_bundling_prose",),
        "23 prose rules wired; corpus tail open",
    ),
    FactCheckAuditUnit(
        "L2.1",
        "Copay exemption EK-1A",
        "PARTIAL",
        "ADDITIVE",
        ("copay_exemption_ek1a",),
    ),
    FactCheckAuditUnit(
        "L2.2",
        "Visit/status exemptions",
        "COMPLIANT",
        "ADDITIVE",
        ("copay_exemption_visit_type",),
    ),
    FactCheckAuditUnit(
        "L2.3",
        "Surcharge EK-2G",
        "COMPLIANT",
        "ADDITIVE",
        ("surcharge_ek2g",),
    ),
    FactCheckAuditUnit(
        "L2.4",
        "Copay rate EK-2C-1",
        "COMPLIANT",
        "ADDITIVE",
        ("copay_rate_ek2c1",),
    ),
    FactCheckAuditUnit(
        "L2.5",
        "Temporal price audit",
        "COMPLIANT",
        "ADDITIVE",
        ("pricing_ek2b", "pricing_ek2c"),
    ),
    FactCheckAuditUnit(
        "L2.6",
        "DRG unbundling cohort",
        "PARTIAL",
        "ADDITIVE",
        ("drg_unbundling",),
    ),
    FactCheckAuditUnit(
        "L2.7",
        "Drug discount validation",
        "COMPLIANT",
        "PARTIAL_OVERLAP",
        ("drug_discount_prose", "drug_ek4a"),
    ),
    FactCheckAuditUnit(
        "L2.8",
        "Cohort aggregator",
        "COMPLIANT",
        "ADDITIVE",
        (),
        "Orchestration layer — no dedicated registry rule",
    ),
    FactCheckAuditUnit(
        "L3.1",
        "Lab optimizer",
        "PARTIAL",
        "ADDITIVE",
        ("lab_billing",),
        note=(
            "Duplicate detection HEURISTIC; hemogram core fixed. "
            "§2.2.2.B same-session multi-procedure session-fraction remains PARTIAL/unimplemented "
            "in lab optimizer (session_pricing_2_2_2_B manifest; runtime in session_pricing.py)."
        ),
    ),
    FactCheckAuditUnit(
        "L3.2",
        "Drug optimizer",
        "HEURISTIC",
        "ADDITIVE",
        ("drug_ek4a",),
        "Exact when claim lines present; substitution savings heuristic",
    ),
    FactCheckAuditUnit(
        "L3.3",
        "Copay savings",
        "PARTIAL",
        "ADDITIVE",
        ("copay_exemption_ek1a",),
    ),
    FactCheckAuditUnit(
        "L3.4",
        "Billing strategy",
        "PARTIAL",
        "ADDITIVE",
        (
            "payment_method_package",
            "payment_method_itemized",
            "payment_method_tier_override",
        ),
        note=(
            "Claim-exact only: recommend_billing_strategy_from_claims with claim_lines / "
            "ek2c_code methodology; legacy chapter-median estimator removed 2026-06."
        ),
    ),
    FactCheckAuditUnit(
        "L3.5",
        "Material pre-check",
        "COMPLIANT",
        "PARTIAL_OVERLAP",
        ("material_preauth_ek3c1", "material_miat_ek3c2", "material_bundling_prose"),
        note=(
            "MIAT interval + pre-auth + bundled taxonomy exact on synthetic claim lines. "
            "Pricing via price_material_lines (billed or exact EK-3 code); "
            "fuzzy estimate_material_costs removed 2026-06."
        ),
    ),
    FactCheckAuditUnit(
        "L3.6",
        "Billing orchestrator",
        "PARTIAL",
        "ADDITIVE",
        (),
        note=(
            "Cross-cutting orchestrator — no dedicated registry rule. "
            "SUT_REQUIRE_CLAIM_LINES fail-closed: missing claim context yields "
            "missing_exact_inputs blocks with zero fabricated ₺ (2026-06)."
        ),
    ),
    FactCheckAuditUnit(
        "L4.1",
        "EK-2B FFS pricing",
        "COMPLIANT",
        "ADDITIVE",
        ("pricing_ek2b",),
    ),
    FactCheckAuditUnit(
        "L4.2",
        "EK-2C DRG pricing",
        "COMPLIANT",
        "ADDITIVE",
        ("pricing_ek2c",),
        note=(
            "Patient DRG panel is claim-exact (billed package lines + dated EK-2C catalog "
            "via get_ek2c_price_for_date). Legacy ICD-chapter median helper pricing.drg "
            "was removed 2026-06."
        ),
    ),
    FactCheckAuditUnit(
        "L4.3",
        "EK-2A outpatient",
        "PARTIAL",
        "ADDITIVE",
        ("pricing_ek2a",),
        note=(
            "enrich_visit_prices_from_claim_header uses exact EK-2A tier row only; "
            "cohort-mean fallback removed 2026-06."
        ),
    ),
    FactCheckAuditUnit(
        "L4.4",
        "Specialty materials EK-3",
        "PARTIAL",
        "ADDITIVE",
        ("specialty_materials_prose", "specialty_materials"),
    ),
)

_VERDICT_RANK: dict[FactCheckVerdict, int] = {
    "WRONG": 0,
    "NEEDS_CLAIM_LINES": 1,
    "PARTIAL": 2,
    "HEURISTIC": 3,
    "COMPLIANT": 4,
    "OUT_OF_SCOPE": 5,
}

_MEDULA_RANK: dict[MedulaOverlap, int] = {
    "MEDULA_DUPLICATE": 0,
    "PARTIAL_OVERLAP": 1,
    "ADDITIVE": 2,
    "NOT_APPLICABLE": 3,
}


def _worst_verdict(verdicts: list[FactCheckVerdict]) -> FactCheckVerdict:
    return min(verdicts, key=lambda v: _VERDICT_RANK[v])


def _worst_medula(overlaps: list[MedulaOverlap]) -> MedulaOverlap:
    return min(overlaps, key=lambda o: _MEDULA_RANK[o])


def build_rule_fact_check_index() -> dict[str, dict[str, Any]]:
    """Map rule_id -> fact-check fields for :class:`RuleRegistryEntry` enrichment."""
    bucket: dict[str, dict[str, Any]] = {}

    for unit in FACT_CHECK_AUDIT_UNITS:
        for rule_id in unit.linked_rule_ids:
            row = bucket.setdefault(
                rule_id,
                {
                    "fact_check_units": [],
                    "verdicts": [],
                    "medula_overlaps": [],
                    "notes": [],
                },
            )
            row["fact_check_units"].append(unit.unit_id)
            row["verdicts"].append(unit.verdict)
            row["medula_overlaps"].append(unit.medula_overlap)
            if unit.note:
                row["notes"].append(f"{unit.unit_id}: {unit.note}")

    index: dict[str, dict[str, Any]] = {}
    for rule_id, row in bucket.items():
        index[rule_id] = {
            "fact_check_verdict": _worst_verdict(row["verdicts"]),
            "medula_overlap": _worst_medula(row["medula_overlaps"]),
            "fact_check_units": tuple(row["fact_check_units"]),
            "fact_check_note": "; ".join(row["notes"]),
        }
    for rule_id, supplemental in SUPPLEMENTAL_FACT_CHECK_RULES.items():
        index[rule_id] = supplemental
    return index


RULE_FACT_CHECK_INDEX: dict[str, dict[str, Any]] = build_rule_fact_check_index()


def fact_check_rollup() -> dict[str, Any]:
    """Aggregate verdict counts for API / UI summary banner."""
    by_verdict = dict(Counter(unit.verdict for unit in FACT_CHECK_AUDIT_UNITS))
    return {
        "audit_closed": AUDIT_CLOSED,
        "total_units": AUDIT_TOTAL_UNITS,
        "by_verdict": {
            "COMPLIANT": by_verdict.get("COMPLIANT", 0),
            "PARTIAL": by_verdict.get("PARTIAL", 0),
            "HEURISTIC": by_verdict.get("HEURISTIC", 0),
            "NEEDS_CLAIM_LINES": by_verdict.get("NEEDS_CLAIM_LINES", 0),
            "WRONG": by_verdict.get("WRONG", 0),
            "OUT_OF_SCOPE": by_verdict.get("OUT_OF_SCOPE", 0),
        },
        "units": [
            {
                "unit_id": unit.unit_id,
                "title": unit.title,
                "verdict": unit.verdict,
                "medula_overlap": unit.medula_overlap,
                "linked_rule_ids": list(unit.linked_rule_ids),
                "note": unit.note or None,
            }
            for unit in FACT_CHECK_AUDIT_UNITS
        ],
    }
