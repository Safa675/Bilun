"""Fabricated machine: exercise orchestration, ordering, and real DuckDB snapshots."""

from __future__ import annotations

import json
import fcntl
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from dataclasses import replace
from functools import wraps
from types import SimpleNamespace

from tests.unit.deploy.probe_auth_fixtures import write_old_auth

import duckdb
import pytest

from scripts.deploy import prepare_single_vps_release as module

TARGET = "a" * 40
OLD = "b" * 40


def old_python_context(tmp_path: Path, *, environment_sha256="e" * 64,
                       name="old-python", terminal: Path | None = None):
    """Real launcher links and venv bytes; the process is never executed."""
    context = tmp_path / name
    (context / "bin").mkdir(parents=True)
    packages = context / "lib/python3.13/site-packages"
    packages.mkdir(parents=True)
    (packages / "old_dependency.py").write_text("CONTEXT = " + repr(name) + "\n")
    (context / "pyvenv.cfg").write_text("home = /fixture/base-python\ninclude-system-site-packages = false\n")
    if terminal is None:
        terminal = tmp_path / "python3.13"
        terminal.write_bytes(b"independently observed terminal executable fixture\n")
        terminal.chmod(0o755)
    intermediate = context / "bin/python3"
    intermediate.symlink_to(terminal)
    launcher = context / "bin/python"
    launcher.symlink_to("python3")
    dependencies = (context, intermediate, terminal)
    pins = module._pin_inputs(set(dependencies), set(), dependency_roots=dependencies,
                              allow_dependency_file_links=True)
    service = SimpleNamespace(
        process_argv=(str(launcher), "-m", "uvicorn", "src.bilun.api:app",
                      "--host", "127.0.0.1", "--port", "8001"),
        process_executable=terminal, environment_sha256=environment_sha256,
    )
    identity = module._capture_old_backend_python_identity(
        service, dependency_roots=dependencies, dependency_pins=pins,
        allow_dependency_file_links=True,
    )
    return SimpleNamespace(context=context, terminal=terminal, launcher=launcher,
                           intermediate=intermediate, dependencies=dependencies,
                           pins=pins, service=service, identity=identity,
                           packages=packages)


def old_python_record(root: Path, old, *, runtime_sha256="a" * 64) -> tuple[Path, str]:
    """Bind the identity to independently recorded process/environment digests."""
    path = root / "live-after-snapshot.json"
    save(path, {
        "backend_runtime_sha256": runtime_sha256,
        "backend": {
            "process_executable": str(old.service.process_executable),
            "process_argv_sha256": hashlib.sha256(
                b"\0".join(argument.encode() for argument in old.service.process_argv)
            ).hexdigest(),
            "effective_environment_sha256": old.service.environment_sha256,
            "old_backend_python_identity": old.identity,
        },
    })
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def load_old_python_record(tmp_path, old, path, digest):
    snapshot = tmp_path / "old-snapshot"
    snapshot.mkdir(exist_ok=True)
    return module._load_old_backend_python_identity(
        path, digest, old_snapshot=snapshot, old_runtime_sha256="a" * 64,
        old_environment_sha256=old.service.environment_sha256,
        dependency_roots=old.dependencies,
    )


def test_old_python_identity_preserves_launcher_context_and_terminal(tmp_path):
    old = old_python_context(tmp_path)
    launcher, terminal = module._verify_old_backend_python_identity(old.identity)
    assert launcher == old.launcher and terminal == old.terminal
    assert launcher != terminal and launcher.resolve(strict=True) == terminal
    assert old.identity["context_root"] == str(old.context)
    record, digest = old_python_record(tmp_path, old)
    assert load_old_python_record(tmp_path, old, record, digest) == old.identity


def test_old_python_identity_accepts_a_separately_pinned_shared_candidate_terminal(tmp_path):
    old = old_python_context(tmp_path)
    pins = module._pin_inputs(set(old.dependencies), {old.terminal},
                              dependency_roots=old.dependencies,
                              allow_dependency_file_links=True)
    assert pins[str(old.terminal)]["executable_target"] == str(old.terminal)
    old.identity = module._capture_old_backend_python_identity(
        old.service, dependency_roots=old.dependencies, dependency_pins=pins,
        allow_dependency_file_links=True,
    )
    assert module._verify_old_backend_python_identity(old.identity) == (old.launcher, old.terminal)
    record, digest = old_python_record(tmp_path, old)
    assert load_old_python_record(tmp_path, old, record, digest) == old.identity


@pytest.mark.parametrize("missing", ["context", "intermediate", "terminal"])
def test_old_python_capture_requires_explicit_context_and_link_terminal_roles(tmp_path, missing):
    old = old_python_context(tmp_path)
    omitted = {"context": old.context, "intermediate": old.intermediate,
               "terminal": old.terminal}[missing]
    dependencies = tuple(path for path in old.dependencies if path != omitted)
    with pytest.raises(ValueError):
        module._capture_old_backend_python_identity(
            old.service, dependency_roots=dependencies,
            dependency_pins={str(path): old.pins[str(path)] for path in dependencies},
            allow_dependency_file_links=True,
        )


@pytest.mark.parametrize("changed", ["pyvenv_cfg", "site_packages", "link", "terminal"])
def test_old_python_frozen_identity_rejects_real_dependency_mutation(tmp_path, changed):
    old = old_python_context(tmp_path)
    if changed == "pyvenv_cfg":
        (old.context / "pyvenv.cfg").write_text("home = /different/base-python\n")
    elif changed == "site_packages":
        (old.packages / "old_dependency.py").write_text("CONTEXT = 'changed'\n")
    elif changed == "terminal":
        old.terminal.write_bytes(b"changed terminal executable\n")
    else:
        old.launcher.unlink()
        old.launcher.symlink_to(old.terminal)
    with pytest.raises(ValueError):
        module._verify_old_backend_python_identity(old.identity)


@pytest.mark.parametrize("replacement", ["candidate", "same_terminal_other_venv"])
def test_old_python_record_rejects_resealed_interpreter_substitution(tmp_path, replacement):
    old = old_python_context(tmp_path)
    other = old_python_context(tmp_path, name=replacement, terminal=old.terminal)
    assert other.launcher.resolve(strict=True) == old.launcher.resolve(strict=True)
    assert hashlib.sha256(other.terminal.read_bytes()).digest() == hashlib.sha256(old.terminal.read_bytes()).digest()
    assert (other.packages / "old_dependency.py").read_bytes() != (old.packages / "old_dependency.py").read_bytes()
    record, _ = old_python_record(tmp_path, old)
    value = json.loads(record.read_bytes())
    value["backend"]["old_backend_python_identity"] = other.identity
    save(record, value)
    # Rehashing a private file cannot grant authority over the original argv.
    with pytest.raises(ValueError):
        load_old_python_record(tmp_path, old, record, hashlib.sha256(record.read_bytes()).hexdigest())


def test_old_python_frozen_record_rejects_same_terminal_context_swap_with_both_roots_declared(tmp_path):
    old = old_python_context(tmp_path)
    other = old_python_context(tmp_path, name="candidate-python", terminal=old.terminal)
    old.dependencies = tuple(dict.fromkeys((*old.dependencies, *other.dependencies)))
    old.pins = module._pin_inputs(set(old.dependencies), set(), dependency_roots=old.dependencies,
                                 allow_dependency_file_links=True)
    old.identity = module._capture_old_backend_python_identity(
        old.service, dependency_roots=old.dependencies, dependency_pins=old.pins,
        allow_dependency_file_links=True,
    )
    record, producer_digest = old_python_record(tmp_path, old)
    assert load_old_python_record(tmp_path, old, record, producer_digest) == old.identity
    changed = json.loads(record.read_bytes())
    identity = changed["backend"]["old_backend_python_identity"]
    identity["launcher_path"] = str(other.launcher)
    identity["context_root"] = str(other.context)
    # Both contexts and their common executable were authorized dependencies;
    # they are still distinct from the particular launcher observed at capture.
    assert identity["dependency_roots"] == old.identity["dependency_roots"]
    assert identity["dependency_pins"] == old.identity["dependency_pins"]
    assert identity["process_argv_sha256"] == old.identity["process_argv_sha256"]
    assert identity["effective_environment_sha256"] == old.identity["effective_environment_sha256"]
    save(record, changed)
    with pytest.raises(ValueError, match="frozen observation"):
        load_old_python_record(tmp_path, old, record, producer_digest)


@pytest.mark.parametrize("fault", ["file_digest", "omitted_identity", "omitted_key", "extra_key",
                                   "argv_digest", "environment_digest", "runtime_digest"])
