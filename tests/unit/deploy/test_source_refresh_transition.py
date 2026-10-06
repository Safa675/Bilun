"""Public adversarial fixtures for the bounded 499 to d033 source refresh.

Handwritten replay values exercise the contract; they are not a production
admission receipt. No retained patient payload is used as an expected value.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import duckdb

from scripts.deploy import prepare_single_vps_release as preparation
from scripts.deploy import issue_wavea_activation as issuer
from scripts.deploy import rehearse_wavea_same_port as rehearsal
from scripts.deploy import verify_candidate_semantics as semantics
from scripts.deploy import verify_clinical_semantic_transition as historical
from scripts.deploy import verify_source_refresh_transition as transition
from src.bilun.domain.billing.rule_findings import build_evaluation_id
from tests.unit.deploy.test_generate_candidate_source_roster import _candidate, _roster
from tests.unit.deploy.test_prepare_single_vps_release import machine as machine
from tests.unit.deploy.test_prepare_single_vps_release import old_python_context, old_python_record
from tests.unit.deploy.test_same_port_rehearsal import private_json
from tests.unit.deploy.test_same_port_rehearsal import fabricated_transport, fixture_rehearsal, sealed_rehearsal
from tests.unit.deploy.test_issue_wavea_activation import _issuer_transition_fixture
from scripts.deploy.verify_private_rehearsal import verify_private_rehearsal
from tests.integration.deploy import test_signed_transition_startup as signed_startup
from tests.integration.deploy.test_signed_transition_startup import signed_bundle as signed_bundle
from tests.unit.deploy.test_verify_candidate_semantics import _current_fixture, _mutate_payload, _verify

_ORGAN_RULES = (
    "2.4.2.A.(2).non_covered_donor_organ_tissue_no_pay",
    "2.4.2.A.(4).domestic_organ_transfer_per_2_6",
    "2.4.2.A.(5).cadaver_donor_procurement_p911146_ek2c",
)
_UNRELATED_RULE = "public.unrelated_rule"
_STATUSES = ("evaluated", "missing_inputs", "unavailable")
_REAL_PREPARE_REHEARSE = preparation._rehearse


@pytest.fixture
def source_projection_wrapper_case(tmp_path, monkeypatch):
    """Exercise the real wrapper and trace/Git gates with a public child double.

    Only the strace child is replaced. Git subprocesses and trace validation
    still execute; expected projections are handwritten public fixtures.
    """
    candidate = _candidate(tmp_path)
    checkout, _, claims, clean = candidate
    roster = _roster(candidate)
    runtime = tmp_path / "public-runtime"
    runtime.mkdir()
    executable = runtime / "python"
    executable.write_bytes(b"public executable fixture; subprocess is observed")
    directory = runtime / "dependencies"
    directory.mkdir()
    directory_module = directory / "public_dependency.py"
    directory_module.write_text("PUBLIC = True\n", encoding="utf-8")
    file = runtime / "public-runtime-metadata.json"
    file.write_text('{"public_runtime_fixture": true}\n', encoding="utf-8")
    alias = runtime / "public-runtime-alias.json"
    alias.symlink_to(file)
    expected = _public_projection_pair()[0]
    case = {
        "checkout": checkout, "claims": claims, "clean": clean, "roster": roster,
        "runtime": runtime, "executable": executable, "directory": directory,
        "directory_module": directory_module, "file": file, "alias": alias,
        "dependencies": (file, directory), "reads": [file, directory_module],
        "extra_reads": [], "worker_calls": [], "trace_calls": [],
        "expected": expected, "output": expected, "returncode": 0,
    }
    original_run = subprocess.run
    original_validator = transition.validate_runtime_read_trace

    def run(command, **kwargs):
        if command[0] != "strace":
            return original_run(command, **kwargs)
        case["worker_calls"].append((list(command), kwargs))
        trace = Path(command[command.index("-o") + 1])
        reads = [checkout / "data/gazette/prose_rules/rule.json",
                 claims / "claim_headers.parquet", *case["reads"], *case["extra_reads"]]
        trace.write_text("\n".join(
            [f'openat(AT_FDCWD, "public-fixture", O_RDONLY) = {number}<{path}>'
             for number, path in enumerate(reads, 3)] + ["+++ exited with 0 +++"]
        ) + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            command, case["returncode"],
            stdout=json.dumps(case["output"], allow_nan=False).encode(),
            stderr=b"masked public fixture diagnostics",
        )

    def validate(trace, **kwargs):
        case["trace_calls"].append(kwargs.copy())
        return original_validator(trace, **kwargs)

    def invoke():
        return transition._replay_projection(
            checkout, claims, clean, "synthetic_demo", case["executable"],
            roster=roster, dependency_roots=case["dependencies"],
        )

    monkeypatch.setattr(transition.subprocess, "run", run)
    monkeypatch.setattr(transition, "validate_runtime_read_trace", validate)
    case["invoke"] = invoke
    return case


@pytest.mark.parametrize("dependency_kind", [
    "directory", "file", "file_then_directory", "directory_then_file", "runtime_file_alias",
])
def test_source_projection_wrapper_preserves_each_explicit_dependency_and_order(
    source_projection_wrapper_case, dependency_kind,
):
    case = source_projection_wrapper_case
    dependencies, reads = {
        "directory": ((case["directory"],), [case["directory_module"]]),
        "file": ((case["file"],), [case["file"]]),
        "file_then_directory": ((case["file"], case["directory"]),
                                [case["file"], case["directory_module"]]),
        "directory_then_file": ((case["directory"], case["file"]),
                                [case["directory_module"], case["file"]]),
        # Existing reviewed runtime aliases remain caller-owned. The trace
        # gate resolves them and still applies the source/data boundary.
        "runtime_file_alias": ((case["alias"],), [case["file"]]),
    }[dependency_kind]
    case["dependencies"], case["reads"] = dependencies, reads
    result = case["invoke"]()
    assert result == case["expected"]
    assert len(case["worker_calls"]) == len(case["trace_calls"]) == 1
    command, options = case["worker_calls"][0]
    assert command[command.index("-c") + 1] == transition._WORKER
    assert command[-4:] == [str(case["claims"]), str(case["clean"]), "synthetic_demo",
                             json.dumps([str(path) for path in dependencies])]
    assert str(case["executable"]) in command
    assert all(flag in command for flag in ("-I", "-S", "-B"))
    assert options["cwd"] == case["checkout"]
    assert options["env"] == {
        "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC",
        "PYTHONDONTWRITEBYTECODE": "1", "POLARS_MAX_THREADS": "1",
    }
    assert case["trace_calls"][0]["dependency_roots"] == dependencies
    assert case["trace_calls"][0]["roster"] == case["roster"]


@pytest.mark.parametrize("invalid", ["empty", "relative", "missing", "broken_alias", "fifo"])
def test_source_projection_wrapper_rejects_invalid_dependency_before_starting_child(
    source_projection_wrapper_case, invalid,
):
    case = source_projection_wrapper_case
    if invalid == "empty":
        dependencies = ()
    elif invalid == "relative":
        dependencies = (Path("relative-public-runtime.json"),)
    elif invalid == "missing":
        dependencies = (case["runtime"] / "missing.json",)
    elif invalid == "broken_alias":
        broken = case["runtime"] / "broken.json"
        broken.symlink_to(case["runtime"] / "absent.json")
        dependencies = (broken,)
    else:
        fifo = case["runtime"] / "public-fifo"
        os.mkfifo(fifo)
        dependencies = (fifo,)
    case["dependencies"] = dependencies
    with pytest.raises(ValueError, match="explicit existing runtime and dependency roots"):
        case["invoke"]()
    assert case["worker_calls"] == case["trace_calls"] == []


@pytest.mark.parametrize("filename", [
    ".env", ".env.production", "public-cache.duckdb", "public-cache.db",
    "public-cache.sqlite3", "public-cache.sqlite3-wal", "public-cache.db-shm",
])
def test_source_projection_wrapper_never_uses_dependency_allowance_for_secrets_or_cache(
    source_projection_wrapper_case, filename,
):
    case = source_projection_wrapper_case
    forbidden = case["directory"] / filename
    forbidden.write_bytes(b"masked public fixture")
    case["extra_reads"] = [forbidden]
    with pytest.raises(ValueError, match="environment file|database oracle"):
        case["invoke"]()
    assert len(case["worker_calls"]) == 1
    assert case["trace_calls"] == []


@pytest.mark.parametrize("overlap", [
    "checkout", "source_file", "claims", "claim_file", "clean", "clean_file",
    "broad_parent", "source_alias", "claims_alias",
])
def test_source_projection_wrapper_keeps_actual_trace_source_and_input_overlap_gate(
    source_projection_wrapper_case, overlap,
):
    case = source_projection_wrapper_case
    paths = {
        "checkout": case["checkout"],
        "source_file": case["checkout"] / "data/gazette/prose_rules/rule.json",
        "claims": case["claims"], "claim_file": case["claims"] / "claim_headers.parquet",
        "clean": case["clean"], "clean_file": next(case["clean"].iterdir()),
        "broad_parent": case["checkout"].parent,
    }
    if overlap in {"source_alias", "claims_alias"}:
        target = paths["source_file" if overlap == "source_alias" else "claims"]
        alias = case["runtime"] / "source-or-input-alias"
        alias.symlink_to(target, target_is_directory=target.is_dir())
        dependency = alias
    else:
        dependency = paths[overlap]
    case["dependencies"] = (dependency,)
    case["reads"] = []
    with pytest.raises(ValueError, match="must not overlap candidate source or data paths"):
        case["invoke"]()
    assert len(case["worker_calls"]) == len(case["trace_calls"]) == 1
    assert case["trace_calls"][0]["dependency_roots"] == (dependency,)


@pytest.mark.parametrize("unrostered", ["source", "claim", "clean", "foreign_source"])
def test_source_projection_wrapper_rejects_unrostered_reads_through_actual_trace_gate(
    source_projection_wrapper_case, unrostered,
):
    case = source_projection_wrapper_case
    path = {
        "source": case["checkout"] / "data/gazette/unreviewed.json",
        "claim": case["claims"] / "unreviewed.parquet",
        "clean": case["clean"] / "unreviewed.parquet",
        "foreign_source": case["runtime"] / "unapproved_source.py",
    }[unrostered]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"public unrostered fixture")
    case["extra_reads"] = [path]
    with pytest.raises(ValueError, match="Runtime read outside source roster"):
        case["invoke"]()
    assert len(case["worker_calls"]) == len(case["trace_calls"]) == 1


@pytest.mark.parametrize("failure", ["exit", "unknown_output_contract"])
def test_source_projection_wrapper_stops_before_trace_permission_for_failed_worker(
    source_projection_wrapper_case, failure,
):
    case = source_projection_wrapper_case
    if failure == "exit":
        case["returncode"] = 1
    else:
        case["output"] = {**case["expected"], "allow_unknown_source": True}
    with pytest.raises(ValueError, match="no transition permission|unknown ownership contract"):
        case["invoke"]()
    assert len(case["worker_calls"]) == 1
    assert case["trace_calls"] == []


def _git(checkout: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(checkout), *arguments],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _commit(checkout: Path, path: str, content: str, message: str) -> str:
    destination = checkout / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    _git(checkout, "add", path)
    _git(checkout, "commit", "-qm", message)
    return _git(checkout, "rev-parse", "HEAD")


def _request(candidate: str = "a" * 40) -> dict:
    return {
        "contract": transition.TRANSITION_CONTRACT,
        "expected_candidate_sha": candidate,
        "expected_verifier_sha": candidate,
    }


def test_exact_public_anchors_and_historical_verifier_are_unchanged():
    assert transition.BASELINE_CODE_SHA == "499dff4c40298075d9c90d6254baf903266b6611"
    assert transition.BASELINE_TREE == "a8b1f10c977da1fab5fd05ed605ac0853be84397"
    assert transition.PRODUCT_ANCHOR_SHA == "d0337600f45a17aa635f6bbe8d584095a6f3e82e"
    assert transition.PRODUCT_ANCHOR_TREE == "cab00a2d077ab15fdbcf37a52533f4b85f21de76"
    assert transition.SOURCE_PATH == "data/gazette/prose_rules/treatment_pricing_2_4.json"
    assert transition.BASELINE_SOURCE_BLOB == "fe9a8a060db1788e330a8ff29b4f0d5cbf7db9a6"
    assert transition.PRODUCT_SOURCE_BLOB == "f0b0e0a5be44e0ad6ac470bd4859325be469984c"
    assert hashlib.sha256(Path(historical.__file__).read_bytes()).hexdigest() == (
        "73f20d6a5302aafe7456ec81a57fa515dbbb1084453f37110b199b9eaa1d36de"
    )
    assert historical.BASELINE_CODE_SHA == "3f5540cf199cb464b1fca1d7d7d6ff024d5edc3b"
    assert historical.PRODUCT_ANCHOR_SHA == "3e0e0c6d88fdcd4817e0a7a84b3361184d78b1ea"
    assert "scripts/deploy/verify_clinical_semantic_transition.py" not in transition.AUTHORIZED_TOOLING_PATHS
    assert "src/bilun/api/wavea_activation.py" not in transition.AUTHORIZED_TOOLING_PATHS
    assert ".github/workflows/deploy.yml" not in transition.AUTHORIZED_TOOLING_PATHS


def test_explicit_request_is_detached_and_none_retains_strict_default():
    assert transition.validate_transition_request(None) is None
    request = _request()
    validated = transition.validate_transition_request(request)
    assert validated == request and validated is not request
    request["expected_candidate_sha"] = "b" * 40
    assert validated["expected_candidate_sha"] == "a" * 40
    old = {
        "contract": historical.TRANSITION_CONTRACT,
        "expected_candidate_sha": historical.PRODUCT_ANCHOR_SHA,
        "expected_verifier_sha": "e" * 40,
    }
    assert transition.validate_transition_request(old) == historical.validate_transition_request(old)


@pytest.mark.parametrize("mutation", [
    "extra", "unknown", "short", "uppercase", "bool", "missing", "non_mapping",
])
def test_request_cannot_enable_unknown_partial_or_untyped_contracts(mutation):
    request = _request()
    if mutation == "extra":
        request["skip_parity"] = True
    elif mutation == "unknown":
        request["contract"] = "source-drift-allowlist"
    elif mutation == "short":
        request["expected_candidate_sha"] = "d0337600"
    elif mutation == "uppercase":
        request["expected_verifier_sha"] = "A" * 40
    elif mutation == "bool":
        request["expected_verifier_sha"] = True
    elif mutation == "missing":
        request.pop("expected_verifier_sha")
    else:
        request = []
    with pytest.raises(ValueError):
        transition.validate_transition_request(request)


def test_preparation_accepts_only_the_exact_new_candidate_and_verifier_target(machine):
    manifest, spec, _, _ = machine
    spec["clinical_transition"] = _request(spec["target_sha"])
    private_json(manifest, spec)
    assert preparation.load_preparation_manifest(manifest)["clinical_transition"] == spec["clinical_transition"]


@pytest.mark.parametrize("field", ["expected_candidate_sha", "expected_verifier_sha"])
def test_preparation_rejects_another_head_before_any_replay(machine, field):
    manifest, spec, _, _ = machine
    spec["clinical_transition"] = _request(spec["target_sha"])
    spec["clinical_transition"][field] = "f" * 40
    private_json(manifest, spec)
    with pytest.raises(ValueError, match="identity|exact target/tooling head"):
        preparation.load_preparation_manifest(manifest)


@pytest.fixture
def source_history(tmp_path: Path, monkeypatch):
    """Real public Git ancestry, without old objects in shallow hosted CI."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    _git(checkout, "init", "-q", "-b", "main")
    _git(checkout, "config", "user.name", "Bilun Source Refresh Test")
    _git(checkout, "config", "user.email", "source-refresh@example.invalid")
    _git(checkout, "config", "commit.gpgsign", "false")
    baseline = _commit(checkout, "src/bilun/product.py", "old public source\n", "baseline")
    monkeypatch.setattr(transition, "BASELINE_CODE_SHA", baseline)
    monkeypatch.setattr(transition, "BASELINE_TREE", _git(checkout, "rev-parse", "HEAD^{tree}"))
    anchor = _commit(checkout, "src/bilun/product.py", "reviewed public source\n", "product")
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_SHA", anchor)
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_TREE", _git(checkout, "rev-parse", "HEAD^{tree}"))
    path = "tests/unit/deploy/test_source_refresh_transition.py"
    candidate = _commit(checkout, path, "# reviewed regression\n", "tooling")
    return checkout, baseline, anchor, candidate, path


