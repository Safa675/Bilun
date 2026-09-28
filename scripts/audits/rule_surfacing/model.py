"""Value types and explicit repository inputs for the static audit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeCall:
    entrypoint: str
    callable: str
    module: str
    lines: tuple[int, ...]
    gates: tuple[str, ...]
    report_fields: tuple[str, ...]


@dataclass(frozen=True)
class AuditContext:
    """Paths and source-name adapters supplied by the compatible entrypoint."""

    root: Path
    frontend_source_root: Path
    engine_path: Path
    patient_report_path: Path
    focused_materializer_path: Path
    focused_projection_path: Path
    wavea_evidence_path: Path
    registry_path: Path
    claim_compliance_path: Path
    cohort_compliance_path: Path
    recommended_actions_path: Path
    billing_actions_path: Path
    billing_api_path: Path
    alerts_api_path: Path
    compliance_api_path: Path
    wavea_gate_api_path: Path
    patient_sections_path: Path
    compliance_view_path: Path
    revenue_view_path: Path
    audit_view_path: Path
    cohort_dashboard_path: Path
    prose_rules_dir: Path
    matrix_path: Path
    report_path: Path
    relative_path: Callable[[Path], str]
    module_for_path: Callable[[Path], str]
    module_path: Callable[[str], Path | None]
