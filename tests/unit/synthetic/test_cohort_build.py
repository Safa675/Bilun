"""Acceptance, round-trip and hygiene tests for `scripts/synthetic/cohort/build.py`."""

from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path
import re
from typing import Any
import warnings

import polars as pl
import pytest

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
    BuildResult,
    build_tables,
    clean_tables_digest,
    load_recipes,
    tables_digest,
    validate_cohort_registry,
    write_showcase,
)
from scripts.synthetic.cohort.build import DEFAULT_OUT_DIR, main
from scripts.synthetic.faults import (
    FaultInjectionRecord,
    build_expected_rule_outputs,
)
from scripts.synthetic.pathways.loader import hygiene
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.models import ExpectedRuleOutput, PatientCopayProfile
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_OUT_DIR = DEFAULT_OUT_DIR
_CLAIMS_DIR = _OUT_DIR / "sut" / "claims"
_CLEAN_DIR = _OUT_DIR / "sut" / "clean"
_REGISTRY_JSON_PATH = _OUT_DIR / "cohort_registry.json"
_RESULTS_DIR = _REPO / "reports/synthetic-data/2026-10-15-showcase-proofs/results"

_EXPECTED_AMOUNTS_BY_STORY: dict[str, str] = {
    "S1": "4122.12",
    "S2": "667.05",
    "S3": "928.08",
    "S4": "370.45",
    "S5": "6465.27",
    "S6": "0.00",
    "S7": "1138.22",
    "S8": "5377.20",
    "S9": "758.00",
    "S10": "5.88",
    "S11": "6089.82",
    "S12": "1322.94",
    "S14": "222.35",
    "S15": "222.35",  # the ward bed beside the cot on the admission day: the 510010 line at risk (deduction_risk)
    "S17": "0.00",  # the ESA prescribed by the wrong branch: a drug line, and drugs enter at 0 TL
    "S18": "0.00",  # the albumin without the specialist report: a drug line, and drugs enter at 0 TL
    "S20": "4724.86",
    "S21": "0.00",  # the radiotherapy course keyed as totals: reviews of the course and day limits without an amount (EI-19)
    "S22": "439.86",
    "S24": "0.00",  # the red-cell units without their ISBT 128 numbers: a flag of the lines, no amount (a compliance error)
    "S33": "0.00",  # the enoxaparin count: a drug line, and drugs enter at 0 TL
    "S34": "0.00",  # the examination flagged as a package component: a flag without money
    "S38": "0.00",  # the neuromonitoring beside an instrumentation not on EK-2/D-4: a review without money (compliance_error)
    "S40": "0.00",
    "S42": "5712.18",  # two red-cell units billed in full inside a package instead of 36 %: the difference of the totals
    "S44": "0.00",  # romosozumab on a report of 12 months: a drug line, and drugs enter at 0 TL
    "S46": "252.00",  # the second walker inside the MIAT of the first: the walker line is at risk (deduction_risk)
    "S47": "44.45",
    "S49": "0.00",  # the CRP and the ultrasound beside the flat-fee green-area visit: a review without money (compliance_error)
    "S50": "1347.94",  # the sphincterotomy and the stone extraction billed in full beside the ERCP package instead of 30 %
}