def test_history_accepts_only_externally_pinned_linear_tooling_descendants(source_history):
    checkout, _, _, candidate, _ = source_history
    assert transition._verify_candidate_history(checkout, candidate)
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, "f" * 40)


@pytest.mark.parametrize("path", [
    "src/bilun/domain/clinical.py", "src/bilun/domain/clinical_followup.py",
    "data/gazette/clinical_sources/clinical_versions.json",
    "data/gazette/prose_rules/copay_gate_b_generic.json",
    "data/gazette/prose_rules/treatment_pricing_2_4.json",
    "data/synthetic/sut/claims/claim_headers.parquet",
    "scripts/deploy/verify_clinical_semantic_transition.py",
    "scripts/deploy/verify_source_refresh_transition_extra.py",
    "tests/unit/deploy/test_source_refresh_transition_extra.py",
    ".github/workflows/ci.yml", "frontend/next.config.ts",
])
def test_unrelated_source_future_assets_and_similar_tooling_names_are_rejected(source_history, path):
    checkout, _, _, _, _ = source_history
    candidate = _commit(checkout, path, "unreviewed bytes\n", "unreviewed")
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, candidate)


def test_product_change_then_revert_still_fails_even_when_final_tree_is_clean(source_history):
    checkout, _, _, _, path = source_history
    _commit(checkout, "src/bilun/product.py", "unreviewed source\n", "change")
    _commit(checkout, "src/bilun/product.py", "reviewed public source\n", "revert")
    candidate = _commit(checkout, path, "# next regression\n", "more tooling")
    assert _git(checkout, "diff", "--name-only", transition.PRODUCT_ANCHOR_SHA, candidate) == path
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, candidate)


@pytest.mark.parametrize("constant", ["BASELINE_TREE", "PRODUCT_ANCHOR_TREE"])
def test_same_commit_name_with_wrong_product_tree_is_rejected(source_history, monkeypatch, constant):
    checkout, _, _, candidate, _ = source_history
    monkeypatch.setattr(transition, constant, "f" * 40)
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, candidate)


def test_merge_history_cannot_broaden_the_linear_tooling_exception(source_history):
    checkout, _, anchor, _, _ = source_history
    _git(checkout, "checkout", "-qb", "side", anchor)
    _commit(checkout, "scripts/deploy/verify_source_refresh_transition.py", "# side\n", "side tooling")
    _git(checkout, "checkout", "-q", "main")
    _git(checkout, "merge", "-q", "--no-ff", "side", "-m", "nonlinear tooling")
    candidate = _git(checkout, "rev-parse", "HEAD")
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, candidate)


@pytest.fixture
def replay_checkout_pair(tmp_path):
    """Real committed source objects plus a separate roster for each side."""
    records = {}
    for side in ("baseline", "candidate"):
        root = tmp_path / side
        root.mkdir()
        checkout, sha, claims, clean = _candidate(root)
        if side == "candidate":
            sha = _commit(checkout, "src/bilun/domain/rules.py", "# new public source\n", "source")
        for filename in ("performed_procedure_lines.parquet", "medula_rejection_events.parquet"):
            (claims / filename).write_bytes(b"public synthetic input fixture")
        candidate = checkout, sha, claims, clean
        roster = _roster(candidate)
        roster_path = root / "roster.json"
        private_json(roster_path, roster)
        records[side] = {"candidate": candidate, "roster": roster, "roster_path": roster_path}
    return records


def _hidden_source_change(record, relative="src/bilun/domain/rules.py"):
    checkout, sha, _, _ = record["candidate"]
    _git(checkout, "update-index", "--assume-unchanged", relative)
    (checkout / relative).write_text("unreviewed disk source\n", encoding="utf-8")
    assert _git(checkout, "diff", "--name-only", sha, "--", relative) == ""
    replacement = _roster(record["candidate"])
    private_json(record["roster_path"], replacement)
    # Both ordinary disk hashes and Git's diff view can agree, while committed
    # bytes remain different. The source refresh must prove Git-object binding.
    loaded, _ = transition._roster(record["roster_path"], sha)
    assert loaded == replacement
    return replacement


