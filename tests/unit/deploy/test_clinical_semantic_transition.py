"""Adversarial tests for the source-bound clinical release transition.

Small replay doubles below exercise normalization and strict cache comparison;
they are not evidence that a production source transition is approved.  The
private retained-cache regression separately runs the genuine pinned runtimes.
"""

from __future__ import annotations

import copy
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import FrozenInstanceError
from pathlib import Path

import duckdb
import pytest
import yaml

from scripts.deploy import verify_clinical_semantic_transition as transition
from scripts.deploy import rehearse_wavea_same_port as rehearsal
from scripts.deploy import prepare_single_vps_release as preparation
from scripts.deploy import issue_wavea_activation as issuer
from scripts.deploy.release_sidecar import _load_private_json
from scripts.deploy.verify_private_rehearsal import verify_private_rehearsal
from scripts.deploy.verify_candidate_semantics import _current_content_parity
from scripts.deploy.verify_same_input import _config_hash, verify_same_input_rosters
from src.bilun.cache.builder import SUT_CLAIM_FILENAMES, SUT_CLEAN_FILENAMES
from src.bilun.db.hashing import source_hash_from_files
from src.bilun.domain.billing.drug_indication_findings import _route_evidence
from src.bilun.domain.prose_rules import drug_indication as prose
from tests.unit.deploy.test_generate_candidate_source_roster import _candidate, _roster
from tests.unit.deploy.test_prepare_single_vps_release import machine as machine
from tests.unit.deploy.test_issue_wavea_activation import _issuer_fixture
from tests.unit.deploy.test_same_port_rehearsal import private_json, sealed_rehearsal
from tests.unit.deploy.test_verify_candidate_semantics import (
    _current_fixture,
    _mutate_payload,
)


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


def _approved_frontend_configs() -> tuple[str, str]:
    root = Path(transition.__file__).resolve().parents[2]
    source = (root / "frontend/next.config.ts").read_text(encoding="utf-8")
    line = "  images: { maximumDiskCacheSize: 0 },\n"
    before = source.replace(line, "")
    after = before.replace("  productionBrowserSourceMaps: false,\n",
                           "  productionBrowserSourceMaps: false,\n" + line)
    for content, blob, digest in (
        (before, "d4b1241ba2e8a2bef5fbfb69e1a0a05c652182cc",
         "fd6785328e47d801e0ff70e715b42f5823dacce290f2df81ac94b4ca6f526d1a"),
        (after, "cbc2b7e615dba97135d1221375eac00c41e2ca05",
         "b5c2bf140e79eb8f0cb19f713f26e53a09ea32ebef8338c29ff3752c70669da3"),
    ):
        raw = content.encode()
        assert hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() == blob
        assert hashlib.sha256(raw).hexdigest() == digest
    return before, after


@pytest.fixture
def source_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Use real Git history without requiring old objects in shallow CI."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.name", "Bilun Transition Test")
    _git(checkout, "config", "user.email", "transition@example.invalid")
    _git(checkout, "config", "commit.gpgsign", "false")
    _commit(checkout, transition.FRONTEND_CONFIG_PATH, _approved_frontend_configs()[0], "original config")
    baseline = _commit(checkout, "src/bilun/product.py", "old source\n", "baseline")
    baseline_tree = _git(checkout, "rev-parse", "HEAD^{tree}")
    anchor = _commit(checkout, "src/bilun/product.py", "reviewed source\n", "reviewed product")
    monkeypatch.setattr(transition, "BASELINE_CODE_SHA", baseline)
    monkeypatch.setattr(transition, "BASELINE_TREE", baseline_tree)
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_SHA", anchor)
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_TREE", _git(checkout, "rev-parse", "HEAD^{tree}"))
    path = "tests/unit/deploy/test_clinical_semantic_transition.py"
    assert path in transition.AUTHORIZED_TOOLING_PATHS
    candidate = _commit(checkout, path, "# reviewed transition regression\n", "tooling only")
    return checkout, baseline, anchor, candidate, path


def test_production_source_pins_remain_exact():
    assert transition.BASELINE_CODE_SHA == "3f5540cf199cb464b1fca1d7d7d6ff024d5edc3b"
    assert transition.PRODUCT_ANCHOR_SHA == "3e0e0c6d88fdcd4817e0a7a84b3361184d78b1ea"
    assert transition.PRODUCT_ANCHOR_TREE == "6f102905fc1e150de89eefdac91fddbfdff10d10"
    assert transition.INPUT_BYTES_SHA256 == "84efa030d2c5e927f8afb94ce8c494647e398e236d02b560a3d281531231d1f3"
    assert transition.BASELINE_SOURCE_HASH == "c211fa8490d12db89b5456a071e6a20775c271ade49270776374c0f292b49b92"
    assert transition.BASELINE_CONFIG_HASH == "474642a8400d820435d8dbe3f40524ffd357edf8d40cc77a9621fd56b6b5921b"
    assert ".github/workflows/deploy.yml" not in transition.AUTHORIZED_TOOLING_PATHS
    assert transition.FRONTEND_CONFIG_PATH == "frontend/next.config.ts"
    assert transition.FRONTEND_CONFIG_PATH not in transition.AUTHORIZED_TOOLING_PATHS
    assert transition.FRONTEND_CONFIG_BASELINE_BLOB == "d4b1241ba2e8a2bef5fbfb69e1a0a05c652182cc"
    assert transition.FRONTEND_CONFIG_CANDIDATE_BLOB == "cbc2b7e615dba97135d1221375eac00c41e2ca05"
    _approved_frontend_configs()


@pytest.mark.parametrize("path,authorized", [
    ("src/bilun/api/wavea_activation.py", True),
    ("tests/integration/deploy/test_signed_transition_startup.py", True),
    ("tests/integration/deploy/test_generated_launcher_startup.py", True),
    ("src/bilun/api/schemas.py", False),
    ("src/bilun/api/wavea_activation_extra.py", False),
    ("tests/integration/deploy/test_signed_transition_startup_extra.py", False),
    ("tests/integration/deploy/test_generated_launcher_startup_extra.py", False),
    ("tests/integration/deploy/generated_launcher_startup.py", False),
])
def test_startup_source_exception_is_an_exact_approved_path(source_history, path, authorized):
    checkout, _, _, _, _ = source_history
    candidate = _commit(checkout, path, "# source-closed fixture\n", "startup boundary fixture")
    if authorized:
        assert transition._verify_candidate_history(checkout, candidate)
    else:
        with pytest.raises(ValueError):
            transition._verify_candidate_history(checkout, candidate)


def _retained_meta() -> dict:
    return {
        "code_sha": transition.BASELINE_CODE_SHA,
        "source_hash": "c211fa8490d12db89b5456a071e6a20775c271ade49270776374c0f292b49b92",
        "config_hash": "474642a8400d820435d8dbe3f40524ffd357edf8d40cc77a9621fd56b6b5921b",
    }


def test_transition_opt_in_has_exact_external_identities_and_defaults_to_strict():
    assert transition.validate_transition_request(None) is None
    request = {
        "contract": transition.TRANSITION_CONTRACT,
        "expected_candidate_sha": transition.PRODUCT_ANCHOR_SHA,
        "expected_verifier_sha": "e" * 40,
    }
    validated = transition.validate_transition_request(request)
    assert validated == request and validated is not request
    request["expected_candidate_sha"] = "f" * 40
    assert validated["expected_candidate_sha"] == transition.PRODUCT_ANCHOR_SHA


@pytest.mark.parametrize("mutation", ["extra_field", "wrong_contract", "short_candidate", "boolean_verifier", "missing_verifier"])
def test_transition_request_cannot_enable_unknown_or_partial_contracts(mutation):
    request = {
        "contract": transition.TRANSITION_CONTRACT,
        "expected_candidate_sha": transition.PRODUCT_ANCHOR_SHA,
        "expected_verifier_sha": "e" * 40,
    }
    if mutation == "extra_field":
        request["skip_parity"] = True
    elif mutation == "wrong_contract":
        request["contract"] = "generic-drift-allowlist"
    elif mutation == "short_candidate":
        request["expected_candidate_sha"] = "3e0e0c6d"
    elif mutation == "boolean_verifier":
        request["expected_verifier_sha"] = True
    else:
        request.pop("expected_verifier_sha")
    with pytest.raises(ValueError, match="unknown contract or identity"):
        transition.validate_transition_request(request)


def test_preparation_opt_in_binds_both_identities_to_the_exact_target(machine):
    manifest, spec, _, _ = machine
    request = {
        "contract": transition.TRANSITION_CONTRACT,
        "expected_candidate_sha": spec["target_sha"],
        "expected_verifier_sha": spec["target_sha"],
    }
    spec["clinical_transition"] = request
    private_json(manifest, spec)
    loaded = preparation.load_preparation_manifest(manifest)
    assert loaded["clinical_transition"] == request


@pytest.mark.parametrize("field", ["expected_candidate_sha", "expected_verifier_sha"])
def test_preparation_rejects_a_transition_request_for_another_head(machine, field):
    manifest, spec, _, _ = machine
    request = {
        "contract": transition.TRANSITION_CONTRACT,
        "expected_candidate_sha": spec["target_sha"],
        "expected_verifier_sha": spec["target_sha"],
    }
    request[field] = "f" * 40
    spec["clinical_transition"] = request
    private_json(manifest, spec)
    with pytest.raises(ValueError, match="exact target/tooling head"):
        preparation.load_preparation_manifest(manifest)


def test_tooling_descendant_uses_external_head_identity(source_history):
    checkout, _, _, candidate, _ = source_history
    transition._verify_candidate_history(checkout, candidate)


def test_reviewed_frontend_config_has_exact_history_and_disk_binding(source_history):
    checkout, _, _, original, tooling_path = source_history
    untouched = transition._verify_candidate_history(checkout, original)
    assert untouched["frontend_config"]["git_blob"] == transition.FRONTEND_CONFIG_BASELINE_BLOB
    assert "frontend_config_transition" not in untouched
    config = transition.FRONTEND_CONFIG_PATH
    changed = _commit(checkout, config, _approved_frontend_configs()[1], "disable image disk cache")
    candidate = _commit(checkout, tooling_path, "# reviewed follow-up test\n", "reviewed tooling")
    before = (checkout / config).read_bytes()
    report = transition._verify_candidate_history(checkout, candidate)
    assert report["frontend_config_transition"] == {
        "commit_sha": changed, "path": config,
        "baseline_blob": transition.FRONTEND_CONFIG_BASELINE_BLOB,
        "candidate_blob": transition.FRONTEND_CONFIG_CANDIDATE_BLOB,
    }
    assert report["frontend_config"] == {
        "path": config, "git_mode": "100644", "git_blob": transition.FRONTEND_CONFIG_CANDIDATE_BLOB,
        "sha256": "b5c2bf140e79eb8f0cb19f713f26e53a09ea32ebef8338c29ff3752c70669da3",
    }
    assert set(report["authorized_changed_paths"]) == {config, tooling_path}
    assert (checkout / config).read_bytes() == before


@pytest.mark.parametrize("mutation", ["nonzero", "remove", "format", "proxy", "sourcemaps"])
def test_frontend_config_rejects_every_other_content_blob(source_history, mutation):
    checkout, _, _, _, _ = source_history
    before, after = _approved_frontend_configs()
    content = {
        "nonzero": after.replace("maximumDiskCacheSize: 0", "maximumDiskCacheSize: 1"),
        "remove": before.replace("  productionBrowserSourceMaps: false,\n", ""),
        "format": after + "\n",
        "proxy": after.replace("http://localhost:8001", "http://localhost:8002"),
        "sourcemaps": after.replace("productionBrowserSourceMaps: false", "productionBrowserSourceMaps: true"),
    }[mutation]
    candidate = _commit(checkout, transition.FRONTEND_CONFIG_PATH, content, "unreviewed config")
    with pytest.raises(ValueError, match="single reviewed blob change"):
        transition._verify_candidate_history(checkout, candidate)


