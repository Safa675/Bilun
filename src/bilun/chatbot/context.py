"""BILUN SUT context builders — pure text formatters.

These functions receive pre-fetched data dicts from the API layer
and format LLM-friendly plain-text context blocks. They never import
from api/routes/, domain/, or db/ — pure formatters only.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from .prompts import ChatIntent
from .tools import UserRole

ChatLocale = Literal["en", "tr"]

_FULL_BILLING_LIST_CAP = 50
_SUMMARY_BILLING_LIST_CAP = 5
BillingDetailLevel = Literal["summary", "full"]

_PAGE_SECTION_SUMMARY_KEYS: dict[str, tuple[str, ...]] = {
    "outcome": ("patient_id",),
    "optimization_snapshot": ("patient_id", "n_diagnoses"),
    "billing_report": (
        "patient_id",
        "total_recoverable_try",
        "priority",
        "exactness_status",
    ),
}


def _format_sut_section(
    lines: list[str],
    header: str,
    value: Any,
    exactness: str | None = None,
    detail: str | None = None,
) -> None:
    """Append a labelled line with optional exactness badge and detail."""
    line = f"  {header}: {value}"
    if exactness:
        line += f"  [exactness: {exactness}]"
    lines.append(line)
    if detail:
        for dline in detail.split("\n"):
            if dline.strip():
                lines.append(f"    {dline.strip()}")


def _format_list_section(
    lines: list[str],
    header: str,
    items: list[dict],
    key: str = "label",
    fmt: str = "{label}",
    exactness: str | None = None,
    max_items: int = 10,
) -> None:
    lines.append(f"  {header}:")
    shown = 0
    for item in items[:max_items]:
        if isinstance(item, dict):
            label = item.get(key, item.get("name", "?"))
            values = {**item, key: label, "label": label}
            for field in re.findall(r"\{(\w+)\}", fmt):
                values.setdefault(field, "?")
            text = fmt.format(**values)
            lines.append(f"    - {text}")
        else:
            lines.append(f"    - {item!s}")
        shown += 1
    if len(items) > max_items:
        lines.append(f"    ... and {len(items) - max_items} more")
    if exactness:
        lines.append(f"    [exactness: {exactness}]")


def build_cohort_context(data: dict[str, Any]) -> str:
    """Build cohort-level SUT context from pre-fetched data.

    Expects data keys: optimization_summary (with summary dict inside).
    """
    lines: list[str] = []
    opt = data.get("optimization_summary", {}) or {}

    # Unwrap the _safe_context_block wrapper if present
    if isinstance(opt, dict) and "summary" in opt and isinstance(opt["summary"], dict):
        opt = opt["summary"]

    lines.append("--- COHORT OPTIMIZATION ---")

    copay = opt.get("copay_exemptions", {}) or {}
    exemption_by_category = copay.get("exemption_by_category") or []
    n_exempt = copay.get("n_exempt_patients")
    n_total = copay.get("n_total_patients")
    rate = copay.get("exemption_rate")

    if n_exempt is not None and n_total is not None:
        lines.append(
            f"  Copay exemptions: {n_exempt}/{n_total} patients exempt "
            f"({rate * 100:.1f}% rate)" if rate is not None
            else f"  Copay exemptions: {n_exempt}/{n_total} patients exempt"
        )
    if exemption_by_category:
        _format_list_section(
            lines,
            "Exemption by category",
            exemption_by_category,
            key="category",
            fmt="{category} ({count} patients)",
            max_items=6,
        )
    n_status_only = copay.get("n_exempt_status_only_patients")
    n_ek1a_only = copay.get("n_exempt_ek1a_patients")
    if isinstance(n_status_only, int) and isinstance(n_ek1a_only, int):
        lines.append(
            f"  Status-only exempt: {n_status_only}; EK-1A (any): {n_ek1a_only}"
        )
    if copay.get("top_diseases"):
        _format_list_section(
            lines,
            "Top qualifying diseases (EK-1A)",
            copay["top_diseases"],
            key="disease",
            fmt="{disease} ({count} patients)",
            max_items=5,
        )

    surcharge = opt.get("surcharge_exposure", {}) or {}
    exactness = surcharge.get("exactness_status")
    if exactness != "exact":
        lines.append(
            f"  Surcharge exposure: UNAVAILABLE "
            f"[exactness: {exactness or 'missing_exact_inputs'}]"
        )
        if surcharge.get("unavailable_reason"):
            lines.append(f"    Reason: {surcharge['unavailable_reason']}")
        if surcharge.get("required_inputs_missing"):
            lines.append(
                f"    Needs: {', '.join(surcharge['required_inputs_missing'])}"
            )
    else:
        _format_sut_section(
            lines,
            "Surcharge exposure",
            f"{surcharge.get('n_applicable_procedures', '?')} procedures",
            exactness=exactness,
            detail=surcharge.get("methodology"),
        )

    copay_rate = opt.get("copay_rate_exposure", {}) or {}
    cr_exactness = copay_rate.get("exactness_status")
    if cr_exactness != "exact":
        lines.append(
            f"  Copay rate exposure: UNAVAILABLE "
            f"[exactness: {cr_exactness or 'missing_exact_inputs'}]"
        )
        if copay_rate.get("unavailable_reason"):
            lines.append(f"    Reason: {copay_rate['unavailable_reason']}")
    else:
        _format_sut_section(
            lines,
            "Copay rate exposure",
            f"mean rate {copay_rate.get('mean_rate', '?')}%",
            exactness=cr_exactness,
        )

    drg = opt.get("drg_unbundling", {}) or {}
    drg_exactness = drg.get("exactness_status")
    if drg_exactness != "exact":
        lines.append(
            f"  DRG unbundling: UNAVAILABLE "
            f"[exactness: {drg_exactness or 'missing_exact_inputs'}]"
        )

    recovery = data.get("revenue_recovery", {}) or {}
    if isinstance(recovery, dict) and recovery.get("status") == "ready":
        recovery = recovery.get("summary") or {}
    elif isinstance(recovery, dict) and recovery.get("summary") and "status" not in recovery:
        recovery = recovery["summary"]
    if recovery:
        lines.append("\n--- COHORT REVENUE RECOVERY ---")
        n_override = recovery.get("n_optional_override_patients")
        override_uplift = recovery.get("total_optional_override_uplift")
        n_drg = recovery.get("n_drg_uplift_patients")
        drg_uplift = recovery.get("total_drg_uplift")
        n_blood = recovery.get("n_blood_uplift_patients")
        blood_uplift = recovery.get("total_blood_uplift")
        n_material = recovery.get("n_material_uplift_patients")
        material_uplift = recovery.get("total_material_uplift")
        sgk_uplift = recovery.get("total_sgk_uplift")
        if sgk_uplift is not None:
            lines.append(f"  SGK uplift (headline): {float(sgk_uplift):.2f} TRY")
        if n_override is not None:
            lines.append(
                f"  Optional §2.2.2(2) override: {int(n_override)} patients"
                + (
                    f", {float(override_uplift):.2f} TRY uplift"
                    if override_uplift is not None
                    else ""
                )
            )
        if n_drg is not None:
            lines.append(
                f"  DRG itemized-vs-package uplift: {int(n_drg)} patients"
                + (
                    f", {float(drg_uplift):.2f} TRY uplift"
                    if drg_uplift is not None
                    else ""
                )
            )
        if n_blood is not None:
            lines.append(
                f"  Blood component uplift: {int(n_blood)} patients"
                + (
                    f", {float(blood_uplift):.2f} TRY uplift"
                    if blood_uplift is not None
                    else ""
                )
            )
        if n_material is not None:
            lines.append(
                f"  Missing billable materials: {int(n_material)} patients"
                + (
                    f", {float(material_uplift):.2f} TRY uplift"
                    if material_uplift is not None
                    else ""
                )
            )
        n_addon = recovery.get("n_procedure_addon_patients")
        addon_uplift = recovery.get("total_procedure_addon_uplift")
        if n_addon is not None:
            lines.append(
                f"  Missing procedure add-ons: {int(n_addon)} patients"
                + (
                    f", {float(addon_uplift):.2f} TRY uplift"
                    if addon_uplift is not None
                    else ""
                )
            )

    temporal = opt.get("temporal_price_validation", {}) or {}
    if temporal.get("n_codes_with_changes"):
        lines.append("\n--- TEMPORAL PRICE AUDIT ---")
        _format_sut_section(
            lines,
            "Codes with price changes",
            temporal["n_codes_with_changes"],
            exactness="exact",
        )
        _format_sut_section(
            lines,
            "Date range",
            f"{temporal.get('date_range', '?')}",
            exactness="exact",
        )
        _format_list_section(
            lines,
            "Top price increases",
            temporal.get("top_increases", [])[:5],
            key="code",
            fmt="{code} {description}: +{pct_change:.1f}%",
            max_items=5,
        )

    return "\n".join(lines)


def build_patient_context(data: dict[str, Any]) -> str:
    """Build per-patient SUT context from pre-fetched data.

    Expects data keys: patient_outcome, patient_optimization.
    """
    lines: list[str] = []
    outcome = data.get("patient_outcome", {}) or {}
    if isinstance(outcome, dict) and "summary" in outcome:
        outcome = outcome["summary"]
    optimization = data.get("patient_optimization", {}) or {}
    if isinstance(optimization, dict) and "summary" in optimization:
        optimization = optimization["summary"]

    lines.append("--- PATIENT CONTEXT ---")

    _format_sut_section(lines, "Patient ID", outcome.get("patient_id", "?"))

    # Optimization
    opt_copay = optimization.get("copay_exemptions", {}) or {}
    if opt_copay:
        exempt = opt_copay.get("exempt")
        lines.append(f"  Copay exempt: {'YES' if exempt else 'NO'}")
        sources = opt_copay.get("exemption_sources") or []
        if sources:
            _format_list_section(
                lines,
                "Exemption grounds",
                sources,
                key="category",
                fmt="{category} ({rule_source})",
                max_items=5,
            )
        not_evaluated = opt_copay.get("categories_not_evaluated") or []
        if not_evaluated:
            _format_list_section(
                lines,
                "Categories not evaluated",
                not_evaluated,
                key="category",
                fmt="{category}",
                max_items=5,
            )
        if exempt and opt_copay.get("qualifying_diagnoses"):
            for qd in opt_copay["qualifying_diagnoses"][:5]:
                lines.append(
                    f"    - {qd.get('disease', '?')} ({qd.get('icd10', '?')})"
                )
            if len(opt_copay.get("qualifying_diagnoses", [])) > 5:
                lines.append(
                    f"    ... and "
                    f"{len(opt_copay['qualifying_diagnoses']) - 5} more"
                )

    opt_surcharge = optimization.get("surcharge_exposure", {}) or {}
    if opt_surcharge:
        sr_exactness = opt_surcharge.get("exactness_status")
        if sr_exactness == "exact":
            lines.append(
                f"  Surcharge exposure: {opt_surcharge.get('n_applicable_procedures', '?')} "
                f"procedures [exactness: exact]"
            )
        else:
            lines.append(
                f"  Surcharge exposure: UNAVAILABLE "
                f"[exactness: {sr_exactness or 'missing_exact_inputs'}]"
            )

    opt_cr = optimization.get("copay_rate_exposure", {}) or {}
    if opt_cr:
        cr_exactness = opt_cr.get("exactness_status")
        if cr_exactness == "exact":
            lines.append(
                f"  Copay rate exposure: mean {opt_cr.get('mean_rate', '?')}% "
                f"[exactness: exact]"
            )
        else:
            lines.append(
                f"  Copay rate exposure: UNAVAILABLE "
                f"[exactness: {cr_exactness or 'missing_exact_inputs'}]"
            )

    return "\n".join(lines)


def _billing_list_cap(detail_level: BillingDetailLevel) -> int:
    return _FULL_BILLING_LIST_CAP if detail_level == "full" else _SUMMARY_BILLING_LIST_CAP


def _unwrap_billing_report(data: dict[str, Any]) -> dict[str, Any]:
    report = data.get("billing_report", {}) or {}
    if isinstance(report, dict) and "summary" in report:
        return report["summary"]
    return report if isinstance(report, dict) else {}


def _copay_correction_label(correction: dict[str, Any]) -> str:
    name = (correction.get("name") or correction.get("procedure") or "").strip()
    code = (
        correction.get("code")
        or correction.get("procedure_code")
        or ""
    ).strip()
    if name and code:
        return f"{name} ({code})"
    return name or code or "?"


def _copay_correction_savings_try(correction: dict[str, Any]) -> float | None:
    for key in ("copay_component_try", "correction_try", "savings_try"):
        value = correction.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _copay_correction_ilave_try(correction: dict[str, Any]) -> float | None:
    value = correction.get("ilave_ucret_try")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _format_copay_correction_line(correction: dict[str, Any]) -> str:
    label = _copay_correction_label(correction)
    billed = correction.get("billed_try", correction.get("gazette_rate"))
    payable = correction.get("payable_try")
    savings = _copay_correction_savings_try(correction)
    ilave = _copay_correction_ilave_try(correction)
    rate = correction.get("correct_rate_pct")

    if billed is not None and payable is not None and savings is not None:
        parts = [
            f"{label}: billed {float(billed):.2f} TRY, "
            f"payable {float(payable):.2f} TRY, katılım payı {savings:.2f} TRY"
        ]
        if ilave is not None and ilave > 0:
            parts.append(f"ilave ücret {ilave:.2f} TRY")
        return ", ".join(parts)
    if rate is not None and savings is not None:
        return f"{label}: {rate}% correction ({savings:.2f} TRY)"
    if savings is not None:
        return f"{label}: {savings:.2f} TRY"
    return label


def _strategy_primary_label(row: dict[str, Any]) -> str:
    return (
        (row.get("claim_id") or row.get("chapter") or row.get("chapter_description") or "")
        .strip()
        or "?"
    )


def _strategy_mode_label(row: dict[str, Any]) -> str:
    return (row.get("recommendation") or row.get("strategy") or "unknown").strip()


def _format_strategy_line(row: dict[str, Any]) -> str:
    primary = _strategy_primary_label(row)
    mode = _strategy_mode_label(row)
    savings = row.get("savings_try")
    savings_text = f" ({float(savings):.2f} TRY)" if isinstance(savings, (int, float)) else ""
    detail = (row.get("detail") or row.get("ek2c_group") or "").strip()
    if detail:
        return f"{primary}: {mode}{savings_text} — {detail}"
    return f"{primary}: {mode}{savings_text}"


def _append_list_lines(
    lines: list[str],
    header: str,
    items: list[dict[str, Any]],
    *,
    formatter,
    max_items: int,
    exactness: str | None = None,
) -> None:
    if not items:
        return
    lines.append(f"  {header}:")
    for item in items[:max_items]:
        if isinstance(item, dict):
            lines.append(f"    - {formatter(item)}")
        else:
            lines.append(f"    - {item!s}")
    if len(items) > max_items:
        lines.append(f"    ... and {len(items) - max_items} more")
    if exactness:
        lines.append(f"    [exactness: {exactness}]")


def _append_billing_sections(
    lines: list[str],
    report: dict[str, Any],
    *,
    detail_level: BillingDetailLevel,
) -> None:
    """Append lab/copay/strategy/materials blocks for summary or full detail."""
    list_cap = _billing_list_cap(detail_level)
    is_full = detail_level == "full"

    lab = report.get("lab", {}) or report.get("lab_optimization", {}) or {}
    if lab:
        lab_exactness = lab.get("exactness_status", "unknown")
        _format_sut_section(
            lines,
            "Lab optimization",
            lab_exactness,
            exactness=lab_exactness,
        )
        lab_source = lab.get("rule_source", "")
        if lab_source:
            lines.append(f"    Source: {lab_source}")
        if is_full:
            normative = lab.get("normative_cost_try")
            if normative is not None:
                lines.append(f"    Normative cost: {normative:.2f} TRY")
        hemogram = lab.get("hemogram_bundling_savings")
        if hemogram is not None:
            lines.append(f"    Hemogram bundling savings: {hemogram:.2f} TRY")
        total = lab.get("total_savings")
        if total is None:
            total = hemogram or 0
        if total is None and not is_full:
            total = hemogram or 0
        if total is not None:
            lines.append(f"    Total lab savings: {total:.2f} TRY")
        if lab.get("flagged_tests"):
            lines.append("  Flagged tests:")
            for row in (lab["flagged_tests"] or [])[:list_cap]:
                savings = row.get("savings_try")
                if savings is None:
                    savings_part = "clinical review — no recoverable TRY"
                else:
                    savings_part = f"{float(savings):.2f} TRY"
                lines.append(
                    f"    - {row.get('test_name', '?')}: "
                    f"{row.get('flag_type', '?')} ({savings_part})"
                )
            if len(lab["flagged_tests"]) > list_cap:
                extra = len(lab["flagged_tests"]) - list_cap
                lines.append(f"    ... and {extra} more")
            if lab_exactness:
                lines.append(f"    [exactness: {lab_exactness}]")

    copay = report.get("copay", {}) or report.get("copay_optimization", {}) or {}
    if copay:
        copay_exactness = copay.get("exactness_status", "unknown")
        lines.append(f"\n  Copay optimization [exactness: {copay_exactness}]")
        copay_source = copay.get("rule_source", "")
        if is_full and copay_source:
            lines.append(f"    Source: {copay_source}")
        exempt = copay.get("is_exempt")
        if exempt is not None:
            lines.append(f"    Exempt: {'YES' if exempt else 'NO'}")
        sources = copay.get("exemption_sources") or []
        if sources:
            categories = ", ".join(
                str(source.get("category") or "?") for source in sources[:5]
            )
            lines.append(f"    Exemption basis: {categories}")
        if copay.get("copay_primary_outcome") and copay.get("copay_primary_outcome") != "none":
            lines.append(f"    Copay outcome: {copay['copay_primary_outcome']}")
        if copay.get("exemption_disease"):
            lines.append(f"    Qualifying disease: {copay['exemption_disease']}")
        if is_full and copay.get("exemption_range"):
            lines.append(f"    Exemption range: {copay['exemption_range']}")
        if is_full:
            visit = copay.get("visit_copay_savings_try")
            if visit is not None and visit > 0:
                lines.append(f"    Procedure exemption gap: {visit:.2f} TRY")
            rx = copay.get("rx_copay_savings_try")
            if rx is not None and rx > 0:
                lines.append(f"    Prescription exemption gap: {rx:.2f} TRY")
        decomposition_status = copay.get("line_decomposition_status")
        if decomposition_status:
            lines.append(f"    Line decomposition: {decomposition_status}")
        patient_copay = copay.get("patient_copay_try")
        if is_full and isinstance(patient_copay, (int, float)) and float(patient_copay) > 0:
            lines.append(f"    Total katılım payı on lines: {float(patient_copay):.2f} TRY")
        ilave_total = copay.get("ilave_ucret_total_try")
        if isinstance(ilave_total, (int, float)) and float(ilave_total) > 0:
            lines.append(f"    Total ilave ücret (§2.4, informational): {float(ilave_total):.2f} TRY")
            if is_full:
                lines.append(
                    "    Katılım payı (§1.8) and ilave ücret (§2.4) are separate — "
                    "exemption waives katılım payı only, not ilave ücret."
                )
        total_gap = copay.get("patient_copay_waived_total_try")
        if total_gap is None:
            visit_val = float(copay.get("visit_copay_savings_try") or 0)
            rx_val = float(copay.get("rx_copay_savings_try") or 0)
            total_gap = visit_val + rx_val
        if total_gap is not None and float(total_gap) > 0:
            label = "Total exemption gap" if is_full else "Exemption gap"
            lines.append(f"    {label}: {float(total_gap):.2f} TRY")
            if is_full:
                lines.append(
                    "    (Corrective: raises SGK payable and waives patient copay when "
                    "katilimPayindanMuaf=E is set before invoice.)"
                )
        if copay.get("rate_corrections"):
            _append_list_lines(
                lines,
                "Rate corrections",
                copay["rate_corrections"],
                formatter=_format_copay_correction_line,
                max_items=list_cap,
                exactness=copay_exactness if is_full else None,
            )

    strategy = report.get("strategy", {}) or report.get("billing_strategy", {}) or {}
    if strategy:
        strat_exactness = strategy.get("exactness_status", "unknown")
        lines.append(f"\n  Billing strategy [exactness: {strat_exactness}]")
        override_uplift = strategy.get("optional_override_uplift_try")
        if override_uplift is not None and float(override_uplift) > 0:
            lines.append(
                f"    Optional §2.2.2(2) override uplift: {float(override_uplift):.2f} TRY"
            )
        strat_source = strategy.get("rule_source", "")
        if is_full and strat_source:
            lines.append(f"    Source: {strat_source}")
        if strategy.get("recommendations"):
            _append_list_lines(
                lines,
                "Strategy recommendations",
                strategy["recommendations"],
                formatter=_format_strategy_line,
                max_items=list_cap,
                exactness=strat_exactness if is_full else None,
            )

    materials = report.get("materials", {}) or report.get("material_pre_check", {}) or {}
    if materials:
        mat_exactness = materials.get("exactness_status", "unknown")
        lines.append(f"\n  Material pre-check [exactness: {mat_exactness}]")
        mat_source = materials.get("rule_source", "")
        if is_full and mat_source:
            lines.append(f"    Source: {mat_source}")
        pre_auth = materials.get("pre_auth_required", [])
        if pre_auth:
            _format_list_section(
                lines,
                "Pre-auth required (EK-3C-1 tibbi uygunluk)",
                pre_auth,
                key="material_name",
                fmt="{material_name}",
                max_items=list_cap,
            )
        miat_interval = materials.get("miat_interval_violations", [])
        if miat_interval:
            _format_list_section(
                lines,
                "MIAT interval violations",
                miat_interval,
                key="material_name",
                fmt="{material_name}",
                max_items=list_cap,
            )
        bundled = materials.get("bundled_separate_billing", [])
        if bundled:
            _format_list_section(
                lines,
                "Bundled — billed separately",
                bundled,
                key="material_name",
                fmt="{material_name}",
                max_items=list_cap,
            )
        miat = materials.get("miat_restricted", [])
        if miat:
            _format_list_section(
                lines,
                "MIAT catalog (verify interval)",
                miat,
                key="material_name",
                fmt="{material_name}",
                max_items=list_cap,
            )
        if is_full:
            ceilings = materials.get("gazette_ceiling_by_specialty", {}) or {}
            if ceilings:
                lines.append("  Gazette ceiling by specialty:")
                for specialty, ceiling in list(ceilings.items())[:list_cap]:
                    lines.append(f"    - {specialty}: {ceiling:.2f} TRY")

    total_recoverable = report.get("total_recoverable_try")
    if total_recoverable is not None:
        lines.append(f"\n  MAX ADDITIONAL SGK REIMBURSEMENT: {total_recoverable:.2f} TRY")
    if is_full:
        action_count = report.get("action_count")
        if action_count is not None:
            lines.append(f"  Action count: {action_count}")
    priority = report.get("priority")
    if priority:
        lines.append(f"  Priority: {priority}")
    if is_full:
        report_exactness = report.get("exactness_status")
        if report_exactness:
            lines.append(f"  Report exactness: {report_exactness}")


def _append_billing_scope(lines: list[str], report: dict[str, Any]) -> None:
    scope = report.get("scope", "patient")
    lines.append(f"  Scope: {scope}")
    if scope == "bill":
        _format_sut_section(lines, "Bill ID", report.get("claim_id", "?"))


def build_full_billing_context(report: dict[str, Any]) -> str:
    """Build full per-patient billing context with all detail rows (cap 50 per list)."""
    if not report:
        return ""

    lines: list[str] = ["--- BILLING OPTIMIZATION (FULL) ---"]
    _format_sut_section(lines, "Patient ID", report.get("patient_id", "?"))
    _append_billing_scope(lines, report)
    _append_billing_sections(lines, report, detail_level="full")
    return "\n".join(lines)


def build_billing_context(
    data: dict[str, Any],
    *,
    detail_level: BillingDetailLevel = "summary",
) -> str:
    """Build per-patient billing optimization context from pre-fetched data."""
    report = _unwrap_billing_report(data)
    if not report:
        return ""

    if detail_level == "full":
        return build_full_billing_context(report)

    lines: list[str] = ["--- BILLING OPTIMIZATION ---"]
    _append_billing_scope(lines, report)
    _append_billing_sections(lines, report, detail_level="summary")
    return "\n".join(lines)


def build_catalog_context(data: dict[str, Any]) -> str:
    """Build gazette catalog reference context.

    Expects data keys: catalog_info.
    """
    info = data.get("catalog_info", {}) or {}
    if not info:
        return ""

    lines: list[str] = ["--- CATALOG REFERENCE ---"]
    if info.get("gazette_version"):
        lines.append(f"  Gazette version: {info['gazette_version']}")
    if info.get("katsayi"):
        lines.append(f"  SUT katsayi: {info['katsayi']} TL/puan")
    if info.get("ek2b_count"):
        lines.append(f"  EK-2B procedures: {info['ek2b_count']}")
    if info.get("ek2c_group_count"):
        lines.append(f"  EK-2C groups: {info['ek2c_group_count']}")
    return "\n".join(lines)


def build_medula_context(data: dict[str, Any]) -> str:
    """Build MEDULA knowledge base context from search results.

    Expects data keys: medula_search (dict with known_codes, rejection_categories,
    workflow_stage).
    """
    search = data.get("medula_search", {}) or {}
    if isinstance(search, dict) and "summary" in search:
        search = search.get("summary") or {}
    if not search:
        return ""

    has_content = (
        search.get("known_codes")
        or search.get("rejection_categories")
        or search.get("workflow_stage")
        or search.get("playbook_entries")
    )
    if not has_content:
        return ""

    lines: list[str] = ["--- MEDULA KNOWLEDGE BASE ---"]

    known_codes = search.get("known_codes", []) or []
    for entry in known_codes:
        code = entry.get("code", "?")
        meaning = entry.get("meaning_tr", entry.get("meaning_en", ""))
        action = entry.get("action", "")
        is_error = entry.get("is_error", True)
        label = "HATA" if is_error else "UYARI / BAŞARILI"
        lines.append(f"  Kod {code} ({label}): {meaning}")
        if action:
            lines.append(f"    Yapılması gereken: {action}")

    workflow = search.get("workflow_stage")
    if workflow:
        lines.append(f"\n  İlgili MEDULA Aşaması: {workflow.get('name_tr', '')}")
        desc = workflow.get("description_tr", workflow.get("description_en", ""))
        if desc:
            lines.append(f"    {desc}")

    categories = search.get("rejection_categories", []) or []
    for cat in categories:
        stage = cat.get("stage", "")
        stage_en = cat.get("stage_en", "")
        category = cat.get("category", "")
        problem = cat.get("problem", "")
        causes = cat.get("causes", [])
        resolution = cat.get("resolution", "")
        lines.append(f"\n  [{stage} - {category}]")
        if problem:
            lines.append(f"    Sorun: {problem}")
        if causes:
            lines.append("    Nedenler:")
            for c in causes:
                lines.append(f"      - {c}")
        if resolution:
            lines.append(f"    Çözüm: {resolution}")

    playbook_entries = search.get("playbook_entries", []) or []
    for entry in playbook_entries:
        lines.append(f"\n  [Playbook — {entry.get('playbook_key', '')}]")
        lines.append(f"    SUT: {entry.get('sut_anchor', '')}")
        lines.append(f"    Sorun: {entry.get('problem_summary_tr', '')}")
        steps = entry.get("corrective_steps_tr", []) or []
        if steps:
            lines.append("    Düzeltici adımlar:")
            for step in steps:
                lines.append(f"      - {step}")
        if entry.get("rebill_permitted"):
            lines.append(
                f"    Yeniden fatura: izinli ({entry.get('rebill_stage', '')})"
            )
        else:
            lines.append("    Yeniden fatura: önce ön koşulu giderin")

    return "\n".join(lines)


def build_rule_database_context(data: dict[str, Any]) -> str:
    """Build SUT Rule Database & clause coverage context from pre-fetched catalog."""
    catalog = data.get("rule_catalog", {}) or {}
    if isinstance(catalog, dict) and "summary" in catalog and isinstance(catalog["summary"], dict):
        catalog = catalog["summary"]
    if not catalog or not isinstance(catalog, dict):
        return ""

    lines: list[str] = ["--- SUT RULE DATABASE & CLAUSE COVERAGE ---"]
    lines.append(f"  Registered rule engines: {catalog.get('total_rules', 0)}")
    lines.append(
        f"    Implemented: {catalog.get('implemented_rules', 0)}, "
        f"Partial: {catalog.get('partial_rules', 0)}, "
        f"Missing: {catalog.get('missing_rules', 0)}, "
        f"Needs claim lines: {catalog.get('needs_claim_lines_rules', 0)}, "
        f"Non-algorithmic (reference only): {catalog.get('non_algorithmic_rules', 0)}"
    )
    total_clauses = catalog.get("total_clauses", 0)
    numbered = catalog.get("numbered_clause_count", 0)
    lines.append(
        f"  Live SUT clause corpus: {total_clauses} total paragraphs in force ({numbered} numbered rule clauses)"
    )
    types = catalog.get("clause_type_breakdown", {})
    if isinstance(types, dict) and types:
        lines.append(
            f"    Clause types: {types.get('fikra', 0)} fıkra, {types.get('bent', 0)} bent, "
            f"{types.get('prose', 0)} prose paragraphs, {types.get('section_heading', 0)} headings"
        )
    gaps = catalog.get("algorithmic_gaps", 0)
    gap_pct = catalog.get("algorithmic_gap_pct", 0.0)
    lines.append(f"  Algorithmic gaps: {gaps} clauses ({gap_pct:.1f}% gap rate)")
    top_gaps = catalog.get("top_gap_categories", [])
    if top_gaps and isinstance(top_gaps, list):
        _format_list_section(
            lines,
            "Top gap categories",
            top_gaps,
            key="category",
            fmt="{category} ({count} clauses)",
            max_items=6,
        )
    fc = catalog.get("fact_check_summary")
    if isinstance(fc, dict) and fc.get("total_units"):
        lines.append(
            f"  Fact-check audit rollup: {fc.get('compliant', 0)} compliant, "
            f"{fc.get('partial', 0)} partial, {fc.get('heuristic', 0)} heuristic units"
        )
    return "\n".join(lines)


def slim_page_context(page_context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Keep page_view metadata only — full patient data is fetched server-side."""
    if not page_context:
        return None

    slim: dict[str, Any] = dict(page_context)
    visible = page_context.get("visible_billing")
    if isinstance(visible, dict):
        slim["visible_billing"] = visible

    sections = page_context.get("sections")
    if not isinstance(sections, dict):
        return slim

    slim_sections: dict[str, Any] = {}
    for section_key, value in sections.items():
        if section_key in _PAGE_SECTION_SUMMARY_KEYS and isinstance(value, dict):
            summary: dict[str, Any] = {"loaded": True}
            for field in _PAGE_SECTION_SUMMARY_KEYS[section_key]:
                if field in value:
                    summary[field] = value[field]
            if section_key == "billing_report" and value.get("claim_id"):
                summary["claim_id"] = value["claim_id"]
            slim_sections[section_key] = summary
        else:
            slim_sections[section_key] = value

    slim["sections"] = slim_sections
    return slim


