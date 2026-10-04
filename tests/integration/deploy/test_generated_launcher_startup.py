"""Cold generated systemd launchers with genuine signed startup verification.

Only the backend listening executable and existing synthetic cache/replay/OS
boundaries are fabricated. The frontend runs its genuine rebuilt standalone
server. Original generated wrappers and signed startup/loaders remain intact.

Requires Node >=20.9 and npm. BILUN_TEST_FRONTEND_BUILD may select a completed
frontend source/build directory; otherwise one copied frontend is installed
and built per module. A missing prerequisite or failed build fails the test.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

import pytest

from scripts.deploy import paired_release as paired
from scripts.deploy import prepare_single_vps_release as preparer
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

    The shim exists outside the sealed runtime before preparation pins and
    forwards every generated interpreter argument unchanged. Only the uvicorn
    service is replaced by the original API lifespan; frontend exec is real.
    """
    executable_dir = tmp_path / "synthetic-executables"
    executable_dir.mkdir(mode=0o700)
    python = executable_dir / "python"
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
else:
    command = [{real_python!r}, *args]
os.execve({real_python!r}, command, dict(os.environ))
""")
    python.chmod(0o700)
    return python


def _signed_tree_inventory(root, *, backend=True):
    # Match the existing production runtime digest's mutable-root policy;
    # application logging is permitted, while source bytecode remains included.
    ignored = {".git", ".cache", ".worktrees", "frontend", "logs"} if backend else {".git"}
    return {path.relative_to(root).as_posix(): integration.sha(path)
            for path in root.rglob("*") if path.is_file()
            and path.relative_to(root).parts[0] not in ignored
            and path.name != ".env" and not path.name.startswith(".env.")}


def _frontend_inventory(root):
    # Include empty directories: a strict file digest alone misses mkdir churn.
    return {path.relative_to(root).as_posix():
            ("link", os.readlink(path)) if path.is_symlink() else
            ("directory",) if path.is_dir() else ("file", integration.sha(path))
            for path in root.rglob("*")}


def _authored_png():
    def chunk(kind, payload):
        return struct.pack("!I", len(payload)) + kind + payload + struct.pack("!I", zlib.crc32(kind + payload))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", 128, 64, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + bytes((17, 83, 149)) * 128) * 64)) + chunk(b"IEND", b""))


@pytest.fixture(scope="module")
def launcher_frontend_build(tmp_path_factory):
    node = shutil.which("node")
    npm = shutil.which("npm")
    assert node and npm, "Real standalone regression requires Node >=20.9 and npm"
    node = Path(node).resolve(strict=True)
    version = subprocess.check_output([str(node), "--version"], text=True).strip()
    assert tuple(map(int, version.removeprefix("v").split(".")[:2])) >= (20, 9), version
    selected = os.environ.get("BILUN_TEST_FRONTEND_BUILD")
    if selected:
        frontend = Path(selected).resolve(strict=True)
    else:
        frontend = tmp_path_factory.mktemp("real-standalone-build") / "frontend"
        shutil.copytree(Path(__file__).resolve().parents[3] / "frontend", frontend,
                        ignore=shutil.ignore_patterns("node_modules", ".next", ".env", ".env.*"))
        environment = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1", "NODE_ENV": "production",
                       "API_PROXY_TARGET": "http://127.0.0.1:8001"}
        for arguments in (("ci", "--include=dev"), ("run", "build")):
            result = subprocess.run([str(node), str(Path(npm).resolve(strict=True)), *arguments],
                                    cwd=frontend, env=environment, capture_output=True, text=True, timeout=1800)
            assert result.returncode == 0, f"Real frontend {' '.join(arguments)} failed:\n{result.stdout}\n{result.stderr}"
    assert (frontend / ".next/standalone").is_dir(), "Selected frontend must contain a completed standalone build"
    return frontend, node


@pytest.fixture(scope="module")
def launcher_transport_sources(tmp_path_factory, launcher_frontend_build):
    snapshots = signed.combined_transport_sources.__wrapped__(tmp_path_factory)
    # Commit the actual build's frontend source, including its config/lockfile,
    # before the existing factory makes final source commits and runtime seals.
    frontend, _ = launcher_frontend_build
    for source, _ in snapshots.values():
        shutil.copytree(frontend, source / "frontend",
                        ignore=shutil.ignore_patterns("node_modules", ".next", ".env", ".env.*"))
        signed._fixture_git(source, "add", "frontend")
        signed._fixture_git(source, "commit", "-qm", "authentic standalone frontend source inputs")
    return snapshots


def _install_real_frontend(monkeypatch, frontend, node):
    real_prepare, real_identity = preparer.prepare_release_bundle, integration.candidate_identity

    def build(spec, _checkout):
        runtime = spec["bundle_root"] / "candidate-frontend"
        preparer.assemble_release_payload(frontend, runtime, spec["target_sha"], spec["release_id"])
        old = spec["bundle_root"] / "old-snapshot/frontend"
        for relative, digest in preparer.build_asset_manifest(old).items():
            destination = runtime / ".next/static" / relative
            if destination.exists():
                assert integration.sha(destination) == digest
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old / ".next/static" / relative, destination)
        # The existing middleware permits public brand assets; use that actual
        # route without fabricating authentication or changing access policy.
        (runtime / "public/brand").mkdir(parents=True, exist_ok=True)
        (runtime / "public/brand/signed-test-image.png").write_bytes(_authored_png())
        config = signed._read(runtime / ".next/required-server-files.json")["config"]
        images = config["images"]
        assert images["maximumDiskCacheSize"] == 0
        assert images["loader"] == "default" and images["unoptimized"] is False
        assert images["customCacheHandler"] is False
        assert not config.get("cacheHandler") and config["experimental"]["isrFlushToDisk"] is True
        embedded = re.search(r"const nextConfig = (.+)\n", (runtime / "server.js").read_text())
        assert embedded and json.loads(embedded[1])["images"]["maximumDiskCacheSize"] == 0
        preparer._verify_frontend_api_rewrite(runtime, 8001)
        assert preparer.inspect_assets(runtime)["ok"]
        return runtime

    def prepare(manifest):
        # The combined factory installs its synthetic builder immediately before
        # this call. Replace only that build boundary before any runtime hashes.
        spec = signed._read(manifest)
        spec["node"] = str(node)
        integration.save(manifest, spec)
        monkeypatch.setattr(preparer, "_build_frontend", build)
        return real_prepare(manifest)

    def identity(root):
        return {**real_identity(root), "frontend_build_id": (root / "candidate-frontend/.next/BUILD_ID").read_text().strip()}

    monkeypatch.setattr(preparer, "prepare_release_bundle", prepare)
    monkeypatch.setattr(integration, "candidate_identity", identity)


def _real_image_cycles(argv, cwd, environment, node, driver, real_python, backend_environment, immutable):
    # Fail if this exact loopback port belongs to another process. Only our own
    # subprocess is ever terminated; generated argv/PORT are not rewritten.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 3000))
    from scripts.deploy.launch_wavea_candidate import candidate_command
    executable, command, expected_cwd, expected_environment = candidate_command("frontend", signed._read(driver.root / "launch.json"))
    assert executable == node and command == [str(node), str(cwd / "server.js")] and expected_cwd == cwd
    assert expected_environment["PORT"] == "3000" and "PYTHONPATH" not in expected_environment
    runtime_before = integration._runtime_digest(cwd, backend=False)
    cycles = []
    png_responses = []
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = "http://127.0.0.1:3000/_next/image?url=%2Fbrand%2Fsigned-test-image.png&w=64&q=75"
    decode = """const sharp = require('sharp'); const fs = require('fs');
