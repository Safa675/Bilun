"""Source evidence must survive component moves without accepting dead UI."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import re
import sys

import pytest

from scripts.audits.rule_surfacing.surface_sources import SurfaceSourceResolver


ROOT = Path(__file__).resolve().parents[3]
VIEW_NAME = "ComplianceViewSection"
COMPONENT = "DrugIndicationReviewSection"
SECTION_ID = "drug-indication"


def _write(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _graph(tmp_path: Path, *, view_body: str | None = None, section_body: str | None = None):
    source_root = tmp_path / "frontend/src"
    view = _write(
        source_root / "components/patient/views/ComplianceViewSection.tsx",
        'import { DrugIndicationReviewSection } from "../SutBillingReportSections";\n'
        "export default function ComplianceViewSection({ enabled }: { enabled: boolean }) {\n"
        + (view_body or "return <main>{enabled && <DrugIndicationReviewSection />}</main>;")
        + "\n}\n",
    )
    sections = _write(
        source_root / "components/patient/SutBillingReportSections.tsx",
        "export function DrugIndicationReviewSection() {\n"
        + (section_body or 'return <section id="drug-indication" />;')
        + "\n}\n",
    )
    return SurfaceSourceResolver(source_root, {VIEW_NAME: view}), view, sections


def _evidence(resolver: SurfaceSourceResolver) -> list[Path]:
    return resolver.component_evidence(VIEW_NAME, COMPONENT, section_id=SECTION_ID)


def _load_audit():
    path = ROOT / "scripts/audits/build_rule_surfacing_inventory.py"
    spec = importlib.util.spec_from_file_location("surface_sources_audit_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_named_component_and_conditional_render_have_source_evidence(tmp_path: Path) -> None:
    resolver, view, sections = _graph(tmp_path)

    assert set(_evidence(resolver)) == {view, sections}


def test_moved_component_follows_named_reexports_and_import_aliases(tmp_path: Path) -> None:
    resolver, view, sections = _graph(tmp_path)
    leaf = _write(
        sections.parent / "billing-report/DrugIndicationReviewSection.tsx",
        "export function DrugReview() { return <section id='drug-indication' />; }\n",
    )
    sections.write_text(
        '"use client";\n'
        "export { DrugReview as DrugIndicationReviewSection }\n"
        '  from "./billing-report/DrugIndicationReviewSection";\n',
        encoding="utf-8",
    )
    view.write_text(
        "import { DrugIndicationReviewSection as DrugSection }\n"
        '  from "@/components/patient/SutBillingReportSections";\n'
        "export default function ComplianceViewSection() { return <DrugSection />; }\n",
        encoding="utf-8",
    )

    assert set(_evidence(resolver)) == {view, sections, leaf}


def test_rendered_map_callback_is_not_mistaken_for_an_unused_function(tmp_path: Path) -> None:
    resolver, view, sections = _graph(
        tmp_path,
        view_body=(
            "return <main>{[1, 2].map((key) => ("
            "<DrugIndicationReviewSection key={key} />))}</main>;"
        ),
    )

    assert set(_evidence(resolver)) == {view, sections}


@pytest.mark.parametrize(
    "view_body",
    [
        "return <main />;",
        "// return <DrugIndicationReviewSection />;\nreturn <main />;",
        'const note = "<DrugIndicationReviewSection />"; return <main>{note}</main>;',
        "const note = `<DrugIndicationReviewSection />`; return <main>{note}</main>;",
        "function unused() { return <DrugIndicationReviewSection />; } return <main />;",
        "function unused({ enabled }: { enabled: boolean }) { return <DrugIndicationReviewSection />; } return <main />;",
        "const unused = () => <DrugIndicationReviewSection />; return <main />;",
        "const unused = <DrugIndicationReviewSection />; return <main />;",
        "return <main>{/* <DrugIndicationReviewSection /> */}</main>;",
        "const DrugIndicationReviewSection = () => null; return <DrugIndicationReviewSection />;",
    ],
    ids=["unused-import", "comment", "string", "template", "function", "typed-function", "arrow", "unused-jsx", "jsx-comment", "shadowed-import"],
)
def test_unrendered_component_references_do_not_prove_visibility(tmp_path: Path, view_body: str) -> None:
    resolver, _, _ = _graph(tmp_path, view_body=view_body)

    with pytest.raises(ValueError, match="patient UI source"):
        _evidence(resolver)


@pytest.mark.parametrize(
    "view_body",
    [
        "const unused = { render() { return <DrugIndicationReviewSection />; } }; return <main />;",
        "class Unused { render() { return <DrugIndicationReviewSection />; } } return <main />;",
        "return <main>{ignore(<DrugIndicationReviewSection />)}</main>;",
        "return <main>{[1].map(x => <DrugIndicationReviewSection />).length}</main>;",
    ],
    ids=["uncalled-object-method", "uncalled-class-method", "opaque-call", "consumed-map-output"],
)
def test_nested_or_consumed_jsx_does_not_prove_a_rendered_surface(tmp_path: Path, view_body: str) -> None:
    resolver, _, _ = _graph(tmp_path, view_body=view_body)

    with pytest.raises(ValueError, match="patient UI source"):
        _evidence(resolver)


@pytest.mark.parametrize(
    "section_body",
    [
        'return <section id="different-section" />;',
        '// id="drug-indication"\nreturn <section />;',
        "const note = 'id=\"drug-indication\"'; return <section>{note}</section>;",
        'function unused() { return <section id="drug-indication" />; } return <section />;',
        'const unused = () => <section id="drug-indication" />; return <section />;',
        'const unused = <section id="drug-indication" />; return <section />;',
        'return <section id="drug-indication" id="different-section" />;',
    ],
    ids=["changed-id", "comment", "string", "function", "arrow", "unused-jsx", "duplicate-id"],
)
def test_section_id_must_belong_to_rendered_component_output(tmp_path: Path, section_body: str) -> None:
    resolver, _, _ = _graph(tmp_path, section_body=section_body)

    with pytest.raises(ValueError, match="patient UI source"):
        _evidence(resolver)


def test_view_owned_section_id_is_checked_in_its_rendered_output(tmp_path: Path) -> None:
    resolver, view, _ = _graph(tmp_path, view_body='return <section id="claim-compliance" />;')
    assert resolver.view_evidence(VIEW_NAME, section_id="claim-compliance") == [view]


def test_unrelated_function_cannot_supply_a_view_owned_section_id(tmp_path: Path) -> None:
    resolver, view, _ = _graph(tmp_path, view_body="return <main />;")
    with view.open("a", encoding="utf-8") as stream:
        stream.write('function unused() { return <section id="claim-compliance" />; }\n')

    with pytest.raises(ValueError, match="patient UI source"):
        resolver.view_evidence(VIEW_NAME, section_id="claim-compliance")


@pytest.mark.parametrize("missing", ["file", "export", "reexport-target"])
def test_missing_component_contract_fails_closed(tmp_path: Path, missing: str) -> None:
    resolver, _, sections = _graph(tmp_path)
    if missing == "file":
        sections.unlink()
    elif missing == "export":
        sections.write_text("export function DifferentSection() { return null; }\n", encoding="utf-8")
    else:
        sections.write_text(
            'export { DrugIndicationReviewSection } from "./missing-leaf";\n', encoding="utf-8"
        )

    with pytest.raises(ValueError, match="patient UI source"):
        _evidence(resolver)


def test_named_reexport_cycle_fails_closed(tmp_path: Path) -> None:
    resolver, _, sections = _graph(tmp_path)
    sections.write_text('export { DrugIndicationReviewSection } from "./cycle";\n', encoding="utf-8")
    _write(
        sections.parent / "cycle.tsx",
        'export { DrugIndicationReviewSection } from "./SutBillingReportSections";\n',
    )

    with pytest.raises(ValueError, match="patient UI source"):
        _evidence(resolver)


@pytest.mark.parametrize("type_only", ["import", "inline-import", "reexport", "inline-reexport"])
def test_type_only_bindings_are_not_runtime_surface_evidence(tmp_path: Path, type_only: str) -> None:
    resolver, view, sections = _graph(tmp_path)
    if type_only.endswith("import"):
        source = view.read_text(encoding="utf-8")
        replacement = "import type {" if type_only == "import" else "import { type"
        view.write_text(source.replace("import {", replacement, 1), encoding="utf-8")
    else:
        _write(sections.parent / "leaf.tsx", sections.read_text(encoding="utf-8"))
        declaration = "export type {" if type_only == "reexport" else "export { type"
        sections.write_text(
            declaration + ' DrugIndicationReviewSection } from "./leaf";\n', encoding="utf-8"
        )

    with pytest.raises(ValueError, match="patient UI source"):
        _evidence(resolver)


def test_competing_named_exports_fail_closed(tmp_path: Path) -> None:
    resolver, _, sections = _graph(tmp_path)
    with sections.open("a", encoding="utf-8") as stream:
        stream.write('export { DrugIndicationReviewSection } from "./other";\n')
    _write(
        sections.parent / "other.tsx",
        'export function DrugIndicationReviewSection() { return <section id="drug-indication" />; }\n',
    )

    with pytest.raises(ValueError, match="patient UI source"):
        _evidence(resolver)


@pytest.mark.parametrize(
    "source",
    [
        'export const DrugIndicationReviewSection = () => <section id="drug-indication" />;',
        'export * from "./other";',
    ],
    ids=["arrow-component", "wildcard-reexport"],
)
def test_unsupported_audited_component_forms_fail_explicitly(tmp_path: Path, source: str) -> None:
    resolver, _, sections = _graph(tmp_path)
    sections.write_text(source, encoding="utf-8")
    _write(
        sections.parent / "other.tsx",
        'export function DrugIndicationReviewSection() { return <section id="drug-indication" />; }\n',
    )

    with pytest.raises(ValueError, match="patient UI source"):
        _evidence(resolver)


def test_audit_accepts_real_report_facade_extraction_without_changing_classifications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = _load_audit()
    before = audit.build_audit()
    copied_source_root = tmp_path / "frontend/src"
    original_source_root = ROOT / "frontend/src"
    monkeypatch.setattr(audit, "FRONTEND_SOURCE_ROOT", copied_source_root)

    for name in ("PATIENT_SECTIONS_PATH", "COMPLIANCE_VIEW_PATH", "REVENUE_VIEW_PATH", "AUDIT_VIEW_PATH"):
        original = getattr(audit, name)
        copied = _write(copied_source_root / original.relative_to(original_source_root), original.read_text(encoding="utf-8"))
        monkeypatch.setattr(audit, name, copied)

    sections = audit.PATIENT_SECTIONS_PATH
    source = sections.read_text(encoding="utf-8")
    exported_names = re.findall(r"^export (?:function|const) (\w+)", source, re.MULTILINE)
    assert COMPONENT in exported_names
    leaf = _write(sections.parent / "billing-report/sections.tsx", source)
    sections.write_text(
        '"use client";\nexport { ' + ", ".join(exported_names) + ' } from "./billing-report/sections";\n',
        encoding="utf-8",
    )
    original_rel = audit._rel

    def relative_evidence(path: Path) -> str:
        if path.is_relative_to(copied_source_root):
            return "frontend/src/" + path.relative_to(copied_source_root).as_posix()
        return original_rel(path)

    monkeypatch.setattr(audit, "_rel", relative_evidence)
    after = audit.build_audit()
    expected = deepcopy(before)
    leaf_evidence = relative_evidence(leaf)
    changed_rows = []
    for original_row, actual_row, expected_row in zip(before["rows"], after["rows"], expected["rows"], strict=True):
        if actual_row["evidence_files"] != original_row["evidence_files"]:
            assert actual_row["evidence_files"] == sorted(set(original_row["evidence_files"]) | {leaf_evidence})
            changed_rows.append(actual_row["runtime_id"])
            expected_row["evidence_files"] = actual_row["evidence_files"]

    assert "compute_patient_billing_report:validate_drug_indication_from_claims" in changed_rows
    assert after == expected
    assert leaf in audit._patient_ui_evidence_paths("ComplianceViewSection:DrugIndicationReviewSection")

    leaf.write_text(source.replace('id="drug-indication"', 'id="removed-drug-indication"'), encoding="utf-8")
    with pytest.raises(ValueError, match="patient UI source"):
        audit._patient_ui_evidence_paths("ComplianceViewSection:DrugIndicationReviewSection")
