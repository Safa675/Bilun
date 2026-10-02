"""Real derived DB/signature/install/startup checks on a disposable fake host.

Only the already-tested original v1 attestation and OS/network boundaries are
stubbed. Derivation, strict all-row validation, v2 signing/hashing, replacement,
restoration and application cache startup use the production implementations.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from scripts.deploy import paired_release as paired
from scripts.deploy.paired_release_transaction import atomic_json
from src.bilun.api import release_identity, startup, wavea_activation
from tests.unit.deploy.test_derive_serving_cache import _initialize
from tests.unit.deploy.test_verify_candidate_cache import BUILD_ID, CODE_SHA, _cache_fixture


def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / "release"
    root.mkdir(mode=0o700)
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir(mode=0o700)
    candidate, roster, _ = _cache_fixture(candidate_dir)
    with duckdb.connect(str(candidate)) as con:
        con.execute("UPDATE build_pointer_scopes SET active_build_id=? WHERE scope='bilun'", [BUILD_ID])
    live = tmp_path / "live.duckdb"
    _initialize(live)
    os.chmod(live, 0o640)
    backend, frontend, old_frontend = (tmp_path / name for name in ("backend", "frontend", "old-frontend"))
    for path in (backend, frontend, old_frontend): path.mkdir()
    current = tmp_path / "current"
    current.symlink_to(old_frontend)
    key = root / "key"
    key.write_bytes(b"fixture only existing signing key" * 2)
    key.chmod(0o600)
    original = {
        "schema_version": wavea_activation.RECEIPT_VERSION,
        "cache_build_id": BUILD_ID, "cache_sha256": _sha(candidate),
        "code_sha": CODE_SHA, "source_roster_path": str(roster),
        "source_roster_sha256": _sha(roster),
    }
    original_path = root / "candidate-receipt.json"
    atomic_json(original_path, original)
    original_startup = wavea_activation.load_startup_activation
    activation = wavea_activation.WaveAActivation(
        release_id="fixture", ci_run_id="123", code_sha=CODE_SHA,
        source_roster_sha256=_sha(roster), cache_build_id=BUILD_ID,
        cache_sha256=_sha(candidate), sidecar_sha256="a" * 64,
        receipt_sha256=_sha(original_path),
    )

    def original_gate(environ, **kwargs):
        if environ["BILUN_WAVEA_ACTIVATION_RECEIPT"] == str(original_path):
            if _sha(Path(kwargs["cache_path"])) != activation.cache_sha256:
                raise ValueError("Original candidate bytes differ")
            return activation
        return original_startup(environ, **kwargs)

    monkeypatch.setattr(wavea_activation, "load_startup_activation", original_gate)
    monkeypatch.setattr(startup, "load_startup_activation", original_gate)
    driver = object.__new__(paired.SingleVpsDriver)
    driver.root, driver.candidate_db, driver.candidate_receipt = root, candidate, original_path
    driver.key, driver.backend, driver.frontend = key, backend, frontend
    driver.manifest = {"old_build_id": "old-13"}
    driver.paths = {"live_cache_path": live, "frontend_current": current}
    config_files = {}
    for role in ("backend", "frontend"):
        path = tmp_path / f"bilun-{role}.service.d"
        path.mkdir()
        dropin = path / "bilun-paired-release.conf"
        driver.paths[f"{role}_dropin"] = dropin
        config_files[str(dropin)] = None
    backend_environment = root / "backend.nul"
    frontend_environment = root / "frontend.nul"
    for path in (backend_environment, frontend_environment):
        path.write_bytes(b"KEY=value\0"); path.chmod(0o600)
    driver.config = {
        "backend_python": sys.executable, "cache_path": str(candidate),
        "activation_receipt_path": str(original_path),
        "candidate_backend_environment": str(backend_environment),
        "candidate_frontend_environment": str(frontend_environment),
    }
    driver.config_sha = "b" * 64
    atomic_json(root / "prepared-pair.json", {
        "configuration": config_files, "old_link": str(old_frontend),
        "candidate_config_sha256": driver.config_sha,
        "candidate_receipt_sha256": _sha(original_path),
        "candidate_environment_sha256": {name: _sha(Path(driver.config[name]))
                                         for name in ("candidate_backend_environment", "candidate_frontend_environment")},
    })
    monkeypatch.setattr(driver, "_candidate_gate", lambda: original)
    monkeypatch.setattr(driver, "_verify_pins", lambda: None)
    monkeypatch.setattr(driver, "_known_route_gate", lambda: None)
    monkeypatch.setattr(driver, "_require_maintenance", lambda: None)
    monkeypatch.setattr(driver, "_verify_old_artifacts", lambda: None)
    monkeypatch.setattr(paired, "candidate_environments", lambda *_: ({}, {}))
    monkeypatch.setattr(driver, "stop_pair", lambda: None)
    monkeypatch.setattr(paired, "_run", lambda *_: "")
    monkeypatch.setattr(paired, "observe_service", lambda *_: SimpleNamespace(active_state="active"))
    return driver, activation, original_startup


def _activate(host, monkeypatch):
    driver, activation, loader = host
    old_bytes = driver.paths["live_cache_path"].read_bytes()
    driver.snapshot()
    timings = driver.derive_and_sign()
    assert timings["derivation"] >= 0 and timings["final_validation_and_signing"] >= 0
    driver.install_candidate()
    driver.start_pair()
    monkeypatch.setattr(release_identity, "STARTUP_RELEASE_IDENTITY", release_identity.ReleaseIdentity(
        activation.code_sha, activation.source_roster_sha256,
    ))
    monkeypatch.setattr(startup, "_PROJECT_ROOT", driver.backend)
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "verified-load-only")
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(driver.paths["live_cache_path"]))
    monkeypatch.setenv("BILUN_WAVEA_ACTIVATION_RECEIPT", str(driver.root / "serving-receipt.json"))
    monkeypatch.setenv("BILUN_WAVEA_ACTIVATION_KEY_FILE", str(driver.key))
    return old_bytes


def test_real_derive_sign_install_startup_and_exact_restore(host, monkeypatch):
    driver, original, _ = host
    old = _activate(host, monkeypatch)
    asyncio.run(startup.startup())
    assert startup.is_cache_ready() is True
    activated = wavea_activation.activation_for_build(BUILD_ID)
    assert activated.cache_sha256 == _sha(driver.paths["live_cache_path"])
    assert activated.cache_sha256 != original.cache_sha256
    with duckdb.connect(str(driver.paths["live_cache_path"]), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM build_meta").fetchone()[0] == 15
        assert con.execute("SELECT note FROM annotations").fetchone()[0] == "keep me"
        assert con.execute("SELECT active_build_id FROM build_pointer_scopes WHERE scope='research'").fetchone()[0] == "old-2"
    assert driver.paths["live_cache_path"].stat().st_mode & 0o777 == 0o640
    driver.restore_old()
    assert driver.paths["live_cache_path"].read_bytes() == old
    assert not driver.paths["backend_dropin"].exists()
    assert not driver.paths["frontend_dropin"].exists()
    assert driver.paths["frontend_current"].resolve().name == "old-frontend"


@pytest.mark.parametrize("artifact", ["receipt", "proof", "serving", "candidate", "wal"])
def test_final_artifact_tamper_prevents_startup(host, monkeypatch, artifact):
    driver, _, _ = host
    _activate(host, monkeypatch)
    paths = {"receipt": driver.root / "serving-receipt.json", "proof": driver.root / "derivation.json",
             "serving": driver.paths["live_cache_path"], "candidate": driver.candidate_db}
    if artifact == "wal":
        Path(str(driver.paths["live_cache_path"]) + ".wal").symlink_to(driver.root / "missing-wal")
    elif artifact == "serving":
        with duckdb.connect(str(paths[artifact])) as con:
            con.execute("UPDATE annotations SET note='tampered'")
    elif artifact in {"receipt", "proof"}:
        value = json.loads(paths[artifact].read_text())
        value["serving_cache_sha256" if artifact == "receipt" else "serving_sha256"] = "0" * 64
        atomic_json(paths[artifact], value)
    else:
        with paths[artifact].open("ab") as output: output.write(b"tamper")
    with pytest.raises(SystemExit): asyncio.run(startup.startup())
    assert startup.is_cache_ready() is False
    assert wavea_activation.activation_for_build(BUILD_ID) is None


def test_final_receipt_uses_existing_key_without_modification(host, monkeypatch):
    driver, _, _ = host
    before = driver.key.read_bytes()
    _activate(host, monkeypatch)
    assert driver.key.read_bytes() == before


def test_generated_units_declare_actual_role_cwd_and_pinned_import_root(host):
    driver, _, _ = host
    driver.snapshot(); driver.derive_and_sign()
    for role, runtime in (("backend", driver.backend), ("frontend", driver.frontend)):
        unit = (driver.root / f"{role}.conf").read_text()
        assert f"WorkingDirectory={runtime}\n" in unit
        assert f"Environment=PYTHONPATH={driver.backend}\n" in unit
        assert f"scripts.deploy.launch_wavea_candidate {role}" in unit


def test_unsigned_v2_never_authorizes_extra_pointer_startup(host, monkeypatch):
    driver, _, _ = host
    _activate(host, monkeypatch)
    receipt = driver.root / "serving-receipt.json"
    value = json.loads(receipt.read_text())
    value["signature_sha256"] = "0" * 64
    atomic_json(receipt, value)
    with pytest.raises(SystemExit): asyncio.run(startup.startup())
    assert not startup.is_cache_ready()


def test_v1_keeps_single_scope_constraint(host, monkeypatch):
    driver, _, _ = host
    _activate(host, monkeypatch)
    monkeypatch.setenv("BILUN_WAVEA_ACTIVATION_RECEIPT", str(driver.candidate_receipt))
    with pytest.raises(RuntimeError, match="one active Bilun"):
        startup._load_verified_release_cache()


@pytest.mark.parametrize("sql", [
    "DELETE FROM build_pointer_scopes WHERE scope='bilun'",
    "UPDATE build_pointer_scopes SET active_build_id='old-13' WHERE scope='bilun'",
    "UPDATE build_meta SET code_sha='wrong' WHERE build_id='candidate-build'",
])
def test_invalid_selected_bilun_pointer_is_rejected(host, monkeypatch, sql):
    driver, _, _ = host
    _activate(host, monkeypatch)
    with duckdb.connect(str(driver.paths["live_cache_path"])) as con: con.execute(sql)
    with pytest.raises((RuntimeError, SystemExit)):
        asyncio.run(startup.startup())


@pytest.mark.parametrize("point", ["database", "backend_dropin", "frontend_dropin", "symlink"])
def test_real_install_interruption_restores_database_and_config(host, monkeypatch, point):
    driver, _, _ = host
    old = driver.paths["live_cache_path"].read_bytes()
    driver.snapshot(); driver.derive_and_sign()
    real_file, real_link = paired._replace_file, paired._replace_link
    count = 0
    def fail_file(source, target, mode, **kwargs):
        nonlocal count
        real_file(source, target, mode, **kwargs)
        count += 1
        if count == {"database": 1, "backend_dropin": 2, "frontend_dropin": 3}.get(point):
            raise KeyboardInterrupt()
    def fail_link(*args):
        real_link(*args)
        if point == "symlink": raise KeyboardInterrupt()
    monkeypatch.setattr(paired, "_replace_file", fail_file)
    monkeypatch.setattr(paired, "_replace_link", fail_link)
    with pytest.raises(KeyboardInterrupt): driver.install_candidate()
    monkeypatch.setattr(paired, "_replace_file", real_file)
    monkeypatch.setattr(paired, "_replace_link", real_link)
    driver.restore_old()
    assert driver.paths["live_cache_path"].read_bytes() == old
    assert driver.paths["frontend_current"].resolve().name == "old-frontend"
    assert not driver.paths["backend_dropin"].exists()
    assert not driver.paths["frontend_dropin"].exists()


def test_byte_identical_final_cache_replay_remains_attestable(host, monkeypatch):
    driver, original, loader = host
    _activate(host, monkeypatch)
    replay = driver.root / "replay.duckdb"
    shutil.copyfile(driver.paths["live_cache_path"], replay)
    value = loader({"BILUN_WAVEA_ACTIVATION_RECEIPT": str(driver.root / "serving-receipt.json"),
                    "BILUN_WAVEA_ACTIVATION_KEY_FILE": str(driver.key)},
                   cache_path=replay, active_build_id=BUILD_ID, code_sha=CODE_SHA,
                   source_manifest_sha256=original.source_roster_sha256, backend_runtime=driver.backend)
    assert value.cache_sha256 == _sha(replay)


@pytest.mark.parametrize("role,key,value", [
    ("backend", "BILUN_AUTH_PASSWORD", "changed"),
    ("backend", "BILUN_PUBLIC_BILLING_ENABLED", "true"),
    ("backend", "BILUN_DATA_MODE", "real_claims"),
    ("backend", "BILUN_PUBLIC_CHAT_BUDGET_DB", "/tmp/reset.sqlite"),
    ("frontend", "EXTRA_UNTESTED", "true"),
])
def test_signed_rehearsal_rejects_post_rehearsal_environment_change(role, key, value):
    from scripts.deploy.rehearse_wavea_pair import env_digest
    receipt = {"code_sha": CODE_SHA, "source_roster_sha256": "a" * 64}
    cache = Path("/candidate.duckdb")
    backend, frontend = {"BILUN_AUTH_PASSWORD": "original"}, {}
    observed = {"logical_tuple": {
        "backend": {"effective_environment_sha256": env_digest({**backend,
            "BILUN_CACHE_DB_PATH": str(cache), "BILUN_RELEASE_CODE_SHA": CODE_SHA,
            "BILUN_RELEASE_SOURCE_MANIFEST_SHA256": "a" * 64,
            "BILUN_STARTUP_POLICY": "verified-load-only", "PYTHONDONTWRITEBYTECODE": "1"})},
        "frontend": {"effective_environment_sha256": env_digest({"PORT": "3000",
            "HOSTNAME": "127.0.0.1", "NODE_ENV": "production",
            "API_PROXY_TARGET": "http://127.0.0.1:8001", "BILUN_RELEASE_CODE_SHA": CODE_SHA})},
    }}
    paired._verify_rehearsed_environments(backend, frontend, receipt, cache, observed)
    (backend if role == "backend" else frontend)[key] = value
    with pytest.raises(ValueError, match="signed rehearsal"):
        paired._verify_rehearsed_environments(backend, frontend, receipt, cache, observed)


def test_v2_duplicate_selected_pointer_fails_before_readiness(tmp_path, monkeypatch):
    cache = tmp_path / "duplicate.duckdb"
    with duckdb.connect(str(cache)) as con:
        con.execute("CREATE TABLE build_pointer_scopes(scope VARCHAR,active_build_id VARCHAR)")
        con.execute("INSERT INTO build_pointer_scopes VALUES ('bilun','one'),('bilun','two'),('research','saved')")
    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"schema_version":"wavea-serving-receipt-v2"}')
    receipt.chmod(0o600)
    monkeypatch.setattr(release_identity, "STARTUP_RELEASE_IDENTITY", release_identity.ReleaseIdentity(CODE_SHA, "a" * 64))
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(cache))
    monkeypatch.setenv("BILUN_WAVEA_ACTIVATION_RECEIPT", str(receipt))
    with pytest.raises(RuntimeError, match="one active Bilun"):
        startup._load_verified_release_cache()


@pytest.mark.parametrize("foreign", ["environment", "dropin", "symlink", "database", "wal"])
def test_foreign_changes_are_not_clobbered_by_restore(host, monkeypatch, foreign):
    driver, _, _ = host
    _activate(host, monkeypatch)
    if foreign == "environment":
        target, backup = driver.root / "operator.env", driver.root / "operator.saved"
        target.write_bytes(b"before"); backup.write_bytes(b"before")
        saved = driver._prepared()
        saved["configuration"][str(target)] = {
            "backup": str(backup), "sha256": _sha(backup), "mode": target.stat().st_mode & 0o777,
            "uid": target.stat().st_uid, "gid": target.stat().st_gid,
        }
        atomic_json(driver.root / "prepared-pair.json", saved)
        target.write_bytes(b"operator edit")
    elif foreign == "dropin":
        target = driver.paths["backend_dropin"]
        target.write_bytes(b"operator unit edit")
    elif foreign == "symlink":
        target = driver.paths["frontend_current"]
        target.unlink(); target.symlink_to(driver.root / "third-frontend")
    elif foreign == "database":
        target = driver.paths["live_cache_path"]
        with duckdb.connect(str(target)) as con: con.execute("UPDATE annotations SET note='operator edit'")
    else:
        target = Path(str(driver.paths["live_cache_path"]) + ".wal")
        target.write_bytes(b"unrelated WAL")
    before_db = driver.paths["live_cache_path"].read_bytes()
    before_target = os.readlink(target) if target.is_symlink() else target.read_bytes()
    with pytest.raises(ValueError, match="Unrelated|unrelated"):
        driver.rollback_gate()
    with pytest.raises(ValueError, match="Unrelated|unrelated"):
        driver.restore_old()
    assert driver.paths["live_cache_path"].read_bytes() == before_db
    assert (os.readlink(target) if target.is_symlink() else target.read_bytes()) == before_target


def test_incomplete_receipt_before_install_does_not_block_old_restore(host):
    driver, _, _ = host
    old = driver.paths["live_cache_path"].read_bytes()
    driver.snapshot()
    (driver.root / "serving-receipt.json").write_bytes(b'{"incomplete"')
    driver.restore_old()
    assert driver.paths["live_cache_path"].read_bytes() == old
