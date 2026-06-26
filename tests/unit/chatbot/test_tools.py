"""Regression tests for BILUN chat tool execution."""

from __future__ import annotations

import asyncio

import pytest

from src.bilun.chatbot.llm import _extract_tool_calls
from src.bilun.chatbot.tools import (
    ToolSession,
    _normalize_alert_category,
    execute_tool_call,
)

pytestmark = pytest.mark.unit


def test_normalize_alert_category_maps_legacy_labels():
    assert _normalize_alert_category("surcharge-exposure") == "surcharge"
    assert _normalize_alert_category("copay-rate") == "copay_rates"
    assert _normalize_alert_category(None) == "exemptions"


def test_extract_tool_calls_when_finish_reason_is_not_tool_calls():
    response = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "get_revenue_recovery", "arguments": "{}"},
                        }
                    ]
                },
            }
        ]
    }
    assert _extract_tool_calls(response) is not None
    assert len(_extract_tool_calls(response)) == 1


def test_execute_tool_call_get_patient_alerts_normalizes_category(monkeypatch):
    captured: dict[str, str] = {}

    def fake_get_patient_alerts(*, category, status, limit, offset):
        captured["category"] = category
        return {"alerts": [], "category": category}

    monkeypatch.setattr(
        "src.bilun.api.routes.alerts.get_patient_alerts",
        fake_get_patient_alerts,
    )

    result = asyncio.run(
        execute_tool_call(
            "get_patient_alerts",
            {"category": "surcharge-exposure"},
            ToolSession(),
        )
    )

    assert result.success is True
    assert captured["category"] == "surcharge"


def test_execute_tool_call_search_sut_clauses_routes_to_retrieval(monkeypatch):
    captured: dict = {}

    def fake_search_clauses(query, *, top_k, annex, section_prefix):
        captured.update(query=query, top_k=top_k, annex=annex, section_prefix=section_prefix)
        return [{"clause_id": "C000001", "section_id": "1.8", "text_tr": "x", "score": 0.9}]

    monkeypatch.setattr(
        "src.bilun.domain.sut.clause_retrieval.search_clauses",
        fake_search_clauses,
    )

    result = asyncio.run(
        execute_tool_call(
            "search_sut_clauses",
            {"query": "katılım payı", "annex": "EK-2/C"},
            ToolSession(),
        )
    )

    assert result.success is True
    assert captured["query"] == "katılım payı"
    assert captured["annex"] == "EK-2/C"
    assert captured["top_k"] == 5
    assert "C000001" in result.content


def test_search_sut_clauses_rejects_unknown_param():
    result = asyncio.run(
        execute_tool_call("search_sut_clauses", {"qry": "typo"}, ToolSession())
    )
    assert result.success is False
    assert result.error is not None


def test_execute_tool_call_returns_string_content(monkeypatch):
    monkeypatch.setattr(
        "src.bilun.api.routes.optimization.get_revenue_recovery",
        lambda: {"grand_total_recoverable": 123.45, "n_patients": 2},
    )

    result = asyncio.run(execute_tool_call("get_revenue_recovery", {}, ToolSession()))

    assert result.success is True
    assert isinstance(result.content, str)
    assert "123.45" in result.content
    assert len(result.content) > 0


def test_execute_tool_call_search_medula_playbook_routes_to_kb(monkeypatch):
    captured: dict = {}

    def fake_search_playbook_entries(query, *, sonuc_kodu, top_n):
        captured.update(query=query, sonuc_kodu=sonuc_kodu, top_n=top_n)
        return [
            {
                "playbook_key": "1688_molecular_microbiology",
                "sonuc_kodu": "1688",
                "sut_anchor": "EK-2",
            }
        ]

    monkeypatch.setattr(
        "src.bilun.chatbot.medula_kb.search_playbook_entries",
        fake_search_playbook_entries,
    )

    result = asyncio.run(
        execute_tool_call(
            "search_medula_playbook",
            {"query": "moleküler mikrobiyoloji rapor eksik", "sonuc_kodu": "1688"},
            ToolSession(),
        )
    )

    assert result.success is True
    assert captured["query"] == "moleküler mikrobiyoloji rapor eksik"
    assert captured["sonuc_kodu"] == "1688"
    assert captured["top_n"] == 5
    assert "1688_molecular_microbiology" in result.content


def test_execute_tool_call_get_bill_billing_report(monkeypatch):
    captured: dict[str, str] = {}

    def fake_get_bill_billing_report(patient_id, claim_id):
        captured["patient_id"] = patient_id
        captured["claim_id"] = claim_id
        return {"patient_id": patient_id, "claim_id": claim_id, "audit_exposure_try": 1.0}

    monkeypatch.setattr(
        "src.bilun.api.routes.billing.get_bill_billing_report",
        fake_get_bill_billing_report,
    )

    result = asyncio.run(
        execute_tool_call(
            "get_bill_billing_report",
            {"patient_id": "P-001", "claim_id": "F-P-001-048"},
            ToolSession(),
        )
    )

    assert result.success is True
    assert captured == {"patient_id": "P-001", "claim_id": "F-P-001-048"}
    assert "audit_exposure_try" in result.content


def test_get_tool_schemas_includes_repo_tools_for_dev():
    from src.bilun.chatbot.tools import get_tool_schemas

    dev_names = {tool["function"]["name"] for tool in get_tool_schemas(user_role="dev")}
    officer_names = {tool["function"]["name"] for tool in get_tool_schemas(user_role="billing_officer")}

    assert "read_repo_file" in dev_names
    assert "grep_repo" in dev_names
    assert "read_repo_file" not in officer_names
    assert "get_bill_billing_report" in officer_names