def test_each_replay_source_binds_its_own_git_objects_without_writes(replay_checkout_pair):
    for record in replay_checkout_pair.values():
        roster = record["roster"]
        sources = [Path(row["path"]) for row in roster["sources"] if row["label"].startswith("repo:")]
        before = {source: source.read_bytes() for source in sources}
        binding = transition._replay_checkout_binding(roster)
        assert binding["code_sha"] == roster["code_sha"]
        assert binding["file_count"] == len(sources)
        assert len(binding["source_sha256"]) == 64
        assert {source: source.read_bytes() for source in sources} == before


@pytest.mark.parametrize("side", ["baseline", "candidate"])
@pytest.mark.parametrize("relative", ["src/bilun/domain/rules.py", "data/gazette/prose_rules/rule.json"])
def test_fresh_self_consistent_roster_cannot_hide_uncommitted_source_bytes(replay_checkout_pair, side, relative):
    roster = _hidden_source_change(replay_checkout_pair[side], relative)
    with pytest.raises(ValueError, match="Git"):
        transition._replay_checkout_binding(roster)


@pytest.mark.parametrize("mutation", [
    "missing", "extra", "duplicate", "wrong_sha", "wrong_checkout", "wrong_path",
    "wrong_hash", "wrong_size", "changed_head", "root_link", "source_link",
    "source_hardlink", "deleted",
])
def test_source_roster_requires_exact_identity_inventory_and_regular_disk_files(
    replay_checkout_pair, tmp_path, mutation,
):
    record = replay_checkout_pair["baseline"]
    checkout, _, _, _ = record["candidate"]
    roster = copy.deepcopy(record["roster"])
    row = next(item for item in roster["sources"] if item["label"] == "repo:src/bilun/domain/rules.py")
    source = Path(row["path"])
    if mutation == "missing":
        roster["sources"].remove(row)
    elif mutation == "extra":
        roster["sources"].append({**row, "label": "repo:src/bilun/unreviewed.py"})
    elif mutation == "duplicate":
        roster["sources"].append(copy.deepcopy(row))
    elif mutation == "wrong_sha":
        roster["code_sha"] = "f" * 40
    elif mutation == "wrong_checkout":
        roster["checkout"] = replay_checkout_pair["candidate"]["roster"]["checkout"]
    elif mutation == "wrong_path":
        outside = tmp_path / "outside.py"
        outside.write_bytes(source.read_bytes())
        row["path"] = str(outside)
    elif mutation == "wrong_hash":
        row["sha256"] = "f" * 64
    elif mutation == "wrong_size":
        row["size_bytes"] += 1
    elif mutation == "changed_head":
        _commit(checkout, "README.md", "other head\n", "other identity")
    elif mutation == "root_link":
        linked = tmp_path / "linked-checkout"
        linked.symlink_to(checkout, target_is_directory=True)
        roster["checkout"] = str(linked)
    elif mutation in {"source_link", "source_hardlink"}:
        shared = tmp_path / "shared.py"
        shared.write_bytes(source.read_bytes())
        source.unlink()
        if mutation == "source_link":
            source.symlink_to(shared)
        else:
            source.hardlink_to(shared)
    else:
        source.unlink()
    with pytest.raises(ValueError):
        transition._replay_checkout_binding(roster)


@pytest.mark.parametrize("table,statement", [
    ("cohort_sut_summary", "INSERT INTO cohort_sut_summary VALUES ('candidate', '{}')"),
    ("validation_payload", "INSERT INTO validation_payload VALUES ('candidate', '{}', '{}')"),
    ("patient_meta", "UPDATE patient_meta SET age = 999 WHERE build_id = 'candidate'"),
    ("cohort_sut_exposure", "INSERT INTO cohort_sut_exposure VALUES ('candidate', '{}')"),
    ("patient_diagnoses", "INSERT INTO patient_diagnoses VALUES ('candidate', 'P1', '[\"Q99\"]')"),
    ("patient_alert_rows", "UPDATE patient_alert_rows SET copay_action = 'unexpected' WHERE build_id = 'candidate'"),
    ("patient_billing_reports", "INSERT INTO patient_billing_reports VALUES ('candidate', '{}')"),
])
def test_no_opt_in_keeps_all_nonpayload_row_tables_strict(tmp_path, table, statement):
    baseline, candidate, _ = _current_fixture(tmp_path)
    with duckdb.connect(str(candidate)) as con:
        con.execute(statement)
    with pytest.raises(ValueError, match=f"Current {table} payload drift"):
        _verify(baseline, candidate)


@pytest.mark.parametrize("table", [
    "patient_billing_report_rows", "patient_bill_billing_report_rows",
    "wavea_evidence_detail", "wavea_bill_evidence_detail", "wavea_evidence_index",
])
def test_new_source_changes_are_rejected_without_an_explicit_transition(tmp_path, table):
    baseline, candidate, _ = _current_fixture(tmp_path)
    def mutate(row):
        if table.startswith("patient_"):
            row["drug_indication"]["coverage_scope"]["pilot_rule_count"] += 1
        elif table == "wavea_evidence_index":
            row["unreviewed_counter"] = 1
        else:
            row["evaluations"][-1]["reason"] = "source_review_required"
    _mutate_payload(candidate, table, mutate)
    with pytest.raises(ValueError, match=f"Current {table} payload drift"):
        _verify(baseline, candidate)


def _counts(evaluations, rule_groups):
    """Handwritten public fixture arithmetic, independent of verifier helpers."""
    by_rule = {rule: {status: 0 for status in _STATUSES} for rule in rule_groups}
    by_group = {group: {status: 0 for status in _STATUSES} for group in set(rule_groups.values())}
    for row in evaluations:
        by_rule[row["rule_id"]][row["evaluation_status"]] += 1
        by_group[rule_groups[row["rule_id"]]][row["evaluation_status"]] += 1
    return {
        "by_rule": by_rule, "by_group": by_group,
        "evaluation_count": len(evaluations), "review_count": 0,
        "advisory_count": 0, "financial_count": 0,
        "review_by_rule": {}, "advisory_by_rule": {}, "financial_by_rule": {},
    }


def _detail_pair(*, claims=("C1",), extra_rules=0, available=True):
    """Authored neutral organ rows plus strictly unchanged unrelated rows."""
    rule_groups = {rule: "treatment_pricing_2_4" for rule in _ORGAN_RULES}
    rule_groups[_UNRELATED_RULE] = "lab"
    rule_groups.update({f"public.unrelated_{i:04d}": "lab" for i in range(extra_rules)})
    baseline_rows = []
    for claim in claims if available else (None,):
        for rule in rule_groups:
            matched = rule == _ORGAN_RULES[1] and available
            status = "evaluated" if (matched or rule not in _ORGAN_RULES) and available else "missing_inputs"
            reason = None if status == "evaluated" else "missing_required_inputs"
            row = {
                "evaluation_id": build_evaluation_id(
                    rule_id=rule, patient_id="P1", claim_id=claim, line_kind="claim", line_id=None,
                ),
                "patient_id": "P1", "claim_id": claim, "rule_id": rule,
                "line_kind": "claim", "line_id": None,
                "evaluation_status": status,
                "decision": "not_matched" if status == "evaluated" else None,
                "required_inputs": ["procedure_category", "source_detail"] if rule in _ORGAN_RULES else [],
                "missing_inputs": ["source_detail"] if status == "missing_inputs" else [],
                "reason": reason,
                "disposition": "not_matched" if status == "evaluated" else "missing_inputs",
                "disposition_reason": reason,
                "source_status": "authored_locator_unverified" if available else "not_evaluated",
                "source_authority": "sut_authored_reference",
                "selected_rule_id": None, "savings_try": None,
                "clinical_eligibility_complete": False,
                "provenance": {"source_file": "public_source.json", "source_sha256": "a" * 64},
            }
            baseline_rows.append(row)
    baseline_rows.sort(key=lambda row: row["evaluation_id"])
    candidate_rows = copy.deepcopy(baseline_rows)
    if available:
        for row in candidate_rows:
            if row["rule_id"] in _ORGAN_RULES:
                row.update(
                    evaluation_status="unavailable", decision=None,
                    required_inputs=[], missing_inputs=[], reason="source_review_required",
                    disposition="unavailable", disposition_reason="source_review_required",
                )
    detail = {
        "schema_version": "wavea-evidence-v2", "roster_version": "public-fixture-v1",
        "patient_id": "P1", "available": available,
        "unavailable_reason": None if available else "claim_context_unavailable",
        "claim_scope_inventory": {
            "context_state": "available" if available else "missing",
            "claims": [{"claim_id": claim, "material_line_ids": []} for claim in claims] if available else [],
        },
        "reviews": [], "advisories": [], "financial_rows": [],
    }
    return (
        {**copy.deepcopy(detail), "evaluations": baseline_rows, "counts": _counts(baseline_rows, rule_groups)},
        {**copy.deepcopy(detail), "evaluations": candidate_rows, "counts": _counts(candidate_rows, rule_groups)},
        rule_groups,
    )


@pytest.mark.parametrize("claims", [("C1",), ("C1", "C2")])
def test_only_three_neutral_organ_rows_can_change_with_exact_claim_ownership(claims):
    old, new, groups = _detail_pair(claims=claims)
    before = copy.deepcopy((old, new))
    transition._check_detail_pair(old, new, groups)
    assert (old, new) == before
    assert sum(row["decision"] is not None for row in new["evaluations"] if row["rule_id"] in _ORGAN_RULES) == 0
    assert all(row["clinical_eligibility_complete"] is False for row in new["evaluations"])


def test_no_header_organ_rows_keep_the_existing_missing_input_state():
    old, new, groups = _detail_pair(available=False)
    transition._check_detail_pair(old, new, groups)
    assert all(row["evaluation_status"] == "missing_inputs" for row in new["evaluations"])


