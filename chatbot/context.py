"""Runtime context builders for ILAY chat and smart notes."""

from __future__ import annotations

import math
from typing import Any

from .metadata import get_missing_context_blocks, has_performance_metrics


def _safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        fval = float(val)
    except (TypeError, ValueError):
        return default
    if math.isnan(fval) or math.isinf(fval):
        return default
    return fval


def _append_unavailable(lines: list[str], title: str, reason: str) -> None:
    lines.append(f"\n═══ {title} UNAVAILABLE ═══")
    lines.append(f"• {reason}")


def _normalize_counts(
    raw: dict | list | None,
    *,
    name_key: str,
    count_key: str = "count",
) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, list):
        return {}
    normalized: dict[str, Any] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get(name_key)
        if name is None:
            continue
        normalized[str(name)] = item.get(count_key, 0)
    return normalized


def _get_id_col(df) -> str:
    if "HASTA_ID" in df.columns:
        return "HASTA_ID"
    if "patient_id" in df.columns:
        return "patient_id"
    return "HASTA_ID"


def build_cohort_context(
    active_tab: str,
    cache: dict,
    db_context: dict | None = None,
    model_context: dict | None = None,
) -> str:
    """Build cohort-level chat context from the active cache and model metadata."""
    model_context = model_context or {}
    db_context = db_context or {}
    missing_blocks = get_missing_context_blocks(
        active_tab,
        db_context=db_context,
        model_context=model_context,
    )

    lines = [
        f"\n═══ ACTIVE DASHBOARD TAB: {active_tab or 'Unknown'} ═══",
        "═══ ACTIVE MODEL ═══",
        f"• Build ID: {model_context.get('build_id') or 'unavailable'}",
        f"• Engine: {(model_context.get('engine') or 'unavailable').upper()}",
        f"• Target: {model_context.get('target') or 'unavailable'}",
        f"• Artifact Created At: {model_context.get('created_at') or 'unavailable'}",
        f"• Feature Count: {model_context.get('n_features') if model_context.get('n_features') is not None else 'unavailable'}",
        f"• Subscore Groups: {model_context.get('n_subscores') if model_context.get('n_subscores') is not None else 'unavailable'}",
        "═══ COHORT SUMMARY ═══",
    ]

    kpi = cache.get("kpi", {})
    lines.append(f"• Total Patients Scored: {kpi.get('n_patients', '?')}")
    lines.append(f"• Mean IHP: {_safe_float(kpi.get('mean_ihp')):.2f}")
    lines.append(f"• Mean CCI: {_safe_float(kpi.get('mean_cci')):.1f}")
    lines.append(
        f"• Mean Symptoms: {_safe_float(kpi.get('mean_symptoms', kpi.get('mean_symptom_count'))):.1f}"
    )
    lines.append(f"• Mean Severity: {_safe_float(kpi.get('mean_severity')):.2f}")
    lines.append(f"• Mean IHP Confidence: {_safe_float(kpi.get('mean_ihp_confidence')):.1%}")

    outcome_dist = _normalize_counts(
        cache.get("outcome_distribution"),
        name_key="outcome",
    )
    if outcome_dist:
        lines.append("\nOutcome Distribution:")
        for outcome, count in outcome_dist.items():
            lines.append(f"  • {outcome}: {count}")

    alert_kpi = cache.get("alert_kpi", {})
    total_alerts = alert_kpi.get("total", 0) if isinstance(alert_kpi, dict) else 0
    if total_alerts > 0:
        lines.append(f"\nClinical Alerts: {total_alerts} total")
        by_severity = _normalize_counts(
            alert_kpi.get("by_severity") if isinstance(alert_kpi, dict) else None,
            name_key="severity",
        )
        for sev in ("CRITICAL", "HIGH", "MEDIUM"):
            if by_severity.get(sev, 0) > 0:
                lines.append(f"  • {sev}: {by_severity[sev]}")

    lines.append("═══ END COHORT SUMMARY ═══")

    tab = (active_tab or "").lower()
    if "cohort" in tab:
        ss = cache.get("subscore_summary")
        if ss and isinstance(ss, dict):
            lines.append("\n═══ VISIBLE: Subscore Averages ═══")
            for name, stats in ss.items():
                if isinstance(stats, dict):
                    lines.append(
                        f"  • {name}: mean={stats.get('mean', '?')}, "
                        f"median={stats.get('median', '?')}, "
                        f"range=[{stats.get('min', '?')}-{stats.get('max', '?')}]"
                    )

        ihp_hist = cache.get("ihp_histogram")
        if isinstance(ihp_hist, list) and ihp_hist:
            lines.append("\n═══ VISIBLE: IHP Distribution ═══")
            for item in ihp_hist:
                if isinstance(item, dict) and item.get("count", 0) > 0:
                    lines.append(f"  • {item.get('bin', '?')}: {item['count']}")

        util = cache.get("utilization")
        if isinstance(util, dict) and util:
            lines.append("\n═══ VISIBLE: Utilization ═══")
            for key, value in util.items():
                lines.append(f"  • {key}: {value}")

        trend_summary = _normalize_counts(
            cache.get("trend_summary"),
            name_key="direction",
            count_key="count",
        )
        if trend_summary:
            lines.append("\n═══ VISIBLE: Trend Directions ═══")
            for direction, count in trend_summary.items():
                lines.append(f"  • {direction}: {count}")

    elif "validation" in tab or "performance" in tab:
        title = "Validation Metrics" if "validation" in tab else "Performance Metrics"
        if has_performance_metrics(model_context):
            lines.append(f"\n═══ VISIBLE: Active Model {title} ═══")
            lines.append(f"  • Engine: {(model_context.get('engine') or 'unavailable').upper()}")
            lines.append(f"  • Target: {model_context.get('target') or 'unavailable'}")
            lines.append(f"  • Training AUC: {_safe_float(model_context.get('training_auc')):.4f}")
            lines.append(
                f"  • Training PR-AUC: {_safe_float(model_context.get('training_pr_auc')):.4f}"
            )
            lines.append(
                f"  • Training Brier: {_safe_float(model_context.get('training_brier')):.4f}"
            )
            lines.append(f"  • Samples: {model_context.get('n_samples', 'unavailable')}")
            lines.append(f"  • CV Folds: {model_context.get('n_folds', 'unavailable')}")
        else:
            _append_unavailable(
                lines,
                f"VISIBLE: Active Model {title}",
                "Active-model performance metrics are unavailable for the current build. Do not infer benchmark or validation numbers.",
            )

    elif "causal" in tab:
        causal = db_context.get("causal_drivers")
        if causal:
            lines.append("\n═══ VISIBLE: Causal Drivers ═══")
            lines.append(
                f"  • Patients with significant IHP changes: {causal.get('n_patients_with_changes', '?')}"
            )
            lines.append(
                f"  • Total significant changes: {causal.get('n_total_significant_changes', '?')}"
            )

            decline = causal.get("top_decline_drivers", [])[:3]
            if decline:
                lines.append("  Top decline drivers:")
                for driver in decline:
                    lines.append(
                        f"    • {driver.get('label', '?')}: avg {driver.get('avg_contribution', 0):+.2f} pts/event ({driver.get('n_events', 0)} events)"
                    )

            improvement = causal.get("top_improvement_drivers", [])[:3]
            if improvement:
                lines.append("  Top improvement drivers:")
                for driver in improvement:
                    lines.append(
                        f"    • {driver.get('label', '?')}: avg {driver.get('avg_contribution', 0):+.2f} pts/event ({driver.get('n_events', 0)} events)"
                    )
        else:
            _append_unavailable(
                lines,
                "VISIBLE: Causal Drivers",
                "Causal driver summaries are unavailable for the active build. Do not fabricate attribution explanations.",
            )

    elif "optimizer" in tab:
        opt = db_context.get("optimization_summary")
        recovery = db_context.get("recovery_summary")
        alerts_summary = db_context.get("patient_alerts_summary")
        if opt or recovery or alerts_summary:
            lines.append("\n═══ VISIBLE: SUT Optimization Intelligence ═══")
            if opt:
                copay_ex = opt.get("copay_exemptions", {})
                lines.append(
                    f"  • Copay exemptions (EK-1A): {copay_ex.get('n_exempt_patients', 0)}/{copay_ex.get('n_total_patients', '?')} patients exempt ({copay_ex.get('exemption_rate', 0):.1%})"
                )
                surcharge = opt.get("surcharge_exposure", {})
                lines.append(
                    f"  • Surcharge-free procedures (EK-2G): {surcharge.get('n_patients_with_flags', 0)} patients flagged"
                )
                copay_rate = opt.get("copay_rate_exposure", {})
                lines.append(
                    f"  • Copay rate exposure (EK-2C-1): {copay_rate.get('n_patients_with_flags', 0)} patients flagged"
                )

            if recovery:
                lines.append(
                    f"  • Grand total recoverable: {recovery.get('grand_total_recoverable', 0):,.0f} TRY"
                )
                savings = recovery.get("savings_by_category", {})
                for category, amount in sorted(
                    savings.items(),
                    key=lambda item: -(item[1] if isinstance(item[1], (int, float)) else 0),
                ):
                    if isinstance(amount, (int, float)):
                        lines.append(f"    • {category}: {amount:,.0f} TRY")

            if alerts_summary:
                lines.append(
                    f"  • Patient alert summary exemption rate: {alerts_summary.get('exemption_rate', 0):.1%}"
                )
        else:
            _append_unavailable(
                lines,
                "VISIBLE: SUT Optimization Intelligence",
                "Optimization summaries are unavailable for the active build. Do not infer exemption or recovery totals.",
            )

    if missing_blocks:
        lines.append("\n═══ OPTIONAL CONTEXT STATUS ═══")
        for block in missing_blocks:
            lines.append(f"• {block} unavailable")

    return "\n".join(lines)