def test_old_python_record_rejects_tamper_or_missing_original_binding(tmp_path, fault):
    old = old_python_context(tmp_path)
    record, digest = old_python_record(tmp_path, old)
    value = json.loads(record.read_bytes())
    if fault == "file_digest":
        record.write_bytes(record.read_bytes() + b"\n")
    else:
        if fault == "omitted_identity":
            del value["backend"]["old_backend_python_identity"]
        elif fault == "omitted_key":
            del value["backend"]["old_backend_python_identity"]["launcher_path"]
        elif fault == "extra_key":
            value["backend"]["old_backend_python_identity"]["fallback_python"] = str(old.terminal)
        elif fault == "argv_digest":
            value["backend"]["process_argv_sha256"] = "0" * 64
        elif fault == "environment_digest":
            value["backend"]["effective_environment_sha256"] = "0" * 64
        else:
            value["backend_runtime_sha256"] = "0" * 64
        save(record, value)
        digest = hashlib.sha256(record.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        load_old_python_record(tmp_path, old, record, digest)


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value))
    path.chmod(0o600)


def cache(path: Path, build: str, code: str) -> None:
    with duckdb.connect(str(path)) as connection:
        connection.execute("CREATE TABLE build_meta(build_id VARCHAR, code_sha VARCHAR, source_hash VARCHAR, config_hash VARCHAR, status VARCHAR, build_scope VARCHAR)")
        connection.execute("INSERT INTO build_meta VALUES (?, ?, ?, ?, 'complete', 'bilun')", [build, code, "c" * 64, "d" * 64])
        connection.execute("CREATE TABLE build_pointer_scopes(scope VARCHAR, active_build_id VARCHAR)")
        connection.execute("INSERT INTO build_pointer_scopes VALUES ('bilun', ?)", [build])
    path.chmod(0o600)


@pytest.fixture
def machine(tmp_path: Path, monkeypatch):
    tmp_path.chmod(0o700)
    inputs = tmp_path / "inputs"
    inputs.mkdir(mode=0o700)
    spec = {"schema_version": module.SCHEMA, "release_id": "test-release", "target_sha": TARGET,
            "ci_run_id": "42", "baseline_code_sha": OLD, "serving_code_sha": OLD,
            "old_build_id": "old", "data_mode": "synthetic_demo", "patient_id": "patient-1",
            "payload_workers": 1, "billing_workers": 3,
            "baseline_build_config_environment": dict.fromkeys(module._CONFIG_KEYS, "")}
    directories = {"repository", "baseline_checkout", "baseline_claims_dir", "baseline_clean_dir",
                   "live_backend_runtime", "live_frontend_runtime"}
    absent = {"bundle_root", "backend_dropin", "frontend_dropin", "lock_path", "frontend_current"}
    for key in module._PATHS:
        path = tmp_path / "bundle" if key == "bundle_root" else inputs / key
        spec[key] = str(path)
        if key in directories:
            path.mkdir(mode=0o700)
            (path / "input.txt").write_text(key)
        elif key not in absent:
            path.write_bytes(b"x" * 32)
            path.chmod(0o600)
    for key in ("candidate_backend_environment", "candidate_frontend_environment"):
        Path(spec[key]).write_bytes(b"EXISTING=value\0")
    Path(spec["live_cache_path"]).unlink()
    write_old_auth(Path(spec["live_backend_runtime"]))
    cache(Path(spec["live_cache_path"]), "old", OLD)
    Path(spec["frontend_current"]).symlink_to(spec["live_frontend_runtime"])
    dependency = inputs / "dependencies"
    dependency.mkdir()
    (dependency / "module.py").write_text("# fixed dependency\n")
    mutable = inputs / "mutable.sqlite"
    mutable.write_bytes(b"external-state")
    spec["dependency_roots"] = [str(dependency)]
    spec["external_state_paths"] = [str(mutable)]
    manifest = tmp_path / "machine.json"
    save(manifest, spec)
    events = []
    root = Path(spec["bundle_root"])
    live_bytes = Path(spec["live_cache_path"]).read_bytes()
    baseline = {"roster_version": "wavea-source-v1", "code_sha": OLD}

    def event(name):
        events.append(name)

    def ci(**kwargs):
        event("ci")
        assert kwargs["code_sha"] == TARGET and kwargs["run_id"] == "42"
        return {"status": "release_ci_verified", "code_sha": TARGET, "ci_run_id": "42"}

    def observe(spec):
        event("observe")
        return {"cache": module._candidate_db_hash(Path(spec["live_cache_path"])),
                "frontend": str(Path(spec["frontend_current"]).resolve()), "services": "unchanged",
                "backend": {"effective_environment_sha256": "e" * 64},
                "backend_runtime_sha256": module._runtime_digest(Path(spec["live_backend_runtime"]), backend=True)}

    def snapshot(spec, before):
        event("snapshot")
        (root / "old-snapshot").mkdir(mode=0o700)
        shutil.copy2(spec["live_cache_path"], root / "old-snapshot/cache.duckdb")
        shutil.copy2(spec["live_cache_path"], root / "baseline.duckdb")
        return before

    def baseline_roster(spec):
        event("baseline")
        return baseline

    def checkout(spec):
        event("checkout")
        out = root / "candidate-backend"
        out.mkdir()
        (out / "code.py").write_text("# exact target\n")
        write_old_auth(out)
        claims, clean = out / "claims", out / "clean"
        claims.mkdir()
        clean.mkdir()
        return out, claims, clean

    def frontend(spec, checkout):
        event("frontend")
        out = root / "candidate-frontend"
        out.mkdir()
        (out / "server.js").write_text("// compiled frontend\n")
        return out

    def roster(checkout, **kwargs):
        event("roster")
        return {"code_sha": kwargs["code_sha"], "checkout": str(checkout)}

    def build(**kwargs):
        event("build")
        assert kwargs["payload_workers"] == 1 and kwargs["billing_workers"] == 3
        assert (root / "baseline-roster.json").is_file()
        assert (root / "candidate-frontend/server.js").is_file()
        cache(kwargs["db_path"], "new", TARGET)
        for key in ("trace_path", "log_path"):
            kwargs[key].write_text("fabricated private build output")
        save(kwargs["report_path"], {"build_id": "new"})
        return {"build_id": "new"}

    def structural(*args, **kwargs):
        event("structural")
        return {"status": "all_rows_structurally_verified"}

    def bridge(*args, **kwargs):
        event("bridge")
        assert args[0].read_bytes() == kwargs["baseline_db"].read_bytes()
        return {"status": "serving_baseline_legacy_equivalent"}

    def semantic(*args, **kwargs):
        event("semantic")
        assert (root / "structural.json").is_file()
        return {"status": "semantic_checkpoint_verified"}

    def trace(**kwargs):
        event("trace")
        assert kwargs["payload_workers"] == 1 and kwargs["billing_workers"] == 3
        return {"status": "traced_build_attestation_verified"}

    def rehearse(*args):
        event("rehearse")
        assert (root / "semantic.json").is_file() and (root / "trace-attestation.json").is_file()
        directory = root / "rehearsal"
        directory.mkdir(mode=0o700)
        for name in ("real-candidate-namespace-rehearsal.json", "candidate-tuple-observation.json"):
            save(directory / name, {"passed": True})

    def sidecar(**kwargs):
        event("sidecar")
        assert kwargs["rehearsal_path"].is_file()
        save(kwargs["evidence_dir"] / "sidecar.json", {"passed": True})
        return {"status": "wavea_sidecar_built"}

    def issue(*, old_snapshot_journal_path=None, old_snapshot_journal_identity_sha256=None, **kwargs):
        if spec.get("snapshot_mode") == "early-owned-maintenance":
            from scripts.deploy.snapshot_maintenance import assert_held_snapshot

            assert old_snapshot_journal_path == root / "snapshot-maintenance/transaction.json"
            assert old_snapshot_journal_identity_sha256 is not None
            held = assert_held_snapshot(old_snapshot_journal_path,
                                        expected_identity_sha256=old_snapshot_journal_identity_sha256)
            assert held["state"] == "held"
            assert held["identity_sha256"] == old_snapshot_journal_identity_sha256
        else:
            assert old_snapshot_journal_path is None and old_snapshot_journal_identity_sha256 is None
        event("issue")
        assert events.count("ci") == 2
        assert kwargs["use_existing_key"] is True
        assert kwargs["payload_workers"] == 1 and kwargs["billing_workers"] == 3
        assert kwargs["serving_code_sha"] == OLD
        save(kwargs["receipt_path"], {"signed": True})
        return {"status": "private_activation_receipt_issued"}

    for name, replacement in {
        "_github_read_token": lambda: "existing-read-token",
        "fetch_successful_release_ci": ci, "candidate_environments": lambda *args: ({}, {}),
        "_observe_live": observe, "_snapshot_old": snapshot, "_baseline_roster": baseline_roster,
        "_create_checkout": checkout, "_build_frontend": frontend, "generate_source_roster": roster,
        "build_traced_candidate": build, "verify_candidate_cache": structural,
        "verify_serving_baseline_equivalence": bridge, "verify_candidate_semantic_checkpoint": semantic,
        "verify_traced_build_attestation": trace, "_rehearse": rehearse,
        "build_wavea_sidecar": sidecar, "issue_wavea_activation": issue,
    }.items():
        monkeypatch.setattr(module, name, replacement)
    return manifest, spec, events, live_bytes


