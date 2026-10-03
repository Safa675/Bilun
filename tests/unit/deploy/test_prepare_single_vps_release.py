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

from tests.unit.deploy.probe_auth_fixtures import write_old_auth

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
    fresh._rehearse(spec, spec["bundle_root"] / "backend", spec["bundle_root"] / "frontend", "a" * 64)
    argv, kwargs = calls[0]
    assert argv[:3] == ["unshare", "--net", "--"]
    assert "scripts.deploy.rehearse_wavea_same_port" in argv
    assert argv[argv.index("--old-backend-runtime-sha256") + 1] == "a" * 64
    assert "systemctl" not in argv and "--profile" not in argv
    assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"


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
