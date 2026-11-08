"""Synthetic selected-bill chat regressions; provider calls are captured, never sent."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.bilun.api.routes import chat
from src.bilun.chatbot.context import build_billing_context, officer_page_context
from src.bilun.shared.exceptions import ServiceUnavailableError

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def chat_budget(monkeypatch, tmp_path):
    # Every non-developer chat draws on the daily allowance, so the run needs one.
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_DAILY_TOKEN_BUDGET", "1000000")
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_BUDGET_DB", str(tmp_path / "budget.sqlite3"))


def _page(claim_id="BILL-A"):
    return {
        "patient_id": "PATIENT",
        "visible_billing": {"scope": "bill", "patient_id": "PATIENT", "claim_id": claim_id},
        "sections": {"billing_report": {"claim_id": claim_id, "loaded": True}},
    }


def _report(claim_id="BILL-A"):
    return {
        "patient_id": "PATIENT", "claim_id": claim_id, "scope": "bill",
        "total_recoverable_try": 100 if claim_id == "BILL-A" else 300,
        "lab": {"flagged_tests": [{"test_name": f"Lab-{i}"} for i in range(8)]},
        "source_path": "PRIVATE_PATH",
    }


@pytest.mark.parametrize("role", ["billing_officer", "dev"])
@pytest.mark.parametrize("claim_id", ["BILL-A", "BILL-B"])
def test_selected_bill_scope_is_role_independent_and_formatted(monkeypatch, role, claim_id):
    calls = []
    monkeypatch.setattr(chat, "get_bill_billing_report", lambda pid, cid: calls.append((pid, cid)) or _report(cid))
    monkeypatch.setattr(chat, "get_patient_billing_report", lambda _: pytest.fail("patient fallback"))
    page = _page(claim_id)
    if role == "billing_officer":
        page = officer_page_context(page)
    result = chat._fetch_billing_report_for_chat("PATIENT", user_role=role, page_context=page)
    assert calls == [("PATIENT", claim_id)]
    assert result["scope"] == "bill" and result["claim_id"] == claim_id
    context = build_billing_context({"billing_report": result}, detail_level="full" if role == "dev" else "summary")
    assert f"Bill ID: {claim_id}" in context
    assert "Scope: bill" in context
    assert f"{result['total_recoverable_try']:.2f} TRY" in context
    assert len(result["lab"]["flagged_tests"]) == (8 if role == "dev" else 5)
    assert ("source_path" in result) is (role == "dev")


@pytest.mark.parametrize("role", ["billing_officer", "dev"])
@pytest.mark.parametrize("field,value", [("patient_id", "OTHER"), ("claim_id", "OTHER"), ("scope", "patient")])
def test_mismatched_server_report_never_falls_back(monkeypatch, role, field, value):
    monkeypatch.setattr(chat, "get_bill_billing_report", lambda *_: {**_report(), field: value})
    monkeypatch.setattr(chat, "get_patient_billing_report", lambda _: pytest.fail("patient fallback"))
    with pytest.raises(ServiceUnavailableError):
        chat._fetch_billing_report_for_chat("PATIENT", user_role=role, page_context=_page())


@pytest.mark.parametrize("role", ["billing_officer", "dev"])
def test_missing_selected_bill_never_falls_back(monkeypatch, role):
    def missing(*_):
        raise ServiceUnavailableError("Missing synthetic bill")
    monkeypatch.setattr(chat, "get_bill_billing_report", missing)
    monkeypatch.setattr(chat, "get_patient_billing_report", lambda _: pytest.fail("patient fallback"))
    with pytest.raises(ServiceUnavailableError):
        chat._fetch_billing_report_for_chat("PATIENT", user_role=role, page_context=_page())


@pytest.mark.parametrize("value", ["", " ", 17, [], {}, "x" * 129, None])
def test_malformed_selected_claim_rejected_before_filtering(value):
    with pytest.raises(ValidationError):
        chat.BilunChatRequest(patient_id="PATIENT", page_context=_page(value))


@pytest.mark.parametrize("change", ["conflict", "foreign", "no_patient", "missing_claim"])
def test_contradictory_selection_rejected(change):
    page = _page()
    patient_id = "PATIENT"
    if change == "conflict":
        page["sections"]["billing_report"]["claim_id"] = "BILL-B"
    elif change == "foreign":
        page["visible_billing"]["patient_id"] = "OTHER"
    elif change == "no_patient":
        patient_id = None
    else:
        del page["visible_billing"]["claim_id"]
        del page["sections"]["billing_report"]["claim_id"]
    with pytest.raises(ValidationError):
        chat.BilunChatRequest(patient_id=patient_id, page_context=page)


def test_visible_only_selection_survives_officer_filter():
    assert chat._claim_id_from_page_context(officer_page_context({"visible_billing": _page()["visible_billing"]})) == "BILL-A"


@pytest.mark.parametrize("role", ["billing_officer", "dev"])
def test_no_claim_selection_keeps_patient_report(monkeypatch, role):
    monkeypatch.setattr(chat, "get_patient_billing_report", lambda pid: {"patient_id": pid, "scope": "patient", "total_recoverable_try": 1000})
    monkeypatch.setattr(chat, "get_bill_billing_report", lambda *_: pytest.fail("unexpected bill lookup"))
    result = chat._fetch_billing_report_for_chat("PATIENT", user_role=role, page_context={})
    assert result["total_recoverable_try"] == 1000


@pytest.mark.parametrize("role", ["billing_officer", "dev"])
@pytest.mark.parametrize("missing", [False, True])
def test_http_chat_uses_selected_bill_and_preserves_role_tools(monkeypatch, role, missing):
    from src.bilun.api import app
    captured = []
    async def startup():
        pass
    async def plain(_messages, context, **kwargs):
        captured.append(("plain", context, kwargs["user_role"]))
        yield "ok"
    async def tools(_messages, context, **kwargs):
        captured.append(("tools", context, kwargs["user_role"]))
        yield "ok"
    def bill(*_):
        if missing:
            raise ServiceUnavailableError("Missing selected bill")
        return _report()
    monkeypatch.setattr("src.bilun.api.startup.startup", startup)
    monkeypatch.setattr(chat, "_check_rate_limit", lambda _: True)
    monkeypatch.setattr(chat, "resolve_user_role", lambda _: role)
    for name in ("get_optimization_summary", "get_revenue_recovery", "get_bilun_patient_outcome", "_get_patient_optimization_for_chat"):
        monkeypatch.setattr(chat, name, lambda *_: {})
    monkeypatch.setattr(chat, "get_bill_billing_report", bill)
    monkeypatch.setattr(chat, "get_patient_billing_report", lambda _: pytest.fail("patient fallback"))
    monkeypatch.setattr(chat, "stream_chat_response", plain)
    monkeypatch.setattr(chat, "stream_chat_response_with_tools", tools)
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"patient_id": "PATIENT", "page_context": _page(), "messages": [{"role": "user", "content": "Explain selected bill"}], "user_role": "dev"})
    assert response.status_code == 200
    if missing:
        assert captured == []
        assert "event: error" in response.text
    else:
        assert len(captured) == 1
        assert captured[0][0] == ("tools" if role == "dev" else "plain")
        assert captured[0][2] == role
        assert "100.00 TRY" in captured[0][1]
        assert "Bill ID: BILL-A" in captured[0][1]
        assert ("PRIVATE_PATH" in captured[0][1]) is (role == "dev")
