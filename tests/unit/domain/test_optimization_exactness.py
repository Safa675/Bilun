"""Phase 5 regression coverage for optimization exactness gating."""

from __future__ import annotations

import polars as pl
import pytest

pytestmark = pytest.mark.unit


def test_is_exact_output_requires_explicit_exact_status() -> None:
    from src.bilun.domain.optimization.exactness import is_exact_output

    assert is_exact_output({"exactness_status": "exact"}) is True
    assert is_exact_output({"exactness_status": " exact "}) is True
    assert is_exact_output({"exactness_status": "missing_exact_inputs"}) is False
    assert is_exact_output({"pricing_status": "exact"}) is False
    assert is_exact_output({}) is False
    assert is_exact_output(None) is False


def test_non_exact_optimization_features_return_missing_exact_inputs() -> None:
    from src.bilun.domain.optimization.copay_rates import analyze_copay_rate_exposure
    from src.bilun.domain.optimization.surcharge import analyze_surcharge_exposure
    from src.bilun.domain.optimization.unbundling import detect_drg_unbundling

    surcharge = analyze_surcharge_exposure({"C"})
    assert surcharge["exactness_status"] == "missing_exact_inputs"
    assert surcharge["n_applicable_procedures"] is None
    assert surcharge["required_inputs_missing"] == [
        "billed_procedure_codes",
        "procedure_dates",
    ]

    copay_rate = analyze_copay_rate_exposure({"C"})
    assert copay_rate["exactness_status"] == "missing_exact_inputs"
    assert copay_rate["mean_rate"] is None

    drg = detect_drg_unbundling({"C"})
    assert drg["exactness_status"] == "missing_exact_inputs"
    assert drg["has_unbundling_risk"] is None
    assert drg["chapter_analysis"] == []

def test_compute_optimization_summary_keeps_exact_exemptions_but_gates_non_exact_blocks(
    monkeypatch,
) -> None:
    import src.bilun.domain.optimization.aggregator as agg_mod

    def _fake_evaluate(inp):
        if "E11.9" in inp.diagnoses:
            return {
                "exempt": True,
                "n_qualifying": 1,
                "qualifying_diagnoses": [
                    {"icd10": "E11.9", "disease": "Diabetes", "range": "E10-E14"}
                ],
                "exemption_sources": [{"category": "ek1a_chronic"}],
                "categories_not_evaluated": [],
                "primary_exemption_category": "ek1a_chronic",
            }
        return {
            "exempt": False,
            "n_qualifying": 0,
            "qualifying_diagnoses": [],
            "exemption_sources": [],
            "categories_not_evaluated": [],
            "primary_exemption_category": None,
        }

    monkeypatch.setattr(agg_mod, "_get_ek1a_by_letter", lambda: {})
    monkeypatch.setattr(agg_mod, "evaluate_copay_exemption", _fake_evaluate)
    monkeypatch.setattr(
        agg_mod,
        "audit_temporal_prices",
        lambda: {"ek2b": {}, "ek2c": {}, "methodology": "Real gazette history"},
    )

    summary = agg_mod.compute_optimization_summary(
        pl.DataFrame({"patient_id": ["P1"], "TANIKODU": ["E11.9"]}),
        ["P1"],
        diagnoses_by_pid={"P1": ["E11.9"]},
    )

    assert summary["copay_exemptions"]["n_total_patients"] == 1
    assert summary["copay_exemptions"]["n_exempt_patients"] == 1

    assert summary["surcharge_exposure"]["exactness_status"] == "missing_exact_inputs"
    assert summary["surcharge_exposure"]["mean_applicable_per_patient"] is None

    assert summary["copay_rate_exposure"]["exactness_status"] == "missing_exact_inputs"
    assert summary["copay_rate_exposure"]["cohort_mean_rate"] is None

    assert summary["drg_unbundling"]["exactness_status"] == "missing_exact_inputs"
    assert summary["drg_unbundling"]["n_patients_checked"] == 1
    assert summary["drg_unbundling"]["total_potential_savings"] is None

    assert summary["drug_discount_validation"]["exactness_status"] == "missing_exact_inputs"
    assert summary["drug_discount_validation"]["n_drug_lines"] is None
