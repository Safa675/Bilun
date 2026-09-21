"""API tests for GET /api/compliance-index."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index
from src.bilun.shared.exceptions import ServiceUnavailableError, ValidationError

pytestmark = pytest.mark.unit


def _index_payload() -> dict:
    return build_cohort_compliance_index(
        {
            "P-A": {
                "recommended_actions": [
                    {
                        "action_id": "mat-a",
                        "surface": "materials",
                        "kind": "material_pre_auth",
                        "finding_type": "compliance",
                        "claim_id": "F-A",
                        "billed_try": 40.0,
                        "material_code": "M1",
                    }
                ]
            },
            "P-B": {
                "recommended_actions": [
                    {
                        "action_id": "lab-b",
                        "surface": "lab",
                        "kind": "hemogram_bundling",
                        "finding_type": "compliance",
                        "billed_try": 12.0,
                        "procedure_code": "L107020",
                    }
                ]
            },
        }
    )


def test_compliance_index_returns_cached_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.api.routes import compliance as route

    payload = _index_payload()
    monkeypatch.setattr(route, "_pipeline_mode", lambda: "hybrid")
    monkeypatch.setattr(route, "_get_cache_reader", lambda: object())
    monkeypatch.setattr(route, "_get_active_bilun_build_id", lambda _reader: "build-1")
    monkeypatch.setattr(route, "read_cache_json_payload", lambda *_args, **_kw: payload)
    monkeypatch.setattr(
        route,
        "read_active_bilun_data_source",
        lambda *_args, **_kw: {"mode": "synthetic_demo", "label": "demo", "is_synthetic": True, "notice": ""},
    )

    result = route.get_compliance_index()
    assert result["artifacts_available"] is True
    assert result["n_findings"] == 2
    assert result["pagination"]["total_matching"] == 2
    surfaces = {row["surface"] for row in result["rows"]}
    assert surfaces == {"materials", "lab"}


def test_compliance_index_filters_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.api.routes import compliance as route

    monkeypatch.setattr(route, "_pipeline_mode", lambda: "hybrid")
    monkeypatch.setattr(route, "_get_cache_reader", lambda: object())
    monkeypatch.setattr(route, "_get_active_bilun_build_id", lambda _reader: "build-1")
    monkeypatch.setattr(route, "read_cache_json_payload", lambda *_args, **_kw: _index_payload())
    monkeypatch.setattr(
        route,
        "read_active_bilun_data_source",
        lambda *_args, **_kw: {"mode": "synthetic_demo", "label": "demo", "is_synthetic": True, "notice": ""},
    )

    result = route.get_compliance_index(surface="materials")
    assert result["n_findings"] == 1
    assert result["rows"][0]["surface"] == "materials"


def test_compliance_index_http_keeps_drug_indication_nonfinancial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.bilun.api.routes import compliance as route

    payload = build_cohort_compliance_index(
        {
            "P-DRUG": {
                "recommended_actions": [
                    {
                        "action_id": "drug_indication:P-DRUG:C-1:D-1:indication_mismatch",
                        "finding_id": "drug_indication:P-DRUG:C-1:D-1:indication_mismatch",
                        "surface": "drug_indication",
                        "kind": "indication_mismatch",
                        "finding_type": "compliance",
                        "claim_id": "C-1",
                        "drug_claim_line_id": "D-1",
                        "billed_try": None,
                    }
                ]
            }
        }
    )
    monkeypatch.setattr(route, "_pipeline_mode", lambda: "hybrid")
    monkeypatch.setattr(route, "_get_cache_reader", lambda: object())
    monkeypatch.setattr(route, "_get_active_bilun_build_id", lambda _reader: "build-1")
    monkeypatch.setattr(route, "read_cache_json_payload", lambda *_args, **_kw: payload)
    monkeypatch.setattr(
        route,
        "read_active_bilun_data_source",
        lambda *_args, **_kw: {
            "mode": "synthetic_demo",
            "label": "demo",
            "is_synthetic": True,
            "notice": "",
        },
    )

    result = route.get_compliance_index(surface="drug_indication")

    assert result["rows"][0]["billed_try"] is None
    assert result["by_surface"]["drug_indication"]["billed_try"] is None
    assert result["billed_at_risk_try"] is None


def test_missing_cache_is_unavailable_not_zeros(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.api.routes import compliance as route

    monkeypatch.setattr(route, "_pipeline_mode", lambda: "hybrid")
    monkeypatch.setattr(route, "_get_cache_reader", lambda: object())
    monkeypatch.setattr(route, "_get_active_bilun_build_id", lambda _reader: "build-1")
    monkeypatch.setattr(route, "read_cache_json_payload", lambda *_args, **_kw: None)
    monkeypatch.setattr(
        route,
        "read_active_bilun_data_source",
        lambda *_args, **_kw: {"mode": "unavailable", "label": "missing", "is_synthetic": None, "notice": ""},
    )

    result = route.get_compliance_index()
    assert result["artifacts_available"] is False
    assert result["n_findings"] is None
    assert result["billed_at_risk_try"] is None
    assert result["rows"] == []


def test_invalid_surface_raises() -> None:
    from src.bilun.api.routes import compliance as route

    with pytest.raises(ValidationError):
        route.get_compliance_index(surface="surgical_sessions")


def test_no_active_build_raises_503(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.api.routes import compliance as route

    monkeypatch.setattr(route, "_pipeline_mode", lambda: "hybrid")
    monkeypatch.setattr(route, "_get_cache_reader", lambda: object())
    monkeypatch.setattr(route, "_get_active_bilun_build_id", lambda _reader: None)

    with pytest.raises(ServiceUnavailableError):
        route.get_compliance_index()
