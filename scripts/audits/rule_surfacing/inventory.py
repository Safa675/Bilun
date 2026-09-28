"""Inventory for the deterministic rule-surfacing audit."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from .model import AuditContext, RuntimeCall
from .metadata import (
    LOCKED_DEFINITIONS,
    BROAD_WRAPPED_CALLS,
    NON_EMITTING_RUNTIME_HELPERS,
    REPORT_FIELD_OVERRIDES,
    ARTIFACTS_BY_CALLABLE,
    EQUIVALENT_EMISSIONS,
    GENERIC_SURFACE_EMISSION_SOURCES,
    EMISSION_OVERRIDES,
    PATIENT_REPORT_META,
)
from .python_sources import (
    _canonical_evaluator_emissions,
    _direct_calls_in_callable,
    _focused_specs,
    _load_registry,
    _static_emissions,
    _validate_focused_report_dataflow,
    assert_known_runtime_calls,
    discover_recommended_action_surfaces,
    discover_runtime_calls,
)
from .surface_sources import (
    _cohort_api_evidence_path,
    _cohort_ui_evidence_path,
    _patient_ui_evidence_paths,
    discover_deep_link_sections,
)


def _artifact_rule_ids(ctx: AuditContext, filename: str) -> set[str]:
    path = ctx.prose_rules_dir / filename
    if not path.is_file():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(rules, list):
        return set()
    return {
        str(row["rule_id"])
        for row in rules
        if isinstance(row, dict) and row.get("rule_id")
    }


def validate_explicit_metadata(ctx: AuditContext, report_calls: Iterable[RuntimeCall]) -> None:
    report_calls = list(report_calls)
    discovered = [row.callable for row in report_calls]
    if len(discovered) != len(set(discovered)):
        raise ValueError("duplicate patient-report runtime call discovered")
    discovered_set = set(discovered)
    metadata_set = set(PATIENT_REPORT_META)
    missing = sorted(discovered_set - metadata_set)
    stale = sorted(metadata_set - discovered_set)
    if missing or stale:
        raise ValueError(f"patient-report metadata drift: missing={missing}, stale={stale}")

    action_surfaces = discover_recommended_action_surfaces(ctx)
    deep_links = discover_deep_link_sections(ctx)
    for callable_name in discovered:
        meta = PATIENT_REPORT_META[callable_name]
        visibility = str(meta.get("visibility") or "")
        patient_visible = visibility in {"patient_visible", "patient_and_cohort_visible"}
        cohort_visible = visibility in {"cohort_visible", "patient_and_cohort_visible"}
        patient_ui = meta.get("patient_ui")
        cohort_api = meta.get("cohort_api")
        cohort_ui = meta.get("cohort_ui")

        if patient_visible and not patient_ui:
            raise ValueError(f"{callable_name}: patient-visible metadata lacks patient_ui")
        if cohort_visible and (not cohort_api or not cohort_ui):
            raise ValueError(f"{callable_name}: cohort-visible metadata lacks API/UI proof")
        if visibility in {"aggregate_only", "not_applicable"} and any(
            value is not None for value in (patient_ui, cohort_api, cohort_ui)
        ):
            raise ValueError(f"{callable_name}: {visibility} row cannot claim patient/cohort UI")
        if visibility in {"aggregate_only", "hidden_runtime", "not_applicable"} and not str(
            meta.get("hidden_reason") or ""
        ).strip():
            raise ValueError(
                f"{callable_name}: {visibility} metadata lacks an explicit internal rationale"
            )

        if patient_ui:
            _patient_ui_evidence_paths(ctx, str(patient_ui))
        if cohort_api:
            _cohort_api_evidence_path(ctx, str(cohort_api))
        if cohort_ui:
            _cohort_ui_evidence_path(ctx, str(cohort_ui))

        duplicate_group = str(meta.get("duplicate_group") or "")
        surfaces = [value for value in str(meta.get("surface") or "").split(",") if value]
        if "recommended_actions" in duplicate_group:
            if not surfaces:
                raise ValueError(f"{callable_name}: recommended-actions group lacks surfaces")
            missing_actions = sorted(set(surfaces) - action_surfaces)
            missing_links = sorted(set(surfaces) - set(deep_links))
            if missing_actions or missing_links:
                raise ValueError(
                    f"{callable_name}: recommended-actions surface drift: "
                    f"missing_actions={missing_actions}, missing_deep_links={missing_links}"
                )
        if patient_ui == "RecommendedActionsPanel":
            missing_actions = sorted(set(surfaces) - action_surfaces)
            if missing_actions:
                raise ValueError(
                    f"{callable_name}: recommended-actions panel surface drift: {missing_actions}"
                )

        money = str(meta.get("money") or "")
        money_fields = list(meta.get("money_fields") or [])
        included = bool(meta.get("included"))
        finding_type = str(meta.get("finding_type") or "")
        if money not in LOCKED_DEFINITIONS["money_semantics"]:
            raise ValueError(f"{callable_name}: unknown money semantics {money!r}")
        if money in {"priced_opportunity", "priced_exposure"} and not money_fields:
            raise ValueError(f"{callable_name}: priced finding lacks money_fields")
        if money == "unpriced_compliance" and (money_fields or included):
            raise ValueError(f"{callable_name}: unpriced compliance cannot carry/count money")
        if (patient_visible or cohort_visible) and money == "informational" and included:
            raise ValueError(
                f"{callable_name}: informational visible finding cannot count in totals"
            )
        if included and money not in {"priced_opportunity", "priced_exposure"} and finding_type not in {
            "aggregate",
            "internal",
        }:
            raise ValueError(
                f"{callable_name}: included_in_totals is incompatible with money={money}, "
                f"finding_type={finding_type}"
            )


def _metadata_evidence_files(ctx: AuditContext, meta: dict[str, Any]) -> list[str]:
    paths: set[Path] = set()
    surfaces = [value for value in str(meta.get("surface") or "").split(",") if value]
    if set(surfaces) & discover_recommended_action_surfaces(ctx):
        paths.add(ctx.billing_actions_path)
    if set(surfaces) & set(discover_deep_link_sections(ctx)):
        paths.add(ctx.recommended_actions_path)
    patient_ui = meta.get("patient_ui")
    if patient_ui:
        paths.update(_patient_ui_evidence_paths(ctx, str(patient_ui)))
    cohort_api = meta.get("cohort_api")
    if cohort_api:
        paths.add(_cohort_api_evidence_path(ctx, str(cohort_api)))
    cohort_ui = meta.get("cohort_ui")
    if cohort_ui:
        paths.add(_cohort_ui_evidence_path(ctx, str(cohort_ui)))
    return sorted(ctx.relative_path(path) for path in paths)


def _all_discovered_by_name(calls: Iterable[RuntimeCall]) -> dict[str, RuntimeCall]:
    return {row.callable: row for row in calls}


def resolve_emissions(ctx: AuditContext,
    row: RuntimeCall,
    all_calls: dict[str, RuntimeCall],
    *,
    _seen: frozenset[str] = frozenset(),
) -> list[str]:
    if row.callable in NON_EMITTING_RUNTIME_HELPERS:
        return []
    focused_specs, non_emitting = _focused_specs(ctx)
    if row.callable in focused_specs:
        return sorted(
            rule_id for rule_id, _ in focused_specs[row.callable] if rule_id not in non_emitting
        )
    if row.callable in {"project_focused_legacy_rows", "project_full_wavea_evidence"}:
        broad_ids = (
            {
                rule_id
                for detector in BROAD_WRAPPED_CALLS.values()
                for filename in ARTIFACTS_BY_CALLABLE[detector]
                for rule_id in _artifact_rule_ids(ctx, filename)
            }
            if row.callable == "project_full_wavea_evidence" else set()
        )
        return sorted(
            broad_ids | {
                rule_id
                for specs in focused_specs.values()
                for rule_id, _ in specs
                if rule_id not in non_emitting
            }
        )
    if row.callable in _seen:
        return []
    seen = _seen | {row.callable}
    values = set(EMISSION_OVERRIDES.get(row.callable, ()))
    values.update(_canonical_evaluator_emissions(ctx, row.module, row.callable))
    artifact_values: set[str] = set()
    for filename in ARTIFACTS_BY_CALLABLE.get(row.callable, ()):
        artifact_values.update(_artifact_rule_ids(ctx, filename))
    if artifact_values:
        values.update(artifact_values)
    else:
        values.update(_static_emissions(ctx, row.module, row.callable))
    for source_name in GENERIC_SURFACE_EMISSION_SOURCES.get(row.callable, ()):
        source = all_calls.get(source_name)
        if source is None:
            raise ValueError(
                f"generic surface emission source drift: {row.callable}->{source_name}"
            )
        values.update(resolve_emissions(ctx, source, all_calls, _seen=seen))
    if row.callable == "project_claim_compliance":
        values.update(
            rule_id
            for specs in focused_specs.values()
            for rule_id, disposition in specs
            if rule_id not in non_emitting
            and disposition in {"unpriced_compliance", "drug_quantity"}
        )
    for equivalent in EQUIVALENT_EMISSIONS.get(row.callable, ()):
        other = all_calls.get(equivalent)
        if other is not None:
            values.update(resolve_emissions(ctx, other, all_calls, _seen=seen))
    if not values and row.entrypoint == "compute_patient_billing_report":
        meta = PATIENT_REPORT_META.get(row.callable, {})
        if meta.get("visibility") not in {"not_applicable"}:
            field = REPORT_FIELD_OVERRIDES.get(row.callable)
            if not field and row.report_fields:
                field = "+".join(row.report_fields)
            values.add(f"kind:{field or row.callable}")
    if not values and row.entrypoint == "analyze_claim":
        values.add(f"kind:{row.callable}")
    return sorted(values)


def _required_inputs(row: RuntimeCall) -> list[str]:
    text = " ".join(row.gates)
    required: set[str] = {"claim_context"} if row.entrypoint == "analyze_claim" else set()
    for needle, label in (
        ("patient_id", "patient_id"),
        ("procedure_lines", "procedure_lines"),
        ("drug_lines", "drug_lines"),
        ("material_lines", "material_lines"),
        ("claims", "claim_headers"),
    ):
        if needle in text:
            required.add(label)
    if row.entrypoint == "compute_patient_billing_report" and row.callable not in {
        "project_claim_compliance",
        "set_missing_inputs_report",
        "finalize_report_totals",
        "finalize_report_exactness",
    }:
        required.add("claim_context")
    return sorted(required)


def _top_level_rule_sets(ctx: AuditContext) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted(ctx.prose_rules_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("rules"), list):
            continue
        rule_set_id = payload.get("rule_set_id")
        if not rule_set_id:
            continue
        result.append(
            {
                "path": ctx.relative_path(path),
                "rule_set_id": str(rule_set_id),
                "rule_count": len(payload["rules"]),
            }
        )
    return result


def _registry_matches(row: RuntimeCall, registry: list[dict[str, Any]]) -> list[str]:
    source_path = row.module.replace(".", "/") + ".py"
    return sorted(
        str(entry["rule_id"])
        for entry in registry
        if source_path in tuple(entry.get("domain_modules") or ())
    )


def _runtime_row(ctx: AuditContext,
    row: RuntimeCall,
    registry: list[dict[str, Any]],
    all_calls: dict[str, RuntimeCall],
) -> dict[str, Any]:
    registry_ids = _registry_matches(row, registry)
    module_path = row.module.replace(".", "/") + ".py"
    artifacts = [f"data/gazette/prose_rules/{name}" for name in ARTIFACTS_BY_CALLABLE.get(row.callable, ())]
    focused_specs, _ = _focused_specs(ctx)
    legacy_monetary_hint_unconfirmed = (
        row.entrypoint == "analyze_claim"
        and any(
            disposition == "financial_review"
            for _, disposition in focused_specs.get(row.callable, ())
        )
    )

    if row.entrypoint == "analyze_claim":
        meta = {
            "surface": None,
            "finding_type": "compliance",
            "patient_ui": None,
            "cohort_api": None,
            "cohort_ui": None,
            "money": "unpriced_compliance",
            "money_fields": [],
            "included": False,
            "visibility": "hidden_runtime",
            "duplicate_group": None,
            "duplicate_status": "none",
            "hidden_reason": (
                "The flat analyze_claim result is not projected into BillingActionReport. "
                "Equivalent semantic findings may still be visible through an independently re-run billing adapter."
            ),
        }
    else:
        meta = {
            "surface": None,
            "finding_type": "informational",
            "patient_ui": None,
            "cohort_api": None,
            "cohort_ui": None,
            "money": "informational",
            "money_fields": [],
            "included": False,
            "visibility": "hidden_runtime",
            "duplicate_group": None,
            "duplicate_status": "none",
            "hidden_reason": "Runtime output has no verified product finding surface.",
            **PATIENT_REPORT_META.get(row.callable, {}),
        }
        if meta.get("visibility") in {
            "patient_visible",
            "cohort_visible",
            "patient_and_cohort_visible",
        }:
            meta["hidden_reason"] = None
    if legacy_monetary_hint_unconfirmed:
        meta.update(
            finding_type="financial review (legacy raw)",
            money="informational",
            hidden_reason=(
                "Legacy raw rows may carry an unverified amount hint; the focused financial-review "
                "projection sets confirmed amount to null and the current API draft gate hides it."
            ),
        )

    report_field = REPORT_FIELD_OVERRIDES.get(row.callable)
    if report_field is None:
        report_field = ",".join(row.report_fields) or None
    gates = list(row.gates)
    required_inputs = _required_inputs(row)
    if row.entrypoint == "compute_patient_billing_report" and "claim_context" in required_inputs:
        gates = [
            "claim_context is not None (enforced by early return/assert)"
            if gate == "always"
            else f"claim_context is not None AND {gate}"
            for gate in gates
        ]

    deep_link_map = discover_deep_link_sections(ctx)
    surface_text = str(meta.get("surface") or "")
    deep_link_sections = sorted(
        {
            deep_link_map[surface]
            for surface in surface_text.split(",")
            if surface in deep_link_map
        }
    )

    regulatory: list[str] = []
    for entry in registry:
        if str(entry.get("rule_id")) not in registry_ids:
            continue
        regulatory.extend(str(item) for item in tuple(entry.get("sut_section_prefixes") or ()))
        regulatory.extend(str(item) for item in tuple(entry.get("annex_refs") or ()))
    if not regulatory:
        regulatory.extend(ARTIFACTS_BY_CALLABLE.get(row.callable, ()))

    evidence = [
        ctx.relative_path(ctx.engine_path if row.entrypoint == "analyze_claim" else ctx.patient_report_path),
        module_path,
        *artifacts,
    ]
    if row.entrypoint == "analyze_claim" and row.callable in _focused_specs(ctx)[0]:
        evidence.append(ctx.relative_path(ctx.focused_materializer_path))
    if row.entrypoint == "compute_patient_billing_report":
        evidence.extend(_metadata_evidence_files(ctx, meta))

    emissions = resolve_emissions(ctx, row, all_calls)
    focused_confirmed = {
        rule_id
        for specs in focused_specs.values()
        for rule_id, disposition in specs
        if disposition in {"unpriced_compliance", "drug_quantity"}
    }
    draft_hidden = (
        sorted(focused_confirmed & set(emissions))
        if row.callable == "project_claim_compliance"
        else []
    )

    return {
        "inventory_level": "runtime_detector",
        "registry_rule_id": registry_ids,
        "runtime_id": f"{row.entrypoint}:{row.callable}",
        "callable": f"{row.module}.{row.callable}",
        "entrypoint": row.entrypoint,
        "runtime_status": "gated" if gates != ["always"] else "executed",
        "gating_condition": " OR ".join(dict.fromkeys(gates)) if gates else "always within entrypoint",
        "required_inputs": required_inputs,
        "emitted_rule_ids_or_kinds": emissions,
        **(
            {
                "public_emitted_rule_ids_or_kinds": sorted(set(emissions) - set(draft_hidden)),
                "draft_hidden_emitted_rule_ids_or_kinds": draft_hidden,
                "public_visibility_gate": "complete-25-v1",
            }
            if draft_hidden
            else {}
        ),
        "report_field": report_field,
        "recommended_action_surface": meta.get("surface"),
        "finding_type": meta.get("finding_type"),
        "cohort_api_surface": meta.get("cohort_api"),
        "patient_ui_surface": meta.get("patient_ui"),
        "patient_deep_link_sections": deep_link_sections,
        "cohort_ui_surface": meta.get("cohort_ui"),
        "money_semantics": meta.get("money"),
        "money_fields": list(meta.get("money_fields") or []),
        "legacy_monetary_hint_unconfirmed": legacy_monetary_hint_unconfirmed,
        "included_in_totals": bool(meta.get("included")),
        "visibility_status": meta.get("visibility"),
        "duplicate_group": meta.get("duplicate_group"),
        "duplicate_status": meta.get("duplicate_status", "none"),
        "hidden_reason": meta.get("hidden_reason"),
        "regulatory_source": sorted(set(regulatory)),
        "catalog_visible": bool(registry_ids),
        "mapping_status": "mapped" if registry_ids else "runtime_without_registry_family",
        "evidence_files": sorted(set(evidence)),
        "source_lines": list(row.lines),
    }


def _registry_only_rows(
    registry: list[dict[str, Any]],
    runtime_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mapped = {rule_id for row in runtime_rows for rule_id in row["registry_rule_id"]}
    result: list[dict[str, Any]] = []
    for entry in registry:
        rule_id = str(entry["rule_id"])
        if rule_id in mapped:
            continue
        result.append(
            {
                "inventory_level": "registry_rule_family",
                "registry_rule_id": [rule_id],
                "runtime_id": None,
                "callable": None,
                "entrypoint": None,
                "runtime_status": "registry_only",
                "gating_condition": None,
                "required_inputs": [],
                "emitted_rule_ids_or_kinds": [],
                "report_field": None,
                "recommended_action_surface": None,
                "finding_type": None,
                "cohort_api_surface": None,
                "patient_ui_surface": None,
                "patient_deep_link_sections": [],
                "cohort_ui_surface": None,
                "money_semantics": "informational",
                "money_fields": [],
                "included_in_totals": False,
                "visibility_status": "not_applicable",
                "duplicate_group": None,
                "duplicate_status": "none",
                "hidden_reason": "Registry metadata has no verified invocation from either canonical runtime entrypoint.",
                "regulatory_source": sorted(
                    {
                        *[str(value) for value in tuple(entry.get("sut_section_prefixes") or ())],
                        *[str(value) for value in tuple(entry.get("annex_refs") or ())],
                    }
                ),
                "catalog_visible": True,
                "mapping_status": "registry_only",
                "evidence_files": ["src/bilun/domain/sut/rule_registry.py"],
                "source_lines": [],
            }
        )
    return result


def _artifact_only_rows(rule_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    consumed = {
        f"data/gazette/prose_rules/{filename}"
        for filenames in ARTIFACTS_BY_CALLABLE.values()
        for filename in filenames
    }
    result: list[dict[str, Any]] = []
    for item in rule_sets:
        if item["path"] in consumed:
            continue
        result.append(
            {
                "inventory_level": "artifact_rule_set",
                "registry_rule_id": [],
                "runtime_id": None,
                "callable": None,
                "entrypoint": None,
                "runtime_status": "artifact_only",
                "gating_condition": None,
                "required_inputs": [],
                "emitted_rule_ids_or_kinds": [],
                "report_field": None,
                "recommended_action_surface": None,
                "finding_type": None,
                "cohort_api_surface": None,
                "patient_ui_surface": None,
                "patient_deep_link_sections": [],
                "cohort_ui_surface": None,
                "money_semantics": "informational",
                "money_fields": [],
                "included_in_totals": False,
                "visibility_status": "not_applicable",
                "duplicate_group": None,
                "duplicate_status": "none",
                "hidden_reason": "Top-level authored prose rule set has no verified canonical runtime consumer.",
                "regulatory_source": [item["rule_set_id"]],
                "catalog_visible": False,
                "mapping_status": "artifact_only",
                "evidence_files": [item["path"]],
                "source_lines": [],
                "artifact_rule_count": item["rule_count"],
            }
        )
    return result


def _independent_rerun_debt(ctx: AuditContext,
    runtime_calls: list[RuntimeCall],
    all_calls: dict[str, RuntimeCall],
) -> dict[str, Any]:
    relationships: list[dict[str, Any]] = []
    all_overlap: set[str] = set()
    for adapter_name, analyzer_names in sorted(EQUIVALENT_EMISSIONS.items()):
        adapter = all_calls.get(adapter_name)
        if adapter is None or adapter.entrypoint != "compute_patient_billing_report":
            raise ValueError(f"stale independent-rerun adapter metadata: {adapter_name}")
        adapter_emissions = set(resolve_emissions(ctx, adapter, all_calls))
        direct_calls = _direct_calls_in_callable(ctx, adapter)
        for analyzer_name in analyzer_names:
            analyzer = next(
                (
                    row
                    for row in runtime_calls
                    if row.entrypoint == "analyze_claim"
                    and row.callable == analyzer_name
                ),
                None,
            )
            if analyzer is None:
                raise ValueError(
                    f"stale independent-rerun analyzer metadata: {adapter_name}->{analyzer_name}"
                )
            analyzer_emissions = set(resolve_emissions(ctx, analyzer, all_calls))
            overlap = sorted(adapter_emissions & analyzer_emissions)
            if not overlap:
                raise ValueError(
                    f"independent-rerun emission drift: {adapter_name}->{analyzer_name} has no overlap"
                )
            all_overlap.update(overlap)
            flags = ["independent_rerun"]
            relationships.append(
                {
                    "analyzer_runtime_id": f"analyze_claim:{analyzer_name}",
                    "adapter_runtime_id": f"compute_patient_billing_report:{adapter_name}",
                    "overlap_count": len(overlap),
                    "overlap_rule_ids_or_kinds": overlap,
                    "architectural_debt": True,
                    "debt_flags": flags,
                    "direct_source_call": analyzer_name in direct_calls,
                    "classification_basis": (
                        "source_direct_call"
                        if analyzer_name in direct_calls
                        else "manual_semantic_equivalence_with_fail_closed_runtime_and_emission_validation"
                    ),
                    "evidence_files": sorted(
                        {
                            ctx.relative_path(ctx.engine_path),
                            ctx.relative_path(ctx.patient_report_path),
                            analyzer.module.replace(".", "/") + ".py",
                            adapter.module.replace(".", "/") + ".py",
                        }
                    ),
                    "analyzer_source_lines": list(analyzer.lines),
                    "adapter_source_lines": list(adapter.lines),
                }
            )
    return {
        "relationship_count": len(relationships),
        "distinct_overlap_rule_ids_or_kinds": len(all_overlap),
        "relationships": relationships,
    }


def _semantic_rollup(runtime_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_emission: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in runtime_rows:
        for emission in row["emitted_rule_ids_or_kinds"]:
            by_emission[emission].append(row)

    result: dict[str, dict[str, Any]] = {}
    for emission, rows in sorted(by_emission.items()):
        public_rows = [
            row
            for row in rows
            if emission
            in row.get("public_emitted_rule_ids_or_kinds", row["emitted_rule_ids_or_kinds"])
        ]
        statuses = {row["visibility_status"] for row in public_rows}
        patient = bool(statuses & {"patient_visible", "patient_and_cohort_visible"})
        cohort = bool(statuses & {"cohort_visible", "patient_and_cohort_visible"})
        hidden = not patient and not cohort and "aggregate_only" not in statuses
        aggregate_only = not patient and not cohort and "aggregate_only" in statuses
        financial = any(
            row["money_semantics"] in {"priced_opportunity", "priced_exposure"}
            for row in rows
        )
        duplicates = [
            row
            for row in public_rows
            if row["duplicate_status"] != "none"
            and row["visibility_status"]
            in {"patient_visible", "cohort_visible", "patient_and_cohort_visible"}
        ]
        result[emission] = {
            "patient_visible": patient,
            "cohort_visible": cohort,
            "hidden_runtime": hidden,
            "aggregate_only": aggregate_only,
            "financial": financial,
            "duplicate_surfaced": bool(duplicates),
            "duplicate_surface_runtime_ids": sorted(
                {row["runtime_id"] for row in duplicates}
            ),
            "runtime_ids": sorted({row["runtime_id"] for row in rows}),
        }
    return result


def _counts(registry: list[dict[str, Any]], runtime_rows: list[dict[str, Any]], semantic: dict[str, dict[str, Any]]) -> dict[str, int]:
    return {
        "registry_rule_families": len(registry),
        "runtime_detectors_adapters": len(runtime_rows),
        "distinct_emitted_rule_ids_or_kinds": len(semantic),
        "patient_visible_findings": sum(1 for value in semantic.values() if value["patient_visible"]),
        "cohort_visible_findings": sum(1 for value in semantic.values() if value["cohort_visible"]),
        "hidden_runtime_findings": sum(1 for value in semantic.values() if value["hidden_runtime"]),
        "aggregate_only_findings": sum(1 for value in semantic.values() if value["aggregate_only"]),
        "duplicate_surfaced_findings": sum(1 for value in semantic.values() if value["duplicate_surfaced"]),
        "financial_findings": sum(1 for value in semantic.values() if value["financial"]),
        "nonfinancial_findings": sum(1 for value in semantic.values() if not value["financial"]),
    }


def _claim_compliance_surface(ctx: AuditContext, runtime_calls: list[RuntimeCall]) -> dict[str, Any]:
    evaluator_runtime_ids = sorted(
        f"{row.entrypoint}:{row.callable}"
        for row in runtime_calls
        if row.callable == "evaluate_rule_findings"
    )
    projection_runtime_id = "compute_patient_billing_report:project_claim_compliance"
    if len(evaluator_runtime_ids) != 2:
        raise ValueError(
            "claim-compliance canonical evaluator drift: "
            f"expected two entrypoint uses, found {evaluator_runtime_ids}"
        )
    if not any(
        f"{row.entrypoint}:{row.callable}" == projection_runtime_id
        for row in runtime_calls
    ):
        raise ValueError("claim-compliance generic projection drift: projector call missing")
    return {
        "canonical_evaluator_runtime_ids": evaluator_runtime_ids,
        "generic_projection_runtime_id": projection_runtime_id,
        "generic_cohort_projection": f"{ctx.relative_path(ctx.cohort_compliance_path)}::_claim_projection",
        "projection_contract": (
            "serialized RuleFinding/RuleEvaluation rows are projected generically; "
            "no rule-ID allowlist controls patient or cohort projection"
        ),
    }


def build_audit(ctx: AuditContext) -> dict[str, Any]:
    analyze = discover_runtime_calls(ctx, ctx.engine_path, "analyze_claim")
    report = discover_runtime_calls(ctx, ctx.patient_report_path, "compute_patient_billing_report")
    assert_known_runtime_calls("analyze_claim", analyze)
    assert_known_runtime_calls("compute_patient_billing_report", report)
    validate_explicit_metadata(ctx, report)
    _validate_focused_report_dataflow(ctx)

    runtime_calls = sorted([*analyze, *report], key=lambda row: (row.entrypoint, row.callable))
    all_calls = _all_discovered_by_name(runtime_calls)
    rerun_debt = _independent_rerun_debt(ctx, runtime_calls, all_calls)
    registry = _load_registry(ctx)
    runtime_rows = [_runtime_row(ctx, row, registry, all_calls) for row in runtime_calls]
    registry_only = _registry_only_rows(registry, runtime_rows)
    artifact_only = _artifact_only_rows(_top_level_rule_sets(ctx))
    semantic = _semantic_rollup(runtime_rows)

    status_breakdown: dict[str, int] = defaultdict(int)
    for entry in registry:
        status_breakdown[str(entry.get("coverage_status") or "unknown")] += 1

    focused_specs, non_emitting = _focused_specs(ctx)
    focused_current = {
        rule_id
        for specs in focused_specs.values()
        for rule_id, _ in specs
        if rule_id not in non_emitting
    }
    focused_confirmed_candidates = {
        rule_id
        for specs in focused_specs.values()
        for rule_id, disposition in specs
        if rule_id not in non_emitting
        and disposition in {"unpriced_compliance", "drug_quantity"}
    }
    broad_ids = {
        rule_id
        for detector in BROAD_WRAPPED_CALLS.values()
        for filename in ARTIFACTS_BY_CALLABLE[detector]
        for rule_id in _artifact_rule_ids(ctx, filename)
    }
    if len(BROAD_WRAPPED_CALLS) != 7 or len(broad_ids) != 496:
        raise ValueError("Broad Wave A authored family or identity roster drift")

    return {
        "schema_version": 4,
        "audit_date": "2026-09-27",
        "source_revision": "wavea-current-working-tree-checkpoint",
        "canonical_entrypoints": [
            "src/bilun/domain/billing/engine.py::analyze_claim",
            "src/bilun/domain/billing/patient_report.py::compute_patient_billing_report",
        ],
        "product_projection_entrypoints": [
            "src/bilun/domain/billing/billing_actions.py::collect_billing_actions",
            "src/bilun/domain/billing/claim_compliance.py::project_claim_compliance",
            "src/bilun/domain/billing/cohort_compliance.py::build_cohort_compliance_index",
        ],
        "claim_compliance_surface": _claim_compliance_surface(ctx, runtime_calls),
        "focused_wavea_checkpoint": {
            "detector_groups": len(focused_specs),
            "tracked_rule_ids": sum(len(specs) for specs in focused_specs.values()),
            "currently_detector_emittable_rule_ids": len(focused_current),
            "non_emitting_unavailable_rule_ids": sorted(non_emitting),
            "potential_confirmed_unpriced_rule_ids": sorted(focused_confirmed_candidates),
            "review_and_financial_evidence_visibility": "draft_gate_hidden",
            "release_ready": False,
        },
        "broad_wavea_checkpoint": {
            "detector_groups": len(BROAD_WRAPPED_CALLS),
            "authored_rule_ids": len(broad_ids),
            "review_and_financial_evidence_visibility": "draft_gate_hidden",
            "release_ready": False,
        },
        "locked_definitions": LOCKED_DEFINITIONS,
        "registry_status_breakdown": dict(sorted(status_breakdown.items())),
        "independent_rerun_debt": rerun_debt,
        "counts": _counts(registry, runtime_rows, semantic),
        "rows": [*runtime_rows, *registry_only, *artifact_only],
        "semantic_findings": semantic,
    }
