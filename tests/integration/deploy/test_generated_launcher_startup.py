"""Cold generated systemd launchers with genuine signed startup verification.

Only listening executables and existing synthetic build/replay/OS boundaries
are fabricated. Generated wrapper arguments and original API startup/loaders
execute in fresh interpreters, without inherited bytecode suppression.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.deploy import paired_release as paired
from scripts.deploy.paired_release_transaction import PairedReleaseTransaction
from src.bilun.api import wavea_activation
from tests.integration.deploy import test_signed_transition_startup as signed
from tests.unit.deploy import test_single_vps_release_integration as integration


_COLD_STARTUP_PROBE = """
import asyncio
import json
import os
import sys
from src.bilun.api import app, release_identity, startup, wavea_activation

async def check():
    async with app.router.lifespan_context(app):
        assert startup.is_cache_ready()
        activation = wavea_activation.activation_for_build('candidate')
        assert activation is not None
        print(json.dumps({
            'stage': 'signed_startup', 'ready': True,
            'receipt_version': activation.receipt_version,
            'dont_write_bytecode': sys.flags.dont_write_bytecode,
            'environment_no_bytecode': os.environ.get('PYTHONDONTWRITEBYTECODE'),
            'code_sha': release_identity.STARTUP_RELEASE_IDENTITY.code_sha,
            'source_manifest_sha256': release_identity.STARTUP_RELEASE_IDENTITY.source_manifest_sha256,
            'origins': {name: module.__file__ for name, module in (
                ('startup', startup), ('wavea_activation', wavea_activation),
                ('release_identity', release_identity),
            )},
        }), flush=True)

asyncio.run(check())
"""


def _cold_probe_executable(tmp_path, real_python):
    """Replace only listening executables; retain original launcher/API imports.

    The shim exists outside the sealed runtime before preparation pins. Its
    Python shim forwards every generated interpreter argument unchanged; only
    the subsequent uvicorn service is replaced by the original API lifespan.
    The Node shim's diagnostic Python starts with -B only AFTER the unchanged
    frontend launcher has imported/execed, so it cannot mask launcher churn.
    """
    executable_dir = tmp_path / "synthetic-executables"
    executable_dir.mkdir(mode=0o700)
    python = executable_dir / "python"
    launch_path = tmp_path / "bundle/transaction/launch.json"
    frontend_probe = f"""
import json
import os
import sys
print(json.dumps({{
    'stage': 'frontend_exec', 'arguments': sys.argv[1:], 'cwd': os.getcwd(),
    'frontend_port': os.environ.get('PORT'),
    'frontend_pythonpath': os.environ.get('PYTHONPATH'),
}}), flush=True)
config = json.loads(open({str(launch_path)!r}).read())
sys.path.insert(0, config['backend_runtime'])
from scripts.deploy.launch_wavea_candidate import candidate_command
_, _, cwd, environment = candidate_command('backend', config)
os.chdir(cwd)
os.execve({real_python!r}, [{real_python!r}, '-B', '-c', {_COLD_STARTUP_PROBE!r}], environment)
"""
    python.write_text(f"#!{real_python}\n" + f"""
import json
import os
import sys
args = sys.argv[1:]
module = args.index('-m') if '-m' in args else -1
if module >= 0 or (args and args[0].endswith('/server.js')):
    print(json.dumps({{'stage': 'interpreter_exec', 'arguments': args}}), flush=True)
if module >= 0 and args[module + 1] == 'uvicorn':
    command = [{real_python!r}, *args[:module], '-c', {_COLD_STARTUP_PROBE!r}]
elif args and args[0].endswith('/server.js'):
    command = [{real_python!r}, '-B', '-c', {frontend_probe!r}, *args]
else:
    command = [{real_python!r}, *args]