@pytest.mark.parametrize("field,value", [
    ("evaluation_status", "evaluated"), ("decision", "not_matched"), ("decision", False),
    ("decision", 0), ("reason", None), ("reason", "clinical_pass"),
    ("disposition", "permission_or_instruction"), ("disposition_reason", None),
    ("required_inputs", ["invented"]), ("required_inputs", None),
    ("missing_inputs", ["invented"]), ("missing_inputs", None),
])
def test_organ_allowed_field_names_do_not_authorize_arbitrary_new_values(field, value):
    old, new, groups = _detail_pair()
    next(row for row in new["evaluations"] if row["rule_id"] == _ORGAN_RULES[0])[field] = value
    # Preserve the aggregate counters if the altered status happens to be valid.
    # A coherent count alone cannot admit an unreviewed decision/status.
    if field == "evaluation_status":
        new["counts"] = _counts(new["evaluations"], groups)
    with pytest.raises(ValueError):
        transition._check_detail_pair(old, new, groups)


@pytest.mark.parametrize("field,value", [
    ("savings_try", 0), ("savings_try", 0.0), ("savings_try", False),
    ("clinical_eligibility_complete", True), ("selected_rule_id", "invented"),
    ("source_status", "primary_meaning_and_date_verified"),
    ("source_authority", "unreviewed_authority"), ("unexpected", True),
    ("provenance", {"source_file": "other.json", "source_sha256": "b" * 64}),
])
def test_neutral_organ_exception_preserves_money_identity_and_provenance(field, value):
    old, new, groups = _detail_pair()
    next(row for row in new["evaluations"] if row["rule_id"] == _ORGAN_RULES[0])[field] = value
    with pytest.raises(ValueError):
        transition._check_detail_pair(old, new, groups)


@pytest.mark.parametrize("mutation", [
    "foreign_rule", "claim_swap", "patient", "evaluation_id", "duplicate",
    "drop", "reorder", "foreign_group", "foreign_no_header_quarantine",
])
def test_aggregate_equality_does_not_replace_stable_row_ownership(mutation):
    old, new, groups = _detail_pair(claims=("C1", "C2"))
    row = next(item for item in new["evaluations"] if item["rule_id"] == _ORGAN_RULES[0])
    if mutation == "foreign_rule":
        row["rule_id"] = _UNRELATED_RULE
    elif mutation == "claim_swap":
        row["claim_id"] = "C2" if row["claim_id"] == "C1" else "C1"
    elif mutation == "patient":
        row["patient_id"] = "P2"
    elif mutation == "evaluation_id":
        row["evaluation_id"] = "invented"
    elif mutation == "duplicate":
        new["evaluations"].append(copy.deepcopy(row))
    elif mutation == "drop":
        new["evaluations"].remove(row)
    elif mutation == "reorder":
        new["evaluations"].reverse()
    elif mutation == "foreign_group":
        groups[_ORGAN_RULES[0]] = "lab"
    else:
        old, new, groups = _detail_pair(available=False)
        row = next(item for item in new["evaluations"] if item["rule_id"] == _ORGAN_RULES[0])
        row.update(
            evaluation_status="unavailable", decision=None, reason="source_review_required",
            disposition="unavailable", disposition_reason="source_review_required",
            required_inputs=[], missing_inputs=[],
        )
    if mutation not in {"foreign_rule", "foreign_group"}:
        new["counts"] = _counts(new["evaluations"], groups)
    with pytest.raises(ValueError):
        transition._check_detail_pair(old, new, groups)


def test_identical_neutral_projection_on_an_unrelated_rule_is_not_authorized():
    old, new, groups = _detail_pair()
    row = next(item for item in new["evaluations"] if item["rule_id"] == _UNRELATED_RULE)
    row.update(
        evaluation_status="unavailable", decision=None, reason="source_review_required",
        disposition="unavailable", disposition_reason="source_review_required",
        required_inputs=[], missing_inputs=[],
    )
    new["counts"] = _counts(new["evaluations"], groups)
    with pytest.raises(ValueError):
        transition._check_detail_pair(old, new, groups)


def test_neutral_transition_checks_every_evaluation_beyond_preview_limit():
    old, new, groups = _detail_pair(extra_rules=510)
    assert len(new["evaluations"]) > 500
    transition._check_detail_pair(old, new, groups)
    new["evaluations"][-1]["reason"] = "unreviewed_late_evaluation"
    with pytest.raises(ValueError):
        transition._check_detail_pair(old, new, groups)


@pytest.mark.parametrize("mutation", ["rule", "group", "bool", "float", "evaluation", "sparse"])
def test_status_counter_mutations_cannot_be_hidden_by_the_organ_exception(mutation):
    old, new, groups = _detail_pair()
    if mutation == "rule":
        new["counts"]["by_rule"][_ORGAN_RULES[0]]["unavailable"] += 1
    elif mutation == "group":
        new["counts"]["by_group"]["lab"]["unavailable"] += 1
    elif mutation == "bool":
        new["counts"]["by_rule"][_ORGAN_RULES[0]]["unavailable"] = True
    elif mutation == "float":
        new["counts"]["by_rule"][_ORGAN_RULES[0]]["unavailable"] = 1.0
    elif mutation == "evaluation":
        new["counts"]["evaluation_count"] += 1
    else:
        new["counts"]["financial_count"] = 1
    with pytest.raises(ValueError):
        transition._check_detail_pair(old, new, groups)


def _public_projection_pair():
    """Construct all five producer outputs from public, authored fixture facts."""
    old_detail, new_detail, groups = _detail_pair()
    provenance = {
        "mode": "synthetic_demo", "is_synthetic": True,
        "claim_source": "claims", "clinical_source": "clean",
    }
    result = []
    for number, detail in ((1, old_detail), (2, new_detail)):
        coverage = {
            "drug": {"pilot_rule_count": number, "reviewed_through": "2026-10-05"},
            "materials": {"encoded_corpus_rows": number, "clinical_eligibility_complete": False},
        }
        count = detail["counts"]
        report = {
            "patient_id": "P1", "sgk_uplift_try": 0.0,
            "recommended_actions": [{"action_id": "unrelated", "savings_try": None}],
            "drug_indication": {"coverage_scope": copy.deepcopy(coverage["drug"]), "findings": []},
            "materials": {"specialty_coverage_scope": copy.deepcopy(coverage["materials"]), "findings": []},
            "wavea_coverage": {
                "schema_version": detail["schema_version"],
                "available": True, "unavailable_reason": None, "tracked_rule_count": len(groups),
                "evaluation_count": len(detail["evaluations"]), "by_group": copy.deepcopy(count["by_group"]),
            },
            "data_source": copy.deepcopy(provenance), "clinical_eligibility_complete": False,
        }
        bill = copy.deepcopy(report)
        bill.update(claim_id="C1", report_scope="bill")
        detail = {**copy.deepcopy(detail), "data_source": copy.deepcopy(provenance)}
        index_counts = {key: copy.deepcopy(count[key]) for key in (
            "by_rule", "by_group", "review_count", "advisory_count", "financial_count",
        )}
        patient_counts = {**copy.deepcopy(index_counts), "evaluation_count": len(detail["evaluations"])}
        index = {
            "schema_version": "wavea-evidence-v2", "roster_version": "public-fixture-v1",
            "capability": "draft", "available": True, "n_patients": 1,
            "n_patients_unavailable": 0,
            "patients": {"P1": {"available": True, "unavailable_reason": None, "counts": patient_counts}},
            "counts": index_counts, "evidence_rows": [], "data_source": copy.deepcopy(provenance),
        }
        rules = {"rule_set_id": "treatment_pricing_2_4", "rules": [
            {"rule_id": rule, "sut_section": "2.4.2.A", "gate_b_sources": [],
             "condition": {"procedure_category": "organ_transplant"},
             "action": {"payment_tr": "Public authored fixture"},
             **({"source_review_required": True} if number == 2 else {})}
            for rule in _ORGAN_RULES
        ]}
        raw_evaluations = [{field: copy.deepcopy(row[field]) for field in (
            "evaluation_id", "patient_id", "claim_id", "rule_id", "line_kind", "line_id",
            "evaluation_status", "decision", "reason", "required_inputs", "missing_inputs",
        )} for row in detail["evaluations"]]
        legacy_rows = []
        if number == 2:
            for rule in _ORGAN_RULES:
                # Authored independently of the verifier's expected-row helper.
                legacy_rows.append({
                    "patient_id": "P1", "claim_id": "C1", "rule_id": rule, "family": "treatment_pricing_2_4",
                    "legacy_row": {
                        "rule": "treatment_pricing_2_4", "severity": "review",
                        "message": "Kaynak incelemesi tamamlanmadığı için bu kuralın değerlendirmesi ertelendi.",
                        "savings_try": 0.0, "risk_amount": 0.0, "sut_section": "2.4.2.A",
                        "rule_id": rule, "billable": None, "material_outcome": "review_required",
                        "annex_basis": None,
                        "details": {"prose_rule_set": "treatment_pricing_2_4", "source_status": "review_required",
                                    "clinical_eligibility_complete": False},
                    },
                })
        raw = {"claims": ["C1"], "evaluations": raw_evaluations, "legacy_rows": legacy_rows, "matches": []}
        result.append({
            "tables": {
                "patient_billing_report_rows": {"P1": report},
                "patient_bill_billing_report_rows": {"P1::C1": bill},
                "wavea_evidence_detail": {"P1": detail},
                "wavea_bill_evidence_detail": {"P1::C1": copy.deepcopy(detail)},
                "wavea_evidence_index": index,
            },
            "coverage": coverage, "rule_groups": copy.deepcopy(groups), "rules": rules,
            "neutral_raw": {"patients": {"P1": copy.deepcopy(raw)}, "bills": {"P1::C1": copy.deepcopy(raw)}},
        })
    return tuple(result)


def test_full_five_table_projection_is_source_derived_and_payment_neutral():
    old, new = _public_projection_pair()
    before = copy.deepcopy((old, new))
    result = transition._check_projection_pair(old, new)
    assert result == {"changed_organ_evaluations": 6, "neutral_raw_rows": 6}
    assert (old, new) == before