def test_frontend_config_rejects_an_unreviewed_predecessor(source_history, monkeypatch):
    checkout, _, _, _, _ = source_history
    config = transition.FRONTEND_CONFIG_PATH
    before, after = _approved_frontend_configs()
    anchor = _commit(checkout, config, before + "\n", "different predecessor")
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_SHA", anchor)
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_TREE", _git(checkout, "rev-parse", "HEAD^{tree}"))
    candidate = _commit(checkout, config, after, "otherwise reviewed successor")
    with pytest.raises(ValueError, match="single reviewed blob change"):
        transition._verify_candidate_history(checkout, candidate)


def test_frontend_config_cannot_be_added_without_the_reviewed_predecessor(source_history, monkeypatch):
    checkout, _, _, _, _ = source_history
    config = transition.FRONTEND_CONFIG_PATH
    _git(checkout, "rm", config)
    _git(checkout, "commit", "-qm", "anchor without config")
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_SHA", _git(checkout, "rev-parse", "HEAD"))
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_TREE", _git(checkout, "rev-parse", "HEAD^{tree}"))
    candidate = _commit(checkout, config, _approved_frontend_configs()[1], "add reviewed successor")
    with pytest.raises(ValueError, match="single reviewed blob change"):
        transition._verify_candidate_history(checkout, candidate)


@pytest.mark.parametrize("mutation", ["revert", "bad_then_reviewed", "reviewed_then_bad_then_reviewed",
                                    "delete_then_reviewed", "rename_then_reviewed"])
def test_frontend_config_rejects_intermediate_mutations_even_with_valid_final_bytes(source_history, mutation):
    checkout, _, _, _, _ = source_history
    config = transition.FRONTEND_CONFIG_PATH
    before, after = _approved_frontend_configs()
    if mutation != "bad_then_reviewed":
        _commit(checkout, config, after, "reviewed config")
    if mutation == "revert":
        candidate = _commit(checkout, config, before, "revert reviewed config")
    else:
        if mutation == "delete_then_reviewed":
            _git(checkout, "rm", config)
            _git(checkout, "commit", "-qm", "delete config")
        elif mutation == "rename_then_reviewed":
            _git(checkout, "mv", config, "frontend/next.config.extra.ts")
            _git(checkout, "commit", "-qm", "rename config")
            _git(checkout, "rm", "frontend/next.config.extra.ts")
        else:
            _commit(checkout, config, after.replace("maximumDiskCacheSize: 0", "maximumDiskCacheSize: 9"),
                    "unreviewed temporary config")
        candidate = _commit(checkout, config, after, "restore exact reviewed bytes")
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, candidate)


@pytest.mark.parametrize("mutation", ["executable", "symlink", "deleted", "parent_symlink"])
def test_frontend_config_rejects_non_regular_git_entries(source_history, mutation):
    checkout, _, _, _, _ = source_history
    config = transition.FRONTEND_CONFIG_PATH
    source = checkout / config
    if mutation == "executable":
        source.write_text(_approved_frontend_configs()[1])
        source.chmod(0o755)
    elif mutation == "symlink":
        source.unlink()
        source.symlink_to("next.config.other.ts")
    elif mutation == "parent_symlink":
        _git(checkout, "rm", config)
        source.parent.symlink_to("missing-frontend", target_is_directory=True)
    else:
        source.unlink()
    _git(checkout, "add", "frontend")
    _git(checkout, "commit", "-qm", "unreviewed config entry")
    candidate = _git(checkout, "rev-parse", "HEAD")
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, candidate)


@pytest.mark.parametrize("index_flag", ["--assume-unchanged", "--skip-worktree"])
def test_frontend_config_disk_bytes_cannot_hide_behind_index_flags(source_history, index_flag):
    checkout, _, _, _, _ = source_history
    config = transition.FRONTEND_CONFIG_PATH
    after = _approved_frontend_configs()[1]
    candidate = _commit(checkout, config, after, "reviewed config")
    _git(checkout, "update-index", index_flag, config)
    (checkout / config).write_text(after.replace("maximumDiskCacheSize: 0", "maximumDiskCacheSize: 1"))
    assert _git(checkout, "diff", "--name-only") == ""
    with pytest.raises(ValueError, match="disk bytes differ"):
        transition._verify_candidate_history(checkout, candidate)


@pytest.mark.parametrize("mutation", ["symlink", "hardlink", "missing", "executable", "parent_symlink"])
def test_frontend_config_disk_identity_is_independent_and_canonical(source_history, tmp_path, mutation):
    checkout, _, _, _, _ = source_history
    config = transition.FRONTEND_CONFIG_PATH
    after = _approved_frontend_configs()[1]
    candidate = _commit(checkout, config, after, "reviewed config")
    source = checkout / config
    shared = tmp_path / "shared-config.ts"
    shared.write_text(after)
    if mutation in {"symlink", "hardlink", "missing"}:
        source.unlink()
        if mutation == "symlink":
            source.symlink_to(shared)
        elif mutation == "hardlink":
            source.hardlink_to(shared)
    elif mutation == "parent_symlink":
        source.parent.rename(checkout / "linked-frontend")
        source.parent.symlink_to("linked-frontend", target_is_directory=True)
    else:
        source.chmod(0o755)
    with pytest.raises(ValueError, match="independent regular disk file"):
        transition._verify_candidate_history(checkout, candidate)


def test_ordered_auth_tooling_descendant_uses_external_head_identity(source_history):
    checkout, _, _, semantic_head, semantic_path = source_history
    source_root = Path(transition.__file__).resolve().parents[2]
    auth_paths = ("scripts/deploy/probe_auth.py", "scripts/deploy/paired_release.py")
    auth_commits = [
        _commit(checkout, path, (source_root / path).read_text(), "reviewed auth tooling")
        for path in auth_paths
    ]
    report = transition._verify_candidate_history(checkout, auth_commits[-1])
    assert report["descendant_commits"] == [semantic_head, *auth_commits]
    assert set(report["authorized_changed_paths"]) == {semantic_path, *auth_paths}
    with pytest.raises(ValueError, match="explicit candidate SHA"):
        transition._verify_candidate_history(checkout, semantic_head)


def test_history_rejects_wrong_external_head(source_history):
    checkout, baseline, _, _, _ = source_history
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, baseline)


@pytest.mark.parametrize("path", [
    "src/bilun/product.py",
    "data/gazette/prose_rules/drug_indication_prose.json",
    "data/synthetic/sut/claims/drug_claim_lines.parquet",
    ".github/workflows/deploy.yml",
    "scripts/deploy/unrelated_security_bypass.py",
    "scripts/deploy/future_probe_auth.py",
    "src/bilun/api/auth.py",
    "frontend/src/middleware.ts",
    "frontend/next.config.extra.ts",
    "frontend/next.config.ts.extra",
    ".venv/lib/python3.13/site-packages/sitecustomize.py",
    "tasks/todo.md",
])
def test_history_rejects_unrelated_source_input_and_deployment_changes(source_history, path):
    checkout, _, _, _, _ = source_history
    candidate = _commit(checkout, path, "unreviewed change\n", "unrelated")
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, candidate)


def test_reverted_product_mutation_still_invalidates_descendant_history(source_history):
    checkout, _, _, _, _ = source_history
    _commit(checkout, "src/bilun/product.py", "unreviewed transient source\n", "product mutation")
    candidate = _commit(checkout, "src/bilun/product.py", "reviewed source\n", "restore final bytes")
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, candidate)


def test_history_rejects_wrong_reviewed_anchor_tree(source_history, monkeypatch):
    checkout, _, _, candidate, _ = source_history
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_TREE", "0" * 40)
    with pytest.raises(ValueError):
        transition._verify_candidate_history(checkout, candidate)


@pytest.fixture
def controller_guard(tmp_path, monkeypatch):
    checkout = tmp_path / "guard-checkout"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.name", "Bilun Transition Test")
    _git(checkout, "config", "user.email", "transition@example.invalid")
    _git(checkout, "config", "commit.gpgsign", "false")
    relative = "scripts/deploy/verify_clinical_semantic_transition.py"
    source = Path(transition.__file__).read_text(encoding="utf-8")
    running_root = tmp_path / "running"
    _commit(checkout, transition.FRONTEND_CONFIG_PATH, _approved_frontend_configs()[0], "original config")
    for path in (
        "src/bilun/product.py", "data/gazette/catalog.json",
        "scripts/bilun/generate.py", "scripts/sut/generate.py",
        "scripts/__init__.py", "pyproject.toml", "requirements.txt",
    ):
        _commit(checkout, path, "reviewed fixture bytes\n", "reviewed controller dependency")
    sha = _commit(checkout, relative, source, "exact running guard")
    _git(tmp_path, "clone", "-q", "--no-local", str(checkout), str(running_root))
    running_guard = running_root / relative
    monkeypatch.setattr(transition, "__file__", str(running_guard))
    return checkout, running_root, sha, relative, source


def test_running_guard_must_match_exact_committed_tooling_bytes(controller_guard):
    checkout, running_root, sha, relative, source = controller_guard
    binding = transition._guard_code_binding(checkout, sha)
    assert binding["verifier_sha"] == sha
    assert set(binding["files"]) == {
        relative, "src/bilun/product.py", "data/gazette/catalog.json",
        "scripts/bilun/generate.py", "scripts/sut/generate.py",
        "scripts/__init__.py", "pyproject.toml", "requirements.txt",
    }
    changed = _commit(checkout, relative, source + "\n# unreviewed guard mutation\n", "different guard")
    _git(running_root, "fetch", "-q", "origin", changed)
    _git(running_root, "update-ref", "HEAD", changed)
    with pytest.raises(ValueError, match="source/catalog bytes differ from reviewed Git"):
        transition._guard_code_binding(checkout, changed)


@pytest.mark.parametrize("successor", [False, True])
def test_controller_closure_binds_the_frontend_config_outside_generic_files(controller_guard, successor):
    checkout, running_root, sha, _, _ = controller_guard
    config = transition.FRONTEND_CONFIG_PATH
    if successor:
        sha = _commit(checkout, config, _approved_frontend_configs()[1], "reviewed config")
        _git(running_root, "fetch", "-q", "origin", sha)
        _git(running_root, "checkout", "-q", "--detach", sha)
    binding = transition._guard_code_binding(checkout, sha)
    assert config not in binding["files"]
    assert binding["frontend_config"]["git_blob"] == (
        transition.FRONTEND_CONFIG_CANDIDATE_BLOB if successor else transition.FRONTEND_CONFIG_BASELINE_BLOB
    )
    assert binding["source_sha256"] == transition._digest({
        "files": binding["files"], "frontend_config": binding["frontend_config"],
    })


@pytest.mark.parametrize("mutation", ["hidden_bytes", "symlink", "hardlink", "parent_symlink",
                                    "executable", "missing"])
