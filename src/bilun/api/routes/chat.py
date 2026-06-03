"""BILUN streaming chatbot endpoint."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.bilun.shared.exceptions import RateLimitError
from src.bilun.shared.state import _chat_rate_lock as _rate_lock, _chat_rate_window as _rate_window
from src.bilun.chatbot import stream_chat_response
from src.bilun.chatbot.context import build_bilun_runtime_context
from src.bilun.chatbot.llm import stream_chat_response_with_tools
from src.bilun.chatbot.prompts import ChatIntent

logger = logging.getLogger("bilun.api.chat")

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
    now = time.time()
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
from .billing import get_patient_billing_report

from src.bilun.chatbot.medula_kb import search_medula
from src.bilun.db import read_patient_alert_row_by_id, read_patient_alerts_summary
from src.bilun.domain.optimization.exactness import (
    EXACTNESS_STATUS_EXACT,
    is_exact_output,
    unavailable_patient_alert_copay_rate,
    unavailable_patient_alert_surcharge,
    unavailable_patient_drg_unbundling,
)
from src.bilun.shared.state import (
    _get_active_build_id_or_none,
    _get_cache_reader,
    get_pipeline_mode,
)

router = APIRouter()


class BilunChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class BilunChatRequest(BaseModel):
    messages: list[BilunChatMessage] = Field(default_factory=list)
    active_tab: str = "BILUN Analytics"
    patient_id: str | None = None
    intent: ChatIntent = "user_question"
    page_context: dict[str, Any] | None = None


# ── Summarizers (keep in chat.py — they depend on route imports) ──────────────


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


def _summarize_billing_report(payload: dict[str, Any]) -> dict[str, Any]:
    lab = payload.get("lab", {}) or {}
    drug = payload.get("drug", {}) or {}
    copay = payload.get("copay", {}) or {}
    strategy = payload.get("billing_strategy", {}) or {}
    materials = payload.get("materials", {}) or {}
    summary_cap = 5
    return {
        "patient_id": payload.get("patient_id"),
        "lab": {
            "exactness_status": lab.get("exactness_status"),
            "hemogram_bundling_savings": lab.get("hemogram_bundling_savings"),
            "duplicate_test_savings": lab.get("duplicate_test_savings"),
            "total_savings": lab.get("total_savings"),
            "flagged_tests": (lab.get("flagged_tests") or [])[:summary_cap],
            "rule_source": lab.get("rule_source", "EK-2B hemogram bundling, duplicate test rules"),
        },
        "drug": {
            "exactness_status": drug.get("exactness_status"),
            "n_generics_available": drug.get("n_generics_available"),
            "passivated_drug_count": drug.get("passivated_drug_count"),
            "generic_substitution_savings": drug.get("generic_substitution_savings"),
            "drug_recommendations": (drug.get("drug_recommendations") or [])[:summary_cap],
            "rule_source": drug.get("rule_source", "EK-4A drug equivalence groups"),
        },
        "copay": {
            "exactness_status": copay.get("exactness_status"),
            "is_exempt": copay.get("is_exempt"),
            "exemption_disease": copay.get("exemption_disease"),
            "total_copay_savings_try": copay.get("total_copay_savings_try"),
            "rate_corrections": (copay.get("rate_corrections") or [])[:summary_cap],
            "rule_source": copay.get("rule_source", "EK-1A chronic disease copay exemptions"),
        },
        "billing_strategy": {
            "exactness_status": strategy.get("exactness_status"),
            "recommendations": (strategy.get("recommendations") or [])[:summary_cap],
            "rule_source": strategy.get("rule_source", "EK-2C DRG package, EK-2B fee-for-service"),
        },
        "materials": {
            "exactness_status": materials.get("exactness_status"),
            "pre_auth_required": (materials.get("pre_auth_required") or [])[:summary_cap],
            "miat_restricted": (materials.get("miat_restricted") or [])[:summary_cap],
            "miat_interval_violations": (
                materials.get("miat_interval_violations") or []
            )[:summary_cap],
            "bundled_separate_billing": (
                materials.get("bundled_separate_billing") or []
            )[:summary_cap],
            "prose_bundling_violations": (
                materials.get("prose_bundling_violations") or []
            )[:summary_cap],
            "coverage_scope": materials.get("coverage_scope"),
            "rule_source": materials.get(
                "rule_source",
                "EK-3C-1 tıbbi uygunluk, EK-3C-2 MIAT intervals, partial §3.1 prose",
            ),
        },
        "total_recoverable_try": payload.get("total_recoverable_try"),
        "action_count": payload.get("action_count"),
        "priority": payload.get("priority"),
        "exactness_status": payload.get("exactness_status"),
    }


def _safe_context_block(label: str, builder) -> dict[str, Any]:
    try:
        return {"status": "ready", "summary": builder()}
    except Exception as exc:
        return {"status": "unavailable", "detail": f"{label} unavailable: {exc}"}


# ── Data fetching (lives in chat.py — this is the only place that imports   ──
# ── from sibling route modules)                                              ──


def _should_use_chat_tools(
    *,
    patient_id: str | None,
    intent: ChatIntent,
) -> bool:
    """Patient chats pre-fetch all context; tools are only useful on cohort/home views."""
    if intent == "auto_brief":
        return False
    return patient_id is None


def _cached_patient_optimization_payload(patient_id: str) -> dict[str, Any] | None:
    """Read precomputed patient optimization from alert cache (fast path for chat)."""

    mode = get_pipeline_mode()
    if mode not in {"hybrid", "persistent"}:
        return None

    reader = _get_cache_reader()
    active_build = _get_active_build_id_or_none(reader, scope="bilun")
    if not active_build:
        return None

    row = read_patient_alert_row_by_id(reader, active_build, patient_id)
    if row is None:
        return None

    summary = read_patient_alerts_summary(reader, active_build) or {}
    copay_exemption = row.get("copay_exemption") or {}

    if is_exact_output(
        {"exactness_status": summary.get("surcharge_exactness_status")}
    ):
        surcharge_exposure = {
            **dict(row.get("surcharge_exposure") or {}),
            "exactness_status": EXACTNESS_STATUS_EXACT,
        }
    else:
        surcharge_exposure = unavailable_patient_alert_surcharge()

    if is_exact_output(
        {"exactness_status": summary.get("copay_rate_exactness_status")}
    ):
        copay_rate_exposure = {
            **dict(row.get("copay_rate_exposure") or {}),
            "exactness_status": EXACTNESS_STATUS_EXACT,
        }
    else:
        copay_rate_exposure = unavailable_patient_alert_copay_rate()

    return {
        "patient_id": row.get("patient_id"),
        "n_diagnoses": row.get("n_diagnoses"),
        "icd10_chapters": row.get("icd10_chapters"),
        "copay_exemptions": {
            "exempt": copay_exemption.get("exempt"),
            "n_qualifying": copay_exemption.get("n_qualifying"),
            "qualifying_diagnoses": copay_exemption.get("qualifying_diagnoses"),
        },
        "surcharge_exposure": surcharge_exposure,
        "copay_rate_exposure": copay_rate_exposure,
        "drg_unbundling": unavailable_patient_drg_unbundling(),
    }


def _get_patient_optimization_for_chat(patient_id: str) -> dict[str, Any]:
    cached = _cached_patient_optimization_payload(patient_id)
    if cached is not None:
        return cached
    return get_patient_optimization(patient_id)


def _fetch_runtime_data(
    active_tab: str,
    patient_id: str | None,
    user_message: str | None = None,
    *,
    intent: ChatIntent = "user_question",
) -> dict[str, Any]:
    """Fetch all data needed for context assembly (parallel where independent)."""

    def _fetch_optimization_summary() -> dict[str, Any]:
        return _safe_context_block(
            "Optimization summary",
            lambda: _summarize_optimization(get_optimization_summary()),
        )

    def _fetch_patient_outcome() -> dict[str, Any]:
        return _safe_context_block(
            "Patient outcome",
            lambda: _summarize_patient_outcome(
                get_bilun_patient_outcome(patient_id, include_expensive=False)
            ),
        )

    def _fetch_patient_optimization() -> dict[str, Any]:
        return _safe_context_block(
            "Patient optimization",
            lambda: _summarize_patient_optimization(
                _get_patient_optimization_for_chat(patient_id)
            ),
        )

    def _fetch_billing_report() -> dict[str, Any]:
        return _safe_context_block(
            "Billing report",
            lambda: _summarize_billing_report(
                get_patient_billing_report(patient_id)
            ),
        )

    def _fetch_medula_search() -> dict[str, Any]:
        return _safe_context_block(
            "MEDULA knowledge base",
            lambda: search_medula(user_message or ""),
        )

    jobs: dict[str, Any] = {
        "optimization_summary": _fetch_optimization_summary,
    }
    if patient_id:
        jobs["patient_outcome"] = _fetch_patient_outcome
        jobs["patient_optimization"] = _fetch_patient_optimization
        jobs["billing_report"] = _fetch_billing_report
    if user_message:
        jobs["medula_search"] = _fetch_medula_search

    data: dict[str, Any] = {}
    max_workers = min(4, len(jobs))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fn): key for key, fn in jobs.items()}
        for future in futures:
            key = futures[future]
            data[key] = future.result()
    return data


async def _sse_event_stream(
    producer: Any,
) -> Any:
    """Wrap an async producer with immediate stream-start and keepalive comments."""

    queue: asyncio.Queue = asyncio.Queue()

    async def _run_producer() -> None:
        try:
            async for kind, payload in producer():
                await queue.put((kind, payload))
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.exception("Chat SSE producer failed")
            await queue.put(("error", f"BILUN chat stream failed: {exc}"))
        finally:
            await queue.put(None)

    task = asyncio.create_task(_run_producer())
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


# ── Endpoint ─────────────────────────────────────────────────────────────────


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

    user_message: str | None = None
    for msg in reversed(req.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    async def _producer():
        t0 = time.perf_counter()
        raw_data = await asyncio.to_thread(
            _fetch_runtime_data,
            req.active_tab,
            req.patient_id,
            user_message,
            intent=req.intent,
        )
        t_fetch = time.perf_counter()
        runtime_context = build_bilun_runtime_context(
            raw_data,
            req.active_tab,
            req.patient_id,
            page_context=req.page_context,
            intent=req.intent,
            billing_detail="summary",
        )
        use_tools = _should_use_chat_tools(
            patient_id=req.patient_id,
            intent=req.intent,
        )
        logger.info(
            "CHAT PRE-LLM | intent=%s patient=%s fetch_ms=%.0f ctx_ms=%.0f ctx_chars=%d tools=%s",
            req.intent,
            req.patient_id or "-",
            (t_fetch - t0) * 1000,
            (time.perf_counter() - t_fetch) * 1000,
            len(runtime_context),
            use_tools,
        )

        stream_fn = (
            stream_chat_response_with_tools
            if use_tools
            else stream_chat_response
        )
        async for item in stream_fn(
            [message.model_dump() for message in req.messages],
            runtime_context,
            intent=req.intent,
        ):
            if isinstance(item, tuple):
                kind, text = item
                yield (kind, text)
            else:
                yield ("data", item)

    return StreamingResponse(
        _sse_event_stream(_producer),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Weekly Brief ──────────────────────────────────────────────────────────────

WEEKLY_BRIEF_PROMPT = (
    "You are BILUN's weekly revenue recovery analyst. Generate a concise weekly"
    " brief based on the provided cohort data. Structure your response as"
    " follows:\n\n"
    "1. TOP OPPORTUNITY: The single largest recovery category with TRY amount.\n"
    "2. TOTAL RECOVERABLE: Grand total across all categories.\n"
    "3. PRIORITY PATIENTS: Top 3 patients to review, with their recoverable"
    " amounts.\n"
    "4. RISK ALERT: Any exactness gaps or missing data that blocks action.\n"
    "5. RECOMMENDED ACTION: One concrete next step for the billing team.\n\n"
    "Write in natural paragraphs like a colleague on Slack. No markdown, no"
    " bullet points. Use plain Turkish or English based on context. Always cite"
    " exactness_status and rule_source when reporting amounts."
)


class WeeklyBriefRequest(BaseModel):
    language: str = "tr"


@router.post("/weekly-brief")
async def weekly_brief(req: WeeklyBriefRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise RateLimitError("Too many requests. Please wait a moment.")

    messages = [{"role": "user", "content": WEEKLY_BRIEF_PROMPT}]

    async def _producer():
        raw_data = await asyncio.to_thread(
            _fetch_runtime_data,
            "SUT Analytics",
            None,
            intent="auto_brief",
        )
        runtime_context = build_bilun_runtime_context(
            raw_data, "SUT Analytics", None, intent="auto_brief", billing_detail="summary"
        )
        async for item in stream_chat_response(
            messages,
            runtime_context,
            intent="auto_brief",
        ):
            if isinstance(item, tuple):
                kind, text = item
                yield (kind, text)
            else:
                yield ("data", item)

    return StreamingResponse(
        _sse_event_stream(_producer),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
