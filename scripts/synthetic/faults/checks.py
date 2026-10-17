"""Validity checks for the fault registry against pathways, catalogs and detector modules.

Each check is a pure function `(registry, catalogs) -> list[Problem]`; every check id is registered
in `schema.CHECKS` and covered by a mutation test. Reuses `Catalogs`, `load_pathway` and `expand`
from `scripts.synthetic.pathways`.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from scripts.synthetic.pathways import Pathway, PathwayLoadError, load_pathway
from scripts.synthetic.pathways.checks import Catalogs
from scripts.synthetic.pathways.expand import expand
from scripts.synthetic.pathways.loader import PATHWAYS_DIR
from scripts.synthetic.pathways.schema import DrugFlags, MaterialFlags

from .loader import REGISTRY_PATH, SIBLINGS_DIR, FaultRegistryLoadError, load_registry
from .schema import (
    MUTATION_OPS,
    SHOWCASE_STORIES,
    DropDiagnosis,
    DropEntry,
    FaultRegistry,
    Problem,
    SetBilledRatio,
    SetFlag,
    TruncateLineDays,
    UseSiblingPathway,
)

_LINE_TYPE_SECTION = {
    "islem": "procedures",
    "malzeme": "materials",
    "ilac": "drugs",
}

_FLAG_MODELS = {
    "materials": MaterialFlags,
    "drugs": DrugFlags,
}


@lru_cache(maxsize=64)
def _cached_pathway(path: Path) -> Pathway:
    return load_pathway(path)


@lru_cache(maxsize=64)
def _cached_annotated_bill(path: Path) -> dict:
    return expand(_cached_pathway(path), annotate=True)


def _load_known_pathways(
    registry: FaultRegistry,
    pathways_dir: Path = PATHWAYS_DIR,
    siblings_dir: Path = SIBLINGS_DIR,
) -> tuple[dict[str, Pathway], dict[str, Pathway], list[Problem]]:
    """Load referenced target pathways and sibling pathways, collecting `fault.target_pathway`."""
    targets: dict[str, Pathway] = {}
    siblings: dict[str, Pathway] = {}
    problems: list[Problem] = []

    for fault in registry.faults:
        pid = fault.target_pathway
        if pid not in targets:
            path = pathways_dir / f"{pid}.yaml"
            if not path.is_file():
                problems.append(
                    Problem(
                        "fault.target_pathway",
                        f"faults[{fault.fault_id}].target_pathway",
                        f"pathway {pid!r} does not exist in data/synthetic/pathways",
                    )
                )
            else:
                try:
                    targets[pid] = _cached_pathway(path)
                except PathwayLoadError as exc:
                    problems.append(
                        Problem(
                            "fault.target_pathway",
                            f"faults[{fault.fault_id}].target_pathway",
                            f"pathway {pid!r} failed to load: {exc.problems[0].message}",
                        )
                    )
        for idx, op in enumerate(fault.mutations):
            if isinstance(op, UseSiblingPathway):
                sid = op.sibling_pathway_id
                if sid not in siblings:
                    spath = siblings_dir / f"{sid}.yaml"
                    if not spath.is_file():
                        problems.append(
                            Problem(
                                "fault.target_pathway",
                                f"faults[{fault.fault_id}].mutations[{idx}].sibling_pathway_id",
                                f"sibling pathway {sid!r} does not exist in data/synthetic/faults/siblings",
                            )
                        )
                    else:
                        try:
                            siblings[sid] = _cached_pathway(spath)
                        except PathwayLoadError as exc:
                            problems.append(
                                Problem(
                                    "fault.target_pathway",
                                    f"faults[{fault.fault_id}].mutations[{idx}].sibling_pathway_id",
                                    f"sibling pathway {sid!r} failed to load: {exc.problems[0].message}",
                                )
                            )
    return targets, siblings, problems


def check_target_pathways(registry: FaultRegistry, cat: Catalogs) -> list[Problem]:
    """fault.target_pathway: every target_pathway and sibling_pathway_id exists and loads."""
    _, _, problems = _load_known_pathways(registry)
    return problems


def check_mutations(registry: FaultRegistry, cat: Catalogs) -> list[Problem]:
    """fault.entry_id, fault.keep_day_indices, fault.flag, fault.drop_diagnosis,
    fault.breaks_indication, fault.billed_ratio_target."""
    targets, _, _ = _load_known_pathways(registry)
    out: list[Problem] = []

    for fault in registry.faults:
        pathway = targets.get(fault.target_pathway)
        if pathway is None:
            continue
        expanded = _cached_annotated_bill(PATHWAYS_DIR / f"{pathway.id}.yaml")
        dropped_drugs = {
            op.entry_id
            for op in fault.mutations
            if isinstance(op, DropEntry) and op.section == "drugs"
        }

        for idx, op in enumerate(fault.mutations):
            where = f"faults[{fault.fault_id}].mutations[{idx}]"

            if isinstance(op, UseSiblingPathway):
                continue

            if isinstance(op, TruncateLineDays):
                proc_ids = {p.id for p in pathway.procedures}
                if op.entry_id not in proc_ids:
                    out.append(
                        Problem(
                            "fault.entry_id",
                            f"{where}.entry_id",
                            f"{op.entry_id!r} is not in procedures of {pathway.id}",
                        )
                    )
                    continue
                available = sorted(
                    {r["day_index"] for r in expanded["procedures"] if r["entry_id"] == op.entry_id}
                )
                keep = set(op.keep_day_indices)
                if not keep <= set(available) or len(keep) >= len(available):
                    out.append(
                        Problem(
                            "fault.keep_day_indices",
                            f"{where}.keep_day_indices",
                            f"keep_day_indices {op.keep_day_indices} must be a strict subset of {available}",
                        )
                    )

            elif isinstance(op, DropEntry):
                section_ids = {x.id for x in getattr(pathway, op.section)}
                if op.entry_id not in section_ids:
                    out.append(
                        Problem(
                            "fault.entry_id",
                            f"{where}.entry_id",
                            f"{op.entry_id!r} is not in {op.section} of {pathway.id}",
                        )
                    )

            elif isinstance(op, SetFlag):
                section_ids = {x.id for x in getattr(pathway, op.section)}
                if op.entry_id not in section_ids:
                    out.append(
                        Problem(
                            "fault.entry_id",
                            f"{where}.entry_id",
                            f"{op.entry_id!r} is not in {op.section} of {pathway.id}",
                        )
                    )
                model = _FLAG_MODELS[op.section]
                try:
                    model.model_validate({op.flag: op.value}, strict=True)
                except ValidationError:
                    out.append(
                        Problem(
                            "fault.flag",
                            f"{where}.flag",
                            f"flag {op.flag!r} with value {op.value!r} is not valid on {model.__name__}",
                        )
                    )

            elif isinstance(op, DropDiagnosis):
                diag = next((d for d in pathway.diagnoses if d.icd10 == op.icd10), None)
                if diag is None or diag.role != "secondary":
                    out.append(
                        Problem(
                            "fault.drop_diagnosis",
                            f"{where}.icd10",
                            f"{op.icd10!r} is not a secondary diagnosis of {pathway.id}",
                        )
                    )
                    continue
                dependent_drugs = [
                    d.id
                    for d in pathway.drugs
                    if d.id not in dropped_drugs and d.indication == op.icd10
                ]
                if bool(dependent_drugs) != op.breaks_indication:
                    if dependent_drugs:
                        msg = (
                            f"dropping {op.icd10} breaks indication for kept drug(s) "
                            f"{dependent_drugs}, but breaks_indication is false"
                        )
                    else:
                        msg = (
                            f"breaks_indication is true for {op.icd10}, "
                            f"but no kept drug in {pathway.id} uses it as indication"
                        )
                    out.append(
                        Problem("fault.breaks_indication", f"{where}.breaks_indication", msg)
                    )

            elif isinstance(op, SetBilledRatio):
                proc = next((p for p in pathway.procedures if p.id == op.entry_id), None)
                if proc is None:
                    out.append(
                        Problem(
                            "fault.entry_id",
                            f"{where}.entry_id",
                            f"{op.entry_id!r} is not in procedures of {pathway.id}",
                        )
                    )
                    continue
                if proc.session_role is None:
                    out.append(
                        Problem(
                            "fault.billed_ratio_target",
                            f"{where}.entry_id",
                            f"procedure {op.entry_id!r} in {pathway.id} has no session_role",
                        )
                    )

    return out


def check_target_entry_ids(registry: FaultRegistry, cat: Catalogs) -> list[Problem]:
    """fault.target_entry_id: target_entry_id (when set) exists in the pathway or sibling."""
    targets, siblings, _ = _load_known_pathways(registry)
    out: list[Problem] = []

    for fault in registry.faults:
        finding = fault.expected_finding
        if finding.target_entry_id is None:
            continue
        section = _LINE_TYPE_SECTION[finding.line_type]
        first_op = fault.mutations[0]
        if isinstance(first_op, UseSiblingPathway):
            pathway = siblings.get(first_op.sibling_pathway_id)
        else:
            pathway = targets.get(fault.target_pathway)
        if pathway is None:
            continue

        dropped = {
            op.entry_id
            for op in fault.mutations
            if isinstance(op, DropEntry) and op.section == section
        }
        valid_ids = {x.id for x in getattr(pathway, section)} - dropped
        if finding.target_entry_id not in valid_ids:
            out.append(
                Problem(
                    "fault.target_entry_id",
                    f"faults[{fault.fault_id}].expected_finding.target_entry_id",
                    f"{finding.target_entry_id!r} is not a kept {section} entry of {pathway.id}",
                )
            )
    return out


def check_clauses_and_sources(registry: FaultRegistry, cat: Catalogs) -> list[Problem]:
    """fault.sut_clauses, fault.source_cites: SUT clause ids exist and are in force."""
    out: list[Problem] = []
    for fault in registry.faults:
        where_clauses = f"faults[{fault.fault_id}].expected_finding.sut_clauses"
        for clause in fault.expected_finding.sut_clauses:
            if clause not in cat.clause_ids:
                out.append(
                    Problem(
                        "fault.sut_clauses",
                        where_clauses,
                        f"{clause} is not an in-force clause of sut_clauses.parquet",
                    )
                )
        where_source = f"faults[{fault.fault_id}].source"
        cited = sorted(set(re.findall(r"\bC[0-9]{6}\b", fault.source)))
        for clause in cited:
            if clause not in cat.clause_ids:
                out.append(
                    Problem(
                        "fault.sut_clauses",
                        where_source,
                        f"{clause} is not an in-force clause of sut_clauses.parquet",
                    )
                )
        if fault.basis == "sut" and not cited and not re.search(r"\bEK-[0-9]", fault.source):
            out.append(
                Problem(
                    "fault.source_cites",
                    where_source,
                    "basis sut needs a clause id (C000000) or an annex (EK-2B) in source",
                )
            )
    return out


def check_detectors(registry: FaultRegistry, cat: Catalogs) -> list[Problem]:
    """fault.detectors: every detector module exists and contains `def <function>`."""
    out: list[Problem] = []
    cache: dict[Path, str] = {}

    for fault in registry.faults:
        where = f"faults[{fault.fault_id}].expected_finding.detectors"
        for detector in fault.expected_finding.detectors:
            mod_rel, func_name = detector.split(":", 1)
            mod_path = cat.root / mod_rel
            if not mod_path.is_file():
                out.append(Problem("fault.detectors", where, f"module {mod_rel!r} does not exist"))
                continue
            if mod_path not in cache:
                cache[mod_path] = mod_path.read_text(encoding="utf-8")
            pattern = rf"^\s*(?:async\s+)?def\s+{re.escape(func_name)}\b"
            if not re.search(pattern, cache[mod_path], re.MULTILINE):
                out.append(
                    Problem(
                        "fault.detectors",
                        where,
                        f"function 'def {func_name}' not found in {mod_rel}",
                    )
                )
    return out


def check_registry_coverage(registry: FaultRegistry, cat: Catalogs) -> list[Problem]:
    """fault.duplicate_id, fault.duplicate_story, fault.story_coverage, fault.op_coverage."""
    out: list[Problem] = []

    ids = [f.fault_id for f in registry.faults]
    dup_ids = sorted({fid for fid in ids if ids.count(fid) > 1})
    if dup_ids:
        out.append(
            Problem(
                "fault.duplicate_id",
                "faults",
                f"duplicate fault_id(s): {', '.join(dup_ids)}",
            )
        )

    stories = [f.story for f in registry.faults if f.story is not None]
    dup_stories = sorted({s for s in stories if stories.count(s) > 1})
    if dup_stories:
        out.append(
            Problem(
                "fault.duplicate_story",
                "faults",
                f"duplicate showcase story(s): {', '.join(dup_stories)}",
            )
        )

    missing_stories = sorted(set(SHOWCASE_STORIES) - set(stories))
    if missing_stories:
        out.append(
            Problem(
                "fault.story_coverage",
                "faults",
                f"missing showcase story(s): {', '.join(missing_stories)}",
            )
        )

    used_ops = {op.op for f in registry.faults for op in f.mutations}
    missing_ops = sorted(set(MUTATION_OPS) - used_ops)
    if missing_ops:
        out.append(
            Problem(
                "fault.op_coverage",
                "faults",
                f"unused mutation op(s): {', '.join(missing_ops)}",
            )
        )

    return out


CHECK_FUNCTIONS: tuple[Callable[[FaultRegistry, Catalogs], list[Problem]], ...] = (
    check_target_pathways,
    check_mutations,
    check_target_entry_ids,
    check_clauses_and_sources,
    check_detectors,
    check_registry_coverage,
)


def run_all(registry: FaultRegistry, catalogs: Catalogs | None = None) -> list[Problem]:
    """Run every check on `registry`; an empty list means the registry is valid."""
    cat = catalogs or Catalogs()
    return [problem for check in CHECK_FUNCTIONS for problem in check(registry, cat)]


def main(argv: list[str] | None = None) -> int:
    """`python -m scripts.synthetic.faults.checks [file ...]`: load and check fault registry files."""
    paths = [Path(a) for a in (sys.argv[1:] if argv is None else argv)] or [REGISTRY_PATH]
    catalogs, failed = Catalogs(), 0
    for path in paths:
        try:
            problems = run_all(load_registry(path), catalogs)
        except FaultRegistryLoadError as exc:
            problems = exc.problems
        failed += bool(problems)
        print(f"{path.name}: {'ok' if not problems else f'{len(problems)} problem(s)'}")
        for problem in problems:
            print(f"  {problem}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
