"""Unit tests for pure ID builders in scripts/synthetic/cohort/ids.py and their agreement with the committed tables."""

from __future__ import annotations

from collections.abc import Callable

import polars as pl
import pytest

from scripts.synthetic.cohort.build import DEFAULT_OUT_DIR
from scripts.synthetic.cohort.ids import (
    CLAIM_ID_RE,
    DIAGNOSIS_ID_RE,
    DRUG_CLAIM_LINE_ID_RE,
    EPISODE_ID_RE,
    MATERIAL_LINE_ID_RE,
    PATIENT_ID_RE,
    PERFORMED_LINE_ID_RE,
    PRESCRIPTION_ID_RE,
    PROCEDURE_LINE_ID_RE,
    claim_id,
    claim_sequence,
    diagnosis_id,
    drug_claim_line_id,
    drug_line_id,
    episode_id,
    material_line_id,
    patient_id,
    performed_line_id,
    prescription_id,
    procedure_line_id,
)

pytestmark = pytest.mark.unit

_CLAIMS_DIR = DEFAULT_OUT_DIR / "sut" / "claims"


def test_id_builders_exact_formats() -> None:
    pid = patient_id(1)
    assert pid == "SENTETIK-HASTA-0001"
    assert PATIENT_ID_RE.fullmatch(pid)

    cid = claim_id(pid, 1)
    assert cid == "F-SENTETIK-HASTA-0001-001"
    assert CLAIM_ID_RE.fullmatch(cid)

    eid = episode_id(pid, 1)
    assert eid == "B-SENTETIK-HASTA-0001-001"
    assert EPISODE_ID_RE.fullmatch(eid)

    plid = procedure_line_id(cid, 1)
    assert plid == "ISL-F-SENTETIK-HASTA-0001-001-001"
    assert PROCEDURE_LINE_ID_RE.fullmatch(plid)

    mlid = material_line_id(cid, 1)
    assert mlid == "MLZ-F-SENTETIK-HASTA-0001-001-001"
    assert MATERIAL_LINE_ID_RE.fullmatch(mlid)

    dlid = drug_claim_line_id(cid, 1)
    assert dlid == "ILC-F-SENTETIK-HASTA-0001-001-001"
    assert drug_line_id(cid, 1) == dlid
    assert DRUG_CLAIM_LINE_ID_RE.fullmatch(dlid)

    dxid_two_arg = diagnosis_id(cid, 1)
    dxid_three_arg = diagnosis_id(pid, 1, 1)
    assert dxid_two_arg == "TANI-SENTETIK-HASTA-0001-001-001"
    assert dxid_three_arg == dxid_two_arg
    assert DIAGNOSIS_ID_RE.fullmatch(dxid_two_arg)

    emr_cid = claim_id(patient_id(9), 23)
    emr_id = performed_line_id(emr_cid, 1)
    assert emr_id == "EMR-F-SENTETIK-HASTA-0009-023-001"
    assert PERFORMED_LINE_ID_RE.fullmatch(emr_id)

    rx_id = prescription_id(cid)
    assert rx_id == "RCT-F-SENTETIK-HASTA-0001-001"
    assert PRESCRIPTION_ID_RE.fullmatch(rx_id)