def test_running_controller_frontend_config_rejects_disk_identity_and_byte_drift(controller_guard, tmp_path, mutation):
    checkout, running_root, sha, _, _ = controller_guard
    config = transition.FRONTEND_CONFIG_PATH
    source = running_root / config
    before = source.read_bytes()
    shared = tmp_path / "independent-config.ts"
    shared.write_bytes(before)
    if mutation == "hidden_bytes":
        _git(running_root, "update-index", "--assume-unchanged", config)
        source.write_bytes(before + b"\n")
        assert _git(running_root, "diff", "--name-only") == ""
    elif mutation in {"symlink", "hardlink", "missing"}:
        source.unlink()
        if mutation == "symlink":
            source.symlink_to(shared)
        elif mutation == "hardlink":
            source.hardlink_to(shared)
    elif mutation == "parent_symlink":
        source.parent.rename(running_root / "linked-frontend")
        source.parent.symlink_to("linked-frontend", target_is_directory=True)
    else:
        source.chmod(0o755)
    with pytest.raises(ValueError, match="frontend config"):
        transition._guard_code_binding(checkout, sha)


def test_running_controller_rejects_an_unknown_frontend_config_git_blob(controller_guard):
    checkout, running_root, _, _, _ = controller_guard
    config = transition.FRONTEND_CONFIG_PATH
    sha = _commit(checkout, config, _approved_frontend_configs()[1] + "\n", "unreviewed config bytes")
    _git(running_root, "fetch", "-q", "origin", sha)
    _git(running_root, "checkout", "-q", "--detach", sha)
    with pytest.raises(ValueError, match="unreviewed Git blob"):
        transition._guard_code_binding(checkout, sha)


@pytest.mark.parametrize("mutation", ["regular", "symlink", "parent_symlink"])
def test_absent_git_config_cannot_hide_an_untracked_disk_config(controller_guard, tmp_path, mutation):
    checkout, running_root, _, _, _ = controller_guard
    config = transition.FRONTEND_CONFIG_PATH
    _git(checkout, "rm", config)
    _git(checkout, "commit", "-qm", "legacy fixture without config")
    sha = _git(checkout, "rev-parse", "HEAD")
    _git(running_root, "fetch", "-q", "origin", sha)
    _git(running_root, "checkout", "-q", "--detach", sha)
    assert "frontend_config" not in transition._guard_code_binding(checkout, sha)
    source = running_root / config
    if mutation == "parent_symlink":
        target = tmp_path / "external-frontend"
        target.mkdir()
        source.parent.symlink_to(target, target_is_directory=True)
    else:
        source.parent.mkdir()
        if mutation == "regular":
            source.write_text("untracked config\n")
        else:
            source.symlink_to("missing-config.ts")
    with pytest.raises(ValueError, match="no reviewed Git file"):
        transition._guard_code_binding(checkout, sha)


def test_running_guard_requires_its_own_explicit_head(controller_guard):
    checkout, _, sha, relative, source = controller_guard
    changed = _commit(checkout, relative, source + "\n# tooling update\n", "different head")
    with pytest.raises(ValueError, match="HEAD differs from the explicit reviewed identity"):
        transition._guard_code_binding(checkout, changed)
    transition._guard_code_binding(checkout, sha)


@pytest.mark.parametrize("relative", [
    "src/bilun/product.py", "data/gazette/catalog.json",
    "scripts/bilun/generate.py", "scripts/sut/generate.py",
    "scripts/__init__.py", "pyproject.toml", "requirements.txt",
])
def test_running_controller_rejects_source_catalog_and_dependency_byte_drift(controller_guard, relative):
    checkout, running_root, sha, _, _ = controller_guard
    (running_root / relative).write_text("unreviewed controller bytes\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source/catalog bytes differ from reviewed Git"):
        transition._guard_code_binding(checkout, sha)


@pytest.mark.parametrize("relative", [
    "src/unreviewed.py", "data/gazette/unreviewed.json",
    "scripts/deploy/unreviewed.py", "scripts/bilun/unreviewed.json",
    "scripts/sut/unreviewed.yaml",
])
def test_running_controller_rejects_untracked_source_and_catalog_files(controller_guard, relative):
    checkout, running_root, sha, _, _ = controller_guard
    (running_root / relative).write_text("unreviewed shadow\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unreviewed Python/source closure"):
        transition._guard_code_binding(checkout, sha)


@pytest.mark.parametrize("relative", ["src/bilun/product.py", "data/gazette/unreviewed.json"])
def test_running_controller_rejects_source_links(controller_guard, relative):
    checkout, running_root, sha, guard_relative, _ = controller_guard
    path = running_root / relative
    if path.exists():
        path.unlink()
    path.symlink_to(running_root / guard_relative)
    with pytest.raises(ValueError):
        transition._guard_code_binding(checkout, sha)


@pytest.fixture
def replay_checkout_pair(tmp_path):
    """Independent real Git objects and disk rosters for both replay sources."""
    records = {}
    for side in ("baseline", "candidate"):
        root = tmp_path / side
        root.mkdir()
        checkout, sha, claims, clean = _candidate(root)
        if side == "candidate":
            sha = _commit(checkout, "src/bilun/domain/rules.py",
                          "# reviewed candidate source\n", "reviewed candidate source")
        for filename in ("performed_procedure_lines.parquet", "medula_rejection_events.parquet"):
            (claims / filename).write_bytes(b"public synthetic input fixture")
        candidate = checkout, sha, claims, clean
        roster = _roster(candidate)
        roster_path = root / "roster.json"
        private_json(roster_path, roster)
        records[side] = {"candidate": candidate, "roster": roster, "roster_path": roster_path}
    return records


def _hidden_replay_source_change(record: dict, *, relative="src/bilun/domain/rules.py") -> dict:
    """Make Git diff and a freshly self-consistent roster miss object-byte drift."""
    checkout, sha, _, _ = record["candidate"]
    _git(checkout, "update-index", "--assume-unchanged", relative)
    path = checkout / relative
    path.write_text("unreviewed replay source bytes\n", encoding="utf-8")
    assert _git(checkout, "diff", "--name-only", sha, "--", relative) == ""
    committed = subprocess.run(
        ["git", "-C", str(checkout), "show", f"{sha}:{relative}"],
        capture_output=True, check=True,
    ).stdout
    assert committed != path.read_bytes()
    regenerated = _roster(record["candidate"])
    private_json(record["roster_path"], regenerated)
    # The existing real roster loader checks Git diff and all disk hashes;
    # its success is deliberately insufficient proof of the Git source bytes.
    loaded, _ = transition._roster(record["roster_path"], sha)
    assert loaded == regenerated
    return regenerated


def test_both_replay_checkouts_bind_their_own_git_objects_without_writes(replay_checkout_pair):
    for record in replay_checkout_pair.values():
        roster = record["roster"]
        source_paths = [Path(row["path"]) for row in roster["sources"] if row["label"].startswith("repo:")]
        before = {path: path.read_bytes() for path in source_paths}
        binding = transition._replay_checkout_binding(roster)
        assert binding["code_sha"] == roster["code_sha"]
        assert binding["file_count"] == len(source_paths)
        assert len(binding["source_sha256"]) == 64
        assert {path: path.read_bytes() for path in source_paths} == before


@pytest.mark.parametrize("side", ["baseline", "candidate"])
@pytest.mark.parametrize("relative", ["src/bilun/domain/rules.py", "data/gazette/prose_rules/rule.json"])
def test_clean_git_diff_and_current_roster_cannot_replace_git_object_bytes(replay_checkout_pair, side, relative):
    regenerated = _hidden_replay_source_change(replay_checkout_pair[side], relative=relative)
    with pytest.raises(ValueError, match="Git"):
        transition._replay_checkout_binding(regenerated)


@pytest.mark.parametrize("mutation", [
    "missing_repo_row", "additional_repo_row", "duplicate_repo_row", "wrong_code_sha",
    "wrong_checkout", "wrong_row_path", "wrong_row_hash", "wrong_row_size", "changed_head",
    "checkout_link", "source_link", "source_hardlink", "missing_source",
])
def test_replay_git_binding_requires_exact_roster_root_identity_and_files(replay_checkout_pair, tmp_path, mutation):
    record = replay_checkout_pair["baseline"]
    roster = copy.deepcopy(record["roster"])
    checkout, _, _, _ = record["candidate"]
    row = next(item for item in roster["sources"] if item["label"] == "repo:src/bilun/domain/rules.py")
    if mutation == "missing_repo_row":
        roster["sources"].remove(row)
    elif mutation == "additional_repo_row":
        roster["sources"].append({**row, "label": "repo:src/bilun/unreviewed.py"})
    elif mutation == "duplicate_repo_row":
        roster["sources"].append(copy.deepcopy(row))
    elif mutation == "wrong_code_sha":
        roster["code_sha"] = "f" * 40
    elif mutation == "wrong_checkout":
        roster["checkout"] = replay_checkout_pair["candidate"]["roster"]["checkout"]
    elif mutation == "wrong_row_path":
        row["path"] = str(tmp_path / "outside-source.py")
        Path(row["path"]).write_bytes(b"fixture")
    elif mutation == "wrong_row_hash":
        row["sha256"] = "f" * 64
    elif mutation == "wrong_row_size":
        row["size_bytes"] += 1
    elif mutation == "changed_head":
        _commit(checkout, "README.md", "unchanged source, different HEAD\n", "another identity")
    elif mutation == "checkout_link":
        linked = tmp_path / "linked-checkout"
        linked.symlink_to(checkout, target_is_directory=True)
        roster["checkout"] = str(linked)
    elif mutation == "source_link":
        path = Path(row["path"])
        path.unlink()
        path.symlink_to(replay_checkout_pair["candidate"]["candidate"][0] / "src/__init__.py")
    elif mutation == "source_hardlink":
        path = Path(row["path"])
        shared = tmp_path / "shared-source.py"
        shared.write_bytes(path.read_bytes())
        path.unlink()
        path.hardlink_to(shared)
    else:
        Path(row["path"]).unlink()
    with pytest.raises(ValueError):
        transition._replay_checkout_binding(roster)


@pytest.fixture
def replay_binding_case(replay_checkout_pair, monkeypatch):
    """Keep real roster/Git binding; isolate only the pure replay and other gates."""
    records = replay_checkout_pair
    old, new = _authored_route_pair(monkeypatch)
    expected = {}
    for side, projection in (("baseline", old), ("candidate", new)):
        expected[side] = {
            "patients": {"P1": projection}, "bills": {"P1::C1": projection},
            "rules": {}, "source_routes": {},
            "coverage_scope": projection["drug_indication"]["coverage_scope"],
        }
    old_sha = records["baseline"]["roster"]["code_sha"]
    new_sha = records["candidate"]["roster"]["code_sha"]
    monkeypatch.setattr(transition, "BASELINE_CODE_SHA", old_sha)
    monkeypatch.setattr(transition, "_verify_candidate_history", lambda *_args: {"fixture_history": True})
    monkeypatch.setattr(transition, "_guard_code_binding", lambda *_args: {"verifier_sha": new_sha})
    events = []
    active_rosters = {}
    original_binding = transition._replay_checkout_binding

    def side_for(checkout):
        return next(side for side, record in records.items() if Path(record["roster"]["checkout"]) == Path(checkout))

    def bind(roster):
        side = side_for(roster["checkout"])
        active_rosters[side] = roster
        events.append(("binding", side))
        return original_binding(roster)

    def replay(checkout, *_args, **_kwargs):
        side = side_for(checkout)
        events.append(("replay", side))
        return copy.deepcopy(expected[side])

    def intent(*_args):
        events.append(("intent", None))
        return {"public_fixture_intent": True}

    monkeypatch.setattr(transition, "_replay_checkout_binding", bind)
    monkeypatch.setattr(transition, "_replay_projection", replay)
    monkeypatch.setattr(transition, "_source_intent", intent)
    metas = {
        "baseline": _retained_meta(),
        "candidate": {"code_sha": new_sha, "source_hash": "c" * 64, "config_hash": "d" * 64},
    }
    same_input = {
        "status": "same_input_bytes_verified", "input_bytes_sha256": transition.INPUT_BYTES_SHA256,
        "input_file_count": 12, "data_mode": "synthetic_demo",
        **{side: {
            "roster_sha256": hashlib.sha256(record["roster_path"].read_bytes()).hexdigest(),
            "source_hash": metas[side]["source_hash"], "config_hash": metas[side]["config_hash"],
        } for side, record in records.items()},
    }
    arguments = {
        "baseline_roster": records["baseline"]["roster_path"],
        "candidate_roster": records["candidate"]["roster_path"],
        "baseline_meta": metas["baseline"], "candidate_meta": metas["candidate"],
        "same_input": same_input, "python_executable": Path("/usr/bin/python3"),
        "dependency_roots": (), "expected_candidate_sha": new_sha,
    }
    return records, arguments, events, active_rosters, replay, intent


