"""Read the synthetic demo cohort through its registry, never through hard-coded ids.

`data/synthetic/cohort_registry.json` is written by `python -m scripts.synthetic.cohort.build` next to the
tables the app loads (`data/synthetic/sut/claims`, `data/synthetic/sut/clean`). It names the patients and
claims, the row count of every table and the injection record of every fault. A test that needs "the
patient with the package-billed fault", "how many claims there are" or "which line carries the
deduction" asks this module instead of writing `SENTETIK-HASTA-0001`, `8` or `4122.06` in its source:
when the cohort changes and is rebuilt, the tests follow.

This module reads ONLY that JSON file, with the standard library. It never imports the generator
(`scripts.synthetic`) or the application (`src`): `test_synthetic_cohort_fixture.py` checks the
imports, and checks every value below against the committed tables, so a registry that disagrees
with its tables is caught there (and by `build --check`).

API (every function reads the registry through `load_registry()`; all of them but `load_registry()`
return a fresh object that the caller may change):

- `REGISTRY_PATH`: the path of `cohort_registry.json`.
- `load_registry()`: the parsed registry, read once per process and cached. It is shared: do not
  change it (`copy.deepcopy` it first).
- `Role(patient_id, claim_id)`: frozen dataclass, one patient and one of the patient's claims.
- `role(name)`: the `Role` called `name`. An unknown name raises `KeyError` whose message lists the
  roles. `roles()`: every role as `{name: Role}`. The roles are `default_landing` (the claim the app
  opens on) and `showcase_S1` to `showcase_S8` (the first eight stories, one claim each). They are
  fixed: a story after the eighth is a scenario, never a new role.
- `Scenario(patient_id, claim_ids)`: frozen dataclass, one patient and the claims of its bills in bill
  order (a tuple). `scenario(story)`: the `Scenario` of a story after the eighth (`S9`, ...). An
  unknown story raises `KeyError` whose message lists the scenarios. `scenarios()`: every scenario as
  `{story: Scenario}`.
- `patient_ids()` and `claim_ids()`: every patient id and every claim id of the `encounters`, each
  sorted. `patient_count()` and `claim_count()` are their lengths.
- `counts()`: `{table file name: row count}` for the 9 claims tables (`counts` of the registry, for
  example `claim_headers.parquet`) and the 3 clean tables (`clean_counts`, for example
  `lab_clean.parquet`), sorted by name.
- `fault(story)`: the injection record of the fault of a story (`S1` to `S8`, and every scenario story),
  a dict with the registry's keys. An unknown story raises `KeyError` whose message lists the stories. The keys to use:
  `amount_try` (the amount at stake as a decimal string such as `"4122.06"`; wrap it in `Decimal`),
  `line_type` (`fatura` when the fault is about the whole bill, else `islem`, `malzeme` or `ilac`),
  `line_id` (the id of the faulty line in the table of that line type, `""` when `line_type` is
  `fatura`), `line_ids` (further lines that carry the fault, for example the EMR line of an unbilled
  procedure), `claim_id`, `patient_id`, `fault_id`, `engine_rule`, `effect_kind` and `sut_section`.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import cache
import json
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "cohort_registry.json"


@dataclass(frozen=True)
class Role:
    """One patient and one of the patient's claims, as the registry names them."""

    patient_id: str
    claim_id: str


@dataclass(frozen=True)
class Scenario:
    """One patient and the claims of the patient's bills (in bill order), for a story after the eighth."""

    patient_id: str
    claim_ids: tuple[str, ...]


@cache
def load_registry() -> dict[str, Any]:
    """The parsed `cohort_registry.json`, read once per process. Shared: do not change it."""
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def roles() -> dict[str, Role]:
    """Every role of the registry as `{name: Role}`, in the registry's order."""
    return {
        name: Role(patient_id=target["patient_id"], claim_id=target["claim_id"])
        for name, target in load_registry()["roles"].items()
    }


def role(name: str) -> Role:
    """The role called `name`; `KeyError` listing the roles when there is none."""
    known = roles()
    if name not in known:
        raise KeyError(f"unknown role {name!r}; the roles are {', '.join(known)}")
    return known[name]


def scenarios() -> dict[str, Scenario]:
    """Every scenario of the registry (the stories after the eighth) as `{story: Scenario}`."""
    return {
        story: Scenario(patient_id=target["patient_id"], claim_ids=tuple(target["claim_ids"]))
        for story, target in load_registry()["scenarios"].items()
    }


def scenario(story: str) -> Scenario:
    """The scenario of `story`; `KeyError` listing the scenarios when there is none."""
    known = scenarios()
    if story not in known:
        raise KeyError(f"unknown scenario {story!r}; the scenarios are {', '.join(known)}")
    return known[story]


def patient_ids() -> list[str]:
    """The distinct patient ids of the encounters, sorted."""
    return sorted({encounter["patient_id"] for encounter in load_registry()["encounters"]})


def claim_ids() -> list[str]:
    """The distinct claim ids of the encounters, sorted."""
    return sorted({encounter["claim_id"] for encounter in load_registry()["encounters"]})


def patient_count() -> int:
    """How many patients the cohort has."""
    return len(patient_ids())


def claim_count() -> int:
    """How many claims the cohort has."""
    return len(claim_ids())


def counts() -> dict[str, int]:
    """Row count per table file name: the claims tables and the clean tables, sorted by name."""
    registry = load_registry()
    return dict(sorted({**registry["counts"], **registry["clean_counts"]}.items()))


def fault(story: str) -> dict[str, Any]:
    """The injection record of the fault of `story`; `KeyError` listing the stories that have one."""
    records = {
        record["story"]: record for record in load_registry()["faults"] if record.get("story")
    }
    if story not in records:
        raise KeyError(
            f"no fault for story {story!r}; the stories are {', '.join(sorted(records))}"
        )
    return copy.deepcopy(records[story])