def test_constructs_all_artifacts_in_dependency_order(machine):
    manifest, spec, events, original = machine
    result = module.prepare_release_bundle(manifest)
    root = Path(spec["bundle_root"])
    assert events == ["ci", "observe", "snapshot", "baseline", "checkout", "frontend", "roster",
                      "build", "structural", "bridge", "semantic", "trace", "rehearse", "sidecar",
                      "observe", "baseline", "roster", "ci", "issue", "observe"]
    assert result["production_mutated"] is False
    assert result["snapshot_mode"] == "online-read-lock"
    assert result["public_activation_ready"] is False
    assert json.loads((root / "prepared.json").read_text()) == result
    paired = json.loads(Path(result["paired_manifest_path"]).read_text())
    assert paired["schema_version"] == "bilun-single-vps-pair-v1"
    launch = json.loads(Path(paired["candidate_launch_config"]).read_text())
    assert launch["profile"] == "single-vps-same-port-v2"
    assert launch["activation_key_path"] == spec["signing_key_path"]
    module.verify_preparation_pins(Path(paired["preparation_pins_path"]), paired["preparation_pins_sha256"])
    assert Path(spec["live_cache_path"]).read_bytes() == original
    assert Path(spec["signing_key_path"]).read_bytes() == b"x" * 32
    assert Path(spec["frontend_current"]).resolve() == Path(spec["live_frontend_runtime"])


def test_early_owned_maintenance_requires_explicit_manifest_opt_in(machine):
    manifest, spec, events, _ = machine
    assert module.load_preparation_manifest(manifest)["snapshot_mode"] == "online-read-lock"
    spec["snapshot_mode"] = "early-owned-maintenance"
    save(manifest, spec)
    assert module.load_preparation_manifest(manifest)["snapshot_mode"] == "early-owned-maintenance"
    assert events == [] and not Path(spec["bundle_root"]).exists()


@pytest.mark.parametrize("mode", [True, None, "early_owned_maintenance", "early-owned-maintenance "])
def test_ambiguous_early_maintenance_mode_has_no_service_or_capture_effect(machine, mode):
    manifest, spec, events, _ = machine
    spec["snapshot_mode"] = mode
    save(manifest, spec)
    with pytest.raises(ValueError, match="Snapshot mode"):
        module.prepare_release_bundle(manifest)
    assert events == [] and not Path(spec["bundle_root"]).exists()


def test_handoff_dependency_pin_rejects_postprepare_external_venv_change(machine):
    manifest, spec, _, _ = machine
    result = module.prepare_release_bundle(manifest)
    paired = json.loads(Path(result["paired_manifest_path"]).read_text())
    (Path(spec["dependency_roots"][0]) / "module.py").write_text("# replacement dependency")
    with pytest.raises(ValueError, match="dependency bytes"):
        module.verify_preparation_pins(Path(paired["preparation_pins_path"]), paired["preparation_pins_sha256"])


def test_handoff_mutable_pin_allows_new_records_but_rejects_path_replacement(machine):
    manifest, spec, _, _ = machine
    result = module.prepare_release_bundle(manifest)
    paired = json.loads(Path(result["paired_manifest_path"]).read_text())
    target = Path(spec["external_state_paths"][0])
    target.write_bytes(b"new live records")
    module.verify_preparation_pins(Path(paired["preparation_pins_path"]), paired["preparation_pins_sha256"])
    replacement = target.with_suffix(".new")
    replacement.write_bytes(b"replacement")
    os.replace(replacement, target)
    with pytest.raises(ValueError, match="ownership changed"):
        module.verify_preparation_pins(Path(paired["preparation_pins_path"]), paired["preparation_pins_sha256"])


@pytest.mark.parametrize("stage", ["_snapshot_old", "_baseline_roster", "_create_checkout", "_build_frontend",
                                  "build_traced_candidate", "verify_candidate_cache",
                                  "verify_candidate_semantic_checkpoint", "verify_traced_build_attestation",
                                  "_rehearse", "build_wavea_sidecar", "issue_wavea_activation"])
def test_failure_never_changes_live_pair_or_emits_prepared(machine, monkeypatch, stage):
    manifest, spec, events, original = machine

    def fail(*args, **kwargs):
        raise ValueError("injected stage failure")

    monkeypatch.setattr(module, stage, fail)
    with pytest.raises(ValueError, match="injected"):
        module.prepare_release_bundle(manifest)
    root = Path(spec["bundle_root"])
    assert not (root / "prepared.json").exists()
    assert not (root / "paired-manifest.json").exists()
    assert (root / "failed.json").is_file()
    assert Path(spec["live_cache_path"]).read_bytes() == original
    assert Path(spec["frontend_current"]).resolve() == Path(spec["live_frontend_runtime"])
    assert Path(spec["signing_key_path"]).read_bytes() == b"x" * 32
    if stage != "issue_wavea_activation":
        assert "issue" not in events


@pytest.mark.parametrize("when", [1, 2])
def test_stale_ci_stops_before_signing(machine, monkeypatch, when):
    manifest, spec, events, original = machine
    original_ci = module.fetch_successful_release_ci
    calls = 0

    def ci(**kwargs):
        nonlocal calls
        calls += 1
        if calls == when:
            raise ValueError("exact main moved or CI not successful")
        return original_ci(**kwargs)

    monkeypatch.setattr(module, "fetch_successful_release_ci", ci)
    with pytest.raises(ValueError, match="main moved"):
        module.prepare_release_bundle(manifest)
    assert "issue" not in events
    assert not (Path(spec["bundle_root"]) / "prepared.json").exists()
    assert Path(spec["live_cache_path"]).read_bytes() == original
    if when == 1:
        assert not Path(spec["bundle_root"]).exists()


@pytest.mark.parametrize("changed", ["external", "runtime", "roster", "live"])
def test_stale_source_and_mutable_state_fail_before_signing(machine, monkeypatch, changed):
    manifest, spec, events, original = machine
    sidecar = module.build_wavea_sidecar

    def mutate(**kwargs):
        result = sidecar(**kwargs)
        if changed == "external":
            target = Path(spec["external_state_paths"][0])
            replacement = target.with_suffix(".replacement")
            replacement.write_bytes(b"replaced ownership identity")
            os.replace(replacement, target)
        elif changed == "runtime":
            (Path(spec["bundle_root"]) / "candidate-backend/code.py").write_text("changed")
        elif changed == "roster":
            monkeypatch.setattr(module, "generate_source_roster", lambda *args, **kwargs: {"changed": True})
        else:
            monkeypatch.setattr(module, "_observe_live", lambda spec: {"services": "restarted"})
        return result

    monkeypatch.setattr(module, "build_wavea_sidecar", mutate)
    with pytest.raises(ValueError, match="changed"):
        module.prepare_release_bundle(manifest)
    assert "issue" not in events
    assert Path(spec["live_cache_path"]).read_bytes() == original


def test_external_ledger_contents_can_evolve_without_reset_or_copy(machine, monkeypatch):
    manifest, spec, _, _ = machine
    sidecar = module.build_wavea_sidecar
    target = Path(spec["external_state_paths"][0])
    inode = target.stat().st_ino

    def update(**kwargs):
        result = sidecar(**kwargs)
        target.write_bytes(b"new live audit records")
        return result

    monkeypatch.setattr(module, "build_wavea_sidecar", update)
    assert module.prepare_release_bundle(manifest)["status"] == "release_bundle_prepared"
    assert target.read_bytes() == b"new live audit records" and target.stat().st_ino == inode


def test_shared_machine_lock_blocks_concurrent_preparation(machine):
    manifest, spec, events, _ = machine
    descriptor = os.open(spec["lock_path"], os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="shared machine lock"):
            module.prepare_release_bundle(manifest)
    finally:
        os.close(descriptor)
    assert events == [] and not Path(spec["bundle_root"]).exists()


def test_configured_ledger_cannot_be_omitted_before_maintenance(machine, monkeypatch):
    manifest, spec, events, _ = machine
    ledger = spec["external_state_paths"][0]
    spec["external_state_paths"] = []
    spec["snapshot_mode"] = "brief-maintenance"
    save(manifest, spec)
    monkeypatch.setattr(module, "candidate_environments", lambda *args: (
        {"BILUN_PUBLIC_CHAT_BUDGET_DB": ledger}, {},
    ))
    monkeypatch.setattr(module, "_observe_live", lambda spec: {
        "backend": {"persistent_state_settings": {"BILUN_PUBLIC_CHAT_BUDGET_DB": ledger}},
    })
    with pytest.raises(ValueError, match="missing from explicit external state inventory"):
        module.prepare_release_bundle(manifest)
    assert "snapshot" not in events and not Path(spec["bundle_root"]).exists()


def test_successful_prepare_retry_reuses_exact_bundle(machine):
    manifest, spec, events, _ = machine
    first = module.prepare_release_bundle(manifest)
    completed = list(events)
    assert module.prepare_release_bundle(manifest) == first
    assert events == completed
    spec["billing_workers"] = 4
    save(manifest, spec)
    with pytest.raises(ValueError, match="different preparation request"):
        module.prepare_release_bundle(manifest)