def test_transition_binds_both_git_checkouts_before_workers_and_after_each_worker(replay_binding_case):
    records, arguments, events, _, _, _ = replay_binding_case
    proof = transition.verify_clinical_semantic_transition(**arguments)
    assert proof.report["status"] == "clinical_semantic_transition_verified"
    for side, record in records.items():
        sources = {row["label"][5:]: row["sha256"] for row in record["roster"]["sources"]
                   if row["label"].startswith("repo:")}
        assert proof.report["replay_checkouts"][side] == {
            "code_sha": record["roster"]["code_sha"],
            "source_sha256": _json_sha256(sources), "file_count": len(sources),
        }
    assert set(events[:2]) == {("binding", "baseline"), ("binding", "candidate")}
    assert events[2] == ("replay", "baseline")
    second_worker = events.index(("replay", "candidate"))
    assert {("binding", "baseline"), ("binding", "candidate")} <= set(events[3:second_worker])
    for side in ("baseline", "candidate"):
        assert events.count(("binding", side)) >= 4


@pytest.mark.parametrize("side", ["baseline", "candidate"])
def test_transition_rejects_hidden_git_object_drift_before_any_worker(replay_binding_case, side):
    records, arguments, events, _, _, _ = replay_binding_case
    regenerated = _hidden_replay_source_change(records[side])
    arguments["same_input"][side]["roster_sha256"] = hashlib.sha256(records[side]["roster_path"].read_bytes()).hexdigest()
    records[side]["roster"] = regenerated
    with pytest.raises(ValueError, match="Git"):
        transition.verify_clinical_semantic_transition(**arguments)
    assert not any(kind in {"replay", "intent"} for kind, _ in events)


@pytest.mark.parametrize("worker_side", ["baseline", "candidate"])
@pytest.mark.parametrize("mutated_side", ["baseline", "candidate"])
def test_transition_rechecks_both_git_objects_when_either_worker_mutates_either_checkout(
    replay_binding_case, monkeypatch, worker_side, mutated_side,
):
    records, arguments, events, active_rosters, replay, _ = replay_binding_case

    def mutate_during_worker(checkout, *args, **kwargs):
        result = replay(checkout, *args, **kwargs)
        if events[-1] == ("replay", worker_side):
            regenerated = _hidden_replay_source_change(records[mutated_side])
            active_rosters[mutated_side].clear()
            active_rosters[mutated_side].update(regenerated)
        return result

    monkeypatch.setattr(transition, "_replay_projection", mutate_during_worker)
    with pytest.raises(ValueError, match="Git"):
        transition.verify_clinical_semantic_transition(**arguments)
    assert ("intent", None) not in events
    expected_workers = ["baseline"] if worker_side == "baseline" else ["baseline", "candidate"]
    assert [side for kind, side in events if kind == "replay"] == expected_workers


@pytest.mark.parametrize("side", ["baseline", "candidate"])
def test_transition_rechecks_both_git_objects_before_issuing_final_proof(replay_binding_case, monkeypatch, side):
    records, arguments, events, active_rosters, _, intent = replay_binding_case

    def mutate_after_workers(*args):
        result = intent(*args)
        regenerated = _hidden_replay_source_change(records[side])
        active_rosters[side].clear()
        active_rosters[side].update(regenerated)
        return result

    monkeypatch.setattr(transition, "_source_intent", mutate_after_workers)
    with pytest.raises(ValueError, match="Git"):
        transition.verify_clinical_semantic_transition(**arguments)
    assert [side for kind, side in events if kind == "replay"] == ["baseline", "candidate"]
    assert ("intent", None) in events


@pytest.fixture
def public_source_intent(tmp_path, monkeypatch):
    """Real Git blobs and reviewed public YAML, independent of cached payloads."""
    root = Path(__file__).resolve().parents[3]
    checkout = tmp_path / "source-intent"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.name", "Bilun Transition Test")
    _git(checkout, "config", "user.email", "transition@example.invalid")
    _git(checkout, "config", "commit.gpgsign", "false")
    # Public rows from the old source corpus; no copied patient/cache data.
    old_rows = [{
        "rule_id": key, "sut_section": "4.2.9.A-2",
        "drug_names": ["eritropoietin", "epoetin", "darbepoetin", "aranesp", "binocrit"],
        "icd10_ranges": ["D46", "D47"], "report_required": True,
    } for key in sorted(transition.REMOVED_RULE_IDS)]
    baseline = _commit(checkout, transition.SOURCE_PATH, json.dumps({"rules": old_rows}), "old public aliases")
    baseline_blob = _git(checkout, "rev-parse", f"{baseline}:{transition.SOURCE_PATH}")
    source_text = (root / transition.SOURCE_PATH).read_text(encoding="utf-8")
    _commit(checkout, transition.SOURCE_PATH, source_text, "reviewed public source")
    anchor = _commit(checkout, transition.REVIEW_PACKET_PATH,
                     (root / transition.REVIEW_PACKET_PATH).read_text(encoding="utf-8"), "review packet")
    monkeypatch.setattr(transition, "BASELINE_CODE_SHA", baseline)
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_SHA", anchor)
    monkeypatch.setattr(transition, "BASELINE_SOURCE_BLOB", baseline_blob)
    monkeypatch.setattr(transition, "PRODUCT_SOURCE_BLOB", _git(checkout, "rev-parse", f"{anchor}:{transition.SOURCE_PATH}"))
    monkeypatch.setattr(transition, "REVIEW_PACKET_BLOB", _git(checkout, "rev-parse", f"{anchor}:{transition.REVIEW_PACKET_PATH}"))
    old = {"rules": {row["rule_id"]: row for row in old_rows}}
    new = {"rules": {row["rule_id"]: row for row in yaml.safe_load(source_text)["rules"]}}
    roster = {"checkout": str(checkout)}
    return roster, old, new


def test_public_source_rule_intent_is_quarantine_with_unchanged_review_window(public_source_intent):
    roster, old, new = public_source_intent
    result = transition._source_intent(roster, roster, old, new)
    assert result["review_window"] == ["2024-05-17", "2026-10-02"]
    assert result["clinical_eligibility_complete"] is False
    assert result["inventory_is_before_diagnosis"] is True
    rule = new["rules"][transition.ADDED_RULE_ID]
    assert rule["drug_names"] == ["darbepoetin", "aranesp"]
    for key in transition.REMOVED_RULE_IDS:
        assert "darbepoetin" in old["rules"][key]["drug_names"]
        assert not {"darbepoetin", "aranesp"} & set(new["rules"][key]["drug_names"])


def test_expected_fingerprints_are_reproducible_from_public_source_without_a_cache():
    assert _json_sha256(prose.drug_indication_coverage_scope()) == transition.PRODUCT_COVERAGE_SHA256
    rules = {rule["rule_id"]: rule for rule in prose.list_drug_indication_rules()}
    for key, expected in transition.SOURCE_ROUTE_SHA256.items():
        routes, truncated = _route_evidence([rules[key]])
        assert len(routes) == 1 and truncated is False
        assert _json_sha256(routes[0].to_dict()) == expected


@pytest.mark.parametrize("mutation", ["source_blob", "packet_blob", "missing_old_rule", "added_old_rule", "missing_new_rule", "compiled_rule_scope", "compiled_old_scope", "added_rule_body"])
def test_source_intent_rejects_catalog_and_source_evidence_mutations(public_source_intent, monkeypatch, mutation):
    roster, old, new = public_source_intent
    if mutation == "source_blob":
        monkeypatch.setattr(transition, "PRODUCT_SOURCE_BLOB", "0" * 40)
    elif mutation == "packet_blob":
        monkeypatch.setattr(transition, "REVIEW_PACKET_BLOB", "0" * 40)
    elif mutation == "missing_old_rule":
        old["rules"].pop(next(iter(transition.REMOVED_RULE_IDS)))
    elif mutation == "added_old_rule":
        old["rules"][transition.ADDED_RULE_ID] = copy.deepcopy(new["rules"][transition.ADDED_RULE_ID])
    elif mutation == "missing_new_rule":
        new["rules"].pop(transition.ADDED_RULE_ID)
    elif mutation == "compiled_old_scope":
        old["rules"][next(iter(transition.REMOVED_RULE_IDS))]["drug_names"].remove("aranesp")
    elif mutation == "added_rule_body":
        new["rules"][transition.ADDED_RULE_ID]["icd10_ranges"] = ["N18"]
    else:
        new["rules"][transition.ADDED_RULE_ID]["source_review_verified_through"] = "2026-10-04"
    with pytest.raises(ValueError):
        transition._source_intent(roster, roster, old, new)


@pytest.mark.parametrize("field,value", [
    ("source_review_verified_through", "2026-10-04"),
    ("source_review_change_date", "2024-05-16"),
    ("source_review_quarantine", False),
    ("source_clinical_scope_incomplete", False),
])
def test_even_self_consistent_source_blobs_cannot_expand_the_review_window(public_source_intent, monkeypatch, field, value):
    roster, old, new = public_source_intent
    changed = copy.deepcopy(new)
    changed["rules"][transition.ADDED_RULE_ID][field] = value
    checkout = Path(roster["checkout"])
    anchor = _commit(checkout, transition.SOURCE_PATH,
                     json.dumps({"rules": list(changed["rules"].values())}), "unreviewed source scope")
    monkeypatch.setattr(transition, "PRODUCT_ANCHOR_SHA", anchor)
    monkeypatch.setattr(transition, "PRODUCT_SOURCE_BLOB", _git(checkout, "rev-parse", f"{anchor}:{transition.SOURCE_PATH}"))
    with pytest.raises(ValueError, match="quarantine/source window"):
        transition._source_intent(roster, roster, old, changed)


@pytest.mark.parametrize("field,value", [
    ("status", "unverified"),
    ("input_bytes_sha256", "0" * 64),
    ("input_file_count", 11),
    ("data_mode", "real_claims"),
])
def test_transition_rejects_wrong_input_identity_before_any_replay(tmp_path, monkeypatch, field, value):
    def must_not_read_roster(*_args):
        raise AssertionError("Wrong production identity must stop before source/replay reads")

    monkeypatch.setattr(transition, "_roster", must_not_read_roster)
    same_input = {
        "status": "same_input_bytes_verified", "input_bytes_sha256": transition.INPUT_BYTES_SHA256,
        "input_file_count": 12, "data_mode": "synthetic_demo",
    }
    same_input[field] = value
    with pytest.raises(ValueError):
        transition.verify_clinical_semantic_transition(
            baseline_roster=tmp_path / "old.json", candidate_roster=tmp_path / "new.json",
            baseline_meta=_retained_meta(),
            candidate_meta={"code_sha": transition.PRODUCT_ANCHOR_SHA}, same_input=same_input,
            python_executable=Path("/usr/bin/python3"), dependency_roots=(),
            expected_candidate_sha=transition.PRODUCT_ANCHOR_SHA,
        )


