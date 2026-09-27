"""Independently reconcile Wave A broad scopes with pinned claim Parquets.

The evidence producer's claim_scope_inventory is not a source of truth: an
omitted claim or material could otherwise disappear from both that inventory
and its evaluations. This checkpoint reads only the identity columns from
the source-rostered Parquets and does not authorize release.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _parse_json, _stable_file_hash
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.billing.focused_rule_projection import FOCUSED_RULE_SPECS
from src.bilun.domain.billing.rule_findings import build_evaluation_id

_ROSTER_VERSION = "wavea-source-v1"
_REQUIRED_DATA_LABELS = frozenset(
    {
        "claim:claim_headers.parquet",
        "claim:claim_diagnoses.parquet",
        "claim:procedure_claim_lines.parquet",
        "claim:material_claim_lines.parquet",
        "claim:drug_claim_lines.parquet",
        "claim:expected_rule_outputs.parquet",
        "clean:lab_clean.parquet",
        "clean:anadata_clean.parquet",
        "clean:recete_clean.parquet",
    }
)
_STATUS_NAMES = ("evaluated", "missing_inputs", "unavailable")
_LINE_SOURCES = {
    "procedure": ("claim:procedure_claim_lines.parquet", "procedure_line_id"),
    "drug": ("claim:drug_claim_lines.parquet", "drug_claim_line_id"),
    "material": ("claim:material_claim_lines.parquet", "material_line_id"),
}
_OBSERVED_AMOUNT_BASIS = "procedure_claim_line.billed_amount_try"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _pinned_claim_paths(
    roster: Path, labels_to_read: tuple[str, ...]
) -> tuple[dict[str, Path], str, dict[str, str]]:
    roster_sha = _candidate_db_hash(roster)
    manifest = _parse_json(roster.read_text(), context="candidate source roster")
    if not isinstance(manifest, dict) or manifest.get("roster_version") != _ROSTER_VERSION:
        raise ValueError("Candidate source roster version is missing or unsupported")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or manifest.get("source_count") != len(sources):
        raise ValueError("Candidate source roster count disagrees with entries")
    labels: dict[str, dict[str, Any]] = {}
    for entry in sources:
        if not isinstance(entry, dict):
            raise ValueError("Candidate source roster entry is malformed")
        label = entry.get("label")
        if not isinstance(label, str) or not label or label in labels:
            raise ValueError("Candidate source roster has a duplicate or blank label")
        labels[label] = entry
    if sorted(labels) != [entry["label"] for entry in sources]:
        raise ValueError("Candidate source roster entries are not ordered")
    if not _REQUIRED_DATA_LABELS <= labels.keys():
        raise ValueError("Candidate source roster omits required claim or clinical inputs")
    expected_roster_sha = hashlib.sha256(
        _canonical(
            [
                {key: entry[key] for key in ("label", "path", "sha256", "size_bytes")}
                for entry in sources
            ]
        )
    ).hexdigest()
    if manifest.get("roster_sha256") != expected_roster_sha:
        raise ValueError("Candidate source roster digest disagrees with entries")
    pinned: dict[str, str] = {}
    paths: dict[str, Path] = {}
    for label in labels_to_read:
        entry = labels[label]
        raw_path, expected_sha, expected_size = (
            entry.get("path"),
            entry.get("sha256"),
            entry.get("size_bytes"),
        )
        if (
            not isinstance(raw_path, str)
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
            or any(char not in "0123456789abcdef" for char in expected_sha)
            or type(expected_size) is not int
            or expected_size < 0
        ):
            raise ValueError(f"Pinned claim source metadata is malformed: {label}")
        path = Path(raw_path)
        if (
            not path.is_absolute()
            or path.name != label.split(":", 1)[1]
            or path.is_symlink()
            or not path.is_file()
            or path.stat().st_nlink != 1
            or path.stat().st_size != expected_size
            or _stable_file_hash(path) != expected_sha
        ):
            raise ValueError(f"Pinned claim source byte identity differs: {label}")
        paths[label] = path
        pinned[label] = expected_sha
    if len({path.parent for path in paths.values()}) != 1 or roster_sha != _candidate_db_hash(roster):
        raise ValueError("Pinned claim inputs or source roster changed during verification")
    return paths, roster_sha, pinned


def _id(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"Blank or noncanonical {label} in pinned claim Parquet")
    return value


def _id_rows(path: Path, columns: tuple[str, ...]):
    source = pq.ParquetFile(path)
    if not set(columns) <= set(source.schema_arrow.names):
        raise ValueError(f"Pinned claim Parquet lacks identity columns: {path.name}")
    for batch in source.iter_batches(batch_size=4096, columns=list(columns)):
        values = batch.to_pydict()
        yield from zip(*(values[column] for column in columns), strict=True)


def _minor_units(value: Any, *, label: str) -> int:
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"Missing or malformed {label}")
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
            raise ValueError(f"Non-cent {label}")
        return int(amount * 100)
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ValueError(f"Missing or malformed {label}") from exc


def _procedure_charge_state(matches: list[tuple[str, Any]], patient_id: str) -> tuple[str | None, int | None]:
    owned = [raw_amount for owner, raw_amount in matches if owner == patient_id]
    if len(owned) > 1:
        return "procedure_line_ambiguous", None
    if not owned and matches:
        return "procedure_line_owner_mismatch", None
    if not owned:
        return "procedure_line_missing", None
    raw_amount = owned[0]
    if raw_amount is None or isinstance(raw_amount, bool) or not isinstance(
        raw_amount, (str, int, float, Decimal)
    ):
        return "procedure_line_charge_invalid", None
    try:
        amount = Decimal(str(raw_amount))
        if not amount.is_finite() or amount < 0:
            return "procedure_line_charge_invalid", None
        if amount * 100 != (amount * 100).to_integral_value():
            return "procedure_line_charge_not_cent_exact", None
        amount_value = float(amount)
        if not math.isfinite(amount_value) or Decimal(str(amount_value)) != amount:
            return "procedure_line_charge_invalid", None
        return None, int(amount * 100)
    except (InvalidOperation, ValueError, OverflowError):
        return "procedure_line_charge_invalid", None


def _source_scopes(
    headers_path: Path, materials_path: Path, patient_ids: set[str]
) -> dict[str, dict[str, Any]]:
    header_owners: dict[str, str] = {}
    for claim_raw, patient_raw in _id_rows(headers_path, ("claim_id", "patient_id")):
        claim_id = _id(claim_raw, label="claim_id")
        patient_id = _id(patient_raw, label="patient_id")
        if claim_id in header_owners:
            raise ValueError(f"Duplicate claim header identity in pinned source: {claim_id}")
        header_owners[claim_id] = patient_id
    unreported_owners = set(header_owners.values()) - patient_ids
    if unreported_owners:
        raise ValueError("Pinned claim header patient is absent from billing report details")
    material_ids: set[str] = set()
    by_claim: dict[str, set[str]] = {}
    for line_raw, claim_raw, patient_raw in _id_rows(
        materials_path, ("material_line_id", "claim_id", "patient_id")
    ):
        line_id = _id(line_raw, label="material_line_id")
        claim_id = _id(claim_raw, label="material claim_id")
        patient_id = _id(patient_raw, label="material patient_id")
        if line_id in material_ids:
            raise ValueError(f"Duplicate material line identity in pinned source: {line_id}")
        material_ids.add(line_id)
        if header_owners.get(claim_id) != patient_id:
            raise ValueError(f"Orphan or cross-patient material line in pinned source: {line_id}")
        by_claim.setdefault(claim_id, set()).add(line_id)
    claims_by_patient: dict[str, list[str]] = {patient_id: [] for patient_id in patient_ids}
    for claim_id, owner in header_owners.items():
        if owner in claims_by_patient:
            claims_by_patient[owner].append(claim_id)
    return {
        patient_id: {
            "context_state": "available" if claims else "no_headers",
            "claims": [
                {"claim_id": claim_id, "material_line_ids": sorted(by_claim.get(claim_id, ()))}
                for claim_id in sorted(claims)
            ],
        }
        for patient_id, claims in sorted(claims_by_patient.items())
    }


def _expected_broad(
    patient_id: str, scope: dict[str, Any], claim_rules: set[str], dental_rules: set[str]
) -> dict[str, tuple[str, str | None, str, str | None, bool]]:
    expected: dict[str, tuple[str, str | None, str, str | None, bool]] = {}

    def add(
        rule_id: str, claim_id: str | None, kind: str, line_id: str | None, missing: bool
    ) -> None:
        evaluation_id = build_evaluation_id(
            rule_id=rule_id,
            patient_id=patient_id,
            claim_id=claim_id,
            line_kind=kind,
            line_id=line_id,
        )
        expected[evaluation_id] = (rule_id, claim_id, kind, line_id, missing)

    if scope["context_state"] == "no_headers":
        for rule_id in claim_rules | dental_rules:
            add(rule_id, None, "claim", None, True)
        return expected
    for claim in scope["claims"]:
        claim_id = claim["claim_id"]
        for rule_id in claim_rules:
            add(rule_id, claim_id, "claim", None, False)
        material_ids = claim["material_line_ids"]
        for rule_id in dental_rules:
            if material_ids:
                for line_id in material_ids:
                    add(rule_id, claim_id, "material", line_id, False)
            else:
                add(rule_id, claim_id, "claim", None, True)
    return expected


def verify_pinned_claim_scopes(
    source_roster: Path, details_by_patient: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Require exact broad identities against raw, pinned claim/material rows."""
    if not details_by_patient or any(not patient_id for patient_id in details_by_patient):
        raise ValueError("Scope verification requires nonempty patient detail identities")
    paths, roster_sha, pinned = _pinned_claim_paths(
        source_roster,
        ("claim:claim_headers.parquet", "claim:material_claim_lines.parquet"),
    )
    headers = paths["claim:claim_headers.parquet"]
    materials = paths["claim:material_claim_lines.parquet"]
    scopes = _source_scopes(headers, materials, set(details_by_patient))
    catalog = load_broad_rule_catalog()
    dental_rules = {rule.rule_id for rule in catalog if rule.family == "dental_2_4_1"}
    claim_rules = {rule.rule_id for rule in catalog if rule.family != "dental_2_4_1"}
    if len(claim_rules) != 477 or len(dental_rules) != 19:
        raise ValueError("Broad source roster differs from 477 claim and 19 dental rules")
    total_evaluations = 0
    total_claims = 0
    total_materials = 0
    for patient_id, detail in details_by_patient.items():
        scope = scopes[patient_id]
        if detail.get("claim_scope_inventory") != scope:
            raise ValueError(
                f"Wave A claim/material inventory differs from pinned Parquet: {patient_id}"
            )
        expected = _expected_broad(patient_id, scope, claim_rules, dental_rules)
        evaluations = detail.get("evaluations")
        if not isinstance(evaluations, list):
            raise ValueError(f"Wave A detail lacks evaluations: {patient_id}")
        actual: dict[str, dict[str, Any]] = {}
        for evaluation in evaluations:
            if not isinstance(evaluation, dict):
                raise ValueError(f"Malformed Wave A evaluation: {patient_id}")
            if evaluation.get("rule_id") not in claim_rules | dental_rules:
                continue
            identity = evaluation.get("evaluation_id")
            if not isinstance(identity, str) or identity in actual:
                raise ValueError(f"Duplicate or malformed broad evaluation identity: {patient_id}")
            actual[identity] = evaluation
        if actual.keys() != expected.keys():
            raise ValueError(
                f"Broad evaluation scope/cardinality differs from pinned Parquet: {patient_id}"
            )
        statuses_by_rule: dict[str, Counter[str]] = {
            rule_id: Counter() for rule_id in claim_rules | dental_rules
        }
        for identity, (rule_id, claim_id, kind, line_id, missing) in expected.items():
            evaluation = actual[identity]
            if any(
                evaluation.get(key) != value
                for key, value in (
                    ("patient_id", patient_id),
                    ("rule_id", rule_id),
                    ("claim_id", claim_id),
                    ("line_kind", kind),
                    ("line_id", line_id),
                )
            ):
                raise ValueError(f"Broad evaluation source ownership differs: {identity}")
            status = evaluation.get("evaluation_status")
            if status not in _STATUS_NAMES or (missing and status != "missing_inputs"):
                raise ValueError(f"Broad evaluation has wrong missing/source status: {identity}")
            statuses_by_rule[rule_id][status] += 1
        counts = detail.get("counts")
        by_rule = counts.get("by_rule") if isinstance(counts, dict) else None
        if not isinstance(by_rule, dict) or any(
            by_rule.get(rule_id) != {status: statuses[status] for status in _STATUS_NAMES}
            for rule_id, statuses in statuses_by_rule.items()
        ):
            raise ValueError(
                f"Broad per-rule status counts differ from pinned scopes: {patient_id}"
            )
        total_evaluations += len(expected)
        total_claims += len(scope["claims"])
        total_materials += sum(len(claim["material_line_ids"]) for claim in scope["claims"])
    if (
        pinned["claim:claim_headers.parquet"] != _stable_file_hash(headers)
        or pinned["claim:material_claim_lines.parquet"] != _stable_file_hash(materials)
        or roster_sha != _candidate_db_hash(source_roster)
    ):
        raise ValueError("Pinned claim inputs or source roster changed during scope verification")
    return {
        "source_roster_sha256": roster_sha,
        "claim_headers_sha256": pinned["claim:claim_headers.parquet"],
        "material_lines_sha256": pinned["claim:material_claim_lines.parquet"],
        "patient_count": len(scopes),
        "claim_count": total_claims,
        "material_line_count": total_materials,
        "broad_evaluation_count": total_evaluations,
        "scope_semantic_sha256": hashlib.sha256(_canonical(scopes)).hexdigest(),
        "release_ready": False,
    }