def test_get_tool_schemas_exposes_drg_and_validator_to_both_roles():
    """The two newly-exposed algorithms must be in the core schema (both roles)."""
    from src.bilun.chatbot.tools import get_tool_schemas

    officer_names = {tool["function"]["name"] for tool in get_tool_schemas(user_role="billing_officer")}
    dev_names = {tool["function"]["name"] for tool in get_tool_schemas(user_role="dev")}

    assert "get_drg_episode_cost" in officer_names
    assert "get_drg_episode_cost" in dev_names
    assert "validate_claim" in officer_names
    assert "validate_claim" in dev_names


def test_execute_tool_call_get_drg_episode_cost_extracts_summary(monkeypatch):
    """DRG tool must call the outcome route with include_expensive=True and return drg_summary."""
    captured: dict = {}

    def fake_get_bilun_patient_outcome(patient_id, include_expensive=True):
        captured["patient_id"] = patient_id
        captured["include_expensive"] = include_expensive
        return {
            "patient_id": patient_id,
            "drg_summary": {
                "n_episodes": 2,
                "total_drg_cost": 45678.9,
                "mean_episode_cost": 22839.45,
                "most_expensive_drg": "Q-123",
                "pricing_status": "fully_priced",
            },
        }

    monkeypatch.setattr(
        "src.bilun.api.routes.patients.get_bilun_patient_outcome",
        fake_get_bilun_patient_outcome,
    )

    result = asyncio.run(
        execute_tool_call(
            "get_drg_episode_cost",
            {"patient_id": "P-001"},
            ToolSession(),
        )
    )

    assert result.success is True
    assert captured["patient_id"] == "P-001"
    assert captured["include_expensive"] is True
    assert "45678.9" in result.content
    assert "most_expensive_drg" in result.content


def test_execute_tool_call_get_drg_episode_cost_missing_returns_unavailable(monkeypatch):
    """When the patient has no DRG data, the tool surfaces a clear unavailable marker."""
    monkeypatch.setattr(
        "src.bilun.api.routes.patients.get_bilun_patient_outcome",
        lambda patient_id, include_expensive=True: {"patient_id": patient_id},
    )

    result = asyncio.run(
        execute_tool_call(
            "get_drg_episode_cost",
            {"patient_id": "P-001"},
            ToolSession(),
        )
    )

    assert result.success is True
    assert "unavailable_reason" in result.content


def test_execute_tool_call_validate_claim_remaps_stored_fields(monkeypatch):
    """validate_claim tool must remap stored-claim fields into validator's short names."""
    detail_captured: dict = {}

    def fake_get_patient_claim_detail(patient_id, claim_id):
        detail_captured["patient_id"] = patient_id
        detail_captured["claim_id"] = claim_id
        return {
            "claim_id": claim_id,
            "patient_id": patient_id,
            "primary_icd10": "I10",
            "procedures": [
                {"procedure_code": "600160", "procedure_name": "Konsültasyon"},
            ],
            "materials": [
                {
                    "material_name": "Stent",
                    "material_code": "EK3-001",
                    "quantity": 1,
                    "unit_price_try": 2000.0,
                    "billed_amount_try": 2000.0,
                },
            ],
        }

    validator_captured: dict = {}

    def fake_validate_claim(claim_dict):
        validator_captured.update(claim_dict)
        # Return a ClaimValidationResult-shaped object (duck-typed).
        class _Violation:
            def __init__(self):
                self.rule = "bundling"
                self.severity = "warning"
                self.material_name = "Stent"
                self.message = "bundled"
                self.savings_try = 0.0
                self.risk_amount = 0.0

        class _Line:
            def __init__(self):
                self.material_code = claim_dict["materials"][0]["code"]
                self.material_name = claim_dict["materials"][0]["name"]
                self.unit_price = claim_dict["materials"][0]["unit_price"]
                self.quantity = claim_dict["materials"][0]["quantity"]
                self.total_price = 2000.0
                self.is_reimbursable = True
                self.is_bundled = False
                self.source = "billed"
                self.exactness_status = "exact"
                self.notes = ""

        class _Result:
            claim_id = claim_dict["claim_id"]
            is_valid = True
            violations = [_Violation()]
            material_lines = [_Line()]
            total_claim_amount = 2000.0
            total_savings_try = 0.0
            total_risk_try = 0.0
            n_bundling_violations = 1
            n_exclusion_violations = 0
            validation_time_ms = 1.0
            summary = "ok"

        return _Result()

    monkeypatch.setattr(
        "src.bilun.api.routes.patients.get_patient_claim_detail",
        fake_get_patient_claim_detail,
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.validate_claim",
        fake_validate_claim,
    )

    result = asyncio.run(
        execute_tool_call(
            "validate_claim",
            {"patient_id": "P-001", "claim_id": "F-P-001-048"},
            ToolSession(),
        )
    )

    assert result.success is True
    # Adapter remapped the material fields to the validator's short names
    assert validator_captured["procedure_code"] == "600160"
    remapped = validator_captured["materials"][0]
    assert remapped["name"] == "Stent"
    assert remapped["code"] == "EK3-001"
    assert remapped["unit_price"] == 2000.0
    assert remapped["billed_amount"] == 2000.0
    assert validator_captured["drug_context"] is None
    # Result serialized with the flattened route shape
    assert "600160" not in result.content  # procedure_code not echoed, but materials are
    assert "EK3-001" in result.content
    assert "is_valid" in result.content


def test_validate_claim_rejects_missing_claim_id():
    result = asyncio.run(
        execute_tool_call("validate_claim", {"patient_id": "P-001"}, ToolSession())
    )
    assert result.success is False
    assert result.error is not None
    assert "claim_id" in result.error