@pytest.mark.parametrize("mutation", [
    "patient_detail", "bill_detail", "patient_report", "bill_report",
    "index_root", "index_patient", "index_duplicate_patient", "spurious_index_field",
    "sparse_extra", "bill_claim_owner", "raw_claim", "raw_missing_organ", "raw_extra_organ",
    "raw_payable", "raw_eligibility", "raw_match", "raw_provenance",
    "coverage_unknown", "coverage_unapproved_date", "report_money", "report_null",
    "report_list_order", "report_provenance", "missing_table", "extra_table",
])
def test_all_five_tables_and_raw_rows_must_match_their_own_source_derivation(mutation):
    old, new = _public_projection_pair()
    tables = new["tables"]
    rule = _ORGAN_RULES[0]
    if mutation in {"patient_detail", "bill_detail"}:
        table, key = ("wavea_evidence_detail", "P1") if mutation == "patient_detail" else ("wavea_bill_evidence_detail", "P1::C1")
        tables[table][key]["counts"]["by_rule"][rule]["unavailable"] += 1
    elif mutation in {"patient_report", "bill_report"}:
        table, key = ("patient_billing_report_rows", "P1") if mutation == "patient_report" else ("patient_bill_billing_report_rows", "P1::C1")
        tables[table][key]["wavea_coverage"]["by_group"]["treatment_pricing_2_4"]["unavailable"] += 1
    elif mutation == "index_root":
        tables["wavea_evidence_index"]["counts"]["by_rule"][rule]["unavailable"] += 1
    elif mutation == "index_patient":
        tables["wavea_evidence_index"]["patients"]["P1"]["counts"]["by_rule"][rule]["unavailable"] += 1
    elif mutation == "index_duplicate_patient":
        tables["wavea_evidence_index"]["patients"]["P2"] = copy.deepcopy(tables["wavea_evidence_index"]["patients"]["P1"])
    elif mutation == "spurious_index_field":
        tables["wavea_evidence_index"]["counts"]["new_flag"] = True
    elif mutation == "sparse_extra":
        tables["wavea_bill_evidence_detail"]["P1::C1"]["reviews"].append({"rule_id": rule})
    elif mutation == "bill_claim_owner":
        tables["patient_bill_billing_report_rows"]["P1::C1"]["claim_id"] = "C2"
    elif mutation.startswith("raw_"):
        raw = new["neutral_raw"]["bills"]["P1::C1"]
        row = raw["legacy_rows"][0]
        if mutation == "raw_claim":
            raw["claims"] = ["C2"]
        elif mutation == "raw_missing_organ":
            raw["legacy_rows"].pop()
        elif mutation == "raw_extra_organ":
            raw["legacy_rows"].append(copy.deepcopy(row))
        elif mutation == "raw_payable":
            row["legacy_row"]["billable"] = True
        elif mutation == "raw_eligibility":
            row["legacy_row"]["details"]["clinical_eligibility_complete"] = True
        elif mutation == "raw_match":
            raw["matches"].append({"rule_id": rule})
        else:
            row["legacy_row"]["details"]["source_status"] = "primary_meaning_and_date_verified"
    elif mutation == "coverage_unknown":
        new["coverage"]["drug"]["new_counter"] = 1
    elif mutation == "coverage_unapproved_date":
        new["coverage"]["drug"]["reviewed_through"] = "2026-10-06"
    elif mutation == "missing_table":
        tables.pop("wavea_evidence_index")
    elif mutation == "extra_table":
        tables["new_release_table"] = {}
    else:
        report = tables["patient_bill_billing_report_rows"]["P1::C1"]
        if mutation == "report_money":
            report["sgk_uplift_try"] = 0
        elif mutation == "report_null":
            report["sgk_uplift_try"] = None
        elif mutation == "report_list_order":
            report["recommended_actions"].append({"action_id": "new", "savings_try": None})
        else:
            report["data_source"]["is_synthetic"] = False
    with pytest.raises(ValueError):
        transition._check_projection_pair(old, new)


def _json_digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _report(projections, candidate="a" * 40):
    """Public synthetic metadata; never labeled as a real release receipt."""
    identity = {
        "contract": transition.TRANSITION_CONTRACT,
        "baseline_code_sha": transition.BASELINE_CODE_SHA, "baseline_tree": transition.BASELINE_TREE,
        "candidate_code_sha": candidate,
        "history": {
            "product_anchor_sha": transition.PRODUCT_ANCHOR_SHA, "product_anchor_tree": transition.PRODUCT_ANCHOR_TREE,
            "candidate_sha": candidate, "descendant_commits": [candidate],
            "authorized_changed_paths": ["scripts/deploy/verify_source_refresh_transition.py"],
        },
        "verifier": {
            "verifier_sha": candidate,
            "files": {"scripts/deploy/verify_source_refresh_transition.py": "c" * 64},
            "source_sha256": _json_digest({"scripts/deploy/verify_source_refresh_transition.py": "c" * 64}),
        },
        "replay_checkouts": {
            "baseline": {"code_sha": transition.BASELINE_CODE_SHA, "source_sha256": "b" * 64, "file_count": 1},
            "candidate": {"code_sha": candidate, "source_sha256": "c" * 64, "file_count": 1},
        },
        "same_input": {
            "status": "same_input_bytes_verified", "input_bytes_sha256": transition.INPUT_BYTES_SHA256,
            "input_file_count": 12, "data_mode": "synthetic_demo",
            "baseline": {"roster_sha256": "d" * 64, "source_hash": transition.BASELINE_SOURCE_HASH,
                         "config_hash": transition.BASELINE_CONFIG_HASH},
            "candidate": {"roster_sha256": "f" * 64, "source_hash": "c" * 64,
                          "config_hash": transition.BASELINE_CONFIG_HASH},
            "paths": {
                side: {"claim_source": "claims", "clinical_source": "clean"}
                for side in ("baseline", "candidate")
            },
        },
        "source_intent": {
            "source_path": transition.SOURCE_PATH, "baseline_blob": transition.BASELINE_SOURCE_BLOB,
            "product_blob": transition.PRODUCT_SOURCE_BLOB, "neutral_rule_ids": sorted(_ORGAN_RULES),
            "clinical_eligibility_complete": False, "quarantine_is_payment_neutral": True,
        },
        "baseline_replay_sha256": _json_digest(projections["baseline"]),
        "candidate_replay_sha256": _json_digest(projections["candidate"]),
    }
    report = {
        "status": "source_refresh_transition_verified", **identity,
        "changed_organ_evaluations": 6,
        "neutral_raw_rows": 6, "patient_count": 1, "bill_count": 1,
        "protected_fields": "all_other_fields_type_exact_unchanged",
    }
    report["transition_sha256"] = _json_digest({key: value for key, value in report.items() if key != "status"})
    return report


def _public_proof():
    old, new = _public_projection_pair()
    projections = {"baseline": old, "candidate": new}
    return transition._issue_proof(_report(projections), projections)


def test_fresh_typed_proof_exposes_detached_immutable_metadata():
    proof = _public_proof()
    proof.report["status"] = "forged"
    proof.projections["candidate"]["tables"].clear()
    assert proof.report["status"] == "source_refresh_transition_verified"
    assert len(proof.projections["candidate"]["tables"]) == 5
    with pytest.raises(FrozenInstanceError):
        proof._report_json = "{}"


def _cached_value(proof, table, side):
    value = copy.deepcopy(proof.projections[side]["tables"][table])
    if table == "wavea_evidence_index":
        value["build_id"] = side + "-build"
    elif table.startswith("wavea_"):
        for row in value.values():
            row["build_id"] = side + "-build"
    return value


@pytest.mark.parametrize("table", [
    "patient_billing_report_rows", "patient_bill_billing_report_rows",
    "wavea_evidence_detail", "wavea_bill_evidence_detail", "wavea_evidence_index",
])
def test_normalizer_verifies_all_five_whole_payloads_and_preserves_build_identity(table):
    proof = _public_proof()
    values = {side: _cached_value(proof, table, side) for side in ("baseline", "candidate")}
    before = copy.deepcopy(values)
    old = transition.normalize_transition_content(table, values["baseline"], side="baseline", proof=proof)
    new = transition.normalize_transition_content(table, values["candidate"], side="candidate", proof=proof)
    assert values == before
    assert old == values["baseline"]
    if table == "wavea_evidence_index":
        assert new["build_id"] == "candidate-build"
        old.pop("build_id")
        new.pop("build_id")
    elif table.startswith("wavea_"):
        for key in old:
            assert new[key]["build_id"] == "candidate-build"
            old[key].pop("build_id")
            new[key].pop("build_id")
    assert _json_digest(new) == _json_digest(old)


@pytest.mark.parametrize("value", [3, None, False, 2.0, "2"])
def test_allowed_coverage_path_still_requires_its_exact_independent_source_value(value):
    proof = _public_proof()
    rows = _cached_value(proof, "patient_bill_billing_report_rows", "candidate")
    rows["P1::C1"]["drug_indication"]["coverage_scope"]["pilot_rule_count"] = value
    with pytest.raises(ValueError):
        transition.normalize_transition_content("patient_bill_billing_report_rows", rows, side="candidate", proof=proof)


@pytest.mark.parametrize("side", ["baseline", "candidate"])
@pytest.mark.parametrize("mutation", ["unknown", "missing", "extra_entity", "null", "int", "bool", "list_order", "third_count"])
def test_full_replay_comparison_rejects_every_unproved_field_type_order_and_entity(side, mutation):
    proof = _public_proof()
    table = "patient_billing_report_rows"
    rows = _cached_value(proof, table, side)
    row = rows["P1"]
    if mutation == "unknown":
        row["new_field"] = True
    elif mutation == "missing":
        row.pop("clinical_eligibility_complete")
    elif mutation == "extra_entity":
        rows["P2"] = copy.deepcopy(row)
    elif mutation in {"null", "int", "bool"}:
        row["sgk_uplift_try"] = {"null": None, "int": 0, "bool": False}[mutation]
    elif mutation == "list_order":
        row["recommended_actions"].insert(0, {"action_id": "new", "savings_try": None})
    else:
        row["wavea_coverage"]["by_group"]["treatment_pricing_2_4"]["unavailable"] += 1
    with pytest.raises(ValueError):
        transition.normalize_transition_content(table, rows, side=side, proof=proof)


@pytest.mark.parametrize("mutation", ["mapping", "unsealed", "copied_seal", "historical_dict"])
def test_forged_dict_or_reconstructed_proof_cannot_supply_normalization_permission(mutation):
    proof = _public_proof()
    rows = _cached_value(proof, "patient_billing_report_rows", "candidate")
    if mutation == "mapping":
        supplied = proof.report
    elif mutation == "unsealed":
        supplied = transition.SourceRefreshProof(proof._report_json, proof._projections_json)
    elif mutation == "copied_seal":
        altered = proof.projections
        altered["candidate"]["tables"]["patient_billing_report_rows"]["P1"]["sgk_uplift_try"] = 99.0
        supplied = transition.SourceRefreshProof(proof._report_json, json.dumps(altered), proof._seal)
    else:
        supplied = {"status": "clinical_semantic_transition_verified", "contract": historical.TRANSITION_CONTRACT}
    with pytest.raises(ValueError):
        transition.normalize_transition_content("patient_billing_report_rows", rows, side="candidate", proof=supplied)