def test_invalid_candidate_metadata_stops_before_structural_gate(machine, monkeypatch):
    manifest, spec, events, original = machine
    build = module.build_traced_candidate

    def invalid(**kwargs):
        result = build(**kwargs)
        with duckdb.connect(str(kwargs["db_path"])) as connection:
            connection.execute("UPDATE build_meta SET status='building'")
        return result

    monkeypatch.setattr(module, "build_traced_candidate", invalid)
    with pytest.raises(ValueError, match="metadata"):
        module.prepare_release_bundle(manifest)
    assert "structural" not in events and "rehearse" not in events and "issue" not in events
    assert Path(spec["live_cache_path"]).read_bytes() == original


@pytest.mark.parametrize("field,value", [("payload_workers", True), ("billing_workers", 9),
                                       ("target_sha", "main"), ("ci_run_id", "0"),
                                       ("unknown_field", "value"), ("dependency_roots", []),
                                       ("schema_version", []), ("schema_version", {})])
def test_manifest_rejects_ambiguous_inputs_before_any_work(machine, field, value):
    manifest, spec, events, _ = machine
    spec[field] = value
    save(manifest, spec)
    with pytest.raises(ValueError):
        module.prepare_release_bundle(manifest)
    assert events == []
    assert not Path(spec["bundle_root"]).exists()


def test_consistent_snapshot_preserves_exact_bytes(tmp_path):
    source, copy = tmp_path / "live.duckdb", tmp_path / "copy.duckdb"
    cache(source, "old", OLD)
    original = source.read_bytes()
    module._copy_cache_consistently(source, copy, "old")
    assert source.read_bytes() == original == copy.read_bytes()
    assert source.stat().st_ino != copy.stat().st_ino


@pytest.mark.parametrize("broken_symlink", [False, True])
def test_snapshot_refuses_any_wal_without_touching_live(tmp_path, broken_symlink):
    source, copy = tmp_path / "live.duckdb", tmp_path / "copy.duckdb"
    cache(source, "old", OLD)
    wal = source.with_suffix(".duckdb.wal")
    if broken_symlink:
        wal.symlink_to(tmp_path / "absent")
    else:
        wal.write_bytes(b"uncheckpointed")
    before = source.read_bytes()
    with pytest.raises(ValueError, match="WAL"):
        module._copy_cache_consistently(source, copy, "old")
    assert not copy.exists() and source.read_bytes() == before
    assert os.path.lexists(wal)


def test_snapshot_refuses_idle_writer_owned_cache_without_stopping_it(tmp_path):
    source, copy = tmp_path / "live.duckdb", tmp_path / "copy.duckdb"
    cache(source, "old", OLD)
    before = source.read_bytes()
    with duckdb.connect(str(source)) as writer:
        writer.execute("CHECKPOINT")
        with pytest.raises(duckdb.Error):
            module._copy_cache_consistently(source, copy, "old")
        assert writer.execute("SELECT count(*) FROM build_meta").fetchone() == (1,)
    assert not copy.exists() and source.read_bytes() == before


def test_snapshot_with_real_other_process_writer(tmp_path):
    source, copy = tmp_path / "live.duckdb", tmp_path / "copy.duckdb"
    cache(source, "old", OLD)
    script = "import duckdb,sys; c=duckdb.connect(sys.argv[1]); c.execute('CHECKPOINT'); print('ready',flush=True); input(); c.close()"
    child = subprocess.Popen([sys.executable, "-c", script, str(source)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        with pytest.raises(duckdb.Error, match="lock"):
            duckdb.connect(str(source), read_only=True)
        with pytest.raises(duckdb.Error, match="lock"):
            module._copy_cache_consistently(source, copy, "old")
        assert child.poll() is None
        assert not copy.exists()
    finally:
        child.communicate("\n", timeout=10)
        assert child.returncode == 0


@pytest.mark.parametrize("change", ["wal", "stat", "replace"])
def test_snapshot_rejects_state_drift_during_copy(tmp_path, monkeypatch, change):
    source, copy = tmp_path / "live.duckdb", tmp_path / "copy.duckdb"
    cache(source, "old", OLD)
    stream = module.shutil.copyfileobj

    def changed(*args, **kwargs):
        stream(*args, **kwargs)
        if change == "wal":
            source.with_suffix(".duckdb.wal").write_bytes(b"committed WAL appeared")
        elif change == "stat":
            os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1))
        else:
            replacement = source.with_suffix(".replacement")
            replacement.write_bytes(source.read_bytes())
            os.replace(replacement, source)

    monkeypatch.setattr(module.shutil, "copyfileobj", changed)
    with pytest.raises(ValueError, match="WAL|moved"):
        module._copy_cache_consistently(source, copy, "old")


def test_frontend_snapshot_retains_settled_image_cache_bytes_and_strict_digest(tmp_path):
    source, destination = tmp_path / "frontend", tmp_path / "snapshot"
    image = source / ".next/cache/images/authored-key/fixture.webp"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"authored synthetic stopped image cache")
    (source / "server.js").write_bytes(b"authored synthetic standalone")
    before = module._runtime_digest(source, backend=False)
    module._copy_runtime(source, destination, backend=False)
    assert (destination / image.relative_to(source)).read_bytes() == image.read_bytes()
    assert module._runtime_digest(source, backend=False) == before
    assert module._runtime_digest(destination, backend=False) == before


@pytest.mark.parametrize("existed", [False, True])
def test_frontend_snapshot_rejects_image_cache_write_during_real_copy(tmp_path, monkeypatch, existed):
    source, destination = tmp_path / "frontend", tmp_path / "snapshot"
    image = source / ".next/cache/images/authored-key/fixture.webp"
    image.parent.mkdir(parents=True)
    (source / "server.js").write_bytes(b"authored synthetic standalone")
    if existed:
        image.write_bytes(b"settled authored image cache")
    copytree = module.shutil.copytree

    def late_write(*args, **kwargs):
        result = copytree(*args, **kwargs)
        if Path(args[0]) == source:
            image.write_bytes(b"late authored image cache")
        return result

    monkeypatch.setattr(module.shutil, "copytree", late_write)
    with pytest.raises(ValueError, match="runtime changed"):
        module._copy_runtime(source, destination, backend=False)
    assert image.read_bytes() == b"late authored image cache"


