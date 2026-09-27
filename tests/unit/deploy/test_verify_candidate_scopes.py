"""Pinned source scopes must dominate producer inventories and status counts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.deploy.verify_candidate_scopes import verify_pinned_claim_scopes
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.billing.rule_findings import build_evaluation_id

_DATA_NAMES = (
    "claim:claim_headers.parquet",
    "claim:claim_diagnoses.parquet",
    "claim:procedure_claim_lines.parquet",
    "claim:material_claim_lines.parquet",
    "claim:drug_claim_lines.parquet",
    "claim:expected_rule_outputs.parquet",
    "clean:lab_clean.parquet",
    "clean:anadata_clean.parquet",
    "clean:recete_clean.parquet",
)
_STATUSES = ("evaluated", "missing_inputs", "unavailable")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def _write_roster(root: Path) -> Path:
    sources = []
    for label in sorted(_DATA_NAMES):
        family, name = label.split(":", 1)
        path = root / family / name
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            path.write_bytes(b"source fixture")
        data = path.read_bytes()
        sources.append(
            {
                "label": label,
                "path": str(path),
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
        )
    manifest = {
        "roster_version": "wavea-source-v1",
        "source_count": len(sources),
        "roster_sha256": hashlib.sha256(_canonical(sources)).hexdigest(),
        "sources": sources,
    }
    path = root / "roster.json"
    path.write_text(json.dumps(manifest))
    return path


def _write_claim_parquets(root: Path, *, extra_material: dict | None = None) -> None:
    claims = root / "claim"
    claims.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.table({"claim_id": ["C1", "C2"], "patient_id": ["P1", "P1"]}),
        claims / "claim_headers.parquet",
    )
    materials = [
        {"material_line_id": "M1", "claim_id": "C1", "patient_id": "P1"},
        {"material_line_id": "M2", "claim_id": "C1", "patient_id": "P1"},
    ]
    if extra_material is not None:
        materials.append(extra_material)
    pq.write_table(pa.Table.from_pylist(materials), claims / "material_claim_lines.parquet")


def _detail(patient_id: str, scopes: list[tuple[str, list[str]]]) -> dict:
    catalog = load_broad_rule_catalog()
    dental = [rule.rule_id for rule in catalog if rule.family == "dental_2_4_1"]
    claim = [rule.rule_id for rule in catalog if rule.family != "dental_2_4_1"]
    evaluations = []
    counts = {rule.rule_id: Counter() for rule in catalog}

    def add(
        rule_id: str, claim_id: str | None, kind: str, line_id: str | None, status: str
    ) -> None:
        evaluations.append(
            {
                "evaluation_id": build_evaluation_id(
                    rule_id=rule_id,
                    patient_id=patient_id,
                    claim_id=claim_id,
                    line_kind=kind,
                    line_id=line_id,
                ),
                "patient_id": patient_id,
                "claim_id": claim_id,
                "rule_id": rule_id,
                "line_kind": kind,
                "line_id": line_id,
                "evaluation_status": status,
            }
        )
        counts[rule_id][status] += 1

    for claim_id, material_ids in scopes:
        for rule_id in claim:
            add(rule_id, claim_id, "claim", None, "evaluated")
        for rule_id in dental:
            if material_ids:
                for line_id in material_ids:
                    add(rule_id, claim_id, "material", line_id, "evaluated")
            else:
                add(rule_id, claim_id, "claim", None, "missing_inputs")
    if not scopes:
        for rule_id in claim + dental:
            add(rule_id, None, "claim", None, "missing_inputs")
    return {
        "claim_scope_inventory": {
            "context_state": "available" if scopes else "no_headers",
            "claims": [
                {"claim_id": claim_id, "material_line_ids": material_ids}
                for claim_id, material_ids in scopes
            ],
        },
        "evaluations": evaluations,
        "counts": {
            "by_rule": {
                rule_id: {status: counter[status] for status in _STATUSES}
                for rule_id, counter in counts.items()
            }
        },
    }


def _fixture(root: Path) -> tuple[Path, dict[str, dict]]:
    _write_claim_parquets(root)
    roster = _write_roster(root)
    return roster, {
        "P1": _detail("P1", [("C1", ["M1", "M2"]), ("C2", [])]),
        "P2": _detail("P2", []),
    }


def test_exact_material_and_no_header_cardinality_comes_from_pinned_parquet(tmp_path: Path) -> None:
    roster, details = _fixture(tmp_path)

    result = verify_pinned_claim_scopes(roster, details)

    assert result["release_ready"] is False
    assert result["patient_count"] == 2
    assert result["claim_count"] == 2
    assert result["material_line_count"] == 2
    assert result["broad_evaluation_count"] == 477 * 2 + 19 * 3 + 496


def test_unrostered_source_mutation_and_false_producer_inventory_block(tmp_path: Path) -> None:
    roster, details = _fixture(tmp_path)
    _write_claim_parquets(
        tmp_path,
        extra_material={"material_line_id": "M3", "claim_id": "C1", "patient_id": "P1"},
    )
    with pytest.raises(ValueError, match="source byte identity differs"):
        verify_pinned_claim_scopes(roster, details)

    roster = _write_roster(tmp_path)
    with pytest.raises(ValueError, match="inventory differs from pinned Parquet"):
        verify_pinned_claim_scopes(roster, details)


def test_omitted_or_wrong_scope_evaluation_blocks_even_with_matching_inventory(
    tmp_path: Path,
) -> None:
    roster, details = _fixture(tmp_path)
    removed = details["P1"]["evaluations"].pop()
    rule_counts = details["P1"]["counts"]["by_rule"][removed["rule_id"]]
    rule_counts[removed["evaluation_status"]] -= 1
    with pytest.raises(ValueError, match="scope/cardinality differs"):
        verify_pinned_claim_scopes(roster, details)

    roster, details = _fixture(tmp_path / "fresh")
    dental_row = next(
        row
        for row in details["P1"]["evaluations"]
        if row["claim_id"] == "C1" and row["line_kind"] == "material"
    )
    dental_row["line_kind"] = "claim"
    dental_row["line_id"] = None
    dental_row["evaluation_id"] = build_evaluation_id(
        rule_id=dental_row["rule_id"],
        patient_id="P1",
        claim_id="C1",
        line_kind="claim",
        line_id=None,
    )
    with pytest.raises(ValueError, match="scope/cardinality differs"):
        verify_pinned_claim_scopes(roster, details)


def test_missing_input_status_and_no_header_context_are_required(tmp_path: Path) -> None:
    roster, details = _fixture(tmp_path)
    dental_ids = {
        rule.rule_id for rule in load_broad_rule_catalog() if rule.family == "dental_2_4_1"
    }
    no_material = next(
        row
        for row in details["P1"]["evaluations"]
        if row["claim_id"] == "C2" and row["rule_id"] in dental_ids
    )
    no_material["evaluation_status"] = "evaluated"
    with pytest.raises(ValueError, match="wrong missing/source status"):
        verify_pinned_claim_scopes(roster, details)

    roster, details = _fixture(tmp_path / "fresh")
    details["P2"]["claim_scope_inventory"]["context_state"] = "missing"
    with pytest.raises(ValueError, match="inventory differs from pinned Parquet"):
        verify_pinned_claim_scopes(roster, details)


@pytest.mark.parametrize(
    "extra_material",
    [
        {"material_line_id": "M1", "claim_id": "C1", "patient_id": "P1"},
        {"material_line_id": "M3", "claim_id": "missing", "patient_id": "P1"},
        {"material_line_id": "M3", "claim_id": "C1", "patient_id": "P2"},
    ],
)
def test_duplicate_or_orphan_source_material_blocks(tmp_path: Path, extra_material: dict) -> None:
    roster, details = _fixture(tmp_path)
    _write_claim_parquets(tmp_path, extra_material=extra_material)
    roster = _write_roster(tmp_path)
    with pytest.raises(ValueError, match="Duplicate material|Orphan or cross-patient"):
        verify_pinned_claim_scopes(roster, details)


def test_pinned_claim_header_patient_cannot_be_omitted_from_reports(tmp_path: Path) -> None:
    roster, details = _fixture(tmp_path)
    pq.write_table(
        pa.table({"claim_id": ["C1", "C2", "C3"], "patient_id": ["P1", "P1", "P3"]}),
        tmp_path / "claim" / "claim_headers.parquet",
    )
    roster = _write_roster(tmp_path)
    with pytest.raises(ValueError, match="patient is absent from billing report details"):
        verify_pinned_claim_scopes(roster, details)


def test_missing_required_manifest_source_blocks(tmp_path: Path) -> None:
    roster, details = _fixture(tmp_path)
    manifest = json.loads(roster.read_text())
    manifest["sources"] = [
        source for source in manifest["sources"] if source["label"] != "claim:claim_headers.parquet"
    ]
    manifest["source_count"] = len(manifest["sources"])
    manifest["roster_sha256"] = hashlib.sha256(_canonical(manifest["sources"])).hexdigest()
    roster.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="omits required claim"):
        verify_pinned_claim_scopes(roster, details)