def _reseal_report(report):
    report["transition_sha256"] = _json_digest({
        key: value for key, value in report.items() if key not in {"status", "transition_sha256"}
    })


@pytest.mark.parametrize("mutation", [
    "contract", "status", "baseline_sha", "baseline_tree", "anchor_sha", "anchor_tree",
    "verifier_sha", "missing_verifier", "wrong_verifier_hash", "malformed_verifier_path",
    "duplicate_commit", "empty_history", "unauthorized_path", "extra_history_key",
    "unknown_future_asset", "wrong_source_blob", "eligibility_true", "eligibility_zero",
    "neutral_one", "neutral_rule", "wrong_input_hash", "input_count_float", "wrong_mode",
    "old_source_hash", "old_config_hash", "new_config_hash", "new_replay_sha",
    "replay_count_bool", "unknown_replay_field", "counts_bool", "zero_count", "missing_count",
])
def test_rehashed_reports_still_require_exact_source_input_history_and_typed_neutrality(mutation):
    proof = _public_proof()
    report = proof.report
    if mutation == "contract":
        report["contract"] = "future-source-refresh-v2"
    elif mutation == "status":
        report["status"] = "clinical_semantic_transition_verified"
    elif mutation == "baseline_sha":
        report["baseline_code_sha"] = "f" * 40
    elif mutation == "baseline_tree":
        report["baseline_tree"] = "f" * 40
    elif mutation == "anchor_sha":
        report["history"]["product_anchor_sha"] = "f" * 40
    elif mutation == "anchor_tree":
        report["history"]["product_anchor_tree"] = "f" * 40
    elif mutation == "verifier_sha":
        report["verifier"]["verifier_sha"] = "f" * 40
    elif mutation == "missing_verifier":
        report["verifier"]["files"].clear()
    elif mutation == "wrong_verifier_hash":
        report["verifier"]["source_sha256"] = "f" * 64
    elif mutation == "malformed_verifier_path":
        report["verifier"]["files"]["scripts/deploy/../bad.py"] = "f" * 64
        report["verifier"]["source_sha256"] = _json_digest(report["verifier"]["files"])
    elif mutation == "duplicate_commit":
        report["history"]["descendant_commits"].append(report["candidate_code_sha"])
    elif mutation == "empty_history":
        report["history"]["descendant_commits"] = []
    elif mutation == "unauthorized_path":
        report["history"]["authorized_changed_paths"] = ["src/bilun/domain/clinical.py"]
    elif mutation == "extra_history_key":
        report["history"]["skip_product_proof"] = True
    elif mutation == "unknown_future_asset":
        report["history"]["authorized_changed_paths"] = ["data/gazette/source_authority/2027.json"]
    elif mutation == "wrong_source_blob":
        report["source_intent"]["product_blob"] = "f" * 40
    elif mutation == "eligibility_true":
        report["source_intent"]["clinical_eligibility_complete"] = True
    elif mutation == "eligibility_zero":
        report["source_intent"]["clinical_eligibility_complete"] = 0
    elif mutation == "neutral_one":
        report["source_intent"]["quarantine_is_payment_neutral"] = 1
    elif mutation == "neutral_rule":
        report["source_intent"]["neutral_rule_ids"][-1] = "unreviewed_rule"
    elif mutation == "wrong_input_hash":
        report["same_input"]["input_bytes_sha256"] = "f" * 64
    elif mutation == "input_count_float":
        report["same_input"]["input_file_count"] = 12.0
    elif mutation == "wrong_mode":
        report["same_input"]["data_mode"] = "real_claims"
    elif mutation == "old_source_hash":
        report["same_input"]["baseline"]["source_hash"] = "f" * 64
    elif mutation == "old_config_hash":
        report["same_input"]["baseline"]["config_hash"] = "f" * 64
    elif mutation == "new_config_hash":
        report["same_input"]["candidate"]["config_hash"] = "f" * 64
    elif mutation == "new_replay_sha":
        report["replay_checkouts"]["candidate"]["code_sha"] = "f" * 40
    elif mutation == "replay_count_bool":
        report["replay_checkouts"]["baseline"]["file_count"] = True
    elif mutation == "unknown_replay_field":
        report["replay_checkouts"]["baseline"]["tolerate_source_drift"] = True
    elif mutation == "counts_bool":
        report["changed_organ_evaluations"] = True
    elif mutation == "zero_count":
        report["bill_count"] = 0
    else:
        report.pop("neutral_raw_rows")
    _reseal_report(report)
    with pytest.raises(ValueError):
        transition.validate_transition_report_contract(report)


@pytest.mark.parametrize("field,value", [
    ("status", "unverified"), ("input_bytes_sha256", "f" * 64),
    ("input_file_count", 11), ("input_file_count", 12.0), ("data_mode", "real_claims"),
])
def test_wrong_same_input_identity_stops_before_reading_any_source(tmp_path, monkeypatch, field, value):
    inputs = _public_proof().report["same_input"]
    inputs[field] = value
    monkeypatch.setattr(transition, "_roster", lambda *_: pytest.fail("Bad input identity reached source reads"))
    with pytest.raises(ValueError):
        transition.verify_transition(
            request=_request(), baseline_roster=tmp_path / "old.json", candidate_roster=tmp_path / "new.json",
            baseline_meta={"code_sha": transition.BASELINE_CODE_SHA, "source_hash": transition.BASELINE_SOURCE_HASH,
                           "config_hash": transition.BASELINE_CONFIG_HASH},
            candidate_meta={"code_sha": "a" * 40, "config_hash": transition.BASELINE_CONFIG_HASH},
            same_input=inputs, python_executable=Path("/usr/bin/python3"), dependency_roots=(),
            expected_candidate_sha="a" * 40,
        )


@pytest.fixture
def bound_replay_case(replay_checkout_pair, monkeypatch):
    """Keep real roster/object gates; isolate controller/history and producers.

    The producer double returns handwritten public expectations, not values
    extracted from the cache under verification.
    """
    records = replay_checkout_pair
    old, new = _public_projection_pair()
    expected = {"baseline": old, "candidate": new}
    old_sha = records["baseline"]["roster"]["code_sha"]
    new_sha = records["candidate"]["roster"]["code_sha"]
    monkeypatch.setattr(transition, "BASELINE_CODE_SHA", old_sha)
    binding = _report(expected, new_sha)["verifier"]
    history = _report(expected, new_sha)["history"]
    monkeypatch.setattr(transition, "_guard_code_binding", lambda *_: copy.deepcopy(binding))
    monkeypatch.setattr(transition, "_verify_candidate_history", lambda *_: copy.deepcopy(history))
    events = []
    original_binding = transition._replay_checkout_binding

    def side_for(checkout):
        return next(side for side, record in records.items() if Path(record["roster"]["checkout"]) == Path(checkout))

    def bind(roster):
        events.append(("binding", side_for(roster["checkout"])))
        return original_binding(roster)

    def replay(checkout, *_args, **_kwargs):
        side = side_for(checkout)
        events.append(("replay", side))
        return copy.deepcopy(expected[side])

    def intent(*_args):
        events.append(("intent", None))
        return _report(expected, new_sha)["source_intent"]

    monkeypatch.setattr(transition, "_replay_checkout_binding", bind)
    monkeypatch.setattr(transition, "_replay_projection", replay)
    monkeypatch.setattr(transition, "_source_intent", intent)
    metas = {
        "baseline": {"code_sha": old_sha, "source_hash": transition.BASELINE_SOURCE_HASH,
                     "config_hash": transition.BASELINE_CONFIG_HASH},
        "candidate": {"code_sha": new_sha, "source_hash": "c" * 64, "config_hash": transition.BASELINE_CONFIG_HASH},
    }
    inputs = _report(expected, new_sha)["same_input"]
    for side, record in records.items():
        inputs[side] = {
            "roster_sha256": hashlib.sha256(record["roster_path"].read_bytes()).hexdigest(),
            "source_hash": metas[side]["source_hash"], "config_hash": metas[side]["config_hash"],
        }
    arguments = {
        "request": _request(new_sha), "baseline_roster": records["baseline"]["roster_path"],
        "candidate_roster": records["candidate"]["roster_path"],
        "baseline_meta": metas["baseline"], "candidate_meta": metas["candidate"],
        "same_input": inputs, "python_executable": Path("/usr/bin/python3"),
        "dependency_roots": (), "expected_candidate_sha": new_sha,
    }
    return records, arguments, events, replay, intent


def test_both_independent_sources_are_rechecked_before_after_and_at_final_proof(bound_replay_case):
    records, arguments, events, _, _ = bound_replay_case
    before = {Path(row["path"]): Path(row["path"]).read_bytes()
              for record in records.values() for row in record["roster"]["sources"]}
    proof = transition.verify_transition(**arguments)
    assert proof.report["status"] == "source_refresh_transition_verified"
    assert len(proof.projections["candidate"]["tables"]) == 5
    assert set(events[:2]) == {("binding", "baseline"), ("binding", "candidate")}
    assert events[2] == ("replay", "baseline")
    assert [side for kind, side in events if kind == "replay"] == ["baseline", "candidate"]
    assert all(events.count(("binding", side)) >= 4 for side in ("baseline", "candidate"))
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("side", ["baseline", "candidate"])
def test_source_drift_stops_before_either_producer_runs(bound_replay_case, side):
    records, arguments, events, _, _ = bound_replay_case
    regenerated = _hidden_source_change(records[side])
    arguments["same_input"][side]["roster_sha256"] = hashlib.sha256(records[side]["roster_path"].read_bytes()).hexdigest()
    records[side]["roster"] = regenerated
    with pytest.raises(ValueError, match="Git"):
        transition.verify_transition(**arguments)
    assert not any(kind in {"replay", "intent"} for kind, _ in events)


