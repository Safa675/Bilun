"""Acceptance, round-trip, determinism, hygiene and mutation tests for `scripts/synthetic/cohort/build.py`."""

from __future__ import annotations

import copy
from decimal import Decimal
import json
from pathlib import Path
import re
import shutil
from typing import Any
import warnings

import polars as pl
import pytest
from pydantic import ValidationError

from scripts.synthetic.cohort import (
    CLAIM_ID_RE,
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
    load_recipes,
    tables_digest,
    validate_cohort_registry,
)
from scripts.synthetic.cohort.build import DEFAULT_OUT_DIR, main
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

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_SHOWCASE_DIR = DEFAULT_OUT_DIR
_CLAIMS_DIR = _SHOWCASE_DIR / "sut" / "claims"
_REGISTRY_JSON_PATH = _SHOWCASE_DIR / "cohort_registry.json"
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
}

_ANON_RE = re.compile(r"anon_|\banon[\s-]*[0-9]", re.IGNORECASE)
_CURRENCY_RE = re.compile(
    r"(?=[0-9.,]*[1-9])[0-9][0-9.,]*\s*(?:TL|TRY|\u20ba)(?![A-Za-z])|\u20ba\s*(?=[0-9.,]*[1-9])[0-9][0-9.,]*",
    re.IGNORECASE,
)


@pytest.fixture(autouse=True)
def _allow_showcase_synthetic_claims_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow `load_sut_claim_dataset(..., mode='synthetic_demo')` to read `data/synthetic/showcase/sut/claims`."""
    monkeypatch.setattr(claims_config, "SYNTHETIC_SUT_DIR", _SHOWCASE_DIR / "sut")
    monkeypatch.setattr(
        claims_config, "DEFAULT_SYNTHETIC_CLEAN_DIR", _SHOWCASE_DIR / "sut" / "clean"
    )
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


def test_cli_check_passes_on_committed_and_fails_on_table_or_json_change(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--check"]) == 0
    assert "ok (8 claims, 9 tables)" in capsys.readouterr().out

    assert main(["--out", str(_SHOWCASE_DIR), "--check"]) == 0
    capsys.readouterr()

    # Copy committed folder to tmp_path and verify --check passes on the untouched copy.
    copy_dir = tmp_path / "showcase_copy"
    shutil.copytree(_SHOWCASE_DIR, copy_dir)
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


# --- 4. Loader acceptance ----------------------------------------------------------------------


def test_loader_accepts_committed_showcase_dataset_and_matches_composed_claims(
    built_showcase: BuildResult,
) -> None:
    load_sut_claim_dataset.cache_clear()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dataset = load_sut_claim_dataset(_CLAIMS_DIR, mode="synthetic_demo")

    expected_counts = built_showcase.registry["counts"]
    assert len(dataset.claims) == 8 == expected_counts["claim_headers.parquet"]
    assert len(dataset.diagnoses) == expected_counts["claim_diagnoses.parquet"]
    assert len(dataset.procedure_lines) == expected_counts["procedure_claim_lines.parquet"]
    assert len(dataset.material_lines) == expected_counts["material_claim_lines.parquet"]
    assert len(dataset.drug_lines) == expected_counts["drug_claim_lines.parquet"]
    assert len(dataset.expected_outputs) == 8 == expected_counts["expected_rule_outputs.parquet"]
    assert (
        len(dataset.copay_profiles_by_patient)
        == 8
        == expected_counts["patient_copay_profiles.parquet"]
    )
    assert (
        len(dataset.performed_procedure_lines)
        == expected_counts["performed_procedure_lines.parquet"]
    )
    assert len(dataset.medula_rejection_events) == 0

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
    assert len(built_showcase.records) == 8
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

    # S1, S5, S8 have package_candidate=True in both clean and faulty composed headers; others False.
    for story_idx, (clean_c, faulty_c) in enumerate(
        zip(built_showcase.clean_claims, built_showcase.claims, strict=True), start=1
    ):
        story = f"S{story_idx}"
        expected_pkg_cand = story in {"S1", "S5", "S8"}
        assert clean_c.header.package_candidate is expected_pkg_cand
        assert faulty_c.header.package_candidate is expected_pkg_cand


# --- 6. Registry consistency -------------------------------------------------------------------


def test_registry_consistency_against_committed_tables(built_showcase: BuildResult) -> None:
    committed_reg = json.loads(_REGISTRY_JSON_PATH.read_text(encoding="utf-8"))
    committed_tables = {name: pl.read_parquet(_CLAIMS_DIR / name) for name in TABLE_FILES}

    validate_cohort_registry(committed_reg, committed_tables)

    assert committed_reg["schema_version"] == 1
    assert committed_reg["dataset_id"] == "showcase-v3"
    assert committed_reg["seed"] is None

    # counts equal the table heights.
    assert committed_reg["counts"] == {name: df.height for name, df in committed_tables.items()}

    # tables_digest equals a fresh digest of the committed tables.
    assert committed_reg["tables_digest"] == tables_digest(committed_tables)

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
    assert set(roles) == {"default_landing", *(f"showcase_S{n}" for n in range(1, 9))}
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

    for text_path in (RECIPES_PATH, _REGISTRY_JSON_PATH, _SHOWCASE_DIR / "README.md"):
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
    problems = check_recipes(mismatched_recipes)
    assert [p.check for p in problems] == ["recipe.fault_pathway"]
    with pytest.raises(RecipeLoadError) as exc_info:
        build_showcase(recipes=mismatched_recipes)
    assert [p.check for p in exc_info.value.problems] == ["recipe.fault_pathway"]

    # Also caught directly by apply_fault if called with mismatched pathway.
    pathways = load_all()
    with pytest.raises(FaultApplyError, match="target_pathway"):
        apply_fault(s1_fault, pathways["copd_exacerbation_pneumonia_ward"])


def test_target_and_evidence_line_resolution_guards(built_showcase: BuildResult) -> None:
    from dataclasses import replace
    from scripts.synthetic.cohort.build import _resolve_evidence_line_ids, _resolve_target_line_id

    faults_by_story = {f.story: f for f in load_registry().faults if f.story is not None}

    # If a line-level fault's target_entry_id resolves to 0 or >1 lines, _resolve_target_line_id raises BuildError.
    s5_fault = faults_by_story["S5"]
    s5_claim = built_showcase.claims[4]
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
    s7_claim = built_showcase.claims[6]
    no_ev_claim = replace(s7_claim, entry_line_ids={})
    with pytest.raises(
        BuildError, match="evidence_entry_id 'ct_angiography_pacs' resolved to 0 lines"
    ):
        _resolve_evidence_line_ids(s7_fault, no_ev_claim)


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
