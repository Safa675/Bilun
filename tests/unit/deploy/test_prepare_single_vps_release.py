"""Fabricated machine: exercise orchestration, ordering, and real DuckDB snapshots."""

from __future__ import annotations

import json
import fcntl
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from scripts.deploy import prepare_single_vps_release as module

TARGET = "a" * 40
OLD = "b" * 40


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
                "frontend": str(Path(spec["frontend_current"]).resolve()), "services": "unchanged"}

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

    def issue(**kwargs):
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
                                       ("unknown_field", "value"), ("dependency_roots", [])])
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


def test_rehearsal_uses_private_namespace_and_same_port_producer(machine, monkeypatch):
    _, raw, _, _ = machine
    spec = {key: Path(value) if key in module._PATHS else value for key, value in raw.items()}
    spec["bundle_root"].mkdir(mode=0o700)
    calls = []
    monkeypatch.setattr(module, "_run", lambda argv, **kwargs: calls.append((argv, kwargs)))
    # Call the real function, independently of the orchestration fixture's I/O double.
    from importlib.util import module_from_spec, spec_from_file_location
    definition = spec_from_file_location("preparation_command_test", module.__file__)
    fresh = module_from_spec(definition)
    definition.loader.exec_module(fresh)
    monkeypatch.setattr(fresh, "_run", lambda argv, **kwargs: calls.append((argv, kwargs)))
    fresh._rehearse(spec, spec["bundle_root"] / "backend", spec["bundle_root"] / "frontend")
    argv, kwargs = calls[0]
    assert argv[:3] == ["unshare", "--net", "--"]
    assert "scripts.deploy.rehearse_wavea_same_port" in argv
    assert "systemctl" not in argv and "--profile" not in argv
    assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