@pytest.mark.parametrize("side", ["baseline", "candidate"])
def test_transition_rejects_wrong_selected_cache_code_sha_before_replay(tmp_path, monkeypatch, side):
    monkeypatch.setattr(transition, "_roster", lambda *_args: pytest.fail("Wrong code SHA reached source replay"))
    baseline = {"code_sha": transition.BASELINE_CODE_SHA}
    candidate = {"code_sha": transition.PRODUCT_ANCHOR_SHA}
    (baseline if side == "baseline" else candidate)["code_sha"] = "f" * 40
    with pytest.raises(ValueError, match="cache code identities"):
        transition.verify_clinical_semantic_transition(
            baseline_roster=tmp_path / "old.json", candidate_roster=tmp_path / "new.json",
            baseline_meta=baseline, candidate_meta=candidate, same_input={},
            python_executable=Path("/usr/bin/python3"), dependency_roots=(),
            expected_candidate_sha=transition.PRODUCT_ANCHOR_SHA,
        )


@pytest.mark.parametrize("field", ["source_hash", "config_hash"])
def test_self_consistent_metadata_cannot_replace_retained_production_source_or_config(tmp_path, monkeypatch, field):
    old_meta = _retained_meta()
    old_meta[field] = "f" * 64
    same_input = {
        "status": "same_input_bytes_verified", "input_bytes_sha256": transition.INPUT_BYTES_SHA256,
        "input_file_count": 12, "data_mode": "synthetic_demo",
        "baseline": {"roster_sha256": "a" * 64, **{key: old_meta[key] for key in ("source_hash", "config_hash")}},
    }
    monkeypatch.setattr(transition, "_roster", lambda *_args: pytest.fail("Altered retained identity reached replay"))
    with pytest.raises(ValueError, match="reviewed retained baseline"):
        transition.verify_clinical_semantic_transition(
            baseline_roster=tmp_path / "old.json", candidate_roster=tmp_path / "new.json",
            baseline_meta=old_meta, candidate_meta={"code_sha": transition.PRODUCT_ANCHOR_SHA},
            same_input=same_input, python_executable=Path("/usr/bin/python3"), dependency_roots=(),
            expected_candidate_sha=transition.PRODUCT_ANCHOR_SHA,
        )


def test_consistently_changed_inputs_pass_pair_equality_but_not_production_transition(tmp_path, monkeypatch):
    """Both datasets and stored hashes can agree without being the approved data."""
    environment = dict.fromkeys((
        "PIPELINE_MODE", "PIPELINE_SUT_MODE", "BILUN_DATA_MODE", "BILUN_CLAIMS_DIR", "BILUN_CLEAN_DIR",
    ), "")
    records = []
    for name in ("old", "new"):
        root = tmp_path / name
        root.mkdir()
        checkout, sha, claims, clean = _candidate(root)
        # All twelve retained input roles exist, but both copies now contain
        # the same altered bytes instead of the exact production dataset.
        for filename in ("performed_procedure_lines.parquet", "medula_rejection_events.parquet"):
            (claims / filename).write_bytes(b"same altered synthetic fixture")
        for path in (*claims.glob("*.parquet"), *clean.glob("*.parquet")):
            path.write_bytes(b"same altered synthetic fixture")
        roster_path = root / "roster.json"
        roster_path.write_text(json.dumps(_roster((checkout, sha, claims, clean))), encoding="utf-8")
        meta = {
            "code_sha": sha,
            "source_hash": source_hash_from_files(
                [clean / filename for filename in SUT_CLEAN_FILENAMES]
                + [claims / filename for filename in SUT_CLAIM_FILENAMES]
            ),
            "config_hash": _config_hash(
                environment, mode="synthetic_demo",
                claims_dir="data/synthetic/sut/claims", clean_dir="data/synthetic/sut/clean",
            ),
        }
        records.append((roster_path, meta))
    (old_roster, old_meta), (new_roster, new_meta) = records
    same_input = verify_same_input_rosters(
        old_roster, new_roster, baseline_meta=old_meta, candidate_meta=new_meta,
        build_config_environment=environment,
    )
    assert same_input["status"] == "same_input_bytes_verified"
    assert same_input["input_file_count"] == 12
    assert same_input["input_bytes_sha256"] != transition.INPUT_BYTES_SHA256
    monkeypatch.setattr(transition, "BASELINE_CODE_SHA", old_meta["code_sha"])
    # This is an isolated common-byte equality unit, so give its separate
    # baseline pins the fixture values to reach the production input gate.
    monkeypatch.setattr(transition, "BASELINE_SOURCE_HASH", old_meta["source_hash"], raising=False)
    monkeypatch.setattr(transition, "BASELINE_CONFIG_HASH", old_meta["config_hash"], raising=False)
    with pytest.raises(ValueError, match="exact reviewed same-input dataset"):
        transition.verify_clinical_semantic_transition(
            baseline_roster=old_roster, candidate_roster=new_roster,
            baseline_meta=old_meta, candidate_meta=new_meta, same_input=same_input,
            python_executable=Path("/usr/bin/python3"), dependency_roots=(),
            expected_candidate_sha=new_meta["code_sha"],
        )


def _proof(projections: dict, *, baseline_sha: str = transition.BASELINE_CODE_SHA,
           candidate_sha: str = transition.PRODUCT_ANCHOR_SHA) -> transition.ClinicalTransitionProof:
    return transition.ClinicalTransitionProof(
        _report_json=json.dumps({
            "status": "clinical_semantic_transition_verified",
            "contract": transition.TRANSITION_CONTRACT,
            "baseline_code_sha": baseline_sha,
            "candidate_code_sha": candidate_sha,
        }, sort_keys=True),
        _projections_json=json.dumps(projections, sort_keys=True),
    )


def _replay_double() -> tuple[dict, dict, transition.ClinicalTransitionProof]:
    old = {
        "patient_id": "P1", "sgk_uplift_try": 0.0,
        "drug_indication": {
            "coverage_scope": {"pilot_rule_count": 1},
            "findings": [], "evaluations": [], "violations": [],
        },
        "recommended_actions": [
            {"action_id": "unrelated", "surface": "lab", "savings_try": 12.5},
        ],
    }
    new = copy.deepcopy(old)
    new["drug_indication"]["coverage_scope"]["pilot_rule_count"] = 2
    projections = {
        side: {
            family: {key: {
                "drug_indication": copy.deepcopy(row["drug_indication"]),
                "recommended_actions": [],
            }}
            for family, key in (("patients", "P1"), ("bills", "P1::C1"))
        }
        for side, row in (("baseline", old), ("candidate", new))
    }
    return old, new, _proof(projections)


def test_proof_properties_are_immutable_detached_copies():
    _, _, proof = _replay_double()
    report = proof.report
    report["status"] = "forged"
    projections = proof.projections
    projections["candidate"]["patients"]["P1"]["drug_indication"] = {}
    assert proof.report["status"] == "clinical_semantic_transition_verified"
    assert proof.projections["candidate"]["patients"]["P1"]["drug_indication"]
    with pytest.raises(FrozenInstanceError):
        proof._report_json = "{}"


@pytest.mark.parametrize("table,key", [
    ("patient_billing_report_rows", "P1"),
    ("patient_bill_billing_report_rows", "P1::C1"),
])
def test_normalizer_requires_exact_independent_replay_and_preserves_other_fields(table, key):
    old, new, proof = _replay_double()
    before = copy.deepcopy(new)
    normalized = transition.normalize_transition_content(
        table, {key: new}, side="candidate", proof=proof,
    )
    assert normalized == {key: old}
    assert new == before
    assert normalized[key]["sgk_uplift_try"] == 0.0
    assert normalized[key]["recommended_actions"] == old["recommended_actions"]


@pytest.mark.parametrize("value", [3, None, False, 2.0, "2"])
def test_third_coverage_value_cannot_be_normalized(value):
    _, new, proof = _replay_double()
    new["drug_indication"]["coverage_scope"]["pilot_rule_count"] = value
    with pytest.raises(ValueError):
        transition.normalize_transition_content(
            "patient_billing_report_rows", {"P1": new}, side="candidate", proof=proof,
        )


@pytest.mark.parametrize("mutation", ["unexpected_field", "extra_row", "missing_row"])
def test_owned_projection_cannot_hide_additional_fields_or_report_rows(mutation):
    _, new, proof = _replay_double()
    rows = {"P1": new}
    if mutation == "unexpected_field":
        new["drug_indication"]["unreviewed"] = True
    elif mutation == "extra_row":
        rows["P2"] = copy.deepcopy(new)
    else:
        rows.clear()
    with pytest.raises(ValueError):
        transition.normalize_transition_content(
            "patient_billing_report_rows", rows, side="candidate", proof=proof,
        )