def officer_page_context(page_context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Keep only UI hints; browser-supplied text never selects private context."""
    if not page_context:
        return None
    allowed = {"page", "tab", "patient_id", "selected_section"}
    result = {key: value for key, value in page_context.items() if key in allowed and isinstance(value, str)}
    tab = result.get("tab", "").lower()
    if "rule" in tab or "kural" in tab:
        result["tab"] = "patients"
    visible = page_context.get("visible_billing")
    if isinstance(visible, dict):
        # Retain selection identity only. Server lookup owns bill amounts.
        result["visible_billing"] = {
            key: visible[key] for key in ("patient_id", "claim_id", "scope")
            if key in visible and isinstance(visible[key], str)
        }
    sections = page_context.get("sections")
    if isinstance(sections, dict):
        result["sections"] = {
            name: {key: value for key, value in section.items()
                   if key in (*_PAGE_SECTION_SUMMARY_KEYS[name], "loaded", "claim_id")
                   and isinstance(value, (str, int, float, bool, type(None)))}
            for name, section in sections.items()
            if name in _PAGE_SECTION_SUMMARY_KEYS and isinstance(section, dict)
        }
    return result


def build_bilun_runtime_context(
    data: dict[str, Any],
    active_tab: str,
    patient_id: str | None = None,
    *,
    page_context: dict[str, Any] | None = None,
    intent: ChatIntent = "user_question",
    billing_detail: BillingDetailLevel | None = None,
    user_role: UserRole = "billing_officer",
    ui_locale: ChatLocale = "en",
) -> str:
    """Build the complete BILUN runtime context string for the LLM.

    Args:
        data: Pre-fetched data dict from the API layer.
            May contain: optimization_summary, patient_outcome,
            patient_optimization, billing_report, catalog_info, rule_catalog.
        active_tab: Current workspace tab name.
        patient_id: Currently selected patient, if any.
        page_context: Structured view of the current page (sections, labels, values).
        intent: Chat intent — ``user_question`` uses full billing detail by default;
            ``auto_brief`` uses capped summary billing.
        billing_detail: Optional override for billing context depth (chat uses summary).

    Returns:
        Formatted context string ready for the LLM system prompt.
    """
    import json

    context: dict[str, Any] = {
        "product": "BILUN",
        "active_tab": active_tab,
        "intent": intent,
        "user_role": user_role,
        "ui_locale": ui_locale,
        "assistant_rules": [
            "Answer only from BILUN financial, reimbursement, optimization, rule-database, and patient-workspace context.",
            "If an exactness or pricing status is not exact, describe that surface as unavailable instead of inventing zero, clear, or low-risk values.",
            "Do not rely on IHP-only risk, causal, or trajectory claims.",
            "Always cite the exactness_status when reporting financial amounts.",
            "When a feature is gated, explain what claim data is needed.",
        ],
    }

    if user_role == "dev":
        context["assistant_rules"].extend([
            "Developer mode: you may call read_repo_file and grep_repo to explain implementation.",
            "For patient-specific TRY amounts, prefer page_view.visible_billing or billing tools — never infer amounts from source code.",
            "sgk_uplift_try is recoverable SGK revenue; audit_exposure_try is compliance/denetim risk (overbilling exposure); compliance_adjustment_try is downward compliance correction; exemption_gap_try is waived copay the patient should not pay.",
            "Cite repository file paths when explaining how an algorithm works.",
        ])

    if ui_locale == "tr":
        context["assistant_rules"].append(
            "UI locale is Turkish (tr): every assistant reply must be written entirely in Turkish, even if the user prompt is in English."
        )

    if user_role != "dev":
        page_context = officer_page_context(page_context)
    slim_view = slim_page_context(page_context)
    if slim_view:
        context["page_view"] = slim_view

    tab_normalized = active_tab.strip().lower()
    if page_context and isinstance(page_context.get("tab"), str):
        tab_normalized = page_context["tab"].strip().lower()

    is_rule_db = user_role == "dev" and ("rule" in tab_normalized or "kural" in tab_normalized)

    if is_rule_db:
        rule_db_ctx = build_rule_database_context(data)
        if rule_db_ctx:
            context["rule_database_context"] = rule_db_ctx
    else:
        context["cohort_context"] = build_cohort_context(data)

    if patient_id:
        context["patient_context"] = build_patient_context(data)
        resolved_billing_detail: BillingDetailLevel = (
            billing_detail
            if billing_detail is not None
            else ("full" if intent == "user_question" else "summary")
        )
        context["billing_context"] = build_billing_context(
            data,
            detail_level=resolved_billing_detail,
        )
        if user_role == "dev":
            raw_report = _unwrap_billing_report(data)
            if raw_report:
                context["billing_report_json"] = raw_report

    catalog = build_catalog_context(data)
    if catalog:
        context["catalog_context"] = catalog

    medula_queue = data.get("medula_queue_count")
    if isinstance(medula_queue, dict) and medula_queue.get("status") == "ready":
        queue_summary = medula_queue.get("summary") or {}
        if queue_summary.get("ingest_available"):
            context["medula_queue"] = {
                "ingest_available": True,
                "total": queue_summary.get("total", 0),
            }

    medula = build_medula_context(data)
    if medula:
        context["medula_context"] = medula

    return (
        "BILUN runtime context for the BILUN assistant.\n"
        "Use this context to answer reimbursement, optimization, and patient financial workspace questions.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