async function check() { const image = sharp(fs.readFileSync(0)); const metadata = await image.metadata();
if(metadata.format!==process.argv[1]) throw Error('wrong encoded format');
const {data,info} = await image.ensureAlpha().raw().toBuffer({resolveWithObject:true});
if(info.width!==64 || info.height!==32 || info.channels!==4) throw Error(JSON.stringify(info));
const tolerance = Number(process.argv[2]);
for(let i=0;i<data.length;i+=4) if(Math.abs(data[i]-17)>tolerance || Math.abs(data[i+1]-83)>tolerance || Math.abs(data[i+2]-149)>tolerance || data[i+3]!==255) throw Error('wrong pixel');
console.log(JSON.stringify({...info, source_format:metadata.format})); }
check().catch(error => {console.error(error); process.exit(1)});"""
    for cycle in range(2):
        assert _frontend_inventory(cwd) == immutable
        with (driver.root / f"real-frontend-{cycle}.log").open("w+") as log:
            process = subprocess.Popen(argv, cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 30
                while True:
                    assert process.poll() is None, "Real standalone exited before image response"
                    try:
                        response = http.open(urllib.request.Request(url, headers={"Accept": "image/png"}), timeout=2)
                        break
                    except urllib.error.HTTPError:
                        raise
                    except (urllib.error.URLError, TimeoutError):
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.1)
                proc = Path(f"/proc/{process.pid}")
                assert (proc / "exe").resolve(strict=True) == node
                assert (proc / "cwd").resolve(strict=True) == cwd
                # Next replaces process.title after starting; executable/cwd/env
                # remain observable while original candidate_command proves argv.
                assert (proc / "cmdline").read_bytes().startswith(b"next-server (v")
                effective = dict(item.split(b"=", 1) for item in (proc / "environ").read_bytes().split(b"\0") if item)
                assert effective[b"PORT"] == b"3000" and b"PYTHONPATH" not in effective
                requests = []
                for repeat, accept in enumerate(["image/png", "image/png"] + (["image/webp"] if cycle == 0 else [])):
                    if repeat:
                        response = http.open(urllib.request.Request(url, headers={"Accept": accept}), timeout=10)
                    with response:
                        body = response.read()
                        assert response.status == 200 and response.headers.get_content_type() == accept
                        assert "Accept" in response.headers.get("Vary", "")
                        assert "public" in response.headers["Cache-Control"] and "must-revalidate" in response.headers["Cache-Control"]
                        decoded = subprocess.run([str(node), "-e", decode, accept.removeprefix("image/"),
                                                  "3" if accept == "image/webp" else "0"],
                                                 cwd=cwd, env=expected_environment, input=body, capture_output=True, timeout=30)
                        assert decoded.returncode == 0, decoded.stderr
                        body_sha, etag = hashlib.sha256(body).hexdigest(), response.headers["ETag"]
                        assert etag
                        if accept == "image/png":
                            png_responses.append((body_sha, etag))
                        requests.append({"bytes": len(body), "body_sha256": body_sha, "etag": etag,
                                         "decoded": json.loads(decoded.stdout),
                                         "cache": response.headers.get("X-Nextjs-Cache"), "cache_control": response.headers["Cache-Control"]})
                    assert _frontend_inventory(cwd) == immutable
                    assert integration._runtime_digest(cwd, backend=False) == runtime_before
                startup = subprocess.run([real_python, "-B", "-c", _COLD_STARTUP_PROBE], cwd=driver.backend,
                                         env=backend_environment, capture_output=True, text=True, timeout=60)
                assert startup.returncode == 0, startup.stderr
                assert process.poll() is None
                assert _frontend_inventory(cwd) == immutable
                assert integration._runtime_digest(cwd, backend=False) == runtime_before
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            log.seek(0)
            stdout = log.read()
        assert _frontend_inventory(cwd) == immutable
        assert integration._runtime_digest(cwd, backend=False) == runtime_before
        assert process.returncode in (-signal.SIGTERM, 128 + signal.SIGTERM)
        cycles.append({"cycle": cycle, "requests": requests, "startup_stdout": startup.stdout, "stdout": stdout,
                       "returncode": process.returncode, "node": str(node), "cwd": str(cwd),
                       "runtime_sha256": runtime_before, "inventory_entries": len(immutable)})
    assert len(png_responses) == 4 and len(set(png_responses)) == 1
    return cycles


def test_actual_generated_units_cold_signed_v1_v2_startup(tmp_path, monkeypatch, launcher_transport_sources,
                                                       launcher_frontend_build):
    """Exact generated ExecStart imports cannot mutate the signed runtime.

    Original source/runtime hashes, API lifespan, captured release identity and
    both receipt loaders run in fresh interpreters. The actual standalone image
    optimizer serves/repeats/restarts without changing the signed frontend.
    Controller -B does not reach generated units.
    """
    real_python = sys.executable
    executable = _cold_probe_executable(tmp_path, real_python)
    monkeypatch.setattr(sys, "executable", str(executable))
    frontend, node = launcher_frontend_build
    _install_real_frontend(monkeypatch, frontend, node)
    bundle = signed.make_combined_transition_bundle(tmp_path, monkeypatch, launcher_transport_sources)
    bundle.spec["node"] = str(node)
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
    frontend_before = _frontend_inventory(driver.frontend)
    assert os.access(driver.frontend, os.W_OK) and os.access(driver.frontend / ".next", os.W_OK)
    assert not (driver.frontend / ".next/cache/images").exists()
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
        if role == "frontend":
            # Derive the backend's fresh process environment with the original
            # signed launcher, then run original API startup after image cycles.
            from scripts.deploy.launch_wavea_candidate import candidate_command
            _, _, _, backend_environment = candidate_command("backend", signed._read(driver.root / "launch.json"))
            cycles = _real_image_cycles(argv, cwd, environment, node, driver, real_python,
                                        backend_environment, frontend_before)
            stdout = cycles[0]["stdout"] + cycles[-1]["startup_stdout"]
            returncode, stderr = cycles[-1]["returncode"], ""
        else:
            process = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, text=True, timeout=60)
            returncode, stdout, stderr = process.returncode, process.stdout, process.stderr
        after = _signed_tree_inventory(driver.backend)
        changed = sorted(path for path in set(after) | set(backend_before)
                         if after.get(path) != backend_before.get(path))
        outcome = {"role": role, "argv": argv, "cwd": str(cwd), "import_root": import_root,
                   "returncode": returncode, "stdout": stdout, "stderr": stderr,
                   "runtime_before": runtime_before,
                   "runtime_after": integration._runtime_digest(driver.backend, backend=True),
                   "changed_files": changed,
                   "frontend_runtime_before": frontend_runtime_before,
                   "frontend_runtime_after": integration._runtime_digest(driver.frontend, backend=False),
                   "frontend_files_unchanged": _frontend_inventory(driver.frontend) == frontend_before,
                   "signed_artifacts_unchanged": signed_before == {str(path): integration.sha(path) for path in signed_paths}}
        outcomes.append(outcome)
        if role == "frontend":
            outcome["image_cycles"] = cycles
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
        assert outcome["returncode"] in ((-signal.SIGTERM, 128 + signal.SIGTERM)
                                         if outcome["role"] == "frontend" else (0,)), outcome
        events = [json.loads(line) for line in outcome["stdout"].splitlines() if line.startswith("{")]
        forwarded = next(event for event in events if event.get("stage") == "interpreter_exec")
        assert forwarded["arguments"] == outcome["argv"][1:]
        assert "-B" in outcome["argv"][1:outcome["argv"].index("-m")]
        if outcome["role"] == "frontend":
            assert len(outcome["image_cycles"]) == 2
            for cycle in outcome["image_cycles"]:
                started = [json.loads(line) for line in cycle["startup_stdout"].splitlines() if line.startswith("{")][-1]
                assert started["receipt_version"] == "wavea-serving-receipt-v2" and started["ready"] is True
                assert started["code_sha"] == config["code_sha"]
                assert started["source_manifest_sha256"] == v1_environment["BILUN_RELEASE_SOURCE_MANIFEST_SHA256"]
                assert all(Path(path).is_relative_to(driver.backend) for path in started["origins"].values())
        started = next(event for event in events if event.get("stage") == "signed_startup")
        assert started["receipt_version"] == "wavea-serving-receipt-v2" and started["ready"] is True
        assert all(Path(path).is_relative_to(driver.backend) for path in started["origins"].values())
        assert started["code_sha"] == config["code_sha"]
        assert started["source_manifest_sha256"] == v1_environment["BILUN_RELEASE_SOURCE_MANIFEST_SHA256"]
    assert fake.running == {"backend": False, "frontend": False}
