"""Deterministic public chat quota and cancellation tests; no model requests."""

import asyncio
import json
import sqlite3
import threading

import pytest
from starlette.requests import Request

from src.bilun.chatbot import public_limits as limits
from src.bilun.shared.exceptions import RateLimitError, ServiceUnavailableError

pytestmark = pytest.mark.unit


def request(client="192.0.2.1", forwarded="203.0.113.9"):
    return Request({"type": "http", "client": (client, 123), "headers": [(b"x-forwarded-for", forwarded.encode())]})


@pytest.fixture
def ledger(monkeypatch, tmp_path):
    path = tmp_path / "budget.sqlite3"
    monkeypatch.setenv("BILUN_PUBLIC_BILLING_ENABLED", "1")
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_DAILY_TOKEN_BUDGET", "1000000")
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_BUDGET_DB", str(path))
    return path


def test_public_admission_fails_closed_without_explicit_budget(monkeypatch):
    monkeypatch.setenv("BILUN_PUBLIC_BILLING_ENABLED", "1")
    monkeypatch.delenv("BILUN_PUBLIC_CHAT_DAILY_TOKEN_BUDGET", raising=False)
    monkeypatch.delenv("BILUN_PUBLIC_CHAT_BUDGET_DB", raising=False)
    with pytest.raises(ServiceUnavailableError):
        limits.admit_public_chat(request(), user_role="billing_officer")
    assert limits.admit_public_chat(request(), user_role="dev") is None


def test_client_forwarding_headers_cannot_choose_quota_bucket(ledger):
    first = limits.admit_public_chat(request(), user_role="billing_officer")
    second = limits.admit_public_chat(request(forwarded="198.51.100.1"), user_role="billing_officer")
    with pytest.raises(RateLimitError):
        limits.admit_public_chat(request(forwarded="198.51.100.2"), user_role="billing_officer")
    first.release()
    second.release()
    third = limits.admit_public_chat(request(), user_role="billing_officer")
    third.release()


def test_global_admission_and_per_minute_counts_survive_new_instances(ledger):
    leases = [limits.admit_public_chat(request(f"192.0.2.{n}"), user_role="billing_officer") for n in range(4)]
    with pytest.raises(RateLimitError):
        limits.admit_public_chat(request("192.0.2.99"), user_role="billing_officer")
    for lease in leases:
        lease.release()
    for _ in range(limits.PUBLIC_REQUESTS_PER_MINUTE):
        lease = limits.admit_public_chat(request("192.0.2.99"), user_role="billing_officer")
        lease.release()
    with pytest.raises(RateLimitError):
        limits.admit_public_chat(request("192.0.2.99"), user_role="billing_officer")


def test_provider_allowance_is_reserved_before_use_and_never_refunded(ledger, monkeypatch):
    payload = {"messages": [{"role": "user", "content": "Synthetic question"}], "max_tokens": 10}
    cost = len(json.dumps(payload, ensure_ascii=False).encode()) + 10
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_DAILY_TOKEN_BUDGET", str(cost))
    lease = limits.admit_public_chat(request(), user_role="billing_officer")
    assert lease.reserve(payload) == payload
    lease.release()  # failed/disconnected requests must still consume allowance
    with sqlite3.connect(ledger) as connection:
        assert connection.execute("SELECT reserved FROM usage").fetchone() == (cost,)
    with pytest.raises(RateLimitError):
        limits.admit_public_chat(request("192.0.2.2"), user_role="billing_officer")


def test_budget_reservation_is_atomic_across_independent_leases(ledger, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    payload = {"max_tokens": 10}
    cost = len(json.dumps(payload).encode()) + 10
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_DAILY_TOKEN_BUDGET", str(cost))
    a = limits.admit_public_chat(request(), user_role="billing_officer")
    b = limits.admit_public_chat(request("192.0.2.2"), user_role="billing_officer")
    def reserve(lease):
        try:
            lease.reserve(payload)
            return True
        except RateLimitError:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(reserve, [a, b])) == [False, True]
    a.release()
    b.release()


def test_public_call_and_payload_limits_are_hard_caps(ledger):
    lease = limits.admit_public_chat(request(), user_role="billing_officer")
    with pytest.raises(RateLimitError):
        lease.reserve({"messages": [{"content": "x" * limits.PUBLIC_MAX_PROVIDER_BYTES}]})
    assert lease.calls == 0
    for _ in range(limits.PUBLIC_MAX_PROVIDER_CALLS):
        assert lease.reserve({"max_tokens": 999999})["max_tokens"] == limits.PUBLIC_MAX_OUTPUT_TOKENS
    with pytest.raises(RateLimitError):
        lease.reserve({"max_tokens": 1})
    lease.release()


def test_timed_out_worker_holds_slot_until_real_execution_finishes(monkeypatch):
    monkeypatch.setattr(limits, "_work_slots", threading.BoundedSemaphore(1))
    started = threading.Event()
    finish = threading.Event()
    def slow():
        started.set()
        finish.wait(2)
    async def run():
        try:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(limits.bounded_chat_work(slow), 0.05)
            assert started.is_set()
            with pytest.raises(RateLimitError):
                await limits.bounded_chat_work(lambda: "new work")
        finally:
            finish.set()
    asyncio.run(run())


def test_cancelled_stream_releases_lease_and_model_context(ledger):
    lease = limits.admit_public_chat(request(), user_role="billing_officer")
    closed = []
    async def producer():
        try:
            yield ("data", "hello")
            await asyncio.sleep(60)
        finally:
            closed.append(True)
    async def run():
        stream = limits.public_chat_stream(producer, lease)
        assert await anext(stream) == ("data", "hello")
        await stream.aclose()
        assert limits._budget.get() is None
        assert closed == [True]
    asyncio.run(run())
    with sqlite3.connect(ledger) as connection:
        assert connection.execute("SELECT active FROM requests").fetchone() == (0,)


def test_every_provider_transport_reserves_budget_before_network(ledger, monkeypatch):
    from src.bilun.chatbot import llm

    sent = []
    class Response:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "Synthetic answer"}}]}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"Synthetic answer"}}]}'
            yield 'data: [DONE]'
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            sent.append(kwargs["json"])
            return Response()
        def stream(self, *args, **kwargs):
            sent.append(kwargs["json"])
            return Response()
    monkeypatch.setattr(llm.httpx, "AsyncClient", Client)
    monkeypatch.setattr(llm, "_get_api_key", lambda: "synthetic-test-key")
    monkeypatch.setattr(llm, "get_chat_model_context", lambda: {})
    lease = limits.admit_public_chat(request(), user_role="billing_officer")
    async def run():
        token = limits._budget.set(lease)
        try:
            await llm._call_llm_non_streaming({"max_tokens": 4096, "messages": []})
            assert [item async for item in llm._stream_text_from_llm({"max_tokens": 4096, "messages": []})]
            assert [item async for item in llm.stream_chat_response([{"role": "user", "content": "Synthetic question"}])]
        finally:
            limits._budget.reset(token)
            lease.release()
    asyncio.run(run())
    assert lease.calls == len(sent) == 3
    assert all(payload["max_tokens"] == 2048 for payload in sent)
    expected = sum(len(json.dumps(payload, ensure_ascii=False).encode()) + 2048 for payload in sent)
    with sqlite3.connect(ledger) as connection:
        assert connection.execute("SELECT reserved FROM usage").fetchone() == (expected,)