def _early_private_capture(tmp_path, monkeypatch):
    """Reuse real held maintenance; only OS/process observations are fabricated.

    The fresh preparer executes its original snapshot/private inventory logic,
    copies and hash functions. The sibling helper runs original ownership and
    loaded/installed route checks with disposable systemd/Caddy observations.
    """
    from scripts.deploy import paired_release as paired
    from scripts.deploy import snapshot_maintenance as maintenance
    from scripts.deploy.capture_release_preflight import ServiceObservation
    from scripts.deploy.service_identity import stable_environment_sha256
    from tests.unit.deploy.test_observe_candidate_tuple import _process
    from tests.unit.deploy.test_snapshot_maintenance import _held_host

    definition = spec_from_file_location("private_stopped_capture_test", module.__file__)
    fresh = module_from_spec(definition)
    definition.loader.exec_module(fresh)
    host = _held_host(tmp_path, monkeypatch)
    bundle = tmp_path / "bundle"
    bundle.mkdir(mode=0o700)
    host.journal = bundle / "snapshot-maintenance/transaction.json"
    host.output = bundle / "old-snapshot/cache.duckdb"
    spec = {**host.spec, "bundle_root": bundle, "lock_path": host.lock,
            "snapshot_mode": "early-owned-maintenance"}
    proc = tmp_path / "proc"
    proc.mkdir(mode=0o700)
    services, environments = {}, {}
    for role, pid in (("backend", 101), ("frontend", 202)):
        raw = f"AUTH_SECRET=authored-{role}-only\0BILUN_CACHE_DB_PATH={host.live}\0".encode()
        environment_sha = hashlib.sha256(b"\0".join(sorted(raw[:-1].split(b"\0")))).hexdigest()
        executable = Path(sys.executable).resolve()
        if role == "backend":
            old = old_python_context(tmp_path, environment_sha256=environment_sha)
            executable = old.terminal
            argv = old.service.process_argv
            spec["dependency_roots"] = old.dependencies
            spec["_old_backend_python_authority"] = {
                "dependency_roots": old.dependencies, "dependency_pins": old.pins,
                "allow_dependency_file_links": True,
            }
        else:
            argv = (str(executable), str(tmp_path / role / "source"))
        _process(proc, pid, tmp_path / role, b"\0".join(arg.encode() for arg in argv) + b"\0", raw)
        (proc / str(pid) / "exe").unlink()
        (proc / str(pid) / "exe").symlink_to(executable)
        (proc / str(pid) / "status").write_text("Uid:\t0\t0\t0\t0\n")
        service = ServiceObservation(
            unit=f"bilun-{role}.service", active_state="active", main_pid=pid, listener_pid=pid,
            declared_working_directory=tmp_path / role, process_working_directory=tmp_path / role,
            process_executable=executable, process_argv=argv,
            unit_sha256=hashlib.sha256((tmp_path / f"{role}.service").read_bytes()).hexdigest(),
            unit_fragment=str(tmp_path / f"{role}.service"), unit_files=(tmp_path / f"{role}.service",),
            environment_files=(tmp_path / f"{role}.env",), selected_environment={"BILUN_STARTUP_POLICY": "load-only"},
            environment_sha256=environment_sha,
            process_started_at_utc=datetime.now(UTC),
        )
        services[role] = service
        environments[role] = raw
        host.expected[role] = {**fresh._public_service(service), "stable_environment_sha256": stable_environment_sha256(raw)}

    def path(*args, **kwargs):
        value = Path(*args, **kwargs)
        return proc / value.relative_to("/proc") if value.is_relative_to("/proc") else value

    monkeypatch.setattr(fresh, "Path", path)
    def observe(unit, _port):
        role = unit.removeprefix("bilun-").removesuffix(".service")
        service = services[role]
        current = proc / str(service.listener_pid)
        return replace(service, unit_sha256=hashlib.sha256((tmp_path / f"{role}.service").read_bytes()).hexdigest(),
                       process_argv=tuple(item.decode() for item in (current / "cmdline").read_bytes().split(b"\0") if item),
                       process_executable=(current / "exe").resolve(strict=True))

    monkeypatch.setattr(fresh, "observe_service", observe)
    def private_observe(_spec):
        result = host.observe()
        result["backend"]["old_backend_python_identity"] = old.identity
        return result

    monkeypatch.setattr(fresh, "_observe_live", private_observe)
    save(bundle / "live-before.json", private_observe(spec))
    gate = paired.SingleVpsDriver._service_access_gate

    def access_run(*args):
        assert args[:2] == ("systemctl", "show")
        assert args[3] in {"--property=User", "--property=DynamicUser"}
        return "root" if args[3] == "--property=User" else "no"

    monkeypatch.setattr(paired, "_run", access_run)
    def access_gate(values):
        with monkeypatch.context() as process_identity:
            process_identity.setattr(paired.os, "geteuid", lambda: 0)
            gate(values, proc_root=proc)

    monkeypatch.setattr(paired.SingleVpsDriver, "_service_access_gate", staticmethod(access_gate))
    run = maintenance._run

    def stop(*args):
        result = run(*args)
        if args[:2] == ("systemctl", "stop"):
            role = args[2].removeprefix("bilun-").removesuffix(".service")
            shutil.rmtree(proc / str(services[role].listener_pid))
        return result

    monkeypatch.setattr(maintenance, "_run", stop)
    digest = fresh._runtime_digest

    def stopped_digest(root, *, backend):
        if root in {spec["live_backend_runtime"], spec["live_frontend_runtime"]}:
            assert host.barrier() and not any(host.running.values())
            assert not any(proc.iterdir()), "original process inventory must be gone before runtime capture"
            assert maintenance._run("systemctl", "show", "bilun-frontend.service", "--property=MainPID", "--value") == "0"
            assert maintenance._run("systemctl", "show", "bilun-frontend.service", "--property=ActiveState", "--value") == "inactive"
            assert maintenance._run("ss", "-H", "-ltn", "sport = :3000") == ""
            host.calls.append("capture_runtime")
        return digest(root, backend=backend)

    monkeypatch.setattr(fresh, "_runtime_digest", stopped_digest)
    return fresh, spec, host, proc, services, environments


def test_early_capture_seals_private_inventory_before_proc_disappears(tmp_path, monkeypatch):
    fresh, spec, host, proc, services, environments = _early_private_capture(tmp_path, monkeypatch)
    before = fresh._observe_live(spec)
    captured = fresh._snapshot_old(spec, before)
    assert captured == before and not any(proc.iterdir())
    assert not any(host.running.values()) and host.barrier()
    assert host.calls.index("route_barrier") < host.calls.index("stop_frontend") < host.calls.index("stop_backend") < host.calls.index("capture_runtime")
    assert "start_backend" not in host.calls and "start_frontend" not in host.calls
    journal = json.loads(host.journal.read_text())
    assert journal["state"] == "held" and journal["snapshot_complete"] is True
    assert "old_backend_python_identity" not in journal["expected_pair"]["backend"]
    assert (host.lock.parent / "paired-release-owner.json").is_file()
    for role in ("backend", "frontend"):
        private = spec["bundle_root"] / "old-snapshot"
        assert (private / f"{role}-effective-env.nul").read_bytes() == environments[role]
        service = json.loads((private / f"{role}-service.json").read_text())
        assert service["process_argv"] == list(services[role].process_argv)
        assert service["process_executable"] == str(services[role].process_executable)
        assert fresh._runtime_digest(private / role, backend=role == "backend") == captured[f"{role}_runtime_sha256"]
    assert fresh._observe_preparation(spec) == captured


@pytest.mark.parametrize("changed", ["environment", "unit"])
def test_early_capture_rejects_private_process_or_configuration_drift_before_stop(tmp_path, monkeypatch, changed):
    fresh, spec, host, proc, _, _ = _early_private_capture(tmp_path, monkeypatch)
    if changed == "environment":
        (proc / "101/environ").write_bytes(b"AUTH_SECRET=unexpected-authored-change\0")
    else:
        (tmp_path / "backend.service").write_bytes(b"changed authored unit")
    with pytest.raises(ValueError, match="environment moved|service moved"):
        fresh._snapshot_old(spec, fresh._observe_live(spec))
    assert host.calls == [] and all(host.running.values())
    assert not host.journal.exists() and not (spec["bundle_root"] / "old-snapshot/backend").exists()


@pytest.mark.parametrize("changed", ["environment", "argv", "executable", "runtime"])
def test_held_preparation_rejects_frozen_private_inventory_tampering(tmp_path, monkeypatch, changed):
    fresh, spec, host, _, _, _ = _early_private_capture(tmp_path, monkeypatch)
    fresh._snapshot_old(spec, fresh._observe_live(spec))
    private = spec["bundle_root"] / "old-snapshot"
    if changed == "environment":
        (private / "frontend-effective-env.nul").write_bytes(b"AUTH_SECRET=changed-authored-capture\0")
    elif changed == "runtime":
        (private / "frontend/source").write_bytes(b"changed authored runtime")
    else:
        service = json.loads((private / "frontend-service.json").read_text())
        if changed == "argv":
            service["process_argv"] = ["changed-authored-executable"]
        else:
            service["process_executable"] = str(tmp_path / "frontend.exe")
        save(private / "frontend-service.json", service)
    calls = list(host.calls)
    with pytest.raises(ValueError, match="Frozen old"):
        fresh._observe_preparation(spec)
    assert host.calls == calls and not any(host.running.values()) and host.barrier()
    assert (host.lock.parent / "paired-release-owner.json").is_file()


@pytest.mark.parametrize("changed", ["unit", "environment", "route"])
def test_held_preparation_rejects_operator_configuration_drift_without_writes(tmp_path, monkeypatch, changed):
    from scripts.deploy import snapshot_maintenance as maintenance

    fresh, spec, host, proc, _, _ = _early_private_capture(tmp_path, monkeypatch)
    fresh._snapshot_old(spec, fresh._observe_live(spec))
    owner = host.lock.parent / "paired-release-owner.json"
    journal_before, owner_before = host.journal.read_bytes(), owner.read_bytes()
    target = {"unit": tmp_path / "frontend.service", "environment": tmp_path / "frontend.env",
              "route": spec["caddy_config"]}[changed]
    target.write_bytes(b"authored operator configuration change")
    calls, loaded_route = list(host.calls), json.loads(json.dumps(host.loaded_route))
    with pytest.raises(maintenance.SnapshotMaintenanceError, match="changed"):
        fresh._observe_preparation(spec)
    assert host.calls == calls and not any(host.running.values()) and not any(proc.iterdir())
    assert host.loaded_route == loaded_route
    assert host.journal.read_bytes() == journal_before and owner.read_bytes() == owner_before
    assert target.read_bytes() == b"authored operator configuration change"


