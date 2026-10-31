"""Tests for `tests/fixtures/synthetic_cohort.py`, the registry helper the other tests build on.

The helper reads `data/synthetic/cohort_registry.json` only. These tests check that what it returns
agrees with the committed tables.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

import polars as pl
import pytest

from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_CLAIMS = cohort.REGISTRY_PATH.parent / "sut" / "claims"
_CLEAN = cohort.REGISTRY_PATH.parent / "sut" / "clean"
_STORIES = tuple(f"S{n}" for n in range(1, 9))  # the stories named by roles
_SCENARIO_STORIES = ("S9", "S10", "S11", "S12", "S14", "S15", "S17", "S18", "S20", "S21", "S22", "S23", "S24", "S30", "S31", "S32", "S33", "S34", "S36", "S37", "S38", "S39", "S40", "S41", "S42", "S43", "S44", "S45", "S46", "S47", "S48", "S49", "S50", "S51", "S52", "S53", "S54", "S55", "S56", "S57", "S58", "S59", "S60", "S61", "S62", "S63", "S64")  # the stories after the eighth, named by scenarios
_CLEAN_STORIES = ("S23", "S30", "S31", "S32", "S36", "S37", "S39", "S41", "S43", "S45", "S48", "S51", "S52", "S53", "S54", "S55", "S56", "S57", "S58", "S59", "S60", "S61", "S62", "S63", "S64")  # the bills without a fault: a story and a claim, no fault record
_FAULT_STORIES = tuple(s for s in (*_STORIES, *_SCENARIO_STORIES) if s not in _CLEAN_STORIES)
_ROLE_NAMES = ("default_landing", *(f"showcase_{story}" for story in _STORIES))

#: the table and the id column of each line type a fault record can name
_LINE_TABLES = {
    "islem": ("procedure_claim_lines.parquet", "procedure_line_id"),
    "malzeme": ("material_claim_lines.parquet", "material_line_id"),
    "ilac": ("drug_claim_lines.parquet", "drug_claim_line_id"),
}
#: where a record's `line_ids` may point
_LINKED_TABLES = (
    *_LINE_TABLES.values(),
    ("performed_procedure_lines.parquet", "performed_line_id"),
)


def _claim_line_pairs(table: str, column: str) -> set[tuple[str, str]]:
    frame = pl.read_parquet(_CLAIMS / table, columns=["claim_id", column])
    return set(zip(frame["claim_id"].to_list(), frame[column].to_list(), strict=True))


def _row_count(path: Path) -> int:
    return pl.scan_parquet(path).select(pl.len()).collect().item()


def _problems() -> list[str]:
    """Every way in which what the helper returns disagrees with the committed tables."""
    problems: list[str] = []
    headers = pl.read_parquet(_CLAIMS / "claim_headers.parquet", columns=["patient_id", "claim_id"])
    header_pairs = set(
        zip(headers["patient_id"].to_list(), headers["claim_id"].to_list(), strict=True)
    )
    known = cohort.roles()

    # roles: the nine names, each a (patient, claim) pair of the headers
    if set(known) != set(_ROLE_NAMES):
        problems.append(f"roles {sorted(known)} are not {sorted(_ROLE_NAMES)}")
    for name, target in known.items():
        if (target.patient_id, target.claim_id) not in header_pairs:
            problems.append(f"role {name} {target} is not a patient and claim of claim_headers")

    # scenarios: the stories after the eighth, each a patient and claims of the headers
    scenarios = cohort.scenarios()
    if set(scenarios) != set(_SCENARIO_STORIES):
        problems.append(f"scenarios {sorted(scenarios)} are not {sorted(_SCENARIO_STORIES)}")
    for story, scenario in scenarios.items():
        for claim in scenario.claim_ids:
            if (scenario.patient_id, claim) not in header_pairs:
                problems.append(
                    f"scenario {story} {scenario.patient_id}/{claim} is not a patient and claim of claim_headers"
                )

    # ids and their counts
    if cohort.claim_ids() != sorted(headers["claim_id"].to_list()):
        problems.append("claim_ids() differ from the claim ids of claim_headers")
    if cohort.patient_ids() != sorted(set(headers["patient_id"].to_list())):
        problems.append("patient_ids() differ from the patient ids of claim_headers")
    if cohort.claim_count() != headers.height:
        problems.append(
            f"claim_count() is {cohort.claim_count()}, claim_headers has {headers.height}"
        )
    if cohort.patient_count() != headers["patient_id"].n_unique():
        problems.append(
            f"patient_count() is {cohort.patient_count()}, "
            f"claim_headers has {headers['patient_id'].n_unique()} patients"
        )

    # row counts: one entry per parquet file of the two folders, equal to the rows of the file
    on_disk = {
        path.name: _row_count(path)
        for folder in (_CLAIMS, _CLEAN)
        for path in sorted(folder.glob("*.parquet"))
    }
    registry_counts = cohort.counts()
    for name in sorted(set(on_disk) | set(registry_counts)):
        if registry_counts.get(name) != on_disk.get(name):
            problems.append(
                f"counts()[{name!r}] is {registry_counts.get(name)}, the file has {on_disk.get(name)} rows"
            )

    # faults: the record of each story agrees with its role, its answer row and its lines
    answers = pl.read_parquet(
        _CLAIMS / "expected_rule_outputs.parquet",
        columns=["claim_id", "line_type", "line_id", "expected_savings_try"],
    )
    answer_of_claim = {row["claim_id"]: row for row in answers.iter_rows(named=True)}
    pairs = {table: _claim_line_pairs(table, column) for table, column in _LINKED_TABLES}
    for story in _FAULT_STORIES:
        try:
            record = cohort.fault(story)
        except KeyError:
            problems.append(f"{story}: fault() has no record")
            continue
        claim = record["claim_id"]
        if story in _STORIES:
            target = known.get(f"showcase_{story}")
            if target is None or (target.patient_id, target.claim_id) != (
                record["patient_id"],
                claim,
            ):
                problems.append(
                    f"{story}: the fault record is not on the claim of role showcase_{story}"
                )
        else:
            scenario = scenarios.get(story)
            if scenario is None or (scenario.patient_id, claim) != (
                record["patient_id"],
                claim,
            ) or claim not in scenario.claim_ids:
                problems.append(f"{story}: the fault record is not on a claim of scenario {story}")
        answer = answer_of_claim.get(claim)
        if answer is None:
            problems.append(f"{story}: expected_rule_outputs has no row for claim {claim}")
        else:
            if (answer["line_type"], answer["line_id"]) != (record["line_type"], record["line_id"]):
                problems.append(f"{story}: the line of the record differs from the answer row")
            try:
                amount = Decimal(record["amount_try"])
            except InvalidOperation:
                problems.append(f"{story}: amount_try {record['amount_try']!r} is not a decimal")
            else:
                if round(float(amount), 2) != round(answer["expected_savings_try"], 2):
                    problems.append(
                        f"{story}: amount_try {amount} differs from the answer row "
                        f"{answer['expected_savings_try']}"
                    )
        line_type, line_id = record["line_type"], record["line_id"]
        if line_type == "fatura":
            if line_id:
                problems.append(f"{story}: a fatura fault names the line {line_id!r}")
        elif line_type in _LINE_TABLES:
            if (claim, line_id) not in pairs[_LINE_TABLES[line_type][0]]:
                problems.append(
                    f"{story}: {line_type} line {line_id!r} is not a line of claim {claim}"
                )
        else:
            problems.append(f"{story}: unknown line_type {line_type!r}")
        for extra in record["line_ids"]:
            if not any((claim, extra) in linked for linked in pairs.values()):
                problems.append(f"{story}: line_ids entry {extra!r} is not a line of claim {claim}")
    return problems


# --- 1. What the helper returns agrees with the committed tables ------------------------------------


def test_the_committed_tables_agree_with_everything_the_helper_returns() -> None:
    assert _problems() == []


def test_every_role_points_at_a_patient_and_a_claim_in_the_committed_tables() -> None:
    headers = pl.read_parquet(_CLAIMS / "claim_headers.parquet", columns=["patient_id", "claim_id"])
    pairs = set(zip(headers["patient_id"].to_list(), headers["claim_id"].to_list(), strict=True))
    copay = pl.read_parquet(_CLAIMS / "patient_copay_profiles.parquet", columns=["patient_id"])
    anadata = pl.read_parquet(_CLEAN / "anadata_clean.parquet", columns=["HASTA_ID"])
    for name, target in cohort.roles().items():
        assert (target.patient_id, target.claim_id) in pairs, name
        assert target.patient_id in copay["patient_id"].to_list(), name
        assert target.patient_id in anadata["HASTA_ID"].to_list(), name


# --- 1b. Scenarios: the stories after the eighth -----------------------------------------------------


def test_a_scenario_points_at_a_patient_and_claims_in_the_committed_tables() -> None:
    headers = pl.read_parquet(_CLAIMS / "claim_headers.parquet", columns=["patient_id", "claim_id"])
    pairs = set(zip(headers["patient_id"].to_list(), headers["claim_id"].to_list(), strict=True))
    copay = pl.read_parquet(_CLAIMS / "patient_copay_profiles.parquet", columns=["patient_id"])
    for story, scenario in cohort.scenarios().items():
        assert scenario.claim_ids and isinstance(scenario.claim_ids, tuple), story
        assert scenario.patient_id in copay["patient_id"].to_list(), story
        for claim in scenario.claim_ids:
            assert (scenario.patient_id, claim) in pairs, story


def test_every_patient_of_the_cohort_is_a_role_or_a_scenario() -> None:
    named = {target.patient_id for target in cohort.roles().values()}
    named |= {scenario.patient_id for scenario in cohort.scenarios().values()}
    assert named == set(cohort.patient_ids())
