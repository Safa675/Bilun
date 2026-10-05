"""Independent public fixtures for the explicit 499 to final 3d29 profile.

These tests use authored public projections and synthetic Git histories. They
do not read retained patient caches or issue a production admission receipt.
The wrapper tests replace only the strace child; Git and read-trace gates run.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from scripts.deploy import verify_final_source_refresh_transition as final
from scripts.deploy import verify_source_refresh_transition as frozen
from scripts.deploy import issue_wavea_activation as issuer
from scripts.deploy import prepare_single_vps_release as preparation
from scripts.deploy import rehearse_wavea_same_port as rehearsal
from scripts.deploy import verify_candidate_semantics as semantics
from scripts.deploy.verify_private_rehearsal import verify_private_rehearsal
from tests.integration.deploy import test_signed_transition_startup as signed_startup
from tests.integration.deploy.test_signed_transition_startup import signed_bundle as signed_bundle
from tests.unit.deploy.test_issue_wavea_activation import _issuer_transition_fixture
from tests.unit.deploy.test_prepare_single_vps_release import machine as machine
from tests.unit.deploy.test_same_port_rehearsal import (
    fabricated_transport, fixture_rehearsal, private_json, sealed_rehearsal,
)
from tests.unit.deploy.test_verify_candidate_semantics import _current_fixture
from tests.unit.deploy.test_source_refresh_transition import (
    _git,
    _public_projection_pair,
    _report as _old_report,
    source_projection_wrapper_case as source_projection_wrapper_case,
)

# Deliberately authored here rather than obtained from the verifier inventory.
TABLES = (
    "patient_billing_report_rows", "patient_detail_cache", "patient_outcome_base",
    "patient_bill_billing_report_rows", "cohort_compliance_index",
    "cohort_optimization_summary", "patient_alerts_summary", "cohort_recovery_summary",
    "cohort_sut_summary", "validation_payload", "patient_meta", "cohort_sut_exposure",
    "patient_alerts_payload", "patient_diagnoses", "patient_alert_rows",
    "patient_billing_reports", "wavea_evidence_detail", "wavea_bill_evidence_detail",
    "wavea_evidence_index",
)
STRICT_TABLES = (
    "patient_detail_cache", "patient_outcome_base", "cohort_optimization_summary",
    "patient_alerts_summary", "cohort_recovery_summary", "cohort_sut_summary",
    "validation_payload", "patient_meta", "cohort_sut_exposure", "patient_alerts_payload",
    "patient_diagnoses", "patient_alert_rows", "patient_billing_reports",
)
OWNED_TABLES = (
    "patient_billing_report_rows", "patient_bill_billing_report_rows",
    "wavea_evidence_detail", "wavea_bill_evidence_detail", "wavea_evidence_index",
    "cohort_compliance_index",
)
CONTRACT = "bilun-source-refresh-499-3d29-v1"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _request(sha="a" * 40):
    return {"contract": CONTRACT, "expected_candidate_sha": sha, "expected_verifier_sha": sha}


def _commit(checkout, message):
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-q", "-m", message)
    return _git(checkout, "rev-parse", "HEAD")


def test_final_request_is_explicit_and_old_profiles_remain_separate():
    assert final.validate_transition_request(None) is None
    assert final.validate_transition_request(_request()) == _request()
    old = {"contract": frozen.TRANSITION_CONTRACT,
           "expected_candidate_sha": "b" * 40, "expected_verifier_sha": "b" * 40}
    assert final.validate_transition_request(old) == frozen.validate_transition_request(old)
    with pytest.raises(ValueError):
        frozen.validate_transition_request(_request())
    assert final.PRODUCT_ANCHOR_SHA == "3d29a1fefa2b89f9a8d38e2dccab6fe2285c861e"
    assert frozen.PRODUCT_ANCHOR_SHA == "d0337600f45a17aa635f6bbe8d584095a6f3e82e"


@pytest.mark.parametrize("mutation", [
    "unknown", "partial", "extra", "candidate_none", "candidate_short", "verifier_wrong",
    "candidate_upper", "candidate_bool", "verifier_none",
])
def test_request_rejects_unknown_partial_or_unbound_pins(mutation):
    request = _request()
    if mutation == "unknown":
        request["contract"] = "future-unreviewed-profile"
    elif mutation == "partial":
        request.pop("expected_verifier_sha")
    elif mutation == "extra":
        request["future_permission"] = True
    elif mutation == "candidate_none":
        request["expected_candidate_sha"] = None
    elif mutation == "candidate_short":
        request["expected_candidate_sha"] = "a" * 39
    elif mutation == "candidate_upper":
        request["expected_candidate_sha"] = "A" * 40
    elif mutation == "candidate_bool":
        request["expected_candidate_sha"] = True
    elif mutation == "verifier_none":
        request["expected_verifier_sha"] = None
    else:
        request["expected_verifier_sha"] = "b" * 40
    with pytest.raises(ValueError):
        final.validate_transition_request(request)


@pytest.mark.parametrize("table", TABLES)
def test_no_opt_in_keeps_every_table_type_exact_and_detached(table):
    value = {"money": 0.0, "null": None, "flag": False, "order": ["b", "a"],
             "selected_rule_id": "public.unrelated", "data_source": {"mode": "synthetic_demo"}}
    before = copy.deepcopy(value)
    with pytest.raises(ValueError):
        final.normalize_transition_content(table, value, side="candidate", proof=None)
    assert value == before


@pytest.fixture
def final_wrapper(source_projection_wrapper_case, monkeypatch):
    case = source_projection_wrapper_case
    # The child response is public; the real wrapper must require the new key.
    case["output"] = {**copy.deepcopy(case["expected"]), "source_witnesses": {}}
    case["expected"] = copy.deepcopy(case["output"])
    original_validator = final.validate_runtime_read_trace
    child_spy = final.subprocess.run
    case["trace_transform"] = None
    case["runtime_snapshots"] = []
    case["runtime_snapshot_mutation"] = None
    os_bindings = {literal: {"path": literal, "file_type": "regular_file", "uid": 0, "gid": 0,
        "mode": 0o644, "size_bytes": 12, "device": 1, "inode": index + 1, "nlink": 1,
        "mtime_ns": 100, "ctime_ns": 100, "sha256": _digest({"public_os_file": literal})}
        for index, literal in enumerate(("/etc/locale.alias", "/opt/Bilun/.venv/pyvenv.cfg"))}

    def snapshot():
        # A metadata seam for these VPS-only paths; descriptor behavior has
        # separate public-file tests below. This is not a VPS observation.
        value = copy.deepcopy(os_bindings)
        if case["runtime_snapshots"] and case["runtime_snapshot_mutation"] is not None:
            field, replacement = case["runtime_snapshot_mutation"]
            value["/etc/locale.alias"][field] = replacement
        case["runtime_snapshots"].append(value)
        return value

    def run(command, **kwargs):
        result = child_spy(command, **kwargs)
        if command[0] == "strace" and case["trace_transform"] is not None:
            trace = Path(command[command.index("-o") + 1])
            trace.write_text(case["trace_transform"](trace.read_text()), encoding="utf-8")
        return result

    def validate(trace, **kwargs):
        case["trace_calls"].append(kwargs.copy())
        return original_validator(trace, **kwargs)

    monkeypatch.setattr(final, "validate_runtime_read_trace", validate)
    monkeypatch.setattr(final.subprocess, "run", run)
    monkeypatch.setattr(final, "_snapshot_runtime_files", snapshot)

    def invoke():
        return final._replay_projection(case["checkout"], case["claims"], case["clean"],
            "synthetic_demo", case["executable"], roster=case["roster"],
            dependency_roots=case["dependencies"])

    case["invoke"] = invoke
    return case


@pytest.mark.parametrize("dependency_kind", ["file", "directory", "file_directory", "directory_file", "alias"])
def test_final_wrapper_forwards_runtime_dependencies_in_order(final_wrapper, dependency_kind):
    case = final_wrapper
    deps, reads = {
        "file": ((case["file"],), [case["file"]]),
        "directory": ((case["directory"],), [case["directory_module"]]),
        "file_directory": ((case["file"], case["directory"]), [case["file"], case["directory_module"]]),
        "directory_file": ((case["directory"], case["file"]), [case["directory_module"], case["file"]]),
        "alias": ((case["alias"],), [case["file"]]),
    }[dependency_kind]
    case["dependencies"], case["reads"] = deps, reads
    assert case["invoke"]() == case["expected"]
    command, options = case["worker_calls"][0]
    assert command[-5:] == [str(case["claims"]), str(case["clean"]), "synthetic_demo",
                           json.dumps([str(path) for path in deps]), "candidate"]
    assert command[command.index("-c") + 1] == final._WORKER
    assert options["cwd"] == case["checkout"]
    assert options["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert len(case["trace_calls"]) == 1
    assert case["trace_calls"][0]["dependency_roots"] == deps


@pytest.mark.parametrize("filename", [".env", ".env.production", "cache.duckdb", "cache.db", "cache.sqlite3-wal"])
def test_final_wrapper_rejects_secret_or_database_even_if_explicitly_listed(final_wrapper, filename):
    case = final_wrapper
    forbidden = case["runtime"] / filename
    forbidden.write_text("public synthetic forbidden file")
    case["dependencies"], case["reads"] = (forbidden,), [forbidden]
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("flag", ["O_RDWR", "O_WRONLY", "O_RDONLY|O_CREAT", "O_RDONLY|O_TRUNC", "O_RDONLY|O_APPEND"])
def test_final_readonly_producer_cannot_write_even_an_explicit_runtime_dependency(final_wrapper, flag):
    case = final_wrapper
    case["trace_transform"] = lambda text: text.replace("O_RDONLY)", flag + ")")
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("path,flag", [
    ("/etc/bilun-public-unknown-config", "O_RDONLY"),
    ("/tmp/public-unlisted-directory", "O_RDONLY|O_DIRECTORY"),
    ("/root/public-fixture.key", "O_RDONLY"),
    ("/tmp/public-cache.wal", "O_RDONLY"),
    ("/dev/urandom", "O_RDONLY"),
])
def test_final_trace_rejects_unknown_os_directory_key_and_wal_reads(final_wrapper, path, flag):
    case = final_wrapper
    case["trace_transform"] = lambda text: text.replace("+++ exited with 0 +++",
        f'openat(AT_FDCWD, "public", {flag}) = 50<{path}>\n+++ exited with 0 +++')
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("path", [
    "/etc/ld.so.cache", "/dev/null", "/usr/lib/public.so.1", "/lib/public.so.1",
    "/usr/share/locale/en/LC_MESSAGES/public.mo", "/proc/123/status", "/proc/123/stat", "/proc/123/statm",
    "/etc/locale.alias", "/opt/Bilun/.venv/pyvenv.cfg",
])
def test_final_wrapper_preserves_reviewed_startup_os_reads_with_exact_two_file_binding(final_wrapper, path):
    case = final_wrapper
    case["trace_transform"] = lambda text: text.replace("+++ exited with 0 +++",
        f'openat(AT_FDCWD, "public", O_RDONLY) = 50<{path}>\n+++ exited with 0 +++')
    assert case["invoke"]() == case["expected"]
    assert len(case["runtime_snapshots"]) >= 3
    assert all(value == case["runtime_snapshots"][0] for value in case["runtime_snapshots"])


@pytest.mark.parametrize("field,replacement", [
    ("sha256", "f" * 64), ("mode", 0o666), ("uid", 1), ("size_bytes", 13),
    ("inode", 999), ("mtime_ns", 101), ("file_type", "symlink"),
])
def test_runtime_os_file_change_between_child_and_final_binding_is_rejected(final_wrapper, field, replacement):
    case = final_wrapper
    case["runtime_snapshot_mutation"] = field, replacement
    with pytest.raises(ValueError):
        case["invoke"]()


def test_explicit_runtime_dependency_byte_mutation_during_child_is_rejected(final_wrapper):
    case = final_wrapper
    def mutate(text):
        case["file"].write_text('{"public_runtime_fixture": false}\n')
        return text
    case["trace_transform"] = mutate
    with pytest.raises(ValueError):
        case["invoke"]()


class _StatView:
    def __init__(self, observed, **overrides):
        self.observed, self.overrides = observed, overrides
    def __getattr__(self, name):
        return self.overrides.get(name, getattr(self.observed, name))
    def __getitem__(self, key):
        return self.observed[key]


@pytest.fixture
def public_os_file(tmp_path, monkeypatch):
    path = tmp_path / "public-os-metadata.cfg"
    path.write_bytes(b"public immutable runtime fixture\n")
    path.chmod(0o644)
    monkeypatch.setattr(final, "RUNTIME_FILE_PATHS", (str(path),))
    original_lstat, original_fstat = final.os.lstat, final.os.fstat
    case = {"path": path, "uid": 0, "fstat_mutation": None, "fstats": 0}
    def lstat(value, *args, **kwargs):
        observed = original_lstat(value, *args, **kwargs)
        return _StatView(observed, st_uid=case["uid"]) if str(value) == str(path) else observed
    def fstat(fd):
        observed = original_fstat(fd)
        case["fstats"] += 1
        overrides = {"st_uid": case["uid"]}
        if case["fstat_mutation"] is not None:
            key, value = case["fstat_mutation"]
            overrides[key] = value
        return _StatView(observed, **overrides)
    monkeypatch.setattr(final.os, "lstat", lstat)
    monkeypatch.setattr(final.os, "fstat", fstat)
    return case


def test_runtime_descriptor_snapshot_hashes_real_public_bytes_with_metadata_seam(public_os_file):
    case = public_os_file
    value = final._snapshot_runtime_file(str(case["path"]))
    assert value["sha256"] == hashlib.sha256(b"public immutable runtime fixture\n").hexdigest()
    assert value["size_bytes"] == len(b"public immutable runtime fixture\n")
    assert value["uid"] == 0 and value["mode"] == 0o644
    assert case["fstats"] == 2


@pytest.mark.parametrize("mutation", ["foreign_literal", "wrong_uid", "group_write", "world_write", "symlink", "directory", "fd_size", "fd_inode"])
def test_runtime_descriptor_snapshot_rejects_unbound_owner_type_mode_or_descriptor(public_os_file, mutation):
    case = public_os_file
    path = case["path"]
    literal = str(path)
    if mutation == "foreign_literal":
        literal += ".unreviewed"
    elif mutation == "wrong_uid":
        case["uid"] = 1000
    elif mutation in {"group_write", "world_write"}:
        path.chmod(0o664 if mutation == "group_write" else 0o646)
    elif mutation == "symlink":
        target = path.with_suffix(".target")
        path.rename(target)
        path.symlink_to(target)
    elif mutation == "directory":
        path.unlink()
        path.mkdir()
    else:
        key = "st_size" if mutation == "fd_size" else "st_ino"
        case["fstat_mutation"] = key, getattr(path.stat(), key) + 1
    with pytest.raises(ValueError):
        final._snapshot_runtime_file(literal)


@pytest.mark.parametrize("boundary", ["claims", "clean", "checkout", "foreign_source", "unlisted"])
def test_final_wrapper_enforces_real_read_trace_ownership(final_wrapper, boundary):
    case = final_wrapper
    if boundary in {"claims", "clean", "checkout"}:
        case["dependencies"] = (case[boundary],)
    else:
        path = case["runtime"] / ("src/foreign.py" if boundary == "foreign_source" else "unlisted.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("PUBLIC = True")
        case["extra_reads"] = [path]
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("invalid", ["missing", "relative", "empty", "fifo", "bad_child", "missing_witness", "extra_key"])
def test_final_wrapper_rejects_bad_runtime_or_child_contract(final_wrapper, invalid):
    case = final_wrapper
    if invalid == "missing":
        case["dependencies"] = (case["runtime"] / "absent.json",)
    elif invalid == "relative":
        case["dependencies"] = (Path("public-runtime.json"),)
    elif invalid == "empty":
        case["dependencies"] = ()
    elif invalid == "fifo":
        import os
        path = case["runtime"] / "fifo"
        os.mkfifo(path)
        case["dependencies"] = (path,)
    elif invalid == "bad_child":
        case["returncode"] = 1
    elif invalid == "missing_witness":
        case["output"].pop("source_witnesses")
    else:
        case["output"]["future_permission"] = True
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.fixture
def public_history(tmp_path, monkeypatch):
    checkout = tmp_path / "public-git"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.email", "public@example.invalid")
    _git(checkout, "config", "user.name", "Public fixture")
    frozen_paths = ["scripts/deploy/verify_source_refresh_transition.py",
                    "tests/unit/deploy/test_source_refresh_transition.py"]
    for path in frozen_paths:
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("FROZEN = True\n")
    product = checkout / "data/public_product.json"
    product.parent.mkdir(parents=True)
    product.write_text('{"version": 0}')
    baseline = _commit(checkout, "public baseline")
    product.write_text('{"version": 1}')
    first = _commit(checkout, "public source product")
    _git(checkout, "checkout", "-q", "-b", "old-tooling")
    (checkout / frozen_paths[0]).write_text("FROZEN = 'old seed tooling'\n")
    old_tool = _commit(checkout, "frozen old tooling")
    _git(checkout, "checkout", "-q", "-b", "product", first)
    product.write_text('{"version": 2}')
    middle = _commit(checkout, "public followup product")
    product.write_text('{"version": 3}')
    anchor = _commit(checkout, "public copay product")
    _git(checkout, "checkout", "-q", "old-tooling")
    _git(checkout, "merge", "--no-ff", "-m", "reviewed public integration seed", anchor)
    seed = _git(checkout, "rev-parse", "HEAD")
    tree = lambda sha: _git(checkout, "rev-parse", sha + "^{tree}")
    for key, value in {
        "BASELINE_CODE_SHA": baseline, "BASELINE_TREE": tree(baseline),
        "PRODUCT_ANCHOR_SHA": anchor, "PRODUCT_ANCHOR_TREE": tree(anchor),
        "INTEGRATION_SEED_SHA": seed, "INTEGRATION_SEED_TREE": tree(seed),
        "SEED_PARENTS": (old_tool, anchor),
        "PRODUCT_HISTORY": ((first, tree(first), baseline), (middle, tree(middle), first),
                            (anchor, tree(anchor), middle)),
    }.items():
        monkeypatch.setattr(final, key, value)
    new_tool = checkout / "scripts/deploy/verify_final_source_refresh_transition.py"
    new_tool.write_text("PUBLIC = True\n")
    candidate = _commit(checkout, "public new tooling")
    return {"checkout": checkout, "product": product, "candidate": candidate,
            "seed": seed, "anchor": anchor, "new_tool": new_tool, "frozen_paths": frozen_paths}


def test_only_reviewed_seed_linear_tooling_descendant_is_admitted(public_history):
    case = public_history
    result = final._verify_candidate_history(case["checkout"], case["candidate"])
    assert result["integration_seed_sha"] == case["seed"]
    assert result["product_anchor_sha"] == case["anchor"]
    assert result["descendant_commits"] == [case["candidate"]]
    assert result["authorized_changed_paths"] == ["scripts/deploy/verify_final_source_refresh_transition.py"]


@pytest.mark.parametrize("mutation", [
    "wrong_head", "seed_itself", "wrong_seed_tree", "wrong_seed_parents", "product",
    "product_then_revert", "frozen_verifier", "frozen_test", "unauthorized_asset", "merge",
])
def test_final_history_rejects_unknown_product_ancestry_or_intermediate_edit(public_history, monkeypatch, mutation):
    case = public_history
    checkout, candidate = case["checkout"], case["candidate"]
    if mutation == "wrong_head":
        candidate = "f" * 40
    elif mutation == "seed_itself":
        _git(checkout, "checkout", "-q", case["seed"])
        candidate = case["seed"]
    elif mutation == "wrong_seed_tree":
        monkeypatch.setattr(final, "INTEGRATION_SEED_TREE", "f" * 40)
    elif mutation == "wrong_seed_parents":
        monkeypatch.setattr(final, "SEED_PARENTS", tuple(reversed(final.SEED_PARENTS)))
    elif mutation in {"product", "product_then_revert"}:
        old = case["product"].read_bytes()
        case["product"].write_text('{"version": 99}')
        candidate = _commit(checkout, "unreviewed product change")
        if mutation.endswith("revert"):
            case["product"].write_bytes(old)
            candidate = _commit(checkout, "reverted product does not erase history")
    elif mutation in {"frozen_verifier", "frozen_test"}:
        path = case["frozen_paths"][0 if mutation == "frozen_verifier" else 1]
        (checkout / path).write_text("UNREVIEWED = True\n")
        candidate = _commit(checkout, "frozen profile mutation")
    elif mutation == "unauthorized_asset":
        (checkout / "data/extra.json").write_text("{}")
        candidate = _commit(checkout, "unreviewed extra asset")
    else:
        _git(checkout, "checkout", "-q", "-b", "side", case["seed"])
        (checkout / "scripts/deploy/verify_candidate_semantics.py").write_text("SIDE = True\n")
        side = _commit(checkout, "side tooling")
        _git(checkout, "checkout", "-q", "old-tooling")
        _git(checkout, "merge", "--no-ff", "-m", "unknown later merge", side)
        candidate = _git(checkout, "rev-parse", "HEAD")
    with pytest.raises(ValueError):
        final._verify_candidate_history(checkout, candidate)


def _copay():
    frames = {}
    for name, keys in (
        ("sut_clause_coverage.parquet", ["clause_id"]),
        ("sut_coverage_by_rule.parquet", ["primary_rule_id", "primary_rule_category", "coverage_status"]),
        ("sut_coverage_by_section.parquet", ["section_id", "section_title"]),
        ("sut_registry_coverage.parquet", ["rule_id"]),
    ):
        frames[name] = {"columns": keys, "schema": dict.fromkeys(keys, "String"),
                        "row_count": 1, "key_fields": keys, "rows_sha256": _digest({"public": name})}
    return {"manifest_sha256": _digest({"public": "canonical copay manifest"}),
            "frames": frames, "evidence_sha256": _digest({"public": "coverage evidence"}),
            "artifact_stats_sha256": _digest({"public": "immutable source file stats"}),
            "public_summary": {"meta": {"artifacts_available": True}},
            "canonical_manifest_verified": True, "fresh_coverage_verified": True}


def _followup_row(drug, line, rule, *, measured):
    receipt = {
        "kind": "route", "family": "followup", "claim_id": "C1", "drug_claim_line_id": line,
        "evaluator_version": "followup.atomic.v2.2026-10-03", "execution_scope": "public-scope-" + line,
        "route_id": "followup.source_date", "status": "blocked_source",
        "reasons": ["unsupported_source_date"],
        "observed_input_fields": ["drug_claim_date", "drug_name"], "missing_input_fields": [],
    }
    outcome = {
        "constraint_set": "followup_source_constraints", "criterion_status": "not_evaluated",
        "missing_inputs": ["verified_source_for_service_date"], "checks": [],
        "source_refs": ["public-reviewed-followup-source"], "sut_section": rule.split(".clinical")[0],
        "clinical_eligibility_complete": False, "verification_status": "ai_generated_pending_review",
        "source_authority": {"status": "uncovered_service_date", "service_date": "2026-10-06",
                             "reviewed_through": "2026-10-05", "clinical_eligibility_complete": False},
    }
    if measured:
        # Authored from this single blocked route, not from the runtime builder.
        summary = {
            "schema_version": 1, "available": True, "instrumented_families": ["followup"],
            "input_facts_available_count": 2, "input_facts_missing_count": 0,
            "predicate_attempted_count": 0, "predicate_evaluated_count": 0,
            "predicate_passed_count": 0, "predicate_failed_count": 0, "predicate_missing_inputs_count": 0,
            "routes_blocked_source_count": 1, "routes_blocked_inputs_count": 0, "routes_skipped_count": 0,
            "source_metrics_available": True, "source_unavailable_reason": None,
            "unresolved_source_ref_count": 0, "source_clauses_touched_count": 0,
            "complete_clause_mapping_available": False,
            "complete_clause_mapping_unavailable_reason": "No reviewed complete-clause predicate mapping supplied.",
            "source_clauses_fully_evaluated_count": None, "source_clause_ids": [],
            "fully_evaluated_source_clause_ids": None, "receipt_count": 1,
            "receipt_sha256": _digest([{k: v for k, v in receipt.items() if k != "execution_scope"}]),
            "clinical_eligibility_complete": False,
        }
        assert len(summary) == 25
        outcome["runtime_coverage"] = summary
    return {"patient_id": "P1", "claim_id": "C1", "drug_claim_line_id": line, "drug_name": drug,
            "source_rule_ids": [rule], "constraint_set": "followup_source_constraints",
            "outcome": outcome, "receipts": [receipt] if measured else []}


def _public_final_pair():
    old, new = _public_projection_pair()
    rules = [
        {"rule_id": "4.2.57.clinical_16_week_response", "drug_names": ["dupilumab"],
         "clinical_constraint_drugs": ["dupilumab"], "clinical_constraint_set": "followup_source_constraints"},
        {"rule_id": "4.2.46.clinical_annual_reassessment", "drug_names": ["nintedanib"],
         "clinical_constraint_drugs": ["nintedanib"], "clinical_constraint_set": "followup_source_constraints"},
    ]
    for projection, measured in ((old, False), (new, True)):
        witnesses = [
            _followup_row("dupilumab", "L-DUP", rules[0]["rule_id"], measured=measured),
            _followup_row("nintedanib", "L-NINT", rules[1]["rule_id"], measured=measured),
        ]
        for table, key in (("patient_billing_report_rows", "P1"),
                           ("patient_bill_billing_report_rows", "P1::C1")):
            report = projection["tables"][table][key]
            report["drug_indication"]["findings"] = [{
                "patient_id": "P1", "claim_id": "C1", "drug_claim_line_id": row["drug_claim_line_id"],
                "drug_name": row["drug_name"], "selected_rule_id": row["source_rule_ids"][0],
                "savings_try": None, "risk_amount": None, "evaluation_status": "review_required",
                "clinical_restrictions": [copy.deepcopy(row["outcome"])],
            } for row in witnesses]
        # The index is also a source projection, including null monetary fields.
        projection["tables"]["cohort_compliance_index"] = {
            "n_patients": 1, "n_findings": 2, "n_patients_with_findings": 1,
            "billed_at_risk_try": 0.0, "artifacts_available": True,
            "rows": [{"patient_id": "P1", "claim_id": "C1",
                      "drug_claim_line_id": row["drug_claim_line_id"], "drug_name": row["drug_name"],
                      "surface": "drug_indication", "billed_try": None,
                      "selected_rule_id": row["source_rule_ids"][0],
                      "clinical_restrictions": [copy.deepcopy(row["outcome"])]} for row in witnesses],
            "by_surface": {"drug_indication": {"n": 2, "billed_try": None, "n_patients": 1}},
            "claim_compliance": {"counts_by_patient": {"P1": {"evaluated": 0, "missing_inputs": 0, "unavailable": 0}},
                                 "details": [], "detail_limit": 20},
            "data_source": {"mode": "synthetic_demo", "is_synthetic": True,
                            "claim_source": "claims", "clinical_source": "clean"},
        }
        for table in STRICT_TABLES:
            row = {"patient_id": "P1", "claim_id": "C1", "public_surface": table,
                   "money": 0.0, "null": None, "flag": False, "order": ["a", "b"],
                   "selected_rule_id": "public.unrelated", "data_source": {"mode": "synthetic_demo",
                       "claim_source": "claims", "clinical_source": "clean"}}
            projection["tables"][table] = [row] if table in {
                "cohort_sut_summary", "validation_payload", "patient_meta", "cohort_sut_exposure",
                "patient_alerts_payload", "patient_diagnoses", "patient_alert_rows", "patient_billing_reports",
            } else {"P1": row}
        projection["source_witnesses"] = {
            "followup": witnesses, "followup_rules": copy.deepcopy(rules),
            "followup_source_clauses": [{"clause_id": "CF000001", "section_id": "4.2.57",
                "clause_type": "fikra", "text": "Public authored normative source fixture.",
                "is_in_force": True, "is_heading": False, "is_amendment": False}],
            "copay": _copay(),
        }
    assert set(old["tables"]) == set(new["tables"]) == set(TABLES)
    return old, new


def test_full_nineteen_source_projections_allow_only_witnessed_neutral_annotations():
    old, new = _public_final_pair()
    before = copy.deepcopy((old, new))
    assert final._check_projection_pair(old, new) == {
        "changed_organ_evaluations": 6, "neutral_raw_rows": 6, "followup_line_count": 2,
        "source_projected_table_count": 19, "strict_table_count": 13,
    }
    assert (old, new) == before
    outcome = new["source_witnesses"]["followup"][0]["outcome"]
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["source_authority"]["status"] == "uncovered_service_date"
    assert outcome["runtime_coverage"]["predicate_attempted_count"] == 0
    assert outcome["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("table", STRICT_TABLES)
@pytest.mark.parametrize("field,value", [
    ("money", 0), ("money", None), ("null", 0.0), ("flag", 0), ("order", ["b", "a"]),
    ("selected_rule_id", "4.2.57.clinical_16_week_response"), ("data_source", {"mode": "real"}),
])
def test_all_thirteen_other_source_tables_keep_money_null_type_order_and_identity(table, field, value):
    old, new = _public_final_pair()
    rows = new["tables"][table]
    row = rows[0] if isinstance(rows, list) else rows["P1"]
    row[field] = value
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


@pytest.mark.parametrize("table", TABLES)
def test_no_source_table_may_be_dropped(table):
    old, new = _public_final_pair()
    new["tables"].pop(table)
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("available", 1), ("instrumented_families", ["renal"]),
    ("input_facts_available_count", 2.0), ("input_facts_missing_count", None),
    ("predicate_attempted_count", 1), ("predicate_evaluated_count", 1),
    ("predicate_passed_count", 1), ("predicate_failed_count", 1), ("predicate_missing_inputs_count", 1),
    ("routes_blocked_source_count", 0), ("routes_blocked_inputs_count", 1), ("routes_skipped_count", 1),
    ("source_metrics_available", 1), ("source_unavailable_reason", "stale"),
    ("unresolved_source_ref_count", 1), ("source_clauses_touched_count", 1),
    ("complete_clause_mapping_available", True), ("complete_clause_mapping_unavailable_reason", None),
    ("source_clauses_fully_evaluated_count", 0), ("source_clause_ids", ["CF000099"]),
    ("fully_evaluated_source_clause_ids", []), ("receipt_count", 2),
    ("receipt_sha256", "f" * 64), ("clinical_eligibility_complete", 0),
])
def test_every_measured_summary_field_is_independently_typed_and_receipt_derived(field, value):
    _, new = _public_final_pair()
    new["source_witnesses"]["followup"][0]["outcome"]["runtime_coverage"][field] = value
    with pytest.raises(ValueError):
        final._check_source_witnesses(new, candidate=True)


@pytest.mark.parametrize("mutation", [
    "patient", "claim", "line", "drug", "rule", "constraint", "foreign_family", "foreign_claim",
    "foreign_line", "wrong_version", "duplicate_line", "duplicate_receipt", "mixed_scope",
    "complete_clause", "receipt_extra", "summary_extra", "empty_receipts", "baseline_measurement",
    "clinical_true", "source_rule_extra", "source_rules_duplicate",
])
def test_receipts_and_summaries_require_exact_source_and_execution_ownership(mutation):
    old, new = _public_final_pair()
    source = new["source_witnesses"]
    row = source["followup"][0]
    receipt = row["receipts"][0]
    if mutation in {"patient", "claim", "line", "drug", "rule", "constraint"}:
        field = {"patient": "patient_id", "claim": "claim_id", "line": "drug_claim_line_id",
                 "drug": "drug_name", "rule": "source_rule_ids", "constraint": "constraint_set"}[mutation]
        row[field] = ["4.2.46.clinical_annual_reassessment"] if mutation == "rule" else "foreign"
    elif mutation in {"foreign_family", "foreign_claim", "foreign_line", "wrong_version"}:
        field = {"foreign_family": "family", "foreign_claim": "claim_id", "foreign_line": "drug_claim_line_id",
                 "wrong_version": "evaluator_version"}[mutation]
        receipt[field] = "foreign"
    elif mutation == "duplicate_line":
        source["followup"].append(copy.deepcopy(row))
    elif mutation in {"duplicate_receipt", "mixed_scope"}:
        extra = copy.deepcopy(receipt)
        if mutation == "mixed_scope":
            extra.update(route_id="another.route", execution_scope="foreign-scope")
        row["receipts"].append(extra)
    elif mutation == "complete_clause":
        receipt.update(kind="predicate", predicate_id="unsupported.complete", source_refs=["CF000001"],
                       clause_predicate_complete=True)
        receipt.pop("route_id")
        receipt.pop("reasons")
    elif mutation == "receipt_extra":
        receipt["patient_value"] = "not permitted"
    elif mutation == "summary_extra":
        row["outcome"]["runtime_coverage"]["future_counter"] = 0
    elif mutation == "empty_receipts":
        row["receipts"] = []
    elif mutation == "baseline_measurement":
        old["source_witnesses"]["followup"][0] = copy.deepcopy(row)
    elif mutation == "clinical_true":
        row["outcome"]["clinical_eligibility_complete"] = True
    elif mutation == "source_rule_extra":
        source["followup_rules"].append(copy.deepcopy(source["followup_rules"][0]))
    else:
        source["followup_rules"][1] = copy.deepcopy(source["followup_rules"][0])
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


@pytest.mark.parametrize("field,value", [
    ("criterion_status", "criterion_clear"), ("checks", [{"passed": True}]),
    ("missing_inputs", []), ("source_refs", ["unreviewed-source"]),
    ("verification_status", "primary_verified"), ("sut_section", "4.2.99"),
    ("source_authority", {"status": "admitted", "service_date": "2026-10-06"}),
])
def test_source_review_window_and_all_clinical_outcome_fields_stay_unchanged(field, value):
    old, new = _public_final_pair()
    row = new["source_witnesses"]["followup"][0]
    row["outcome"][field] = value
    # Keep projected payload and witness coherent; pair comparison must still reject it.
    for table, key in (("patient_billing_report_rows", "P1"), ("patient_bill_billing_report_rows", "P1::C1")):
        new["tables"][table][key]["drug_indication"]["findings"][0]["clinical_restrictions"][0][field] = value
    new["tables"]["cohort_compliance_index"]["rows"][0]["clinical_restrictions"][0][field] = value
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


@pytest.mark.parametrize("table", ["patient_billing_report_rows", "patient_bill_billing_report_rows", "cohort_compliance_index"])
@pytest.mark.parametrize("mutation", ["wrong_owner", "wrong_summary", "money", "null", "rule", "order", "outside_restriction"])
def test_nested_metadata_permission_does_not_cover_other_fields_or_locations(table, mutation):
    old, new = _public_final_pair()
    root = new["tables"][table]
    rows = root["rows"] if table == "cohort_compliance_index" else root[next(iter(root))]["drug_indication"]["findings"]
    row = rows[0]
    if mutation == "wrong_owner":
        row["drug_claim_line_id"] = "foreign"
    elif mutation == "wrong_summary":
        row["clinical_restrictions"][0]["runtime_coverage"]["receipt_sha256"] = "f" * 64
    elif mutation == "money":
        row["billed_try" if table == "cohort_compliance_index" else "savings_try"] = 0.0
    elif mutation == "null":
        row["billed_try" if table == "cohort_compliance_index" else "risk_amount"] = False
    elif mutation == "rule":
        row["selected_rule_id"] = "public.unrelated"
    elif mutation == "order":
        rows.reverse()
    else:
        row["runtime_coverage"] = row["clinical_restrictions"][0].pop("runtime_coverage")
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


def test_coherent_unrelated_row_mutation_after_five_hundred_is_not_sampled():
    old, new = _public_final_pair()
    rows = [{"patient_id": "P1", "public_id": str(index), "money": None, "flag": False}
            for index in range(601)]
    old["tables"]["patient_billing_reports"] = copy.deepcopy(rows)
    new["tables"]["patient_billing_reports"] = copy.deepcopy(rows)
    new["tables"]["patient_billing_reports"][600]["money"] = 0.0
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


@pytest.mark.parametrize("mutation", [
    "missing_manifest", "deferred_upgrade", "stale_digest", "missing_frame", "duplicate_columns",
    "wrong_keys", "count_bool", "count_float", "count_zero", "schema_missing", "row_hash_short",
    "evidence_null", "artifact_stats_wrong_type", "summary_unavailable", "extra_field",
])
def test_copay_witness_requires_complete_fresh_typed_derivation(mutation):
    witness = _copay()
    frame = witness["frames"]["sut_clause_coverage.parquet"]
    if mutation == "missing_manifest":
        witness.pop("manifest_sha256")
    elif mutation == "deferred_upgrade":
        witness["canonical_manifest_verified"] = False
    elif mutation == "stale_digest":
        witness["fresh_coverage_verified"] = False
    elif mutation == "missing_frame":
        witness["frames"].pop("sut_registry_coverage.parquet")
    elif mutation == "duplicate_columns":
        frame["columns"] *= 2
    elif mutation == "wrong_keys":
        frame["key_fields"] = ["positional_id"]
    elif mutation.startswith("count_"):
        frame["row_count"] = {"count_bool": True, "count_float": 1.0, "count_zero": 0}[mutation]
    elif mutation == "schema_missing":
        frame["schema"] = {}
    elif mutation == "row_hash_short":
        frame["rows_sha256"] = "f" * 63
    elif mutation == "evidence_null":
        witness["evidence_sha256"] = None
    elif mutation == "artifact_stats_wrong_type":
        witness["artifact_stats_sha256"] = 0
    elif mutation == "summary_unavailable":
        witness["public_summary"]["meta"]["artifacts_available"] = False
    else:
        witness["defer_verification_until_after_upgrade"] = True
    with pytest.raises(ValueError):
        final._check_copay_witness(witness)


def _attested(value):
    if isinstance(value, list):
        return [_attested(row) for row in value]
    if not isinstance(value, dict):
        return value
    result = {key: _attested(row) for key, row in value.items()}
    if "data_source" in result:
        result["data_source"].update(claim_source="@attested_claim_inputs",
                                     clinical_source="@attested_clinical_inputs")
    return result


def _final_report(projections, candidate="a" * 40):
    report = _old_report(projections, candidate=candidate)
    report.update(contract=CONTRACT, status="final_source_refresh_transition_verified",
        followup_line_count=2, source_projected_table_count=19, strict_table_count=13,
        cache_comparison_contract="all19_own_source_exact_before_admission")
    report["history"].update(product_anchor_sha="3d29a1fefa2b89f9a8d38e2dccab6fe2285c861e",
        product_anchor_tree="5c1ee20b6b2817de41e7f2ca5fcec68a1bbfe121",
        integration_seed_sha="58e7a14294484de286bd6d98c677a10db8de800d",
        integration_seed_tree="d04625ecb21e92b7fd8bafa6d80fd893f227b620",
        product_closure_sha256=_digest({"public": "full product closure"}),
        authorized_changed_paths=["scripts/deploy/verify_final_source_refresh_transition.py"])
    files = {"scripts/deploy/verify_final_source_refresh_transition.py": "e" * 64,
             "scripts/deploy/verify_source_refresh_transition.py": "c" * 64}
    report["verifier"].update(files=files, source_sha256=_digest(files))
    source = report["source_intent"]
    report["source_intent"] = {
        "organ": source,
        "followup": {"rule_ids": ["4.2.46.clinical_annual_reassessment", "4.2.57.clinical_16_week_response"],
            "constraint_set": "followup_source_constraints", "evaluator_version": "followup.atomic.v2.2026-10-03",
            "summary_fields": sorted(projections["candidate"]["source_witnesses"]["followup"][0]["outcome"]["runtime_coverage"]),
            "clinical_eligibility_complete": False},
        "copay": {"canonical_manifest_verified": True, "fresh_coverage_verified": True,
                  "payment_permission_added": False},
    }
    report["source_cache_witnesses"] = {table: {
        side + "_sha256": _digest(_attested(projections[side]["tables"][table]))
        for side in ("baseline", "candidate")} for table in TABLES}
    report["source_api_witnesses"] = {side: {
        "coverage_summary_sha256": _digest(projections[side]["source_witnesses"]["copay"]["public_summary"]),
        "coverage_closure_sha256": _digest(projections[side]["source_witnesses"]["copay"]),
    } for side in ("baseline", "candidate")}
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
                                          if key not in {"status", "transition_sha256"}})
    return report


def _public_proof():
    old, new = _public_final_pair()
    pair = {"baseline": old, "candidate": new}
    projections = {side: {"tables": row["tables"], "followup": row["source_witnesses"]["followup"]}
                   for side, row in pair.items()}
    return final._issue_proof(_final_report(pair), projections)


def _cached(proof, table, side):
    value = copy.deepcopy(proof.projections[side]["tables"][table])
    if table == "wavea_evidence_index":
        value["build_id"] = side + "-build"
    elif table in {"wavea_evidence_detail", "wavea_bill_evidence_detail"}:
        for row in value.values():
            row["build_id"] = side + "-build"
    return value


def test_final_proof_is_detached_and_immutable():
    proof = _public_proof()
    final.validate_transition_report_contract(proof.report)
    proof.report["status"] = "forged"
    proof.projections["candidate"]["tables"].clear()
    assert proof.report["status"] == "final_source_refresh_transition_verified"
    assert len(proof.projections["candidate"]["tables"]) == 19
    with pytest.raises(FrozenInstanceError):
        proof._report_json = "{}"


@pytest.mark.parametrize("table", TABLES)
def test_actual_cache_is_checked_against_its_own_source_before_normalization(table):
    proof = _public_proof()
    value = _cached(proof, table, "candidate")
    before = copy.deepcopy(value)
    result = final.normalize_transition_content(table, value, side="candidate", proof=proof)
    assert value == before
    expected = _cached(proof, table, "baseline") if table in OWNED_TABLES else before
    if table == "wavea_evidence_index":
        expected["build_id"] = "candidate-build"
    elif table in {"wavea_evidence_detail", "wavea_bill_evidence_detail"}:
        for row in expected.values():
            row["build_id"] = "candidate-build"
    assert result == expected


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("mutation", ["extra", "dropped", "wrong_type"])
def test_even_six_owned_tables_reject_cache_not_produced_by_its_own_source(table, mutation):
    proof = _public_proof()
    value = _cached(proof, table, "candidate")
    if mutation == "extra":
        if isinstance(value, list):
            value.append({"unproduced_row": True})
        else:
            value["unproduced_field"] = True
    elif mutation == "dropped":
        if isinstance(value, list):
            value.pop()
        else:
            value.pop(next(iter(value)))
    else:
        value = [] if isinstance(value, dict) else {}
    with pytest.raises(ValueError):
        final.normalize_transition_content(table, value, side="candidate", proof=proof)


@pytest.mark.parametrize("mutation", ["manual", "report", "projections", "seal", "copied"])
def test_manual_or_tampered_proof_is_rejected_before_any_cache_permission(mutation):
    proof = _public_proof()
    value = _cached(proof, "cohort_compliance_index", "candidate")
    if mutation == "manual":
        proof = final.FinalSourceRefreshProof(proof._report_json, proof._projections_json, object())
    elif mutation == "report":
        object.__setattr__(proof, "_report_json", "{}")
    elif mutation == "projections":
        object.__setattr__(proof, "_projections_json", "{}")
    elif mutation == "seal":
        object.__setattr__(proof, "_seal", object())
    else:
        proof = copy.deepcopy(proof)
    with pytest.raises(ValueError):
        final.normalize_transition_content("cohort_compliance_index", value, side="candidate", proof=proof)


@pytest.mark.parametrize("mutation", [
    "unknown_contract", "wrong_status", "candidate", "verifier", "seed", "anchor", "closure",
    "old_tool_path", "source_counter", "clinical_true", "copay_permission", "input_config",
    "input_count_float", "input_source", "cache_missing", "cache_extra", "cache_digest_type",
    "api_missing", "api_extra", "api_digest_short", "strict_count_bool", "table_count_float",
    "future_contract", "report_extra", "missing_digest", "protected_fields",
])
def test_saved_report_cannot_gain_authority_by_resealing_changed_metadata(mutation):
    old, new = _public_final_pair()
    report = _final_report({"baseline": old, "candidate": new})
    if mutation == "unknown_contract":
        report["contract"] = "future-unknown-profile"
    elif mutation == "wrong_status":
        report["status"] = "source_refresh_transition_verified"
    elif mutation == "candidate":
        report["candidate_code_sha"] = "b" * 40
    elif mutation == "verifier":
        report["verifier"]["verifier_sha"] = "b" * 40
    elif mutation in {"seed", "anchor", "closure"}:
        key = {"seed": "integration_seed_sha", "anchor": "product_anchor_sha", "closure": "product_closure_sha256"}[mutation]
        report["history"][key] = "b" * (64 if mutation == "closure" else 40)
        if mutation == "closure":
            report["history"][key] = None
    elif mutation == "old_tool_path":
        report["history"]["authorized_changed_paths"] = ["scripts/deploy/verify_source_refresh_transition.py"]
    elif mutation == "source_counter":
        report["source_intent"]["followup"]["summary_fields"].append("future_counter")
    elif mutation == "clinical_true":
        report["source_intent"]["followup"]["clinical_eligibility_complete"] = True
    elif mutation == "copay_permission":
        report["source_intent"]["copay"]["payment_permission_added"] = True
    elif mutation == "input_config":
        report["same_input"]["candidate"]["config_hash"] = "b" * 64
    elif mutation == "input_count_float":
        report["same_input"]["input_file_count"] = 12.0
    elif mutation == "input_source":
        report["same_input"]["baseline"]["source_hash"] = "b" * 64
    elif mutation == "cache_missing":
        report["source_cache_witnesses"].pop("patient_meta")
    elif mutation == "cache_extra":
        report["source_cache_witnesses"]["new_table"] = {"baseline_sha256": "a" * 64, "candidate_sha256": "b" * 64}
    elif mutation == "cache_digest_type":
        report["source_cache_witnesses"]["patient_meta"]["candidate_sha256"] = 0
    elif mutation == "api_missing":
        report["source_api_witnesses"].pop("candidate")
    elif mutation == "api_extra":
        report["source_api_witnesses"]["candidate"]["future_digest"] = "b" * 64
    elif mutation == "api_digest_short":
        report["source_api_witnesses"]["candidate"]["coverage_summary_sha256"] = "b" * 63
    elif mutation == "strict_count_bool":
        report["strict_table_count"] = True
    elif mutation == "table_count_float":
        report["source_projected_table_count"] = 19.0
    elif mutation == "future_contract":
        report["cache_comparison_contract"] = "defer_own_source_checks"
    elif mutation == "report_extra":
        report["future_permission"] = True
    elif mutation == "protected_fields":
        report["protected_fields"] = "all_fields_unchanged"
    else:
        report.pop("candidate_replay_sha256")
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
                                          if key not in {"status", "transition_sha256"}})
    with pytest.raises(ValueError):
        final.validate_transition_report_contract(report)


@pytest.mark.parametrize("field,value", [
    ("status", "unverified"), ("input_bytes_sha256", "f" * 64), ("input_file_count", 12.0),
    ("input_file_count", 11), ("data_mode", "real_claims"),
])
def test_wrong_same_input_stops_before_source_reads(tmp_path, monkeypatch, field, value):
    proof = _public_proof()
    inputs = proof.report["same_input"]
    inputs[field] = value
    monkeypatch.setattr(final, "_roster", lambda *_: pytest.fail("Unbound inputs reached source reads"))
    with pytest.raises(ValueError):
        final.verify_transition(request=_request(), baseline_roster=tmp_path / "old.json",
            candidate_roster=tmp_path / "new.json",
            baseline_meta={"code_sha": final.BASELINE_CODE_SHA, "source_hash": final.BASELINE_SOURCE_HASH,
                           "config_hash": final.BASELINE_CONFIG_HASH},
            candidate_meta={"code_sha": "a" * 40, "config_hash": final.BASELINE_CONFIG_HASH},
            same_input=inputs, python_executable=Path(sys.executable), dependency_roots=(),
            expected_candidate_sha="a" * 40)


@pytest.mark.parametrize("wrong", ["request_candidate", "request_verifier", "argument_verifier", "baseline", "candidate", "config"])
def test_wrong_request_or_cache_pin_stops_before_source_reads(tmp_path, monkeypatch, wrong):
    proof = _public_proof()
    args = dict(request=_request(), baseline_roster=tmp_path / "old.json", candidate_roster=tmp_path / "new.json",
        baseline_meta={"code_sha": final.BASELINE_CODE_SHA, "source_hash": final.BASELINE_SOURCE_HASH,
                       "config_hash": final.BASELINE_CONFIG_HASH},
        candidate_meta={"code_sha": "a" * 40, "config_hash": final.BASELINE_CONFIG_HASH},
        same_input=proof.report["same_input"], python_executable=Path(sys.executable), dependency_roots=(),
        expected_candidate_sha="a" * 40)
    if wrong == "request_candidate":
        args["request"].update(expected_candidate_sha="b" * 40, expected_verifier_sha="b" * 40)
    elif wrong == "request_verifier":
        args["request"]["expected_verifier_sha"] = "b" * 40
    elif wrong == "argument_verifier":
        args["expected_verifier_sha"] = "b" * 40
    elif wrong == "baseline":
        args["baseline_meta"]["code_sha"] = "b" * 40
    elif wrong == "candidate":
        args["candidate_meta"]["code_sha"] = "b" * 40
    else:
        args["candidate_meta"]["config_hash"] = "b" * 64
    monkeypatch.setattr(final, "_roster", lambda *_: pytest.fail("Wrong pin reached source reads"))
    with pytest.raises(ValueError):
        final.verify_transition(**args)


def test_prepare_carries_exact_final_opt_in_to_semantics_rehearsal_and_issuer(machine, monkeypatch):
    """Existing fabricated prepare boundaries; no real child or live service."""
    manifest, spec, _, original = machine
    request = _request(spec["target_sha"])
    spec["clinical_transition"] = request
    private_json(manifest, spec)
    calls = []
    semantic, rehearse, issue = (preparation.verify_candidate_semantic_checkpoint,
                               preparation._rehearse, preparation.issue_wavea_activation)
    def verify(*args, **kwargs):
        assert kwargs["clinical_transition"] == request
        calls.append("semantic")
        return semantic(*args, **kwargs)
    def namespace(*args):
        assert args[0]["clinical_transition"] == request
        calls.append("rehearsal")
        return rehearse(*args)
    def receipt(**kwargs):
        assert kwargs["clinical_transition"] == request
        calls.append("issuer")
        return issue(**kwargs)
    monkeypatch.setattr(preparation, "verify_candidate_semantic_checkpoint", verify)
    monkeypatch.setattr(preparation, "_rehearse", namespace)
    monkeypatch.setattr(preparation, "issue_wavea_activation", receipt)
    result = preparation.prepare_release_bundle(manifest)
    assert result["production_mutated"] is False
    assert calls == ["semantic", "rehearsal", "issuer"]
    assert Path(spec["live_cache_path"]).read_bytes() == original


def test_semantic_checkpoint_dispatches_final_proof_and_keeps_release_unready(tmp_path, monkeypatch):
    """Controller seam only; full source/cache values have separate tests."""
    baseline, candidate, roster = _current_fixture(tmp_path)
    proof = _public_proof()
    request = _request(proof.report["candidate_code_sha"])
    calls = []
    monkeypatch.setattr(semantics, "verify_same_input_rosters", lambda *_args, **_kw: proof.report["same_input"])
    def replay(**kwargs):
        assert kwargs["request"] == request
        assert kwargs["expected_candidate_sha"] == kwargs["expected_verifier_sha"] == "a" * 40
        calls.append("replay")
        return proof
    def parity(*_args, **kwargs):
        assert kwargs["clinical_transition"] is proof
        calls.append("parity")
        return {"candidate_code_sha": "a" * 40, "source_hash": "c" * 64}, {}
    monkeypatch.setattr(final, "verify_transition", replay)
    monkeypatch.setattr(semantics, "_check_legacy_parity", parity)
    monkeypatch.setattr(semantics, "_check_evidence", lambda *_args: ({}, []))
    before = {path: path.read_bytes() for path in (baseline, candidate)}
    report = semantics.verify_candidate_semantic_checkpoint(baseline, baseline_build_id="baseline",
        candidate_db=candidate, candidate_build_id="candidate", source_roster=roster,
        baseline_roster=tmp_path / "old-roster.json", build_config_environment={},
        clinical_transition=request, python_executable=Path(sys.executable), dependency_roots=(Path(sys.base_prefix),))
    assert report["clinical_transition"] == proof.report
    assert report["release_ready"] is False
    assert calls == ["replay", "parity"]
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("mutation", [None, "saved", "saved_hash", "relative_locator", "wrong_head"])
def test_issuer_requires_fresh_final_proof_matching_saved_mirror(tmp_path, monkeypatch, mutation):
    arguments, request, fresh, source_path, raw_path = _issuer_transition_fixture(tmp_path, monkeypatch)
    request["contract"] = CONTRACT
    fresh["clinical_transition"] = _public_proof().report
    raw = json.loads(raw_path.read_text())
    raw["source_report_sha256"] = private_json(source_path, fresh)
    if mutation == "saved":
        saved = copy.deepcopy(fresh)
        saved["clinical_transition"]["neutral_raw_rows"] += 1
        saved["clinical_transition"]["transition_sha256"] = _digest({key: value
            for key, value in saved["clinical_transition"].items() if key not in {"status", "transition_sha256"}})
        raw["source_report_sha256"] = private_json(source_path, saved)
    elif mutation == "saved_hash":
        raw["source_report_sha256"] = "f" * 64
    elif mutation == "relative_locator":
        raw["source_report_path"] = source_path.name
    elif mutation == "wrong_head":
        request.update(expected_candidate_sha="f" * 40, expected_verifier_sha="f" * 40)
    private_json(raw_path, raw)
    if mutation is None:
        assert issuer.issue_wavea_activation(**arguments)["status"] == "private_activation_receipt_issued"
    else:
        with pytest.raises(ValueError):
            issuer.issue_wavea_activation(**arguments)
        assert not arguments["key_path"].exists()
        assert not arguments["receipt_path"].exists()


@pytest.mark.parametrize("mutation", [None, "unknown", "wrong_pin"])
def test_namespace_rehearsal_carries_final_request_and_stops_wrong_pin_before_children(tmp_path, monkeypatch, mutation):
    args, work, events, _ = fixture_rehearsal(tmp_path, monkeypatch)
    request = _request()
    if mutation == "unknown":
        request["contract"] = "unreviewed-profile"
    elif mutation == "wrong_pin":
        request.update(expected_candidate_sha="f" * 40, expected_verifier_sha="f" * 40)
    path = tmp_path / "request.json"
    private_json(path, request)
    args.extend(("--clinical-transition", str(path)))
    proof, calls = _public_proof(), []
    class Database:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
    monkeypatch.setattr(rehearsal.duckdb, "connect", lambda *_args, **_kw: Database())
    monkeypatch.setattr(rehearsal, "_build_metadata", lambda *_: {"code_sha": "a" * 40})
    def verify(**kwargs):
        assert kwargs["request"] == request
        assert kwargs["expected_candidate_sha"] == kwargs["expected_verifier_sha"] == "a" * 40
        calls.append("replay")
        return proof
    def normalize(reports, **kwargs):
        assert kwargs["proof"] is proof
        calls.append(kwargs["side"])
        return reports
    monkeypatch.setattr(final, "verify_transition", verify)
    monkeypatch.setattr(final, "normalize_transition_http_reports", normalize)
    if mutation is None:
        rehearsal.main(args)
        assert calls == ["replay", "baseline", "candidate"]
        assert json.loads((work / "clinical-transition-rehearsal.json").read_text()) == proof.report
    else:
        with pytest.raises(ValueError):
            rehearsal.main(args)
        assert calls == []
        assert not any(event.startswith("start:") for event in events)


def _private_final_fixture(tmp_path):
    path, observed, candidate, runtime, rehearsal_report, observation = sealed_rehearsal(tmp_path)
    fresh = _public_proof().report
    candidate["source_hash"] = fresh["same_input"]["candidate"]["source_hash"]
    observation["logical_tuple"]["cache"]["source_hash"] = candidate["source_hash"]
    observation["tuple_sha256"] = _digest(observation["logical_tuple"])
    rehearsal_report["candidate_tuple_sha256"] = observation["tuple_sha256"]
    rehearsal_report["candidate_tuple_observation_sha256"] = private_json(observed, observation)
    files = {}
    for name in ("verify_final_source_refresh_transition.py", "verify_source_refresh_transition.py"):
        producer = runtime / "scripts/deploy" / name
        producer.write_text("# public reviewed fixture producer\n")
        files["scripts/deploy/" + name] = hashlib.sha256(producer.read_bytes()).hexdigest()
    name = "scripts/deploy/rehearse_wavea_same_port.py"
    files[name] = hashlib.sha256((runtime / name).read_bytes()).hexdigest()
    fresh["verifier"] = {"verifier_sha": candidate["code_sha"], "files": files, "source_sha256": _digest(files)}
    fresh["transition_sha256"] = _digest({key: value for key, value in fresh.items()
                                         if key not in {"status", "transition_sha256"}})
    rehearsal_report["same_input_proof_sha256"] = private_json(tmp_path / "same-input-rehearsal.json", fresh["same_input"])
    rehearsal_report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", fresh)
    private_json(path, rehearsal_report)
    return path, observed, candidate, runtime, rehearsal_report, fresh


@pytest.mark.parametrize("mutation", [None, "unknown", "wrong_status", "wrong_pin", "changed_source", "saved_mirror", "saved_hash", "unrequested"])
def test_private_rehearsal_accepts_only_fresh_final_source_input_and_saved_proof(tmp_path, mutation):
    path, observed, candidate, runtime, report, fresh = _private_final_fixture(tmp_path)
    supplied = fresh
    if mutation == "unknown":
        fresh["contract"] = "unknown-profile"
    elif mutation == "wrong_status":
        fresh["status"] = "source_refresh_transition_verified"
    elif mutation == "wrong_pin":
        fresh["candidate_code_sha"] = "f" * 40
    elif mutation == "changed_source":
        (runtime / "scripts/deploy/verify_final_source_refresh_transition.py").write_text("# changed\n")
    elif mutation == "saved_mirror":
        saved = copy.deepcopy(fresh)
        saved["followup_line_count"] += 1
        saved["transition_sha256"] = _digest({key: value for key, value in saved.items()
                                             if key not in {"status", "transition_sha256"}})
        report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", saved)
    elif mutation == "saved_hash":
        report["clinical_transition_report_sha256"] = "f" * 64
    elif mutation == "unrequested":
        supplied = None
    if mutation in {"unknown", "wrong_status", "wrong_pin"}:
        fresh["transition_sha256"] = _digest({key: value for key, value in fresh.items()
                                             if key not in {"status", "transition_sha256"}})
        report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", fresh)
    private_json(path, report)
    if mutation is None:
        assert verify_private_rehearsal(path, observed, candidate=candidate, backend_runtime=runtime,
            clinical_transition=fresh)["status"] == "private_pair_rehearsal_verified"
    else:
        with pytest.raises(ValueError):
            verify_private_rehearsal(path, observed, candidate=candidate, backend_runtime=runtime, clinical_transition=supplied)


@pytest.mark.parametrize("mutation", ["partial", "wrong_status", "wrong_seed", "unknown_source_closure"])
def test_real_signed_loader_rejects_resealed_final_profile_with_unbound_metadata(signed_bundle, mutation):
    source_path = signed_bundle.root / "semantic.json"
    source = json.loads(source_path.read_text())
    report = _public_proof().report
    if mutation == "partial":
        report.pop("source_cache_witnesses")
    elif mutation == "wrong_status":
        report["status"] = "clinical_semantic_transition_verified"
    elif mutation == "wrong_seed":
        report["history"]["integration_seed_sha"] = "f" * 40
    else:
        report["verifier"]["files"] = {}
        report["verifier"]["source_sha256"] = _digest({})
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
                                          if key not in {"status", "transition_sha256"}})
    source["clinical_transition"] = report
    private_json(source_path, source)
    signed_startup._reseal_semantic(signed_bundle, mirror_rehearsal=True)
    with pytest.raises(ValueError):
        signed_startup._candidate_load(signed_bundle)


@pytest.mark.parametrize("view", ["draft", "legacy"])
def test_http_serializer_keeps_same_line_owned_final_annotations_payment_neutral(monkeypatch, view):
    proof, packages = _public_proof(), {}
    for side in ("baseline", "candidate"):
        tables = proof.projections[side]["tables"]
        packages[side] = fabricated_transport(monkeypatch, {
            "/api/billing-report/P1": copy.deepcopy(tables["patient_billing_report_rows"]["P1"]),
            "/api/billing-report/P1/bills/C1": copy.deepcopy(tables["patient_bill_billing_report_rows"]["P1::C1"]),
        }, code_sha=proof.report[side + "_code_sha"], repository=Path("/public-fixture") / side)
    old, new = packages["baseline"], packages["candidate"]
    old_reports = old.draft_reports if view == "draft" else {path: semantics._legacy_report(row) for path, row in old.complete_reports.items()}
    new_reports = new.draft_reports if view == "draft" else {path: semantics._legacy_report(row) for path, row in new.complete_reports.items()}
    actual = final.normalize_transition_http_reports(new_reports, side="candidate", proof=proof,
        transport=new, baseline_transport=old, view=view)
    assert actual == old_reports


@pytest.fixture
def authored_final_source(tmp_path, monkeypatch):
    """Public Git objects and public corpus bytes, independently of cache values."""
    import polars as pl
    old, new = _public_final_pair()
    checkout = tmp_path / "public-authored-source"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.email", "source@example.invalid")
    _git(checkout, "config", "user.name", "Public source fixture")
    organ = checkout / "data/gazette/prose_rules/treatment_pricing_2_4.json"
    followup = checkout / "data/gazette/prose_rules/drug_indication_prose.json"
    corpus = checkout / "data/gazette/sut_clauses.parquet"
    organ.parent.mkdir(parents=True)
    organ.write_text(json.dumps(old["rules"]))
    followup.write_text(json.dumps({"rules": old["source_witnesses"]["followup_rules"]}))
    pl.DataFrame(old["source_witnesses"]["followup_source_clauses"]).write_parquet(corpus)
    baseline = _commit(checkout, "public authored baseline")
    organ.write_text(json.dumps(new["rules"]))
    anchor = _commit(checkout, "public source quarantine")
    for module in (final, frozen):
        monkeypatch.setattr(module, "BASELINE_CODE_SHA", baseline)
        monkeypatch.setattr(module, "PRODUCT_ANCHOR_SHA", anchor)
    monkeypatch.setattr(frozen, "BASELINE_SOURCE_BLOB", _git(checkout, "rev-parse", baseline + ":" + frozen.SOURCE_PATH))
    monkeypatch.setattr(frozen, "PRODUCT_SOURCE_BLOB", _git(checkout, "rev-parse", anchor + ":" + frozen.SOURCE_PATH))
    return {"checkout": str(checkout)}, old, new


def test_followup_authored_rules_and_full_public_corpus_match_own_checkout(authored_final_source):
    roster, old, new = authored_final_source
    intent = final._source_intent(roster, roster, old, new)
    assert intent["followup"]["clinical_eligibility_complete"] is False
    assert intent["copay"]["payment_permission_added"] is False
    assert intent["followup"]["rule_ids"] == [
        "4.2.46.clinical_annual_reassessment", "4.2.57.clinical_16_week_response"]


@pytest.mark.parametrize("side", ["old", "new"])
@pytest.mark.parametrize("mutation", ["authored_rule", "source_body", "source_hash", "source_id", "source_status", "source_missing"])
def test_forged_source_inventory_cannot_be_resealed_as_own_rules_or_corpus(authored_final_source, side, mutation):
    roster, old, new = authored_final_source
    sources = (old if side == "old" else new)["source_witnesses"]
    if mutation == "authored_rule":
        sources["followup_rules"][0]["drug_names"] = ["unrelated drug"]
    elif mutation == "source_missing":
        sources["followup_source_clauses"] = []
    else:
        row = sources["followup_source_clauses"][0]
        field, value = {
            "source_body": ("text", "Forged payment authority"),
            "source_hash": ("content_hash", "f" * 64),
            "source_id": ("clause_id", "CF000099"),
            "source_status": ("is_in_force", False),
        }[mutation]
        row[field] = value
    with pytest.raises(ValueError):
        final._source_intent(roster, roster, old, new)


def _copay_source_rows():
    keys = [
        "1.8.5.(7)#fb187fbe", "1.8.2.(3)#04043a39", "1.8.5.(8)#2c30921a",
        "1.8.5.(5)#424f9787", "1.8.5.(6)#989e2ee8", "1.8.5.(1)#27612764",
        "1.8.5.(11)#4c5d2bce", "1.8.5.(12)#b67e143b", "1.8.5.(13)#3697a89c",
        "1.8.5.(15)#05de89cd", "1.8.5.(16)#89cd1467", "1.8.5.a#a2615b26",
    ]
    return [{"clause_id": f"C{index:06}", "clause_key": key, "is_in_force": True}
            for index, key in enumerate(keys, 1)]


def test_real_copay_resolver_uses_stable_keys_and_never_promotes_deferred_runtime_traces():
    import polars as pl
    from scripts.sut.prose.gate_b_generic import _resolve_copay_compositor_clause_traces
    traces, encoded = _resolve_copay_compositor_clause_traces(pl.DataFrame(_copay_source_rows()))
    assert traces == {
        "copay_exemption_ek1a": ["C000001"], "copay_exemption_ek4d": ["C000002", "C000003"],
        "copay_exemption_visit_type": ["C000004", "C000005"],
        "copay_exemption_occupational": ["C000006"],
        "copay_exemption_patient_status": ["C000007", "C000008", "C000009", "C000010", "C000011", "C000012"],
    }
    assert encoded == set()


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "stale_key", "inactive", "inactive_type", "missing_key"])
def test_copay_current_key_resolution_rejects_stale_duplicate_or_nonactive_source(mutation):
    import polars as pl
    from scripts.sut.prose.gate_b_generic import _resolve_copay_compositor_clause_traces
    rows = _copay_source_rows()
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "stale_key":
        rows[0]["clause_key"] = "1.8.5.(7)#00000000"
    elif mutation == "inactive":
        rows[0]["is_in_force"] = False
    elif mutation == "inactive_type":
        for row in rows:
            row["is_in_force"] = 1
    else:
        for row in rows:
            row.pop("clause_key")
    with pytest.raises(ValueError):
        _resolve_copay_compositor_clause_traces(pl.DataFrame(rows))