def _early_pipeline(machine, tmp_path, monkeypatch):
    """Keep the existing fabricated build gates with a genuine held snapshot."""
    from scripts.deploy import snapshot_maintenance as maintenance

    manifest, spec, events, original = machine
    old_pair = tmp_path / "controlled-old-pair"
    old_pair.mkdir(mode=0o700)
    fresh, capture_spec, host, _, _, _ = _early_private_capture(old_pair, monkeypatch)
    (capture_spec["bundle_root"] / "live-before.json").unlink()
    capture_spec["bundle_root"].rmdir()
    root = Path(spec["bundle_root"])
    host.journal, host.output = root / "snapshot-maintenance/transaction.json", root / "old-snapshot/cache.duckdb"
    spec.update({key: str(value) for key, value in capture_spec.items() if key in module._PATHS})
    spec.update(bundle_root=str(root), snapshot_mode="early-owned-maintenance", old_build_id="old-build",
                serving_code_sha=OLD, schema_version=module.DEPENDENCY_CHAIN_SCHEMA,
                dependency_roots=[str(path) for path in capture_spec["dependency_roots"]])
    save(manifest, spec)
    run = maintenance._run
    monkeypatch.setattr(maintenance, "_run", lambda *args: OLD if args[0] == "git" else run(*args))

    def observe(_spec):
        events.append("observe")
        return fresh._observe_live(_spec)

    def capture(parsed, before):
        events.append("snapshot")
        return fresh._snapshot_old(parsed, before)

    def held(parsed):
        events.append("held_observe")
        return fresh._observe_preparation(parsed)

    monkeypatch.setattr(module, "_observe_live", observe)
    monkeypatch.setattr(module, "_snapshot_old", capture)
    monkeypatch.setattr(module, "_observe_preparation", held)
    return manifest, spec, events, original, host


def test_long_prepare_build_sign_and_handoff_remain_held_without_proc(machine, tmp_path, monkeypatch):
    from scripts.deploy import snapshot_maintenance as maintenance

    manifest, spec, events, original, host = _early_pipeline(machine, tmp_path, monkeypatch)
    checked = []
    for name in ("_build_frontend", "build_traced_candidate", "_rehearse", "issue_wavea_activation", "_handoff"):
        callback = getattr(module, name)

        @wraps(callback)
        def held_stage(*args, _name=name, _callback=callback, **kwargs):
            assert host.barrier() and not any(host.running.values())
            assert not any((host.root / "proc").iterdir())
            assert maintenance.assert_held_snapshot(host.journal)["state"] == "held"
            checked.append(_name)
            return _callback(*args, **kwargs)

        monkeypatch.setattr(module, name, held_stage)
    result = module.prepare_release_bundle(manifest)
    assert checked == ["_build_frontend", "build_traced_candidate", "_rehearse", "issue_wavea_activation", "_handoff"]
    assert result["snapshot_mode"] == "early-owned-maintenance" and result["production_mutated"] is True
    assert result["production_artifacts_changed"] is False and result["public_activation_ready"] is False
    paired = json.loads(Path(result["paired_manifest_path"]).read_text())
    held = maintenance.assert_held_snapshot(host.journal)
    assert paired["snapshot_journal_path"] == str(host.journal)
    assert paired["snapshot_journal_identity_sha256"] == held["identity_sha256"]
    assert host.barrier() and not any(host.running.values())
    assert "start_backend" not in host.calls and "start_frontend" not in host.calls
    assert events.count("ci") == 2 and events.count("observe") == 1
    assert Path(spec["live_cache_path"]).read_bytes() == (Path(spec["bundle_root"]) / "old-snapshot/cache.duckdb").read_bytes()
    assert Path(machine[1]["signing_key_path"]).read_bytes() == b"x" * 32


@pytest.mark.parametrize("stage", ["_build_frontend", "build_traced_candidate", "_rehearse", "issue_wavea_activation", "_handoff"])
def test_early_prepare_failure_retains_owned_barrier_and_never_publishes(machine, tmp_path, monkeypatch, stage):
    from scripts.deploy import snapshot_maintenance as maintenance

    manifest, spec, events, _, host = _early_pipeline(machine, tmp_path, monkeypatch)

    @wraps(getattr(module, stage))
    def fail(*args, **kwargs):
        assert maintenance.assert_held_snapshot(host.journal)["state"] == "held"
        raise ValueError("authored early preparation failure")

    monkeypatch.setattr(module, stage, fail)
    with pytest.raises(ValueError, match="authored early"):
        module.prepare_release_bundle(manifest)
    root = Path(spec["bundle_root"])
    assert not (root / "prepared.json").exists() and not (root / "paired-manifest.json").exists()
    assert (root / "failed.json").is_file()
    assert maintenance.assert_held_snapshot(host.journal)["state"] == "held"
    assert host.barrier() and not any(host.running.values())
    assert "start_backend" not in host.calls and "start_frontend" not in host.calls
    if stage not in {"issue_wavea_activation", "_handoff"}:
        assert "issue" not in events


@pytest.mark.parametrize("stage,changed", [
    ("build_traced_candidate", "owner_missing"), ("_build_frontend", "owner_foreign"),
    ("_rehearse", "loaded_barrier"), ("_rehearse", "installed_barrier"),
])
def test_lost_held_proof_inside_long_build_prevents_signing_and_handoff(machine, tmp_path, monkeypatch, stage, changed):
    from scripts.deploy import snapshot_maintenance as maintenance
    from scripts.deploy.prepare_wavea_routes import OLD_CADDYFILE

    manifest, spec, events, _, host = _early_pipeline(machine, tmp_path, monkeypatch)
    build = getattr(module, stage)
    calls_at_loss = []
    owner = host.lock.parent / "paired-release-owner.json"

    def lose_proof(*args, **kwargs):
        result = build(*args, **kwargs)
        assert maintenance.assert_held_snapshot(host.journal)["state"] == "held"
        if changed == "owner_missing":
            owner.unlink()
        elif changed == "owner_foreign":
            value = json.loads(owner.read_text())
            value["manifest_sha256"] = "f" * 64
            save(owner, value)
        elif changed == "loaded_barrier":
            host.loaded_route = {"apps": {"fixture_caddyfile": OLD_CADDYFILE.decode()}}
        else:
            host.spec["caddy_config"].write_bytes(OLD_CADDYFILE)
        calls_at_loss.extend(host.calls)
        return result

    monkeypatch.setattr(module, stage, lose_proof)
    with pytest.raises(maintenance.SnapshotMaintenanceError):
        module.prepare_release_bundle(manifest)
    root = Path(spec["bundle_root"])
    assert "issue" not in events and not (root / "candidate-receipt.json").exists()
    assert not (root / "prepared.json").exists() and not (root / "paired-manifest.json").exists()
    assert host.calls == calls_at_loss and not any(host.running.values())
    if changed == "owner_missing":
        assert not owner.exists()
    elif changed == "owner_foreign":
        assert json.loads(owner.read_text())["manifest_sha256"] == "f" * 64


@pytest.mark.parametrize("missing", ["both", "identity"])
def test_early_prepare_rejects_missing_issuer_protocol_before_live_effects(machine, monkeypatch, missing):
    manifest, spec, events, original = machine
    spec["snapshot_mode"] = "early-owned-maintenance"
    save(manifest, spec)

    def generic(**kwargs):
        pytest.fail("Issuer without the held protocol must not run")

    def missing_identity(*, old_snapshot_journal_path=None, **kwargs):
        pytest.fail("Issuer without the held identity parameter must not run")

    monkeypatch.setattr(module, "issue_wavea_activation", generic if missing == "both" else missing_identity)
    with pytest.raises(ValueError, match="Receipt issuer lacks the stopped old-pair journal interface"):
        module.prepare_release_bundle(manifest)
    assert events == [] and not Path(spec["bundle_root"]).exists()
    assert Path(spec["live_cache_path"]).read_bytes() == original
    assert Path(spec["frontend_current"]).resolve() == Path(spec["live_frontend_runtime"])


def test_online_prepare_retains_generic_legacy_issuer_interface(machine, monkeypatch):
    manifest, _, events, _ = machine
    issue = module.issue_wavea_activation

    def generic(**kwargs):
        assert "old_snapshot_journal_path" not in kwargs
        assert "old_snapshot_journal_identity_sha256" not in kwargs
        return issue(**kwargs)

    monkeypatch.setattr(module, "issue_wavea_activation", generic)
    assert module.prepare_release_bundle(manifest)["snapshot_mode"] == "online-read-lock"
    assert events.count("issue") == 1


def test_rehearsal_uses_private_namespace_and_same_port_producer(machine, monkeypatch):
    _, raw, _, _ = machine
    spec = {key: Path(value) if key in module._PATHS else value for key, value in raw.items()}
    spec["bundle_root"].mkdir(mode=0o700)
    old = old_python_context(spec["bundle_root"].parent, environment_sha256="b" * 64)
    record, record_sha = old_python_record(spec["bundle_root"], old, runtime_sha256="a" * 64)
    spec["dependency_roots"] = old.dependencies
    spec["_old_backend_python_identity_record_sha256"] = record_sha
    calls = []
    monkeypatch.setattr(module, "_run", lambda argv, **kwargs: calls.append((argv, kwargs)))
    # Call the real function, independently of the orchestration fixture's I/O double.
    from importlib.util import module_from_spec, spec_from_file_location
    definition = spec_from_file_location("preparation_command_test", module.__file__)
    fresh = module_from_spec(definition)
    definition.loader.exec_module(fresh)
    monkeypatch.setattr(fresh, "_run", lambda argv, **kwargs: calls.append((argv, kwargs)))
    fresh._rehearse(spec, spec["bundle_root"] / "backend", spec["bundle_root"] / "frontend",
                    "a" * 64, "b" * 64, "c" * 64)
    argv, kwargs = calls[0]
    assert argv[:3] == ["unshare", "--net", "--"]
    assert "scripts.deploy.rehearse_wavea_same_port" in argv
    assert argv[argv.index("--old-backend-runtime-sha256") + 1] == "a" * 64
    assert argv[argv.index("--old-environment-sha256") + 1] == "b" * 64
    assert argv[argv.index("--candidate-environment-sha256") + 1] == "c" * 64
    assert argv[argv.index("--old-backend-python-identity-record") + 1] == str(record)
    assert argv[argv.index("--old-backend-python-identity-record-sha256") + 1] == record_sha
    assert argv[argv.index("--backend-python") + 1] == str(spec["backend_python"])
    assert "--clinical-transition" not in argv
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--dependency-root"] == [
        str(path) for path in spec["dependency_roots"]
    ]
    assert "systemctl" not in argv and "--profile" not in argv
    assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"


