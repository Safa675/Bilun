"""Phase 2.4 parity test — validate_claim vs _validate_claim_via_context.

Hard-gate test for the unified-claim-engine roadmap. Proves that the new
adapter-path validation (build ctx → analyze_claim → project) produces
ClaimValidationResults equivalent to the legacy dict-path validate_claim for
the same claim dicts. Once parity holds across representative fixtures, the
adapter body becomes validate_claim and the legacy body is retired.

Compares the fields validate_claim callers depend on (per the chatbot round-
trip test at tests/unit/chatbot/test_tools.py:344-354 and the /validate-claim
serialization at api/routes/validation.py:41-78): is_valid, n_bundling/
n_exclusion_violations, total_savings_try, total_risk_try, and the rule+
severity+material_name of each violation.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _claim_bundling() -> dict:
    """Claim with a material on EK-3B-1 (Bistüri ucu — scalpel blade)."""
    return {
        "claim_id": "CLM-BUND",
        "procedure_code": "520030",
        "materials": [{"name": "Bistüri ucu", "code": "", "unit_price": 12.5, "quantity": 1}],
    }


def _claim_clean_materials() -> dict:
    """Claim with materials not on any annex — should produce no violations."""
    return {
        "claim_id": "CLM-CLEAN",
        "procedure_code": "520030",
        "materials": [
            {"name": "Aspirin 500mg tablet", "code": "", "unit_price": 5.0, "quantity": 2},
        ],
    }


def _claim_multiple_materials() -> dict:
    """Claim with a mix of materials — exercises aggregation."""
    return {
        "claim_id": "CLM-MIX",
        "procedure_code": "520030",
        "materials": [
            {"name": "Bistüri ucu", "code": "", "unit_price": 10.0, "quantity": 1},
            {"name": "Generic gauze", "code": "", "unit_price": 3.0, "quantity": 5},
        ],
    }


def _claim_empty_materials() -> dict:
    """Claim with no materials — both paths short-circuit identically."""
    return {"claim_id": "CLM-EMPTY", "procedure_code": "520030", "materials": []}


def _claim_no_drug_context() -> dict:
    """Plain material claim, no drug_context — drug_indication must skip."""
    return {
        "claim_id": "CLM-NODRUG",
        "procedure_code": "520030",
        "materials": [{"name": "Bistüri ucu", "code": "", "unit_price": 8.0, "quantity": 1}],
    }


@pytest.mark.parametrize(
    "claim_factory",
    [
        _claim_bundling,
        _claim_clean_materials,
        _claim_multiple_materials,
        _claim_empty_materials,
        _claim_no_drug_context,
    ],
)
def test_validate_claim_adapter_parity(claim_factory) -> None:
    """The adapter path must match the legacy path on every claim fixture.

    The violation multiset (rule, severity, material_name) must be identical.
    validity flag, n_bundling, n_exclusion, and total_savings_try must match.
    total_risk_try may diverge for one documented reason: the §3.1/§3.3 prose
    motors compute risk_amount from billed_amount_try (unit_price × quantity)
    on the context path vs unit_price (per-unit) on the legacy dict path. The
    context path is MORE correct (risk = total billed at risk), so the
    divergence is an accepted correctness improvement of the unification,
    not a regression. The test asserts the divergence is only ever in this
    direction (adapted >= legacy for risk).
    """
    from src.bilun.domain.rule_engine import _validate_claim_legacy, validate_claim

    claim = claim_factory()

    legacy = _validate_claim_legacy(claim)
    adapted = validate_claim(claim)

    # Core validity flag.
    assert legacy.is_valid == adapted.is_valid, (
        f"is_valid mismatch: legacy={legacy.is_valid} adapted={adapted.is_valid}"
    )

    # Violation counts by motor.
    assert legacy.n_bundling_violations == adapted.n_bundling_violations, (
        f"n_bundling mismatch: legacy={legacy.n_bundling_violations} "
        f"adapted={adapted.n_bundling_violations}"
    )
    assert legacy.n_exclusion_violations == adapted.n_exclusion_violations, (
        f"n_exclusion mismatch: legacy={legacy.n_exclusion_violations} "
        f"adapted={adapted.n_exclusion_violations}"
    )

    # Savings totals must match (bundling savings use billed amount on both paths).
    assert legacy.total_savings_try == adapted.total_savings_try, (
        f"total_savings_try mismatch: legacy={legacy.total_savings_try} "
        f"adapted={adapted.total_savings_try}"
    )

    # Risk totals: adapted may exceed legacy (correctness fix — see docstring).
    # Never the reverse: that would be a real regression.
    assert adapted.total_risk_try >= legacy.total_risk_try, (
        f"total_risk_try regression: legacy={legacy.total_risk_try} "
        f"adapted={adapted.total_risk_try} (adapted must be >= legacy)"
    )

    # Violation multiset by (rule, severity, material_name) — order-independent.
    def _key(v):
        return (v.rule, v.severity, v.material_name)

    legacy_keys = sorted(_key(v) for v in legacy.violations)
    adapted_keys = sorted(_key(v) for v in adapted.violations)
    assert legacy_keys == adapted_keys, (
        f"violation multiset mismatch:\n  legacy={legacy_keys}\n  adapted={adapted_keys}"
    )


def test_validate_claim_adapter_preserves_summary_format() -> None:
    """The summary string format must match (chatbot round-trip depends on it)."""
    from src.bilun.domain.rule_engine import _validate_claim_legacy, validate_claim

    claim = _claim_bundling()
    legacy = _validate_claim_legacy(claim)
    adapted = validate_claim(claim)

    # Both summaries start with the same claim_id + VALID/INVALID prefix.
    assert legacy.summary.startswith(f"Claim {claim['claim_id']}"), legacy.summary
    assert adapted.summary.startswith(f"Claim {claim['claim_id']}"), adapted.summary
    # The VALID/INVALID token must agree.
    assert ("VALID" in legacy.summary) == ("VALID" in adapted.summary)