@pytest.fixture(scope="module")
def transport_sources(tmp_path_factory):
    """Run actual public serializers/models in independent source-only Git trees.

    CI has a shallow checkout. Reconstruct the old schema's exact Git blob
    from the unchanged current file and the five reviewed schema additions;
    this fixture is a transport regression, not a complete production replay.
    """
    repository = Path(__file__).resolve().parents[3]
    schema = (repository / "src/bilun/api/schemas.py").read_text()
    old_schema = schema.replace(
        "from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse as DrugRuntimeCoverageResponse\n"
        "from src.bilun.domain.sut.source_authority_schema import ClinicalSourceAuthorityEvidence\n\n", "",
    )
    start = old_schema.index("class DrugTemporalCheckResponse(BaseModel):")
    end = old_schema.index("class DrugIndicationFindingResponse(BaseModel):")
    old_schema = old_schema[:start] + old_schema[end:]
    for addition in (
        "    source_authority: ClinicalSourceAuthorityEvidence | None = None\n",
        "    runtime_coverage: DrugRuntimeCoverageResponse | None = None\n",
        "    temporal_evidence: DrugTemporalEvidenceResponse | None = None\n",
        "    clinical_restrictions: list[DrugClinicalRestrictionResponse] = Field(default_factory=list)\n"
        "    clinical_eligibility_complete: bool | None = None\n\n",
    ):
        assert old_schema.count(addition) == 2
        old_schema = old_schema.replace(addition, "")
    raw = old_schema.encode()
    assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == "c7d2e3d5bb738c83de23f83f7541d0acc20014f7"
    serializer = (repository / "src/bilun/api/routes/billing.py").read_bytes()
    assert hashlib.sha1(b"blob " + str(len(serializer)).encode() + b"\0" + serializer).hexdigest() == "6cd6f86c92f1deb533692090def668fb00e2bb1d"
    normalizer_path = "src/bilun/domain/billing/drug_indication_findings.py"
    old_normalizer = (repository / normalizer_path).read_text().replace(
        "    # Cached measurement metadata uses the same bounded contract as live rows.\n"
        "    # Missing old-cache metadata stays absent; it cannot become measured zero.\n"
        '    for kind in ("findings", "evaluations", "violations"):\n'
        "        if isinstance(payload.get(kind), list):\n"
        "            payload[kind] = [\n"
        "                _normalize_cached_evidence(row)\n"
        "                for row in payload[kind]\n"
        "            ]\n", "",
    )
    old_node = next(node for node in ast.parse(old_normalizer).body
                    if isinstance(node, ast.FunctionDef) and node.name == "normalize_drug_indication_payload")
    assert hashlib.sha256(ast.get_source_segment(old_normalizer, old_node).encode()).hexdigest() == "1b0f6cf4c0e56683882e459c90bf07f51f58cdc3dba1e3240edddb15ae580203"
    result = {}
    for side in ("baseline", "candidate"):
        root = tmp_path_factory.mktemp("pinned-transport-" + side)
        shutil.copytree(repository / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(repository / "scripts/sut", root / "scripts/sut", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copyfile(repository / "scripts/__init__.py", root / "scripts/__init__.py")
        if side == "baseline":
            (root / "src/bilun/api/schemas.py").write_text(old_schema)
            (root / normalizer_path).write_text(old_normalizer)
        _git(root, "init", "-q")
        _git(root, "config", "user.name", "Bilun Transport Test")
        _git(root, "config", "user.email", "transport@example.invalid")
        _git(root, "config", "commit.gpgsign", "false")
        _git(root, "add", "src", "scripts")
        _git(root, "commit", "-qm", "independent public serializer fixture")
        result[side] = root, _git(root, "rev-parse", "HEAD")
    return result


def _transport_packages(transport_sources, old: dict, new: dict):
    provenance = {
        "mode": "synthetic_demo", "is_synthetic": True, "label": "Synthetic test",
        "notice": "Public authored synthetic fixture", "claim_source": "claims", "clinical_source": "clean",
    }
    paths = ("/api/billing-report/P1", "/api/billing-report/P1/bills/C1")
    projections, packages = {}, {}
    for side, report in (("baseline", old), ("candidate", new)):
        raw = {path: copy.deepcopy(report) for path in paths}
        raw[paths[1]].update(patient_id="P1", claim_id="C1", report_scope="bill")
        projections[side] = {
            family: {key: {
                "drug_indication": copy.deepcopy(report["drug_indication"]),
                "recommended_actions": [copy.deepcopy(row) for row in report["recommended_actions"]
                                        if row.get("surface") == "drug_indication"],
            }}
            for family, key in (("patients", "P1"), ("bills", "P1::C1"))
        }
        repository, sha = transport_sources[side]
        packages[side] = rehearsal.project_report_transport(
            raw, provenance, repository=repository, expected_code_sha=sha,
            python_executable=Path(sys.executable),
            dependency_roots=(Path(sys.base_prefix), Path(sysconfig.get_path("purelib"))),
            cache_sha256=("a" if side == "baseline" else "b") * 64,
            build_id=side + "-fixture-build", contract="wavea-evidence-v2",
        )
    proof = _proof(projections, baseline_sha=transport_sources["baseline"][1],
                   candidate_sha=transport_sources["candidate"][1])
    return packages["baseline"], packages["candidate"], proof


@pytest.fixture(scope="module")
def http_transport_pair(transport_sources):
    old, new, proof = _replay_double()
    return _transport_packages(transport_sources, old, new)


def _http_fixture(http_transport_pair):
    baseline, candidate, proof = http_transport_pair
    return baseline.draft_reports, candidate.draft_reports, baseline.complete_reports, proof, baseline, candidate


def test_http_transition_still_binds_complete_patient_bill_dtos(http_transport_pair):
    old, new, persisted, proof, baseline, candidate = _http_fixture(http_transport_pair)
    rehearsal.compare_reports(
        old, new, contract="wavea-evidence-v2", old_capability="draft",
        old_persisted=persisted, clinical_transition=proof,
        old_transport=baseline, candidate_transport=candidate,
    )


@pytest.mark.parametrize("mutation", ["third_coverage", "money_null", "money_bool", "money_integer", "unknown_field", "missing_bill", "unknown_path", "duplicate_encoded_identity"])
def test_http_transition_does_not_hide_money_fields_or_routing_mutations(http_transport_pair, mutation):
    old, new, persisted, proof, baseline, candidate = _http_fixture(http_transport_pair)
    path = "/api/billing-report/P1"
    if mutation == "third_coverage":
        new[path]["drug_indication"]["coverage_scope"]["pilot_rule_count"] = 3
    elif mutation.startswith("money_"):
        new[path]["sgk_uplift_try"] = {"money_null": None, "money_bool": False, "money_integer": 0}[mutation]
    elif mutation == "unknown_field":
        new[path]["unreviewed_payload"] = True
    elif mutation == "missing_bill":
        new.pop("/api/billing-report/P1/bills/C1")
    elif mutation == "unknown_path":
        for collection in (old, new, persisted):
            collection["/api/rules"] = copy.deepcopy(collection[path])
    else:
        for collection in (old, new, persisted):
            collection["/api/billing-report/P%31"] = copy.deepcopy(collection[path])
    with pytest.raises(ValueError):
        rehearsal.compare_reports(
            old, new, contract="wavea-evidence-v2", old_capability="draft",
            old_persisted=persisted, clinical_transition=proof,
            old_transport=baseline, candidate_transport=candidate,
        )


@pytest.fixture(scope="module", params=["unenriched", "source", "coverage", "temporal", "restrictions"])
def drug_http_transport_pair(transport_sources, request):
    with pytest.MonkeyPatch.context() as patch:
        old, new = _authored_route_pair(patch)
    metadata = {
        "unenriched": {},
        "source": {
            "source_authority": {
                "schema_version": 1, "status": "review_required", "reason": "missing_service_date",
                "family_id": "drug_indication", "next_action": "Review source and service date",
                "clinical_eligibility_complete": False,
            }, "clinical_eligibility_complete": False,
        },
        "coverage": {
            "runtime_coverage": {"schema_version": 1, "available": False,
                                 "instrumented_families": [], "unavailable_reason": "Not measured"},
        },
        "temporal": {
            "temporal_evidence": {
                "status": "review_required", "publication_date": "2026-10-01",
                "source_url": "https://example.invalid/public-authored-fixture",
                "source_sha256": "a" * 64, "source_text_sha256": "b" * 64,
                "date_basis": "service_date", "clinical_eligibility_complete": False,
            },
        },
        "restrictions": {
            "clinical_restrictions": [{"constraint_set": "authored-check", "criterion_status": "missing_inputs",
                                       "missing_inputs": ["report"], "clinical_eligibility_complete": False}],
            "clinical_eligibility_complete": False,
        },
    }[request.param]
    for report in (old, new):
        report.update(patient_id="P1", sgk_uplift_try=0.0)
        report.pop("alias_predicates")
        report["recommended_actions"].insert(0, {"action_id": "lab-first", "surface": "lab", "savings_try": 12.5})
        report["recommended_actions"].append({"action_id": "lab-last", "surface": "lab", "savings_try": None})
        for collection in ("findings", "evaluations"):
            row = report["drug_indication"][collection][0]
            row.update(finding_kind="indication_mismatch", matched_icd10_codes=[], unmatched_icd10_codes=["Z01"],
                       required_inputs=[], missing_inputs=[], **copy.deepcopy(metadata))
            if collection == "findings":
                row["recommended_action_tr"] = "Review report"
            for route in row["eligible_routes"]:
                route.update(regulatory_summary_tr="Public authored inventory", report_duration_months=None,
                             report_specialties=[], prescriber_specialties=[], icd10_code_count=0,
                             icd10_codes_truncated=False, icd10_range_count=len(route["icd10_ranges"]),
                             icd10_ranges_truncated=False)
    return (*_transport_packages(transport_sources, old, new), request.param)


@pytest.mark.parametrize("view", ["draft", "legacy"])
def test_real_old_new_dto_models_normalize_only_source_bound_drug_slice(drug_http_transport_pair, view):
    baseline, candidate, proof, metadata = drug_http_transport_pair
    old = baseline.draft_reports if view == "draft" else {
        path: rehearsal._legacy_report(row) for path, row in baseline.complete_reports.items()
    }
    new = candidate.draft_reports if view == "draft" else {
        path: rehearsal._legacy_report(row) for path, row in candidate.complete_reports.items()
    }
    normalized_old = transition.normalize_transition_http_reports(
        old, side="baseline", proof=proof, transport=baseline, baseline_transport=baseline, view=view,
    )
    normalized_new = transition.normalize_transition_http_reports(
        new, side="candidate", proof=proof, transport=candidate, baseline_transport=baseline, view=view,
    )
    assert normalized_old == old
    assert transition._canonical(normalized_new) == transition._canonical(old)
    for path in new:
        assert normalized_new[path]["recommended_actions"][0] == new[path]["recommended_actions"][0]
        assert normalized_new[path]["recommended_actions"][-1] == new[path]["recommended_actions"][-1]
        assert normalized_new[path]["data_source"] == new[path]["data_source"]
    if metadata == "unenriched":
        for collection in ("findings", "evaluations"):
            row = old["/api/billing-report/P1"]["drug_indication"][collection][0]
            assert "source_authority" not in row
            after = new["/api/billing-report/P1"]["drug_indication"][collection][0]
            assert after["source_authority"] is None
            assert after["clinical_restrictions"] == []
            assert after["clinical_eligibility_complete"] is None
    # Wire defaults do not weaken the exact raw-cache producer contract.
    for side, package in (("baseline", baseline), ("candidate", candidate)):
        with pytest.raises(ValueError, match="cached drug producer replay"):
            transition.normalize_transition_content(
                "patient_billing_report_rows", {"P1": package.draft_reports["/api/billing-report/P1"]},
                side=side, proof=proof,
            )


@pytest.mark.parametrize("side", ["baseline", "candidate"])
@pytest.mark.parametrize("mutation", [
    "null_vs_absent", "new_default_absent", "source_changed", "money_bool", "money_int",
    "third_coverage", "route_id", "clinical_status", "unexpected_metadata", "action_position",
])
def test_source_projected_http_defaults_are_exact_not_a_value_allowlist(drug_http_transport_pair, side, mutation):
    baseline, candidate, proof, _ = drug_http_transport_pair
    package = baseline if side == "baseline" else candidate
    reports = package.draft_reports
    row = reports["/api/billing-report/P1/bills/C1"]
    finding = row["drug_indication"]["findings"][0]
    if mutation == "null_vs_absent":
        if "source_authority" in finding:
            finding.pop("source_authority")
        else:
            finding["source_authority"] = None
    elif mutation == "new_default_absent":
        if "clinical_restrictions" in finding:
            finding.pop("clinical_restrictions")
        else:
            finding["clinical_restrictions"] = []
    elif mutation == "source_changed":
        row["data_source"]["is_synthetic"] = False
    elif mutation == "money_bool":
        row["sgk_uplift_try"] = False
    elif mutation == "money_int":
        row["sgk_uplift_try"] = 0
    elif mutation == "third_coverage":
        row["drug_indication"]["coverage_scope"]["pilot_rule_count"] = 3
    elif mutation == "route_id":
        finding["eligible_routes"][0]["rule_id"] = "unreviewed"
    elif mutation == "clinical_status":
        finding["evaluation_status"] = "unavailable"
    elif mutation == "unexpected_metadata":
        finding["clinical_eligibility_complete"] = True
    else:
        row["recommended_actions"].reverse()
    with pytest.raises(ValueError, match="HTTP pinned serializer/model projection"):
        transition.normalize_transition_http_reports(
            reports, side=side, proof=proof, transport=package, baseline_transport=baseline,
        )


@pytest.mark.parametrize("mutation", ["mapping", "unsealed", "wrong_sha", "wrong_baseline_sha", "unknown_view", "old_dto_from_new_model", "raw_changed"])
def test_http_transition_rejects_unbound_or_wrong_source_transport(http_transport_pair, mutation):
    baseline, candidate, proof = http_transport_pair
    supplied, old_supplied, view = candidate, baseline, "draft"
    reports = candidate.draft_reports
    if mutation == "mapping":
        supplied = {"code_sha": candidate.code_sha, "draft_reports": reports}
    elif mutation == "unsealed":
        supplied = rehearsal.PinnedReportTransport(candidate._binding_json, candidate._raw_json,
                                                   candidate._complete_json, candidate._draft_json)
    elif mutation in {"wrong_sha", "wrong_baseline_sha"}:
        info = proof.report
        info[("candidate" if mutation == "wrong_sha" else "baseline") + "_code_sha"] = "f" * 40
        proof = transition.ClinicalTransitionProof(json.dumps(info), json.dumps(proof.projections))
    elif mutation == "unknown_view":
        view = "remove_defaults"
    elif mutation == "old_dto_from_new_model":
        supplied = baseline
    else:
        altered = candidate.raw_reports
        altered["/api/billing-report/P1"]["drug_indication"]["coverage_scope"]["pilot_rule_count"] = 3
        binding = json.loads(candidate._binding_json)
        raw_json = transition._canonical(altered)
        binding["raw_sha256"] = hashlib.sha256(raw_json.encode()).hexdigest()
        # Even a sealed, internally self-consistent package must match fresh
        # producer replay; changing only its raw payload cannot forge ownership.
        supplied = rehearsal.PinnedReportTransport(json.dumps(binding), raw_json,
            candidate._complete_json, candidate._draft_json, candidate._seal)
    with pytest.raises(ValueError):
        transition.normalize_transition_http_reports(
            reports, side="candidate", proof=proof, transport=supplied, baseline_transport=old_supplied, view=view,
        )


def _private_transition_fixture(tmp_path):
    path, observed, candidate, runtime, report, _ = sealed_rehearsal(tmp_path)
    producer = runtime / "scripts/deploy/rehearse_wavea_same_port.py"
    same_input = json.loads((tmp_path / "same-input-rehearsal.json").read_text())
    fresh = {
        "status": "clinical_semantic_transition_verified", "contract": transition.TRANSITION_CONTRACT,
        "candidate_code_sha": candidate["code_sha"], "same_input": same_input,
        "verifier": {
            "verifier_sha": candidate["code_sha"],
            "files": {"scripts/deploy/rehearse_wavea_same_port.py": hashlib.sha256(producer.read_bytes()).hexdigest()},
        },
    }
    report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", fresh)
    private_json(path, report)
    return path, observed, candidate, runtime, report, fresh


def test_private_rehearsal_binds_saved_transition_to_fresh_proof_and_source_bytes(tmp_path):
    path, observed, candidate, runtime, _, fresh = _private_transition_fixture(tmp_path)
    result = verify_private_rehearsal(
        path, observed, candidate=candidate, backend_runtime=runtime, clinical_transition=fresh,
    )
    assert result["status"] == "private_pair_rehearsal_verified"


@pytest.mark.parametrize("blob", [transition.FRONTEND_CONFIG_BASELINE_BLOB,
                                  transition.FRONTEND_CONFIG_CANDIDATE_BLOB])
def test_private_rehearsal_authenticates_separate_frontend_config_binding(tmp_path, blob):
    path, observed, candidate, runtime, report, fresh = _private_transition_fixture(tmp_path)
    verifier = fresh["verifier"]
    verifier["frontend_config"] = {
        "path": transition.FRONTEND_CONFIG_PATH, "git_mode": "100644", "git_blob": blob,
        "sha256": transition._FRONTEND_CONFIG_SHA256[blob],
    }
    verifier["source_sha256"] = transition._digest({
        "files": verifier["files"], "frontend_config": verifier["frontend_config"],
    })
    assert transition.FRONTEND_CONFIG_PATH not in verifier["files"]
    report["clinical_transition_report_sha256"] = private_json(
        tmp_path / "clinical-transition-rehearsal.json", fresh,
    )
    private_json(path, report)
    result = verify_private_rehearsal(
        path, observed, candidate=candidate, backend_runtime=runtime, clinical_transition=fresh,
    )
    assert result["status"] == "private_pair_rehearsal_verified"
    altered = copy.deepcopy(fresh)
    altered["verifier"]["frontend_config"]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="clinical|Clinical"):
        verify_private_rehearsal(
            path, observed, candidate=candidate, backend_runtime=runtime, clinical_transition=altered,
        )


@pytest.mark.parametrize("mutation", [
    "saved_proof", "candidate_sha", "verifier_sha", "missing_closure", "source_bytes",
    "input_binding", "malformed_locator", "wrong_saved_hash", "downgraded_schema", "unrequested",
])
def test_private_rehearsal_rejects_transition_proof_and_source_binding_mutations(tmp_path, mutation):
    path, observed, candidate, runtime, report, fresh = _private_transition_fixture(tmp_path)
    supplied = fresh
    if mutation == "saved_proof":
        saved = copy.deepcopy(fresh)
        saved["unreviewed"] = True
        private_json(tmp_path / "clinical-transition-rehearsal.json", saved)
    elif mutation == "candidate_sha":
        fresh["candidate_code_sha"] = "f" * 40
    elif mutation == "verifier_sha":
        fresh["verifier"]["verifier_sha"] = "f" * 40
    elif mutation == "missing_closure":
        fresh["verifier"]["files"].clear()
    elif mutation == "source_bytes":
        (runtime / "scripts/deploy/rehearse_wavea_same_port.py").write_text("# unreviewed producer source\n")
    elif mutation == "input_binding":
        fresh["same_input"]["input_bytes_sha256"] = "f" * 64
    elif mutation == "malformed_locator":
        fresh["verifier"]["files"] = {"scripts/deploy/../unreviewed.py": "a" * 64}
    elif mutation == "wrong_saved_hash":
        report["clinical_transition_report_sha256"] = "0" * 64
    elif mutation == "downgraded_schema":
        report["schema_version"] = "wavea-real-pair-rehearsal-v1"
    else:
        supplied = None
    if mutation in {"candidate_sha", "verifier_sha", "missing_closure", "input_binding", "malformed_locator"}:
        report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", fresh)
    private_json(path, report)
    with pytest.raises(ValueError, match="clinical|Clinical"):
        verify_private_rehearsal(
            path, observed, candidate=candidate, backend_runtime=runtime, clinical_transition=supplied,
        )


@pytest.mark.parametrize("mutation", [None, "saved_mismatch", "saved_hash_mismatch", "relative_source_path"])
def test_issuer_replays_opt_in_and_rejects_saved_semantic_proof_drift(tmp_path, monkeypatch, mutation):
    arguments, code_sha, _, _ = _issuer_fixture(tmp_path, monkeypatch)
    request = {
        "contract": transition.TRANSITION_CONTRACT,
        "expected_candidate_sha": code_sha, "expected_verifier_sha": code_sha,
    }
    arguments["clinical_transition"] = request
    fresh = issuer.verify_candidate_semantic_checkpoint()
    fresh["clinical_transition"] = {
        "status": "clinical_semantic_transition_verified", "contract": transition.TRANSITION_CONTRACT,
        "candidate_code_sha": code_sha, "transition_sha256": "a" * 64,
    }

    def verify_fresh(*_args, **kwargs):
        assert kwargs["clinical_transition"] == request
        assert kwargs["python_executable"] == arguments["python_executable"]
        return fresh

    monkeypatch.setattr(issuer, "verify_candidate_semantic_checkpoint", verify_fresh)
    protected = arguments["sidecar_path"].parent
    saved = copy.deepcopy(fresh)
    if mutation == "saved_mismatch":
        saved["clinical_transition"]["transition_sha256"] = "f" * 64
    source_path = protected / "saved-semantic.json"
    source_sha = private_json(source_path, saved)
    raw_path = protected / "semantic-raw.json"
    private_json(raw_path, {
        "source_report_path": "saved-semantic.json" if mutation == "relative_source_path" else str(source_path),
        "source_report_sha256": "0" * 64 if mutation == "saved_hash_mismatch" else source_sha,
    })
    envelope_path = protected / "semantic-envelope.json"
    private_json(envelope_path, {"raw_report_path": str(raw_path)})
    original_loader = issuer._load_private_json

    def load_bound_report(path, **kwargs):
        if path == arguments["sidecar_path"]:
            sidecar, digest = original_loader(path, **kwargs)
            return {**sidecar, "evidence": {"semantic_cache": {"path": str(envelope_path)}}}, digest
        if path in (source_path, raw_path, envelope_path):
            return _load_private_json(path, **kwargs)
        return original_loader(path, **kwargs)

    monkeypatch.setattr(issuer, "_load_private_json", load_bound_report)
    monkeypatch.setattr(issuer, "fetch_successful_release_ci", lambda **_kwargs: {
        "status": "release_ci_verified", "code_sha": code_sha, "ci_run_id": arguments["ci_run_id"],
    })
    monkeypatch.setattr(issuer.secrets, "token_bytes", lambda _size: b"fixture-only-key-for-test-00000000")
    if mutation is None:
        assert issuer.issue_wavea_activation(**arguments)["status"] == "private_activation_receipt_issued"
    else:
        with pytest.raises(ValueError, match="Activation transition"):
            issuer.issue_wavea_activation(**arguments)
        assert not arguments["key_path"].exists()
        assert not arguments["receipt_path"].exists()


def _json_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _authored_route_pair(monkeypatch) -> tuple[dict, dict]:
    """Independent inventory expectation: aliases change, diagnosis does not."""
    shared = {"rule_id": "unchanged-route", "sut_section": "4.2.9", "report_required": True,
              "icd10_codes": [], "icd10_ranges": ["N18"]}
    removed = [{"rule_id": key, "sut_section": "4.2.9.A-2", "report_required": True,
                "icd10_codes": [], "icd10_ranges": ["D46", "D47"]}
               for key in sorted(transition.REMOVED_RULE_IDS)]
    added = {"rule_id": transition.ADDED_RULE_ID, "sut_section": "4.2.9.A-2", "report_required": True,
             "icd10_codes": [], "icd10_ranges": ["D46", "D47"]}
    row = {
        "finding_id": "stable-finding", "drug_claim_line_id": "D1",
        "patient_id": "P1", "claim_id": "C1", "selected_rule_id": None,
        "applicability_status": "indication_mismatch", "evaluation_status": "evaluated",
        "severity": "review", "savings_try": None,
        "drug_name": "aranesp", "observed_icd10_codes": ["Z01"],
        "eligible_routes": [shared, *removed], "eligible_route_count": 3,
        "eligible_routes_truncated": False,
    }
    old_narrative = (
        "Faturada Z01 tanıları bulundu. aranesp için kodlanmış SGK geri ödeme yolları "
        "N18, D46, D47, D46, D47 tanılarını kapsıyor. Mevcut tanılar bu yollarla eşleşmiyor."
    )
    new_narrative = (
        "Faturada Z01 tanıları bulundu. aranesp için kodlanmış SGK geri ödeme yolları "
        "N18, D46, D47 tanılarını kapsıyor. Mevcut tanılar bu yollarla eşleşmiyor."
    )
    finding = {**copy.deepcopy(row), "explanation_tr": old_narrative}
    violation = {
        **{key: copy.deepcopy(value) for key, value in row.items() if key != "eligible_routes"},
        "eligible_route_rule_ids": [route["rule_id"] for route in row["eligible_routes"]],
        "detail": old_narrative, "message": old_narrative, "message_tr": old_narrative,
    }
    action = {**copy.deepcopy(row), "action_id": "stable-finding", "surface": "drug_indication",
              "detail": old_narrative, "sut_section_id": "4.2.9"}
    old = {
        "drug_indication": {
            "coverage_scope": {"pilot_rule_count": 1},
            "evaluations": [row], "findings": [finding], "violations": [violation],
            "n_evaluations": 1, "n_findings": 1, "total_savings_try": None,
        },
        "recommended_actions": [action],
        "alias_predicates": {"D1": {key: True for key in transition.REMOVED_RULE_IDS}},
    }
    new = copy.deepcopy(old)
    new["drug_indication"]["coverage_scope"]["pilot_rule_count"] = 2
    for collection in ("evaluations", "findings"):
        newer = new["drug_indication"][collection][0]
        newer["eligible_routes"] = [copy.deepcopy(shared), copy.deepcopy(added)]
        newer["eligible_route_count"] = 2
    new["drug_indication"]["findings"][0]["explanation_tr"] = new_narrative
    newer = new["drug_indication"]["violations"][0]
    newer["eligible_route_rule_ids"] = [shared["rule_id"], added["rule_id"]]
    newer["eligible_route_count"] = 2
    newer["detail"] = newer["message"] = newer["message_tr"] = new_narrative
    newer = new["recommended_actions"][0]
    newer["eligible_routes"] = [copy.deepcopy(shared), copy.deepcopy(added)]
    newer["eligible_route_count"] = 2
    newer["detail"] = new_narrative
    new["alias_predicates"] = {"D1": {
        **dict.fromkeys(transition.REMOVED_RULE_IDS, False), transition.ADDED_RULE_ID: True,
    }}
    monkeypatch.setattr(transition, "BASELINE_COVERAGE_SHA256", _json_sha256(old["drug_indication"]["coverage_scope"]))
    monkeypatch.setattr(transition, "PRODUCT_COVERAGE_SHA256", _json_sha256(new["drug_indication"]["coverage_scope"]))
    monkeypatch.setattr(transition, "SOURCE_ROUTE_SHA256", {
        **{route["rule_id"]: _json_sha256(route) for route in removed},
        added["rule_id"]: _json_sha256(added),
    })
    return old, new


def test_source_permission_boundary_preserves_the_nonselected_mismatch(monkeypatch):
    old, new = _authored_route_pair(monkeypatch)
    transition._check_projection_pair(old, new)


@pytest.mark.parametrize("mutation", ["third_count", "boolean_count", "unknown_on_both", "changed_unowned_path"])
def test_coverage_permission_rejects_third_values_and_equal_mutations_on_both_replays(monkeypatch, mutation):
    old, new = _authored_route_pair(monkeypatch)
    before, after = old["drug_indication"]["coverage_scope"], new["drug_indication"]["coverage_scope"]
    if mutation == "third_count":
        after["pilot_rule_count"] = 3
    elif mutation == "boolean_count":
        after["pilot_rule_count"] = True
    elif mutation == "unknown_on_both":
        before["unreviewed_source_window"] = after["unreviewed_source_window"] = "2099-01-01"
    else:
        after["unreviewed_registry_flag"] = True
    with pytest.raises(ValueError, match="coverage metadata"):
        transition._check_projection_pair(old, new)


@pytest.mark.parametrize("mutation", ["finding_narrative", "legacy_narrative", "action_narrative", "action_section", "added_route_body", "retired_route_body"])
def test_allowed_path_is_not_permission_for_any_value(monkeypatch, mutation):
    old, new = _authored_route_pair(monkeypatch)
    if mutation == "finding_narrative":
        new["drug_indication"]["findings"][0]["explanation_tr"] = "Unreviewed payment eligibility assertion"
    elif mutation == "legacy_narrative":
        new["drug_indication"]["violations"][0]["detail"] = "Unreviewed payment eligibility assertion"
    elif mutation == "action_narrative":
        new["recommended_actions"][0]["detail"] = "Unreviewed payment eligibility assertion"
    elif mutation == "action_section":
        new["recommended_actions"][0]["sut_section_id"] = "unreviewed-section"
    elif mutation == "added_route_body":
        new["drug_indication"]["evaluations"][0]["eligible_routes"][-1]["report_required"] = False
    else:
        old["drug_indication"]["evaluations"][0]["eligible_routes"][-1]["report_required"] = False
    with pytest.raises(ValueError):
        transition._check_projection_pair(old, new)


@pytest.mark.parametrize("collection", ["evaluations", "findings", "violations", "actions"])
@pytest.mark.parametrize("field,value", [
    ("selected_rule_id", "unreviewed-selected-rule"),
    ("severity", "clear"),
    ("evaluation_status", "unavailable"),
    ("applicability_status", "applicable"),
    ("savings_try", 0), ("savings_try", False), ("savings_try", 0.0),
    ("finding_id", "forged"), ("unexpected", True),
])
def test_replayed_delta_cannot_change_protected_fields(monkeypatch, collection, field, value):
    old, new = _authored_route_pair(monkeypatch)
    rows = new["recommended_actions"] if collection == "actions" else new["drug_indication"][collection]
    rows[0][field] = value
    with pytest.raises(ValueError, match="protected"):
        transition._check_projection_pair(old, new)


@pytest.mark.parametrize("mutation", [
    "different_added_id", "missing_removed_id", "shared_route_object", "duplicate_route",
    "third_route_count", "boolean_route_count", "wrong_old_predicate", "wrong_new_predicate",
    "missing_line_predicate", "missing_finding", "extra_evaluation", "wrong_selected_old_rule",
])
def test_route_permission_requires_exact_ids_shared_objects_and_input_predicates(monkeypatch, mutation):
    old, new = _authored_route_pair(monkeypatch)
    evaluation = new["drug_indication"]["evaluations"][0]
    if mutation == "different_added_id":
        evaluation["eligible_routes"][-1]["rule_id"] = "unreviewed-new-route"
    elif mutation == "missing_removed_id":
        old["drug_indication"]["evaluations"][0]["eligible_routes"].pop()
    elif mutation == "shared_route_object":
        evaluation["eligible_routes"][0]["report_required"] = False
    elif mutation == "duplicate_route":
        evaluation["eligible_routes"].append(copy.deepcopy(evaluation["eligible_routes"][0]))
    elif mutation == "third_route_count":
        evaluation["eligible_route_count"] = 9
    elif mutation == "boolean_route_count":
        evaluation["eligible_route_count"] = True
    elif mutation == "wrong_old_predicate":
        old["alias_predicates"]["D1"][next(iter(transition.REMOVED_RULE_IDS))] = False
    elif mutation == "wrong_new_predicate":
        new["alias_predicates"]["D1"][transition.ADDED_RULE_ID] = False
    elif mutation == "missing_line_predicate":
        new["alias_predicates"].clear()
    elif mutation == "missing_finding":
        new["drug_indication"]["findings"].clear()
    elif mutation == "extra_evaluation":
        new["drug_indication"]["evaluations"].append(copy.deepcopy(evaluation))
    else:
        old["drug_indication"]["evaluations"][0]["selected_rule_id"] = "changed-selection"
        new["drug_indication"]["evaluations"][0]["selected_rule_id"] = "changed-selection"
    with pytest.raises(ValueError):
        transition._check_projection_pair(old, new)


def _cache_proof(baseline: Path, candidate: Path) -> transition.ClinicalTransitionProof:
    projections = {}
    for side, path, build in (
        ("baseline", baseline, "baseline"), ("candidate", candidate, "candidate"),
    ):
        projections[side] = {}
        with duckdb.connect(str(path), read_only=True) as con:
            for family, table in (
                ("patients", "patient_billing_report_rows"),
                ("bills", "patient_bill_billing_report_rows"),
            ):
                rows = con.execute(
                    f'SELECT patient_id, payload_json FROM "{table}" WHERE build_id = ?',
                    [build],
                ).fetchall()
                projections[side][family] = {}
                for key, raw in rows:
                    payload = json.loads(raw)
                    projections[side][family][key] = {
                        "drug_indication": payload["drug_indication"],
                        "recommended_actions": [
                            action for action in payload["recommended_actions"]
                            if action.get("surface") == "drug_indication"
                        ],
                    }
    return _proof(projections)


def _parity(baseline: Path, candidate: Path, proof):
    with duckdb.connect(str(baseline), read_only=True) as old:
        with duckdb.connect(str(candidate), read_only=True) as new:
            return _current_content_parity(
                old, "baseline", new, "candidate", clinical_transition=proof,
            )


def test_transition_preserves_all_nineteen_table_checks_without_writing_caches(tmp_path):
    baseline, candidate, _ = _current_fixture(tmp_path)
    proof = _cache_proof(baseline, candidate)
    before = {path: path.read_bytes() for path in (baseline, candidate)}
    digests, _, bill_count = _parity(baseline, candidate, proof)
    assert len(digests) == 19
    assert bill_count == 1
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("table", [
    "patient_billing_report_rows", "patient_bill_billing_report_rows",
    "patient_detail_cache", "patient_outcome_base", "cohort_optimization_summary",
    "patient_alerts_summary", "cohort_recovery_summary", "cohort_compliance_index",
    "patient_alerts_payload", "wavea_evidence_detail", "wavea_bill_evidence_detail",
    "wavea_evidence_index",
])
def test_enabled_transition_does_not_drop_unrelated_payload_semantics(tmp_path, table):
    baseline, candidate, _ = _current_fixture(tmp_path)
    proof = _cache_proof(baseline, candidate)
    _mutate_payload(candidate, table, lambda row: row.update({"unreviewed_change": "drift"}))
    with pytest.raises(ValueError):
        _parity(baseline, candidate, proof)


@pytest.mark.parametrize("table,statement", [
    ("cohort_sut_summary", "INSERT INTO cohort_sut_summary VALUES ('candidate', '{}')"),
    ("validation_payload", "INSERT INTO validation_payload VALUES ('candidate', '{}', '{}')"),
    ("patient_meta", "UPDATE patient_meta SET age = 999 WHERE build_id = 'candidate'"),
    ("cohort_sut_exposure", "INSERT INTO cohort_sut_exposure VALUES ('candidate', '{}')"),
    ("patient_diagnoses", "INSERT INTO patient_diagnoses VALUES ('candidate', 'P1', '[\"Q99\"]')"),
    ("patient_alert_rows", "UPDATE patient_alert_rows SET copay_action = 'unexpected' WHERE build_id = 'candidate'"),
    ("patient_billing_reports", "INSERT INTO patient_billing_reports VALUES ('candidate', '{}')"),
])
def test_enabled_transition_keeps_the_other_row_tables_strict(tmp_path, table, statement):
    baseline, candidate, _ = _current_fixture(tmp_path)
    proof = _cache_proof(baseline, candidate)
    with duckdb.connect(str(candidate)) as con:
        con.execute(statement)
    with pytest.raises(ValueError, match=f"Current {table} payload drift"):
        _parity(baseline, candidate, proof)


@pytest.mark.parametrize("table", ["wavea_evidence_detail", "wavea_bill_evidence_detail"])
def test_enabled_transition_remains_exhaustive_beyond_five_hundred_evaluations(tmp_path, table):
    baseline, candidate, _ = _current_fixture(tmp_path)
    proof = _cache_proof(baseline, candidate)

    def corrupt_last(row):
        assert len(row["evaluations"]) > 500
        row["evaluations"][-1]["explanation"] = "unreviewed source interpretation"

    _mutate_payload(candidate, table, corrupt_last)
    with pytest.raises(ValueError, match=f"Current {table} payload drift"):
        _parity(baseline, candidate, proof)


@pytest.mark.parametrize("value", [None, False, 0, -0.0, "0.0", 0.01])
def test_enabled_transition_preserves_financial_null_bool_and_numeric_representation(tmp_path, value):
    baseline, candidate, _ = _current_fixture(tmp_path)
    for path in (baseline, candidate):
        _mutate_payload(path, "patient_bill_billing_report_rows", lambda row: row.update({"sgk_uplift_try": 0.0}))
    proof = _cache_proof(baseline, candidate)
    _mutate_payload(candidate, "patient_bill_billing_report_rows", lambda row: row.update({"sgk_uplift_try": value}))
    with pytest.raises(ValueError, match="Current patient_bill_billing_report_rows payload drift"):
        _parity(baseline, candidate, proof)
