"""BILUN tool registry — LLM-callable read-only endpoint tools.

Safety-first architecture:
- Allowlist: only explicitly registered endpoints are callable
- JSON schema validation on all arguments before execution
- Circuit breaker: 3 consecutive errors disables the tool for the conversation
- Per-call timeout: 5 seconds max per tool execution
- Response size cap: 8KB to prevent context window overflow
- Audit log: every tool call is logged
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("bilun.chatbot.tools")

# ── Tool schema definitions (OpenAI function-calling format) ──────────────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_billing_report",
            "description": (
                "Get a patient's billing action report with TRY-denominated"
                " savings recommendations across 4 billing algorithms: lab"
                " hemogram bundling, copay savings,"
                " billing strategy (package vs itemized), and material"
                " pre-check. Returns total_recoverable_try, priority, and"
                " exactness_status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient ID (e.g., SENTETIK-HASTA-0039)",
                    },
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_revenue_recovery",
            "description": (
                "Get cohort-level revenue recovery summary. Returns total"
                " savings across lab, copay, and strategy categories,"
                " plus top patients ranked by recoverable amount and"
                " priority distribution."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_optimization",
            "description": (
                "Get a patient's optimization findings: copay exemptions,"
                " surcharge exposure, copay rate exposure, and DRG"
                " unbundling risk. Each surface reports exactness_status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient ID to look up",
                    },
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_optimization_summary",
            "description": (
                "Get cohort-level SUT optimization summary: copay exemption"
                " rates, surcharge exposure, copay rate exposure, DRG"
                " unbundling flags, and temporal"
                " price audit findings."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_patients",
            "description": (
                "Search BILUN patients by name or ID prefix. Returns"
                " matching patient IDs with metadata."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Search query — patient name or ID prefix",
                    },
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_patients",
            "description": (
                "List all patients in the BILUN cohort. Returns patient"
                " IDs with metadata."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_drugs",
            "description": (
                "Search the EK-4A drug reimbursement catalog. Find drug"
                " names, equivalence groups, discount tiers, and passivation"
                " status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Drug name or active ingredient to search for",
                    },
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_sut_clauses",
            "description": (
                "Search the official SUT (Sağlık Uygulama Tebliği) regulatory"
                " text for clauses relevant to a free-text question. Use this"
                " for any question about what the SUT rules SAY — coverage,"
                " conditions, copay, surcharge, materials, procedures, annex"
                " (EK) references, sections (§). Returns non-superseded clauses"
                " with section_id, annex_refs, and source_effective_date for"
                " citation. Answer only from returned clauses; cite them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "The SUT question or topic in Turkish (e.g."
                            " 'yoğun bakım ilave ücret', 'EK-2/C katılım payı')."
                        ),
                    },
                    "annex": {
                        "type": "string",
                        "description": (
                            "Optional annex filter, e.g. 'EK-2/C', 'EK-1/A'."
                        ),
                    },
                    "section_prefix": {
                        "type": "string",
                        "description": (
                            "Optional SUT section filter, e.g. '3.1', '1.8.5'."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_alerts",
            "description": (
                "Get SUT alerts for patients: exemptions, surcharge"
                " exposure, copay rate exposure. Filterable by category"
                " and status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": (
                            "Alert category filter — one of: exemptions,"
                            " surcharge, copay_rates. Omit for exemptions (default)."
                        ),
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_medula_playbook",
            "description": (
                "Search the MEDULA rejection playbook. Use when the user asks"
                " about a MEDULA sonuç kodu, rejection message, or corrective"
                " rebill steps. Returns matched playbook templates with SUT"
                " anchor, problem summary, and corrective steps."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "The MEDULA rejection message, sonuç kodu, or"
                            " free-text question in Turkish."
                        ),
                    },
                    "sonuc_kodu": {
                        "type": "string",
                        "description": (
                            "Optional numeric MEDULA sonuç kodu, e.g. '1688'."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
]

# ── Endpoint allowlist — maps tool name to executor ───────────────────────────

_TOOL_FUNCTION_MAP: dict[str, str] = {
    "get_billing_report": "get_patient_billing_report",
    "get_revenue_recovery": "get_revenue_recovery",
    "get_patient_optimization": "get_patient_optimization",
    "get_optimization_summary": "get_optimization_summary",
    "search_patients": "search_bilun_patients",
    "list_patients": "get_bilun_patients",
    "search_drugs": "get_drug_catalog",
    "get_patient_alerts": "get_patient_alerts",
    "search_sut_clauses": "search_sut_clauses",
    "search_medula_playbook": "search_medula_playbook_entries",
}

RESPONSE_SIZE_CAP = 8192  # 8KB
TOOL_TIMEOUT_SEC = 5.0
MAX_TOOL_CALLS_PER_TURN = 3
CIRCUIT_BREAKER_THRESHOLD = 3

# Map legacy/alternate LLM category labels to API values (alerts.py).
_ALERT_CATEGORY_ALIASES: dict[str, str] = {
    "exemptions": "exemptions",
    "exemption": "exemptions",
    "surcharge": "surcharge",
    "surcharge-exposure": "surcharge",
    "surcharge_exposure": "surcharge",
    "copay_rates": "copay_rates",
    "copay-rates": "copay_rates",
    "copay-rate": "copay_rates",
    "copay_rate": "copay_rates",
    "copay-rates-exposure": "copay_rates",
}


def _normalize_alert_category(raw: str | None) -> str:
    normalized = (raw or "exemptions").strip().lower()
    return _ALERT_CATEGORY_ALIASES.get(normalized, normalized)


@dataclass
class ToolCallResult:
    tool_name: str
    arguments: dict[str, Any]
    success: bool
    content: str = ""
    error: str | None = None
    elapsed_ms: float = 0.0


@dataclass
class ToolSession:
    call_count: int = 0
    consecutive_errors: dict[str, int] = field(default_factory=dict)
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def is_circuit_open(self, tool_name: str) -> bool:
        return self.consecutive_errors.get(tool_name, 0) >= CIRCUIT_BREAKER_THRESHOLD

    def record_result(self, result: ToolCallResult) -> None:
        entry = {
            "tool": result.tool_name,
            "args": result.arguments,
            "success": result.success,
            "elapsed_ms": result.elapsed_ms,
            "error": result.error,
            "content_len": len(result.content),
            "timestamp": time.time(),
        }
        self.audit_log.append(entry)
        if result.success:
            self.consecutive_errors[result.tool_name] = 0
        else:
            current = self.consecutive_errors.get(result.tool_name, 0)
            self.consecutive_errors[result.tool_name] = current + 1


def _serialize_for_llm(obj: Any) -> str:
    """Serialize a Python value to a JSON string safe for LLM context."""
    if isinstance(obj, (dict, list)):
        raw = json.dumps(obj, ensure_ascii=False, default=str)
    elif isinstance(obj, (int, float, bool, str)):
        raw = json.dumps(obj, ensure_ascii=False)
    else:
        raw = json.dumps(str(obj), ensure_ascii=False)
    if len(raw) > RESPONSE_SIZE_CAP:
        truncated = raw[:RESPONSE_SIZE_CAP]
        truncated += f"\n... [truncated at {RESPONSE_SIZE_CAP} bytes, original was {len(raw)} bytes]"
        return truncated
    return raw


def _validate_arguments(tool_name: str, arguments: dict[str, Any]) -> None:
    """Validate tool arguments against the schema. Raises ValueError on mismatch."""
    schema = None
    for tool in TOOL_SCHEMAS:
        if tool["function"]["name"] == tool_name:
            schema = tool["function"]["parameters"]
            break
    if schema is None:
        raise ValueError(f"Unknown tool: {tool_name}")

    required: list[str] = schema.get("required", [])
    properties: dict[str, Any] = schema.get("properties", {})

    for param in required:
        if param not in arguments or arguments[param] is None:
            raise ValueError(
                f"Missing required parameter '{param}' for tool '{tool_name}'"
            )

    for key, value in arguments.items():
        if key not in properties:
            raise ValueError(
                f"Unknown parameter '{key}' for tool '{tool_name}'"
            )
        expected_type = properties[key].get("type", "string")
        if expected_type == "string" and not isinstance(value, str):
            raise ValueError(
                f"Parameter '{key}' must be a string for tool '{tool_name}'"
            )
        if expected_type == "number" and not isinstance(value, (int, float)):
            raise ValueError(
                f"Parameter '{key}' must be a number for tool '{tool_name}'"
            )


async def execute_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    session: ToolSession | None = None,
) -> ToolCallResult:
    """Execute a single tool call with validation, timeout, and tracking."""
    if session is None:
        session = ToolSession()

    t0 = time.perf_counter()

    if tool_name not in _TOOL_FUNCTION_MAP:
        result = ToolCallResult(
            tool_name=tool_name,
            arguments=arguments,
            success=False,
            content="",
            elapsed_ms=0.0,
            error=f"Tool '{tool_name}' is not in the allowlist. Available tools: {list(_TOOL_FUNCTION_MAP.keys())}",
        )
        session.record_result(result)
        return result

    try:
        _validate_arguments(tool_name, arguments)
    except ValueError as exc:
        result = ToolCallResult(
            tool_name=tool_name,
            arguments=arguments,
            success=False,
            elapsed_ms=(time.perf_counter() - t0) * 1000,
            error=str(exc),
        )
        session.record_result(result)
        return result

    if session.is_circuit_open(tool_name):
        result = ToolCallResult(
            tool_name=tool_name,
            arguments=arguments,
            success=False,
            elapsed_ms=0.0,
            error=f"Circuit breaker open for tool '{tool_name}' — {CIRCUIT_BREAKER_THRESHOLD} consecutive failures.",
        )
        session.record_result(result)
        return result

    content = ""
    error: str | None = None

    try:
        func_name = _TOOL_FUNCTION_MAP[tool_name]

        def _exec() -> str:
            from src.bilun.api.routes.billing import (
                get_drug_catalog,
                get_patient_billing_report,
            )
            from src.bilun.api.routes.alerts import get_patient_alerts
            from src.bilun.api.routes.optimization import (
                get_optimization_summary,
                get_patient_optimization,
                get_revenue_recovery,
            )
            from src.bilun.api.routes.patients import (
                get_bilun_patients,
                search_bilun_patients,
            )
            from src.bilun.domain.sut.clause_retrieval import search_clauses
            from src.bilun.chatbot.medula_kb import search_playbook_entries

            namespace = {
                "get_patient_billing_report": lambda: get_patient_billing_report(
                    arguments["patient_id"]
                ),
                "get_revenue_recovery": get_revenue_recovery,
                "get_patient_optimization": lambda: get_patient_optimization(
                    arguments["patient_id"]
                ),
                "get_optimization_summary": get_optimization_summary,
                "search_bilun_patients": lambda: search_bilun_patients(
                    arguments["q"], limit=20
                ),
                "get_bilun_patients": get_bilun_patients,
                "get_drug_catalog": lambda: get_drug_catalog(
                    arguments.get("q", ""), page=1, per_page=20
                ),
                "get_patient_alerts": lambda: get_patient_alerts(
                    category=_normalize_alert_category(arguments.get("category")),
                    status="all",
                    limit=100,
                    offset=0,
                ),
                "search_sut_clauses": lambda: {
                    "query": arguments["query"],
                    "clauses": search_clauses(
                        arguments["query"],
                        top_k=5,
                        annex=arguments.get("annex"),
                        section_prefix=arguments.get("section_prefix"),
                    ),
                },
                "search_medula_playbook_entries": lambda: search_playbook_entries(
                    arguments["query"],
                    sonuc_kodu=arguments.get("sonuc_kodu"),
                    top_n=5,
                ),
            }
            func = namespace.get(func_name)
            if func is None:
                raise ValueError(f"Executor not found for tool '{tool_name}'")
            result = func()
            return _serialize_for_llm(result)

        content = await asyncio.wait_for(
            asyncio.to_thread(_exec), timeout=TOOL_TIMEOUT_SEC
        )
    except asyncio.TimeoutError:
        error = f"Tool '{tool_name}' timed out after {TOOL_TIMEOUT_SEC}s"
    except Exception as exc:
        error = f"Tool '{tool_name}' execution failed: {exc}"
        logger.warning("Tool execution error | tool=%s | error=%s", tool_name, exc)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    success = error is None

    result = ToolCallResult(
        tool_name=tool_name,
        arguments=arguments,
        success=success,
        content=content,
        error=error,
        elapsed_ms=elapsed_ms,
    )
    session.record_result(result)
    logger.info(
        "TOOL CALL | tool=%s | success=%s | elapsed_ms=%.0f | content_len=%d",
        tool_name,
        success,
        elapsed_ms,
        len(content),
    )
    return result


def get_tool_schemas() -> list[dict[str, Any]]:
    """Return the full list of tool schemas for the LLM request."""
    return TOOL_SCHEMAS
