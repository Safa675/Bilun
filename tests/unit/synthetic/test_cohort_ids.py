"""Unit tests for pure ID builders in scripts/synthetic/cohort/ids.py and legacy Parquet ID format verification."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

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

_REPO = Path(__file__).resolve().parents[3]
_CLAIMS_DIR = _REPO / "data/synthetic/sut/claims"


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


def test_verify_builders_against_legacy_parquet_id_columns() -> None:
    headers = pl.read_parquet(
        _CLAIMS_DIR / "claim_headers.parquet",
        columns=["patient_id", "claim_id", "episode_id"],
    )
    assert headers.height > 0
    assert patient_id(1) in headers["patient_id"].to_list()
    assert claim_id(patient_id(1), 1) in headers["claim_id"].to_list()
    assert episode_id(patient_id(1), 1) in headers["episode_id"].to_list()
    assert all(PATIENT_ID_RE.fullmatch(v) for v in headers["patient_id"].to_list())
    assert all(CLAIM_ID_RE.fullmatch(v) for v in headers["claim_id"].to_list())
    assert all(EPISODE_ID_RE.fullmatch(v) for v in headers["episode_id"].to_list())

    diagnoses = pl.read_parquet(
        _CLAIMS_DIR / "claim_diagnoses.parquet",
        columns=["diagnosis_id"],
    )
    assert diagnoses.height > 0
    assert diagnosis_id(patient_id(1), 1, 1) in diagnoses["diagnosis_id"].to_list()
    assert all(DIAGNOSIS_ID_RE.fullmatch(v) for v in diagnoses["diagnosis_id"].to_list())

    procedures = pl.read_parquet(
        _CLAIMS_DIR / "procedure_claim_lines.parquet",
        columns=["procedure_line_id"],
    )
    assert procedures.height > 0
    assert (
        procedure_line_id(claim_id(patient_id(1), 1), 1)
        in procedures["procedure_line_id"].to_list()
    )
    assert all(PROCEDURE_LINE_ID_RE.fullmatch(v) for v in procedures["procedure_line_id"].to_list())

    materials = pl.read_parquet(
        _CLAIMS_DIR / "material_claim_lines.parquet",
        columns=["material_line_id"],
    )
    assert materials.height > 0
    assert (
        material_line_id(claim_id(patient_id(1), 1), 1) in materials["material_line_id"].to_list()
    )

    drugs = pl.read_parquet(
        _CLAIMS_DIR / "drug_claim_lines.parquet",
        columns=["drug_claim_line_id"],
    )
    assert drugs.height > 0
    assert (
        drug_claim_line_id(claim_id(patient_id(1), 1), 1) in drugs["drug_claim_line_id"].to_list()
    )
    assert all(DRUG_CLAIM_LINE_ID_RE.fullmatch(v) for v in drugs["drug_claim_line_id"].to_list())

    performed = pl.read_parquet(
        _CLAIMS_DIR / "performed_procedure_lines.parquet",
        columns=["performed_line_id", "claim_id"],
    )
    assert performed.height > 0
    assert performed["performed_line_id"].to_list() == [
        performed_line_id(claim_id(patient_id(9), 23), 1)
    ]
    assert all(PERFORMED_LINE_ID_RE.fullmatch(v) for v in performed["performed_line_id"].to_list())
