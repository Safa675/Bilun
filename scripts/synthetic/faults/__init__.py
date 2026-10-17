"""Fault registry for the synthetic demo (v3, P3): schema, loader and validity checks.

`data/synthetic/faults/fault_registry.yaml` declares the billing mutations that turn a clean
expanded pathway bill into a faulty bill. `load_registry` reads and validates the file;
`checks.run_all` checks cross-pathway references, SUT clauses, detector functions and coverage.
"""

from .loader import FaultRegistryLoadError, load_registry, load_registry_text
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
    "ExpectedFinding",
    "ExpectedFindingSpec",
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
    "load_registry",
    "load_registry_text",
]
