"""Acceptance, round-trip, determinism, hygiene and mutation tests for `scripts/synthetic/cohort/build.py`."""

from __future__ import annotations

from collections.abc import Iterator
import copy
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any
import warnings

import polars as pl
import pytest
from pydantic import ValidationError

from scripts.synthetic.cohort import (
    CLAIM_ID_RE,
    CLEAN_TABLE_FILES,
    DIAGNOSIS_ID_RE,
    DRUG_CLAIM_LINE_ID_RE,
    EPISODE_ID_RE,
    MATERIAL_LINE_ID_RE,
    PATIENT_ID_RE,
    PERFORMED_LINE_ID_RE,
    PRESCRIPTION_ID_RE,
    PROCEDURE_LINE_ID_RE,
    RECIPES_PATH,
    TABLE_FILES,
    BuildError,
    BuildResult,
    RecipeLoadError,
    ShowcaseRecipe,
    ShowcaseRecipes,
    build_showcase,
    build_tables,
    check_recipes,
    clean_tables_digest,
    load_recipes,
    tables_digest,
    validate_cohort_registry,
    write_showcase,
)
from scripts.synthetic.cohort.build import DEFAULT_OUT_DIR, _medula_event_rows, check_showcase, main
from scripts.synthetic.cohort.recipes import EncounterPins, MedulaEvent
from scripts.synthetic.faults import (
    FaultApplyError,
    FaultInjectionRecord,
    apply_fault,
    build_expected_rule_outputs,
    load_registry,
    make_record,
)
from scripts.synthetic.pathways import load_all
from scripts.synthetic.pathways.loader import hygiene
import src.bilun.domain.claims.config as claims_config
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.models import ExpectedRuleOutput, PatientCopayProfile
from tests.fixtures import synthetic_cohort as cohort
from tests.fixtures.synthetic_encounters import STANDARD_EXTRAS, Extra, with_encounters

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_OUT_DIR = DEFAULT_OUT_DIR
_CLAIMS_DIR = _OUT_DIR / "sut" / "claims"
_CLEAN_DIR = _OUT_DIR / "sut" / "clean"
_REGISTRY_JSON_PATH = _OUT_DIR / "cohort_registry.json"
_RESULTS_DIR = _REPO / "reports/synthetic-data/2026-10-15-showcase-proofs/results"

_EXPECTED_AMOUNTS_BY_STORY: dict[str, str] = {
    "S1": "4122.06",
    "S2": "667.08",
    "S3": "928.09",
    "S4": "370.50",
    "S5": "6465.27",
    "S6": "0.00",
    "S7": "1138.22",
    "S8": "5377.20",
    "S9": "758.01",
    "S10": "5.88",
    "S11": "6089.82",
    "S12": "1322.94",
    "S14": "222.36",
    "S17": "0.00",  # the ESA prescribed by the wrong branch: a drug line, and drugs enter at 0 TL
    "S18": "0.00",  # the albumin without the specialist report: a drug line, and drugs enter at 0 TL
    "S20": "4724.84",
    "S22": "439.86",
    "S24": "0.00",  # the red-cell units without their ISBT 128 numbers: a flag of the lines, no amount (a compliance error)
    "S33": "0.00",  # the enoxaparin count: a drug line, and drugs enter at 0 TL
    "S34": "0.00",  # the examination flagged as a package component: a flag without money
    "S40": "0.00",
    "S46": "252.00",  # the second walker inside the MIAT of the first: the walker line is at risk (deduction_risk)
    "S47": "44.45",
}

# The stories after the eighth, as the committed registry names them: a patient and the claims of its bills.
# S23, S32, S39, S45 and S48 are clean bills (no fault, no record), the others carry one.
_COMMITTED_SCENARIOS: dict[str, dict[str, Any]] = {
    "S9": {"patient_id": "SENTETIK-HASTA-0009", "claim_ids": ["F-SENTETIK-HASTA-0009-001"]},
    "S11": {"patient_id": "SENTETIK-HASTA-0010", "claim_ids": ["F-SENTETIK-HASTA-0010-001"]},
    "S12": {"patient_id": "SENTETIK-HASTA-0011", "claim_ids": ["F-SENTETIK-HASTA-0011-001"]},
    "S14": {"patient_id": "SENTETIK-HASTA-0010", "claim_ids": ["F-SENTETIK-HASTA-0010-002"]},
    "S10": {"patient_id": "SENTETIK-HASTA-0012", "claim_ids": ["F-SENTETIK-HASTA-0012-001"]},
    "S22": {"patient_id": "SENTETIK-HASTA-0012", "claim_ids": ["F-SENTETIK-HASTA-0012-002"]},
    "S32": {"patient_id": "SENTETIK-HASTA-0002", "claim_ids": ["F-SENTETIK-HASTA-0002-002"]},
    "S33": {"patient_id": "SENTETIK-HASTA-0002", "claim_ids": ["F-SENTETIK-HASTA-0002-003"]},
    "S34": {"patient_id": "SENTETIK-HASTA-0002", "claim_ids": ["F-SENTETIK-HASTA-0002-004"]},
    "S20": {"patient_id": "SENTETIK-HASTA-0013", "claim_ids": ["F-SENTETIK-HASTA-0013-001"]},
    "S17": {"patient_id": "SENTETIK-HASTA-0014", "claim_ids": ["F-SENTETIK-HASTA-0014-001"]},
    "S23": {"patient_id": "SENTETIK-HASTA-0014", "claim_ids": ["F-SENTETIK-HASTA-0014-002"]},
    "S18": {"patient_id": "SENTETIK-HASTA-0015", "claim_ids": ["F-SENTETIK-HASTA-0015-001"]},
    "S24": {"patient_id": "SENTETIK-HASTA-0015", "claim_ids": ["F-SENTETIK-HASTA-0015-002"]},
    "S47": {"patient_id": "SENTETIK-HASTA-0007", "claim_ids": ["F-SENTETIK-HASTA-0007-002"]},
    "S48": {"patient_id": "SENTETIK-HASTA-0007", "claim_ids": ["F-SENTETIK-HASTA-0007-003"]},
    "S39": {"patient_id": "SENTETIK-HASTA-0004", "claim_ids": ["F-SENTETIK-HASTA-0004-002"]},
    "S40": {"patient_id": "SENTETIK-HASTA-0004", "claim_ids": ["F-SENTETIK-HASTA-0004-003"]},
    "S45": {"patient_id": "SENTETIK-HASTA-0006", "claim_ids": ["F-SENTETIK-HASTA-0006-002"]},
    "S46": {"patient_id": "SENTETIK-HASTA-0006", "claim_ids": ["F-SENTETIK-HASTA-0006-003"]},
}

_ANON_RE = re.compile(r"anon_|\banon[\s-]*[0-9]", re.IGNORECASE)
_CURRENCY_RE = re.compile(
    r"(?=[0-9.,]*[1-9])[0-9][0-9.,]*\s*(?:TL|TRY|\u20ba)(?![A-Za-z])|\u20ba\s*(?=[0-9.,]*[1-9])[0-9][0-9.,]*",
    re.IGNORECASE,
)


@pytest.fixture(autouse=True)
def _fresh_claims_cache() -> Iterator[None]:
    """`load_sut_claim_dataset` caches by arguments: every test starts and ends with an empty cache."""
    load_sut_claim_dataset.cache_clear()
    yield
    load_sut_claim_dataset.cache_clear()


@pytest.fixture(scope="module")
def built_showcase() -> BuildResult:
    return build_showcase()


# --- 2. Build equals committed & CLI --check ---------------------------------------------------


def test_build_showcase_equals_committed_files(built_showcase: BuildResult) -> None:
    assert _REGISTRY_JSON_PATH.is_file()
    committed_text = _REGISTRY_JSON_PATH.read_text(encoding="utf-8")
    committed_json = json.loads(committed_text)

    assert built_showcase.registry == committed_json
    assert built_showcase.registry_json == committed_text

    for name in TABLE_FILES:
        committed_path = _CLAIMS_DIR / name
        assert committed_path.is_file(), f"Missing committed table {committed_path}"
        committed_df = pl.read_parquet(committed_path)
        built_df = built_showcase.tables[name]
        assert dict(committed_df.schema) == dict(built_df.schema), name
        assert committed_df.equals(built_df, null_equal=True), name

    for name in CLEAN_TABLE_FILES:
        committed_clean_path = _CLEAN_DIR / name
        assert committed_clean_path.is_file(), (
            f"Missing committed clean table {committed_clean_path}"
        )
        committed_df = pl.read_parquet(committed_clean_path)
        built_df = built_showcase.clean_tables[name]
        assert dict(committed_df.schema) == dict(built_df.schema), name
        assert committed_df.equals(built_df, null_equal=True), name