def build_patient_context(
    patient_id: str,
    cache: dict,
    db_context: dict | None = None,
    model_context: dict | None = None,
) -> str:
    """Build patient-level chat context from the active cache and model metadata."""
    import polars as pl

    model_context = model_context or {}
    db_context = db_context or {}
    lines = [f"\n═══ SELECTED PATIENT DATA: {patient_id} ═══"]

    scored = cache.get("scored")
    if scored is None:
        lines.append("(No patient data available — pipeline not ready)")
        lines.append("═══ END SELECTED PATIENT DATA ═══")
        return "\n".join(lines)

    id_col = _get_id_col(scored)
    patient_df = scored.filter(pl.col(id_col) == patient_id)
    if patient_df.height == 0:
        lines.append(f"(Patient {patient_id} not found in scored data)")
        lines.append("═══ END SELECTED PATIENT DATA ═══")
        return "\n".join(lines)

    row = patient_df.row(0, named=True)
    ts_df = cache.get("timeseries")
    if ts_df is not None:
        ts_id_col = _get_id_col(ts_df)
        patient_ts = ts_df.filter(pl.col(ts_id_col) == patient_id).sort("ym")
        if patient_ts.height > 0:
            latest_ts = patient_ts.row(-1, named=True)
            if latest_ts.get("ihp_probability") is not None:
                row["ihp_probability"] = round(float(latest_ts["ihp_probability"]), 2)
            for subscore in model_context.get("subscores", []):
                col = subscore.get("column")
                if col and latest_ts.get(col) is not None:
                    row[col] = round(float(latest_ts[col]), 4)

    lines.append(f"• Age: {row.get('yas', '?')}")
    lines.append(f"• Gender: {row.get('CINSIYET', '?')}")
    outcome = row.get("outcome", "healthy")
    lines.append(f"• Outcome: {outcome}")
    if outcome == "exitus":
        lines.append(
            "⚠ NOTE: This patient is DECEASED. Do not suggest future treatments or predictions."
        )

    ihp = _safe_float(row.get("ihp_probability"))
    confidence = _safe_float(row.get("ihp_confidence"))
    risk_level = row.get("ihp_risk_tier", "?")
    lines.append(f"\nIHP (ILAY Hazard Probability): {ihp:.2f}/100  (confidence: {confidence:.0%})")
    lines.append(f"Risk Tier: {risk_level}")

    subscores = model_context.get("subscores", [])
    if subscores:
        lines.append("\nRisk contribution domains:")
        for subscore in subscores:
            column = subscore.get("column")
            if not column:
                continue
            if column not in row:
                continue
            label = subscore.get("label", column)
            feature_count = subscore.get("feature_count")
            suffix = f" ({feature_count} features)" if feature_count is not None else ""
            lines.append(f"  • {label}{suffix}: {_safe_float(row.get(column)):+.4f}")
    else:
        lines.append(
            "\nArtifact-backed subscore metadata unavailable for the active model."
        )

    nlp_cci = _safe_float(row.get("nlp_cci_score"))
    nlp_symptoms = _safe_float(row.get("nlp_symptom_count"))
    nlp_severity = _safe_float(row.get("nlp_severity_score"))
    if nlp_cci > 0 or nlp_symptoms > 0:
        lines.append(
            f"\nNLP Features: CCI={nlp_cci:.0f}, symptoms={nlp_symptoms:.0f}, severity={nlp_severity:.2f}"
        )

    lines.append("\nUtilization:")
    lines.append(f"  • Total visits: {row.get('toplam_gelis', '?')}")
    lines.append(f"  • Unique diagnoses: {row.get('benzersiz_tani_sayisi', '?')}")
    lines.append(f"  • Total lab tests: {row.get('toplam_lab_testi', '?')}")
    lines.append(f"  • Abnormal test ratio: {_safe_float(row.get('anormal_test_orani')):.2f}")
    lines.append(f"  • Unique drugs: {row.get('benzersiz_ilac_sayisi', '?')}")
    lines.append(f"  • Total prescriptions: {row.get('toplam_recete', '?')}")

    lab_cols = [
        column
        for column in scored.columns
        if column.startswith("fe_lab_") and column.endswith("_latest")
    ]
    if lab_cols:
        patient_labs = {
            column: row.get(column)
            for column in lab_cols
            if row.get(column) is not None
            and not (
                isinstance(row.get(column), float) and math.isnan(row.get(column))
            )
        }
        if patient_labs:
            lines.append("\nKey Lab Values (latest):")
            for column, value in sorted(patient_labs.items())[:20]:
                name = column.replace("fe_lab_", "").replace("_latest", "")
                lines.append(f"  • {name}: {value}")

    if ts_df is not None:
        ts_id_col = _get_id_col(ts_df)
        patient_ts = ts_df.filter(pl.col(ts_id_col) == patient_id).sort("ym")
        if patient_ts.height > 0:
            latest_ts = patient_ts.row(-1, named=True)
            earliest_ts = patient_ts.row(0, named=True)
            lines.append(f"\nIHP Trajectory ({patient_ts.height} months):")
            lines.append(
                f"  • Earliest IHP: {_safe_float(earliest_ts.get('ihp_probability')):.2f} ({earliest_ts.get('period', '?')})"
            )
            lines.append(
                f"  • Latest IHP: {_safe_float(latest_ts.get('ihp_probability')):.2f} ({latest_ts.get('period', '?')})"
            )
            delta = latest_ts.get("ihp_delta")
            if delta is not None and not (
                isinstance(delta, float) and math.isnan(delta)
            ):
                lines.append(f"  • Latest month delta: {delta:+.2f}")
            rolling = latest_ts.get("ihp_rolling_3m")
            if rolling is not None and not (
                isinstance(rolling, float) and math.isnan(rolling)
            ):
                lines.append(f"  • 3-month rolling avg: {rolling:.2f}")

    trends_df = cache.get("trends")
    if trends_df is not None:
        trend_id_col = _get_id_col(trends_df)
        patient_trend = trends_df.filter(pl.col(trend_id_col) == patient_id)
        if patient_trend.height > 0:
            trend = patient_trend.row(0, named=True)
            slope = trend.get("slope")
            direction = trend.get("direction", "?")
            if slope is not None and not (
                isinstance(slope, float) and math.isnan(slope)
            ):
                lines.append(f"  • Trend slope: {slope:.2f}/month ({direction})")

    alerts_df = cache.get("alerts")
    if alerts_df is not None:
        alert_id_col = _get_id_col(alerts_df)
        patient_alerts = alerts_df.filter(pl.col(alert_id_col) == patient_id)
        if patient_alerts.height > 0:
            lines.append(f"\nActive Alerts ({patient_alerts.height}):")
            for alert in patient_alerts.to_dicts():
                lines.append(
                    f"  • [{alert.get('severity', '?')}] {alert.get('alert_type', '?')}: {alert.get('message', '')}"
                )

    lines.append("═══ END SELECTED PATIENT DATA ═══")
    return "\n".join(lines)