# The stories after the eighth, as the committed registry names them: a patient and the claims of its bills.
# S23, S30, S31, S32, S36, S37, S39, S41, S43, S45, S48 and S51 are clean bills (no fault, no record; S31 was a dormant
# fault of C000714, which no detector reads), the others carry one.
_COMMITTED_SCENARIOS: dict[str, dict[str, Any]] = {
    "S9": {"patient_id": "SENTETIK-HASTA-0009", "claim_ids": ["F-SENTETIK-HASTA-0009-001"]},
    "S11": {"patient_id": "SENTETIK-HASTA-0010", "claim_ids": ["F-SENTETIK-HASTA-0010-001"]},
    "S12": {"patient_id": "SENTETIK-HASTA-0011", "claim_ids": ["F-SENTETIK-HASTA-0011-001"]},
    "S14": {"patient_id": "SENTETIK-HASTA-0010", "claim_ids": ["F-SENTETIK-HASTA-0010-002"]},
    "S15": {"patient_id": "SENTETIK-HASTA-0011", "claim_ids": ["F-SENTETIK-HASTA-0011-002"]},
    "S10": {"patient_id": "SENTETIK-HASTA-0012", "claim_ids": ["F-SENTETIK-HASTA-0012-001"]},
    "S22": {"patient_id": "SENTETIK-HASTA-0012", "claim_ids": ["F-SENTETIK-HASTA-0012-002"]},
    "S32": {"patient_id": "SENTETIK-HASTA-0002", "claim_ids": ["F-SENTETIK-HASTA-0002-002"]},
    "S33": {"patient_id": "SENTETIK-HASTA-0002", "claim_ids": ["F-SENTETIK-HASTA-0002-003"]},
    "S34": {"patient_id": "SENTETIK-HASTA-0002", "claim_ids": ["F-SENTETIK-HASTA-0002-004"]},
    "S36": {"patient_id": "SENTETIK-HASTA-0003", "claim_ids": ["F-SENTETIK-HASTA-0003-002"]},
    "S37": {"patient_id": "SENTETIK-HASTA-0003", "claim_ids": ["F-SENTETIK-HASTA-0003-003"]},
    "S38": {"patient_id": "SENTETIK-HASTA-0003", "claim_ids": ["F-SENTETIK-HASTA-0003-004"]},
    "S20": {"patient_id": "SENTETIK-HASTA-0013", "claim_ids": ["F-SENTETIK-HASTA-0013-001"]},
    "S21": {"patient_id": "SENTETIK-HASTA-0016", "claim_ids": ["F-SENTETIK-HASTA-0016-001"]},
    "S17": {"patient_id": "SENTETIK-HASTA-0014", "claim_ids": ["F-SENTETIK-HASTA-0014-001"]},
    "S23": {"patient_id": "SENTETIK-HASTA-0014", "claim_ids": ["F-SENTETIK-HASTA-0014-002"]},
    "S18": {"patient_id": "SENTETIK-HASTA-0015", "claim_ids": ["F-SENTETIK-HASTA-0015-001"]},
    "S24": {"patient_id": "SENTETIK-HASTA-0015", "claim_ids": ["F-SENTETIK-HASTA-0015-002"]},
    "S47": {"patient_id": "SENTETIK-HASTA-0007", "claim_ids": ["F-SENTETIK-HASTA-0007-002"]},
    "S48": {"patient_id": "SENTETIK-HASTA-0007", "claim_ids": ["F-SENTETIK-HASTA-0007-003"]},
    "S49": {"patient_id": "SENTETIK-HASTA-0008", "claim_ids": ["F-SENTETIK-HASTA-0008-002"]},
    "S50": {"patient_id": "SENTETIK-HASTA-0008", "claim_ids": ["F-SENTETIK-HASTA-0008-003"]},
    "S51": {"patient_id": "SENTETIK-HASTA-0008", "claim_ids": ["F-SENTETIK-HASTA-0008-004"]},
    "S52": {"patient_id": "SENTETIK-HASTA-0002", "claim_ids": ["F-SENTETIK-HASTA-0002-005"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S53": {"patient_id": "SENTETIK-HASTA-0002", "claim_ids": ["F-SENTETIK-HASTA-0002-006"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S54": {"patient_id": "SENTETIK-HASTA-0004", "claim_ids": ["F-SENTETIK-HASTA-0004-004"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S55": {"patient_id": "SENTETIK-HASTA-0005", "claim_ids": ["F-SENTETIK-HASTA-0005-006"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S56": {"patient_id": "SENTETIK-HASTA-0006", "claim_ids": ["F-SENTETIK-HASTA-0006-004"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S57": {"patient_id": "SENTETIK-HASTA-0008", "claim_ids": ["F-SENTETIK-HASTA-0008-005"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S58": {"patient_id": "SENTETIK-HASTA-0008", "claim_ids": ["F-SENTETIK-HASTA-0008-006"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S59": {"patient_id": "SENTETIK-HASTA-0009", "claim_ids": ["F-SENTETIK-HASTA-0009-002"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S60": {"patient_id": "SENTETIK-HASTA-0010", "claim_ids": ["F-SENTETIK-HASTA-0010-003"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S61": {"patient_id": "SENTETIK-HASTA-0012", "claim_ids": ["F-SENTETIK-HASTA-0012-003"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S62": {"patient_id": "SENTETIK-HASTA-0014", "claim_ids": ["F-SENTETIK-HASTA-0014-003"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S63": {"patient_id": "SENTETIK-HASTA-0015", "claim_ids": ["F-SENTETIK-HASTA-0015-003"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S64": {"patient_id": "SENTETIK-HASTA-0015", "claim_ids": ["F-SENTETIK-HASTA-0015-004"]},  # the visit before a stay (review of 2026-10-30, A1)
    "S30": {"patient_id": "SENTETIK-HASTA-0001", "claim_ids": ["F-SENTETIK-HASTA-0001-002"]},
    "S31": {"patient_id": "SENTETIK-HASTA-0001", "claim_ids": ["F-SENTETIK-HASTA-0001-003"]},
    "S39": {"patient_id": "SENTETIK-HASTA-0004", "claim_ids": ["F-SENTETIK-HASTA-0004-002"]},
    "S40": {"patient_id": "SENTETIK-HASTA-0004", "claim_ids": ["F-SENTETIK-HASTA-0004-003"]},
    "S41": {"patient_id": "SENTETIK-HASTA-0005", "claim_ids": ["F-SENTETIK-HASTA-0005-002"]},
    "S42": {"patient_id": "SENTETIK-HASTA-0005", "claim_ids": ["F-SENTETIK-HASTA-0005-003"]},
    "S43": {"patient_id": "SENTETIK-HASTA-0005", "claim_ids": ["F-SENTETIK-HASTA-0005-004"]},
    "S44": {"patient_id": "SENTETIK-HASTA-0005", "claim_ids": ["F-SENTETIK-HASTA-0005-005"]},
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
def built_showcase(committed_showcase: BuildResult) -> BuildResult:
    return committed_showcase


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


def test_hygiene_and_id_formats_on_committed_files() -> None:
    # 1. Text hygiene on showcase_recipes.yaml, cohort_registry.json, and README.md.
    recipes_text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes_raw = json.loads(json.dumps(load_recipes().model_dump()))
    assert hygiene(recipes_raw, recipes_text) == []

    for text_path in (RECIPES_PATH, _REGISTRY_JSON_PATH, _OUT_DIR / "README.md"):
        content = text_path.read_text(encoding="utf-8")
        assert not _ANON_RE.search(content), f"ANON text found in {text_path}"
        assert not _CURRENCY_RE.search(content), f"Currency text found in {text_path}"

    # 2. No ANON_ or currency text in any string column of the 9 Parquet tables, and all IDs match ids.py.
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
    reg_data = json.loads(_REGISTRY_JSON_PATH.read_text(encoding="utf-8"))
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