@pytest.mark.parametrize(
    ("fn", "args"),
    [
        (patient_id, (0,)),
        (patient_id, (-1,)),
        (patient_id, (10000,)),
        (patient_id, (True,)),
        (claim_id, ("BAD", 1)),
        (claim_id, ("SENTETIK-HASTA-0001", 0)),
        (claim_id, ("SENTETIK-HASTA-0001", 1000)),
        (episode_id, ("BAD", 1)),
        (episode_id, ("SENTETIK-HASTA-0001", 0)),
        (procedure_line_id, ("BAD", 1)),
        (procedure_line_id, ("F-SENTETIK-HASTA-0001-001", 0)),
        (material_line_id, ("BAD", 1)),
        (drug_claim_line_id, ("BAD", 1)),
        (diagnosis_id, ("BAD", 1)),
        (diagnosis_id, ("BAD", 1, 1)),
        (diagnosis_id, ("SENTETIK-HASTA-0001", 0, 1)),
        (diagnosis_id, ("SENTETIK-HASTA-0001", 1, 0)),
        (performed_line_id, ("BAD", 1)),
        (performed_line_id, ("F-SENTETIK-HASTA-0001-001", 0)),
        (prescription_id, ("BAD",)),
    ],
)
def test_id_builders_reject_invalid_inputs(fn: object, args: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        fn(*args)  # type: ignore[operator]


def _trailing_int(identifier: str) -> int:
    return int(identifier.rsplit("-", 1)[1])


def _lines_per_claim(table: str, column: str) -> dict[str, list[str]]:
    """The ids of one committed table, sorted, per claim."""
    frame = pl.read_parquet(_CLAIMS_DIR / f"{table}.parquet", columns=["claim_id", column])
    assert frame.height > 0, table
    grouped = frame.group_by("claim_id").agg(pl.col(column).sort())
    return dict(zip(grouped["claim_id"].to_list(), grouped[column].to_list(), strict=True))


def test_builders_reproduce_the_id_columns_of_the_committed_tables() -> None:
    headers = pl.read_parquet(
        _CLAIMS_DIR / "claim_headers.parquet",
        columns=["patient_id", "claim_id", "episode_id"],
    )
    assert headers.height > 0
    # The patient number and the claim sequence are in the ids: rebuild each id from them.
    for pid, cid, eid in headers.sort("claim_id").iter_rows():
        number, seq = _trailing_int(pid), _trailing_int(cid)
        assert PATIENT_ID_RE.fullmatch(pid) and pid == patient_id(number)
        assert CLAIM_ID_RE.fullmatch(cid) and cid == claim_id(patient_id(number), seq)
        assert EPISODE_ID_RE.fullmatch(eid) and eid == episode_id(patient_id(number), seq)

    # The lines of a claim are numbered 1..n by the builders, in every committed line table.
    by_claim_builders: tuple[tuple[str, str, Callable[[str, int], str], object], ...] = (
        ("procedure_claim_lines", "procedure_line_id", procedure_line_id, PROCEDURE_LINE_ID_RE),
        ("material_claim_lines", "material_line_id", material_line_id, MATERIAL_LINE_ID_RE),
        ("drug_claim_lines", "drug_claim_line_id", drug_claim_line_id, DRUG_CLAIM_LINE_ID_RE),
        ("performed_procedure_lines", "performed_line_id", performed_line_id, PERFORMED_LINE_ID_RE),
    )
    for table, column, builder, pattern in by_claim_builders:
        for cid, ids in _lines_per_claim(table, column).items():
            assert ids == [builder(cid, n) for n in range(1, len(ids) + 1)], (table, cid)
            assert all(pattern.fullmatch(v) for v in ids), (table, cid)  # type: ignore[attr-defined]

    # A diagnosis id carries the patient, the claim sequence and the diagnosis sequence.
    patient_of_claim = dict(zip(headers["claim_id"], headers["patient_id"], strict=True))
    for cid, ids in _lines_per_claim("claim_diagnoses", "diagnosis_id").items():
        pid, seq = patient_of_claim[cid], _trailing_int(cid)
        assert ids == [diagnosis_id(pid, seq, n) for n in range(1, len(ids) + 1)], cid
        assert all(DIAGNOSIS_ID_RE.fullmatch(v) for v in ids), cid


def test_claim_sequence_is_the_sequence_claim_id_was_built_with() -> None:
    pid = patient_id(4)
    for sequence in (1, 2, 17, 999):
        assert claim_sequence(claim_id(pid, sequence)) == sequence
    assert claim_sequence("F-SENTETIK-HASTA-0004-002") == 2
    # the patient part does not leak into it, and the diagnosis id carries the same number
    assert claim_sequence(claim_id(patient_id(1234), 5)) == 5
    assert diagnosis_id(claim_id(pid, 7), 3) == "TANI-SENTETIK-HASTA-0004-007-003"


@pytest.mark.parametrize(
    "bad",
    [
        "F-SENTETIK-HASTA-0004",  # no sequence
        "F-SENTETIK-HASTA-0004-0001",  # four digits
        "F-SENTETIK-HASTA-0004-01",  # two digits
        "B-SENTETIK-HASTA-0004-001",  # an episode id, not a claim id
        "ISL-F-SENTETIK-HASTA-0004-001-001",  # a line id
        "F-SENTETIK-HASTA-0004-001 ",  # trailing blank
        "",
        5,
        None,
    ],
)
def test_claim_sequence_refuses_what_is_no_claim_id(bad: object) -> None:
    with pytest.raises(ValueError, match="invalid claim_id"):
        claim_sequence(bad)  # type: ignore[arg-type]