def verify_pinned_evidence_lines(
    source_roster: Path,
    patient_details: dict[str, dict[str, Any]],
    bill_details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Check line-owned evidence against independent, pinned claim inputs."""
    if not patient_details:
        raise ValueError("Line verification requires patient details")
    labels = (
        "claim:claim_headers.parquet",
        "claim:material_claim_lines.parquet",
        "claim:procedure_claim_lines.parquet",
        "claim:drug_claim_lines.parquet",
    )
    paths, roster_sha, pinned = _pinned_claim_paths(source_roster, labels)
    scopes = _source_scopes(
        paths["claim:claim_headers.parquet"],
        paths["claim:material_claim_lines.parquet"],
        set(patient_details),
    )
    claim_owner = {
        claim["claim_id"]: patient_id
        for patient_id, scope in scopes.items()
        for claim in scope["claims"]
    }
    source_lines: dict[str, dict[tuple[str, str], list[tuple[str, Any]]]] = {}
    for kind, (label, id_column) in _LINE_SOURCES.items():
        source_lines[kind] = {}
        seen_nonprocedure: set[str] = set()
        columns = (id_column, "claim_id", "patient_id") + (
            ("billed_amount_try",) if kind == "procedure" else ()
        )
        for values in _id_rows(paths[label], columns):
            line_raw, claim_raw, patient_raw = values[:3]
            line_id = _id(line_raw, label=id_column)
            claim_id = _id(claim_raw, label=f"{kind} claim_id")
            patient_id = _id(patient_raw, label=f"{kind} patient_id")
            if kind != "procedure" and line_id in seen_nonprocedure:
                raise ValueError(f"Duplicate {kind} source line identity: {line_id}")
            seen_nonprocedure.add(line_id)
            if claim_id not in claim_owner or (
                kind != "procedure" and claim_owner[claim_id] != patient_id
            ):
                raise ValueError(f"Orphan or cross-patient {kind} source line: {line_id}")
            source_lines[kind].setdefault((claim_id, line_id), []).append(
                (patient_id, values[3] if kind == "procedure" else None)
            )

    focused_ids = {spec.rule_id for spec in FOCUSED_RULE_SPECS}
    if len(focused_ids) != 32:
        raise ValueError("Focused source roster differs from 32 authored IDs")
    checked_line_rows = 0

    def check_rows(patient_id: str, detail: dict[str, Any]) -> None:
        nonlocal checked_line_rows
        for collection in ("evaluations", "reviews", "advisories", "financial_rows"):
            rows = detail.get(collection)
            if not isinstance(rows, list):
                raise ValueError(f"Wave A {collection} lacks source rows")
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"Malformed Wave A {collection} source row")
                kind = row.get("line_kind")
                if kind == "claim":
                    continue
                if kind not in _LINE_SOURCES:
                    raise ValueError("Wave A source row has unsupported line kind")
                line_id = row.get("line_id")
                claim_id = row.get("claim_id")
                matches = (
                    source_lines[kind].get((claim_id, line_id), [])
                    if isinstance(claim_id, str) and isinstance(line_id, str)
                    else []
                )
                owned = sum(owner == patient_id for owner, _ in matches) == 1
                if not owned:
                    raise ValueError(f"Wave A {collection} line is absent from pinned {kind} Parquet")
                checked_line_rows += 1
                if collection == "financial_rows" and kind == "procedure":
                    source_reason, expected = _procedure_charge_state(matches, patient_id)
                    observed = row.get("observed_billed_amount_try")
                    basis = row.get("observed_amount_basis")
                    reason = row.get("observed_amount_unavailable_reason")
                    if source_reason is None:
                        if basis != _OBSERVED_AMOUNT_BASIS or reason is not None:
                            raise ValueError("Financial review lacks exact procedure-line amount basis")
                        if _minor_units(
                            observed, label="observed procedure billed amount"
                        ) != expected:
                            raise ValueError(
                                "Observed financial amount differs from pinned procedure line"
                            )
                    elif observed is not None or basis is not None or reason != source_reason:
                        raise ValueError("Unavailable observed charge reason differs from pinned procedure line")

    for patient_id, detail in patient_details.items():
        if detail.get("patient_id") != patient_id or detail.get("claim_scope_inventory") != scopes[
            patient_id
        ]:
            raise ValueError(f"Wave A patient scope differs from pinned claims: {patient_id}")
        check_rows(patient_id, detail)
    for key, detail in bill_details.items():
        if "::" not in key:
            raise ValueError("Wave A bill evidence key lacks claim identity")
        patient_id, claim_id = key.split("::", 1)
        if patient_id not in scopes or detail.get("patient_id") != patient_id:
            raise ValueError(f"Wave A bill evidence has foreign patient identity: {key}")
        claim = next(
            (row for row in scopes[patient_id]["claims"] if row["claim_id"] == claim_id),
            None,
        )
        if detail.get("claim_scope_inventory") != {
            "context_state": "available",
            "claims": [claim],
        }:
            raise ValueError(f"Wave A bill scope differs from pinned claims: {key}")
        check_rows(patient_id, detail)
    if any(pinned[label] != _stable_file_hash(path) for label, path in paths.items()) or (
        roster_sha != _candidate_db_hash(source_roster)
    ):
        raise ValueError("Pinned line inputs or source roster changed during verification")
    return {
        "source_roster_sha256": roster_sha,
        "line_source_sha256": pinned,
        "patient_detail_count": len(patient_details),
        "bill_detail_count": len(bill_details),
        "checked_line_evidence_rows": checked_line_rows,
        "source_line_counts": {
            kind: sum(len(matches) for matches in rows.values())
            for kind, rows in source_lines.items()
        },
        "release_ready": False,
    }
