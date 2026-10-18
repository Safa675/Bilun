"""Tests for `tests/fixtures/synthetic_cohort.py`, the registry helper the other tests build on.

The helper reads `data/synthetic/cohort_registry.json` only. These tests check that what it returns
agrees with the committed tables (roles, counts, ids, fault records), that it imports nothing but the
standard library, and that a damaged registry (changed in memory) is caught by those checks.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
import copy
from decimal import Decimal, InvalidOperation
from pathlib import Path
import subprocess
import sys
from typing import Any

import polars as pl
import pytest

from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAIMS = cohort.REGISTRY_PATH.parent / "sut" / "claims"
_CLEAN = cohort.REGISTRY_PATH.parent / "sut" / "clean"
_STORIES = tuple(f"S{n}" for n in range(1, 9))
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
    for story in _STORIES:
        try:
            record = cohort.fault(story)
        except KeyError:
            problems.append(f"{story}: fault() has no record")
            continue
        claim = record["claim_id"]
        target = known.get(f"showcase_{story}")
        if target is None or (target.patient_id, target.claim_id) != (record["patient_id"], claim):
            problems.append(
                f"{story}: the fault record is not on the claim of role showcase_{story}"
            )
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


def _record(registry: dict[str, Any], story: str) -> dict[str, Any]:
    return next(record for record in registry["faults"] if record["story"] == story)


# --- 1. What the helper returns agrees with the committed tables ------------------------------------


def test_the_committed_tables_agree_with_everything_the_helper_returns() -> None:
    assert _problems() == []


def test_the_roles_are_the_default_landing_and_the_eight_stories() -> None:
    known = cohort.roles()
    assert tuple(known) == _ROLE_NAMES
    assert all(isinstance(target, cohort.Role) for target in known.values())
    assert {name: cohort.role(name) for name in _ROLE_NAMES} == known
    assert len({known[f"showcase_{story}"] for story in _STORIES}) == len(_STORIES)
    assert known["default_landing"] in {known[f"showcase_{story}"] for story in _STORIES}


def test_every_role_points_at_a_patient_and_a_claim_in_the_committed_tables() -> None:
    headers = pl.read_parquet(_CLAIMS / "claim_headers.parquet", columns=["patient_id", "claim_id"])
    pairs = set(zip(headers["patient_id"].to_list(), headers["claim_id"].to_list(), strict=True))
    copay = pl.read_parquet(_CLAIMS / "patient_copay_profiles.parquet", columns=["patient_id"])
    anadata = pl.read_parquet(_CLEAN / "anadata_clean.parquet", columns=["HASTA_ID"])
    for name, target in cohort.roles().items():
        assert (target.patient_id, target.claim_id) in pairs, name
        assert target.patient_id in copay["patient_id"].to_list(), name
        assert target.patient_id in anadata["HASTA_ID"].to_list(), name


def test_counts_are_the_row_counts_of_all_twelve_committed_tables() -> None:
    expected = {
        path.name: _row_count(path)
        for folder in (_CLAIMS, _CLEAN)
        for path in sorted(folder.glob("*.parquet"))
    }
    assert len(expected) == 12
    assert cohort.counts() == expected
    assert list(cohort.counts()) == sorted(expected)
    assert cohort.claim_count() == expected["claim_headers.parquet"]
    assert cohort.patient_count() == expected["patient_copay_profiles.parquet"]


def test_patient_and_claim_ids_are_sorted_and_come_from_the_encounters() -> None:
    patients, claims = cohort.patient_ids(), cohort.claim_ids()
    assert patients == sorted(patients) and claims == sorted(claims)
    assert len(set(patients)) == len(patients) == cohort.patient_count()
    assert len(set(claims)) == len(claims) == cohort.claim_count()
    encounters = cohort.load_registry()["encounters"]
    assert set(patients) == {encounter["patient_id"] for encounter in encounters}
    assert set(claims) == {encounter["claim_id"] for encounter in encounters}


def test_every_story_has_a_fault_record_with_an_amount_a_line_type_and_a_line() -> None:
    for story in _STORIES:
        record = cohort.fault(story)
        assert record["story"] == story
        assert Decimal(record["amount_try"]) >= 0
        assert record["line_type"] in {"fatura", *_LINE_TABLES}
        assert (record["line_type"] == "fatura") == (record["line_id"] == "")
        assert record["claim_id"] == cohort.role(f"showcase_{story}").claim_id


# --- 2. Behaviour of the API -------------------------------------------------------------------------


def test_unknown_names_raise_key_errors_that_list_the_valid_ones() -> None:
    with pytest.raises(KeyError) as role_error:
        cohort.role("showcase_S9")
    assert all(name in str(role_error.value) for name in _ROLE_NAMES)
    with pytest.raises(KeyError) as fault_error:
        cohort.fault("S9")
    assert all(story in str(fault_error.value) for story in _STORIES)


def test_the_registry_is_read_once_and_the_accessors_return_copies() -> None:
    assert cohort.load_registry() is cohort.load_registry()
    assert cohort.REGISTRY_PATH == _REPO / "data" / "synthetic" / "cohort_registry.json"
    before = (cohort.counts(), cohort.patient_ids(), cohort.fault("S5"), cohort.roles())
    cohort.counts()["claim_headers.parquet"] = -1
    cohort.patient_ids().append("SENTETIK-HASTA-9999")
    cohort.fault("S5")["line_ids"].append("X")
    cohort.fault("S5")["amount_try"] = "0.00"
    cohort.roles().clear()
    assert (cohort.counts(), cohort.patient_ids(), cohort.fault("S5"), cohort.roles()) == before
    with pytest.raises(AttributeError):
        cohort.role("default_landing").claim_id = "X"  # type: ignore[misc]


# --- 3. The helper reads the registry only -----------------------------------------------------------


def test_the_helper_imports_only_the_standard_library() -> None:
    tree = ast.parse(Path(cohort.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "no relative import"
            imported.add((node.module or "").split(".")[0])
    assert imported
    assert imported <= set(sys.stdlib_module_names), sorted(imported - set(sys.stdlib_module_names))


def test_importing_the_helper_loads_neither_the_generator_nor_the_app() -> None:
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import tests.fixtures.synthetic_cohort; "
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('scripts', 'src', 'polars', 'pydantic')); "
        "assert not bad, bad"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", code, str(_REPO)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr


# --- 4. A damaged registry is caught -----------------------------------------------------------------


def _damaged_problems(
    monkeypatch: pytest.MonkeyPatch, change: Callable[[dict[str, Any]], None]
) -> str:
    registry = copy.deepcopy(cohort.load_registry())
    change(registry)
    monkeypatch.setattr(cohort, "load_registry", lambda: registry)
    return "\n".join(_problems())


def _drop_encounter(registry: dict[str, Any]) -> None:
    registry["encounters"].pop()


def _rename_patient_of_first_encounter(registry: dict[str, Any]) -> None:
    registry["encounters"][0]["patient_id"] = "SENTETIK-HASTA-0099"


def _drop_fault(registry: dict[str, Any], story: str) -> None:
    registry["faults"].remove(_record(registry, story))


def _set_role(registry: dict[str, Any], name: str, **changes: str) -> None:
    registry["roles"][name].update(changes)


_DAMAGES: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
    (
        "role_on_an_unknown_claim",
        lambda r: _set_role(r, "showcase_S2", claim_id="F-SENTETIK-HASTA-0099-001"),
        "role showcase_S2",
    ),
    (
        "role_with_the_patient_of_another_claim",
        lambda r: _set_role(r, "showcase_S3", patient_id=r["roles"]["showcase_S4"]["patient_id"]),
        "role showcase_S3",
    ),
    ("role_removed", lambda r: r["roles"].pop("showcase_S5"), "roles ["),
    ("role_added", lambda r: r["roles"].update(showcase_S9=r["roles"]["showcase_S1"]), "roles ["),
    (
        "claims_count_one_too_high",
        lambda r: r["counts"].update(
            {"procedure_claim_lines.parquet": r["counts"]["procedure_claim_lines.parquet"] + 1}
        ),
        "procedure_claim_lines.parquet",
    ),
    (
        "clean_count_one_too_low",
        lambda r: r["clean_counts"].update(
            {"lab_clean.parquet": r["clean_counts"]["lab_clean.parquet"] - 1}
        ),
        "lab_clean.parquet",
    ),
    (
        "table_missing_from_counts",
        lambda r: r["counts"].pop("drug_claim_lines.parquet"),
        "drug_claim_lines.parquet",
    ),
    (
        "table_that_does_not_exist",
        lambda r: r["counts"].update({"ghost.parquet": 3}),
        "ghost.parquet",
    ),
    ("encounter_dropped", _drop_encounter, "claim_ids() differ"),
    ("patient_of_an_encounter_changed", _rename_patient_of_first_encounter, "patient_ids() differ"),
    (
        "amount_one_cent_off",
        lambda r: _record(r, "S1").update(amount_try="4122.07"),
        "S1: amount_try",
    ),
    ("amount_not_a_number", lambda r: _record(r, "S2").update(amount_try="n/a"), "S2: amount_try"),
    (
        "line_that_is_not_in_the_claim",
        lambda r: _record(r, "S5").update(line_id="MLZ-F-SENTETIK-HASTA-0005-001-099"),
        "S5:",
    ),
    ("line_type_of_another_table", lambda r: _record(r, "S5").update(line_type="ilac"), "S5:"),
    (
        "line_type_unknown",
        lambda r: _record(r, "S8").update(line_type="paket"),
        "S8: unknown line_type",
    ),
    (
        "bill_fault_that_names_a_line",
        lambda r: _record(r, "S1").update(line_id="ISL-F-SENTETIK-HASTA-0001-001-001"),
        "S1:",
    ),
    (
        "extra_line_that_is_not_in_the_claim",
        lambda r: _record(r, "S7").update(line_ids=["EMR-F-SENTETIK-HASTA-0007-001-099"]),
        "S7: line_ids entry",
    ),
    (
        "fault_on_another_claim",
        lambda r: _record(r, "S2").update(claim_id=_record(r, "S3")["claim_id"]),
        "S2:",
    ),
    ("fault_dropped", lambda r: _drop_fault(r, "S6"), "S6: fault() has no record"),
]


@pytest.mark.parametrize(
    ("change", "expected"),
    [pytest.param(change, expected, id=name) for name, change, expected in _DAMAGES],
)
def test_a_damaged_registry_is_caught(
    monkeypatch: pytest.MonkeyPatch,
    change: Callable[[dict[str, Any]], None],
    expected: str,
) -> None:
    assert _problems() == []
    assert expected in _damaged_problems(monkeypatch, change)
