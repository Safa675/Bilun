"""The single entry point over both plausibility families and the package's lazy exports.

The checks themselves are tested in `test_cohort_plausibility.py` (claims tables) and
`test_cohort_plausibility_clean.py` (clean clinical tables). Here: the registries do not clash, the
ids are routed to their family and an unknown id is refused, both families really run, the claims
problems come first, and the package exports are the module objects.
"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import polars as pl
import pytest

import scripts.synthetic.cohort as cohort
from scripts.synthetic.cohort import (
    ALL_PLAUSIBILITY_CHECKS,
    CLEAN_PLAUSIBILITY_CHECKS,
    CLEAN_TABLE_FILES,
    PLAUSIBILITY_CHECKS,
    TABLE_FILES,
    check_all_plausibility,
    check_clean_plausibility,
    check_plausibility,
)
from scripts.synthetic.cohort import plausibility_all

_OUT_DIR = cohort.DEFAULT_OUT_DIR
_CLAIMS_MODULE = "scripts.synthetic.cohort.plausibility"
_CLEAN_MODULE = "scripts.synthetic.cohort.plausibility_clean"

#: the checks the committed (faulty) showcase bills trip: one per injected fault that plausibility can see
FAULT_IDS = {
    "package.mode",
    "stay.bed_coverage",
    "anaesthesia.operation_pairing",
    "material.stray_flag",
    "bill.performed_billed",
    "stay.drug_daily_lines",
}
FORBIDDEN_ATTRIBUTES = {
    "iter_rows",
    "rows",
    "row",
    "to_dicts",
    "to_dict",
    "iterrows",
    "itertuples",
    "map_elements",
    "map_rows",
    "apply",
}


@pytest.fixture(scope="module")
def committed() -> tuple[dict[str, pl.DataFrame], dict[str, pl.DataFrame], dict]:
    claims = {name: pl.read_parquet(_OUT_DIR / "sut" / "claims" / name) for name in TABLE_FILES}
    clean = {name: pl.read_parquet(_OUT_DIR / "sut" / "clean" / name) for name in CLEAN_TABLE_FILES}
    registry = json.loads((_OUT_DIR / "cohort_registry.json").read_text(encoding="utf-8"))
    return claims, clean, registry


def test_the_two_registries_do_not_clash_and_the_union_is_exported() -> None:
    assert not PLAUSIBILITY_CHECKS.keys() & CLEAN_PLAUSIBILITY_CHECKS.keys()
    assert ALL_PLAUSIBILITY_CHECKS == {**PLAUSIBILITY_CHECKS, **CLEAN_PLAUSIBILITY_CHECKS}
    assert len(ALL_PLAUSIBILITY_CHECKS) == len(PLAUSIBILITY_CHECKS) + len(CLEAN_PLAUSIBILITY_CHECKS)
    assert len(ALL_PLAUSIBILITY_CHECKS) >= 37  # 25 claims checks and 12 clean-table checks


def test_the_committed_showcase_trips_exactly_the_pinned_faults_claims_family_first(
    committed,
) -> None:
    claims, clean, registry = committed
    found = check_all_plausibility(claims, clean, registry=registry)
    assert {problem.check for problem in found} == FAULT_IDS
    assert found == [
        *check_plausibility(claims, clean, registry=registry),
        *check_clean_plausibility(claims, clean),
    ]
    assert check_clean_plausibility(claims, clean) == []


def test_only_sends_an_id_to_its_family_and_a_family_without_ids_does_not_run(
    committed, monkeypatch
) -> None:
    claims, clean, registry = committed
    claims_module = importlib.import_module(_CLAIMS_MODULE)
    clean_module = importlib.import_module(_CLEAN_MODULE)
    calls: list[str] = []
    real_claims = claims_module.check_plausibility
    real_clean = clean_module.check_clean_plausibility

    def spy_claims(*args, **kwargs):
        calls.append("claims")
        return real_claims(*args, **kwargs)

    def spy_clean(*args, **kwargs):
        calls.append("clean")
        return real_clean(*args, **kwargs)

    monkeypatch.setattr(claims_module, "check_plausibility", spy_claims)
    monkeypatch.setattr(clean_module, "check_clean_plausibility", spy_clean)

    assert check_all_plausibility(claims, clean, only="lab.value_bounds") == []
    assert calls == ["clean"]
    calls.clear()
    got = check_all_plausibility(claims, clean, only=["package.mode"])
    assert [problem.check for problem in got] == ["package.mode", "package.mode"]  # the faulty bills of S1 and S20
    assert calls == ["claims"]
    calls.clear()
    both = check_all_plausibility(
        claims, clean, only=("package.mode", "lab.value_bounds"), registry=registry
    )
    assert [problem.check for problem in both] == ["package.mode", "package.mode"]
    assert calls == ["claims", "clean"]
    calls.clear()
    assert check_all_plausibility(claims, clean, only=[]) == []
    assert calls == []


def test_an_unknown_id_is_refused_before_anything_runs(committed) -> None:
    claims, clean, _ = committed
    with pytest.raises(KeyError, match=r"no\.such\.check"):
        check_all_plausibility(claims, clean, only=["package.mode", "no.such.check"])


def test_the_labels_checks_are_skipped_without_a_registry(committed) -> None:
    claims, clean, registry = committed
    assert check_all_plausibility(claims, clean, only="labels.answer_rows") == []
    assert check_all_plausibility(claims, clean, only="labels.answer_rows", registry=registry) == []


def test_both_families_really_run_on_one_call(committed) -> None:
    claims, clean, registry = committed
    lab = clean["lab_clean.parquet"]
    flipped = (
        lab.with_row_index("_i")
        .with_columns(
            pl.when(pl.col("_i") == 0)
            .then(~pl.col("anormal_mi"))
            .otherwise(pl.col("anormal_mi"))
            .alias("anormal_mi")
        )
        .drop("_i")
    )
    broken = {**clean, "lab_clean.parquet": flipped}
    checks = [
        problem.check for problem in check_all_plausibility(claims, broken, registry=registry)
    ]
    assert FAULT_IDS <= set(checks)
    assert "lab.flag_and_limits" in checks
    assert checks.index("lab.flag_and_limits") > max(checks.index(check) for check in FAULT_IDS)


def test_the_package_exports_are_the_module_objects() -> None:
    claims_module = importlib.import_module(_CLAIMS_MODULE)
    clean_module = importlib.import_module(_CLEAN_MODULE)
    assert cohort.check_all_plausibility is plausibility_all.check_all_plausibility
    assert cohort.ALL_PLAUSIBILITY_CHECKS is plausibility_all.ALL_CHECKS
    assert cohort.check_plausibility is claims_module.check_plausibility
    assert cohort.PlausibilityProblem is claims_module.Problem
    assert cohort.PlausibilityContext is claims_module.PlausibilityContext
    assert cohort.PlausibilityError is claims_module.PlausibilityError
    assert cohort.PLAUSIBILITY_CHECKS is claims_module.CHECKS
    assert cohort.check_clean_plausibility is clean_module.check_clean_plausibility
    assert cohort.CleanPlausibilityProblem is clean_module.Problem
    assert cohort.CleanPlausibilityContext is clean_module.CleanPlausibilityContext
    assert cohort.CLEAN_PLAUSIBILITY_CHECKS is clean_module.CHECKS
    for name in cohort._PLAUSIBILITY_EXPORTS:
        assert name in cohort.__all__
    with pytest.raises(AttributeError, match="no_such_name"):
        cohort.no_such_name  # noqa: B018 - the lookup itself is the test


def test_the_entry_point_is_plain_routing_code() -> None:
    tree = ast.parse(Path(plausibility_all.__file__).read_text(encoding="utf-8"))
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not attributes & FORBIDDEN_ATTRIBUTES
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "pandas" not in imported
    assert not any(name.startswith(("src.bilun", "bilun")) for name in imported)