def test_rehearsal_receives_initial_candidate_and_independently_observed_old_environment_hashes(machine, monkeypatch):
    from scripts.deploy.rehearse_wavea_pair import env_digest

    manifest, _, _, _ = machine
    candidate_base = {"BILUN_PUBLIC_BILLING_ENABLED": "true"}
    captured = env_digest(candidate_base)
    monkeypatch.setattr(module, "candidate_environments", lambda *_: (candidate_base, {}))
    checkout = module._create_checkout
    rehearsal = module._rehearse
    calls = []

    def changed_after_initial_capture(spec):
        candidate_base["SUT_DATA_MODE"] = "real_claims"
        return checkout(spec)

    def record(*args):
        calls.append(args[-2:])
        return rehearsal(*args)

    monkeypatch.setattr(module, "_create_checkout", changed_after_initial_capture)
    monkeypatch.setattr(module, "_rehearse", record)
    module.prepare_release_bundle(manifest)
    assert calls == [("e" * 64, captured)]
    assert captured != env_digest(candidate_base)


def test_late_candidate_environment_change_cannot_replace_original_rehearsal_expectation(machine, monkeypatch):
    from scripts.deploy.rehearse_wavea_pair import env_digest

    manifest, spec, _, _ = machine
    candidate_base = {"BILUN_PUBLIC_BILLING_ENABLED": "true"}
    expected = env_digest(candidate_base)
    monkeypatch.setattr(module, "candidate_environments", lambda *_: (candidate_base, {}))
    checkout = module._create_checkout

    def change(spec):
        result = checkout(spec)
        candidate_base["SUT_DATA_MODE"] = "real_claims"
        return result

    def reject_changed_capture(*args):
        assert args[-1] == expected
        if env_digest(candidate_base) != args[-1]:
            raise ValueError("Candidate base environment differs from independent initial capture")

    monkeypatch.setattr(module, "_create_checkout", change)
    monkeypatch.setattr(module, "_rehearse", reject_changed_capture)
    with pytest.raises(ValueError, match="independent initial capture"):
        module.prepare_release_bundle(manifest)
    assert not (Path(spec["bundle_root"]) / "prepared.json").exists()


@pytest.fixture
def dependency_machine(machine):
    manifest, spec, _, _ = machine
    spec["schema_version"] = module.DEPENDENCY_FILE_SCHEMA
    dependency = Path(spec["dependency_roots"][0])
    library = manifest.parent / "stdlib"
    library.mkdir()
    target = library / "sitecustomize.py"
    target.write_bytes(b"# system Python customization\n")
    target.chmod(0o644)
    alternate = library / "alternate.py"
    alternate.write_bytes(target.read_bytes())
    alternate.chmod(0o644)
    link = dependency / "lib/python3.12/sitecustomize.py"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)
    spec["dependency_roots"].extend((str(target), str(alternate)))
    save(manifest, spec)
    return machine, dependency, target, alternate, link


def _prepared_pins(result):
    paired = json.loads(Path(result["paired_manifest_path"]).read_text())
    path = Path(paired["preparation_pins_path"])
    return path, paired["preparation_pins_sha256"], json.loads(path.read_text())


@pytest.mark.parametrize("relative_link", [False, True])
@pytest.mark.parametrize("mode", [0o644, 0o4644, 0o2644, 0o1644])
def test_v2_preparation_pins_declared_file_and_replays_exact_bundle(dependency_machine, relative_link, mode):
    machine, dependency, target, _, link = dependency_machine
    manifest, spec, events, original = machine
    target.chmod(mode)
    if relative_link:
        link.unlink()
        link.symlink_to(os.path.relpath(target, link.parent))
    result = module.prepare_release_bundle(manifest)
    path, digest, report = _prepared_pins(result)
    target_pin = {"file": hashlib.sha256(target.read_bytes()).hexdigest(), "mode": mode}
    assert report["schema_version"] == "bilun-preparation-pins-v2"
    assert report["dependency_roots"] == spec["dependency_roots"]
    assert report["immutable_inputs"][str(target)] == target_pin
    assert report["immutable_inputs"][str(dependency)][link.relative_to(dependency).as_posix()] == {
        "link": os.readlink(link), "resolved_target": str(target), "target": target_pin,
    }
    assert result["schema_version"] == module.DEPENDENCY_FILE_SCHEMA
    module.verify_preparation_pins(path, digest)
    before = list(events)
    assert module.prepare_release_bundle(manifest) == result
    assert events == before
    assert Path(spec["live_cache_path"]).read_bytes() == original
    assert json.loads(Path(result["paired_manifest_path"]).read_text())["schema_version"] == "bilun-single-vps-pair-v1"


def test_v1_still_emits_exact_legacy_pin_contract(machine):
    manifest, spec, _, _ = machine
    path, digest, report = _prepared_pins(module.prepare_release_bundle(manifest))
    assert set(report) == {"schema_version", "immutable_inputs", "external_state"}
    assert report["schema_version"] == "bilun-preparation-pins-v1"
    module.verify_preparation_pins(path, digest)
    assert module.load_preparation_manifest(manifest, allow_existing_bundle=True)["schema_version"] == module.SCHEMA


