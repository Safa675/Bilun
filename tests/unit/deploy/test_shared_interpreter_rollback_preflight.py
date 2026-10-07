"""Rollback readiness when the old backend runs from a shared interpreter.

Releases made by the single-VPS tool run from a git worktree through a shared
launcher, so the copied old runtime has no ``.venv``. These tests drive the real
preflight and the real PR 165 identity verifier against that layout.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import duckdb
import pytest

from scripts.deploy import capture_release_preflight as preflight
from scripts.deploy import issue_wavea_activation as issuer
from scripts.deploy import observe_old_pair as observe
from scripts.deploy import prepare_single_vps_release as prepare
from scripts.deploy.prepare_wavea_routes import OLD_CADDYFILE
from scripts.deploy.release_sidecar import _load_private_json
from tests.unit.deploy.test_capture_release_preflight import _fixture, _probes
from tests.unit.deploy.test_issue_wavea_activation import _allow_release_ci, _issuer_fixture
from tests.unit.deploy.test_prepare_single_vps_release import (
    old_python_context,
    old_python_record,
    save,
)

BLOCKER = "backend_rollback_artifact_unverified: backend snapshot lacks runnable Python environment"


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, local_venv: bool = False,
            environment_sha256: str = "e" * 64):
    """A bundle-shaped fixture: serving runtime without .venv and its snapshot."""
    bundle = tmp_path / "bundle"
    bundle.mkdir(mode=0o700)
    work = tmp_path / "work"
    work.mkdir()
    state = _fixture(work, monkeypatch)
    snapshot = bundle / "old-snapshot"
    shutil.move(str(work / "snapshots"), snapshot)
    state.update(
        frontend_snapshot=snapshot / "frontend", backend_snapshot=snapshot / "backend",
        cache_snapshot=snapshot / "cache.duckdb", config_snapshot_dir=snapshot / "config",
    )
    if not local_venv:
        shutil.rmtree(work / "live-backend" / ".venv")
        shutil.rmtree(snapshot / "backend" / ".venv")
    old = old_python_context(tmp_path, environment_sha256=environment_sha256)
    state["backend"] = replace(
        state["backend"], process_argv=old.service.process_argv,
        process_executable=old.terminal, environment_sha256=old.service.environment_sha256,
    )
    runtime_sha256 = preflight._runtime_digest(state["backend"].process_working_directory, backend=True)
    old_python_record(bundle, old, runtime_sha256=runtime_sha256)
    save(bundle / "preparation-pins.json", {
        "schema_version": "bilun-preparation-pins-v3", "immutable_inputs": old.pins,
        "dependency_roots": [str(path) for path in old.dependencies], "external_state": {},
    })
    front_probe, back_probe = _probes(state, tmp_path)
    report = json.loads(back_probe.read_text())
    report["effective_environment_sha256"] = old.service.environment_sha256
    back_probe.write_text(json.dumps(report))
    state.update(old=old, bundle=bundle, front_probe=front_probe, back_probe=back_probe)
    return state


def _prover(state):
    return lambda backend, runtime_sha256: issuer._old_shared_interpreter_evidence(
        old_snapshot=state["bundle"] / "old-snapshot", dependency_roots=state["old"].dependencies,
        runtime_sha256=runtime_sha256, environment_sha256=backend.environment_sha256,
    )


def _assess(state, **options):
    return preflight.assess_release_preflight(
        state["frontend"], state["backend"], state["health"],
        frontend_current=state["frontend_current"],
        frontend_snapshot=state["frontend_snapshot"], backend_snapshot=state["backend_snapshot"],
        cache_snapshot=state["cache_snapshot"], frontend_probe=state["front_probe"],
        backend_probe=state["back_probe"], config_snapshot_dir=state["config_snapshot_dir"],
        caddy_config=state["caddy_config"], **options,
    )


def test_venvless_old_runtime_without_interpreter_proof_keeps_the_measured_blocker(tmp_path, monkeypatch):
    """The 2026-10-06 c44aa78c prepare: one blocker, no backend artifact, no backend probe."""
    state = _bundle(tmp_path, monkeypatch)
    report = _assess(state)
    assert report["rollback"]["blockers"] == [BLOCKER]
    assert set(report["rollback"]["artifacts"]) == {"cache", "frontend", "service_and_proxy_configuration"}


def test_venvless_old_runtime_is_ready_with_the_frozen_shared_interpreter(tmp_path, monkeypatch):
    state = _bundle(tmp_path, monkeypatch)
    report = _assess(state, prove_shared_interpreter=_prover(state))
    assert report["rollback"]["blockers"] == [] and report["rollback"]["ready"] is True
    backend = report["rollback"]["artifacts"]["backend"]
    assert backend["interpreter"]["kind"] == "shared_interpreter"
    assert backend["interpreter"]["identity_sha256"] == _digest(state["old"].identity)
    assert backend["interpreter"]["executable_target"] == str(state["old"].terminal)
    assert str(state["old"].launcher) not in json.dumps(report)
    assert "private_probe" in backend


def test_legacy_snapshot_venv_never_consults_the_shared_interpreter_proof(tmp_path, monkeypatch):
    state = _bundle(tmp_path, monkeypatch, local_venv=True)

    def forbidden(*_):
        raise AssertionError("the legacy layout must not need the shared interpreter proof")

    report = _assess(state, prove_shared_interpreter=forbidden)
    assert report["rollback"]["blockers"] == []
    assert "interpreter" not in report["rollback"]["artifacts"]["backend"]


@pytest.mark.parametrize("changed", ["pyvenv_cfg", "site_packages", "link", "terminal"])
def test_shared_interpreter_closure_mutation_blocks_readiness(tmp_path, monkeypatch, changed):
    state = _bundle(tmp_path, monkeypatch)
    old = state["old"]
    if changed == "pyvenv_cfg":
        (old.context / "pyvenv.cfg").write_text("home = /different/base-python\n")
    elif changed == "site_packages":
        (old.packages / "old_dependency.py").write_text("CONTEXT = 'changed'\n")
    elif changed == "terminal":
        old.terminal.write_bytes(b"changed terminal executable\n")
    else:
        old.launcher.unlink()
        old.launcher.symlink_to(old.terminal)
    report = _assess(state, prove_shared_interpreter=_prover(state))
    assert len(report["rollback"]["blockers"]) == 1
    assert report["rollback"]["blockers"][0].startswith("backend_rollback_artifact_unverified: ")
    assert "backend" not in report["rollback"]["artifacts"] and report["rollback"]["ready"] is False


@pytest.mark.parametrize("fault", ["argv", "executable", "environment"])
def test_shared_interpreter_proof_must_describe_the_serving_old_process(tmp_path, monkeypatch, fault):
    state = _bundle(tmp_path, monkeypatch)
    backend = state["backend"]
    if fault == "argv":
        state["backend"] = replace(backend, process_argv=(*backend.process_argv[:-1], "8099"))
    elif fault == "executable":
        other = tmp_path / "other-python3.13"
        other.write_bytes(state["old"].terminal.read_bytes())
        state["backend"] = replace(backend, process_executable=other)
    else:
        state["backend"] = replace(backend, environment_sha256="f" * 64)
    report = _assess(state, prove_shared_interpreter=_prover(state))
    assert len(report["rollback"]["blockers"]) == 1
    assert report["rollback"]["blockers"][0].startswith("backend_rollback_artifact_unverified: ")
    assert report["rollback"]["ready"] is False


@pytest.mark.parametrize("fault", ["record_missing", "pins_root_missing", "pins_value_changed"])
def test_shared_interpreter_closure_must_be_covered_by_the_hash_bound_pins(tmp_path, monkeypatch, fault):
    state = _bundle(tmp_path, monkeypatch)
    pins_path = state["bundle"] / "preparation-pins.json"
    pins = json.loads(pins_path.read_text())
    if fault == "record_missing":
        (state["bundle"] / "live-after-snapshot.json").unlink()
    elif fault == "pins_root_missing":
        pins["dependency_roots"].pop()
        save(pins_path, pins)
    else:
        first = pins["dependency_roots"][0]
        pins["immutable_inputs"][first] = {"changed": True}
        save(pins_path, pins)
    report = _assess(state, prove_shared_interpreter=_prover(state))
    assert len(report["rollback"]["blockers"]) == 1
    assert report["rollback"]["ready"] is False


def test_record_resealed_onto_another_declared_context_cannot_describe_the_running_process(tmp_path, monkeypatch):
    """Same terminal, same argv digest, both contexts declared: only argv[0] tells them apart."""
    state = _bundle(tmp_path, monkeypatch)
    old = state["old"]
    other = old_python_context(tmp_path, name="candidate-python", terminal=old.terminal)
    old.dependencies = tuple(dict.fromkeys((*old.dependencies, *other.dependencies)))
    old.pins = prepare._pin_inputs(set(old.dependencies), set(), dependency_roots=old.dependencies,
                                   allow_dependency_file_links=True)
    old.identity = prepare._capture_old_backend_python_identity(
        old.service, dependency_roots=old.dependencies, dependency_pins=old.pins,
        allow_dependency_file_links=True)
    runtime_sha256 = preflight._runtime_digest(state["backend"].process_working_directory, backend=True)
    record, _ = old_python_record(state["bundle"], old, runtime_sha256=runtime_sha256)
    save(state["bundle"] / "preparation-pins.json", {
        "schema_version": "bilun-preparation-pins-v3", "immutable_inputs": old.pins,
        "dependency_roots": [str(path) for path in old.dependencies], "external_state": {},
    })
    assert _assess(state, prove_shared_interpreter=_prover(state))["rollback"]["ready"] is True
    value = json.loads(record.read_text())
    value["backend"]["old_backend_python_identity"].update(
        launcher_path=str(other.launcher), context_root=str(other.context))
    save(record, value)
    report = _assess(state, prove_shared_interpreter=_prover(state))
    assert report["rollback"]["ready"] is False
    assert "differs from the serving old backend" in report["rollback"]["blockers"][0]


def test_partial_local_environment_and_malformed_proof_stay_blocked(tmp_path, monkeypatch):
    state = _bundle(tmp_path, monkeypatch)
    (state["backend_snapshot"] / ".venv").mkdir()
    assert _assess(state, prove_shared_interpreter=_prover(state))["rollback"]["blockers"] == [BLOCKER]
    (state["backend_snapshot"] / ".venv").rmdir()
    evidence = _prover(state)
    for broken in ({}, {"identity_sha256": "0" * 64}):
        report = _assess(state, prove_shared_interpreter=lambda *_: broken)
        assert report["rollback"]["ready"] is False and len(report["rollback"]["blockers"]) == 1
    assert _assess(state, prove_shared_interpreter=evidence)["rollback"]["ready"] is True


def test_route_flow_observation_stays_closed_for_a_venvless_snapshot(tmp_path, monkeypatch):
    """The two-port route chain still needs snapshot/.venv; it must fail before activation."""
    state = _bundle(tmp_path, monkeypatch)
    snapshot = state["bundle"] / "old-snapshot"
    monkeypatch.setattr(observe, "_live_health", lambda *_: state["health"])
    monkeypatch.setattr(observe, "observe_service", lambda unit, _port: (
        state["frontend"] if unit == "bilun-frontend.service" else state["backend"]))
    with pytest.raises(ValueError, match="Protected old pair differs from its tested rollback artifacts"):
        observe.observe_old_pair(
            baseline_code_sha="a" * 40, baseline_build_id="old-build", old_snapshot=snapshot,
            old_probe_dir=state["back_probe"].parent, frontend_current=state["frontend_current"],
        )


def test_shared_launcher_keeps_the_venv_but_a_snapshot_symlink_or_terminal_does_not(tmp_path):
    """Why the interpreter must be started through its captured launcher path."""
    venv = tmp_path / "shared-venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    probe = ["-I", "-c", "import sys; print(sys.prefix)"]

    def prefix(executable: Path) -> str:
        return subprocess.run([str(executable), *probe], check=True, capture_output=True,
                              text=True).stdout.strip()

    assert Path(prefix(venv / "bin/python")).resolve() == venv.resolve()
    snapshot_python = tmp_path / "snapshot/backend/.venv/bin/python"
    snapshot_python.parent.mkdir(parents=True)
    snapshot_python.symlink_to(venv / "bin/python")
    assert Path(prefix(snapshot_python)).resolve() != venv.resolve()
    assert Path(prefix(Path((venv / "bin/python").resolve()))).resolve() != venv.resolve()


def _issuer_arguments(tmp_path, monkeypatch, state):
    """The real issuer and preflight over the measured layout; only unrelated gates are stubbed."""
    (tmp_path / "issuer").mkdir()
    real_connect = duckdb.connect
    arguments, code_sha, _, _ = _issuer_fixture(tmp_path / "issuer", monkeypatch)
    stub_connect = duckdb.connect
    monkeypatch.setattr(duckdb, "connect", lambda path, *a, **k: (
        real_connect(path, *a, **k) if Path(str(path)) == state["cache_snapshot"]
        else stub_connect(path, *a, **k)))
    bundle = state["bundle"]
    rehearsal = bundle / "rehearsal"
    rehearsal.mkdir(mode=0o700)
    shutil.copy2(state["front_probe"], rehearsal / "old-frontend-probe.json")
    shutil.copy2(state["back_probe"], rehearsal / "old-backend-probe.json")
    serving_sha = preflight._stable_file_digest(state["cache_snapshot"])
    bridge = issuer.verify_serving_baseline_equivalence
    fixture_loader = issuer._load_private_json
    monkeypatch.setattr(issuer, "verify_serving_baseline_equivalence",
                        lambda *a, **k: {**bridge(*a, **k), "serving_cache_sha256": serving_sha})
    monkeypatch.setattr(issuer, "_load_private_json", lambda path, **k: (
        _load_private_json(path, **k) if path.name == "preparation-pins.json" else fixture_loader(path, **k)))
    monkeypatch.setattr(issuer, "assess_release_preflight", preflight.assess_release_preflight)
    monkeypatch.setattr(issuer, "_live_health", lambda *_: state["health"])
    monkeypatch.setattr(issuer, "observe_service", lambda unit, _port: (
        state["frontend"] if unit == "bilun-frontend.service" else state["backend"]))
    arguments.update(
        old_snapshot=bundle / "old-snapshot", serving_old_build_id="old-build",
        serving_code_sha="a" * 40, rehearsal_path=rehearsal / "real-candidate-namespace-rehearsal.json",
        frontend_current=state["frontend_current"], caddy_config=state["caddy_config"],
        dependency_roots=state["old"].dependencies,
    )
    _allow_release_ci(monkeypatch, code_sha)
    return arguments


def test_issuer_seals_a_receipt_for_the_measured_venvless_old_backend(tmp_path, monkeypatch):
    """Fails on c44aa78c with 'Protected old-pair rollback preflight differs' (issue_wavea_activation.py:472)."""
    state = _bundle(tmp_path, monkeypatch)
    arguments = _issuer_arguments(tmp_path, monkeypatch, state)
    issued = issuer.issue_wavea_activation(**arguments)
    assert issued["status"] == "private_activation_receipt_issued"
    assert issued["old_backend_interpreter"]["kind"] == "shared_interpreter"
    assert issued["old_backend_interpreter"]["identity_sha256"] == _digest(state["old"].identity)
    assert arguments["receipt_path"].is_file()


def test_issuer_refuses_to_seal_when_the_shared_interpreter_closure_changed(tmp_path, monkeypatch):
    state = _bundle(tmp_path, monkeypatch)
    arguments = _issuer_arguments(tmp_path, monkeypatch, state)
    (state["old"].packages / "old_dependency.py").write_text("CONTEXT = 'changed after capture'\n")
    with pytest.raises(ValueError, match="Protected old-pair rollback preflight differs"):
        issuer.issue_wavea_activation(**arguments)
    assert not arguments["receipt_path"].exists() and not arguments["key_path"].exists()


def _held_fixture(tmp_path, monkeypatch, state, journal_value):
    """Owned-maintenance copies: frozen env/service files, config copies and probes."""
    from scripts.deploy.snapshot_maintenance import SnapshotMaintenanceError  # noqa: F401

    bundle, snapshot = state["bundle"], state["bundle"] / "old-snapshot"
    live_backend, live_frontend = (state[role].process_working_directory for role in ("backend", "frontend"))
    runtime = {"backend": preflight._runtime_digest(live_backend, backend=True),
               "frontend": preflight._runtime_digest(live_frontend, backend=False)}
    cache_sha = preflight._stable_file_digest(snapshot / "cache.duckdb")
    configs, saved_configs = set(), {}
    identities = {}
    for role in ("backend", "frontend"):
        service = state[role]
        raw = (b"BILUN_CACHE_DB_PATH=" + str(tmp_path / "work/live-cache.duckdb").encode() + b"\0"
               if role == "backend" else b"PORT=3000\0")
        env_path = snapshot / f"{role}-effective-env.nul"
        env_path.write_bytes(raw)
        env_path.chmod(0o600)
        env_sha = hashlib.sha256(b"\0".join(sorted(item for item in raw.split(b"\0") if item))).hexdigest()
        record = {
            "unit": service.unit, "active_state": "active", "main_pid": service.main_pid,
            "listener_pid": service.listener_pid,
            "declared_working_directory": str(service.declared_working_directory),
            "process_working_directory": str(service.process_working_directory),
            "process_executable": str(service.process_executable),
            "unit_sha256": service.unit_sha256, "unit_fragment": service.unit_fragment,
            "unit_files": [str(path) for path in service.unit_files],
            "selected_environment": {}, "process_started_at_utc": "2026-10-06T00:00:00+00:00",
        }
        identities[role] = {
            **record, "effective_environment_sha256": env_sha, "environment_file_paths": [],
            "process_argv_sha256": hashlib.sha256(
                b"\0".join(arg.encode() for arg in service.process_argv)).hexdigest(),
            "unit_files_modified_since_start": [], "environment_files_modified_since_start": [],
        }
        save(snapshot / f"{role}-service.json", {
            **record, "process_argv": list(service.process_argv), "environment_sha256": env_sha,
            "environment_files": [],
        })
        configs.update(record["unit_files"])
    caddy = state["caddy_config"]
    configs.add(str(caddy))
    for raw_path in configs:
        copied = snapshot / "config" / Path(raw_path).relative_to("/")
        if Path(raw_path) == caddy:
            copied.write_bytes(OLD_CADDYFILE)
        copied.chmod(0o600)
        for parent in copied.parents:
            if parent == snapshot.parent:
                break
            parent.chmod(0o700)
        saved_configs[raw_path] = {"sha256": preflight._stable_file_digest(copied)}
    probes = bundle / "rehearsal"
    probes.mkdir(mode=0o700)
    for role, extra in (("backend", {"cache_sha256": cache_sha, "active_build": "old-build",
                                      "checks": ["health", "representative_api"]}),
                        ("frontend", {"build_id": "serving-build", "checks": ["login_assets"]})):
        save(probes / f"old-{role}-probe.json", {
            "passed": True, "private_url": "http://127.0.0.1:8001/health",
            "runtime_sha256": runtime[role],
            "effective_environment_sha256": identities[role]["effective_environment_sha256"], **extra,
        })
    link = state["frontend_current"]
    journal_value.update(
        expected_pair={
            "backend": identities["backend"], "frontend": identities["frontend"],
            "backend_runtime_sha256": runtime["backend"], "frontend_runtime_sha256": runtime["frontend"],
            "cache_sha256": cache_sha, "frontend_target": str(link.resolve()),
            "health_identity": {"status": "ok", "cache_ready": True, "active_build": "old-build",
                                 "code_sha": "a" * 40},
        },
        recovery_spec={"serving_code_sha": "a" * 40, "frontend_current": str(link),
                       "caddy_config": str(caddy), "live_backend_runtime": str(live_backend),
                       "live_frontend_runtime": str(live_frontend)},
        output_cache=str(snapshot / "cache.duckdb"), build_id="old-build",
        frontend_link=os.readlink(link), live_cache=str(tmp_path / "work/live-cache.duckdb"),
        configuration=saved_configs,
        routes={"old": {"file_sha256": saved_configs[str(caddy)]["sha256"]}},
    )
    monkeypatch.setattr("scripts.deploy.snapshot_maintenance.assert_held_snapshot",
                        lambda *_a, **_k: journal_value)
    return dict(
        journal_path=bundle / "snapshot-maintenance/transaction.json", journal_identity_sha256="a" * 64,
        old_snapshot=snapshot, frontend_current=link, caddy_config=caddy,
        serving_old_build_id="old-build", serving_code_sha="a" * 40,
        old_backend_environment_path=snapshot / "backend-effective-env.nul",
        rehearsal_path=probes / "real-candidate-namespace-rehearsal.json",
        dependency_roots=state["old"].dependencies,
    )


def _held_state(tmp_path, monkeypatch, *, local_venv=False):
    raw = b"BILUN_CACHE_DB_PATH=" + str(tmp_path / "work/live-cache.duckdb").encode() + b"\0"
    env_sha = hashlib.sha256(b"\0".join(sorted(item for item in raw.split(b"\0") if item))).hexdigest()
    return _bundle(tmp_path, monkeypatch, local_venv=local_venv, environment_sha256=env_sha)


def test_held_old_preflight_binds_the_shared_interpreter_of_a_venvless_copy(tmp_path, monkeypatch):
    state = _held_state(tmp_path, monkeypatch)
    arguments = _held_fixture(tmp_path, monkeypatch, state, {})
    result, health = issuer._held_old_preflight(**arguments)
    assert result["rollback"]["blockers"] == [] and health["active_build"] == "old-build"
    backend = result["rollback"]["artifacts"]["backend"]
    assert backend["interpreter"]["identity_sha256"] == _digest(state["old"].identity)
    assert "interpreter" not in result["rollback"]["artifacts"]["frontend"]
    # The issuer compares two evaluations before sealing: the proof must be reproducible.
    assert issuer._held_old_preflight(**arguments)[0] == result


@pytest.mark.parametrize("fault, message", [
    ("record_missing", "Expected independent regular file"),
    ("closure", "launcher, context or dependency pins changed"),
    ("partial_venv", "lacks its runnable Python environment"),
    ("argv", "service or argv copy differs"),
    ("pins_root_missing", "differs from its frozen observation|not covered by the hash-bound"),
])
def test_held_old_preflight_fails_closed_without_an_exact_interpreter_proof(
        tmp_path, monkeypatch, fault, message):
    state = _held_state(tmp_path, monkeypatch)
    arguments = _held_fixture(tmp_path, monkeypatch, state, {})
    snapshot = arguments["old_snapshot"]
    if fault == "record_missing":
        (state["bundle"] / "live-after-snapshot.json").unlink()
    elif fault == "closure":
        state["old"].terminal.write_bytes(b"changed terminal executable\n")
    elif fault == "partial_venv":
        (snapshot / "backend/.venv").mkdir()
    elif fault == "argv":
        service = json.loads((snapshot / "backend-service.json").read_text())
        service["process_argv"][0] = str(state["old"].terminal)
        save(snapshot / "backend-service.json", service)
    else:
        pins = json.loads((state["bundle"] / "preparation-pins.json").read_text())
        pins["dependency_roots"].pop()
        save(state["bundle"] / "preparation-pins.json", pins)
    with pytest.raises(ValueError, match=message):
        issuer._held_old_preflight(**arguments)


def test_held_old_preflight_record_resealed_onto_another_declared_context(tmp_path, monkeypatch):
    """The sealed argv matches the digest in the record; only argv[0] tells the contexts apart."""
    state = _held_state(tmp_path, monkeypatch)
    old = state["old"]
    other = old_python_context(tmp_path, name="candidate-python", terminal=old.terminal)
    old.dependencies = tuple(dict.fromkeys((*old.dependencies, *other.dependencies)))
    old.pins = prepare._pin_inputs(set(old.dependencies), set(), dependency_roots=old.dependencies,
                                   allow_dependency_file_links=True)
    old.identity = prepare._capture_old_backend_python_identity(
        old.service, dependency_roots=old.dependencies, dependency_pins=old.pins,
        allow_dependency_file_links=True)
    runtime_sha256 = preflight._runtime_digest(state["backend"].process_working_directory, backend=True)
    record, _ = old_python_record(state["bundle"], old, runtime_sha256=runtime_sha256)
    save(state["bundle"] / "preparation-pins.json", {
        "schema_version": "bilun-preparation-pins-v3", "immutable_inputs": old.pins,
        "dependency_roots": [str(path) for path in old.dependencies], "external_state": {},
    })
    arguments = _held_fixture(tmp_path, monkeypatch, state, {})
    arguments["dependency_roots"] = old.dependencies
    result, _ = issuer._held_old_preflight(**arguments)
    assert result["rollback"]["blockers"] == []
    value = json.loads(record.read_text())
    value["backend"]["old_backend_python_identity"].update(
        launcher_path=str(other.launcher), context_root=str(other.context))
    save(record, value)
    with pytest.raises(ValueError, match="differs from the serving old backend"):
        issuer._held_old_preflight(**arguments)


def test_held_old_preflight_keeps_the_legacy_venv_layout(tmp_path, monkeypatch):
    state = _held_state(tmp_path, monkeypatch, local_venv=True)
    arguments = _held_fixture(tmp_path, monkeypatch, state, {})
    result, _ = issuer._held_old_preflight(**arguments)
    assert "interpreter" not in result["rollback"]["artifacts"]["backend"]


# --- synthesiser additions: overlap guard, declared roots, process semantics -----------------

def _evidence(tmp_path: Path, **override):
    context = tmp_path / "shared" / ".venv"
    value = {
        "identity_sha256": "1" * 64, "launcher_path": str(context / "bin/python"),
        "process_argv_sha256": "2" * 64, "executable_target": "/usr/bin/python3.13",
        "effective_environment_sha256": "3" * 64, "runtime_sha256": "4" * 64,
        "dependency_roots": [str(context), "/usr/bin/python3.13"],
    }
    value.update(override)
    return value


def _bind(evidence, runtime_roots):
    return preflight.bind_shared_interpreter(
        evidence, process_launcher=evidence["launcher_path"], process_argv_sha256="2" * 64,
        process_executable=Path("/usr/bin/python3.13"), effective_environment_sha256="3" * 64,
        runtime_sha256="4" * 64, runtime_roots=runtime_roots,
    )


def test_bind_accepts_a_closure_disjoint_from_both_runtime_copies(tmp_path):
    projection = _bind(_evidence(tmp_path), (tmp_path / "live", tmp_path / "snapshot"))
    assert projection["kind"] == "shared_interpreter"
    assert "launcher_path" not in projection and "dependency_roots" not in projection


@pytest.mark.parametrize("where", ["context_is_runtime", "context_inside_runtime",
                                    "runtime_inside_context", "root_inside_runtime"])
def test_bind_refuses_an_interpreter_closure_that_overlaps_a_runtime_copy(tmp_path, where):
    context = tmp_path / "shared" / ".venv"
    runtime = {
        "context_is_runtime": context,
        "context_inside_runtime": tmp_path / "shared",
        "runtime_inside_context": context / "lib/app",
        "root_inside_runtime": tmp_path / "usr",
    }[where]
    roots = [str(context), "/usr/bin/python3.13"]
    if where == "root_inside_runtime":
        roots.append(str(runtime / "stdlib"))
    with pytest.raises(ValueError, match="overlaps a runtime copy"):
        _bind(_evidence(tmp_path, dependency_roots=roots), (runtime, tmp_path / "snapshot"))


@pytest.mark.parametrize("roots", [None, [], ["relative/root"], [1]])
def test_bind_refuses_malformed_declared_roots_and_missing_runtime_roots(tmp_path, roots):
    with pytest.raises(ValueError, match="malformed"):
        _bind(_evidence(tmp_path, dependency_roots=roots), (tmp_path / "live",))
    with pytest.raises(ValueError, match="malformed"):
        _bind(_evidence(tmp_path), ())


@pytest.mark.parametrize("fault", [
    "missing_field", "extra_field", "non_text_digest", "non_hex_digest",
    "uppercase_digest", "short_digest", "trailing_newline_digest",
])
def test_bind_refuses_a_proof_that_is_not_exactly_the_issued_shape(tmp_path, fault):
    evidence = _evidence(tmp_path)
    if fault == "missing_field":
        del evidence["identity_sha256"]
    elif fault == "extra_field":
        evidence["raw_secret"] = "value"
    else:
        evidence["identity_sha256"] = {
            "non_text_digest": 5, "non_hex_digest": "z" * 64, "uppercase_digest": "A" * 64,
            "short_digest": "1" * 63, "trailing_newline_digest": "1" * 64 + "\n",
        }[fault]
    with pytest.raises(ValueError, match="malformed"):
        _bind(evidence, (tmp_path / "live", tmp_path / "snapshot"))


@pytest.mark.parametrize("copy", ["live", "snapshot"])
def test_overlapping_closure_blocks_the_preflight(tmp_path, monkeypatch, copy):
    state = _bundle(tmp_path, monkeypatch)
    runtime = (state["backend"].process_working_directory if copy == "live"
               else state["backend_snapshot"])
    real = _prover(state)

    def overlapping(backend, runtime_sha256):
        evidence = real(backend, runtime_sha256)
        return {**evidence, "dependency_roots": [*evidence["dependency_roots"], str(runtime / "src")]}

    report = _assess(state, prove_shared_interpreter=overlapping)
    assert report["rollback"]["ready"] is False and "backend" not in report["rollback"]["artifacts"]
    assert "overlaps a runtime copy" in report["rollback"]["blockers"][0]


@pytest.mark.parametrize("copy", ["live", "snapshot"])
def test_held_gate_refuses_an_overlapping_closure(tmp_path, monkeypatch, copy):
    state = _held_state(tmp_path, monkeypatch)
    arguments = _held_fixture(tmp_path, monkeypatch, state, {})
    runtime = (state["backend"].process_working_directory if copy == "live"
               else arguments["old_snapshot"] / "backend")
    original = issuer._old_shared_interpreter_evidence
    monkeypatch.setattr(issuer, "_old_shared_interpreter_evidence", lambda **kw: {
        **original(**kw), "dependency_roots": [*original(**kw)["dependency_roots"], str(runtime / "src")]})
    with pytest.raises(ValueError, match="overlaps a runtime copy"):
        issuer._held_old_preflight(**arguments)


@pytest.mark.parametrize("fault", ["root_dropped", "root_reordered", "root_added"])
def test_issuer_declared_roots_must_equal_the_identity_and_the_preparation_pins(tmp_path, monkeypatch, fault):
    state = _bundle(tmp_path, monkeypatch)
    arguments = _issuer_arguments(tmp_path, monkeypatch, state)
    roots = list(arguments["dependency_roots"])
    arguments["dependency_roots"] = tuple({
        "root_dropped": roots[:-1], "root_reordered": roots[::-1], "root_added": [*roots, tmp_path],
    }[fault])
    with pytest.raises(ValueError, match="Protected old-pair rollback preflight differs"):
        issuer.issue_wavea_activation(**arguments)
    assert not arguments["receipt_path"].exists() and not arguments["key_path"].exists()


def test_a_different_declared_closure_verifies_but_changes_the_identity_digest(tmp_path, monkeypatch):
    """Closure completeness is an external property: only the reviewed digest tells closures apart."""
    state = _bundle(tmp_path, monkeypatch)
    full = _assess(state, prove_shared_interpreter=_prover(state))
    full_digest = full["rollback"]["artifacts"]["backend"]["interpreter"]["identity_sha256"]
    old = state["old"]
    stdlib = tmp_path / "base-stdlib"
    stdlib.mkdir()
    (stdlib / "os.py").write_text("# fixture standard library\n")
    wider = (*old.dependencies, stdlib)
    old.dependencies = wider
    old.pins = prepare._pin_inputs(set(wider), set(), dependency_roots=wider,
                                   allow_dependency_file_links=True)
    old.identity = prepare._capture_old_backend_python_identity(
        old.service, dependency_roots=wider, dependency_pins=old.pins,
        allow_dependency_file_links=True)
    runtime_sha256 = preflight._runtime_digest(state["backend"].process_working_directory, backend=True)
    old_python_record(state["bundle"], old, runtime_sha256=runtime_sha256)
    save(state["bundle"] / "preparation-pins.json", {
        "schema_version": "bilun-preparation-pins-v3", "immutable_inputs": old.pins,
        "dependency_roots": [str(path) for path in wider], "external_state": {},
    })
    report = _assess(state, prove_shared_interpreter=_prover(state))
    assert report["rollback"]["ready"] is True
    assert report["rollback"]["artifacts"]["backend"]["interpreter"]["identity_sha256"] != full_digest


def test_real_launcher_semantics_match_what_the_identity_binds(tmp_path):
    """The captured launcher path (argv[0]) decides the environment; the terminal is /proc exe."""
    if sys.platform != "linux":
        pytest.skip("needs /proc")
    venv = tmp_path / "shared-venv"
    built = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)],
                           capture_output=True, text=True)
    if built.returncode:
        assert not os.environ.get("CI"), "venv creation must work on CI: " + built.stderr[-300:]
        pytest.skip("cannot build a venv on this host")
    launcher = venv / "bin/python"
    report = subprocess.run(
        [str(launcher), "-I", "-c",
         "import json,os,sys;print(json.dumps({'prefix':sys.prefix,'executable':sys.executable,"
         "'exe':os.readlink('/proc/self/exe'),'argv0':sys.orig_argv[0]}))"],
        check=True, capture_output=True, text=True).stdout
    seen = json.loads(report)
    assert Path(seen["prefix"]).resolve() == venv.resolve()
    assert seen["argv0"] == str(launcher) and seen["executable"] == str(launcher)
    assert Path(seen["exe"]) == launcher.resolve()


def _held_issuer_arguments(tmp_path, monkeypatch, state):
    """The real issuer in owned-maintenance mode: held journal stubbed, everything else real."""
    arguments = _issuer_arguments(tmp_path, monkeypatch, state)
    bundle = state["bundle"]
    shutil.rmtree(bundle / "rehearsal")
    held = _held_fixture(tmp_path, monkeypatch, state, {})
    probes = bundle / "rehearsal"
    probe_sha = {role: hashlib.sha256((probes / f"old-{role}-probe.json").read_bytes()).hexdigest()
                 for role in ("backend", "frontend")}
    previous = issuer.verify_private_rehearsal
    monkeypatch.setattr(issuer, "verify_private_rehearsal", lambda *a, **k: {
        **previous(*a, **k), "old_backend_probe_sha256": probe_sha["backend"],
        "old_frontend_probe_sha256": probe_sha["frontend"]})
    loader = issuer._load_private_json
    monkeypatch.setattr(issuer, "_load_private_json", lambda path, **k: (
        ({}, "f" * 64) if path == held["rehearsal_path"]
        else ({}, "1" * 64) if path == arguments["tuple_observation_path"]
        else _load_private_json(path, **k) if path.parent == bundle / "old-snapshot"
        else loader(path, **k)))
    arguments.update(
        rehearsal_path=held["rehearsal_path"], old_backend_environment_path=held["old_backend_environment_path"],
        old_snapshot_journal_path=held["journal_path"],
        old_snapshot_journal_identity_sha256=held["journal_identity_sha256"],
    )
    return arguments


def test_issuer_in_owned_maintenance_mode_seals_the_measured_layout_and_reports_the_identity(
        tmp_path, monkeypatch):
    state = _held_state(tmp_path, monkeypatch)
    arguments = _held_issuer_arguments(tmp_path, monkeypatch, state)
    issued = issuer.issue_wavea_activation(**arguments)
    assert issued["old_backend_interpreter"]["identity_sha256"] == _digest(state["old"].identity)
    assert arguments["receipt_path"].is_file()


def test_issuer_in_owned_maintenance_mode_hands_the_declared_roots_to_the_held_gate(tmp_path, monkeypatch):
    state = _held_state(tmp_path, monkeypatch)
    arguments = _held_issuer_arguments(tmp_path, monkeypatch, state)
    arguments["dependency_roots"] = tuple(arguments["dependency_roots"][:-1])
    with pytest.raises(ValueError, match="differs from its frozen observation"):
        issuer.issue_wavea_activation(**arguments)
    assert not arguments["receipt_path"].exists()


def test_issuer_in_online_mode_never_adds_the_identity_for_the_legacy_layout(tmp_path, monkeypatch):
    state = _bundle(tmp_path, monkeypatch, local_venv=True)
    arguments = _issuer_arguments(tmp_path, monkeypatch, state)
    assert "old_backend_interpreter" not in issuer.issue_wavea_activation(**arguments)


@pytest.mark.parametrize("field", [
    "launcher_path", "process_argv_sha256", "executable_target",
    "effective_environment_sha256", "runtime_sha256",
])
def test_bind_requires_every_observed_process_field_to_match(tmp_path, field):
    evidence = _evidence(tmp_path)
    observed = dict(
        process_launcher=evidence["launcher_path"], process_argv_sha256="2" * 64,
        process_executable=Path("/usr/bin/python3.13"), effective_environment_sha256="3" * 64,
        runtime_sha256="4" * 64, runtime_roots=(tmp_path / "live",),
    )
    assert preflight.bind_shared_interpreter(evidence, **observed)["kind"] == "shared_interpreter"
    key = {"launcher_path": "process_launcher", "executable_target": "process_executable"}.get(field, field)
    observed[key] = Path("/usr/bin/other") if key == "process_executable" else "9" * 64 \
        if key != "process_launcher" else str(tmp_path / "other/.venv/bin/python")
    with pytest.raises(ValueError, match="differs from the serving old backend"):
        preflight.bind_shared_interpreter(evidence, **observed)


@pytest.mark.parametrize("where", ["live", "snapshot"])
def test_a_local_environment_directory_in_either_copy_blocks_the_shared_proof(tmp_path, monkeypatch, where):
    """An empty .venv directory is invisible to the runtime digest, so it must be refused explicitly."""
    state = _bundle(tmp_path, monkeypatch)
    root = state["backend"].process_working_directory if where == "live" else state["backend_snapshot"]
    (root / ".venv").mkdir()
    report = _assess(state, prove_shared_interpreter=_prover(state))
    assert report["rollback"]["blockers"] == [BLOCKER]


def test_paired_release_old_artifact_gate_needs_no_snapshot_environment(tmp_path, monkeypatch):
    """The real rollback gate hashes the LIVE old runtime and terminal executable, never a snapshot .venv."""
    from types import SimpleNamespace

    from scripts.deploy.paired_release import SingleVpsDriver

    state = _bundle(tmp_path, monkeypatch)
    live = state["backend"].process_working_directory
    assert not os.path.lexists(live / ".venv")
    node = tmp_path / "node"
    node.write_bytes(b"fixture frontend executable\n")
    prepared = {
        "old_services": [{"process_working_directory": str(live),
                          "process_executable": str(state["old"].terminal)},
                         {"process_working_directory": str(state["frontend"].process_working_directory),
                          "process_executable": str(node)}],
        "old_runtime_sha256": [preflight._runtime_digest(live, backend=True),
                               preflight._runtime_digest(state["frontend"].process_working_directory,
                                                         backend=False)],
        "old_executable_sha256": [preflight._stable_file_digest(state["old"].terminal),
                                  preflight._stable_file_digest(node)],
    }
    driver = SimpleNamespace(_prepared=lambda: prepared)
    SingleVpsDriver._verify_old_artifacts(driver)
    state["old"].terminal.write_bytes(b"changed terminal executable\n")
    with pytest.raises(ValueError, match="Protected old runtime or executable changed"):
        SingleVpsDriver._verify_old_artifacts(driver)
