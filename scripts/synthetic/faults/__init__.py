"""Fault registry for the synthetic demo (v3, P3): schema, loader, validity checks, mutation and answer key.

`data/synthetic/faults/fault_registry.yaml` declares the billing mutations that turn a clean
expanded pathway bill into a faulty bill. `load_registry` reads and validates the file;
`checks.run_all` checks cross-pathway references, SUT clauses, detector functions and coverage;
`apply_fault` mutates an expanded pathway bill; `FaultInjectionRecord` and
`build_expected_rule_outputs` derive the answer key.
"""

from .answer_key import EXPECTED_OUTPUT_COLUMNS, build_expected_rule_outputs
from .loader import FaultRegistryLoadError, load_registry, load_registry_text, load_siblings
from .mutate import FaultApplyError, apply_fault
from .records import FaultInjectionRecord, make_record
from .schema import (
    CHECKS,
    MUTATION_OPS,
    SHOWCASE_STORIES,
    DropDiagnosis,
    DropEntry,
    ExpectedFinding,
    ExpectedFindingSpec,
    FaultRegistry,
    FaultSpec,
    MutationOp,
    Problem,
    SetBilledRatio,
    SetFlag,
    TruncateLineDays,
    UseSiblingPathway,
)

__all__ = [
    "CHECKS",
    "DropDiagnosis",
    "DropEntry",
    "EXPECTED_OUTPUT_COLUMNS",
    "ExpectedFinding",
    "ExpectedFindingSpec",
    "FaultApplyError",
    "FaultInjectionRecord",
    "FaultRegistry",
    "FaultRegistryLoadError",
    "FaultSpec",
    "MUTATION_OPS",
    "MutationOp",
    "Problem",
    "SHOWCASE_STORIES",
    "SetBilledRatio",
    "SetFlag",
    "TruncateLineDays",
    "UseSiblingPathway",
    "apply_fault",
    "build_expected_rule_outputs",
    "load_registry",
    "load_registry_text",
    "load_siblings",
    "make_record",
]