def test_legacy_literal_pin_report_accepts_internal_and_executable_links(tmp_path):
    dependency = tmp_path / "dependency"
    dependency.mkdir()
    target = dependency / "module.py"
    target.write_bytes(b"legacy bytes")
    target.chmod(0o640)
    (dependency / "internal.py").symlink_to("module.py")
    executable = tmp_path / "python"
    executable.symlink_to(target)
    digest = hashlib.sha256(b"legacy bytes").hexdigest()
    report = {
        "schema_version": "bilun-preparation-pins-v1",
        "immutable_inputs": {
            str(dependency): {"internal.py": {"link": "module.py"},
                              "module.py": {"sha256": digest, "mode": 0o640}},
            str(executable): {"executable_target": str(target),
                              "bytes": {"file": digest, "mode": 0o640}},
        },
        "external_state": {},
    }
    path = tmp_path / "legacy-pins.json"
    save(path, report)
    module.verify_preparation_pins(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_v1_refuses_even_independently_declared_external_file(dependency_machine):
    machine, _, _, _, _ = dependency_machine
    manifest, spec, events, _ = machine
    spec["schema_version"] = module.SCHEMA
    save(manifest, spec)
    with pytest.raises(ValueError, match="escapes"):
        module.prepare_release_bundle(manifest)
    assert events == ["ci"]
    assert not Path(spec["bundle_root"]).exists()


@pytest.mark.parametrize("mutation", ["bytes", "mode", "setuid", "setgid", "sticky", "equal_bytes_retarget", "link_text",
                                     "deleted", "target_symlink", "new_file"])
@pytest.mark.parametrize("boundary", ["handoff", "repeat_prepare"])
def test_v2_replay_rejects_dependency_drift(dependency_machine, mutation, boundary):
    machine, dependency, target, alternate, link = dependency_machine
    manifest, _, events, _ = machine
    path, digest, _ = _prepared_pins(module.prepare_release_bundle(manifest))
    before = list(events)
    if mutation == "bytes":
        target.write_bytes(b"# changed OS package\n")
    elif mutation == "mode":
        target.chmod(0o600)
    elif mutation in {"setuid", "setgid", "sticky"}:
        target.chmod({"setuid": 0o4644, "setgid": 0o2644, "sticky": 0o1644}[mutation])
    elif mutation in {"equal_bytes_retarget", "link_text"}:
        link.unlink()
        link.symlink_to(alternate if mutation == "equal_bytes_retarget" else os.path.relpath(target, link.parent))
    elif mutation == "deleted":
        target.unlink()
    elif mutation == "target_symlink":
        target.unlink()
        target.symlink_to(alternate)
    else:
        (dependency / "injected.py").write_bytes(b"unexpected module")
    with pytest.raises((ValueError, OSError)):
        if boundary == "handoff":
            module.verify_preparation_pins(path, digest)
        else:
            module.prepare_release_bundle(manifest)
    assert events == before


@pytest.mark.parametrize("stage", ["build_wavea_sidecar", "issue_wavea_activation"])
@pytest.mark.parametrize("mutation", ["bytes", "mode"])
def test_v2_rechecks_external_file_before_and_after_signing(dependency_machine, monkeypatch, stage, mutation):
    machine, _, target, _, _ = dependency_machine
    manifest, spec, events, original = machine
    operation = getattr(module, stage)

    def change(**kwargs):
        result = operation(**kwargs)
        target.write_bytes(b"changed during preparation") if mutation == "bytes" else target.chmod(0o600)
        return result

    monkeypatch.setattr(module, stage, change)
    with pytest.raises(ValueError, match="changed"):
        module.prepare_release_bundle(manifest)
    assert not (Path(spec["bundle_root"]) / "prepared.json").exists()
    assert not (Path(spec["bundle_root"]) / "paired-manifest.json").exists()
    assert Path(spec["live_cache_path"]).read_bytes() == original
    if stage == "build_wavea_sidecar":
        assert "issue" not in events


@pytest.mark.parametrize("declaration", ["undeclared", "directory_only", "other_immutable_input"])
def test_v2_requires_separate_file_role_not_directory_or_other_input(dependency_machine, declaration):
    machine, _, target, _, _ = dependency_machine
    manifest, spec, events, _ = machine
    spec["dependency_roots"].remove(str(target))
    if declaration == "directory_only":
        spec["dependency_roots"].append(str(target.parent))
    elif declaration == "other_immutable_input":
        # Already hashed as a candidate environment is not a dependency-file declaration.
        spec["candidate_backend_environment"] = str(target)
    save(manifest, spec)
    with pytest.raises(ValueError, match="escapes"):
        module.prepare_release_bundle(manifest)
    assert "snapshot" not in events and not Path(spec["bundle_root"]).exists()


@pytest.mark.parametrize("link_kind", ["directory", "file_chain", "directory_chain",
                                      "hidden_parent_chain", "dangling", "cycle"])
def test_v2_rejects_external_directories_chains_and_invalid_targets(dependency_machine, link_kind):
    machine, _, target, _, link = dependency_machine
    manifest, spec, events, _ = machine
    link.unlink()
    if link_kind == "directory":
        link.symlink_to(target.parent)
        spec["dependency_roots"].append(str(target.parent))
    elif link_kind == "file_chain":
        alias = target.with_name("alias.py")
        alias.symlink_to(target)
        link.symlink_to(alias)
    elif link_kind in {"directory_chain", "hidden_parent_chain"}:
        alias = target.parent.parent / "stdlib-alias"
        if link_kind == "directory_chain":
            alias.symlink_to(target.parent, target_is_directory=True)
            link.symlink_to(alias / target.name)
        else:
            child = target.parent / "nested"
            child.mkdir()
            alias.symlink_to(child, target_is_directory=True)
            link.symlink_to(alias / ".." / target.name)
    elif link_kind == "dangling":
        link.symlink_to(target.with_name("absent.py"))
    else:
        alias = target.with_name("cycle.py")
        alias.symlink_to(link)
        link.symlink_to(alias)
    save(manifest, spec)
    with pytest.raises((ValueError, OSError, RuntimeError)):
        module.prepare_release_bundle(manifest)
    assert "snapshot" not in events and not Path(spec["bundle_root"]).exists()


@pytest.mark.parametrize("alias_kind", ["file_symlink", "parent_symlink", "parent_traversal", "duplicate"])
def test_v2_manifest_rejects_noncanonical_or_duplicate_file_declarations(dependency_machine, alias_kind):
    machine, _, target, _, _ = dependency_machine
    manifest, spec, events, _ = machine
    if alias_kind == "file_symlink":
        alias = target.with_name("alias.py")
        alias.symlink_to(target)
    elif alias_kind == "parent_symlink":
        parent = target.parent.parent / "alias"
        parent.symlink_to(target.parent, target_is_directory=True)
        alias = parent / target.name
    elif alias_kind == "parent_traversal":
        alias = target.parent / ".." / target.parent.name / target.name
    else:
        alias = target
    spec["dependency_roots"].append(str(alias))
    save(manifest, spec)
    with pytest.raises(ValueError, match="canonical|repeats"):
        module.prepare_release_bundle(manifest)
    assert events == []


@pytest.mark.parametrize("source_key", ["baseline_claims_dir", "baseline_clean_dir"])
@pytest.mark.parametrize("overlap", ["equal", "ancestor", "descendant", "file", "filesystem_root"])
def test_v2_dependency_roles_cannot_overlap_source_inventory(dependency_machine, source_key, overlap):
    machine, _, _, _, _ = dependency_machine
    manifest, spec, events, _ = machine
    source = Path(spec[source_key])
    if overlap == "descendant":
        overlap_path = source / "nested"
        overlap_path.mkdir()
    else:
        overlap_path = {"equal": source, "ancestor": source.parent,
                        "file": source / "input.txt", "filesystem_root": Path("/")}[overlap]
    spec["dependency_roots"].append(str(overlap_path))
    save(manifest, spec)
    with pytest.raises(ValueError, match="source data"):
        module.prepare_release_bundle(manifest)
    assert events == []


@pytest.mark.parametrize("source_key", ["baseline_claims_dir", "baseline_clean_dir"])
def test_v2_declared_dependency_file_never_authorizes_source_links(dependency_machine, source_key):
    machine, _, target, _, _ = dependency_machine
    manifest, spec, events, _ = machine
    (Path(spec[source_key]) / "source-link.py").symlink_to(target)
    with pytest.raises(ValueError, match="escapes"):
        module.prepare_release_bundle(manifest)
    assert "snapshot" not in events and not Path(spec["bundle_root"]).exists()


@pytest.mark.parametrize("forgery", ["missing_roles", "null_roles", "string_roles", "empty_roles",
                                    "duplicate_role", "undeclared_role", "relative_role", "alias_role",
                                    "nonstring_role", "too_many_roles", "filesystem_root",
                                    "missing_file_role", "missing_directory_role", "extra_field",
                                    "missing_target_pin", "changed_target_pin", "changed_link_target",
                                    "downgrade", "malformed_pin", "malformed_version"])
def test_v2_hash_bound_replay_rejects_malformed_or_forged_contract(dependency_machine, forgery):
    machine, dependency, target, alternate, link = dependency_machine
    manifest, _, _, _ = machine
    path, _, report = _prepared_pins(module.prepare_release_bundle(manifest))
    roles = report["dependency_roots"]
    if forgery == "missing_roles":
        del report["dependency_roots"]
    elif forgery in {"null_roles", "string_roles", "empty_roles"}:
        report["dependency_roots"] = {"null_roles": None, "string_roles": str(target), "empty_roles": []}[forgery]
    elif forgery == "duplicate_role":
        roles.append(str(target))
    elif forgery == "undeclared_role":
        roles.append(str(manifest))
    elif forgery == "relative_role":
        roles.append("sitecustomize.py")
    elif forgery == "alias_role":
        alias = target.with_name("alias.py")
        alias.symlink_to(target)
        roles.append(str(alias))
    elif forgery == "nonstring_role":
        roles.append({"path": str(target)})
    elif forgery == "too_many_roles":
        report["dependency_roots"] = [str(target)] * 65
    elif forgery == "filesystem_root":
        roles.append("/")
    elif forgery == "missing_file_role":
        roles.remove(str(target))
    elif forgery == "missing_directory_role":
        roles.remove(str(dependency))
    elif forgery == "extra_field":
        report["external_dependency_files"] = [str(target)]
    elif forgery == "missing_target_pin":
        del report["immutable_inputs"][str(target)]
    elif forgery == "changed_target_pin":
        report["immutable_inputs"][str(target)]["mode"] = 0o600
    elif forgery == "changed_link_target":
        report["immutable_inputs"][str(dependency)][link.relative_to(dependency).as_posix()]["resolved_target"] = str(alternate)
    elif forgery == "downgrade":
        report["schema_version"] = "bilun-preparation-pins-v1"
        del report["dependency_roots"]
    elif forgery == "malformed_version":
        report["schema_version"] = []
    else:
        report["immutable_inputs"][str(target)] = None
    save(path, report)
    # Recompute only to reach structural validation; production handoffs retain
    # the original hash, independently covered by the next regression.
    with pytest.raises(ValueError):
        module.verify_preparation_pins(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_v2_role_permissions_are_bound_to_original_handoff_digest(dependency_machine):
    machine, _, target, _, _ = dependency_machine
    manifest, _, _, _ = machine
    path, digest, report = _prepared_pins(module.prepare_release_bundle(manifest))
    report["dependency_roots"].remove(str(target))
    save(path, report)
    with pytest.raises(ValueError, match="contract is malformed or changed"):
        module.verify_preparation_pins(path, digest)


def test_v2_declared_external_target_must_be_regular_file(dependency_machine):
    machine, _, target, _, _ = dependency_machine
    manifest, spec, events, _ = machine
    target.unlink()
    os.mkfifo(target)
    with pytest.raises(ValueError, match="ordinary files or directories"):
        module.prepare_release_bundle(manifest)
    assert "snapshot" not in events and not Path(spec["bundle_root"]).exists()