def build_smart_notes_prompt(
    patient_id: str,
    cache: dict,
    model_context: dict | None = None,
) -> tuple[str, str]:
    """Build the patient smart-notes runtime context and prompt."""
    import polars as pl

    model_context = model_context or {}
    context = build_patient_context(patient_id, cache, model_context=model_context)

    subscore_specs = model_context.get("subscores", [])
    top_concerns: list[tuple[str, float]] = []
    patient_outcome: str | None = None
    scored = cache.get("scored")
    if scored is not None:
        id_col = _get_id_col(scored)
        patient_df = scored.filter(pl.col(id_col) == patient_id)
        if patient_df.height > 0:
            row = patient_df.row(0, named=True)
            patient_outcome = row.get("outcome", "healthy")

            ts_df = cache.get("timeseries")
            if ts_df is not None:
                ts_id_col = _get_id_col(ts_df)
                patient_ts = ts_df.filter(pl.col(ts_id_col) == patient_id).sort("ym")
                if patient_ts.height > 0:
                    latest_ts = patient_ts.row(-1, named=True)
                    for spec in subscore_specs:
                        column = spec.get("column")
                        if column and latest_ts.get(column) is not None:
                            row[column] = round(float(latest_ts[column]), 1)

            scored_values = []
            for spec in subscore_specs:
                column = spec.get("column")
                if not column:
                    continue
                scored_values.append(
                    (spec.get("label", column), _safe_float(row.get(column)))
                )
            scored_values.sort(key=lambda item: item[1], reverse=True)
            top_concerns = [
                (name, value) for name, value in scored_values[:3] if value > 0
            ]

    alert_lines: list[str] = []
    alerts_df = cache.get("alerts")
    if alerts_df is not None:
        alert_id_col = _get_id_col(alerts_df)
        patient_alerts = alerts_df.filter(pl.col(alert_id_col) == patient_id)
        if patient_alerts.height > 0:
            for alert in patient_alerts.to_dicts():
                alert_lines.append(
                    f"[{alert.get('severity', '?')}] {alert.get('alert_type', '?')}: {alert.get('message', '')}"
                )

    trend_direction: str | None = None
    trends_df = cache.get("trends")
    if trends_df is not None:
        trend_id_col = _get_id_col(trends_df)
        patient_trend = trends_df.filter(pl.col(trend_id_col) == patient_id)
        if patient_trend.height > 0:
            trend_direction = patient_trend.row(0, named=True).get("direction")

    concern_str = (
        ", ".join(f"{name}: {value:.1f}/100" for name, value in top_concerns)
        if top_concerns
        else "No artifact-backed subscore concerns available"
    )
    target = model_context.get("target") or "the active target"

    prompt_parts = [
        "You are ILAY, an AI clinical risk intelligence assistant.",
        "",
        "Below is the complete clinical data for one patient.",
        "Write a concise clinical intelligence briefing (4-8 sentences) that:",
        "1. States the patient's overall health status using the IHP score and risk level in one sentence.",
        f"2. Explains the primary drivers of risk for {target}, focusing on the top 2-3 artifact-backed burden groups: {concern_str}.",
        "3. References exact labs, utilization signals, alerts, and trajectory details only when they appear in the patient context.",
    ]

    if alert_lines:
        prompt_parts.append(f"4. Note active alerts: {'; '.join(alert_lines)}.")

    if trend_direction:
        step = "5" if alert_lines else "4"
        prompt_parts.append(
            f"{step}. Comment on the trajectory trend (current direction: {trend_direction})."
        )

    if patient_outcome == "exitus":
        prompt_parts.append(
            "IMPORTANT: This patient is DECEASED (outcome: exitus). Frame the briefing as a retrospective summary and do not suggest future monitoring or treatment."
        )

    prompt_parts.append(
        "Provide a brief clinical interpretation in the same language as the patient context. Be direct, use exact numbers, avoid fluff, and do not give treatment advice."
    )

    return (context, "\n".join(prompt_parts))
