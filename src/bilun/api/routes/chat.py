"""BILUN streaming chatbot endpoint."""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.bilun.shared.exceptions import RateLimitError
from src.bilun.shared.state import _chat_rate_lock as _rate_lock, _chat_rate_window as _rate_window
from src.bilun.chatbot import stream_chat_response

import time as _time

# Rate limiter constants
RATE_LIMIT = 15  # max requests per window
RATE_WINDOW_SEC = 60  # window size in seconds


def _prune_rate_windows(now: float) -> None:
    stale_ips = []
    for ip, window in list(_rate_window.items()):
        fresh = [t for t in window if now - t < RATE_WINDOW_SEC]
        if fresh:
            _rate_window[ip] = fresh
        else:
            stale_ips.append(ip)
    for ip in stale_ips:
        _rate_window.pop(ip, None)


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = _time.time()
    with _rate_lock:
        _prune_rate_windows(now)
        _rate_window.setdefault(client_ip, [])
        if len(_rate_window[client_ip]) >= RATE_LIMIT:
            return False
        _rate_window[client_ip].append(now)
    return True


def _encode_sse(kind: str, payload: str) -> str:
    data = f"data: {json.dumps(payload)}\n"
    if kind == "data":
        return f"{data}\n"
    return f"event: {kind}\n{data}\n"

from .optimization import get_optimization_summary, get_patient_optimization
from .patients import get_bilun_patient_outcome

router = APIRouter()


class BilunChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class BilunChatRequest(BaseModel):
    messages: list[BilunChatMessage] = Field(default_factory=list)
    active_tab: str = "BILUN Analytics"
    patient_id: str | None = None


def _summarize_optimization(payload: dict[str, Any]) -> dict[str, Any]:
    copay = payload.get("copay_exemptions", {})
    surcharge = payload.get("surcharge_exposure", {})
    copay_rate = payload.get("copay_rate_exposure", {})
    drg = payload.get("drg_unbundling", {})
    drugs = payload.get("drug_discount_validation", {})
    return {
        "copay_exemptions": {
            "n_exempt_patients": copay.get("n_exempt_patients"),
            "n_total_patients": copay.get("n_total_patients"),
            "exemption_rate": copay.get("exemption_rate"),
        },
        "surcharge_exposure": {
            "exactness_status": surcharge.get("exactness_status"),
            "unavailable_reason": surcharge.get("unavailable_reason"),
            "required_inputs_missing": surcharge.get("required_inputs_missing"),
        },
        "copay_rate_exposure": {
            "exactness_status": copay_rate.get("exactness_status"),
            "unavailable_reason": copay_rate.get("unavailable_reason"),
            "required_inputs_missing": copay_rate.get("required_inputs_missing"),
        },
        "drg_unbundling": {
            "exactness_status": drg.get("exactness_status"),
            "unavailable_reason": drg.get("unavailable_reason"),
            "required_inputs_missing": drg.get("required_inputs_missing"),
        },
        "drug_discount_validation": {
            "exactness_status": drugs.get("exactness_status"),
            "unavailable_reason": drugs.get("unavailable_reason"),
            "required_inputs_missing": drugs.get("required_inputs_missing"),
        },
    }


def _summarize_patient_outcome(payload: dict[str, Any]) -> dict[str, Any]:
    drg = payload.get("drg_summary") or {}
    expensive = payload.get("expensive_analytics") or {}
    return {
        "patient_id": payload.get("patient_id"),
        "drg_summary": {
            "pricing_status": drg.get("pricing_status"),
            "unavailable_reason": drg.get("unavailable_reason"),
            "required_inputs_missing": drg.get("required_inputs_missing"),
            "n_episodes": drg.get("n_episodes"),
            "total_drg_package_price": drg.get("total_drg_package_price"),
        },
        "expensive_analytics": {
            "state": expensive.get("state"),
            "included": expensive.get("included"),
        },
    }