def test_cli_check_passes_on_committed_and_fails_on_table_or_json_change(
    built_showcase: BuildResult,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry_counts = cohort.load_registry()["counts"]
    assert main(["--check"]) == 0
    assert f"ok ({cohort.claim_count()} claims, {len(registry_counts)} tables)" in capsys.readouterr().out

    assert main(["--out", str(_OUT_DIR), "--check"]) == 0
    capsys.readouterr()

    # Write a fresh copy of the dataset to tmp_path (the builder's own files, nothing else of
    # data/synthetic) and verify --check passes on the untouched copy.
    copy_dir = tmp_path / "dataset_copy"
    write_showcase(built_showcase, copy_dir)
    assert main(["--out", str(copy_dir), "--check"]) == 0
    capsys.readouterr()

    # (a) Mutate one value of one table in the copy -> --check exits 1.
    proc_path = copy_dir / "sut" / "claims" / "procedure_claim_lines.parquet"
    proc_df = pl.read_parquet(proc_path)
    first_id = proc_df["procedure_line_id"][0]
    first_val = proc_df["billed_amount_try"][0]
    mutated_proc_df = proc_df.with_columns(
        pl.when(pl.col("procedure_line_id") == first_id)
        .then(pl.lit(round(first_val + 1.00, 2), dtype=pl.Float64))
        .otherwise(pl.col("billed_amount_try"))
        .alias("billed_amount_try")
    )
    mutated_proc_df.write_parquet(proc_path)
    assert main(["--out", str(copy_dir), "--check"]) == 1
    assert "procedure_claim_lines.parquet" in capsys.readouterr().err

    # Restore the table and verify --check exits 0 again.
    proc_df.write_parquet(proc_path)
    assert main(["--out", str(copy_dir), "--check"]) == 0
    capsys.readouterr()

    # (b) Mutate one JSON field in cohort_registry.json -> --check exits 1.
    reg_path = copy_dir / "cohort_registry.json"
    reg_data = json.loads(reg_path.read_text(encoding="utf-8"))
    reg_data["dataset_id"] = "showcase-v3-tampered"
    reg_path.write_text(json.dumps(reg_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert main(["--out", str(copy_dir), "--check"]) == 1
    assert "cohort_registry.json" in capsys.readouterr().err

    # (c) Missing file -> --check exits 1.
    reg_path.unlink()
    assert main(["--out", str(copy_dir), "--check"]) == 1
    assert "missing" in capsys.readouterr().err


# --- 3. Determinism ----------------------------------------------------------------------------


def test_determinism_in_memory_and_byte_identical_writes(tmp_path: Path) -> None:
    first = build_showcase()
    second = build_showcase()

    assert first == second
    assert first.registry == second.registry
    assert first.registry_json == second.registry_json
    for name in TABLE_FILES:
        assert first.tables[name].equals(second.tables[name], null_equal=True), name
    for name in CLEAN_TABLE_FILES:
        assert first.clean_tables[name].equals(second.clean_tables[name], null_equal=True), name

    dir_a = tmp_path / "run_a"
    dir_b = tmp_path / "run_b"
    assert main(["--out", str(dir_a)]) == 0
    assert main(["--out", str(dir_b)]) == 0

    assert (dir_a / "cohort_registry.json").read_bytes() == (
        dir_b / "cohort_registry.json"
    ).read_bytes()
    for name in TABLE_FILES:
        bytes_a = (dir_a / "sut" / "claims" / name).read_bytes()
        bytes_b = (dir_b / "sut" / "claims" / name).read_bytes()
        assert bytes_a == bytes_b, f"Parquet bytes differed across two writes for {name}"
    for name in CLEAN_TABLE_FILES:
        bytes_a = (dir_a / "sut" / "clean" / name).read_bytes()
        bytes_b = (dir_b / "sut" / "clean" / name).read_bytes()
        assert bytes_a == bytes_b, f"Clean Parquet bytes differed across two writes for {name}"


# --- 4. Loader acceptance ----------------------------------------------------------------------


def test_loader_accepts_committed_showcase_dataset_and_matches_composed_claims(
    built_showcase: BuildResult,
) -> None:
    load_sut_claim_dataset.cache_clear()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dataset = load_sut_claim_dataset(_CLAIMS_DIR, mode="synthetic_demo")

    expected_counts = built_showcase.registry["counts"]
    assert len(dataset.claims) == cohort.claim_count() == expected_counts["claim_headers.parquet"]
    assert len(dataset.diagnoses) == expected_counts["claim_diagnoses.parquet"]
    assert len(dataset.procedure_lines) == expected_counts["procedure_claim_lines.parquet"]
    assert len(dataset.material_lines) == expected_counts["material_claim_lines.parquet"]
    assert len(dataset.drug_lines) == expected_counts["drug_claim_lines.parquet"]
    # an answer row for every injected fault, none for a clean bill (S32, S39, S45, S48)
    assert len(dataset.expected_outputs) == len(cohort.load_registry()["faults"]) == expected_counts["expected_rule_outputs.parquet"]
    assert (
        len(dataset.copay_profiles_by_patient)
        == cohort.patient_count()
        == expected_counts["patient_copay_profiles.parquet"]
    )
    assert (
        len(dataset.performed_procedure_lines)
        == expected_counts["performed_procedure_lines.parquet"]
    )
    assert len(dataset.medula_rejection_events) == expected_counts["medula_rejection_events.parquet"] == 1
    assert set(dataset.medula_rejection_events) == {"RED-F-SENTETIK-HASTA-0012-001-01"}  # the one rejection of S10

    # Loaded objects equal the composed faulty claims.
    assert tuple(dataset.claims.values()) == tuple(c.header for c in built_showcase.claims)
    for composed in built_showcase.claims:
        cid = composed.header.claim_id
        assert dataset.claims[cid] == composed.header
        assert dataset.diagnoses_by_claim.get(cid, ()) == composed.diagnoses
        assert dataset.procedure_lines_by_claim.get(cid, ()) == composed.procedures
        assert dataset.material_lines_by_claim.get(cid, ()) == composed.materials
        assert dataset.drug_lines_by_claim.get(cid, ()) == composed.drugs
        assert dataset.performed_procedure_lines_by_claim.get(cid, ()) == composed.performed

    for prof in built_showcase.copay_profiles:
        pid = prof["patient_id"]
        assert dataset.copay_profiles_by_patient[pid] == PatientCopayProfile(**prof)

    # Every answer row's line_id is a line of the loaded dataset of the right type.
    for row in built_showcase.answer_rows:
        oid = row["expected_output_id"]
        loaded_out = dataset.expected_outputs[oid]
        assert loaded_out == ExpectedRuleOutput(**row)
        ltype = loaded_out.line_type
        lid = loaded_out.line_id
        if ltype == "fatura":
            assert lid == ""
        elif ltype == "islem":
            assert lid in dataset.procedure_lines
            assert dataset.procedure_lines[lid].claim_id == loaded_out.claim_id
        elif ltype == "malzeme":
            assert lid in dataset.material_lines
            assert dataset.material_lines[lid].claim_id == loaded_out.claim_id
        elif ltype == "ilac":
            assert lid in dataset.drug_lines
            assert dataset.drug_lines[lid].claim_id == loaded_out.claim_id
        else:
            pytest.fail(f"Unexpected line_type {ltype!r}")


# --- 5. Effects match proof results/S<n>.json --------------------------------------------------


def test_effects_match_showcase_proof_results(built_showcase: BuildResult) -> None:
    assert len(built_showcase.records) == len(cohort.load_registry()["faults"])
    by_story = {rec.story: rec for rec in built_showcase.records}
    assert set(by_story) == set(_EXPECTED_AMOUNTS_BY_STORY)

    for story, expected_amount in _EXPECTED_AMOUNTS_BY_STORY.items():
        rec = by_story[story]
        proof = json.loads((_RESULTS_DIR / f"{story}.json").read_text(encoding="utf-8"))
        assert rec.amount_try == expected_amount, story
        assert rec.billed_clean_try == proof["clean"]["total_billed"], story
        assert rec.billed_faulty_try == proof["faulty"]["total_billed"], story

    # S7 carries the performed CT angiography line ID in line_ids.
    s7_rec = by_story["S7"]
    assert s7_rec.line_id == ""
    assert s7_rec.line_ids == ("EMR-F-SENTETIK-HASTA-0007-001-004",)

    # S1, S5, S8, S20 and the haemodialysis bills S17 and S23 (EK-2C session packages) have package_candidate=True in
    # both clean and faulty composed headers; others False. The story of a bill comes from its encounter (a clean bill,
    # S23, S32, S39, S45 or S48, has no record).
    story_of_claim = {e["claim_id"]: e["story"] for e in built_showcase.registry["encounters"]}
    for clean_c, faulty_c in zip(built_showcase.clean_claims, built_showcase.claims, strict=True):
        story = story_of_claim[faulty_c.header.claim_id]
        expected_pkg_cand = story in {"S1", "S5", "S8", "S17", "S20", "S23"}
        assert clean_c.header.package_candidate is expected_pkg_cand
        assert faulty_c.header.package_candidate is expected_pkg_cand


# --- 6. Registry consistency -------------------------------------------------------------------


def test_registry_consistency_against_committed_tables(built_showcase: BuildResult) -> None:
    committed_reg = json.loads(_REGISTRY_JSON_PATH.read_text(encoding="utf-8"))
    committed_tables = {name: pl.read_parquet(_CLAIMS_DIR / name) for name in TABLE_FILES}
    committed_clean = {name: pl.read_parquet(_CLEAN_DIR / name) for name in CLEAN_TABLE_FILES}

    validate_cohort_registry(committed_reg, committed_tables, committed_clean)

    assert committed_reg["schema_version"] == 1
    assert committed_reg["dataset_id"] == "showcase-v3"
    assert committed_reg["seed"] is None

    # counts equal the table heights.
    assert committed_reg["counts"] == {name: df.height for name, df in committed_tables.items()}
    assert committed_reg["clean_counts"] == {
        name: df.height for name, df in committed_clean.items()
    }

    # tables_digest and clean_tables_digest equal fresh digests of the committed tables.
    assert committed_reg["tables_digest"] == tables_digest(committed_tables)
    assert committed_reg["clean_tables_digest"] == clean_tables_digest(committed_clean)

    # every role resolves to an existing claim and patient.
    headers_df = committed_tables["claim_headers.parquet"]
    claim_to_patient = dict(
        zip(
            headers_df["claim_id"].to_list(),
            headers_df["patient_id"].to_list(),
            strict=True,
        )
    )
    roles = committed_reg["roles"]
    # the roles are the landing patient and the first eight stories; later stories are scenarios
    assert set(roles) == {"default_landing", *(f"showcase_S{n}" for n in range(1, 9))}
    assert committed_reg["scenarios"] == _COMMITTED_SCENARIOS
    assert roles["default_landing"] == {
        "patient_id": "SENTETIK-HASTA-0001",
        "claim_id": "F-SENTETIK-HASTA-0001-001",
    }
    for role_name, target in roles.items():
        cid = target["claim_id"]
        pid = target["patient_id"]
        assert cid in claim_to_patient, role_name
        assert claim_to_patient[cid] == pid, role_name

    # answer rows equal build_expected_rule_outputs of the records.
    records = [FaultInjectionRecord.model_validate(item) for item in committed_reg["faults"]]
    assert tuple(records) == built_showcase.records
    expected_answer_rows = build_expected_rule_outputs(records)
    assert tuple(expected_answer_rows) == built_showcase.answer_rows

    rebuilt_expected_df = build_tables(
        (),
        answer_rows=expected_answer_rows,
        copay_profiles=(),
    )["expected_rule_outputs.parquet"]
    assert committed_tables["expected_rule_outputs.parquet"].equals(
        rebuilt_expected_df, null_equal=True
    )


# --- 7. Hygiene on the committed files ---------------------------------------------------------


def _collect_json_keys(node: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            keys.add(str(k))
            keys.update(_collect_json_keys(v))
    elif isinstance(node, list):
        for item in node:
            keys.update(_collect_json_keys(item))
    return keys


def test_hygiene_and_id_formats_on_committed_files() -> None:
    # 1. Text hygiene on showcase_recipes.yaml, cohort_registry.json, and README.md.
    recipes_text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes_raw = json.loads(json.dumps(load_recipes().model_dump()))
    assert hygiene(recipes_raw, recipes_text) == []

    for text_path in (RECIPES_PATH, _REGISTRY_JSON_PATH, _OUT_DIR / "README.md"):
        content = text_path.read_text(encoding="utf-8")
        assert not _ANON_RE.search(content), f"ANON text found in {text_path}"
        assert not _CURRENCY_RE.search(content), f"Currency text found in {text_path}"

    # 2. No `package_candidate` key in any JSON file.
    reg_data = json.loads(_REGISTRY_JSON_PATH.read_text(encoding="utf-8"))
    all_json_keys = _collect_json_keys(reg_data)
    assert "package_candidate" not in {k.lower() for k in all_json_keys}

    # 3. No ANON_ or currency text in any string column of the 9 Parquet tables, and all IDs match ids.py.
    tables = {name: pl.read_parquet(_CLAIMS_DIR / name) for name in TABLE_FILES}
    for name, df in tables.items():
        for col, dtype in df.schema.items():
            if dtype == pl.String:
                for val in df[col].drop_nulls().to_list():
                    assert not _ANON_RE.search(val), f"ANON text in {name}.{col}: {val!r}"
                    assert not _CURRENCY_RE.search(val), f"Currency text in {name}.{col}: {val!r}"

    hdr = tables["claim_headers.parquet"]
    assert all(PATIENT_ID_RE.fullmatch(v) for v in hdr["patient_id"].to_list())
    assert all(CLAIM_ID_RE.fullmatch(v) for v in hdr["claim_id"].to_list())
    assert all(EPISODE_ID_RE.fullmatch(v) for v in hdr["episode_id"].to_list())

    dx = tables["claim_diagnoses.parquet"]
    assert all(DIAGNOSIS_ID_RE.fullmatch(v) for v in dx["diagnosis_id"].to_list())
    assert all(CLAIM_ID_RE.fullmatch(v) for v in dx["claim_id"].to_list())
    assert all(PATIENT_ID_RE.fullmatch(v) for v in dx["patient_id"].to_list())
    assert all(EPISODE_ID_RE.fullmatch(v) for v in dx["episode_id"].to_list())

    proc = tables["procedure_claim_lines.parquet"]
    assert all(PROCEDURE_LINE_ID_RE.fullmatch(v) for v in proc["procedure_line_id"].to_list())
    assert all(CLAIM_ID_RE.fullmatch(v) for v in proc["claim_id"].to_list())
    assert all(PATIENT_ID_RE.fullmatch(v) for v in proc["patient_id"].to_list())
    assert all(EPISODE_ID_RE.fullmatch(v) for v in proc["episode_id"].to_list())

    mat = tables["material_claim_lines.parquet"]
    assert all(MATERIAL_LINE_ID_RE.fullmatch(v) for v in mat["material_line_id"].to_list())
    assert all(PROCEDURE_LINE_ID_RE.fullmatch(v) for v in mat["procedure_line_id"].to_list())
    assert all(CLAIM_ID_RE.fullmatch(v) for v in mat["claim_id"].to_list())
    assert all(PATIENT_ID_RE.fullmatch(v) for v in mat["patient_id"].to_list())

    drg = tables["drug_claim_lines.parquet"]
    assert all(DRUG_CLAIM_LINE_ID_RE.fullmatch(v) for v in drg["drug_claim_line_id"].to_list())
    assert all(PRESCRIPTION_ID_RE.fullmatch(v) for v in drg["prescription_id"].to_list())
    assert all(CLAIM_ID_RE.fullmatch(v) for v in drg["claim_id"].to_list())
    assert all(PATIENT_ID_RE.fullmatch(v) for v in drg["patient_id"].to_list())
    assert all(EPISODE_ID_RE.fullmatch(v) for v in drg["episode_id"].to_list())

    perf = tables["performed_procedure_lines.parquet"]
    assert all(PERFORMED_LINE_ID_RE.fullmatch(v) for v in perf["performed_line_id"].to_list())
    assert all(CLAIM_ID_RE.fullmatch(v) for v in perf["claim_id"].to_list())
    assert all(PATIENT_ID_RE.fullmatch(v) for v in perf["patient_id"].to_list())
    assert all(EPISODE_ID_RE.fullmatch(v) for v in perf["episode_id"].to_list())

    copay = tables["patient_copay_profiles.parquet"]
    assert all(PATIENT_ID_RE.fullmatch(v) for v in copay["patient_id"].to_list())

    out = tables["expected_rule_outputs.parquet"]
    assert all(CLAIM_ID_RE.fullmatch(v) for v in out["claim_id"].to_list())
    assert all(PATIENT_ID_RE.fullmatch(v) for v in out["patient_id"].to_list())
    for enc in reg_data["encounters"]:
        assert PATIENT_ID_RE.fullmatch(enc["patient_id"])
        assert CLAIM_ID_RE.fullmatch(enc["claim_id"])
    for rec in reg_data["faults"]:
        assert PATIENT_ID_RE.fullmatch(rec["patient_id"])
        assert CLAIM_ID_RE.fullmatch(rec["claim_id"])
        for lid in rec["line_ids"]:
            assert (
                PERFORMED_LINE_ID_RE.fullmatch(lid)
                or PROCEDURE_LINE_ID_RE.fullmatch(lid)
                or MATERIAL_LINE_ID_RE.fullmatch(lid)
                or DRUG_CLAIM_LINE_ID_RE.fullmatch(lid)
            )


# --- 8. In-memory defect detection proofs ------------------------------------------------------


def test_in_memory_defects_are_caught(built_showcase: BuildResult) -> None:
    # (a) A record with the wrong amount:
    # 1) On a revenue_uplift fault (S1), make_record / FaultInjectionRecord rejects wrong arithmetic.
    s1_fault = next(f for f in load_registry().faults if f.story == "S1")
    with pytest.raises(ValidationError, match="revenue_uplift amount_try"):
        make_record(
            s1_fault,
            patient_id="SENTETIK-HASTA-0001",
            claim_id="F-SENTETIK-HASTA-0001-001",
            line_id="",
            amount_try="9999.99",
            billed_clean_try="8636.51",
            billed_faulty_try="4514.45",
        )

    # 2) On a deduction_risk or compliance_error fault in registry["faults"], validate_cohort_registry
    # catches any tampered amount_try (both against the line/claim totals and expected_rule_outputs).
    bad_amount_reg = copy.deepcopy(built_showcase.registry)
    s5_entry = next(f for f in bad_amount_reg["faults"] if f["story"] == "S5")
    s5_entry["amount_try"] = "100.00"
    with pytest.raises(BuildError, match="deduction_risk amount_try 100.00"):
        validate_cohort_registry(bad_amount_reg, built_showcase.tables)

    bad_compliance_reg = copy.deepcopy(built_showcase.registry)
    s6_entry = next(f for f in bad_compliance_reg["faults"] if f["story"] == "S6")
    s6_entry["amount_try"] = "50.00"
    with pytest.raises(BuildError, match="compliance_error amount_try must be 0.00"):
        validate_cohort_registry(bad_compliance_reg, built_showcase.tables)

    # (b) A roles entry that points to a missing claim (or mismatched patient):
    bad_role_reg = copy.deepcopy(built_showcase.registry)
    bad_role_reg["roles"]["showcase_S3"] = {
        "patient_id": "SENTETIK-HASTA-0003",
        "claim_id": "F-SENTETIK-HASTA-9999-001",
    }
    with pytest.raises(
        BuildError,
        match="role 'showcase_S3' references missing claim_id 'F-SENTETIK-HASTA-9999-001'",
    ):
        validate_cohort_registry(bad_role_reg, built_showcase.tables)

    bad_role_patient_reg = copy.deepcopy(built_showcase.registry)
    bad_role_patient_reg["roles"]["default_landing"] = {
        "patient_id": "SENTETIK-HASTA-0002",
        "claim_id": "F-SENTETIK-HASTA-0001-001",
    }
    with pytest.raises(BuildError, match="role 'default_landing' patient_id"):
        validate_cohort_registry(bad_role_patient_reg, built_showcase.tables)

    # (c) A changed table value (digest):
    proc_df = built_showcase.tables["procedure_claim_lines.parquet"]
    first_proc_id = proc_df["procedure_line_id"][0]
    first_proc_val = proc_df["billed_amount_try"][0]
    mutated_proc_df = proc_df.with_columns(
        pl.when(pl.col("procedure_line_id") == first_proc_id)
        .then(
            pl.lit(
                round(
                    first_proc_val + Decimal("0.01")
                    if isinstance(first_proc_val, Decimal)
                    else first_proc_val + 0.01,
                    2,
                ),
                dtype=pl.Float64,
            )
        )
        .otherwise(pl.col("billed_amount_try"))
        .alias("billed_amount_try")
    )
    mutated_tables = {
        **built_showcase.tables,
        "procedure_claim_lines.parquet": mutated_proc_df,
    }
    assert tables_digest(mutated_tables) != built_showcase.registry["tables_digest"]
    with pytest.raises(
        BuildError,
        match=r"tables_digest mismatch on: \['procedure_claim_lines\.parquet'\]",
    ):
        validate_cohort_registry(built_showcase.registry, mutated_tables)

    # (d) A recipe whose fault belongs to another pathway:
    base_recipes = load_recipes()
    mismatched_recipes = ShowcaseRecipes(
        schema_version=1,
        recipes=[
            ShowcaseRecipe(
                patient_no=1,
                pathway="copd_exacerbation_pneumonia_ward",
                fault="F_S1_PACKAGE_BILLED_ITEMIZED",
            ),
            *base_recipes.recipes[1:],
        ],
    )
    # (every pathway is in use, so the story of patient 2 is now on two bills as well)
    problems = check_recipes(mismatched_recipes)
    assert [p.check for p in problems] == ["recipe.fault_pathway", "recipe.story"]
    with pytest.raises(RecipeLoadError) as exc_info:
        build_showcase(recipes=mismatched_recipes)
    assert [p.check for p in exc_info.value.problems] == ["recipe.fault_pathway", "recipe.story"]

    # Also caught directly by apply_fault if called with mismatched pathway.
    pathways = load_all()
    with pytest.raises(FaultApplyError, match="target_pathway"):
        apply_fault(s1_fault, pathways["copd_exacerbation_pneumonia_ward"])

    # (e) A dangling evidence line_id in a record's line_ids:
    bad_ev_reg = copy.deepcopy(built_showcase.registry)
    s7_entry = next(f for f in bad_ev_reg["faults"] if f["story"] == "S7")
    s7_entry["line_ids"] = ["EMR-F-SENTETIK-HASTA-0007-001-999"]
    with pytest.raises(
        BuildError,
        match="evidence line_id 'EMR-F-SENTETIK-HASTA-0007-001-999' does not exist in performed_procedure_lines.parquet",
    ):
        validate_cohort_registry(bad_ev_reg, built_showcase.tables)


# --- scenarios: the stories after the eighth ----------------------------------------------------


def test_stories_after_the_eighth_are_scenarios_and_not_roles(built_showcase: BuildResult) -> None:
    registry = built_showcase.registry
    assert set(registry["roles"]) == {"default_landing", *(f"showcase_S{n}" for n in range(1, 9))}
    assert registry["scenarios"] == _COMMITTED_SCENARIOS
    assert next(rec for rec in built_showcase.records if rec.story == "S9").claim_id == (
        "F-SENTETIK-HASTA-0009-001"
    )
    encounter = next(e for e in registry["encounters"] if e["story"] == "S9")
    assert encounter["patient_id"] == "SENTETIK-HASTA-0009" and encounter["is_clean"] is False


# --- S14, the second bill of patient 10: the ward bill after the ICU bill ----------------------------------------

_ICU_CLAIM = "F-SENTETIK-HASTA-0010-001"
_WARD_CLAIM = "F-SENTETIK-HASTA-0010-002"
_WARD_PATIENT = "SENTETIK-HASTA-0010"


def test_the_ward_bill_of_patient_10_starts_on_the_day_the_icu_bill_ends(built_showcase: BuildResult) -> None:
    headers = built_showcase.tables["claim_headers.parquet"]
    icu = headers.filter(pl.col("claim_id") == _ICU_CLAIM).row(0, named=True)
    ward = headers.filter(pl.col("claim_id") == _WARD_CLAIM).row(0, named=True)
    assert (icu["admission_date"], icu["discharge_date"]) == ("2026-06-02", "2026-06-07")
    assert (ward["admission_date"], ward["discharge_date"]) == ("2026-06-07", "2026-06-10")
    assert icu["discharge_date"] == ward["admission_date"]  # the transfer day: the last day of one bill, the first of the next
    assert icu["patient_id"] == ward["patient_id"] == _WARD_PATIENT
    assert (ward["episode_id"], ward["claim_type"], ward["department"]) == (
        "B-SENTETIK-HASTA-0010-002", "yatis", "İç Hastalıkları",
    )  # fmt: skip
    ids = headers["claim_id"].to_list()
    assert ids.index(_WARD_CLAIM) == ids.index(_ICU_CLAIM) + 1  # the tables follow the dates inside the patient
    assert cohort.scenario("S14").claim_ids == (_WARD_CLAIM,) and cohort.scenario("S11").claim_ids == (_ICU_CLAIM,)


def test_the_faulty_ward_bill_bills_the_bed_on_the_transfer_day_and_the_clean_twin_does_not(
    built_showcase: BuildResult,
) -> None:
    lines = built_showcase.tables["procedure_claim_lines.parquet"].filter(pl.col("claim_id") == _WARD_CLAIM)
    days = lambda frame, code: sorted(frame.filter(pl.col("procedure_code") == code)["procedure_date"])  # noqa: E731
    assert days(lines, "510010") == ["2026-06-07", "2026-06-08", "2026-06-09", "2026-06-10"]
    assert days(lines, "510121") == ["2026-06-07", "2026-06-08", "2026-06-09"]  # one companion line per night
    assert lines.height == 7
    clean = next(c for c in built_showcase.clean_claims if c.header.claim_id == _WARD_CLAIM)
    assert sorted(p.procedure_date.isoformat() for p in clean.procedures if p.procedure_code == "510010") == [
        "2026-06-08", "2026-06-09", "2026-06-10",
    ]  # fmt: skip
    assert len(clean.procedures) == 6
    # the faulty bill is the clean one plus the transfer-day bed, and nothing else
    faulty = built_showcase.claims[_claim_index(built_showcase, _WARD_CLAIM)]
    identity = lambda claim: sorted((p.procedure_code, p.procedure_date.isoformat(), p.quantity) for p in claim.procedures)  # noqa: E731
    assert [x for x in identity(faulty) if x not in identity(clean)] == [("510010", "2026-06-07", 1)]
    assert [x for x in identity(clean) if x not in identity(faulty)] == []
    for name in ("drug_claim_lines.parquet", "material_claim_lines.parquet", "performed_procedure_lines.parquet"):
        assert built_showcase.tables[name].filter(pl.col("claim_id") == _WARD_CLAIM).is_empty(), name
    assert built_showcase.clean_tables["lab_clean.parquet"].filter(pl.col("basvuru_id") == _WARD_CLAIM.replace("F-", "B-", 1)).is_empty()


def _claim_index(built: BuildResult, claim_id: str) -> int:
    return [c.header.claim_id for c in built.claims].index(claim_id)


def test_the_fault_record_of_the_ward_bill_is_the_one_bed_line(built_showcase: BuildResult) -> None:
    record = next(r for r in built_showcase.records if r.claim_id == _WARD_CLAIM)
    assert (record.story, record.line_id, record.effect_kind, record.expected_status) == ("S14", "", "deduction_risk", "kismi_red")
    assert record.engine_rule == "yatak_icu_overlap_510010"
    assert record.amount_try == "222.36"
    assert Decimal(record.billed_faulty_try) - Decimal(record.billed_clean_try) == Decimal(record.amount_try)  # the bed line
    clean = next(c for c in built_showcase.clean_claims if c.header.claim_id == _WARD_CLAIM)
    assert f"{clean.header.expected_total_billed_try:.2f}" == record.billed_clean_try
    # one record per bill: the ICU bill keeps its own
    assert {r.claim_id: r.story for r in built_showcase.records if r.patient_id == _WARD_PATIENT} == {_ICU_CLAIM: "S11", _WARD_CLAIM: "S14"}


def test_the_ward_bill_has_its_own_anadata_row_and_the_patient_keeps_one_profile(built_showcase: BuildResult) -> None:
    anadata = built_showcase.clean_tables["anadata_clean.parquet"].filter(pl.col("HASTA_ID") == _WARD_PATIENT)
    assert anadata["SQ_EPISODE"].to_list() == ["B-SENTETIK-HASTA-0010-001", "B-SENTETIK-HASTA-0010-002"]
    assert (anadata["TANI_YASI"].to_list(), anadata["CINSIYET"].to_list()) == ([76, 76], ["K", "K"])
    assert anadata["EPISODE_TARIH"].dt.date().to_list() == [date(2026, 6, 2), date(2026, 6, 7)]
    profiles = built_showcase.tables["patient_copay_profiles.parquet"]
    assert profiles.filter(pl.col("patient_id") == _WARD_PATIENT).height == 1  # one profile for the two bills
    assert profiles.height == cohort.patient_count() == 15
    assert built_showcase.tables["claim_headers.parquet"].height == cohort.claim_count() == 28
    registry = built_showcase.registry
    assert registry["counts"]["patient_copay_profiles.parquet"] == cohort.patient_count()
    assert registry["clean_counts"]["anadata_clean.parquet"] == cohort.claim_count()  # one anadata row a bill, not a patient
    encounter = next(e for e in registry["encounters"] if e["claim_id"] == _WARD_CLAIM)
    assert (encounter["story"], encounter["is_clean"], encounter["pathway_id"]) == ("S14", False, "urosepsis_ward_stay_after_icu_transfer")
    assert "pins" not in encounter  # the pathway pins the patient's identity itself (F, 76 as S11): no override needed


def test_the_ward_bill_leaves_every_other_bill_of_the_cohort_as_it_was(built_showcase: BuildResult) -> None:
    """The tables list the new bill's rows only in the tables that have rows per bill; the other rows are S1-S12's."""
    tables = built_showcase.tables
    per_claim = {name: frame.filter(pl.col("claim_id") == _WARD_CLAIM).height for name, frame in tables.items() if "claim_id" in frame.columns}
    assert per_claim["claim_headers.parquet"] == 1
    assert per_claim["procedure_claim_lines.parquet"] == 7 and per_claim["claim_diagnoses.parquet"] == 2
    assert per_claim["expected_rule_outputs.parquet"] == 1
    assert {name for name, n in per_claim.items() if n} == {
        "claim_headers.parquet", "procedure_claim_lines.parquet", "claim_diagnoses.parquet", "expected_rule_outputs.parquet",
    }  # fmt: skip
    diagnoses = tables["claim_diagnoses.parquet"].filter(pl.col("claim_id") == _WARD_CLAIM)
    assert sorted(diagnoses["icd10_code"]) == ["A41.9", "N39.0"]  # both are on the patient's ICU bill already: the union list stays
    icu = tables["claim_diagnoses.parquet"].filter(pl.col("claim_id") == _ICU_CLAIM)
    assert set(diagnoses["icd10_code"]) <= set(icu["icd10_code"])


def test_the_faulty_s12_bill_lacks_its_first_three_incubator_days_and_ends_on_an_incubator_day(
    built_showcase: BuildResult,
) -> None:
    """The fault sits on the first days: a later ward bill that starts on the discharge day finds a Kuvöz line there."""
    claim = cohort.scenario("S12").claim_ids[0]
    lines = built_showcase.tables["procedure_claim_lines.parquet"].filter(pl.col("claim_id") == claim)
    incubator = lines.filter(pl.col("procedure_code") == "510070")["procedure_date"].sort().to_list()
    assert incubator == ["2026-07-13", "2026-07-14", "2026-07-15"]
    header = built_showcase.tables["claim_headers.parquet"].filter(pl.col("claim_id") == claim)
    assert header["discharge_date"].to_list() == ["2026-07-15"]  # the last day carries an incubator line
    clean = next(c for c in built_showcase.clean_claims if c.header.claim_id == claim)
    clean_days = sorted(p.procedure_date.isoformat() for p in clean.procedures if p.procedure_code == "510070")
    assert clean_days == [f"2026-07-{day}" for day in range(10, 16)]


def test_a_recipe_without_a_fault_builds_the_clean_claim_with_no_record(
    built_showcase: BuildResult,
) -> None:
    base = load_recipes()
    second = next(r for r in base.recipes if (r.patient_no, r.encounter_no) == (2, 1))
    clean_second = ShowcaseRecipe(patient_no=2, pathway=second.pathway)
    recipes = ShowcaseRecipes(
        schema_version=1, recipes=[clean_second if r is second else r for r in base.recipes]
    )
    built = build_showcase(recipes=recipes)

    faults = len(cohort.load_registry()["faults"])
    assert len(built.claims) == cohort.claim_count()
    assert len(built.records) == faults - 1 and len(built.answer_rows) == faults - 1
    assert "S2" not in {rec.story for rec in built.records}
    claim = "F-SENTETIK-HASTA-0002-001"
    built_by_id = {c.header.claim_id: c for c in built.claims}
    committed_faulty = {c.header.claim_id: c for c in built_showcase.claims}
    committed_clean = {c.header.claim_id: c for c in built_showcase.clean_claims}
    assert built_by_id[claim] == committed_clean[claim]  # the bill is the clean twin
    assert {cid: c for cid, c in built_by_id.items() if cid != claim} == {
        cid: c for cid, c in committed_faulty.items() if cid != claim
    }  # every other bill is as it was
    encounter = next(e for e in built.registry["encounters"] if e["claim_id"] == claim)
    assert (encounter["is_clean"], encounter["fault_id"]) == (True, None)
    assert built.registry["roles"]["showcase_S2"]["claim_id"] == "F-SENTETIK-HASTA-0002-001"
    assert built.tables["expected_rule_outputs.parquet"].height == faults - 1
    validate_cohort_registry(built.registry, built.tables, built.clean_tables)


def test_the_landing_claim_is_the_s1_bill_or_else_the_first_bill() -> None:
    from scripts.synthetic.cohort.build import _default_landing

    first = {"patient_id": "SENTETIK-HASTA-0001", "claim_id": "F-SENTETIK-HASTA-0001-001"}
    s1 = {"patient_id": "SENTETIK-HASTA-0003", "claim_id": "F-SENTETIK-HASTA-0003-001"}
    assert _default_landing({"showcase_S2": first, "showcase_S1": s1}, first) == s1  # S1 need not be the first bill
    assert _default_landing({"showcase_S2": first}, first) == first  # a cohort without S1 lands on its first bill
    landing = _default_landing({"showcase_S1": s1}, first)
    landing["claim_id"] = "changed"
    assert s1["claim_id"] == "F-SENTETIK-HASTA-0003-001"  # a copy: the role itself is not shared with the landing


def test_the_story_of_a_clean_recipe_is_the_story_of_its_pathway() -> None:
    base = load_recipes()
    ninth = next(r for r in base.recipes if (r.patient_no, r.encounter_no) == (9, 1))
    clean_ninth = ShowcaseRecipe(patient_no=9, pathway=ninth.pathway)
    recipes = ShowcaseRecipes(
        schema_version=1, recipes=[clean_ninth if r is ninth else r for r in base.recipes]
    )
    built = build_showcase(recipes=recipes)
    assert built.registry["scenarios"] == _COMMITTED_SCENARIOS
    assert len(built.records) == len(cohort.load_registry()["faults"]) - 1  # the S9 fault is gone


def _scenario_defects() -> list[tuple[str, Any, str]]:
    def drop_scenarios(registry: dict[str, Any]) -> None:
        del registry["scenarios"]

    def set_scenario(registry: dict[str, Any], story: str, value: Any) -> None:
        registry["scenarios"][story] = value

    ok = {"patient_id": "SENTETIK-HASTA-0009", "claim_ids": ["F-SENTETIK-HASTA-0009-001"]}
    return [
        ("no_scenarios_key", drop_scenarios, "scenarios must be a mapping"),
        (
            "scenarios_a_list",
            lambda r: r.update(scenarios=[ok]),
            "scenarios must be a mapping",
        ),
        (
            "scenario_named_like_a_role_story",
            lambda r: set_scenario(r, "S3", ok),
            "scenario 'S3' must be a story after S8",
        ),
        (
            "scenario_that_is_not_a_story",
            lambda r: set_scenario(r, "ninth", ok),
            "scenario 'ninth' must be a story after S8",
        ),
        (
            "scenario_with_an_extra_key",
            lambda r: set_scenario(r, "S9", {**ok, "title": "x"}),
            "scenario 'S9' must map to",
        ),
        (
            "scenario_with_the_role_shape",
            lambda r: set_scenario(
                r, "S9", {"patient_id": ok["patient_id"], "claim_id": ok["claim_ids"][0]}
            ),
            "scenario 'S9' must map to",
        ),
        (
            "scenario_without_claims",
            lambda r: set_scenario(r, "S9", {**ok, "claim_ids": []}),
            "scenario 'S9' claim_ids must be a non-empty list of distinct claim ids",
        ),
        (
            "scenario_with_a_claim_twice",
            lambda r: set_scenario(r, "S9", {**ok, "claim_ids": [ok["claim_ids"][0]] * 2}),
            "scenario 'S9' claim_ids must be a non-empty list of distinct claim ids",
        ),
        (
            "scenario_claim_ids_a_string",
            lambda r: set_scenario(r, "S9", {**ok, "claim_ids": ok["claim_ids"][0]}),
            "scenario 'S9' claim_ids must be a non-empty list of distinct claim ids",
        ),
        (
            "scenario_on_a_missing_claim",
            lambda r: set_scenario(
                r, "S9", {**ok, "claim_ids": ["F-SENTETIK-HASTA-9999-001"]}
            ),
            "scenario 'S9' references missing claim_id 'F-SENTETIK-HASTA-9999-001'",
        ),
        (
            "scenario_with_the_patient_of_another_claim",
            lambda r: set_scenario(r, "S9", {**ok, "patient_id": "SENTETIK-HASTA-0002"}),
            "scenario 'S9' patient_id 'SENTETIK-HASTA-0002' does not match claim",
        ),
        (
            "fault_of_a_scenario_story_off_its_scenario",
            lambda r: r["scenarios"].pop("S9"),
            "of story S9 is on claim F-SENTETIK-HASTA-0009-001, which no role or scenario names",
        ),
        (
            "fault_of_a_scenario_story_with_another_patient",
            lambda r: next(f for f in r["faults"] if f["story"] == "S9").update(
                patient_id=r["roles"]["showcase_S2"]["patient_id"]
            ),
            "of story S9 is on claim F-SENTETIK-HASTA-0009-001, which no role or scenario names",
        ),
        (
            "fault_of_a_role_story_off_its_role",
            lambda r: r["roles"].update(
                showcase_S3=dict(r["roles"]["showcase_S4"])
            ),
            "of story S3 is on claim F-SENTETIK-HASTA-0003-001, which no role or scenario names",
        ),
    ]


@pytest.mark.parametrize(
    ("change", "message"),
    [pytest.param(change, message, id=name) for name, change, message in _scenario_defects()],
)
def test_a_damaged_scenarios_section_is_refused(
    built_showcase: BuildResult, change: Any, message: str
) -> None:
    registry = copy.deepcopy(built_showcase.registry)
    change(registry)
    with pytest.raises(BuildError, match=re.escape(message)):
        validate_cohort_registry(registry, built_showcase.tables)


def test_the_undamaged_registry_has_no_scenario_defect(built_showcase: BuildResult) -> None:
    validate_cohort_registry(built_showcase.registry, built_showcase.tables)


def test_a_wrong_lab_count_in_the_registry_is_rejected(built_showcase: BuildResult) -> None:
    lab_name = "lab_clean.parquet"
    lab_rows = built_showcase.clean_tables[lab_name].height
    assert built_showcase.registry["clean_counts"][lab_name] == lab_rows

    # The count is the number of result rows the reference gives for the billed lab lines, so it
    # is checked with the clean tables and also without them (from the billed codes alone).
    validate_cohort_registry(built_showcase.registry, built_showcase.tables)
    validate_cohort_registry(
        built_showcase.registry, built_showcase.tables, built_showcase.clean_tables
    )
    for wrong in (0, lab_rows - 1, lab_rows + 1):
        bad_registry = copy.deepcopy(built_showcase.registry)
        bad_registry["clean_counts"][lab_name] = wrong
        with pytest.raises(BuildError, match=r"clean_counts mismatch"):
            validate_cohort_registry(bad_registry, built_showcase.tables)
        with pytest.raises(BuildError, match=r"clean_counts mismatch"):
            validate_cohort_registry(
                bad_registry, built_showcase.tables, built_showcase.clean_tables
            )

    # A lab table that lost a row no longer matches the registry's count (nor its digest).
    short_lab = built_showcase.clean_tables[lab_name].head(221)
    short_clean = {**built_showcase.clean_tables, lab_name: short_lab}
    with pytest.raises(BuildError, match=r"clean_counts mismatch"):
        validate_cohort_registry(built_showcase.registry, built_showcase.tables, short_clean)


def test_the_registry_check_validates_the_clean_tables_against_the_claims(
    built_showcase: BuildResult,
) -> None:
    """A coherent lab table that no billed line asks for is refused by the registry check itself.

    `clean_tables_digest` validates without the claims, so a digest alone would not notice: the check
    that sees it is `validate_clean_tables(clean, claims)`, which `validate_cohort_registry` runs. Patient
    1's CRP result set is moved one day: the row count and the schema are unchanged.
    """
    lab_name = "lab_clean.parquet"
    lab = built_showcase.clean_tables[lab_name]
    crp = lab.with_row_index("i").filter(
        (pl.col("HASTA_ID") == "SENTETIK-HASTA-0001") & (pl.col("SUB_CODE") == "L101850")
    )["i"][0]
    moved = lab.with_columns(
        pl.when(pl.int_range(pl.len()) == crp)
        .then(pl.col("tarih").dt.offset_by("1d"))
        .otherwise(pl.col("tarih"))
        .alias("tarih")
    )
    assert moved.height == lab.height and not moved.equals(lab)
    tampered = {**built_showcase.clean_tables, lab_name: moved}
    assert (
        clean_tables_digest(tampered)[lab_name]
        != built_showcase.registry["clean_tables_digest"][lab_name]
    )  # the digest alone would notice a change, but not say what is wrong
    with pytest.raises(
        BuildError, match=r"lab_clean\.parquet rows do not match the billed lab lines"
    ):
        validate_cohort_registry(built_showcase.registry, built_showcase.tables, tampered)


def test_target_and_evidence_line_resolution_guards(built_showcase: BuildResult) -> None:
    from dataclasses import replace
    from scripts.synthetic.cohort.build import _resolve_evidence_line_ids, _resolve_target_line_id

    faults_by_story = {f.story: f for f in load_registry().faults if f.story is not None}

    # If a line-level fault's target_entry_id resolves to 0 or >1 lines, _resolve_target_line_id raises BuildError.
    s5_fault = faults_by_story["S5"]
    claims_by_id = {c.header.claim_id: c for c in built_showcase.claims}
    s5_claim = claims_by_id[cohort.role("showcase_S5").claim_id]
    zero_lines_claim = replace(s5_claim, entry_line_ids={})
    with pytest.raises(BuildError, match="resolved to 0 lines"):
        _resolve_target_line_id(s5_fault, zero_lines_claim)

    two_lines_claim = replace(
        s5_claim,
        entry_line_ids={
            **s5_claim.entry_line_ids,
            "femoral_stem": (
                "MLZ-F-SENTETIK-HASTA-0005-001-002",
                "MLZ-F-SENTETIK-HASTA-0005-001-003",
            ),
        },
    )
    with pytest.raises(BuildError, match="resolved to 2 lines"):
        _resolve_target_line_id(s5_fault, two_lines_claim)

    # If an evidence_entry_id resolves to 0 lines, _resolve_evidence_line_ids raises BuildError.
    s7_fault = faults_by_story["S7"]
    s7_claim = claims_by_id[cohort.role("showcase_S7").claim_id]
    no_ev_claim = replace(s7_claim, entry_line_ids={})
    with pytest.raises(
        BuildError, match="evidence_entry_id 'ct_angiography_pacs' resolved to 0 lines"
    ):
        _resolve_evidence_line_ids(s7_fault, no_ev_claim)


# --- several encounters of one patient (G2) ------------------------------------------------------------
#
# These tests build in memory the committed recipes plus `STANDARD_EXTRAS`: patient 4 gets a fourth bill, a stay
# one day after its first (the lab days interleave; it is dated before the committed second and third bill, S39
# and S40), patient 7 a visit nine days BEFORE its first (a precursor: claim 002 is dated before claim 001).
# Nothing is committed from the extras.

_EXTRA_CLAIMS = ("F-SENTETIK-HASTA-0004-004", "F-SENTETIK-HASTA-0007-004")
_EXTRA_EPISODES = ("B-SENTETIK-HASTA-0004-004", "B-SENTETIK-HASTA-0007-004")
_EPISODE_COLUMN = {
    "anadata_clean.parquet": "SQ_EPISODE",
    "lab_clean.parquet": "basvuru_id",
    "recete_clean.parquet": "RF_EPISODE",
}


@pytest.fixture(scope="module")
def two_bills() -> BuildResult:
    recipes, clinical = with_encounters(*STANDARD_EXTRAS)
    return build_showcase(recipes=recipes, clinical=clinical)


def test_the_ids_follow_the_encounter_number_and_the_tables_follow_the_dates(two_bills: BuildResult) -> None:
    headers = two_bills.tables["claim_headers.parquet"]
    assert headers["claim_id"].to_list() == [
        "F-SENTETIK-HASTA-0001-001",
        "F-SENTETIK-HASTA-0002-001",
        "F-SENTETIK-HASTA-0002-002",  # the committed control of patient 2 (S32), three weeks after the stay
        "F-SENTETIK-HASTA-0002-003",  # its readmission through the ER (S33) and the control after it (S34)
        "F-SENTETIK-HASTA-0002-004",
        "F-SENTETIK-HASTA-0003-001",
        "F-SENTETIK-HASTA-0004-001",
        "F-SENTETIK-HASTA-0004-004",  # the extra stay: the last id, the date next to the first stay's
        "F-SENTETIK-HASTA-0004-002",  # the committed control (S39) and second visit (S40), dated later
        "F-SENTETIK-HASTA-0004-003",
        "F-SENTETIK-HASTA-0005-001",
        "F-SENTETIK-HASTA-0006-001",
        "F-SENTETIK-HASTA-0006-002",  # the committed neurology control (S45) and physiatry visit (S46) of patient 6
        "F-SENTETIK-HASTA-0006-003",
        "F-SENTETIK-HASTA-0007-004",  # the precursor: the later id, the earlier date
        "F-SENTETIK-HASTA-0007-001",
        "F-SENTETIK-HASTA-0007-002",  # the committed observation (S47) and follow-up (S48) of patient 7, dated later
        "F-SENTETIK-HASTA-0007-003",
        *(f"F-SENTETIK-HASTA-{n:04d}-001" for n in (8, 9, 10)),
        "F-SENTETIK-HASTA-0010-002",  # the committed second bill (S14, the ward bill after the ICU bill), dated later
        "F-SENTETIK-HASTA-0011-001",
        "F-SENTETIK-HASTA-0012-001",  # the ER visit of patient 12 (S10) and the admission two days later (S22)
        "F-SENTETIK-HASTA-0012-002",
        "F-SENTETIK-HASTA-0013-001",  # the day case of patient 13 (S20)
        "F-SENTETIK-HASTA-0014-001",  # the month of haemodialysis of patient 14 (S17) and its emergency session (S23)
        "F-SENTETIK-HASTA-0014-002",
        "F-SENTETIK-HASTA-0015-001",  # the cirrhosis stay of patient 15 (S18) and its variceal rebleed (S24)
        "F-SENTETIK-HASTA-0015-002",
    ]
    assert headers["episode_id"].to_list() == [
        claim.replace("F-", "B-", 1) for claim in headers["claim_id"].to_list()
    ]
    starts = dict(zip(headers["claim_id"].to_list(), headers["claim_start_date"].to_list(), strict=True))
    assert starts["F-SENTETIK-HASTA-0004-001"] < starts["F-SENTETIK-HASTA-0004-004"] < starts["F-SENTETIK-HASTA-0004-002"]
    assert starts["F-SENTETIK-HASTA-0004-002"] < starts["F-SENTETIK-HASTA-0004-003"]
    assert starts["F-SENTETIK-HASTA-0007-004"] < starts["F-SENTETIK-HASTA-0007-001"]
    # the composed claims are in the table order; a claim is built from its own recipe
    assert [c.header.claim_id for c in two_bills.claims] == headers["claim_id"].to_list()
    assert [c.header.claim_id for c in two_bills.clean_claims] == headers["claim_id"].to_list()

    # the three clean tables list a patient's episodes together, in the order of the claims table
    anadata = two_bills.clean_tables["anadata_clean.parquet"]
    assert anadata["SQ_EPISODE"].to_list() == headers["episode_id"].to_list()
    assert anadata["HASTA_ID"].to_list() == headers["patient_id"].to_list()
    assert anadata["EPISODE_TARIH"].dt.date().to_list() == [
        date.fromisoformat(d) for d in headers["claim_start_date"].to_list()
    ]
    for name in ("lab_clean.parquet", "recete_clean.parquet"):
        patients = two_bills.clean_tables[name]["HASTA_ID"].to_list()
        runs = [p for i, p in enumerate(patients) if i == 0 or p != patients[i - 1]]
        assert runs == sorted(set(runs)), f"{name} lists a patient in two places"
    lab = two_bills.clean_tables["lab_clean.parquet"]
    for _, rows in lab.group_by("HASTA_ID", maintain_order=True):
        assert rows["tarih"].is_sorted(), "the lab rows of a patient are in date order"
    assert set(lab.filter(pl.col("HASTA_ID") == "SENTETIK-HASTA-0004")["basvuru_id"]) == {
        "B-SENTETIK-HASTA-0004-001",
        "B-SENTETIK-HASTA-0004-002",  # the control bills labs, the second visit (-003) none
        "B-SENTETIK-HASTA-0004-004",
    }


def test_a_second_bill_changes_no_row_of_any_other_bill(two_bills: BuildResult) -> None:
    """Every row that does not belong to a new bill is the committed row, in the committed order."""
    for name in TABLE_FILES:
        committed = pl.read_parquet(_CLAIMS_DIR / name)
        built = two_bills.tables[name]
        if "claim_id" in built.columns:
            built = built.filter(~pl.col("claim_id").is_in(_EXTRA_CLAIMS))
        assert dict(built.schema) == dict(committed.schema), name
        assert built.equals(committed, null_equal=True), name
    for name in CLEAN_TABLE_FILES:
        committed = pl.read_parquet(_CLEAN_DIR / name)
        built = two_bills.clean_tables[name]
        built = built.filter(~pl.col(_EPISODE_COLUMN[name]).is_in(_EXTRA_EPISODES))
        assert dict(built.schema) == dict(committed.schema), name
        assert built.equals(committed, null_equal=True), name
    # the new bills are really there: 2 claims, and their own rows in every table that has rows per bill
    assert two_bills.tables["claim_headers.parquet"].height == cohort.claim_count() + 2
    assert two_bills.registry["clean_counts"]["anadata_clean.parquet"] == cohort.claim_count() + 2
    for name in ("claim_diagnoses.parquet", "procedure_claim_lines.parquet", "drug_claim_lines.parquet"):
        assert two_bills.tables[name].filter(pl.col("claim_id").is_in(_EXTRA_CLAIMS)).height > 0, name


def test_a_patient_has_one_copay_profile_with_the_birth_year_of_the_first_encounter(
    two_bills: BuildResult, built_showcase: BuildResult
) -> None:
    assert two_bills.copay_profiles == built_showcase.copay_profiles  # 11 profiles, none added or changed
    by_patient = {p["patient_id"]: p["birth_year"] for p in two_bills.copay_profiles}
    assert (by_patient["SENTETIK-HASTA-0004"], by_patient["SENTETIK-HASTA-0007"]) == (2026 - 86, 2026 - 58)
    assert two_bills.tables["patient_copay_profiles.parquet"].height == cohort.patient_count()
    # the bills agree with the profile: age at the bill = year of the bill - birth year (the tables' own check)
    anadata = two_bills.clean_tables["anadata_clean.parquet"]
    for patient, age, year in zip(
        anadata["HASTA_ID"].to_list(),
        anadata["TANI_YASI"].to_list(),
        anadata["EPISODE_TARIH"].dt.year().to_list(),
        strict=True,
    ):
        assert year - by_patient[patient] == age, patient


def test_roles_and_scenarios_of_a_patient_with_two_bills(two_bills: BuildResult, built_showcase: BuildResult) -> None:
    registry = two_bills.registry
    assert registry["roles"] == built_showcase.registry["roles"]  # the second bills take no role over
    assert registry["roles"]["showcase_S4"]["claim_id"] == "F-SENTETIK-HASTA-0004-001"
    assert registry["roles"]["showcase_S7"]["claim_id"] == "F-SENTETIK-HASTA-0007-001"  # not the earlier bill
    assert registry["roles"]["default_landing"] == registry["roles"]["showcase_S1"]
    assert registry["scenarios"] == {
        "S90": {"patient_id": "SENTETIK-HASTA-0004", "claim_ids": ["F-SENTETIK-HASTA-0004-004"]},
        "S91": {"patient_id": "SENTETIK-HASTA-0007", "claim_ids": ["F-SENTETIK-HASTA-0007-004"]},
        **built_showcase.registry["scenarios"],
    }
    encounters = {e["claim_id"]: e for e in registry["encounters"]}
    assert len(registry["encounters"]) == cohort.claim_count() + 2 == len(encounters)
    assert [e["claim_id"] for e in registry["encounters"] if e["claim_id"] in _EXTRA_CLAIMS] == list(_EXTRA_CLAIMS)
    second = encounters["F-SENTETIK-HASTA-0004-004"]
    assert (second["story"], second["is_clean"], second["fault_id"]) == ("S90", True, None)
    assert second["pins"] == {"story": "S90", "admit": "2026-05-12"}  # only what the recipe overrides
    assert [e["claim_id"] for e in registry["encounters"] if "pins" in e] == list(_EXTRA_CLAIMS)
    # the bills of a patient are found by grouping the encounters (and the scenarios) by patient
    assert {s: t["patient_id"] for s, t in registry["scenarios"].items() if t["patient_id"] == "SENTETIK-HASTA-0007"} == {
        "S47": "SENTETIK-HASTA-0007",  # the committed observation and follow-up
        "S48": "SENTETIK-HASTA-0007",
        "S91": "SENTETIK-HASTA-0007",  # the test-only precursor
    }
    # a clean second bill adds no fault record and no answer row
    assert registry["faults"] == built_showcase.registry["faults"]
    assert two_bills.records == built_showcase.records
    assert two_bills.answer_rows == built_showcase.answer_rows
    assert two_bills.tables["expected_rule_outputs.parquet"].height == len(built_showcase.records)
    for claim in (c for c in two_bills.claims if c.header.claim_id in _EXTRA_CLAIMS):
        clean = next(c for c in two_bills.clean_claims if c.header.claim_id == claim.header.claim_id)
        assert claim == clean  # a bill without a fault is its own clean twin


def test_the_effective_pins_travel_on_every_composed_claim(two_bills: BuildResult, built_showcase: BuildResult) -> None:
    pathways = load_all()
    recipes = load_recipes()
    for claim, recipe in zip(built_showcase.claims, recipes.recipes, strict=True):
        assert claim.pins == pathways[recipe.pathway].showcase  # a recipe without pins: the pathway's own
    for claim in two_bills.claims:
        encounter = next(e for e in two_bills.registry["encounters"] if e["claim_id"] == claim.header.claim_id)
        pathway = pathways[encounter["pathway_id"]]
        overrides = encounter.get("pins", {})
        assert claim.pins == pathway.showcase.model_copy(update=overrides)
    second = next(c for c in two_bills.claims if c.header.claim_id == "F-SENTETIK-HASTA-0004-004")
    assert (second.pins.story, second.pins.admit) == ("S90", "2026-05-12")
    assert second.header.admission_date == date(2026, 5, 12) and second.pins.nights == 5


def test_a_two_bill_dataset_is_deterministic_written_checked_and_loaded(
    two_bills: BuildResult, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipes, clinical = with_encounters(*STANDARD_EXTRAS)
    assert build_showcase(recipes=recipes, clinical=clinical) == two_bills

    write_showcase(two_bills, tmp_path / "a")
    write_showcase(build_showcase(recipes=recipes, clinical=clinical), tmp_path / "b")
    names = ["cohort_registry.json", *(f"sut/claims/{n}" for n in TABLE_FILES), *(f"sut/clean/{n}" for n in CLEAN_TABLE_FILES)]
    for name in names:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name
    assert check_showcase(tmp_path / "a", result=two_bills) == []
    assert check_showcase(DEFAULT_OUT_DIR, result=two_bills) != []  # these are not the committed files

    monkeypatch.setattr(claims_config, "SYNTHETIC_SUT_DIR", tmp_path / "a" / "sut")  # let the loader read it
    monkeypatch.setattr(claims_config, "DEFAULT_SYNTHETIC_CLEAN_DIR", tmp_path / "a" / "sut" / "clean")
    load_sut_claim_dataset.cache_clear()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dataset = load_sut_claim_dataset(tmp_path / "a" / "sut" / "claims", mode="synthetic_demo")
    assert tuple(dataset.claims) == tuple(c.header.claim_id for c in two_bills.claims)
    assert len(dataset.copay_profiles_by_patient) == cohort.patient_count()
    for claim in two_bills.claims:
        cid = claim.header.claim_id
        assert dataset.claims[cid] == claim.header
        assert dataset.procedure_lines_by_claim.get(cid, ()) == claim.procedures
        assert dataset.drug_lines_by_claim.get(cid, ()) == claim.drugs
        assert dataset.diagnoses_by_claim.get(cid, ()) == claim.diagnoses
    assert {c for c, h in dataset.claims.items() if h.patient_id == "SENTETIK-HASTA-0004"} == {
        "F-SENTETIK-HASTA-0004-001",
        "F-SENTETIK-HASTA-0004-002",
        "F-SENTETIK-HASTA-0004-003",
        "F-SENTETIK-HASTA-0004-004",
    }


def test_the_lab_values_of_a_second_bill_are_drawn_afresh_and_the_first_bills_are_not_moved(
    two_bills: BuildResult, built_showcase: BuildResult
) -> None:
    lab = two_bills.clean_tables["lab_clean.parquet"].filter(pl.col("HASTA_ID") == "SENTETIK-HASTA-0004")
    first = lab.filter(pl.col("basvuru_id") == "B-SENTETIK-HASTA-0004-001")
    second = lab.filter(pl.col("basvuru_id") == "B-SENTETIK-HASTA-0004-004")
    assert first.height == second.height > 0  # the same pathway bills the same tests
    assert first.drop("basvuru_id", "tarih").equals(
        built_showcase.clean_tables["lab_clean.parquet"]
        .filter(pl.col("basvuru_id") == "B-SENTETIK-HASTA-0004-001")
        .drop("basvuru_id", "tarih")
    )
    key = ["SUB_CODE", "parametre"]
    paired = first.select(*key, "sonuc_sayisal").join(second.select(*key, "sonuc_sayisal"), on=key, suffix="_2nd")
    numeric = paired.drop_nulls()
    assert numeric.height > 0
    assert (numeric["sonuc_sayisal"] != numeric["sonuc_sayisal_2nd"]).any(), (
        "two bills of one patient must not carry the same lab values"
    )


def test_a_faulty_second_bill_is_recorded_on_its_own_claim() -> None:
    """The first bill of patient 4 is clean (and takes another story), the fault sits on the extra fourth bill."""
    recipes, clinical = with_encounters(
        Extra(4, 4, "pyelonephritis_dementia_delirium_ward", {"admit": "2026-05-12"}, fault="F_S4_COMPANION_NOT_BILLED")
    )
    raw = [r for r in recipes.recipes]
    first = next(i for i, r in enumerate(raw) if (r.patient_no, r.encounter_no) == (4, 1))
    raw[first] = raw[first].model_copy(update={"fault": None, "pins": EncounterPins(story="S92")})
    built = build_showcase(recipes=recipes.model_copy(update={"recipes": raw}), clinical=clinical)

    committed = cohort.fault("S4")
    (record,) = (r for r in built.records if r.story == "S4")
    assert record.claim_id == "F-SENTETIK-HASTA-0004-004"
    assert record.amount_try == committed["amount_try"]  # the same fault, the same amount at stake
    assert record.line_id.startswith("ILC-F-SENTETIK-HASTA-0004-004-") or record.line_type == "fatura"
    row = built.tables["expected_rule_outputs.parquet"].filter(pl.col("claim_id") == record.claim_id)
    assert row.height >= 1 and set(row["patient_id"]) == {"SENTETIK-HASTA-0004"}
    # the faulty bill and its clean twin are expanded with the same pins: the date of the second stay, not the pathway's
    faulty = next(c for c in built.claims if c.header.claim_id == record.claim_id)
    twin = next(c for c in built.clean_claims if c.header.claim_id == record.claim_id)
    assert faulty.pins == twin.pins and faulty.pins.admit == "2026-05-12"
    assert faulty.header.admission_date == twin.header.admission_date == date(2026, 5, 12)
    assert {line.procedure_date for line in faulty.procedures} <= {date(2026, 5, day) for day in range(12, 18)}
    # the role of S4 names the bill that carries the fault; the clean first bill is a scenario of S92
    assert built.registry["roles"]["showcase_S4"]["claim_id"] == "F-SENTETIK-HASTA-0004-004"
    assert built.registry["scenarios"]["S92"]["claim_ids"] == ["F-SENTETIK-HASTA-0004-001"]
    validate_cohort_registry(built.registry, built.tables, built.clean_tables)


def test_two_bills_that_share_a_story_are_refused_before_anything_is_built() -> None:
    recipes, clinical = with_encounters(Extra(4, 4, "pyelonephritis_dementia_delirium_ward", {"admit": "2026-05-12"}))
    with pytest.raises(RecipeLoadError) as excinfo:
        build_showcase(recipes=recipes, clinical=clinical)
    assert [p.check for p in excinfo.value.problems] == ["recipe.story"]


def _encounter_pin_defects() -> list[tuple[str, Any, str]]:
    return [
        ("empty", {}, "pins must be non-empty and hold only the fields the recipe sets, got {}"),
        ("none_kept", {"admit": "2026-05-12", "nights": None}, "hold only the fields the recipe sets"),
        ("not_a_mapping", ["admit"], "pins are not recipe pins"),
        ("a_string", "2026-05-12", "pins are not recipe pins"),
        ("unknown_field", {"price": 5}, "pins are not recipe pins: price: Extra inputs are not permitted"),
        ("bad_date", {"admit": "May 12"}, "pins are not recipe pins: admit: "),
        ("age_out_of_range", {"age": 200}, "pins are not recipe pins: age: "),
        ("date_as_a_number", {"admit": 20260512}, "pins are not recipe pins: admit: "),
    ]


def test_the_registry_check_accepts_the_pins_of_an_encounter(two_bills: BuildResult) -> None:
    validate_cohort_registry(two_bills.registry, two_bills.tables, two_bills.clean_tables)
    registry = copy.deepcopy(two_bills.registry)
    for enc in registry["encounters"]:
        enc.pop("pins", None)  # an encounter with no override has no key at all
    validate_cohort_registry(registry, two_bills.tables, two_bills.clean_tables)


@pytest.mark.parametrize(
    ("pins", "message"),
    [pytest.param(pins, message, id=name) for name, pins, message in _encounter_pin_defects()],
)
def test_damaged_pins_of_an_encounter_are_refused(two_bills: BuildResult, pins: Any, message: str) -> None:
    registry = copy.deepcopy(two_bills.registry)
    next(e for e in registry["encounters"] if e["claim_id"] == "F-SENTETIK-HASTA-0004-004")["pins"] = pins
    with pytest.raises(BuildError, match=re.escape("encounter 'F-SENTETIK-HASTA-0004-004' ")) as excinfo:
        validate_cohort_registry(registry, two_bills.tables, two_bills.clean_tables)
    assert message in str(excinfo.value)


@pytest.mark.parametrize("filename", ["recipes.py", "build.py"])
def test_recipes_and_build_import_hygiene(filename: str) -> None:
    import ast

    source = (_REPO / "scripts/synthetic/cohort" / filename).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=filename)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    for mod in imported_modules:
        assert not mod.startswith("pandas"), f"{filename} imports pandas: {mod}"
        assert not mod.startswith("reports"), f"{filename} imports from reports: {mod}"
        assert "billing" not in mod, f"{filename} imports from billing engine: {mod}"
        assert "prose_rules" not in mod, f"{filename} imports from prose_rules engine: {mod}"


# --- MEDULA rejection events (G8): a recipe input that becomes rows of medula_rejection_events.parquet --------------

_ER_CLAIM = "F-SENTETIK-HASTA-0012-001"  # S10, the ER visit of patient 12


def test_the_committed_rejection_event_is_the_one_of_s10_on_its_manual_haematocrit_line(
    built_showcase: BuildResult,
) -> None:
    events = built_showcase.tables["medula_rejection_events.parquet"]
    lines = built_showcase.tables["procedure_claim_lines.parquet"].filter(pl.col("claim_id") == _ER_CLAIM)
    manual = lines.filter(pl.col("procedure_code") == "L103120").row(0, named=True)
    assert events.to_dicts() == [
        {
            "rejection_event_id": "RED-F-SENTETIK-HASTA-0012-001-01",
            "claim_id": _ER_CLAIM,
            "patient_id": "SENTETIK-HASTA-0012",
            "episode_id": "B-SENTETIK-HASTA-0012-001",
            "medula_stage": "fatura_kayit",
            "sonuc_kodu": "0901",
            "hata_kodu": "",
            "hata_mesaji": "Mükerrer işlem: aynı gün tekrar faturalandırma",
            "rejection_timestamp": "2026-05-09",  # the date of the line, inside the ER bill's one date
            "related_procedure_code": "L103120",
            "related_procedure_line_id": manual["procedure_line_id"],
            "related_line_type": "procedure",
            "related_line_id": manual["procedure_line_id"],
        }
    ]
    assert manual["procedure_date"] == "2026-05-09"
    assert built_showcase.registry["counts"]["medula_rejection_events.parquet"] == 1


def _event(entry_id: str, **changes: str) -> MedulaEvent:
    return MedulaEvent(
        entry_id=entry_id,
        medula_stage=changes.pop("medula_stage", "fatura_kayit"),
        sonuc_kodu=changes.pop("sonuc_kodu", "0901"),
        hata_mesaji="Mükerrer işlem: aynı gün tekrar faturalandırma",
        basis="judgment",
        source="A test event: how the builder resolves an entry of any section.",
        **changes,
    )


@pytest.fixture(scope="module")
def built_with_events() -> BuildResult:
    """The committed recipes with three more rejections: a second one on S10's bill, one on a material of S5 and one
    on a drug of S6 (a material and a drug line are billed lines too)."""
    recipes = load_recipes()
    extra = {
        (12, 1): (_event("hemogram", sonuc_kodu="1205", medula_stage="hizmet_kayit", hata_kodu="E-1205"),),
        (5, 1): (_event("femoral_stem", sonuc_kodu="0704"),),
        (6, 1): (_event("pk_merz", sonuc_kodu="0411"),),
    }
    changed = [
        r.model_copy(update={"medula_events": [*r.medula_events, *extra[(r.patient_no, r.encounter_no)]]})
        if (r.patient_no, r.encounter_no) in extra
        else r
        for r in recipes.recipes
    ]
    return build_showcase(recipes=recipes.model_copy(update={"recipes": changed}))


def test_events_are_numbered_per_claim_dated_with_their_line_and_name_any_billed_line(
    built_with_events: BuildResult,
) -> None:
    events = built_with_events.tables["medula_rejection_events.parquet"]
    rows = {row["rejection_event_id"]: row for row in events.iter_rows(named=True)}
    assert list(rows) == sorted(rows) == [
        "RED-F-SENTETIK-HASTA-0005-001-01",
        "RED-F-SENTETIK-HASTA-0006-001-01",
        "RED-F-SENTETIK-HASTA-0012-001-01",
        "RED-F-SENTETIK-HASTA-0012-001-02",  # the second event of the claim, in the order of the recipe
    ]
    material = rows["RED-F-SENTETIK-HASTA-0005-001-01"]
    assert (material["related_line_type"], material["related_procedure_code"], material["related_procedure_line_id"]) == (
        "material", "", ""
    )  # fmt: skip
    assert MATERIAL_LINE_ID_RE.fullmatch(material["related_line_id"])
    drug = rows["RED-F-SENTETIK-HASTA-0006-001-01"]
    assert drug["related_line_type"] == "drug" and DRUG_CLAIM_LINE_ID_RE.fullmatch(drug["related_line_id"])
    assert drug["related_procedure_code"] == "" and drug["related_procedure_line_id"] == ""
    second = rows["RED-F-SENTETIK-HASTA-0012-001-02"]
    assert (second["related_procedure_code"], second["medula_stage"], second["sonuc_kodu"], second["hata_kodu"]) == (
        "L107020", "hizmet_kayit", "1205", "E-1205"
    )  # fmt: skip
    # each event is dated with its line
    tables = built_with_events.tables
    dated = {
        **dict(zip(tables["procedure_claim_lines.parquet"]["procedure_line_id"], tables["procedure_claim_lines.parquet"]["procedure_date"], strict=True)),
        **dict(zip(tables["material_claim_lines.parquet"]["material_line_id"], tables["material_claim_lines.parquet"]["material_date"], strict=True)),
        **dict(zip(tables["drug_claim_lines.parquet"]["drug_claim_line_id"], tables["drug_claim_lines.parquet"]["drug_claim_date"], strict=True)),
    }
    assert all(row["rejection_timestamp"] == dated[row["related_line_id"]] for row in rows.values())
    assert built_with_events.registry["counts"]["medula_rejection_events.parquet"] == 4
    # the rest of the cohort is the committed one: the events table is the only claims table that moves
    committed = build_showcase()
    assert {name for name in TABLE_FILES if not built_with_events.tables[name].equals(committed.tables[name])} == {
        "medula_rejection_events.parquet"
    }


def test_the_loader_reads_every_kind_of_event_row_the_builder_writes(
    built_with_events: BuildResult, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_showcase(built_with_events, tmp_path)
    monkeypatch.setattr(claims_config, "SYNTHETIC_SUT_DIR", tmp_path / "sut")  # let the loader read it
    monkeypatch.setattr(claims_config, "DEFAULT_SYNTHETIC_CLEAN_DIR", tmp_path / "sut" / "clean")
    load_sut_claim_dataset.cache_clear()
    dataset = load_sut_claim_dataset(tmp_path / "sut" / "claims", mode="synthetic_demo")
    assert sorted(dataset.medula_rejection_events) == built_with_events.tables["medula_rejection_events.parquet"][
        "rejection_event_id"
    ].to_list()
    assert {e.related_line_type for e in dataset.medula_rejection_events.values()} == {"procedure", "material", "drug"}
    assert dataset.medula_rejection_ingest_available is True


def test_an_event_whose_entry_is_not_one_billed_line_stops_the_build(built_showcase: BuildResult) -> None:
    from dataclasses import replace

    recipe = next(r for r in load_recipes().recipes if r.medula_events)
    claim = next(c for c in built_showcase.claims if c.header.claim_id == _ER_CLAIM)
    assert len(_medula_event_rows(recipe, claim)) == 1
    with pytest.raises(BuildError, match=r"names entry 'manual_hematocrit', which is 0 line\(s\)"):
        _medula_event_rows(recipe, replace(claim, entry_line_ids={}))
    two = (claim.procedures[0].procedure_line_id, claim.procedures[1].procedure_line_id)
    with pytest.raises(BuildError, match=r"which is 2 line\(s\)"):
        _medula_event_rows(recipe, replace(claim, entry_line_ids={"manual_hematocrit": two}))
    with pytest.raises(BuildError, match="is not a billed line"):
        _medula_event_rows(recipe, replace(claim, entry_line_ids={"manual_hematocrit": ("EMR-F-SENTETIK-HASTA-0012-001-001",)}))



def test_the_chronic_report_pin_reaches_the_patients_copay_profile_and_nothing_else(
    built_showcase: BuildResult,
) -> None:
    """The committed cohort knows one report, S2's (WP9: both pathways of patient 2 pin it); a pin on a patient's
    bill sets that patient's profile row only: every other row and every other table stays as it was."""
    committed = built_showcase.tables["patient_copay_profiles.parquet"]
    assert committed.schema["has_chronic_health_report"] == pl.Boolean
    known = dict(zip(committed["patient_id"].to_list(), committed["has_chronic_health_report"].to_list(), strict=True))
    assert known.pop(cohort.role("showcase_S2").patient_id) is True
    assert set(known.values()) == {None}

    patient = cohort.role("showcase_S3").patient_id  # a one-bill patient with an EK-1/A match and no report
    recipes = load_recipes()
    pinned = [
        r.model_copy(update={"pins": EncounterPins(chronic_health_report=False)}) if r.patient_no == 3 else r
        for r in recipes.recipes
    ]
    assert sum(r.patient_no == 3 for r in pinned) == 1 and all(r.pins is None for r in recipes.recipes if r.patient_no == 3)
    built = build_showcase(recipes=recipes.model_copy(update={"recipes": pinned}))

    profiles = built.tables["patient_copay_profiles.parquet"]
    flags = dict(zip(profiles["patient_id"].to_list(), profiles["has_chronic_health_report"].to_list(), strict=True))
    assert flags.pop(patient) is False
    assert flags == {**{pid: v for pid, v in known.items() if pid != patient}, cohort.role("showcase_S2").patient_id: True}
    assert profiles.drop("has_chronic_health_report").equals(committed.drop("has_chronic_health_report"))
    for name in TABLE_FILES:
        if name != "patient_copay_profiles.parquet":
            assert built.tables[name].equals(built_showcase.tables[name], null_equal=True), name
    for name in CLEAN_TABLE_FILES:
        assert built.clean_tables[name].equals(built_showcase.clean_tables[name], null_equal=True), name
