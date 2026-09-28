"""Deterministic Rule Engine -> Product Surface inventory.

This audit is intentionally static.  It discovers the two canonical runtime
entrypoints from source, reconciles them with the SUT registry and authored
top-level prose rule-set artifacts, and applies explicit product-surface
metadata.  It never executes claim detectors and never touches patient data.

Run in verification mode (no writes):

    python3 scripts/audits/build_rule_surfacing_inventory.py --check

Regenerate the committed outputs deterministically:

    python3 scripts/audits/build_rule_surfacing_inventory.py --write

The committed JSON/Markdown outputs are generated from :func:`build_audit`,
written by the explicit ``--write`` mode, and checked byte-for-byte by unit
tests.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


FRONTEND_SOURCE_ROOT = ROOT / "frontend/src"
ENGINE_PATH = ROOT / "src/bilun/domain/billing/engine.py"
PATIENT_REPORT_PATH = ROOT / "src/bilun/domain/billing/patient_report.py"
FOCUSED_MATERIALIZER_PATH = ROOT / "src/bilun/domain/billing/focused_legacy_materializer.py"
FOCUSED_PROJECTION_PATH = ROOT / "src/bilun/domain/billing/focused_rule_projection.py"
WAVEA_EVIDENCE_PATH = ROOT / "src/bilun/domain/billing/wavea_evidence.py"
REGISTRY_PATH = ROOT / "src/bilun/domain/sut/rule_registry.py"
CLAIM_COMPLIANCE_PATH = ROOT / "src/bilun/domain/billing/claim_compliance.py"
COHORT_COMPLIANCE_PATH = ROOT / "src/bilun/domain/billing/cohort_compliance.py"
RECOMMENDED_ACTIONS_PATH = ROOT / "frontend/src/lib/recommendedActions.ts"
BILLING_ACTIONS_PATH = ROOT / "src/bilun/domain/billing/billing_actions.py"
BILLING_API_PATH = ROOT / "src/bilun/api/routes/billing.py"
ALERTS_API_PATH = ROOT / "src/bilun/api/routes/alerts.py"
COMPLIANCE_API_PATH = ROOT / "src/bilun/api/routes/compliance.py"
WAVEA_GATE_API_PATH = ROOT / "src/bilun/api/routes/wavea_gate.py"
PATIENT_SECTIONS_PATH = ROOT / "frontend/src/components/patient/SutBillingReportSections.tsx"
COMPLIANCE_VIEW_PATH = ROOT / "frontend/src/components/patient/views/ComplianceViewSection.tsx"
REVENUE_VIEW_PATH = ROOT / "frontend/src/components/patient/views/RevenueViewSection.tsx"
AUDIT_VIEW_PATH = ROOT / "frontend/src/components/patient/views/AuditViewSection.tsx"
COHORT_DASHBOARD_PATH = ROOT / "frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.tsx"
PROSE_RULES_DIR = ROOT / "data/gazette/prose_rules"
MATRIX_PATH = ROOT / "reports/rule-engine-surfacing/2026-09-18-rule-surfacing-matrix.json"
REPORT_PATH = ROOT / "reports/rule-engine-surfacing/2026-09-18-rule-surfacing-audit.md"


from scripts.audits.rule_surfacing.model import AuditContext, RuntimeCall as RuntimeCall
from scripts.audits.rule_surfacing.metadata import (
    LOCKED_DEFINITIONS as LOCKED_DEFINITIONS,
    EXPECTED_ANALYZE_CALLS as EXPECTED_ANALYZE_CALLS,
    EXPECTED_REPORT_CALLS as EXPECTED_REPORT_CALLS,
    NON_RUNTIME_IMPORTED_CALLS as NON_RUNTIME_IMPORTED_CALLS,
    BROAD_WRAPPED_CALLS as BROAD_WRAPPED_CALLS,
    NON_EMITTING_RUNTIME_HELPERS as NON_EMITTING_RUNTIME_HELPERS,
    REPORT_FIELD_OVERRIDES as REPORT_FIELD_OVERRIDES,
    ARTIFACTS_BY_CALLABLE as ARTIFACTS_BY_CALLABLE,
    EQUIVALENT_EMISSIONS as EQUIVALENT_EMISSIONS,
    GENERIC_SURFACE_EMISSION_SOURCES as GENERIC_SURFACE_EMISSION_SOURCES,
    EMISSION_OVERRIDES as EMISSION_OVERRIDES,
    PATIENT_REPORT_META as PATIENT_REPORT_META,
)
from scripts.audits.rule_surfacing import python_sources as _python_sources
from scripts.audits.rule_surfacing.python_sources import (
    _resolve_qualified_imports as _resolve_qualified_imports,
    _attribute_parts as _attribute_parts,
    _call_target as _call_target,
    _report_targets as _report_targets,
    _ancestor_if_gates as _ancestor_if_gates,
    _assignment_report_fields as _assignment_report_fields,
    _parse_focused_specs as _parse_focused_specs,
    assert_known_runtime_calls as assert_known_runtime_calls,
    _module_constants as _module_constants,
    _resolve_static_value as _resolve_static_value,
    _static_module_binding as _static_module_binding,
    _UNRESOLVED_STATIC_VALUE as _UNRESOLVED_STATIC_VALUE,
)
from scripts.audits.rule_surfacing import inventory as _inventory
from scripts.audits.rule_surfacing.inventory import (
    _all_discovered_by_name as _all_discovered_by_name,
    _required_inputs as _required_inputs,
    _registry_matches as _registry_matches,
    _registry_only_rows as _registry_only_rows,
    _artifact_only_rows as _artifact_only_rows,
    _semantic_rollup as _semantic_rollup,
    _counts as _counts,
)
from scripts.audits.rule_surfacing.render import (
    _markdown_list as _markdown_list,
    render_report as render_report,
    render_matrix_json as render_matrix_json,
    _render_chunk as _render_chunk,
)
from scripts.audits.rule_surfacing import cli as _cli
from scripts.audits.rule_surfacing import surface_sources as _surface_sources
from scripts.audits.rule_surfacing.surface_sources import SurfaceSourceResolver as SurfaceSourceResolver


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _module_for_path(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def _module_path(module: str) -> Path | None:
    path = ROOT / (module.replace(".", "/") + ".py")
    return path if path.is_file() else None


def _context() -> AuditContext:
    """Read compatibility globals at call time, including fixture overrides."""
    return AuditContext(
        root=ROOT,
        frontend_source_root=FRONTEND_SOURCE_ROOT,
        engine_path=ENGINE_PATH,
        patient_report_path=PATIENT_REPORT_PATH,
        focused_materializer_path=FOCUSED_MATERIALIZER_PATH,
        focused_projection_path=FOCUSED_PROJECTION_PATH,
        wavea_evidence_path=WAVEA_EVIDENCE_PATH,
        registry_path=REGISTRY_PATH,
        claim_compliance_path=CLAIM_COMPLIANCE_PATH,
        cohort_compliance_path=COHORT_COMPLIANCE_PATH,
        recommended_actions_path=RECOMMENDED_ACTIONS_PATH,
        billing_actions_path=BILLING_ACTIONS_PATH,
        billing_api_path=BILLING_API_PATH,
        alerts_api_path=ALERTS_API_PATH,
        compliance_api_path=COMPLIANCE_API_PATH,
        wavea_gate_api_path=WAVEA_GATE_API_PATH,
        patient_sections_path=PATIENT_SECTIONS_PATH,
        compliance_view_path=COMPLIANCE_VIEW_PATH,
        revenue_view_path=REVENUE_VIEW_PATH,
        audit_view_path=AUDIT_VIEW_PATH,
        cohort_dashboard_path=COHORT_DASHBOARD_PATH,
        prose_rules_dir=PROSE_RULES_DIR,
        matrix_path=MATRIX_PATH,
        report_path=REPORT_PATH,
        relative_path=_rel,
        module_for_path=_module_for_path,
        module_path=_module_path,
    )


def _resolve_imports(path: Path, tree: ast.Module) -> dict[str, str]:
    return _python_sources._resolve_imports(_context(), path, tree)


def _focused_specs() -> tuple[dict[str, tuple[tuple[str, str], ...]], frozenset[str]]:
    return _python_sources._focused_specs(_context())


def _focused_materializer_calls() -> dict[str, str]:
    return _python_sources._focused_materializer_calls(_context())


def discover_runtime_calls(path: Path, entrypoint: str) -> list[RuntimeCall]:
    return _python_sources.discover_runtime_calls(_context(), path, entrypoint)


def _validate_focused_report_dataflow() -> None:
    return _python_sources._validate_focused_report_dataflow(_context())


def _direct_imported_calls(path: Path, callable_name: str) -> dict[str, str]:
    return _python_sources._direct_imported_calls(_context(), path, callable_name)


def _canonical_evaluator_emissions(module: str, callable_name: str) -> set[str]:
    return _python_sources._canonical_evaluator_emissions(_context(), module, callable_name)


def _static_emissions(module: str, callable_name: str) -> set[str]:
    return _python_sources._static_emissions(_context(), module, callable_name)


def _artifact_rule_ids(filename: str) -> set[str]:
    return _inventory._artifact_rule_ids(_context(), filename)


def discover_deep_link_sections() -> dict[str, str]:
    return _surface_sources.discover_deep_link_sections(_context())


def discover_recommended_action_surfaces() -> set[str]:
    return _python_sources.discover_recommended_action_surfaces(_context())


def _require_source_token(path: Path, token: str, *, label: str) -> None:
    return _surface_sources._require_source_token(_context(), path, token, label=label)


def _patient_ui_evidence_paths(patient_ui: str) -> list[Path]:
    return _surface_sources._patient_ui_evidence_paths(_context(), patient_ui)


def _cohort_api_evidence_path(cohort_api: str) -> Path:
    return _surface_sources._cohort_api_evidence_path(_context(), cohort_api)


def _cohort_ui_evidence_path(cohort_ui: str) -> Path:
    return _surface_sources._cohort_ui_evidence_path(_context(), cohort_ui)


def validate_explicit_metadata(report_calls: Iterable[RuntimeCall]) -> None:
    return _inventory.validate_explicit_metadata(_context(), report_calls)


def _metadata_evidence_files(meta: dict[str, Any]) -> list[str]:
    return _inventory._metadata_evidence_files(_context(), meta)


def resolve_emissions(
    row: RuntimeCall,
    all_calls: dict[str, RuntimeCall],
    *,
    _seen: frozenset[str] = frozenset(),
) -> list[str]:
    return _inventory.resolve_emissions(_context(), row, all_calls, _seen=_seen)


def _load_registry() -> list[dict[str, Any]]:
    # Importing the module would pull package dependencies into the audit.  The
    # registry source is declarative, so parse constructor calls statically.
    return _python_sources._load_registry(_context())


def _top_level_rule_sets() -> list[dict[str, Any]]:
    return _inventory._top_level_rule_sets(_context())


def _runtime_row(
    row: RuntimeCall,
    registry: list[dict[str, Any]],
    all_calls: dict[str, RuntimeCall],
) -> dict[str, Any]:
    return _inventory._runtime_row(_context(), row, registry, all_calls)


def _direct_calls_in_callable(row: RuntimeCall) -> set[str]:
    return _python_sources._direct_calls_in_callable(_context(), row)


def _independent_rerun_debt(
    runtime_calls: list[RuntimeCall],
    all_calls: dict[str, RuntimeCall],
) -> dict[str, Any]:
    return _inventory._independent_rerun_debt(_context(), runtime_calls, all_calls)


def _claim_compliance_surface(runtime_calls: list[RuntimeCall]) -> dict[str, Any]:
    return _inventory._claim_compliance_surface(_context(), runtime_calls)


def build_audit() -> dict[str, Any]:
    return _inventory.build_audit(_context())


def check_committed_outputs(audit: dict[str, Any]) -> list[str]:
    return _cli.check_committed_outputs(_context(), audit)


def main() -> int:
    return _cli.main(_context())


if __name__ == "__main__":
    raise SystemExit(main())