@pytest.mark.parametrize("worker_side", ["baseline", "candidate"])
@pytest.mark.parametrize("mutated_side", ["baseline", "candidate"])
def test_either_worker_cannot_mutate_either_source_before_its_next_read(
    bound_replay_case, monkeypatch, worker_side, mutated_side,
):
    records, arguments, events, replay, _ = bound_replay_case
    def worker(checkout, *args, **kwargs):
        result = replay(checkout, *args, **kwargs)
        if events[-1] == ("replay", worker_side):
            _hidden_source_change(records[mutated_side])
        return result
    monkeypatch.setattr(transition, "_replay_projection", worker)
    with pytest.raises(ValueError, match="Git"):
        transition.verify_transition(**arguments)
    assert not any(kind == "intent" for kind, _ in events)


@pytest.mark.parametrize("side", ["baseline", "candidate"])
def test_source_changed_after_replay_is_rejected_before_proof_is_issued(bound_replay_case, monkeypatch, side):
    records, arguments, _, _, intent = bound_replay_case
    def mutate_after_replay(*args):
        result = intent(*args)
        _hidden_source_change(records[side])
        return result
    monkeypatch.setattr(transition, "_source_intent", mutate_after_replay)
    with pytest.raises(ValueError, match="Git"):
        transition.verify_transition(**arguments)


def test_prepare_carries_the_same_new_opt_in_to_semantic_rehearsal_and_issuer(machine, monkeypatch):
    manifest, spec, _, original = machine
    request = _request(spec["target_sha"])
    spec["clinical_transition"] = request
    private_json(manifest, spec)
    calls = []
    semantic, rehearse, issue = (
        preparation.verify_candidate_semantic_checkpoint, preparation._rehearse, preparation.issue_wavea_activation,
    )
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


@pytest.fixture
def namespace_preparation_identity(machine):
    manifest, spec, _, _ = machine
    old = old_python_context(Path(spec["bundle_root"]).parent, environment_sha256="b" * 64)
    spec["clinical_transition"] = _request(spec["target_sha"])
    spec["schema_version"] = preparation.DEPENDENCY_CHAIN_SCHEMA
    spec["dependency_roots"] = [str(path) for path in old.dependencies]
    private_json(manifest, spec)
    loaded = preparation.load_preparation_manifest(manifest)
    loaded["bundle_root"].mkdir(mode=0o700)
    record, digest = old_python_record(loaded["bundle_root"], old, runtime_sha256="a" * 64)
    loaded["_old_backend_python_identity_record_sha256"] = digest
    return loaded, record, digest


def test_prepare_writes_exact_new_request_for_namespace_without_running_a_child(
    namespace_preparation_identity, monkeypatch,
):
    loaded, record, digest = namespace_preparation_identity
    commands = []
    monkeypatch.setattr(preparation, "_run", lambda argv, **kwargs: commands.append((argv, kwargs)))
    _REAL_PREPARE_REHEARSE(loaded, loaded["live_backend_runtime"], loaded["live_frontend_runtime"],
                           "a" * 64, "b" * 64, "c" * 64)
    assert len(commands) == 1
    argv, _ = commands[0]
    assert argv[:3] == ["unshare", "--net", "--"]
    assert argv[argv.index("--old-backend-python-identity-record") + 1] == str(record)
    assert argv[argv.index("--old-backend-python-identity-record-sha256") + 1] == digest
    assert argv[argv.index("--backend-python") + 1] == str(loaded["backend_python"])
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--dependency-root"] == [
        str(path) for path in loaded["dependency_roots"]
    ]
    path = Path(argv[argv.index("--clinical-transition") + 1])
    assert json.loads(path.read_text()) == loaded["clinical_transition"]
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("fault", ["absent", "tampered"])
def test_namespace_request_rejects_unverified_old_identity_before_running_a_child(
    namespace_preparation_identity, monkeypatch, fault,
):
    loaded, record, _ = namespace_preparation_identity
    if fault == "absent":
        record.unlink()
        message = "private independent file"
    else:
        record.write_bytes(record.read_bytes() + b"\n")
        message = "identity differs from its frozen observation"
    commands = []
    monkeypatch.setattr(preparation, "_run", lambda argv, **kwargs: commands.append((argv, kwargs)))
    with pytest.raises(ValueError, match=message):
        _REAL_PREPARE_REHEARSE(loaded, loaded["live_backend_runtime"], loaded["live_frontend_runtime"],
                               "a" * 64, "b" * 64, "c" * 64)
    assert commands == []
    assert not (loaded["bundle_root"] / "clinical-transition-request.json").exists()


def test_semantic_checkpoint_dispatches_the_new_typed_proof_and_keeps_release_unready(tmp_path, monkeypatch):
    """Orchestration-only seam; strict cache/producer gates are tested separately."""
    baseline, candidate, roster = _current_fixture(tmp_path)
    proof = _public_proof()
    request = _request(proof.report["candidate_code_sha"])
    called = []
    monkeypatch.setattr(semantics, "verify_same_input_rosters", lambda *_args, **_kwargs: proof.report["same_input"])
    def replay(**kwargs):
        assert kwargs["request"] == request
        assert kwargs["expected_candidate_sha"] == kwargs["expected_verifier_sha"] == request["expected_candidate_sha"]
        assert kwargs["baseline_roster"] == tmp_path / "old-roster.json"
        assert kwargs["candidate_roster"] == roster
        called.append("replay")
        return proof
    def parity(*_args, **kwargs):
        assert kwargs["clinical_transition"] is proof
        called.append("parity")
        return {"candidate_code_sha": request["expected_candidate_sha"], "source_hash": "c" * 64}, {}
    monkeypatch.setattr(transition, "verify_transition", replay)
    monkeypatch.setattr(semantics, "_check_legacy_parity", parity)
    monkeypatch.setattr(semantics, "_check_evidence", lambda *_args: ({}, []))
    before = {path: path.read_bytes() for path in (baseline, candidate)}
    report = semantics.verify_candidate_semantic_checkpoint(
        baseline, baseline_build_id="baseline", candidate_db=candidate, candidate_build_id="candidate",
        source_roster=roster, baseline_roster=tmp_path / "old-roster.json", build_config_environment={},
        clinical_transition=request, python_executable=Path(sys.executable), dependency_roots=(Path(sys.base_prefix),),
    )
    assert report["clinical_transition"] == proof.report
    assert report["release_ready"] is False
    assert called == ["replay", "parity"]
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("mutation", [None, "saved", "saved_hash", "relative_locator", "wrong_head"])
def test_issuer_binds_new_request_to_fresh_semantics_and_saved_mirror(tmp_path, monkeypatch, mutation):
    arguments, request, fresh, source_path, raw_path = _issuer_transition_fixture(tmp_path, monkeypatch)
    request["contract"] = transition.TRANSITION_CONTRACT
    fresh["clinical_transition"] = _public_proof().report
    source_sha = private_json(source_path, fresh)
    raw = json.loads(raw_path.read_text())
    raw["source_report_sha256"] = source_sha
    if mutation == "saved":
        saved = copy.deepcopy(fresh)
        saved["clinical_transition"]["neutral_raw_rows"] += 1
        raw["source_report_sha256"] = private_json(source_path, saved)
    elif mutation == "saved_hash":
        raw["source_report_sha256"] = "f" * 64
    elif mutation == "relative_locator":
        raw["source_report_path"] = source_path.name
    elif mutation == "wrong_head":
        request.update(expected_candidate_sha="f" * 40, expected_verifier_sha="f" * 40)
    private_json(raw_path, raw)
    original = issuer.verify_candidate_semantic_checkpoint
    def semantic(*args, **kwargs):
        assert kwargs["clinical_transition"] == request
        return original(*args, **kwargs)
    monkeypatch.setattr(issuer, "verify_candidate_semantic_checkpoint", semantic)
    if mutation is None:
        assert issuer.issue_wavea_activation(**arguments)["status"] == "private_activation_receipt_issued"
    else:
        with pytest.raises(ValueError):
            issuer.issue_wavea_activation(**arguments)
        assert not arguments["key_path"].exists()
        assert not arguments["receipt_path"].exists()


def _private_refresh_fixture(tmp_path):
    path, observed_path, candidate, runtime, rehearsal_report, observation = sealed_rehearsal(tmp_path)
    fresh = _public_proof().report
    candidate["source_hash"] = fresh["same_input"]["candidate"]["source_hash"]
    observation["logical_tuple"]["cache"]["source_hash"] = candidate["source_hash"]
    observation["tuple_sha256"] = _json_digest(observation["logical_tuple"])
    rehearsal_report["candidate_tuple_sha256"] = observation["tuple_sha256"]
    rehearsal_report["candidate_tuple_observation_sha256"] = private_json(observed_path, observation)
    producer = runtime / "scripts/deploy/verify_source_refresh_transition.py"
    producer.write_text("# public reviewed test verifier\n")
    files = {
        "scripts/deploy/verify_source_refresh_transition.py": hashlib.sha256(producer.read_bytes()).hexdigest(),
        "scripts/deploy/rehearse_wavea_same_port.py": hashlib.sha256((runtime / "scripts/deploy/rehearse_wavea_same_port.py").read_bytes()).hexdigest(),
    }
    fresh["verifier"] = {"verifier_sha": candidate["code_sha"], "files": files, "source_sha256": _json_digest(files)}
    _reseal_report(fresh)
    rehearsal_report["same_input_proof_sha256"] = private_json(tmp_path / "same-input-rehearsal.json", fresh["same_input"])
    rehearsal_report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", fresh)
    private_json(path, rehearsal_report)
    return path, observed_path, candidate, runtime, rehearsal_report, fresh


def test_private_rehearsal_accepts_only_fresh_exact_new_source_and_input_proof(tmp_path):
    path, observed, candidate, runtime, _, fresh = _private_refresh_fixture(tmp_path)
    assert verify_private_rehearsal(path, observed, candidate=candidate, backend_runtime=runtime,
                                    clinical_transition=fresh)["status"] == "private_pair_rehearsal_verified"


