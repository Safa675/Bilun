"""Public cache-to-HTTP regressions; no private cache or serving process is used.

The source projection worker, transport seal, raw content comparator and HTTP
normalizer run unchanged. Only public proof identities use fixture Git objects.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import sys
import sysconfig
from dataclasses import replace
from pathlib import Path
from urllib.parse import quote

import duckdb
import pytest

from scripts.deploy import rehearse_wavea_same_port as rehearsal
from scripts.deploy import verify_candidate_semantics as semantics
from scripts.deploy import verify_final_source_refresh_transition as final
from scripts.deploy import verify_source_refresh_transition as previous
from tests.unit.deploy.test_final_source_refresh_transition import (
    _final_report,
    _public_final_pair,
)
from tests.unit.deploy.test_same_port_rehearsal import (
    fixture_git_commit,
    full_report,
    isolated_projection_source as isolated_projection_source,
)

PATIENT_PATH = "/api/billing-report/P1"
BILL_PATH = "/api/billing-report/P1/bills/C1"
REPORT_TABLES = ("patient_billing_report_rows", "patient_bill_billing_report_rows")


def _authored_pair():
    """Author raw expectations before writing caches or projecting any DTO.

    Empty typed findings isolate the measured representation boundary; the
    existing clinical-transition suites test the permitted clinical annotations.
    In particular, a cached bill has patient_id, but no claim_id or scope.
    """
    pair = dict(zip(("baseline", "candidate"), _public_final_pair(), strict=True))
    for projection in pair.values():
        for table, key in zip(REPORT_TABLES, ("P1", "P1::C1"), strict=True):
            authored = projection["tables"][table][key]
            report = full_report()
            report["drug_indication"] = {
                "findings": [],
                "coverage_scope": copy.deepcopy(authored["drug_indication"]["coverage_scope"]),
            }
            report["materials"] = {
                "findings": [],
                "specialty_coverage_scope": copy.deepcopy(
                    authored["materials"]["specialty_coverage_scope"]
                ),
            }
            report["nullable_amount"] = None
            report["typed_flag"] = True
            projection["tables"][table][key] = report
    return pair


def _write_cache(path, tables, code_sha, build_id):
    with duckdb.connect(str(path)) as db:
        db.execute("CREATE TABLE build_pointer_scopes(scope VARCHAR, active_build_id VARCHAR)")
        db.execute("INSERT INTO build_pointer_scopes VALUES ('bilun', ?)", [build_id])
        db.execute("CREATE TABLE build_meta(build_id VARCHAR, source_hash VARCHAR, "
                   "status VARCHAR, build_scope VARCHAR, config_hash VARCHAR, "
                   "code_sha VARCHAR, schema_version VARCHAR)")
        db.execute("INSERT INTO build_meta VALUES (?, ?, 'complete', 'bilun', ?, ?, 'v1')",
                   [build_id, "a" * 64, "b" * 64, code_sha])
        for table in REPORT_TABLES:
            db.execute(f"CREATE TABLE {table}(build_id VARCHAR, patient_id VARCHAR, payload_json VARCHAR)")
            db.executemany(f"INSERT INTO {table} VALUES (?, ?, ?)", [
                (build_id, key, json.dumps(row)) for key, row in tables[table].items()
            ])
        db.execute("CREATE TABLE cohort_optimization_summary(build_id VARCHAR, payload_json VARCHAR)")
        provenance = next(iter(tables["patient_billing_report_rows"].values()))["data_source"]
        db.execute("INSERT INTO cohort_optimization_summary VALUES (?, ?)",
                   [build_id, json.dumps({"data_source": provenance})])


@pytest.fixture
def raw_transport_case(tmp_path, monkeypatch, isolated_projection_source):
    repository, code_sha = isolated_projection_source
    tree = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(repository), "rev-parse", "HEAD^{tree}"],
    ).decode().strip()
    # This is an authored unit proof, not production admission. Its serializer
    # identities honestly name the actual public source copied by the fixture.
    for module in (final, previous):
        monkeypatch.setattr(module, "BASELINE_CODE_SHA", code_sha)
        monkeypatch.setattr(module, "BASELINE_TREE", tree)
    pair = _authored_pair()
    proof = final._issue_proof(_final_report(pair, candidate=code_sha), {
        side: {"tables": projection["tables"],
               "followup": projection["source_witnesses"]["followup"]}
        for side, projection in pair.items()
    })
    final.validate_transition_report_contract(proof.report)
    paths = {}
    for side, projection in pair.items():
        paths[side] = tmp_path / (side + ".duckdb")
        _write_cache(paths[side], projection["tables"], code_sha, side + "-build")
    return {
        "repository": repository, "code_sha": code_sha, "pair": pair,
        "proof": proof, "paths": paths,
        "worker": {"repository": repository, "expected_code_sha": code_sha,
                   "python_executable": Path(sys.executable),
                   "dependency_roots": (Path(sysconfig.get_path("stdlib")),
                                        Path(sysconfig.get_path("purelib")))},
    }


def _transport(case, side, *, contract="wavea-evidence-v2"):
    packages = []
    inventory = rehearsal._cache_reports(
        case["paths"][side], transport_out=packages, **case["worker"],
    )
    assert len(packages) == 1
    packages[0].validate()
    assert inventory[2:] == (contract, packages[0].complete_reports, 1, 1)
    return packages[0]


def _compare(case, old, new, *, capability="draft", observed_new=None):
    observed_old = old.draft_reports if capability == "draft" else old.complete_reports
    rehearsal.compare_reports(
        observed_old, new.draft_reports if observed_new is None else observed_new,
        contract="wavea-evidence-v2",
        old_capability=capability, old_persisted=old.complete_reports,
        old_transport=old, candidate_transport=new, clinical_transition=case["proof"],
    )


def test_real_cache_http_chain_preserves_raw_bill_and_route_dto(raw_transport_case):
    case = raw_transport_case
    before = {side: hashlib.sha256(path.read_bytes()).hexdigest()
              for side, path in case["paths"].items()}
    # Both actual raw tables already pass own-source normalization. The old
    # inventory nevertheless adds two fields before declaring its transport raw.
    for side, path in case["paths"].items():
        with duckdb.connect(str(path), read_only=True) as db:
            for table in REPORT_TABLES:
                raw = semantics._payload_rows(db, table, side + "-build")
                final.normalize_transition_content(table, raw, side=side, proof=case["proof"])
    old, new = (_transport(case, side) for side in ("baseline", "candidate"))
    # Desired pass: on frozen f28 this fails specifically at the final raw-cache
    # equality guard, after the actual source worker and transport seal pass.
    _compare(case, old, new)
    for side, transport in (("baseline", old), ("candidate", new)):
        assert transport.raw_reports[BILL_PATH] == case["pair"][side]["tables"][REPORT_TABLES[1]]["P1::C1"]
        assert "claim_id" not in transport.raw_reports[BILL_PATH]
        assert "scope" not in transport.raw_reports[BILL_PATH]
        for projected in (transport.complete_reports, transport.draft_reports):
            assert projected[BILL_PATH]["patient_id"] == "P1"
            assert projected[BILL_PATH]["claim_id"] == "C1"
            assert projected[BILL_PATH]["scope"] == "bill"
        assert hashlib.sha256(case["paths"][side].read_bytes()).hexdigest() == before[side]


def test_real_cache_http_chain_supports_complete_old_pair(raw_transport_case):
    case = raw_transport_case
    old, new = (_transport(case, side) for side in ("baseline", "candidate"))
    _compare(case, old, new, capability="complete-25-v1")
    for side, package in (("baseline", old), ("candidate", new)):
        assert package.raw_reports[PATIENT_PATH] == case["pair"][side]["tables"][REPORT_TABLES[0]]["P1"]
        assert "lab" not in package.raw_reports[PATIENT_PATH]
        assert "lab" in package.complete_reports[PATIENT_PATH]
        for reports in (package.raw_reports, package.complete_reports, package.draft_reports):
            assert reports[PATIENT_PATH]["patient_id"] == "P1"
            assert "claim_id" not in reports[PATIENT_PATH]
            assert "scope" not in reports[PATIENT_PATH]


def test_original_five_cache_and_source_worker_keep_existing_bill_shape(raw_transport_case):
    case = raw_transport_case
    paths = {}
    for side in ("baseline", "candidate"):
        report = full_report()
        for field in ("claim_reviews", "claim_advisories", "financial_findings", "wavea_coverage"):
            del report[field]
        tables = {REPORT_TABLES[0]: {"P1": copy.deepcopy(report)},
                  REPORT_TABLES[1]: {"P1::C1": copy.deepcopy(report)}}
        paths[side] = case["paths"][side].with_name(side + "-original-five.duckdb")
        _write_cache(paths[side], tables, case["code_sha"], side + "-build")
    original = {**case, "paths": paths}
    before = {side: hashlib.sha256(path.read_bytes()).hexdigest() for side, path in paths.items()}
    old, new = (_transport(original, side, contract="original-five")
                for side in ("baseline", "candidate"))
    rehearsal.compare_reports(old.complete_reports, new.draft_reports, contract="original-five",
                              old_capability=None, old_persisted=old.complete_reports,
                              old_transport=old, candidate_transport=new)
    for side, package in (("baseline", old), ("candidate", new)):
        for reports in (package.raw_reports, package.complete_reports, package.draft_reports):
            assert reports[BILL_PATH]["patient_id"] == "P1"
            assert "claim_id" not in reports[BILL_PATH]
            assert "scope" not in reports[BILL_PATH]
        assert hashlib.sha256(paths[side].read_bytes()).hexdigest() == before[side]


def test_real_cache_worker_preserves_encoded_patient_and_bill_ownership(raw_transport_case):
    case = raw_transport_case
    patient, claim = "Public patient /ş", "Public claim /β"
    tables = {}
    for table, key in zip(REPORT_TABLES, (patient, patient + "::" + claim), strict=True):
        report = full_report()
        report["patient_id"] = patient
        tables[table] = {key: report}
    path = case["paths"]["candidate"].with_name("encoded.duckdb")
    _write_cache(path, tables, case["code_sha"], "candidate-build")
    before = path.read_bytes()
    package = _transport({**case, "paths": {"candidate": path}}, "candidate")
    patient_path = "/api/billing-report/" + quote(patient, safe="")
    bill_path = patient_path + "/bills/" + quote(claim, safe="")
    assert package.raw_reports == {
        patient_path: tables[REPORT_TABLES[0]][patient],
        bill_path: tables[REPORT_TABLES[1]][patient + "::" + claim],
    }
    for reports in (package.complete_reports, package.draft_reports):
        assert reports[bill_path]["patient_id"] == patient
        assert reports[bill_path]["claim_id"] == claim
        assert reports[bill_path]["scope"] == "bill"
    assert path.read_bytes() == before


@pytest.mark.parametrize(("field", "value"), [
    ("claim_id", "C1"), ("scope", "bill"), ("patient_id", "foreign-patient"),
    ("total_recoverable_try", 12.35), ("nullable_amount", 0.0),
    ("typed_flag", 1), ("unproduced_field", {"amount": None}),
])
def test_real_chain_never_ignores_added_raw_identity_money_type_or_unknown_fields(
    raw_transport_case, field, value,
):
    case = raw_transport_case
    old = _transport(case, "baseline")
    row = copy.deepcopy(case["pair"]["candidate"]["tables"][REPORT_TABLES[1]]["P1::C1"])
    row[field] = value
    with duckdb.connect(str(case["paths"]["candidate"])) as db:
        db.execute(f"UPDATE {REPORT_TABLES[1]} SET payload_json = ? WHERE build_id = ?",
                   [json.dumps(row), "candidate-build"])
    expected = "serialization failed" if field == "patient_id" else "actual cache against"
    with pytest.raises(ValueError, match=expected):
        _compare(case, old, _transport(case, "candidate"))


@pytest.mark.parametrize("key", ["P1C1", "P1::", "foreign-patient::C1"])
def test_cache_inventory_rejects_malformed_or_foreign_bill_key(raw_transport_case, key):
    case = raw_transport_case
    with duckdb.connect(str(case["paths"]["candidate"])) as db:
        db.execute(f"UPDATE {REPORT_TABLES[1]} SET patient_id = ?", [key])
    with pytest.raises(ValueError, match="bill ownership is malformed"):
        _transport(case, "candidate")


def test_cache_inventory_rejects_duplicate_bill_key(raw_transport_case):
    case = raw_transport_case
    with duckdb.connect(str(case["paths"]["candidate"])) as db:
        db.execute(f"INSERT INTO {REPORT_TABLES[1]} SELECT * FROM {REPORT_TABLES[1]}")
    with pytest.raises(ValueError, match="Malformed or duplicate"):
        _transport(case, "candidate")


def _project(case, raw, *, code_sha=None):
    provenance = case["pair"]["candidate"]["tables"][REPORT_TABLES[0]]["P1"]["data_source"]
    worker = {**case["worker"], "expected_code_sha": code_sha or case["code_sha"]}
    return rehearsal.project_report_transport(
        raw, provenance, **worker,
        cache_sha256=rehearsal._candidate_db_hash(case["paths"]["candidate"]),
        build_id="candidate-build", contract="wavea-evidence-v2",
    )


@pytest.mark.parametrize("fault", [
    "unknown_path", "noncanonical_patient", "noncanonical_claim", "foreign_patient",
    "foreign_claim", "foreign_scope", "claim_type", "scope_type", "orphan_bill",
])
def test_actual_source_worker_rejects_unowned_or_aliased_bill_transport(raw_transport_case, fault):
    case = raw_transport_case
    raw = {
        PATIENT_PATH: copy.deepcopy(case["pair"]["candidate"]["tables"][REPORT_TABLES[0]]["P1"]),
        BILL_PATH: copy.deepcopy(case["pair"]["candidate"]["tables"][REPORT_TABLES[1]]["P1::C1"]),
    }
    if fault == "unknown_path":
        raw[BILL_PATH + "/extra"] = raw.pop(BILL_PATH)
    elif fault == "noncanonical_patient":
        raw["/api/billing-report/P%31/bills/C1"] = raw.pop(BILL_PATH)
    elif fault == "noncanonical_claim":
        raw["/api/billing-report/P1/bills/C%31"] = raw.pop(BILL_PATH)
    elif fault == "orphan_bill":
        del raw[PATIENT_PATH]
    else:
        field, value = {
            "foreign_patient": ("patient_id", "foreign-patient"),
            "foreign_claim": ("claim_id", "foreign-claim"),
            "foreign_scope": ("scope", "patient"),
            "claim_type": ("claim_id", 1),
            "scope_type": ("scope", True),
        }[fault]
        raw[BILL_PATH][field] = value
    with pytest.raises(ValueError, match="Pinned isolated report serialization failed"):
        _project(case, raw)


@pytest.mark.parametrize("fault", ["claim", "scope", "missing_bill", "path_alias"])
def test_http_observation_cannot_change_exact_source_projected_bill(raw_transport_case, fault):
    case = raw_transport_case
    old, new = (_transport(case, side) for side in ("baseline", "candidate"))
    reports = new.draft_reports
    if fault == "claim":
        reports[BILL_PATH]["claim_id"] = "foreign-claim"
    elif fault == "scope":
        reports[BILL_PATH]["scope"] = "patient"
    elif fault == "missing_bill":
        del reports[BILL_PATH]
    else:
        reports["/api/billing-report/P1/bills/C%31"] = reports.pop(BILL_PATH)
    with pytest.raises(ValueError, match="inventory differs|Observed HTTP differs"):
        _compare(case, old, new, observed_new=reports)


def test_actual_transport_rejects_coherently_rehashed_raw_and_dto_forgery(raw_transport_case):
    case = raw_transport_case
    package = _transport(case, "candidate")
    encoded = {}
    binding = package.evidence
    for name in ("raw", "complete", "draft"):
        reports = getattr(package, name + "_reports")
        reports[BILL_PATH]["total_recoverable_try"] = 0.0
        encoded[name] = json.dumps(reports, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        binding[name + "_sha256"] = hashlib.sha256(encoded[name].encode()).hexdigest()
    forged = replace(package, _raw_json=encoded["raw"], _complete_json=encoded["complete"],
                     _draft_json=encoded["draft"], _binding_json=json.dumps(binding, sort_keys=True))
    with pytest.raises(ValueError, match="not generated by pinned source"):
        forged.validate()


def test_actual_transport_rechecks_its_pinned_source_after_projection(raw_transport_case):
    case = raw_transport_case
    package = _transport(case, "candidate")
    schema = case["repository"] / "src/bilun/api/schemas.py"
    schema.write_bytes(schema.read_bytes() + b"\n# Public uncommitted source mutation.\n")
    with pytest.raises(ValueError, match="differs from retained Git bytes"):
        package.validate()


def test_source_worker_rejects_pinned_but_changed_bill_route_assignments(raw_transport_case):
    case = raw_transport_case
    route = case["repository"] / "src/bilun/api/routes/billing.py"
    source = route.read_text()
    target = 'payload["scope"] = "bill"'
    assert source.count(target) == 1
    route.write_text(source.replace(target, 'payload["scope"] = "unreviewed"'))
    code_sha = fixture_git_commit(case["repository"])
    # The changed public source really matches its Git identity. Failure must be
    # the unsupported route projection, rather than an invented source SHA.
    rehearsal._source_binding(case["repository"], code_sha)
    raw = {
        PATIENT_PATH: copy.deepcopy(case["pair"]["candidate"]["tables"][REPORT_TABLES[0]]["P1"]),
        BILL_PATH: copy.deepcopy(case["pair"]["candidate"]["tables"][REPORT_TABLES[1]]["P1::C1"]),
    }
    with pytest.raises(ValueError, match="Pinned isolated report serialization failed"):
        _project(case, raw, code_sha=code_sha)


def test_source_worker_rejects_pinned_but_repeated_bill_route_identity(raw_transport_case):
    case = raw_transport_case
    route = case["repository"] / "src/bilun/api/routes/billing.py"
    tree = ast.parse(route.read_text())
    bill_route = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name == "get_bill_billing_report")
    cache_hit = next(node for node in ast.walk(bill_route)
                     if isinstance(node, ast.If) and ast.unparse(node.test) == "report is not None")
    bill_route.body.append(copy.deepcopy(cache_hit))
    route.write_text(ast.unparse(tree) + "\n")
    code_sha = fixture_git_commit(case["repository"])
    rehearsal._source_binding(case["repository"], code_sha)
    raw = {
        PATIENT_PATH: copy.deepcopy(case["pair"]["candidate"]["tables"][REPORT_TABLES[0]]["P1"]),
        BILL_PATH: copy.deepcopy(case["pair"]["candidate"]["tables"][REPORT_TABLES[1]]["P1::C1"]),
    }
    with pytest.raises(ValueError, match="Pinned isolated report serialization failed"):
        _project(case, raw, code_sha=code_sha)
