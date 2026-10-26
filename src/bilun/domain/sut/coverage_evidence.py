"""Deterministic source inventory, deliberately distinct from clinical completion.

The executable inventory is a lower bound: diagnosis-applicability predicates
accepted by the indication router. It does not assert that every condition in a
rule is executable, nor that any predicate ran for a patient.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl

from ..prose_rules._drug_indication.matching import (
    _is_indication_route_rule,
    _rule_has_icd_selector,
)

_SCOPE = "drug_indication_prose"
_SOURCE_COLUMNS = ("clause_id", "has_rule_encoding", "has_algorithmic_gap")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_drug_coverage_evidence(
    clause_frame: pl.DataFrame, rules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Inventory unique source IDs and a bounded, inspectable predicate subset.

    Conflicting duplicates fail closed rather than selecting whichever row
    happens to appear first. Static artifacts cannot establish runtime input
    availability or execution. Those metrics are null, never a fabricated zero.
    """
    required = {*_SOURCE_COLUMNS, "primary_rule_id"}
    missing = sorted(required - set(clause_frame.columns))
    if missing:
        return {"schema_version": 1, "available": False,
                "unavailable_reason": f"Missing coverage columns: {', '.join(missing)}"}
    for column in ("has_rule_encoding", "has_algorithmic_gap"):
        if clause_frame.schema[column] not in (pl.Boolean, pl.Null):
            raise ValueError(f"Coverage {column} must contain booleans or nulls")
    scoped = clause_frame.filter(pl.col("primary_rule_id") == _SCOPE)
    source_rows = scoped.select(_SOURCE_COLUMNS).with_columns(
        pl.col("clause_id").str.strip_chars()
    ).unique().sort("clause_id")
    if source_rows.filter(
        pl.col("clause_id").is_null() | (pl.col("clause_id").str.strip_chars() == "")
    ).height:
        raise ValueError("Coverage source IDs must be nonempty")
    if source_rows["clause_id"].n_unique() != source_rows.height:
        raise ValueError("Conflicting coverage rows for the same source ID")
    source_ids = source_rows["clause_id"].to_list()
    represented = source_rows.filter(pl.col("has_rule_encoding") == True)["clause_id"].to_list()
    deferred = source_rows.filter(
        (pl.col("has_rule_encoding") == False) & (pl.col("has_algorithmic_gap") == False)
    )["clause_id"].to_list()
    gaps = source_rows.filter(
        (pl.col("has_rule_encoding") == False) & (pl.col("has_algorithmic_gap") == True)
    )["clause_id"].to_list()

    unique_rules: dict[str, dict[str, Any]] = {}
    for rule in rules:
        rule_id = rule.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ValueError("Coverage rule IDs must be nonempty strings")
        if rule_id != rule_id.strip():
            raise ValueError("Coverage rule IDs must not contain surrounding whitespace")
        if rule_id in unique_rules and unique_rules[rule_id] != rule:
            raise ValueError(f"Conflicting rule definitions: {rule_id}")
        unique_rules[rule_id] = rule
    predicate_ids = []
    for rule_id, rule in sorted(unique_rules.items()):
        # Same candidate prerequisites used by routing._drug_rule_candidates.
        # Nested condition/action prose and supplemental metadata are excluded.
        names = rule.get("drug_names")
        codes = rule.get("icd10_codes") or []
        ranges = rule.get("icd10_ranges") or []
        if not isinstance(codes, list) or not isinstance(ranges, list):
            continue
        selectors = codes + ranges
        if (
            not rule.get("temporal_source_only")
            and isinstance(names, list) and names
            and all(isinstance(n, str) and n.strip() for n in names)
            and isinstance(selectors, list)
            and all(isinstance(s, str) and s.strip() for s in selectors)
            and _rule_has_icd_selector(rule) and _is_indication_route_rule(rule)
        ):
            predicate_ids.append(rule_id)

    canonical_inputs = {"sources": source_rows.to_dicts(),
                        "rules": [unique_rules[key] for key in sorted(unique_rules)]}
    return {
        "schema_version": 1,
        "available": True,
        "scope": _SCOPE,
        "input_sha256": hashlib.sha256(_canonical_json(canonical_inputs).encode()).hexdigest(),
        "source_clause_count": len(source_ids),
        "source_represented_clause_count": len(represented),
        "deferred_or_structural_clause_count": len(deferred),
        "unrepresented_gap_clause_count": len(gaps),
        "unknown_source_status_clause_count": len(source_ids) - len(represented) - len(deferred) - len(gaps),
        "source_ids": source_ids,
        "represented_source_ids": represented,
        "deferred_or_structural_source_ids": deferred,
        "unrepresented_gap_source_ids": gaps,
        "executable_predicate_rule_count": len(predicate_ids),
        "executable_predicate_rule_ids": predicate_ids,
        "executable_predicate_scope": "diagnosis_applicability_only_lower_bound",
        "outside_diagnosis_predicate_inventory_rule_count": len(unique_rules) - len(predicate_ids),
        "rules_on_disk_count": len(unique_rules),
        "inputs_available_count": None,
        "actually_evaluated_count": None,
        "runtime_unavailable_reason": "Static inventory has no per-claim execution observations.",
        "clinical_completion_pct": None,
        "limitations": [
            "Source representation includes encoded text; it does not prove executable clinical conditions.",
            "Predicate count uses rule IDs, not clause IDs; it is not a source-coverage percentage.",
            "Only diagnosis applicability predicates are inventoried; other constraints are not audited here.",
            "A routable predicate is not proof of complete SUT implementation, available inputs, or execution.",
        ],
    }


def coverage_evidence_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    """Keep full source/rule IDs in the offline audit, not the API headline."""
    return {key: value for key, value in evidence.items() if not key.endswith("_ids")}


def coverage_dependency_hashes(project_root: Path, clauses_path: Path) -> dict[str, str]:
    """Pin static coverage dependencies, including manifests and compiled rules.

    The resolver also reads the repository's canonical clauses file even when
    the CLI classifies another input. Pin both, and use relative identities so
    relocating the same checkout does not change the report. Missing optional
    data files are recorded separately by their absence from the inventory.
    """
    patterns = (
        "data/gazette/prose_rules/*.json",
        "data/gazette/prose_rules/*.yaml",
        "data/gazette/prose_manifests/*.json",
        "data/gazette/temporal/*.json",
        "data/gazette/source_authority/*.json",
        "data/gazette/source_authority/*.txt",
        "data/gazette/*.yaml",
        "scripts/sut/prose/*.py",
        "src/bilun/domain/prose_rules/_drug_indication/*.py",
    )
    paths = {path for pattern in patterns for path in project_root.glob(pattern)}
    paths.update(project_root / path for path in (
        "data/gazette/sut_clauses.parquet",
        "scripts/sut/build_sut_coverage.py",
        "src/bilun/domain/sut/coverage_evidence.py",
        "src/bilun/domain/sut/source_authority_schema.py",
        "src/bilun/domain/sut/rule_registry.py",
        "src/bilun/domain/prose_rules/drug_indication.py",
        "src/bilun/domain/prose_rules/adult_gh_draft.py",
        "src/bilun/domain/claims/adult_gh.py",
        "src/bilun/domain/claims/mds_evidence.py",
        "src/bilun/domain/optimization/shared.py",
        "src/bilun/domain/icd10.py",
        "src/bilun/domain/turkish_fold.py",
        "src/bilun/domain/constants.py",
        "pyproject.toml",
    ))
    return {
        "input_clauses": hashlib.sha256(clauses_path.read_bytes()).hexdigest(),
        **{
            str(path.relative_to(project_root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()
        },
    }
