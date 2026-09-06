"""BILUN tool registry — LLM-callable read-only endpoint tools.

Safety-first architecture:
- Allowlist: only explicitly registered endpoints are callable
- JSON schema validation on all arguments before execution
- Circuit breaker: 3 consecutive errors disables the tool for the conversation
- Per-call timeout: 5 seconds max per tool execution
- Response size cap: 8KB to prevent context window overflow
- Audit log: every tool call is logged
- Dev-only repo tools: read_repo_file, grep_repo (developer role)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger("bilun.chatbot.tools")

UserRole = Literal["dev", "billing_officer"]

# ── Tool schema definitions (OpenAI function-calling format) ──────────────────

_CORE_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_billing_report",
            "description": (
                "Get a patient's billing action report with TRY-denominated"
                " savings and risk recommendations across all 17 billing"
                " analyzers: lab hemogram bundling, copay exemption review,"
                " billing strategy (package vs itemized), session pricing"
                " uplift, DRG itemized-vs-package uplift, blood component"
                " fraction uplift, missing billable material uplift,"
                " procedure add-on uplift, procedure capture gap, DRG/EK-2C"
                " package adequacy review, gazette repricing, MEDULA rejection"
                " playbook, claim submission checklist, drug indication"
                " validation, and material reimbursability pre-check (MIAT,"
                " bundled, specialty, KDV). Also returns total_recoverable_try,"
                " audit_exposure_try (over-billing risk), priority, and"
                " exactness_status. Use this for any per-patient savings,"
                " uplift, or over-billing-risk question."
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
            "name": "get_bill_billing_report",
            "description": (
                "Get a claim-scoped billing action report for one bill (claim_id)."
                " Use when the UI shows a selected bill or page_view.visible_billing"
                " has scope=bill. Returns full KPI fields including"
                " audit_exposure_try, sgk_uplift_try, compliance_adjustment_try,"
                " and per-block detail for that bill only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient ID",
                    },
                    "claim_id": {
                        "type": "string",
                        "description": "The bill / claim ID (e.g. F-SENTETIK-HASTA-0023-048)",
                    },
                },
                "required": ["patient_id", "claim_id"],
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
            "name": "validate_claim",
            "description": (
                "Validate a STORED claim (by patient_id + claim_id) against"
                " BILUN bundling and exclusion rules: EK-3B-1 bundled"
                " consumables, EK-3B-2 exclusions, §3.1 material-bundling"
                " prose, §3.3 specialty prose, and exact EK-3 material"
                " pricing. Returns per-line violations, total savings and"
                " risk (TRY), and priced material lines. Use this to check"
                " whether a claim's materials are reimbursable / correctly"
                " unbundled. Drug-indication sub-checks are not run on"
                " stored claims (prescriber specialty unavailable)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient ID",
                    },
                    "claim_id": {
                        "type": "string",
                        "description": "The bill / claim ID",
                    },
                },
                "required": ["patient_id", "claim_id"],
            },
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
                "Get cohort-level SUT optimization summary across all 6"
                " optimization features: copay exemption rates (EK-1A),"
                " surcharge exposure (EK-2G), copay rate exposure (EK-2C-1),"
                " DRG unbundling flags, temporal price audit findings"
                " (EK-2B/2C history), and drug discount tier validation"
                " (EK-4A). Each feature reports exactness_status."
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

_DEV_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_repo_file",
            "description": (
                "Read a source file from the BILUN repository (developer mode)."
                " Use to explain how billing algorithms, chat context, or SUT"
                " rules are implemented. Cite the path in your answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Repository-relative path, e.g."
                            " src/bilun/domain/billing/claim_audit_exposure.py"
                        ),
                    },
                    "start_line": {
                        "type": "number",
                        "description": "Optional 1-based start line (default 1)",
                    },
                    "end_line": {
                        "type": "number",
                        "description": "Optional 1-based end line (default EOF)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_repo",
            "description": (
                "Search BILUN source files with a regex (developer mode)."
                " Use to locate symbols, fields, or algorithm entry points."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for",
                    },
                    "path_prefix": {
                        "type": "string",
                        "description": (
                            "Allowed repo prefix to search under"
                            " (default src/bilun)"
                        ),
                    },
                    "max_matches": {
                        "type": "number",
                        "description": "Max matches to return (default 30, cap 40)",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
]

# ── Endpoint allowlist — maps tool name to executor ───────────────────────────

_TOOL_FUNCTION_MAP: dict[str, str] = {
    "get_billing_report": "get_patient_billing_report",
    "get_bill_billing_report": "get_bill_billing_report",
    "get_revenue_recovery": "get_revenue_recovery",
    "validate_claim": "validate_stored_claim",
    "get_patient_optimization": "get_patient_optimization",
    "get_optimization_summary": "get_optimization_summary",
    "search_patients": "search_bilun_patients",
    "list_patients": "get_bilun_patients",
    "search_drugs": "get_drug_catalog",
    "get_patient_alerts": "get_patient_alerts",
    "search_sut_clauses": "search_sut_clauses",
    "search_medula_playbook": "search_medula_playbook_entries",
    "read_repo_file": "read_repo_file",
    "grep_repo": "grep_repo",
}

_DEV_TOOL_NAMES = frozenset({"read_repo_file", "grep_repo"})
_BILLING_TOOL_NAMES = frozenset({"get_billing_report", "get_bill_billing_report"})

RESPONSE_SIZE_CAP = 8192  # 8KB
BILLING_RESPONSE_SIZE_CAP = 16384  # 16KB for full billing JSON
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


def _serialize_for_llm(obj: Any, *, size_cap: int = RESPONSE_SIZE_CAP) -> str:
    """Serialize a Python value to a JSON string safe for LLM context."""
    if isinstance(obj, (dict, list)):
        raw = json.dumps(obj, ensure_ascii=False, default=str)
    elif isinstance(obj, (int, float, bool, str)):
        raw = json.dumps(obj, ensure_ascii=False)
    else:
        raw = json.dumps(str(obj), ensure_ascii=False)
    if len(raw) > size_cap:
        truncated = raw[:size_cap]
        truncated += f"\n... [truncated at {size_cap} bytes, original was {len(raw)} bytes]"
        return truncated
    return raw


def _tool_schema_by_name(tool_name: str) -> dict[str, Any] | None:
    for tool in _CORE_TOOL_SCHEMAS + _DEV_TOOL_SCHEMAS:
        if tool["function"]["name"] == tool_name:
            return tool["function"]["parameters"]
    return None


def _validate_stored_claim(
    claim_detail_loader: Any,
    validator: Any,
    patient_id: str,
    claim_id: str,
) -> dict[str, Any]:
    """Reconstruct a stored claim into the validator's expected dict and run it.

    The rule-engine ``validate_claim`` (``src/bilun/domain/rule_engine.py``)
    expects ``{claim_id, procedure_code, materials[], drug_context}`` where each
    material uses the short field names ``name``/``code``/``unit_price``/
    ``billed_amount``. The stored claim-detail API
    (``get_patient_claim_detail``) emits ``material_name``/``material_code``/
    ``unit_price_try``/``billed_amount_try``. This adapter closes that gap and
    derives ``procedure_code`` from the first procedure line.

    ``drug_context`` is omitted because ``prescriber_specialty`` is not present
    in stored claim detail, so drug-indication sub-checks are skipped.
    """
    detail = claim_detail_loader(patient_id, claim_id)

    procedures = detail.get("procedures") or []
    procedure_code = ""
    for proc in procedures:
        code = str(proc.get("procedure_code") or "").strip()
        if code:
            procedure_code = code
            break

    materials = []
    for line in detail.get("materials") or []:
        materials.append(
            {
                "name": line.get("material_name", ""),
                "code": line.get("material_code", ""),
                "quantity": line.get("quantity", 0),
                "unit_price": line.get("unit_price_try", 0),
                "billed_amount": line.get("billed_amount_try", 0),
            }
        )

    claim_dict = {
        "claim_id": claim_id,
        "procedure_code": procedure_code,
        "materials": materials,
        "drug_context": None,
    }
    result = validator(claim_dict)
    # Mirror the /validate-claim route's serialization (validation.py:53-78):
    # flatten the nested RuleViolation / MaterialLinePricing dataclasses into
    # JSON-friendly dicts so _serialize_for_llm round-trips cleanly.
    return {
        "claim_id": result.claim_id,
        "is_valid": result.is_valid,
        "total_claim_amount": result.total_claim_amount,
        "total_savings_try": result.total_savings_try,
        "total_risk_try": result.total_risk_try,
        "n_bundling_violations": result.n_bundling_violations,
        "n_exclusion_violations": result.n_exclusion_violations,
        "validation_time_ms": result.validation_time_ms,
        "summary": result.summary,
        "violations": [
            {
                "rule": v.rule,
                "severity": v.severity,
                "material_name": v.material_name,
                "message": v.message,
                "savings_try": v.savings_try,
                "risk_amount": v.risk_amount,
            }
            for v in result.violations
        ],
        "material_lines": [
            {
                "material_code": line.material_code,
                "material_name": line.material_name,
                "unit_price": line.unit_price,
                "quantity": line.quantity,
                "total_price": line.total_price,
                "is_reimbursable": line.is_reimbursable,
                "is_bundled": line.is_bundled,
                "source": line.source,
                "exactness_status": line.exactness_status,
                "notes": line.notes,
            }
            for line in result.material_lines
        ],
    }


def _validate_arguments(tool_name: str, arguments: dict[str, Any]) -> None:
    """Validate tool arguments against the schema. Raises ValueError on mismatch."""
    schema = _tool_schema_by_name(tool_name)
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
                get_bill_billing_report,
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
                get_patient_claim_detail,
                search_bilun_patients,
            )
            from src.bilun.chatbot.medula_kb import search_playbook_entries
            from src.bilun.chatbot.repo_tools import grep_repo, read_repo_file
            from src.bilun.domain.rule_engine import validate_claim as sut_validate_claim
            from src.bilun.domain.sut.clause_retrieval import search_clauses

            size_cap = (
                BILLING_RESPONSE_SIZE_CAP
                if tool_name in _BILLING_TOOL_NAMES
                else RESPONSE_SIZE_CAP
            )

            namespace = {
                "get_patient_billing_report": lambda: get_patient_billing_report(
                    arguments["patient_id"]
                ),
                "get_bill_billing_report": lambda: get_bill_billing_report(
                    arguments["patient_id"],
                    arguments["claim_id"],
                ),
                "get_revenue_recovery": get_revenue_recovery,
                "validate_stored_claim": lambda: _validate_stored_claim(
                    get_patient_claim_detail,
                    sut_validate_claim,
                    arguments["patient_id"],
                    arguments["claim_id"],
                ),
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
                "read_repo_file": lambda: read_repo_file(
                    arguments["path"],
                    start_line=arguments.get("start_line"),
                    end_line=arguments.get("end_line"),
                ),
                "grep_repo": lambda: grep_repo(
                    arguments["pattern"],
                    path_prefix=arguments.get("path_prefix", "src/bilun"),
                    max_matches=int(arguments.get("max_matches", 30)),
                ),
            }
            func = namespace.get(func_name)
            if func is None:
                raise ValueError(f"Executor not found for tool '{tool_name}'")
            result = func()
            return _serialize_for_llm(result, size_cap=size_cap)

        content = await asyncio.wait_for(
            asyncio.to_thread(_exec), timeout=TOOL_TIMEOUT_SEC
        )
    except TimeoutError:
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


def get_tool_schemas(*, user_role: UserRole = "billing_officer") -> list[dict[str, Any]]:
    """Return tool schemas for the LLM request."""
    if user_role == "dev":
        return _CORE_TOOL_SCHEMAS + _DEV_TOOL_SCHEMAS
    return list(_CORE_TOOL_SCHEMAS)
