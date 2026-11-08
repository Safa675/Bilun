"""Regression tests for the SUT-owned chat endpoint."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def synthetic_chat_runtime(monkeypatch, tmp_path):
    """Endpoint tests use their explicit synthetic stubs, never rebuild a cache."""
    async def startup():
        pass
    monkeypatch.setattr("src.bilun.api.startup.startup", startup)
    monkeypatch.setattr("src.bilun.api.routes.chat.get_revenue_recovery", lambda: {})
    # Every non-developer chat draws on the daily allowance, so the run needs one.
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_DAILY_TOKEN_BUDGET", "1000000")
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_BUDGET_DB", str(tmp_path / "budget.sqlite3"))


def test_sut_chat_streams_sut_only_context(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    captured: dict[str, object] = {}

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "get_optimization_summary",
        lambda: {
            "copay_exemptions": {
                "n_exempt_patients": 5,
                "n_total_patients": 12,
                "exemption_rate": 0.4167,
            },
            "surcharge_exposure": {
                "exactness_status": "missing_exact_inputs",
                "unavailable_reason": "Needs exact billed procedure lines.",
                "required_inputs_missing": ["billed_procedure_codes"],
            },
            "copay_rate_exposure": {"exactness_status": "missing_exact_inputs"},
            "drg_unbundling": {"exactness_status": "missing_exact_inputs"},
        },
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_bilun_patient_outcome",
        lambda patient_id: {
            "patient_id": patient_id,
            "sut_claim_totals": {
                "claim_count": 2,
                "total_billed_try": 100.0,
                "total_expected_payable_try": 90.0,
                "exactness_status": "exact",
            },
        },
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "_get_patient_optimization_for_chat",
        lambda patient_id: {
            "patient_id": patient_id,
            "n_diagnoses": 2,
            "icd10_chapters": ["E", "I"],
            "copay_exemptions": {"exempt": True, "n_qualifying": 1, "qualifying_diagnoses": []},
            "surcharge_exposure": {"exactness_status": "missing_exact_inputs"},
            "copay_rate_exposure": {"exactness_status": "missing_exact_inputs"},
            "drg_unbundling": {"exactness_status": "missing_exact_inputs"},
        },
    )

    async def fake_stream_chat_response(
        messages, runtime_context="", extra_params=None, intent="user_question", **kwargs
    ):
        captured["messages"] = messages
        captured["runtime_context"] = runtime_context
        captured["extra_params"] = extra_params
        captured["intent"] = intent
        yield "SUT "
        yield "ready"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream_chat_response)

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Summarize this patient."}],
                "patient_id": "P-001",
                "active_tab": "SUT Patient Workspace",
            },
        )

    assert response.status_code == 200
    assert 'data: "SUT "' in response.text
    assert 'data: "ready"' in response.text
    assert 'data: "[DONE]"' in response.text
    assert captured["messages"] == [{"role": "user", "content": "Summarize this patient."}]
    runtime_context = str(captured["runtime_context"])
    assert '"product": "BILUN"' in runtime_context
    assert '"active_tab": "SUT Patient Workspace"' in runtime_context
    assert "Patient ID: P-001" in runtime_context
    assert "Copay exempt: YES" in runtime_context
    assert "Needs exact billed procedure lines." in runtime_context


def test_sut_chat_user_question_uses_summarized_billing_context(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    captured: dict[str, object] = {}
    full_report = {
        "patient_id": "P-001",
        "lab": {
            "exactness_status": "exact",
            "flagged_tests": [
                {"test_name": f"Full-{i}", "flag_type": "dup", "savings_try": i}
                for i in range(8)
            ],
        },
        "copay": {"exactness_status": "missing_exact_inputs"},
        "billing_strategy": {"exactness_status": "exact"},
        "materials": {"exactness_status": "partial_exact"},
        "total_recoverable_try": 100.0,
    }

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "get_optimization_summary",
        lambda: {"copay_exemptions": {}, "surcharge_exposure": {}},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_bilun_patient_outcome",
        lambda patient_id: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "_get_patient_optimization_for_chat",
        lambda patient_id: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_billing_report",
        lambda patient_id: full_report,
    )

    async def fake_stream(messages, runtime_context="", intent="user_question", **kwargs):
        captured["runtime_context"] = runtime_context
        captured["intent"] = intent
        yield "ok"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream)

    page_context = {"sections": {"billing_report": {"loaded": True, "patient_id": "P-001"}}}
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Explain lab flags."}],
                "patient_id": "P-001",
                "active_tab": "SUT Billing Review",
                "intent": "user_question",
                "page_context": page_context,
                "user_role": "billing_officer",
            },
        )

    assert response.status_code == 200
    assert captured["intent"] == "user_question"
    runtime_context = str(captured["runtime_context"])
    assert '"page_view"' in runtime_context
    assert "Full-4" in runtime_context
    assert "Full-7" not in runtime_context
    assert "BILLING OPTIMIZATION (FULL)" not in runtime_context
    assert "--- BILLING OPTIMIZATION ---" in runtime_context


def test_sut_chat_patient_question_skips_tools_path(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    captured: dict[str, object] = {}

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "get_optimization_summary",
        lambda: {"copay_exemptions": {}, "surcharge_exposure": {}},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_bilun_patient_outcome",
        lambda patient_id: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "_get_patient_optimization_for_chat",
        lambda patient_id: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_billing_report",
        lambda patient_id: {"patient_id": patient_id, "lab": {}},
    )

    async def fake_stream(messages, runtime_context="", intent="user_question", **kwargs):
        captured["stream"] = "fast"
        yield "ok"

    async def fake_tools(messages, runtime_context="", intent="user_question", **kwargs):
        captured["stream"] = "tools"
        yield "ok"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream)
    monkeypatch.setattr(sut_chat_mod, "stream_chat_response_with_tools", fake_tools)

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "messages": [
                    {"role": "user", "content": "First question"},
                    {"role": "assistant", "content": "First answer"},
                    {"role": "user", "content": "Follow up"},
                ],
                "patient_id": "P-001",
                "active_tab": "SUT Patient Workspace",
                "intent": "user_question",
                "user_role": "billing_officer",
            },
        )

    assert response.status_code == 200
    assert captured["stream"] == "fast"


    assert captured["stream"] == "fast"


def test_sut_chat_dev_role_uses_tools_on_patient(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    captured: dict[str, object] = {}

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "resolve_user_role",
        lambda _username: "dev",
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "verify_session_token",
        lambda _token: type("Claims", (), {"username": "dev_user"})(),
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "_fetch_runtime_data",
        lambda *_args, **_kwargs: {"optimization_summary": {"status": "ready", "summary": {}}},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "build_bilun_runtime_context",
        lambda *_args, **_kwargs: "ctx",
    )

    async def fake_stream(messages, runtime_context="", intent="user_question", **kwargs):
        captured["stream"] = "fast"
        captured["user_role"] = kwargs.get("user_role")
        yield "ok"

    async def fake_tools(messages, runtime_context="", intent="user_question", **kwargs):
        captured["stream"] = "tools"
        captured["user_role"] = kwargs.get("user_role")
        yield "ok"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream)
    monkeypatch.setattr(sut_chat_mod, "stream_chat_response_with_tools", fake_tools)

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Why is audit exposure high?"}],
                "patient_id": "P-001",
                "active_tab": "SUT Patient Workspace",
                "intent": "user_question",
            },
        )

    assert response.status_code == 200
    assert captured["stream"] == "tools"
    assert captured["user_role"] == "dev"


def test_fetch_billing_report_for_chat_uses_bill_scope_for_dev(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod

    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(
        sut_chat_mod,
        "get_bill_billing_report",
        lambda patient_id, claim_id: calls.append(("bill", patient_id, claim_id)) or {
            "patient_id": patient_id,
            "claim_id": claim_id,
            "scope": "bill",
            "audit_exposure_try": 41103.79,
        },
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_billing_report",
        lambda patient_id: calls.append(("patient", patient_id)) or {"patient_id": patient_id},
    )

    payload = sut_chat_mod._fetch_billing_report_for_chat(
        "P-001",
        user_role="dev",
        page_context={
            "visible_billing": {
                "scope": "bill",
                "patient_id": "P-001",
                "claim_id": "F-P-001-048",
            }
        },
    )

    assert calls == [("bill", "P-001", "F-P-001-048")]
    assert payload["audit_exposure_try"] == 41103.79


def test_fetch_billing_report_for_chat_summarizes_for_officer(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod

    monkeypatch.setattr(
        sut_chat_mod,
        "get_bill_billing_report",
        lambda patient_id, claim_id: {
            "patient_id": patient_id,
            "claim_id": claim_id,
            "scope": "bill",
            "lab": {"exactness_status": "exact", "flagged_tests": [{"test_name": f"T-{i}"} for i in range(8)]},
            "copay": {},
            "billing_strategy": {},
            "materials": {},
            "total_recoverable_try": 10.0,
        },
    )

    payload = sut_chat_mod._fetch_billing_report_for_chat(
        "P-001",
        user_role="billing_officer",
        page_context={"visible_billing": {"claim_id": "F-P-001-048"}},
    )

    assert payload["patient_id"] == "P-001"
    assert len(payload["lab"]["flagged_tests"]) == 5


def test_sut_chat_auto_brief_uses_summarized_billing(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    captured: dict[str, object] = {}
    full_report = {
        "patient_id": "P-001",
        "lab": {
            "exactness_status": "exact",
            "hemogram_bundling_savings": 10.0,
            "flagged_tests": [
                {"test_name": f"Brief-{i}", "flag_type": "hemogram_unbundling", "savings_try": i}
                for i in range(8)
            ],
            "rule_source": "EK-2B",
        },
        "copay": {"exactness_status": "missing_exact_inputs"},
        "billing_strategy": {"exactness_status": "exact", "rule_source": "EK-2C"},
        "materials": {"exactness_status": "partial_exact", "rule_source": "EK-3"},
        "total_recoverable_try": 15.0,
        "action_count": 1,
        "priority": "low",
        "exactness_status": "partial_exact",
    }

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "get_optimization_summary",
        lambda: {"copay_exemptions": {}, "surcharge_exposure": {}},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_bilun_patient_outcome",
        lambda patient_id: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "_get_patient_optimization_for_chat",
        lambda patient_id: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_billing_report",
        lambda patient_id: full_report,
    )

    async def fake_stream(messages, runtime_context="", intent="user_question", **kwargs):
        captured["intent"] = intent
        captured["runtime_context"] = runtime_context
        yield "brief"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream)

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "[SUT Billing Review]\n\nBrief me."}],
                "patient_id": "P-001",
                "active_tab": "SUT Billing Review",
                "intent": "auto_brief",
                "user_role": "billing_officer",
            },
        )

    assert response.status_code == 200
    assert captured["intent"] == "auto_brief"
    runtime_context = str(captured["runtime_context"])
    assert "BILLING OPTIMIZATION (FULL)" not in runtime_context
    assert "Brief-7" not in runtime_context


def test_get_patient_optimization_for_chat_uses_alert_cache(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod

    monkeypatch.setattr(sut_chat_mod, "get_pipeline_mode", lambda: "persistent")
    monkeypatch.setattr(sut_chat_mod, "_get_cache_reader", lambda: object())
    monkeypatch.setattr(
        sut_chat_mod,
        "_get_active_build_id_or_none",
        lambda _reader, scope="bilun": "build-1",
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "read_patient_alert_row_by_id",
        lambda _reader, _build, patient_id: {
            "patient_id": patient_id,
            "n_diagnoses": 2,
            "icd10_chapters": ["I"],
            "copay_exemption": {
                "exempt": True,
                "n_qualifying": 1,
                "qualifying_diagnoses": [{"disease": "HTN", "range": "I10-I15"}],
            },
            "surcharge_exposure": {"n_applicable": 3, "exposure_rate": 0.2, "top_rules": []},
            "copay_rate_exposure": {"n_applicable": 2, "mean_rate": 0.15, "top_procedures": []},
        },
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "read_patient_alerts_summary",
        lambda _reader, _build: {
            "surcharge_exactness_status": "exact",
            "copay_rate_exactness_status": "exact",
        },
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_optimization",
        lambda _patient_id: (_ for _ in ()).throw(AssertionError("should not recompute")),
    )

    payload = sut_chat_mod._get_patient_optimization_for_chat("P-001")

    assert payload["patient_id"] == "P-001"
    assert payload["copay_exemptions"]["exempt"] is True
    assert payload["surcharge_exposure"]["exactness_status"] == "exact"


def test_sut_chat_stream_start_precedes_tokens(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "_fetch_runtime_data",
        lambda *_args, **_kwargs: {"optimization_summary": {"status": "ready", "summary": {}}},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "build_bilun_runtime_context",
        lambda *_args, **_kwargs: "ctx",
    )

    async def slow_stream(*_args, **_kwargs):
        await asyncio.sleep(0.05)
        yield "hi"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", slow_stream)

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "patient_id": "P-001",
                "active_tab": "SUT Patient Workspace",
            },
        ) as response:
            assert response.status_code == 200
            first_chunk = next(response.iter_bytes())
            assert b"stream-start" in first_chunk


def test_removed_estimate_native_sut_routes_return_404():
    from src.bilun.api import app

    with TestClient(app) as client:
        assert client.get("/api/sut/drg-pricing").status_code == 404
        assert client.get("/api/sut/exposure-summary").status_code == 404
        assert client.post(
            "/api/sut/copay-simulate",
            json={
                "facility_tier": "devlet",
                "patient_category": "normal",
                "n_visits": 1,
                "n_prescriptions": 1,
                "rx_cost": 10.0,
            },
        ).status_code == 404


def test_sut_chat_rule_database_context_requires_verified_developer(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app
    from src.bilun.api.auth import COOKIE_NAME, issue_session_token

    monkeypatch.setenv("BILUN_AUTH_USERNAME", "test_developer")
    monkeypatch.setenv("BILUN_AUTH_PASSWORD", "test-only-unused-password-hash")
    monkeypatch.setenv("BILUN_SESSION_SECRET", "test-only-chat-session-secret")
    monkeypatch.setenv("BILUN_DEV_USERNAMES", "test_developer")
    token = issue_session_token("test_developer")

    captured: dict[str, object] = {}

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "get_rule_catalog",
        lambda: {
            "total": 47,
            "artifacts_available": True,
            "coverage_summary": {
                "clauses": {
                    "total_extracted": 3250,
                    "numbered_clause_count": 3250,
                    "algorithmic_gaps": 622,
                    "algorithmic_gap_pct": 19.1,
                    "clause_type_breakdown": {"fikra": 2800, "bent": 450, "prose": 0, "section_heading": 50},
                    "top_gap_categories": [
                        {"category": "drug_indication", "count": 230},
                        {"category": "payment_method", "count": 73},
                    ],
                },
                "registry": {
                    "total_rules": 47,
                    "implemented_rules": 37,
                    "partial_rules": 4,
                    "missing_rules": 0,
                    "needs_claim_lines_rules": 0,
                    "non_algorithmic_rules": 6,
                },
            },
            "fact_check": {
                "total_units": 28,
                "compliant": 26,
                "partial": 2,
                "heuristic": 0,
            },
        },
    )

    async def fake_stream_chat_response(
        messages, runtime_context="", extra_params=None, intent="user_question", **kwargs
    ):
        captured["messages"] = messages
        captured["runtime_context"] = runtime_context
        yield "Kural veritabanı "
        yield "özeti."

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream_chat_response)

    with TestClient(app) as client:
        client.cookies.set(COOKIE_NAME, token)
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "SUT kurallarını özetle"}],
                "patient_id": None,
                "active_tab": "rule-database",
                "intent": "auto_brief",
            },
        )

    assert response.status_code == 200
    runtime_context = str(captured["runtime_context"])
    assert "SUT RULE DATABASE & CLAUSE COVERAGE" in runtime_context
    assert "Registered rule engines: 47" in runtime_context
    assert "Algorithmic gaps: 622" in runtime_context
    assert "drug_indication" in runtime_context
    # Patient cohort context should NOT be present
    assert "COHORT OPTIMIZATION" not in runtime_context
