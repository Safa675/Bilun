"""Regression tests for BILUN chat tool execution."""

from __future__ import annotations

import asyncio

import pytest

from src.bilun.chatbot.llm import _extract_tool_calls, stream_chat_response_with_tools
from src.bilun.chatbot.tools import (
    ToolCallResult,
    ToolSession,
    _normalize_alert_category,
    execute_tool_call,
)

pytestmark = pytest.mark.unit


def _typed_validator_stub():
    return {
        "contract_version": 2, "request_id": "request:1", "claim_id": "C1",
        "validation_status": "partially_evaluated", "is_valid": None,
        "violations": [], "advisories": [], "material_applicability": [],
        "coverage": {"evaluation_count": 496, "authored_rule_count": 496,
                     "unresolved_count": 496, "disposition_counts": {"missing_inputs": 496},
                     "scope": "submitted_request_facts_only"},
        "provenance": {"identity_kind": "request_scoped_not_verified_patient",
                       "supplied_field_count": 1, "adapter_defaults_are_evidence": False},
        "summary": "Incomplete", "validation_time_ms": 1.0,
    }


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


def test_get_tool_schemas_exposes_validator_to_both_roles():
    """validate_claim must be in the core schema for both roles."""
    from src.bilun.chatbot.tools import get_tool_schemas

    officer_names = {tool["function"]["name"] for tool in get_tool_schemas(user_role="billing_officer")}
    dev_names = {tool["function"]["name"] for tool in get_tool_schemas(user_role="dev")}

    assert "get_drg_episode_cost" not in officer_names
    assert "get_drg_episode_cost" not in dev_names
    assert "validate_claim" in officer_names
    assert "validate_claim" in dev_names


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

    def fake_validate_claim(claim_dict, *, supplied_claim):
        validator_captured.update(claim_dict)
        assert supplied_claim["materials"][0]["billed_amount"] == 2000.0
        return {
            **_typed_validator_stub(),
            "contract_version": 2,
            "is_valid": None,
            "validation_status": "review_required",
            "violations": [],
            "advisories": [{
                "evidence_id": "A1", "rule": "test", "rule_id": None,
                "material_name": "Stent", "message": claim_dict["materials"][0]["code"],
                "disposition": "review_only", "source_status": "historical_match_unverified",
                "reason": "source_review_required",
            }],
            "legacy_result": {
                "total_savings_try": 987654.32,
                "violations": [{"message": "Unverified legacy denial statement"}],
            },
        }

    monkeypatch.setattr(
        "src.bilun.api.routes.patients.get_patient_claim_detail",
        fake_get_patient_claim_detail,
    )
    monkeypatch.setattr(
        "src.bilun.domain.claim_validation_v2.validate_claim_v2",
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
    # Result uses the same explicit v2 dictionary contract as the API
    assert "600160" not in result.content  # procedure_code not echoed, but materials are
    assert "EK3-001" in result.content
    assert "is_valid" in result.content
    assert "legacy_result" not in result.content
    assert "987654.32" not in result.content
    assert "Unverified legacy denial statement" not in result.content


def test_validate_claim_rejects_missing_claim_id():
    result = asyncio.run(
        execute_tool_call("validate_claim", {"patient_id": "P-001"}, ToolSession())
    )
    assert result.success is False
    assert result.error is not None
    assert "claim_id" in result.error


def test_stored_validator_keeps_missing_charge_distinct_from_zero():
    from src.bilun.chatbot.tools import _validate_stored_claim

    captured = {}

    def validator(legacy, *, supplied_claim):
        captured.update(supplied_claim)
        assert [row["billed_amount"] for row in legacy["materials"]] == [0, 0]
        return {**_typed_validator_stub(), "legacy_result": {"total_risk_try": 777}}

    result = _validate_stored_claim(
        lambda *_: {"materials": [
            {"material_name": "same", "unit_price_try": 100},
            {"material_name": "same", "unit_price_try": 100, "billed_amount_try": 0},
        ]},
        validator, "P1", "C1",
    )
    assert result == _typed_validator_stub()
    assert "billed_amount" not in captured["materials"][0]
    assert captured["materials"][1]["billed_amount"] == 0


def test_chatbot_and_api_use_identical_typed_contract(monkeypatch):
    from src.bilun.api.routes.validation import validate_claim_endpoint
    from src.bilun.chatbot.tools import _validate_stored_claim
    from src.bilun.domain.claim_validation_v2 import validate_claim_v2
    from src.bilun.shared.models import ClaimValidationRequest

    monkeypatch.setattr("src.bilun.domain.rule_engine.time.perf_counter", lambda: 100)
    chatbot = _validate_stored_claim(
        lambda *_: {"materials": [{"material_name": "altın kanal tedavisi",
                                    "unit_price_try": 100}]},
        validate_claim_v2, "P1", "C1",
    )
    api = validate_claim_endpoint(
        ClaimValidationRequest.model_validate({"claim_id": "C1", "materials": [
            {"name": "altın kanal tedavisi", "unit_price": 100}
        ]}), "2",
    )
    # Stored legacy adapter defaults quantity to 0; API defaults to 1. The
    # provenance-aware surfaces still share the same supplied facts/identity.
    assert {k: v for k, v in chatbot.items() if k != "legacy_result"} == {
        k: v for k, v in api.items() if k != "legacy_result"
    }
    assert chatbot["is_valid"] is None
    assert chatbot["violations"] == []
    assert "legacy_result" not in chatbot


def test_chatbot_shared_projection_rejects_injected_nested_money():
    from pydantic import ValidationError
    from src.bilun.chatbot.tools import _validate_stored_claim

    def leaking_validator(*_, **__):
        return {
            **_typed_validator_stub(), "validation_status": "review_required",
            "advisories": [{
                "evidence_id": "A1", "rule": "test", "material_name": "material",
                "message": "review", "disposition": "review_only",
                "source_status": "historical_match_unverified", "savings_try": 999,
            }],
        }

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _validate_stored_claim(lambda *_: {"materials": []}, leaking_validator, "P1", "C1")


@pytest.mark.parametrize(
    "tool_name,arguments",
    [
        ("read_repo_file", {"path": "src/bilun/chatbot/repo_tools.py"}),
        ("grep_repo", {"pattern": "audit_exposure_try"}),
    ],
)
def test_execute_tool_call_dev_tools_denied_without_dev_role(tool_name, arguments):
    denied_default = asyncio.run(execute_tool_call(tool_name, arguments, ToolSession()))
    denied_officer = asyncio.run(
        execute_tool_call(tool_name, arguments, ToolSession(), user_role="billing_officer")
    )
    for result in (denied_default, denied_officer):
        assert result.success is False
        assert result.error is not None
        assert "dev role" in result.error


def test_execute_tool_call_read_repo_file_allowed_for_dev():
    result = asyncio.run(
        execute_tool_call(
            "read_repo_file",
            {
                "path": "src/bilun/chatbot/repo_tools.py",
                "start_line": 1,
                "end_line": 5,
            },
            ToolSession(),
            user_role="dev",
        )
    )
    assert result.success is True
    assert "1:" in result.content
    assert "repo_tools" in result.content or "Read-only" in result.content


def test_execute_tool_call_grep_repo_allowed_for_dev():
    result = asyncio.run(
        execute_tool_call(
            "grep_repo",
            {
                "pattern": "audit_exposure_try",
                "path_prefix": "src/bilun/domain/billing",
                "max_matches": 5,
            },
            ToolSession(),
            user_role="dev",
        )
    )
    assert result.success is True
    assert "audit_exposure_try" in result.content


def test_stream_chat_response_with_tools_forwards_user_role(monkeypatch):
    """Dev schemas are useless unless execute_tool_call gets the same role."""
    import src.bilun.chatbot.llm as llm_mod

    captured: dict[str, object] = {}
    llm_calls = {"n": 0}

    async def fake_execute(tool_name, arguments, session=None, *, user_role="billing_officer"):
        captured["tool_name"] = tool_name
        captured["user_role"] = user_role
        return ToolCallResult(
            tool_name=tool_name,
            arguments=arguments,
            success=True,
            content="ok",
            elapsed_ms=1.0,
        )

    async def fake_llm(_payload):
        llm_calls["n"] += 1
        if llm_calls["n"] == 1:
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_repo_file",
                                        "arguments": (
                                            '{"path": "src/bilun/chatbot/repo_tools.py"}'
                                        ),
                                    },
                                }
                            ]
                        },
                    }
                ]
            }
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "done"},
                }
            ]
        }

    monkeypatch.setattr(llm_mod, "execute_tool_call", fake_execute)
    monkeypatch.setattr(llm_mod, "_call_llm_non_streaming", fake_llm)

    async def _collect():
        chunks = []
        async for item in stream_chat_response_with_tools(
            [{"role": "user", "content": "show repo_tools.py"}],
            user_role="dev",
        ):
            chunks.append(item)
        return chunks

    chunks = asyncio.run(_collect())
    assert captured["tool_name"] == "read_repo_file"
    assert captured["user_role"] == "dev"
    assert any(item == "done" or (isinstance(item, tuple) and item[1] == "done") for item in chunks)