def _summarize_patient_optimization(payload: dict[str, Any]) -> dict[str, Any]:
    copay = payload.get("copay_exemptions", {})
    surcharge = payload.get("surcharge_exposure", {})
    copay_rate = payload.get("copay_rate_exposure", {})
    drg = payload.get("drg_unbundling", {})
    return {
        "patient_id": payload.get("patient_id"),
        "n_diagnoses": payload.get("n_diagnoses"),
        "icd10_chapters": payload.get("icd10_chapters"),
        "copay_exemptions": {
            "exempt": copay.get("exempt"),
            "n_qualifying": copay.get("n_qualifying"),
            "qualifying_diagnoses": copay.get("qualifying_diagnoses"),
        },
        "surcharge_exposure": {
            "exactness_status": surcharge.get("exactness_status"),
            "unavailable_reason": surcharge.get("unavailable_reason"),
            "required_inputs_missing": surcharge.get("required_inputs_missing"),
            "n_applicable_procedures": surcharge.get("n_applicable_procedures"),
        },
        "copay_rate_exposure": {
            "exactness_status": copay_rate.get("exactness_status"),
            "unavailable_reason": copay_rate.get("unavailable_reason"),
            "required_inputs_missing": copay_rate.get("required_inputs_missing"),
            "mean_rate": copay_rate.get("mean_rate"),
        },
        "drg_unbundling": {
            "exactness_status": drg.get("exactness_status"),
            "unavailable_reason": drg.get("unavailable_reason"),
            "required_inputs_missing": drg.get("required_inputs_missing"),
            "has_unbundling_risk": drg.get("has_unbundling_risk"),
        },
    }


def _safe_context_block(label: str, builder) -> dict[str, Any]:
    try:
        return {"status": "ready", "summary": builder()}
    except Exception as exc:  # pragma: no cover - defensive context assembly
        return {"status": "unavailable", "detail": f"{label} unavailable: {exc}"}


def _build_bilun_runtime_context(active_tab: str, patient_id: str | None) -> str:
    context: dict[str, Any] = {
        "product": "BILUN",
        "active_tab": active_tab,
        "assistant_rules": [
            "Answer only from BILUN financial, reimbursement, optimization, and patient-workspace context.",
            "If an exactness or pricing status is not exact, describe that surface as unavailable instead of inventing zero, clear, or low-risk values.",
            "Do not rely on IHP-only risk, causal, or trajectory claims.",
        ],
        "optimization_summary": _safe_context_block(
            "Optimization summary",
            lambda: _summarize_optimization(get_optimization_summary()),
        ),
    }
    if patient_id:
        context["patient_outcome"] = _safe_context_block(
            "Patient outcome",
            lambda: _summarize_patient_outcome(
                get_bilun_patient_outcome(patient_id, include_expensive=True)
            ),
        )
        context["patient_optimization"] = _safe_context_block(
            "Patient optimization",
            lambda: _summarize_patient_optimization(get_patient_optimization(patient_id)),
        )
    return (
        "BILUN runtime context for the BILUN assistant.\n"
        "Use this context to answer reimbursement, optimization, and patient financial workspace questions.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


@router.post(
    "/chat",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": (
                "Server-sent events stream of BILUN chat tokens. Each frame is "
                "`data: <json-token>\\n\\n`. Stream ends with `data: [DONE]`."
            ),
        },
    },
)
async def bilun_chat(req: BilunChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise RateLimitError("Too many requests. Please wait a moment.")

    runtime_context = await asyncio.to_thread(
        _build_bilun_runtime_context,
        req.active_tab,
        req.patient_id,
    )

    async def sse_generator():
        queue: asyncio.Queue = asyncio.Queue()

        async def _producer():
            try:
                async for token in stream_chat_response(
                    [message.model_dump() for message in req.messages],
                    runtime_context,
                    extra_params={"reasoning": {"effort": "none"}},
                ):
                    await queue.put(("data", token))
            except asyncio.CancelledError:
                return
            except Exception as exc:
                await queue.put(("error", f"BILUN chat stream failed: {exc}"))
            finally:
                await queue.put(None)

        task = asyncio.create_task(_producer())
        yield ": stream-start\n\n"

        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if item is None:
                    break
                kind, payload = item
                yield _encode_sse(kind, payload)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            yield _encode_sse("data", "[DONE]")

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