@pytest.mark.parametrize("mutation", [
    "unknown_contract", "wrong_status", "candidate_sha", "verifier_sha", "missing_closure",
    "changed_source", "same_input", "saved_mirror", "saved_hash", "downgrade", "unrequested",
])
def test_private_rehearsal_rejects_resealed_unknown_or_stale_new_transition_proofs(tmp_path, mutation):
    path, observed, candidate, runtime, rehearsal_report, fresh = _private_refresh_fixture(tmp_path)
    supplied = fresh
    if mutation == "unknown_contract":
        fresh["contract"] = "unknown_source_refresh"
    elif mutation == "wrong_status":
        fresh["status"] = "clinical_semantic_transition_verified"
    elif mutation == "candidate_sha":
        fresh["candidate_code_sha"] = "f" * 40
    elif mutation == "verifier_sha":
        fresh["verifier"]["verifier_sha"] = "f" * 40
    elif mutation == "missing_closure":
        fresh["verifier"]["files"].clear()
    elif mutation == "changed_source":
        (runtime / "scripts/deploy/verify_source_refresh_transition.py").write_text("# unreviewed source\n")
    elif mutation == "same_input":
        fresh["same_input"]["input_bytes_sha256"] = "f" * 64
    elif mutation == "saved_mirror":
        saved = copy.deepcopy(fresh)
        saved["neutral_raw_rows"] += 1
        _reseal_report(saved)
        rehearsal_report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", saved)
    elif mutation == "saved_hash":
        rehearsal_report["clinical_transition_report_sha256"] = "f" * 64
    elif mutation == "downgrade":
        rehearsal_report["schema_version"] = "wavea-real-pair-rehearsal-v1"
    else:
        supplied = None
    if mutation not in {"changed_source", "saved_mirror", "saved_hash", "downgrade", "unrequested"}:
        _reseal_report(fresh)
        rehearsal_report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", fresh)
    private_json(path, rehearsal_report)
    with pytest.raises(ValueError):
        verify_private_rehearsal(path, observed, candidate=candidate, backend_runtime=runtime, clinical_transition=supplied)


@pytest.mark.parametrize("mutation", [None, "unknown_contract", "wrong_head"])
def test_namespace_rehearsal_carries_new_request_and_rejects_wrong_identity_before_children(
    tmp_path, monkeypatch, mutation,
):
    """All processes and HTTP services in this fixture are fabricated."""
    args, work, events, _ = fixture_rehearsal(tmp_path, monkeypatch)
    request = _request()
    if mutation == "unknown_contract":
        request["contract"] = "unreviewed_transition"
    elif mutation == "wrong_head":
        request.update(expected_candidate_sha="f" * 40, expected_verifier_sha="f" * 40)
    request_path = tmp_path / "request.json"
    private_json(request_path, request)
    args.extend(("--clinical-transition", str(request_path)))
    proof = _public_proof()
    calls = []
    class Database:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
    monkeypatch.setattr(rehearsal.duckdb, "connect", lambda *_args, **_kwargs: Database())
    monkeypatch.setattr(rehearsal, "_build_metadata", lambda *_args: {"code_sha": "a" * 40})
    def verify(**kwargs):
        assert kwargs["request"] == request
        assert kwargs["expected_candidate_sha"] == kwargs["expected_verifier_sha"] == "a" * 40
        calls.append("source_replay")
        return proof
    def normalize(reports, **kwargs):
        assert kwargs["proof"] is proof
        calls.append(kwargs["side"])
        return reports
    monkeypatch.setattr(transition, "verify_transition", verify)
    monkeypatch.setattr(transition, "normalize_transition_http_reports", normalize)
    if mutation is None:
        rehearsal.main(args)
        assert calls == ["source_replay", "baseline", "candidate"]
        assert json.loads((work / "clinical-transition-rehearsal.json").read_text()) == proof.report
    else:
        with pytest.raises(ValueError):
            rehearsal.main(args)
        assert calls == []
        assert not any(event.startswith("start:") for event in events)


def _http_packages(monkeypatch):
    """Fabricated serializer seam; source worker serializer tests remain separate."""
    proof = _public_proof()
    packages = {}
    for side in ("baseline", "candidate"):
        tables = proof.projections[side]["tables"]
        reports = {
            "/api/billing-report/P1": copy.deepcopy(tables["patient_billing_report_rows"]["P1"]),
            "/api/billing-report/P1/bills/C1": copy.deepcopy(tables["patient_bill_billing_report_rows"]["P1::C1"]),
        }
        packages[side] = fabricated_transport(
            monkeypatch, reports, code_sha=proof.report[side + "_code_sha"], repository=Path("/fixture") / side,
        )
    return proof, packages


@pytest.mark.parametrize("view", ["draft", "legacy"])
def test_http_projection_uses_the_same_owned_patient_and_bill_replay(view, monkeypatch):
    proof, packages = _http_packages(monkeypatch)
    old, new = packages["baseline"], packages["candidate"]
    old_reports = old.draft_reports if view == "draft" else {key: semantics._legacy_report(row) for key, row in old.complete_reports.items()}
    new_reports = new.draft_reports if view == "draft" else {key: semantics._legacy_report(row) for key, row in new.complete_reports.items()}
    normalized = transition.normalize_transition_http_reports(
        new_reports, side="candidate", proof=proof, transport=new, baseline_transport=old, view=view,
    )
    assert _json_digest(normalized) == _json_digest(old_reports)
    assert normalized["/api/billing-report/P1"]["sgk_uplift_try"] == 0.0


@pytest.mark.parametrize("mutation", [
    "dto_money", "dto_unknown", "missing_bill", "different_path", "unknown_view",
    "mapping_transport", "unsealed_transport", "wrong_source", "coherent_raw_and_dto",
])
def test_http_transport_cannot_hide_unproved_dto_raw_identity_or_routing_changes(monkeypatch, mutation):
    proof, packages = _http_packages(monkeypatch)
    baseline, package = packages["baseline"], packages["candidate"]
    reports, view = package.draft_reports, "draft"
    if mutation == "dto_money":
        reports["/api/billing-report/P1"]["sgk_uplift_try"] = None
    elif mutation == "dto_unknown":
        reports["/api/billing-report/P1"]["unreviewed"] = True
    elif mutation == "missing_bill":
        reports.pop("/api/billing-report/P1/bills/C1")
    elif mutation == "different_path":
        reports["/api/billing-report/P%31"] = reports.pop("/api/billing-report/P1")
    elif mutation == "unknown_view":
        view = "ignore_defaults"
    elif mutation == "mapping_transport":
        package = {"draft_reports": reports, "code_sha": proof.report["candidate_code_sha"]}
    elif mutation == "unsealed_transport":
        package = rehearsal.PinnedReportTransport(package._binding_json, package._raw_json,
                                                   package._complete_json, package._draft_json)
    elif mutation == "wrong_source":
        package = baseline
    else:
        raw = package.raw_reports
        raw["/api/billing-report/P1"]["sgk_uplift_try"] = None
        package = fabricated_transport(monkeypatch, raw, code_sha=proof.report["candidate_code_sha"],
                                       repository=Path("/fixture/candidate"))
        reports = package.draft_reports
    with pytest.raises(ValueError):
        transition.normalize_transition_http_reports(
            reports, side="candidate", proof=proof, transport=package, baseline_transport=baseline, view=view,
        )


@pytest.fixture
def public_authored_sources(tmp_path, monkeypatch):
    old, new = _public_projection_pair()
    checkout = tmp_path / "authored-source"
    checkout.mkdir()
    _git(checkout, "init", "-q", "-b", "main")
    _git(checkout, "config", "user.name", "Bilun Public Authored Source Test")
    _git(checkout, "config", "user.email", "source-proof@example.invalid")
    _git(checkout, "config", "commit.gpgsign", "false")
    baseline = _commit(checkout, transition.SOURCE_PATH, json.dumps(old["rules"]), "old authored organ source")
    product = _commit(checkout, transition.SOURCE_PATH, json.dumps(new["rules"]), "three neutral organ sources")
    monkeypatch.setattr(transition, "BASELINE_CODE_SHA", baseline)
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_SHA", product)
    monkeypatch.setattr(transition, "BASELINE_SOURCE_BLOB", _git(checkout, "rev-parse", f"{baseline}:{transition.SOURCE_PATH}"))
    monkeypatch.setattr(transition, "PRODUCT_SOURCE_BLOB", _git(checkout, "rev-parse", f"{product}:{transition.SOURCE_PATH}"))
    return {"checkout": str(checkout)}, old, new


def test_both_compiled_rule_sets_match_independent_authored_git_objects(public_authored_sources):
    roster, old, new = public_authored_sources
    proof = transition._source_intent(roster, roster, old, new)
    assert proof["neutral_rule_ids"] == sorted(_ORGAN_RULES)
    assert proof["clinical_eligibility_complete"] is False
    assert proof["quarantine_is_payment_neutral"] is True


@pytest.mark.parametrize("mutation", ["baseline_blob", "product_blob", "old_compiled", "new_compiled", "payment_source", "missing_quarantine"])
def test_authored_source_proof_rejects_forged_blobs_compiled_changes_and_payment_authority(
    public_authored_sources, monkeypatch, mutation,
):
    roster, old, new = public_authored_sources
    if mutation == "baseline_blob":
        monkeypatch.setattr(transition, "BASELINE_SOURCE_BLOB", "f" * 40)
    elif mutation == "product_blob":
        monkeypatch.setattr(transition, "PRODUCT_SOURCE_BLOB", "f" * 40)
    elif mutation == "old_compiled":
        old["rules"]["rules"][0]["condition"] = {"invented": True}
    elif mutation == "new_compiled":
        new["rules"]["rules"][0]["action"]["payment_tr"] = "Unreviewed payment permission"
    elif mutation == "payment_source":
        new["rules"]["rules"][0]["gate_b_sources"] = ["invented_clause"]
    else:
        new["rules"]["rules"][0]["source_review_required"] = False
    with pytest.raises(ValueError):
        transition._source_intent(roster, roster, old, new)


@pytest.mark.parametrize("mutation", ["partial", "status_mismatch", "wrong_anchor"])
def test_real_signed_startup_rejects_partial_or_unknown_source_refresh_even_after_resealing(
    signed_bundle, mutation,
):
    """Exercise real signature/sidecar/startup loaders on a fabricated host."""
    source_path = signed_bundle.root / "semantic.json"
    source = json.loads(source_path.read_text())
    proof = source["clinical_transition"]
    proof["contract"] = transition.TRANSITION_CONTRACT
    if mutation != "status_mismatch":
        proof["status"] = "source_refresh_transition_verified"
    if mutation == "wrong_anchor":
        proof["history"] = {"product_anchor_sha": "f" * 40}
    private_json(source_path, source)
    signed_startup._reseal_semantic(signed_bundle, mirror_rehearsal=True)
    with pytest.raises(ValueError):
        signed_startup._candidate_load(signed_bundle)
