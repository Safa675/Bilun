"""Unit tests for claim validation orchestrator (L1.3)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_validate_claim_bundling_violation(monkeypatch) -> None:
    from src.bilun.domain.rule_engine import _validate_claim_legacy as validate_claim  # Phase 2.4: these tests patch the legacy dict-path internals

    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_bundling_violations",
        lambda materials, procedure_code=None: [
            {
                "severity": "warning",
                "material_name": materials[0]["name"],
                "message": "Bundled consumable billed separately",
                "savings_try": 12.5,
            }
        ],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_exclusion_violations",
        lambda materials: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.price_material_lines",
        lambda materials: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_material_bundling_prose",
        lambda materials, procedure_code=None: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_specialty_materials_prose",
        lambda materials: [],
    )

    result = validate_claim(
        {
            "claim_id": "CLM-1",
            "procedure_code": "520030",
            "materials": [{"name": "Bistüri ucu", "unit_price": 12.5, "quantity": 1}],
        }
    )
    assert result.n_bundling_violations == 1
    assert result.total_savings_try == 12.5
    assert result.is_valid is True


def test_validate_claim_exclusion_makes_invalid(monkeypatch) -> None:
    from src.bilun.domain.rule_engine import _validate_claim_legacy as validate_claim  # Phase 2.4: these tests patch the legacy dict-path internals

    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_bundling_violations",
        lambda materials, procedure_code=None: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_exclusion_violations",
        lambda materials: [
            {
                "severity": "error",
                "material_name": materials[0]["name"],
                "message": "Non-reimbursable material",
                "risk_amount": 50.0,
            }
        ],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.price_material_lines",
        lambda materials: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_material_bundling_prose",
        lambda materials, procedure_code=None: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_specialty_materials_prose",
        lambda materials: [],
    )

    result = validate_claim(
        {
            "claim_id": "CLM-2",
            "materials": [{"name": "Excluded item", "unit_price": 50.0}],
        }
    )
    assert result.n_exclusion_violations == 1
    assert result.total_risk_try == 50.0
    assert result.is_valid is False


# ── drug_indication wiring into validate_claim (§4.2) ──────────────────────────


def _stub_no_other_violations(monkeypatch) -> None:
    """Stub bundling/exclusion/prose/pricing so only drug_indication fires."""
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_bundling_violations",
        lambda materials, procedure_code=None: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_exclusion_violations", lambda materials: []
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.price_material_lines", lambda materials: []
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_material_bundling_prose",
        lambda materials, procedure_code=None: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_specialty_materials_prose",
        lambda materials: [],
    )


def test_validate_claim_skips_drug_indication_without_context(monkeypatch) -> None:
    """No drug_context → drug_indication never runs (backwards-compatible)."""
    _stub_no_other_violations(monkeypatch)
    from src.bilun.domain.rule_engine import _validate_claim_legacy as validate_claim  # Phase 2.4: these tests patch the legacy dict-path internals

    result = validate_claim(
        {
            "claim_id": "CLM-1",
            "materials": [{"name": "Trastuzumab", "unit_price": 500}],
        }
    )
    drug_hits = [v for v in result.violations if v.rule == "drug_indication"]
    assert drug_hits == []
    assert result.is_valid is True


def test_validate_claim_drug_indication_biomarker_mismatch(monkeypatch) -> None:
    """drug_context + HER-2 negative → biomarker_mismatch error → invalid."""
    _stub_no_other_violations(monkeypatch)
    from src.bilun.domain.rule_engine import _validate_claim_legacy as validate_claim  # Phase 2.4: these tests patch the legacy dict-path internals

    result = validate_claim(
        {
            "claim_id": "CLM-2",
            "materials": [
                {
                    "name": "Trastuzumab",
                    "unit_price": 500,
                    "biomarkers": [{"marker": "HER2", "status": "negative"}],
                }
            ],
            "drug_context": {
                "primary_icd10": "C50.9",
                "prescriber_specialty": "tıbbi onkoloji",
                "board_report_present": True,
                "report_duration_months": 3,
            },
        }
    )
    drug_hits = [v for v in result.violations if v.rule == "drug_indication"]
    assert len(drug_hits) == 1
    assert drug_hits[0].severity == "error"
    assert drug_hits[0].details["violation_kind"] == "biomarker_mismatch"
    assert result.is_valid is False


def test_validate_claim_drug_indication_valid_passes(monkeypatch) -> None:
    """drug_context + correct HER-2 + valid inputs → no drug_indication violation."""
    _stub_no_other_violations(monkeypatch)
    from src.bilun.domain.rule_engine import _validate_claim_legacy as validate_claim  # Phase 2.4: these tests patch the legacy dict-path internals

    result = validate_claim(
        {
            "claim_id": "CLM-3",
            "materials": [
                {
                    "name": "Trastuzumab",
                    "unit_price": 500,
                    "biomarkers": [{"marker": "HER2", "status": "3+"}],
                }
            ],
            "drug_context": {
                "primary_icd10": "C50.9",
                "prescriber_specialty": "tıbbi onkoloji",
                "board_report_present": True,
                "report_duration_months": 3,
            },
        }
    )
    drug_hits = [v for v in result.violations if v.rule == "drug_indication"]
    assert drug_hits == []
    assert result.is_valid is True


def test_validate_claim_drug_indication_dose_exceeded(monkeypatch) -> None:
    """drug_context + deksametazon annual_count=5 → annual_max_exceeded error."""
    _stub_no_other_violations(monkeypatch)
    from src.bilun.domain.rule_engine import _validate_claim_legacy as validate_claim  # Phase 2.4: these tests patch the legacy dict-path internals

    result = validate_claim(
        {
            "claim_id": "CLM-4",
            "materials": [
                {
                    "name": "Deksametazon",
                    "unit_price": 800,
                    "annual_application_count": 5,
                }
            ],
            "drug_context": {
                "primary_icd10": "H34.8",
                "prescriber_specialty": "göz hastalıkları",
                "board_report_present": True,
            },
        }
    )
    drug_hits = [v for v in result.violations if v.rule == "drug_indication"]
    assert len(drug_hits) == 1
    assert drug_hits[0].details["violation_kind"] == "annual_max_exceeded"
    assert result.is_valid is False


def test_validate_claim_drug_indication_wrong_diagnosis(monkeypatch) -> None:
    """drug_context + trastuzumab with non-cancer ICD → indication_mismatch."""
    _stub_no_other_violations(monkeypatch)
    from src.bilun.domain.rule_engine import _validate_claim_legacy as validate_claim  # Phase 2.4: these tests patch the legacy dict-path internals

    result = validate_claim(
        {
            "claim_id": "CLM-5",
            "materials": [{"name": "Trastuzumab", "unit_price": 500}],
            "drug_context": {
                "primary_icd10": "J45.9",
                "prescriber_specialty": "tıbbi onkoloji",
                "board_report_present": True,
                "report_duration_months": 3,
            },
        }
    )
    drug_hits = [v for v in result.violations if v.rule == "drug_indication"]
    assert len(drug_hits) == 1
    assert drug_hits[0].details["violation_kind"] == "indication_mismatch"