os.execve({real_python!r}, command, dict(os.environ))
""")
    python.chmod(0o700)
    return python


def _signed_tree_inventory(root):
    # Match the existing production runtime digest's mutable-root policy;
    # application logging is permitted, while source bytecode remains included.
    ignored = {".git", ".cache", ".worktrees", "frontend", "logs"}
    return {path.relative_to(root).as_posix(): integration.sha(path)
            for path in root.rglob("*") if path.is_file()
            and path.relative_to(root).parts[0] not in ignored
            and path.name != ".env" and not path.name.startswith(".env.")}


@pytest.fixture(scope="module")
def launcher_transport_sources(tmp_path_factory):
    return signed.combined_transport_sources.__wrapped__(tmp_path_factory)


def test_actual_generated_units_cold_signed_v1_v2_startup(tmp_path, monkeypatch, launcher_transport_sources):
    """Exact generated ExecStart imports cannot mutate the signed runtime.

    Synthetic executable seams avoid network listeners. Original source/runtime
    hash functions, API lifespan, captured release identity and both receipt
    loaders run in fresh interpreters; no startup globals or validators are
    replaced in the children. Controller -B does not reach generated units.
    """
    real_python = sys.executable
    executable = _cold_probe_executable(tmp_path, real_python)
    monkeypatch.setattr(sys, "executable", str(executable))
    bundle = signed.make_combined_transition_bundle(tmp_path, monkeypatch, launcher_transport_sources)
    fake = signed.CombinedHost(bundle, monkeypatch)
    driver = paired.SingleVpsDriver(signed._read(bundle.manifest))
    transaction = PairedReleaseTransaction(state_dir=driver.root, lock_path=driver.paths["lock_path"],
        manifest_sha256=integration.sha(bundle.manifest), driver=driver)
    transaction.prepare()
    backend_before = _signed_tree_inventory(driver.backend)
    assert not any(path.endswith(".pyc") or "__pycache__" in Path(path).parts for path in backend_before)
    assert all(os.access(directory, os.W_OK) for directory in (
        driver.backend, driver.backend / "src", driver.backend / "src/bilun/api",
        driver.backend / "scripts", driver.backend / "scripts/deploy",
    ))
    frontend_before = _signed_tree_inventory(driver.frontend)
    frontend_runtime_before = integration._runtime_digest(driver.frontend, backend=False)
    runtime_before = integration._runtime_digest(driver.backend, backend=True)
    signed_paths = (driver.candidate_receipt, driver.candidate_db, driver.key,
                    Path(driver.config["source_roster_path"]), bundle.root / "semantic.json",
                    bundle.root / "candidate-backend-env.nul", bundle.root / "candidate-frontend-env.nul",
                    *sorted(path for folder in ("evidence", "rehearsal")
                            for path in (bundle.root / folder).rglob("*") if path.is_file()))
    signed_before = {str(path): integration.sha(path) for path in signed_paths}
    # Separate baseline sanity proves this genuinely signed v1 cache can cold
    # boot; its explicit -B is not part of either generated service invocation.
    config = driver.config
    v1_environment = {**bundle.fixed_backend,
        "BILUN_CACHE_DB_PATH": str(driver.candidate_db),
        "BILUN_RELEASE_CODE_SHA": config["code_sha"],
        "BILUN_RELEASE_SOURCE_MANIFEST_SHA256": integration.sha(Path(config["source_roster_path"])),
        "BILUN_STARTUP_POLICY": "verified-load-only",
        "BILUN_WAVEA_ACTIVATION_RECEIPT": str(driver.candidate_receipt),
        "BILUN_WAVEA_ACTIVATION_KEY_FILE": str(driver.key),
        "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "POLARS_MAX_THREADS": "1",
    }
    baseline = subprocess.run([real_python, "-B", "-c", _COLD_STARTUP_PROBE], cwd=driver.backend,
                              env=v1_environment, capture_output=True, text=True, timeout=60)
    assert baseline.returncode == 0, baseline.stderr
    baseline_events = [json.loads(line) for line in baseline.stdout.splitlines() if line.startswith("{")]
    baseline_started = baseline_events[-1]
    assert baseline_started["receipt_version"] == wavea_activation.RECEIPT_VERSION
    assert baseline_started["code_sha"] == config["code_sha"]
    assert baseline_started["source_manifest_sha256"] == v1_environment["BILUN_RELEASE_SOURCE_MANIFEST_SHA256"]
    assert all(Path(path).is_relative_to(driver.backend) for path in baseline_started["origins"].values())
    assert _signed_tree_inventory(driver.backend) == backend_before
    assert signed_before == {str(path): integration.sha(path) for path in signed_paths}
    driver.maintenance()
    driver.stop_pair()
    driver.snapshot()
    driver.derive_and_sign()
    driver.install_candidate()
    signed_paths += (driver.root / "serving-receipt.json", driver.root / "derivation.json",
                     driver.root / "launch.json", driver.paths["live_cache_path"])
    signed_before = {str(path): integration.sha(path) for path in signed_paths}
    outcomes = []
    for role in ("backend", "frontend"):
        unit = (driver.root / f"{role}.conf").read_text()
        command = next(line.removeprefix("ExecStart=") for line in unit.splitlines()
                       if line.startswith("ExecStart=") and line != "ExecStart=")
        argv = shlex.split(command)
        cwd = Path(next(line.removeprefix("WorkingDirectory=") for line in unit.splitlines()
                        if line.startswith("WorkingDirectory=")))
        import_root = next(line.removeprefix("Environment=PYTHONPATH=") for line in unit.splitlines()
                           if line.startswith("Environment=PYTHONPATH="))
        assert cwd == (driver.backend if role == "backend" else driver.frontend)
        assert Path(import_root) == driver.backend
        assert argv[0] == str(executable)
        assert argv[argv.index("-m") + 1:] == ["scripts.deploy.launch_wavea_candidate", role,
                                               "--config", str(driver.root / "launch.json")]
        # Only the generated unit import root enters this fresh interpreter.
        # Explicit whitelist excludes inherited controller suppression/config.
        environment = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": import_root,
                       "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "POLARS_MAX_THREADS": "1"}
        assert not {"PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX", "PYTHONHOME", "PYTHONOPTIMIZE"} & environment.keys()
        assert _signed_tree_inventory(driver.backend) == backend_before
        process = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, text=True, timeout=60)
        after = _signed_tree_inventory(driver.backend)
        changed = sorted(path for path in set(after) | set(backend_before)
                         if after.get(path) != backend_before.get(path))
        outcome = {"role": role, "argv": argv, "cwd": str(cwd), "import_root": import_root,
                   "returncode": process.returncode, "stdout": process.stdout, "stderr": process.stderr,
                   "runtime_before": runtime_before,
                   "runtime_after": integration._runtime_digest(driver.backend, backend=True),
                   "changed_files": changed,
                   "frontend_runtime_before": frontend_runtime_before,
                   "frontend_runtime_after": integration._runtime_digest(driver.frontend, backend=False),
                   "frontend_files_unchanged": _signed_tree_inventory(driver.frontend) == frontend_before,
                   "signed_artifacts_unchanged": signed_before == {str(path): integration.sha(path) for path in signed_paths}}
        outcomes.append(outcome)
        # Retain the actual signed-loader/hash failure BEFORE disposable cleanup;
        # restore only fresh bytecode so the next role gets a cold independent run.
        for relative in changed:
            path = driver.backend / relative
            if relative not in backend_before and path.suffix == ".pyc":
                path.unlink()
        for directory in sorted(driver.backend.rglob("__pycache__"), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()
        assert _signed_tree_inventory(driver.backend) == backend_before
    print("GENERATED_SIGNED_STARTUP=" + json.dumps(outcomes, sort_keys=True))
    for outcome in outcomes:
        assert outcome["signed_artifacts_unchanged"]
        assert outcome["frontend_files_unchanged"]
        assert outcome["frontend_runtime_after"] == outcome["frontend_runtime_before"]
        assert outcome["runtime_after"] == outcome["runtime_before"], outcome
        assert outcome["changed_files"] == [], outcome
        assert outcome["returncode"] == 0, outcome
        events = [json.loads(line) for line in outcome["stdout"].splitlines() if line.startswith("{")]
        forwarded = next(event for event in events if event.get("stage") == "interpreter_exec")
        assert forwarded["arguments"] == outcome["argv"][1:]
        assert "-B" in outcome["argv"][1:outcome["argv"].index("-m")]
        if outcome["role"] == "frontend":
            frontend = next(event for event in events if event.get("stage") == "frontend_exec")
            assert frontend["cwd"] == str(driver.frontend)
            assert frontend["arguments"] == [str(driver.frontend / "server.js")]
            assert frontend["frontend_port"] == "3000" and frontend["frontend_pythonpath"] is None
        started = next(event for event in events if event.get("stage") == "signed_startup")
        assert started["receipt_version"] == "wavea-serving-receipt-v2" and started["ready"] is True
        assert all(Path(path).is_relative_to(driver.backend) for path in started["origins"].values())
        assert started["code_sha"] == config["code_sha"]
        assert started["source_manifest_sha256"] == v1_environment["BILUN_RELEASE_SOURCE_MANIFEST_SHA256"]
    assert fake.running == {"backend": False, "frontend": False}
