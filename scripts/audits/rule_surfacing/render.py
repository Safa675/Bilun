"""Render for the deterministic rule-surfacing audit."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from typing import Any


def _markdown_list(values: Iterable[str]) -> str:
    values = list(values)
    return ", ".join(f"`{value}`" for value in values) if values else "—"


def render_report(audit: dict[str, Any]) -> str:
    counts = audit["counts"]
    rows = audit["rows"]
    runtime_rows = [row for row in rows if row["inventory_level"] == "runtime_detector"]
    semantic = audit["semantic_findings"]
    rerun_debt = audit["independent_rerun_debt"]

    lines = [
        "# Rule Engine → Product Surface Current Wave A Checkpoint",
        "",
        f"Source state: `{audit['source_revision']}` ({audit['audit_date']}). This is a source checkpoint, not a deployed-release claim. Audit taxonomy is frozen by `scripts/audits/build_rule_surfacing_inventory.py`.",
        "",
        "## Current Wave A scope",
        "",
        (
            f"The focused materializer reaches **{audit['focused_wavea_checkpoint']['detector_groups']}** detector groups. "
            f"Its projection tracks **{audit['focused_wavea_checkpoint']['tracked_rule_ids']}** stable rule IDs, "
            f"of which **{audit['focused_wavea_checkpoint']['currently_detector_emittable_rule_ids']}** can currently be emitted by detectors. "
            "The remaining historical IDs have explicit unavailable evaluations: "
            + _markdown_list(audit['focused_wavea_checkpoint']['non_emitting_unavailable_rule_ids'])
            + "."
        ),
        "",
        (
            f"The broad materializer reaches **{audit['broad_wavea_checkpoint']['detector_groups']}** "
            f"groups with **{audit['broad_wavea_checkpoint']['authored_rule_ids']}** authored IDs. "
            "It records evaluated and unavailable statuses; positive, review, financial, and "
            "confirmed unpriced outputs remain separately classified. Its new patient/cohort "
            "evidence is draft-gated until the complete-25-v1 release activation."
        ),
        "",
        f"Only **{len(audit['focused_wavea_checkpoint']['potential_confirmed_unpriced_rule_ids'])}** focused IDs are candidates for confirmed, unpriced claim compliance after source and input gates. "
        "They enter the in-memory generic projection, but the current patient, bill, and cohort APIs hide them until the complete-25-v1 activation gate. "
        "Focused review and financial-review evidence is a draft persisted capability and remains hidden by the same gate. "
        "It contributes no confirmed TRY amount or existing report total. This checkpoint does not certify a complete 25-family release.",
        "",
        f"Relative to the 2026-09-18 baseline, the runtime row count changes from **73** to **{counts['runtime_detectors_adapters']}**: ownership, focused and broad materialization, batch, validation, and projection stages were added. The seven broad detectors remain in the static runtime inventory through their wrapper. "
        "The distinct ID/kind count changes from **1,924** to **1,933** because twelve specific radiation identities replace one generic radiation kind, while the corrected admission-window and exam-date detectors no longer claim to emit findings. "
        "Those two historical identities remain in the 32-ID unavailable evaluation roster.",
        "",
        "## Exact counts",
        "",
        f"1. Registry rule families: **{counts['registry_rule_families']}**",
        f"2. Runtime detectors/adapters: **{counts['runtime_detectors_adapters']}**",
        f"3. Distinct emitted rule IDs/kinds: **{counts['distinct_emitted_rule_ids_or_kinds']}**",
        f"4. Patient-visible findings: **{counts['patient_visible_findings']}**",
        f"5. Cohort-visible findings: **{counts['cohort_visible_findings']}**",
        f"6. Hidden runtime findings: **{counts['hidden_runtime_findings']}**",
        f"7. Aggregate-only findings: **{counts['aggregate_only_findings']}**",
        f"8. Duplicate-surfaced findings: **{counts['duplicate_surfaced_findings']}**",
        f"9. Financial findings: **{counts['financial_findings']}**",
        f"10. Nonfinancial findings: **{counts['nonfinancial_findings']}**",
        "",
        "## Canonical claim-compliance architecture",
        "",
        "Canonical evaluator stages: "
        + _markdown_list(audit["claim_compliance_surface"]["canonical_evaluator_runtime_ids"])
        + ".",
        "Generic patient projection: "
        + f"`{audit['claim_compliance_surface']['generic_projection_runtime_id']}`.",
        "Generic cohort projection: "
        + f"`{audit['claim_compliance_surface']['generic_cohort_projection']}`.",
        audit["claim_compliance_surface"]["projection_contract"] + ".",
        "",
        f"Registry coverage breakdown: `{audit['registry_status_breakdown']}`. Registry rows are metadata and do not satisfy finding visibility.",
        "",
        "## Runtime/family matrix",
        "",
        "| runtime/family | emitted rule/kind | patient UI | cohort UI | financiality | visibility | duplicate | notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in runtime_rows:
        emissions = row["emitted_rule_ids_or_kinds"]
        emission_text = f"{len(emissions)} id(s)" if len(emissions) > 3 else ", ".join(emissions) or "—"
        notes = row["hidden_reason"] or ("registry=" + ",".join(row["registry_rule_id"]) if row["registry_rule_id"] else "no registry family")
        if row.get("draft_hidden_emitted_rule_ids_or_kinds"):
            notes += (
                f"; {len(row['draft_hidden_emitted_rule_ids_or_kinds'])} in-memory ID(s) "
                f"are publicly hidden until {row['public_visibility_gate']}"
            )
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['runtime_id']}`",
                    emission_text.replace("|", "\\|"),
                    str(row["patient_ui_surface"] or "—").replace("|", "\\|"),
                    str(row["cohort_ui_surface"] or "—").replace("|", "\\|"),
                    row["money_semantics"],
                    row["visibility_status"],
                    row["duplicate_status"],
                    str(notes).replace("|", "\\|"),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "Required inputs below are canonical-entrypoint gate inputs. "
            "Every `analyze_claim` row requires `claim_context`; gate-derived fields are additive. "
            "This static audit does not claim that internal medical preconditions were dynamically exercised.",
        ]
    )
    hidden_ids = [key for key, value in semantic.items() if value["hidden_runtime"]]
    lines.extend(["", "## Hidden runtime findings — complete semantic list", ""])
    if not hidden_ids:
        lines.append("None.")
    else:
        for row in runtime_rows:
            row_hidden = [
                emission
                for emission in row["emitted_rule_ids_or_kinds"]
                if semantic[emission]["hidden_runtime"]
            ]
            if not row_hidden:
                continue
            lines.append(
                f"- `{row['runtime_id']}` — required inputs: {_markdown_list(row['required_inputs'])}; "
                f"reason: {row['hidden_reason'] or 'no verified patient/cohort surface'}. "
                f"Hidden IDs/kinds ({len(row_hidden)}): {_markdown_list(row_hidden)}"
            )

    lines.extend(["", "## Independent rerun architecture debt", ""])
    lines.append(
        f"Declared analyzer→adapter reruns: **{rerun_debt['relationship_count']}** relationships covering "
        f"**{rerun_debt['distinct_overlap_rule_ids_or_kinds']}** distinct semantic IDs/kinds. "
        "These overlaps describe independent execution paths and are not duplicate-surface findings by themselves."
    )
    lines.append("")
    lines.append(
        "Relationships marked `source_direct_call` are verified as direct calls in the adapter source. "
        "Other relationships retain an explicit manual semantic-equivalence classification, but fail closed if either "
        "canonical runtime callable disappears or their declared semantic overlap becomes empty."
    )
    for relationship in rerun_debt["relationships"]:
        lines.append(
            f"- `{relationship['analyzer_runtime_id']}` → `{relationship['adapter_runtime_id']}` — "
            f"overlap={relationship['overlap_count']}; basis={relationship['classification_basis']}; "
            f"debt={_markdown_list(relationship['debt_flags'])}; "
            f"evidence={_markdown_list(relationship['evidence_files'])}."
        )

    duplicate_rows = [row for row in runtime_rows if row["duplicate_status"] != "none"]
    lines.extend(["", "## Duplicate groups", ""])
    lines.append(
        "Duplicate-surfaced findings are derived only from explicit product-surface duplicate groups on visible rows. "
        "Independent analyzer→adapter reruns above do not create duplicate-surface counts unless a visible row also "
        "documents the same finding on multiple product surfaces."
    )
    if not duplicate_rows:
        lines.append("None.")
    else:
        by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in duplicate_rows:
            by_group[str(row["duplicate_group"])].append(row)
        for group, group_rows in sorted(by_group.items()):
            emissions = sorted({value for row in group_rows for value in row["emitted_rule_ids_or_kinds"]})
            statuses = sorted({row["duplicate_status"] for row in group_rows})
            financial_risk = any(status == "financial_double_count_risk" for status in statuses)
            surfaces = sorted(
                {
                    value
                    for row in group_rows
                    for value in (
                        row["recommended_action_surface"],
                        row["patient_ui_surface"],
                        row["cohort_ui_surface"],
                    )
                    if value
                }
            )
            lines.append(
                f"- `{group}` — status={','.join(statuses)}; financial-double-count-risk={str(financial_risk).lower()}; "
                f"surfaces={_markdown_list(surfaces)}; findings ({len(emissions)}): {_markdown_list(emissions)}"
            )

    registry_only = [row for row in rows if row["runtime_status"] == "registry_only"]
    artifact_only = [row for row in rows if row["runtime_status"] == "artifact_only"]
    lines.extend(["", "## Registry-only / artifact-only entries", ""])
    lines.append(
        "Registry-only families: "
        + _markdown_list(row["registry_rule_id"][0] for row in registry_only)
    )
    lines.append("")
    lines.append(
        "Artifact-only top-level prose rule sets: "
        + _markdown_list(
            f"{row['regulatory_source'][0]} ({row.get('artifact_rule_count', 0)} rules)"
            for row in artifact_only
        )
    )

    unknown = [
        row
        for row in runtime_rows
        if row["mapping_status"] != "mapped"
        or any(value.startswith("kind:detect_") or value.startswith("kind:check_") for value in row["emitted_rule_ids_or_kinds"])
    ]
    lines.extend(["", "## Unknown / ambiguous mappings", ""])
    if not unknown:
        lines.append("None.")
    else:
        for row in unknown:
            lines.append(
                f"- `{row['runtime_id']}` — mapping={row['mapping_status']}; "
                f"emitted={_markdown_list(row['emitted_rule_ids_or_kinds'])}. No registry mapping is forced."
            )

    lines.extend(
        [
            "",
            "## Audit interpretation",
            "",
            "`analyze_claim` and `compute_patient_billing_report` are independent canonical runtime roots. "
            "A hidden `analyze_claim` output is not counted as a hidden semantic finding when the same emitted ID is verified visible through a billing adapter; the semantic rollup de-duplicates those IDs. "
            "Independent rerun overlap is recorded separately from duplicate product surfacing. Aggregate-only report blocks remain separate from hidden row-level findings. Rule Database/registry visibility is catalog metadata only.",
            "",
            "Patient/cohort visibility classifications remain explicit audit metadata where architectural judgment is required. "
            "The generator validates that every patient-report runtime callable has exactly one current metadata entry, "
            "that referenced UI/API tokens still exist in source, and that recommended-action duplicate groups still map "
            "to emitted backend action surfaces and frontend deep links. It does not treat a shared evidence-file list as proof.",
            "",
            "The artifact-only inventory is intentionally bounded to top-level `data/gazette/prose_rules/*.json` files that contain both a `rule_set_id` and a `rules` list. Golden fixtures, schemas, support lookups, and manifests are evidence artifacts rather than independent runtime finding families.",
            "",
        ]
    )
    return "\n".join(lines)


def render_matrix_json(audit: dict[str, Any]) -> str:
    # The semantic rollup is an internal derivation used to compute counts and
    # render the human report.  Persisting it would duplicate every emitted ID
    # already present in the per-runtime matrix rows.
    payload = dict(audit)
    payload.pop("semantic_findings", None)
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _render_chunk(content: str, *, index: int, chunk_lines: int) -> str:
    if index < 0:
        raise ValueError("chunk index must be >= 0")
    if chunk_lines <= 0:
        raise ValueError("chunk_lines must be > 0")
    lines = content.splitlines()
    start = index * chunk_lines
    end = start + chunk_lines
    selected = lines[start:end]
    return "\n".join(selected) + ("\n" if selected else "")
