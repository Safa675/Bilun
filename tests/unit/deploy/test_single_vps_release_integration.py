"""Cross-module release integration on real DuckDB files and a fabricated host.

No process, service, network namespace, Caddy, or HTTP request is executed. The
fixture substitutes source checkout/build/trace/rehearsal-record production and
same-input build provenance (covered separately). Structural and full-v2 semantic checks,
sidecar construction, v1 issuance/verification, handoff, paired driver/state
machine, derivation, v2 signing, startup, and tuple observation remain real.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import duckdb
import pytest

from scripts.deploy import build_wavea_sidecar as sidecar
from scripts.deploy import http_release_probes as http
from scripts.deploy import issue_wavea_activation as issuer
from scripts.deploy import observe_candidate_tuple as observer
from scripts.deploy import paired_release as paired
from scripts.deploy import prepare_single_vps_release as preparer
from scripts.deploy import snapshot_maintenance as snapshot
from scripts.deploy import verify_frontend_assets as assets
from scripts.deploy import verify_public_billing_access as access
from scripts.deploy import verify_candidate_semantics as semantics
from scripts.deploy.capture_release_preflight import ServiceObservation, _runtime_digest
from scripts.deploy.candidate_environment import candidate_environments
from scripts.deploy.launch_wavea_candidate import candidate_command
from scripts.deploy.paired_release_transaction import PairedReleaseError, PairedReleaseTransaction
from scripts.deploy.prepare_wavea_routes import OLD_CADDYFILE
from scripts.deploy.verify_candidate_cache import _BUILDER_TABLES, verify_candidate_cache
from scripts.deploy.verify_private_rehearsal import _SAME_PORT_ROUTE_SHA256
from src.bilun.api import release_identity, startup, wavea_activation
from tests.unit.deploy.test_candidate_environment import candidate_auth, write_env
from tests.unit.deploy.test_observe_candidate_tuple import _process
from tests.unit.deploy.test_prepare_single_vps_release import machine as preparation_machine
from tests.unit.deploy.test_verify_candidate_semantics import _current_fixture, _reidentify_fixture


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True))
    path.chmod(0o600)


def candidate_identity(root):
    report = json.loads((root / "structural.json").read_text())
    return {
        "build_id": report["build"]["build_id"], "code_sha": report["build"]["code_sha"],
        "source_hash": report["build"]["legacy_source_hash"],
        "source_roster_sha256": sha(root / "source-roster.json"),
        "cache_sha256": sha(root / "candidate.duckdb"),
        "backend_runtime_sha256": _runtime_digest(root / "candidate-backend", backend=True),
        "frontend_runtime_sha256": _runtime_digest(root / "candidate-frontend", backend=False),
        "frontend_build_id": "fixture-front", "frontend_assets_sha256":
            observer._static_assets(root / "candidate-frontend")[1],
        "patient_count": 1, "bill_count": 1,
    }


def recorded_rehearsal(root, old_build="baseline"):
    """Fabricated I/O observation, consumed by the real strict rehearsal verifier."""
    work = root / "rehearsal"
    work.mkdir(mode=0o700)
    candidate = candidate_identity(root)
    logical = {key: candidate[key] for key in (
        "backend_runtime_sha256", "frontend_runtime_sha256", "frontend_build_id",
        "frontend_assets_sha256",
    )}
    logical.update(
        backend={"port": 8001}, frontend={"port": 3000},
        cache={"build_id": candidate["build_id"], "sha256": candidate["cache_sha256"],
               "source_hash": candidate["source_hash"], "patient_count": 1, "bill_count": 1,
               "evidence_capability": "draft"},
        health={"active_build": candidate["build_id"], "code_sha": candidate["code_sha"],
                "source_manifest_sha256": candidate["source_roster_sha256"],
                "wavea_capability": "draft", "cache_ready": True, "status": "ok"},
    )
    backend, frontend = candidate_environments(root / "candidate-backend-env.nul", root / "candidate-frontend-env.nul")
    backend.update(BILUN_CACHE_DB_PATH=str(root / "candidate.duckdb"), BILUN_RELEASE_CODE_SHA=candidate["code_sha"],
                   BILUN_RELEASE_SOURCE_MANIFEST_SHA256=candidate["source_roster_sha256"],
                   BILUN_STARTUP_POLICY="verified-load-only", PYTHONDONTWRITEBYTECODE="1")
    frontend.update(PORT="3000", HOSTNAME="127.0.0.1", NODE_ENV="production",
                    API_PROXY_TARGET="http://127.0.0.1:8001", BILUN_RELEASE_CODE_SHA=candidate["code_sha"])
    for role, values in (("backend", backend), ("frontend", frontend)):
        logical[role]["effective_environment_sha256"] = hashlib.sha256(
            b"\0".join(sorted(f"{key}={value}".encode() for key, value in values.items()))).hexdigest()
    observed = {"status": "candidate_tuple_observed", "activation_ready": False,
                "tuple_sha256": observer._canonical_digest(logical), "logical_tuple": logical,
                "backend_listener": {"port": 8001}, "frontend_listener": {"port": 3000}}
    save(work / "candidate-tuple-observation.json", observed)
    for role, port, suffix, checks in (
        ("backend", 8001, "health", ["health", "representative_api"]),
        ("frontend", 3000, "login", ["login_assets"]),
    ):
        save(work / f"old-{role}-probe.json", {
            "passed": True, "runtime_sha256": "1" * 64, "effective_environment_sha256": "2" * 64,
            "private_url": f"http://127.0.0.1:{port}/{suffix}", "checks": checks,
            "cache_sha256": sha(root / "old-snapshot/cache.duckdb"),
            "active_build": old_build, "build_id": "old-front",
        })
    save(work / "old-api-capture.json", {"/api/billing-report/P1": {},
                                         "/api/billing-report/P1/bills/C1": {}})
    save(work / "same-input-rehearsal.json", {"status": "same_input_bytes_verified", "candidate": {
        "roster_sha256": candidate["source_roster_sha256"], "source_hash": candidate["source_hash"],
    }})
    rehearsal = {
        "schema_version": "wavea-same-port-rehearsal-v2", "profile": "single-vps-same-port-v2",
        "backend_port": 8001, "frontend_port": 3000, "access_checks": 20,
        "baseline_contract": "wavea-evidence-v2", "candidate_wavea_capability": "draft",
        "old_wavea_capability": "complete-25-v1", "public_activation_ready": False,
        "producer_script_sha256": sha(root / "candidate-backend/scripts/deploy/rehearse_wavea_same_port.py"),
        "candidate_sha": candidate["code_sha"], "candidate_cache_sha256": candidate["cache_sha256"],
        "candidate_frontend_build_id": candidate["frontend_build_id"],
        "candidate_tuple_sha256": observed["tuple_sha256"],
        "candidate_tuple_observation_sha256": sha(work / "candidate-tuple-observation.json"),
        "old_api_capture_sha256": sha(work / "old-api-capture.json"),
        "same_input_proof_sha256": sha(work / "same-input-rehearsal.json"),
        "old_backend_probe_sha256": sha(work / "old-backend-probe.json"),
        "old_frontend_probe_sha256": sha(work / "old-frontend-probe.json"),
        "legacy_api_patients_checked": 1, "legacy_api_bills_checked": 1,
        "api_paths_checked": 4, "old_assets_checked": 10, "candidate_assets_checked": 10,
        "old_route_sha256": _SAME_PORT_ROUTE_SHA256, "candidate_route_sha256": _SAME_PORT_ROUTE_SHA256,
    }
    rehearsal.update(dict.fromkeys((
        "passed", "network_namespace_isolated", "candidate_pair_routing_verified", "old_pair_restored",
        "sequential_same_ports_verified", "compiled_proxy_verified", "authentication_verified",
        "public_real_data_guard_verified", "public_asset_guard_verified", "persisted_api_dtos_verified",
    ), True))
    save(work / "real-candidate-namespace-rehearsal.json", rehearsal)


def make_bundle(tmp_path, monkeypatch, previous=None):
    # Capture actual production functions before the existing I/O fixture patches them.
    real_structural = verify_candidate_cache
    real_bridge = semantics.verify_serving_baseline_equivalence
    real_semantic = semantics.verify_candidate_semantic_checkpoint
    manifest, spec, events, _ = preparation_machine.__wrapped__(tmp_path, monkeypatch)
    root = Path(spec["bundle_root"])
    data = tmp_path / "real-artifacts"
    baseline, candidate, roster = _current_fixture(data)
    build_id = "candidate" if previous is None else "candidate-next"
    if previous is not None:
        _reidentify_fixture(candidate, "candidate", build_id)
        with duckdb.connect(str(candidate)) as con:
            con.execute("UPDATE build_meta SET code_sha=?", ["c" * 40])
    for path, build in ((baseline, "baseline"), (candidate, build_id)):
        with duckdb.connect(str(path)) as con:
            counts = {table: con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                      for table in _BUILDER_TABLES}
            con.execute("UPDATE build_meta SET row_counts_json=?,checksums_json=?",
                        [json.dumps(counts), json.dumps({"sut_patient_count": "1"})])
            con.execute("UPDATE build_pointer_scopes SET active_build_id=? WHERE scope='bilun'", [build])
    live = Path(spec["live_cache_path"])
    shutil.copy2(baseline, live)
    with duckdb.connect(str(live)) as con:
        for index in range(14):
            con.execute("INSERT INTO build_meta SELECT * REPLACE (? AS build_id, 'superseded' AS status) "
                        "FROM build_meta WHERE build_id='baseline'", [f"history-{index}"])
        con.execute("INSERT INTO build_pointer_scopes VALUES ('research','history-2','preserve')")
        con.execute("CREATE SCHEMA custom; CREATE TABLE custom.notes(build_id VARCHAR,note VARCHAR)")
        con.execute("INSERT INTO custom.notes VALUES ('candidate','user state'),(NULL,'unknown history')")
        con.execute("CREATE TABLE annotations(id INTEGER,note VARCHAR); INSERT INTO annotations VALUES (1,'retain')")
    spec.update(target_sha="b" * 40, baseline_code_sha="a" * 40, serving_code_sha="a" * 40,
                old_build_id="baseline", patient_id="P1", backend_python=sys.executable,
                node=sys.executable, npm=sys.executable)
    for role in ("backend", "frontend"):
        folder = tmp_path / f"bilun-{role}.service.d"
        folder.mkdir(mode=0o700)
        spec[f"{role}_dropin"] = str(folder / "bilun-paired-release.conf")
    if previous is not None:
        old_fake, old_driver, _ = previous
        for key in ("live_cache_path", "frontend_current", "backend_dropin", "frontend_dropin",
                    "lock_path", "caddy_config", "signing_key_path"):
            spec[key] = old_fake.spec[key]
        spec.update(live_backend_runtime=str(old_driver.backend), live_frontend_runtime=str(old_driver.frontend),
                    old_build_id="candidate", baseline_code_sha="b" * 40, serving_code_sha="b" * 40,
                    target_sha="c" * 40, release_id="repeat-release")
        live = Path(spec["live_cache_path"])
    write_env(Path(spec["candidate_backend_environment"]), candidate_auth())
    write_env(Path(spec["candidate_frontend_environment"]), {"NODE_ENV": "production"})
    Path(spec["caddy_config"]).write_bytes(OLD_CADDYFILE)
    save(manifest, spec)
    original_checkout, original_frontend = preparer._create_checkout, preparer._build_frontend
    original_snapshot = preparer._snapshot_old

    def snapshot(parsed, before):
        result = original_snapshot(parsed, before)
        write_env(root / "old-snapshot/backend-effective-env.nul", {
            **candidate_auth(), "BILUN_CACHE_DB_PATH": str(live),
            "BILUN_HEALTH_PROBE_TOKEN": "fixture-old-health-token-1234567890",
        })
        return result

    def checkout(parsed):
        path, claims, clean = original_checkout(parsed)
        producer = path / "scripts/deploy/rehearse_wavea_same_port.py"
        producer.parent.mkdir(parents=True)
        producer.write_bytes(Path("scripts/deploy/rehearse_wavea_same_port.py").read_bytes())
        (producer.parent / "launch_wavea_candidate.py").write_bytes(Path("scripts/deploy/launch_wavea_candidate.py").read_bytes())
        return path, claims, clean

    def frontend(parsed, backend):
        path = original_frontend(parsed, backend)
        (path / ".next/static").mkdir(parents=True)
        (path / ".next/BUILD_ID").write_text("fixture-front")
        save(path / ".next/required-server-files.json", {"config": {"productionBrowserSourceMaps": False}})
        for index in range(10):
            (path / f".next/static/{index}.js").write_text(f"console.log({index})")
        save(path / ".next/routes-manifest.json", {"rewrites": {"beforeFiles": [], "fallback": [],
             "afterFiles": [{"source": "/api/:path*", "destination": "http://127.0.0.1:8001/api/:path*"}]}})
        return path

    def build(**kwargs):
        shutil.copy2(candidate, kwargs["db_path"])
        for field in ("trace_path", "log_path"):
            kwargs[field].write_text("fabricated build process boundary")
        save(kwargs["report_path"], {"build_id": build_id})
        return {"build_id": build_id}

    def semantic(baseline_path, **kwargs):
        report = real_semantic(baseline_path, baseline_build_id=kwargs["baseline_build_id"],
                               candidate_db=kwargs["candidate_db"], candidate_build_id=kwargs["candidate_build_id"],
                               source_roster=kwargs["source_roster"])
        # Only the detached-checkout/build provenance is fabricated here.
        report["same_input"] = {"status": "same_input_bytes_verified"}
        report["remaining_gates"].remove("same_input_baseline_byte_attestation_missing")
        return report

    def trace(**kwargs):
        return {"status": "traced_build_attestation_verified", "release_ready": False,
                "code_sha": spec["target_sha"], "build_id": build_id,
                "source_roster_sha256": sha(root / "source-roster.json"),
                "cache_sha256": sha(root / "candidate.duckdb")}

    def ci(**kwargs):
        events.append("ci")
        return {"status": "release_ci_verified", "code_sha": kwargs["code_sha"], "ci_run_id": kwargs["run_id"]}

    for name, function in {
        "_create_checkout": checkout, "_build_frontend": frontend, "build_traced_candidate": build,
        "_snapshot_old": snapshot,
        "generate_source_roster": lambda *a, **k: json.loads(roster.read_text()),
        "verify_candidate_cache": real_structural, "verify_serving_baseline_equivalence": real_bridge,
        "verify_candidate_semantic_checkpoint": semantic, "verify_traced_build_attestation": trace,
        "_rehearse": lambda *args: recorded_rehearsal(root, spec["old_build_id"]),
        "build_wavea_sidecar": sidecar.build_wavea_sidecar, "issue_wavea_activation": issuer.issue_wavea_activation,
        "fetch_successful_release_ci": ci,
    }.items():
        monkeypatch.setattr(preparer, name, function)
    # Real v1 issuer re-runs structural, semantic, sidecar, and rehearsal validators.
    for name, function in {"verify_candidate_semantic_checkpoint": semantic,
                           "verify_traced_build_attestation": trace, "fetch_successful_release_ci": ci}.items():
        monkeypatch.setattr(issuer, name, function)
    health = {"status": "ok", "active_build": spec["old_build_id"], "cache_ready": True,
              "code_sha": spec["serving_code_sha"]}
    monkeypatch.setattr(issuer, "_live_health", lambda *_: health)
    monkeypatch.setattr(issuer, "read_loopback_health", lambda *_: health, raising=False)
    monkeypatch.setattr(issuer, "observe_service", lambda *a: object())
    monkeypatch.setattr(issuer, "assess_release_preflight", lambda *a, **k: {
        "observed": {"backend": {"observed_checkout_head": spec["serving_code_sha"],
                     "serving_code_sha_verified": True, "health_code_sha": spec["serving_code_sha"]}},
        "rollback": {"blockers": [], "artifacts": {"backend": {"private_probe": {}},
                     "frontend": {"private_probe": {}}, "service_and_proxy_configuration": {},
                     "cache": {"active_build": spec["old_build_id"], "sha256": sha(root / "old-snapshot/cache.duckdb")}}},
    })
    result = preparer.prepare_release_bundle(manifest)
    pair_manifest = Path(result["paired_manifest_path"])
    return SimpleNamespace(root=root, manifest=pair_manifest, spec=spec, live=live, events=events,
                           old_bytes=live.read_bytes(), candidate=candidate)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    yield make_bundle(tmp_path, monkeypatch)
    # Each real DuckDB workflow uses several independent rollback/derived copies.
    # Do not retain successful large artifacts across a fault-injection matrix.
    shutil.rmtree(tmp_path)


def test_prepare_handoff_constructs_a_real_verifiable_signed_v1_candidate(bundle):
    manifest = json.loads(bundle.manifest.read_text())
    config = json.loads(Path(manifest["candidate_launch_config"]).read_text())
    receipt = json.loads(Path(config["activation_receipt_path"]).read_text())
    activation = wavea_activation.load_startup_activation({
        "BILUN_WAVEA_ACTIVATION_RECEIPT": config["activation_receipt_path"],
        "BILUN_WAVEA_ACTIVATION_KEY_FILE": config["activation_key_path"],
    }, cache_path=Path(config["cache_path"]), active_build_id="candidate", code_sha="b" * 40,
       source_manifest_sha256=receipt["source_roster_sha256"], backend_runtime=Path(config["backend_runtime"]))
    assert activation.cache_sha256 == sha(bundle.root / "candidate.duckdb")
    assert bundle.live.read_bytes() == bundle.old_bytes
    assert not list((bundle.root / "transaction").iterdir())


class FabricatedHost:
    """OS/HTTP adapter with independently modeled files, services, and routing."""

    def __init__(self, bundle, monkeypatch):
        self.bundle, self.patch = bundle, monkeypatch
        self.spec = bundle.spec
        self.events, self.fail_at, self.interrupt = [], None, False
        self.running = {"backend": True, "frontend": True}
        self.active_launch = None
        self.loaded_route = OLD_CADDYFILE
        self.proc = bundle.root / "fabricated-proc"
        self.proc.mkdir()
        (self.proc / "stat").write_text("btime 2100000000\n")
        self.old_environment = {**candidate_auth(), "BILUN_CACHE_DB_PATH": str(bundle.live)}
        self.old_environment.pop("BILUN_SESSION_TOKEN_PURPOSE")
        self.environments = {"backend": self.old_environment, "frontend": {"NODE_ENV": "production"}}
        self.working_dirs = {role: Path(self.spec[f"live_{role}_runtime"]) for role in self.running}
        self.arguments = {"backend": (sys.executable, "-m", "uvicorn", "old.app"),
                          "frontend": (sys.executable, "old-server.js")}
        self.unit_files = {}
        for role in self.running:
            unit = bundle.root / f"original-{role}.service"
            unit.write_text(f"[Service]\nWorkingDirectory={self.working_dirs[role]}\n")
            self.unit_files[role] = unit
        self._write_processes()

        real_read = Path.read_bytes
        def read(path):
            for role, pid in (("backend", 1001), ("frontend", 1002)):
                if str(path) == f"/proc/{pid}/environ":
                    return self._env_bytes(self.environments[role])
            return real_read(path)
        monkeypatch.setattr(Path, "read_bytes", read)
        real_read_text = Path.read_text
        monkeypatch.setattr(Path, "read_text", lambda path, *a, **kw:
                            "Uid:\t0\t0\t0\t0\n" if str(path) in {"/proc/1001/status", "/proc/1002/status"}
                            else real_read_text(path, *a, **kw))
        service_access = paired.SingleVpsDriver._service_access_gate
        def root_services(services):
            # The process adapter models root services, while temporary files
            # retain the real unprivileged test runner's UID/GID.
            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(paired.os, "geteuid", lambda: 0)
                service_access(services)
        monkeypatch.setattr(paired.SingleVpsDriver, "_service_access_gate", staticmethod(root_services))
        monkeypatch.setattr(paired, "observe_service", self.observe)
        monkeypatch.setattr(paired, "_run", self.run)
        monkeypatch.setattr(paired, "_live_health", lambda *_: self.health())
        monkeypatch.setattr(paired, "_github_read_token", lambda: "fabricated-read-token")
        monkeypatch.setattr(paired, "fetch_successful_release_ci", lambda **kw: {
            "status": "release_ci_verified", "code_sha": kw["code_sha"], "ci_run_id": kw["run_id"]})
        monkeypatch.setattr(paired, "_validate", lambda _: None)
        monkeypatch.setattr(paired, "_adapt", lambda path: {"fixture_caddy_bytes": path.read_text()})
        monkeypatch.setattr(paired, "CaddyRouteDriver", self.route_adapter)
        real_observer = observer.observe_candidate_tuple
        monkeypatch.setattr(observer, "observe_candidate_tuple", lambda spec, **kw:
                            real_observer(spec, proc_root=self.proc,
                                          listener_pid=lambda port: 1001 if port == 8001 else 1002, **kw))
        monkeypatch.setattr(http, "_fetch", self.fetch)
        real_access = access.verify
        monkeypatch.setattr(access, "verify", lambda *a, **kw: real_access(*a, fetch=self.access_get, **kw))
        monkeypatch.setattr(assets, "urlopen", self.urlopen)

    @staticmethod
    def _env_bytes(values):
        return b"\0".join(f"{key}={value}".encode() for key, value in values.items()) + b"\0"

    def event(self, name):
        self.events.append(name)
        if name == self.fail_at:
            self.fail_at = None
            raise KeyboardInterrupt(name) if self.interrupt else OSError(name)

    def _write_processes(self):
        for role, pid in (("backend", 1001), ("frontend", 1002)):
            shutil.rmtree(self.proc / str(pid), ignore_errors=True)
            _process(self.proc, pid, self.working_dirs[role],
                     b"\0".join(arg.encode() for arg in self.arguments[role]) + b"\0",
                     self._env_bytes(self.environments[role]))

    def observe(self, unit, port):
        role = "backend" if port == 8001 else "frontend"
        assert unit == f"bilun-{role}.service"
        dropin = Path(self.spec[f"{role}_dropin"])
        declared = self.working_dirs[role]
        files = (self.unit_files[role],)
        if dropin.exists():
            declared = Path(next(line.split("=", 1)[1] for line in dropin.read_text().splitlines()
                                 if line.startswith("WorkingDirectory=")))
            files += (dropin,)
        if declared != self.working_dirs[role]:
            raise ValueError("Observed declared/actual working directory mismatch")
        return ServiceObservation(
            unit=unit, active_state="active" if self.running[role] else "inactive",
            main_pid=1001 if role == "backend" else 1002,
            listener_pid=1001 if role == "backend" else 1002,
            declared_working_directory=declared, process_working_directory=self.working_dirs[role],
            process_executable=Path(sys.executable).resolve(), process_argv=self.arguments[role],
            unit_sha256=hashlib.sha256(b"".join(path.read_bytes() for path in files)).hexdigest(),
            unit_fragment=str(self.unit_files[role]), unit_files=files,
            environment_files=getattr(self, "environment_files", {}).get(role, ()),
            selected_environment=dict(self.environments[role]),
            environment_sha256=hashlib.sha256(self._env_bytes(self.environments[role])).hexdigest(),
            process_started_at_utc=datetime(2037, 1, 1, tzinfo=UTC),
        )

    def run(self, *args):
        if args[0] == "git":
            assert args == ("git", "-C", self.spec["live_backend_runtime"], "rev-parse", "HEAD")
            return self.spec["serving_code_sha"]
        if args[:2] == ("systemctl", "cat"):
            role = args[2].removeprefix("bilun-").removesuffix(".service")
            return self.unit_files[role].read_text()
        if args[:2] == ("systemctl", "daemon-reload"):
            self.event("daemon-reload")
        elif args[:2] == ("systemctl", "show"):
            if "--property=User" in args:
                return "root"
            if "--property=DynamicUser" in args:
                return "no"
            role = "backend" if "backend" in args[2] else "frontend"
            if "--property=ActiveState" in args:
                return "active" if self.running[role] else "inactive"
            return "1001" if self.running[role] else "0"
        elif args[0] == "ss":
            role = "backend" if args[-1].endswith("8001") else "frontend"
            return "fabricated-listener" if self.running[role] else ""
        elif args[:2] == ("systemctl", "stop"):
            for role in (unit.removeprefix("bilun-").removesuffix(".service") for unit in args[2:]):
                self.running[role] = False
                self.event("stop-" + role)
        elif args[:2] == ("systemctl", "start"):
            for role in (unit.removeprefix("bilun-").removesuffix(".service") for unit in args[2:]):
                dropin = Path(self.spec[f"{role}_dropin"])
                if dropin.exists():
                    launch_path = Path(dropin.read_text().split(" --config ")[1].strip())
                    config = json.loads(launch_path.read_text())
                    _, argv, cwd, environment = candidate_command(role, config)
                    self.working_dirs[role], self.arguments[role], self.environments[role] = cwd, tuple(argv), environment
                    if role == "backend":
                        self.active_launch = config
                        with pytest.MonkeyPatch.context() as patch:
                            for key, value in environment.items():
                                patch.setenv(key, value)
                            patch.setattr(release_identity, "STARTUP_RELEASE_IDENTITY", release_identity.ReleaseIdentity(
                                config["code_sha"], sha(config["source_roster_path"])))
                            patch.setattr(startup, "_PROJECT_ROOT", cwd)
                            asyncio.run(startup.startup())
                        assert startup.is_cache_ready()
                else:
                    self.working_dirs[role] = Path(self.spec[f"live_{role}_runtime"])
                    self.environments[role] = self.old_environment if role == "backend" else {"NODE_ENV": "production"}
                    self.arguments[role] = ((sys.executable, "-m", "uvicorn", "old.app") if role == "backend"
                                            else (sys.executable, "old-server.js"))
                    if role == "backend":
                        self.active_launch = None
                self.running[role] = True
                self._write_processes()
                self.event("start-" + role)
        else:
            raise AssertionError(f"Unexpected OS operation: {args}")
        return ""

    def health(self):
        assert self.running["backend"]
        with duckdb.connect(str(self.bundle.live), read_only=True) as con:
            build = con.execute("SELECT active_build_id FROM build_pointer_scopes WHERE scope='bilun'").fetchone()[0]
        value = {"status": "ok", "cache_ready": True, "active_build": build,
                 "code_sha": self.active_launch["code_sha"] if self.active_launch else self.spec["serving_code_sha"]}
        if self.active_launch:
            value.update(source_manifest_sha256=sha(self.active_launch["source_roster_path"]),
                         wavea_capability="complete-25-v1",
                         wavea_receipt_sha256=sha(self.active_launch["activation_receipt_path"]))
        return value

    def route_adapter(self, **kwargs):
        host = self

        class Routes:
            def verify_sealed_routes(self):
                for key, path in kwargs["route_files"].items():
                    if sha(path) != kwargs["expected_file_digests"][key]:
                        raise ValueError(f"Caddy {key} recovery route differs")

            def loaded_route_sha256(self):
                return paired._digest({"fixture_caddy_bytes": host.loaded_route.decode()})

            def installed_route_sha256(self):
                return paired._digest(paired._adapt(kwargs["config_path"]))

            def install(self, name):
                self.verify_sealed_routes()
                data = kwargs["route_files"][name].read_bytes()
                kwargs["config_path"].write_bytes(data)
                host.event("route-installed-" + name)
                host.loaded_route = data
                host.event("route-loaded-" + name)

        return Routes()

    def access_get(self, base, path, cookie=None):
        status, raw = self.fetch(base, path, cookie)
        return status, json.loads(raw) if raw else None

    def fetch(self, base, path, cookie=None):
        if base == "https://app.bilun.tech" and self.loaded_route != OLD_CADDYFILE:
            return 503, b""
        assert all(self.running.values()), "HTTP exposed a partially running pair"
        if path == "/login":
            return 200, "".join(f'<script src="/_next/static/{index}.js"></script>' for index in range(10)).encode()
        if path.startswith("/_next/static/"):
            return 200, b"console.log('fabricated asset')"
        if path == "/api/auth/me":
            dev = bool(cookie and cookie.startswith("bilun:session="))
            public = self.environments["backend"].get("BILUN_PUBLIC_BILLING_ENABLED", "").lower() in {
                "1", "true", "yes",
            }
            payload = {"authenticated": dev, "public_billing_enabled": public,
                       "capabilities": (["developer"] if dev else []) + (["billing"] if public else [])}
        elif path.startswith("/api/rules"):
            return (200 if cookie and cookie.startswith("bilun:session=") else 401), b"{}"
        elif path == "/api/patients" and cookie is None:
            public = self.environments["backend"].get("BILUN_PUBLIC_BILLING_ENABLED", "").lower() in {
                "1", "true", "yes",
            }
            return (200, b'{"patients":["P1"]}') if public else (401, b"{}")
        elif path == "/health":
            payload = self.health()
        else:
            payload = {"active_build": self.health()["active_build"], "path": path}
        return 200, json.dumps(payload).encode()

    def urlopen(self, request, **kwargs):
        path = urlparse(request.full_url).path
        content = ("".join(f'<script src="/_next/static/{index}.js"></script>' for index in range(10)).encode()
                   if path == "/login" else b"console.log('fabricated asset')")

        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return None
            def read(self, *a): return content

        return Response()


@pytest.fixture
def host(bundle, monkeypatch):
    monkeypatch.setattr(startup, "_startup_ready", False)
    monkeypatch.setattr(wavea_activation, "_startup_activation", None)
    fake = FabricatedHost(bundle, monkeypatch)
    driver = paired.SingleVpsDriver(json.loads(bundle.manifest.read_text()))
    transaction = PairedReleaseTransaction(state_dir=driver.root, lock_path=driver.paths["lock_path"],
                                           manifest_sha256=sha(bundle.manifest), driver=driver)
    transaction.prepare()
    return fake, driver, transaction


@pytest.fixture
def held_host(bundle, monkeypatch):
    """Real held snapshot and paired handoff over the existing fabricated host."""
    monkeypatch.setattr(startup, "_startup_ready", False)
    monkeypatch.setattr(wavea_activation, "_startup_activation", None)
    fake = FabricatedHost(bundle, monkeypatch)
    environment_file = bundle.root / "original-backend.env"
    environment_file.write_text("# Existing old service environment file\n")
    environment_file.chmod(0o600)
    fake.environment_files = {"backend": (environment_file,)}
    with fake.unit_files["backend"].open("a") as unit:
        unit.write(f"EnvironmentFile={environment_file}\n")
    journal = bundle.root / "snapshot-maintenance/transaction.json"
    journal.parent.mkdir(mode=0o700)
    output = bundle.root / "old-snapshot/cache.duckdb"
    output.unlink()  # Replace only this disposable fixture's independent copy.
    expected = {"health_identity": {key: fake.health().get(key) for key in (
        "status", "cache_ready", "active_build", "code_sha", "source_manifest_sha256",
    )}, "cache_sha256": sha(bundle.live), "caddy_sha256": sha(fake.spec["caddy_config"]),
        "frontend_target": str(Path(fake.spec["frontend_current"]).resolve())}
    for role, port in (("backend", 8001), ("frontend", 3000)):
        expected[role] = preparer._public_service(fake.observe(f"bilun-{role}.service", port))
        expected[role]["stable_environment_sha256"] = preparer.stable_environment_sha256(
            fake._env_bytes(fake.environments[role]))
        expected[role]["persistent_state_settings"] = {
            "BILUN_PUBLIC_CHAT_BUDGET_DB": fake.environments[role].get("BILUN_PUBLIC_CHAT_BUDGET_DB", ""),
        }
        expected[f"{role}_runtime_sha256"] = _runtime_digest(
            Path(fake.spec[f"live_{role}_runtime"]), backend=role == "backend")
    spec = {key: fake.spec[key] for key in (
        "live_backend_runtime", "live_frontend_runtime", "live_cache_path", "frontend_current",
        "caddy_config", "serving_code_sha", "old_build_id",
    )}
    monkeypatch.setattr(snapshot, "_run", fake.run)
    monkeypatch.setattr(snapshot, "_adapt", paired._adapt)
    monkeypatch.setattr(snapshot, "_validate", paired._validate)
    monkeypatch.setattr(snapshot, "CaddyRouteDriver", fake.route_adapter)

    def captured():
        assert not any(fake.running.values())
        value = copy.deepcopy(expected)
        for role in ("backend", "frontend"):
            value[f"{role}_runtime_sha256"] = _runtime_digest(
                Path(fake.spec[f"live_{role}_runtime"]), backend=role == "backend")
            write_env(output.parent / f"{role}-effective-env.nul", fake.environments[role])
            for raw in set(expected[role]["unit_files"]) | set(expected[role]["environment_file_paths"]):
                path = Path(raw)
                target = output.parent / "config" / path.relative_to("/")
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
        value["cache_sha256"] = sha(bundle.live)
        return value

    with PairedReleaseTransaction(state_dir=journal.parent, lock_path=Path(fake.spec["lock_path"]),
                                  manifest_sha256="0" * 64, driver=None)._locked():
        snapshot.snapshot_with_maintenance(
            journal_path=journal, machine_lock=Path(fake.spec["lock_path"]), live_cache=bundle.live,
            output_cache=output, build_id=fake.spec["old_build_id"],
            copy_cache=preparer._copy_cache_consistently, expected_pair=expected,
            observe_pair=lambda: copy.deepcopy(expected), recovery_spec=spec,
            hold_barrier=True, stopped_runtime_capture=captured,
        )
    saved = json.loads(journal.read_text())
    assert saved["state"] == "held"
    manifest = json.loads(bundle.manifest.read_text())
    manifest.update(snapshot_journal_path=str(journal), snapshot_journal_identity_sha256=saved["identity_sha256"])
    save(bundle.manifest, manifest)
    driver = paired.SingleVpsDriver(manifest)
    transaction = PairedReleaseTransaction(
        state_dir=driver.root, lock_path=driver.paths["lock_path"], manifest_sha256=sha(bundle.manifest),
        driver=driver, snapshot_journal_path=journal, snapshot_journal_identity_sha256=saved["identity_sha256"],
    )
    # Model the same existing root service context as FabricatedHost's access adapter.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(paired.os, "geteuid", lambda: 0)
        transaction.prepare()
    return fake, driver, transaction, journal


def test_paired_public_guards_forward_signed_source_and_captured_environment_context(tmp_path, monkeypatch):
    """The real receipt chain binds the shared source projector's caller inputs."""
    from scripts.deploy import rehearse_wavea_same_port as rehearsal
    from scripts.deploy.rehearse_wavea_pair import env_digest

    auth = candidate_auth()
    monkeypatch.setattr(sys.modules[__name__], "candidate_auth", lambda: {
        **auth, "BILUN_PUBLIC_BILLING_ENABLED": "true",
    })
    bundle = make_bundle(tmp_path, monkeypatch)
    fake = FabricatedHost(bundle, monkeypatch)
    driver = paired.SingleVpsDriver(json.loads(bundle.manifest.read_text()))
    before = {name: Path(driver.config[name]).read_bytes()
              for name in ("candidate_backend_environment", "candidate_frontend_environment")}
    projections, guards = [], []
    reports = [{"data_source": {"mode": "synthetic_demo", "is_synthetic": True}}] * 2

    def project(cache, **kwargs):
        projections.append((cache, kwargs))
        return None, None, None, reports, None, None

    def guard(environment, materialized, **context):
        assert materialized is reports
        assert "BILUN_DATA_MODE" not in environment and "SUT_DATA_MODE" not in environment
        assert env_digest(environment) == context["expected_environment_sha256"]
        guards.append((dict(environment), context))
        return True

    # Projection/source-resolver internals have separate real-source tests. Only
    # this boundary is substituted; original v1/v2 loaders and startup stay real.
    monkeypatch.setattr(rehearsal, "_cache_reports", project)
    monkeypatch.setattr(rehearsal, "_public_data_guard", guard)
    transaction = PairedReleaseTransaction(state_dir=driver.root, lock_path=driver.paths["lock_path"],
                                           manifest_sha256=sha(bundle.manifest), driver=driver)
    transaction.prepare()
    assert transaction.activate()["state"] == "active"
    final = json.loads((driver.root / "serving-launch-proof.json").read_text())
    candidate_receipt = json.loads(driver.candidate_receipt.read_text())
    observed = json.loads(Path(candidate_receipt["tuple_observation_path"]).read_text())
    assert any(cache == driver.candidate_db for cache, _ in projections)
    assert any(cache == driver.root / "serving.duckdb" for cache, _ in projections)
    for _, context in guards:
        assert context["repository"] == driver.backend
        assert context["expected_code_sha"] == driver.config["code_sha"]
        assert context["expected_runtime_sha256"] == observed["logical_tuple"]["backend_runtime_sha256"]
    assert guards[-1][0]["BILUN_WAVEA_ACTIVATION_RECEIPT"] == str(driver.root / "serving-receipt.json")
    assert guards[-1][0]["BILUN_WAVEA_ACTIVATION_KEY_FILE"] == str(driver.key)
    assert guards[-1][1]["expected_environment_sha256"] == final["effective_environment_sha256"]
    assert "fixture-candidate-secret" not in json.dumps(final)
    assert (driver.root / "serving-launch-proof.json").stat().st_mode & 0o777 == 0o600
    assert {name: Path(driver.config[name]).read_bytes() for name in before} == before
    assert wavea_activation.activation_for_build("candidate") is not None
    assert transaction.rollback()["state"] == "rolled_back"
    assert fake.loaded_route == OLD_CADDYFILE
    shutil.rmtree(tmp_path)


@pytest.mark.parametrize("setting", [
    "BILUN_PUBLIC_CHAT_BUDGET_DB", "BILUN_DATA_MODE", "BILUN_CLAIMS_DIR", "BILUN_CLEAN_DIR",
])
def test_paired_prepare_keeps_all_four_raw_persistent_settings_equal(bundle, monkeypatch, setting):
    fake = FabricatedHost(bundle, monkeypatch)
    fake.environments["backend"][setting] = "different-raw-setting"
    fake._write_processes()
    driver = paired.SingleVpsDriver(json.loads(bundle.manifest.read_text()))
    with pytest.raises(ValueError, match=f"Candidate changes persistent input/state setting: {setting}"):
        driver.prepare()
    assert not (driver.root / "prepared-pair.json").exists()
    assert fake.events == []
    assert bundle.live.read_bytes() == bundle.old_bytes


@pytest.mark.parametrize("field", [
    "code_sha", "backend_runtime_sha256", "effective_environment_sha256", "launch_config_sha256",
    "candidate_receipt_sha256", "serving_receipt_sha256", "tuple_observation_sha256",
    "candidate_environment_sha256", "missing",
])
def test_final_serving_launch_proof_drift_stops_before_replacement(host, field):
    fake, driver, transaction = host
    with transaction._locked():
        transaction._claim()
        driver.maintenance()
        driver.stop_pair()
        driver.snapshot()
        driver.derive_and_sign()
        path = driver.root / "serving-launch-proof.json"
        if field == "missing":
            path.unlink()
        else:
            value = json.loads(path.read_text())
            value[field] = {} if field == "candidate_environment_sha256" else "0" * 64
            save(path, value)
        with pytest.raises(ValueError, match="Final serving launcher environment proof|Release evidence"):
            driver.install_candidate()
    assert fake.bundle.live.read_bytes() == fake.bundle.old_bytes
    assert driver.paths["frontend_current"].resolve() == Path(fake.spec["live_frontend_runtime"])
    assert not driver.paths["backend_dropin"].exists()


def test_final_launcher_cannot_self_attest_an_extra_environment_setting(host, monkeypatch):
    from scripts.deploy import launch_wavea_candidate as launcher

    fake, driver, transaction = host
    original = launcher.candidate_command

    def changed(role, config):
        executable, argv, runtime, environment = original(role, config)
        if role == "backend":
            environment["SUT_DATA_MODE"] = "real_claims"
        return executable, argv, runtime, environment

    monkeypatch.setattr(launcher, "candidate_command", changed)
    with transaction._locked():
        transaction._claim()
        driver.maintenance()
        driver.stop_pair()
        driver.snapshot()
        with pytest.raises(ValueError, match="Final serving environment differs"):
            driver.derive_and_sign()
    assert not (driver.root / "serving-launch-proof.json").exists()
    assert fake.bundle.live.read_bytes() == fake.bundle.old_bytes


def test_real_prepare_driver_transaction_signature_startup_observer_and_rollback(host):
    fake, driver, transaction = host
    candidate_sha = sha(driver.candidate_db)
    assert transaction.activate()["state"] == "active"
    assert transaction.status()["live_readiness"] == "verified"
    activation = wavea_activation.activation_for_build("candidate")
    assert activation.cache_sha256 == sha(fake.bundle.live) != candidate_sha
    assert json.loads((driver.root / "serving-receipt.json").read_text())["serving_cache_sha256"] == sha(fake.bundle.live)
    for role in ("backend", "frontend"):
        config = json.loads((driver.root / "launch.json").read_text())
        cwd = candidate_command(role, config)[2]
        assert f"WorkingDirectory={cwd}\n" in driver.paths[f"{role}_dropin"].read_text()
        assert f"Environment=PYTHONPATH={driver.backend}\n" in driver.paths[f"{role}_dropin"].read_text()
        assert "PYTHONPATH" not in candidate_command(role, config)[3]
    resolved = subprocess.run([sys.executable, "-c", "import importlib.util; "
                               "print(importlib.util.find_spec('scripts.deploy.launch_wavea_candidate').origin)"],
                              cwd=driver.frontend, env={"PYTHONPATH": str(driver.backend), "PYTHONDONTWRITEBYTECODE": "1"},
                              check=True, capture_output=True, text=True).stdout.strip()
    assert resolved == str(driver.backend / "scripts/deploy/launch_wavea_candidate.py")
    with duckdb.connect(str(fake.bundle.live), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM build_meta").fetchone() == (16,)
        assert con.execute("SELECT * FROM custom.notes ORDER BY note").fetchall() == [
            (None, "unknown history"), ("candidate", "user state")]
        assert con.execute("SELECT * FROM build_pointer_scopes WHERE scope='research'").fetchone() == (
            "research", "history-2", "preserve")
    assert fake.events.index("route-loaded-barrier") < fake.events.index("stop-backend")
    assert fake.events.index("start-frontend") < fake.events.index("route-loaded-old")
    assert transaction.rollback()["state"] == "rolled_back"
    assert_old_restored(fake, driver, transaction)


def assert_old_restored(fake, driver, transaction):
    assert transaction.status()["state"] == "rolled_back"
    assert transaction.status()["live_readiness"] == "verified"
    assert fake.bundle.live.read_bytes() == fake.bundle.old_bytes
    assert fake.loaded_route == Path(fake.spec["caddy_config"]).read_bytes() == OLD_CADDYFILE
    assert all(fake.running.values())
    assert driver.paths["frontend_current"].resolve() == Path(fake.spec["live_frontend_runtime"])
    assert not driver.paths["backend_dropin"].exists()
    assert not driver.paths["frontend_dropin"].exists()


@pytest.mark.parametrize("kind", ["missing_journal", "missing_identity", "malformed_identity",
                                  "nonabsolute_journal", "unrelated_extra"])
def test_paired_snapshot_manifest_fields_are_strict_before_machine_actions(bundle, monkeypatch, kind):
    manifest = json.loads(bundle.manifest.read_text())
    manifest.update(snapshot_journal_path=str(bundle.root / "snapshot-maintenance/transaction.json"),
                    snapshot_journal_identity_sha256="1" * 64)
    if kind == "missing_journal":
        manifest.pop("snapshot_journal_path")
    elif kind == "missing_identity":
        manifest.pop("snapshot_journal_identity_sha256")
    elif kind == "malformed_identity":
        manifest["snapshot_journal_identity_sha256"] = "not-a-sha256"
    elif kind == "nonabsolute_journal":
        manifest["snapshot_journal_path"] = "snapshot-maintenance/transaction.json"
    else:
        manifest["operator_note"] = "unreviewed manifest field"
    events = list(bundle.events)
    before = {str(path): path.read_bytes() for path in (bundle.live, Path(bundle.spec["caddy_config"]),
                                                     bundle.manifest)}
    current = Path(bundle.spec["frontend_current"])
    pointer = os.readlink(current)

    def unexpected(*args):
        pytest.fail(f"Manifest validation must precede machine actions: {args}")

    monkeypatch.setattr(paired, "_run", unexpected)
    with pytest.raises(ValueError):
        paired.SingleVpsDriver(manifest)
    assert bundle.events == events
    assert {path: Path(path).read_bytes() for path in before} == before
    assert os.readlink(current) == pointer
    assert not list((bundle.root / "transaction").iterdir())
    assert not Path(bundle.spec["backend_dropin"]).exists()
    assert not Path(bundle.spec["frontend_dropin"]).exists()


def test_held_prepare_gate_and_activate_preserve_barrier_until_real_pair_ready(held_host):
    fake, driver, transaction, journal = held_host
    owner = json.loads(transaction.owner_path.read_text())
    saved = json.loads(journal.read_text())
    assert owner == {"manifest_sha256": saved["owner_identity_sha256"], "state_dir": str(journal.parent)}
    status = transaction.status()
    assert status["state"] == "prepared" and status["live_readiness"] == "not_checked"
    assert status["snapshot"]["state"] == "held"
    assert not any(fake.running.values())
    assert fake.loaded_route == Path(fake.spec["caddy_config"]).read_bytes() == (journal.parent / "barrier.caddy").read_bytes()
    before = list(fake.events)
    assert transaction.prepare()["state"] == "prepared"
    driver.activation_gate()
    assert fake.events == before
    assert transaction.activate()["state"] == "active"
    assert json.loads(transaction.owner_path.read_text()) == {
        "manifest_sha256": sha(fake.bundle.manifest), "state_dir": str(driver.root),
    }
    assert json.loads(journal.read_text())["state"] == "adopted"
    events = fake.events[len(before):]
    assert events.index("start-frontend") < events.index("route-loaded-old")
    assert transaction.rollback()["state"] == "rolled_back"
    assert_old_restored(fake, driver, transaction)


@pytest.mark.parametrize("interrupt", [None, "before", "after"])
def test_held_owner_adoption_is_atomic_and_interruption_replays_exact_handoff(held_host, monkeypatch, interrupt):
    fake, driver, transaction, journal = held_host
    original = snapshot.atomic_json
    old_owner = json.loads(transaction.owner_path.read_text())
    target = {"manifest_sha256": sha(fake.bundle.manifest), "state_dir": str(driver.root)}
    observed = []
    interrupted = False

    def written(path, value):
        nonlocal interrupted
        if path == transaction.owner_path and value == target:
            observed.append(json.loads(path.read_text()))
            if interrupt == "before" and not interrupted:
                interrupted = True
                raise KeyboardInterrupt("before owner CAS")
            original(path, value)
            observed.append(json.loads(path.read_text()))
            if interrupt == "after" and not interrupted:
                interrupted = True
                raise KeyboardInterrupt("after owner CAS")
        else:
            original(path, value)

    real_unlink = Path.unlink

    def unlinked(path, *args, **kwargs):
        assert path != transaction.owner_path, "Handoff must replace the exact owner without an absent interval"
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(snapshot, "atomic_json", written)
    monkeypatch.setattr(Path, "unlink", unlinked)
    if interrupt:
        with pytest.raises(KeyboardInterrupt, match="owner CAS"):
            transaction.activate()
        assert transaction.status()["state"] == "prepared"
        assert json.loads(journal.read_text())["state"] == "adopting"
        assert json.loads(transaction.owner_path.read_text()) == (old_owner if interrupt == "before" else target)
        assert not any(fake.running.values())
        driver = paired.SingleVpsDriver(json.loads(fake.bundle.manifest.read_text()))
        transaction = PairedReleaseTransaction(
            state_dir=driver.root, lock_path=driver.paths["lock_path"], manifest_sha256=sha(fake.bundle.manifest),
            driver=driver, snapshot_journal_path=journal,
            snapshot_journal_identity_sha256=json.loads(journal.read_text())["identity_sha256"],
        )
    assert transaction.activate()["state"] == "active"
    assert observed[0] == old_owner and observed[-1] == target
    assert all(owner in (old_owner, target) for owner in observed)
    assert json.loads(transaction.owner_path.read_text()) == target


@pytest.mark.parametrize("kind", ["missing", "foreign", "newer"])
def test_held_activation_refuses_lost_owner_without_any_machine_write(held_host, kind):
    fake, driver, transaction, journal = held_host
    if kind == "missing":
        transaction.owner_path.unlink()
    else:
        directory = driver.root / kind
        directory.mkdir(mode=0o700)
        save(directory / "transaction.json", {"state": "active" if kind == "newer" else "prepared"})
        save(transaction.owner_path, {"manifest_sha256": "f" * 64, "state_dir": str(directory)})
    paths = (fake.bundle.live, Path(fake.spec["caddy_config"]), transaction.journal_path, journal,
             driver.candidate_receipt, Path(driver.config["candidate_backend_environment"]))
    before = {str(path): path.read_bytes() for path in paths}
    before_owner = transaction.owner_path.read_bytes() if transaction.owner_path.exists() else None
    events = list(fake.events)
    for action in (transaction.activate, transaction.rollback, driver.stop_pair, driver.maintenance,
                   driver.start_pair, driver.restore_old, driver.restore_route):
        with pytest.raises((ValueError, PairedReleaseError, snapshot.SnapshotMaintenanceError)):
            action()
        assert fake.events == events
        assert {str(path): path.read_bytes() for path in paths} == before
        assert (transaction.owner_path.read_bytes() if transaction.owner_path.exists() else None) == before_owner
    assert fake.events == events
    assert {str(path): path.read_bytes() for path in paths} == before
    assert (transaction.owner_path.read_bytes() if transaction.owner_path.exists() else None) == before_owner
    assert not any(fake.running.values())
    assert driver.paths["frontend_current"].resolve() == Path(fake.spec["live_frontend_runtime"])
    assert not driver.paths["backend_dropin"].exists() and not driver.paths["frontend_dropin"].exists()


@pytest.mark.parametrize("kind", ["loaded", "installed", "sealed", "identity"])
def test_held_barrier_and_identity_drift_fail_closed_before_signing_or_handoff(held_host, kind):
    fake, driver, transaction, journal = held_host
    if kind == "loaded":
        fake.loaded_route = OLD_CADDYFILE
    elif kind == "installed":
        Path(fake.spec["caddy_config"]).write_bytes(OLD_CADDYFILE)
    elif kind == "sealed":
        (journal.parent / "barrier.caddy").write_bytes(b"foreign sealed maintenance bytes")
    else:
        manifest = json.loads(fake.bundle.manifest.read_text())
        manifest["snapshot_journal_identity_sha256"] = "0" * 64
        driver = paired.SingleVpsDriver(manifest)
        transaction = PairedReleaseTransaction(
            state_dir=driver.root, lock_path=driver.paths["lock_path"], manifest_sha256=sha(fake.bundle.manifest),
            driver=driver, snapshot_journal_path=journal, snapshot_journal_identity_sha256="0" * 64,
        )
    events = list(fake.events)
    before = {str(path): path.read_bytes() for path in (
        fake.bundle.live, transaction.journal_path, transaction.owner_path, journal, driver.candidate_receipt,
    )}
    with pytest.raises((ValueError, PairedReleaseError, snapshot.SnapshotMaintenanceError)):
        transaction.activate()
    assert fake.events == events
    assert {path: Path(path).read_bytes() for path in before} == before
    assert not (driver.root / "serving-receipt.json").exists()
    assert not (driver.root / "serving-launch-proof.json").exists()
    assert not any(fake.running.values())


def test_held_prepared_abort_restores_verified_old_pair_without_candidate_install(held_host):
    fake, driver, transaction, _ = held_host
    before = len(fake.events)
    assert transaction.rollback()["state"] == "rolled_back"
    assert_old_restored(fake, driver, transaction)
    assert "route-loaded-old" in fake.events[before:]
    assert fake.events[before:].index("start-frontend") < fake.events[before:].index("route-loaded-old")
    assert not (driver.root / "serving-receipt.json").exists()
    assert not (driver.root / "serving-launch-proof.json").exists()


@pytest.mark.parametrize("kind", ["unit", "environment", "foreign_loaded", "foreign_installed",
                                  "old_loaded", "old_installed"])
def test_adopted_prepared_abort_refuses_operator_context_drift_without_machine_actions(held_host, kind):
    fake, driver, transaction, journal = held_host
    with transaction._locked():
        transaction._claim()
    environment = fake.environment_files["backend"][0]
    caddy = Path(fake.spec["caddy_config"])
    if kind == "unit":
        fake.unit_files["backend"].write_text("operator changed existing service unit\n")
    elif kind == "environment":
        environment.write_text("FIXTURE_ENVIRONMENT=operator-change\n")
    elif kind.endswith("loaded"):
        fake.loaded_route = OLD_CADDYFILE if kind == "old_loaded" else b"unrelated operator loaded route"
    else:
        caddy.write_bytes(OLD_CADDYFILE if kind == "old_installed" else b"unrelated operator installed route")
    paths = (fake.bundle.live, caddy, fake.unit_files["backend"], environment,
             transaction.owner_path, transaction.journal_path, journal, driver.root / "old-backend-env.nul")
    before = {str(path): path.read_bytes() for path in paths}
    events, loaded, pointer = list(fake.events), fake.loaded_route, os.readlink(driver.paths["frontend_current"])
    for _ in range(2):
        with pytest.raises((ValueError, PairedReleaseError, snapshot.SnapshotMaintenanceError)):
            transaction.rollback()
        assert fake.events == events
        assert {str(path): path.read_bytes() for path in paths} == before
        assert fake.loaded_route == loaded
        assert os.readlink(driver.paths["frontend_current"]) == pointer
        assert not any(fake.running.values())
        assert not driver.paths["backend_dropin"].exists() and not driver.paths["frontend_dropin"].exists()
        assert not (driver.root / "serving-receipt.json").exists()
        assert not (driver.root / "serving-launch-proof.json").exists()


def test_another_release_cannot_claim_adopted_prepared_held_pair(held_host):
    fake, driver, transaction, journal = held_host
    with transaction._locked():
        transaction._claim()
    assert json.loads(journal.read_text())["state"] == "adopted"
    other_root = driver.root / "contender"
    other_root.mkdir(mode=0o700)
    contender = PairedReleaseTransaction(state_dir=other_root, lock_path=driver.paths["lock_path"],
                                        manifest_sha256="c" * 64, driver=None)
    events = list(fake.events)
    owner = transaction.owner_path.read_bytes()
    with contender._locked(), pytest.raises(PairedReleaseError, match="recovery"):
        contender._claim()
    assert transaction.owner_path.read_bytes() == owner
    assert fake.events == events
    assert not any(fake.running.values())
    assert transaction.status()["state"] == "prepared"


def test_held_interrupted_install_recovers_real_old_pair_with_recreated_transaction(held_host, monkeypatch):
    fake, driver, transaction, journal = held_host
    original = paired._replace_file
    interrupted = False

    def replaced(source, target, mode, **kwargs):
        nonlocal interrupted
        original(source, target, mode, **kwargs)
        if target == fake.bundle.live and not interrupted:
            interrupted = True
            raise KeyboardInterrupt("held candidate database installed")

    monkeypatch.setattr(paired, "_replace_file", replaced)
    with pytest.raises(KeyboardInterrupt, match="held candidate database"):
        transaction.activate()
    assert transaction.status()["state"] == "installing"
    assert not any(fake.running.values())
    assert fake.loaded_route == Path(fake.spec["caddy_config"]).read_bytes() == (driver.root / "barrier.caddy").read_bytes()
    driver = paired.SingleVpsDriver(json.loads(fake.bundle.manifest.read_text()))
    resumed = PairedReleaseTransaction(
        state_dir=driver.root, lock_path=driver.paths["lock_path"], manifest_sha256=sha(fake.bundle.manifest),
        driver=driver, snapshot_journal_path=journal,
        snapshot_journal_identity_sha256=json.loads(journal.read_text())["identity_sha256"],
    )
    assert resumed.activate()["state"] == "rolled_back"
    assert_old_restored(fake, driver, resumed)


def _old_frontend_probe_requests(fake, monkeypatch, *, image_preload=False, malicious_second_html=False):
    """Keep real discovery; an optimizer request is a forbidden disk-write trap."""
    requests, html_bodies = [], []
    original = fake.urlopen
    original_fetch = http._fetch
    image_url = "http://127.0.0.1:3000/_next/image?url=%2Fprobe.png&w=64&q=75"
    old_frontend = Path(fake.spec["live_frontend_runtime"])

    def content(url, body):
        requests.append(url)
        path = urlparse(url).path
        if path == "/login":
            repeated = sum(request == url for request in requests) > 1
            if image_preload or (malicious_second_html and repeated):
                body += f'<link rel="preload" as="image" href="{image_url}">'.encode()
            html_bodies.append(body)
        elif path == "/_next/image":
            cache = old_frontend / ".next/cache/images/probe/optimized.webp"
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(b"synthetic old image optimizer cache bytes")
        return body

    def fetched(request, **kwargs):
        response = original(request, **kwargs)
        body = content(request.full_url, response.read())
        response.read = lambda *args: body
        return response

    def fetched_http(base, path, cookie):
        status, body = original_fetch(base, path, cookie)
        if status == 200:
            body = content(base.rstrip("/") + path, body)
        return status, body

    monkeypatch.setattr(assets, "urlopen", fetched)
    monkeypatch.setattr(http, "_fetch", fetched_http)
    return requests, html_bodies


def _frontend_probe_inventory(frontend):
    return {path.relative_to(frontend).as_posix():
            ("link", os.readlink(path)) if path.is_symlink() else ("directory",) if path.is_dir()
            else ("file", sha(path)) for path in frontend.rglob("*")}


def test_old_readiness_probes_preserve_real_frontend_runtime(host, monkeypatch):
    fake, driver, _ = host
    frontend = Path(fake.spec["live_frontend_runtime"])
    before = _runtime_digest(frontend, backend=False)
    inventory = _frontend_probe_inventory(frontend)
    requests, _ = _old_frontend_probe_requests(fake, monkeypatch)
    driver.verify_pair(candidate=False, public=True)
    assert "http://127.0.0.1:3000/login" in requests
    assert {urlparse(url).path for url in requests if "/_next/static/" in url} == {
        f"/_next/static/{index}.js" for index in range(10)
    }
    assert _runtime_digest(frontend, backend=False) == before
    assert _frontend_probe_inventory(frontend) == inventory
    assert fake.events == []


def test_old_readiness_rejects_late_sorted_optimizer_url_before_any_asset_request(host, monkeypatch):
    fake, driver, _ = host
    frontend = Path(fake.spec["live_frontend_runtime"])
    before = _runtime_digest(frontend, backend=False)
    inventory = _frontend_probe_inventory(frontend)
    requests, html = _old_frontend_probe_requests(fake, monkeypatch, image_preload=True)
    with pytest.raises(ValueError):
        driver.verify_pair(candidate=False, public=False)
    discovered = assets.extract_assets_from_html(html[0].decode())
    assert discovered[:-1] == sorted(f"/_next/static/{index}.js" for index in range(10))
    assert discovered[-1] == "http://127.0.0.1:3000/_next/image?url=%2Fprobe.png&w=64&q=75"
    assert not any(urlparse(url).path.startswith("/_next/") for url in requests)
    assert not (frontend / ".next/cache/images").exists()
    assert _runtime_digest(frontend, backend=False) == before
    assert _frontend_probe_inventory(frontend) == inventory
    assert fake.events == []


def test_rollback_optimizer_preload_rejection_keeps_recovery_blocked_behind_503(host, monkeypatch):
    fake, driver, transaction = host
    assert transaction.activate()["state"] == "active"
    before_events = len(fake.events)
    frontend = Path(fake.spec["live_frontend_runtime"])
    digest, inventory = _runtime_digest(frontend, backend=False), _frontend_probe_inventory(frontend)
    requests, html = _old_frontend_probe_requests(fake, monkeypatch, image_preload=True)
    with pytest.raises(PairedReleaseError, match="Rollback blocked"):
        transaction.rollback()
    assert requests.count("http://127.0.0.1:3000/login") == 1 and len(html) == 1
    discovered = assets.extract_assets_from_html(html[0].decode())
    assert discovered[:-1] == sorted(f"/_next/static/{index}.js" for index in range(10))
    assert discovered[-1] == "http://127.0.0.1:3000/_next/image?url=%2Fprobe.png&w=64&q=75"
    assert not any(urlparse(url).path.startswith("/_next/") for url in requests)
    assert not (frontend / ".next/cache/images").exists()
    assert _runtime_digest(frontend, backend=False) == digest
    assert _frontend_probe_inventory(frontend) == inventory
    assert transaction.status()["state"] == "blocked"
    assert "route-loaded-old" not in fake.events[before_events:]
    assert fake.loaded_route == Path(fake.spec["caddy_config"]).read_bytes() == (
        driver.root / "barrier.caddy"
    ).read_bytes()
    for path in ("/health", "/login", "/api/patients"):
        assert fake.fetch("https://app.bilun.tech", path)[0] == 503
    retry_events = len(fake.events)
    with pytest.raises(PairedReleaseError, match="Rollback blocked"):
        transaction.rollback()
    assert "route-loaded-old" not in fake.events[retry_events:]
    assert transaction.status()["state"] == "blocked"


def test_old_readiness_uses_one_html_read_and_the_same_validated_static_urls(host, monkeypatch):
    fake, driver, _ = host
    frontend = Path(fake.spec["live_frontend_runtime"])
    digest, inventory = _runtime_digest(frontend, backend=False), _frontend_probe_inventory(frontend)
    requests, html = _old_frontend_probe_requests(fake, monkeypatch, malicious_second_html=True)
    driver.verify_pair(candidate=False, public=False)
    assert requests.count("http://127.0.0.1:3000/login") == 1
    assert len(html) == 1
    expected = {f"/_next/static/{index}.js" for index in range(10)}
    assert set(assets.extract_assets_from_html(html[0].decode())) == expected
    asset_urls = [url for url in requests if urlparse(url).path.startswith("/_next/")]
    assert sorted(asset_urls) == sorted("http://127.0.0.1:3000" + path for path in expected)
    assert not (frontend / ".next/cache/images").exists()
    assert _runtime_digest(frontend, backend=False) == digest
    assert _frontend_probe_inventory(frontend) == inventory
    assert fake.events == []


def test_real_rollback_probes_verify_unmarked_purpose_bound_old_sessions(host, monkeypatch):
    from src.bilun.api import auth
    from scripts.deploy.rehearse_wavea_pair import env_digest

    fake, driver, transaction = host
    original = fake._env_bytes(fake.old_environment), env_digest(fake.old_environment)
    fetch = fake.fetch
    verified = []

    def authenticated_fetch(base, path, cookie=None):
        if cookie and cookie.startswith("bilun:session="):
            values = fake.environments["backend"]
            with pytest.MonkeyPatch.context() as patch:
                for key, value in values.items():
                    patch.setenv(key, value)
                claims = auth.verify_session_token(cookie.split("=", 1)[1])
                assert claims and claims.username == values["BILUN_AUTH_USERNAME"]
            verified.append((fake.active_launch is None, path))
        return fetch(base, path, cookie)

    fake.fetch = authenticated_fetch
    monkeypatch.setattr(http, "_fetch", authenticated_fetch)
    assert transaction.activate()["state"] == "active"
    assert transaction.rollback()["state"] == "rolled_back"
    assert_old_restored(fake, driver, transaction)
    assert {old for old, _ in verified} == {False, True}
    assert (fake._env_bytes(fake.old_environment), env_digest(fake.old_environment)) == original
    assert (driver.root / "old-backend-env.nul").read_bytes() == original[0]


@pytest.mark.parametrize("point", ["route-installed-barrier", "route-loaded-barrier", "stop-backend",
                                   "stop-frontend", "start-backend", "start-frontend",
                                   "route-installed-old", "route-loaded-old"])
def test_partial_host_failures_restore_real_pair_and_closed_journal(host, point):
    fake, driver, transaction = host
    fake.fail_at = point
    with pytest.raises(PairedReleaseError, match="exact old pair restored"):
        transaction.activate()
    assert_old_restored(fake, driver, transaction)
    with pytest.raises(PairedReleaseError, match="closed"):
        transaction.activate()


@pytest.mark.parametrize("point", ["database", "backend_dropin", "frontend_dropin", "frontend_pointer"])
def test_recreated_driver_recovers_interrupted_real_swaps(host, monkeypatch, point):
    fake, driver, transaction = host
    original_file, original_link = paired._replace_file, paired._replace_link
    crashed = False

    def replaced(source, target, mode, **kwargs):
        nonlocal crashed
        original_file(source, target, mode, **kwargs)
        selected = driver.paths["live_cache_path"] if point == "database" else driver.paths.get(point)
        if not crashed and target == selected:
            crashed = True
            raise KeyboardInterrupt(point)

    def linked(*args):
        nonlocal crashed
        original_link(*args)
        if not crashed and point == "frontend_pointer":
            crashed = True
            raise KeyboardInterrupt(point)

    monkeypatch.setattr(paired, "_replace_file", replaced)
    monkeypatch.setattr(paired, "_replace_link", linked)
    with pytest.raises(KeyboardInterrupt, match=point):
        transaction.activate()
    assert json.loads(transaction.journal_path.read_text())["state"] == "installing"
    assert fake.loaded_route != OLD_CADDYFILE and not any(fake.running.values())
    driver = paired.SingleVpsDriver(json.loads(fake.bundle.manifest.read_text()))
    resumed = PairedReleaseTransaction(state_dir=driver.root, lock_path=driver.paths["lock_path"],
                                       manifest_sha256=sha(fake.bundle.manifest), driver=driver)
    assert resumed.activate()["state"] == "rolled_back"
    assert_old_restored(fake, driver, resumed)


@pytest.mark.parametrize("kind", ["dependency", "candidate_source", "roster_source", "candidate_environment", "ci"])
def test_handoff_drift_fails_before_any_maintenance_or_stops(host, monkeypatch, kind):
    fake, driver, transaction = host
    if kind == "dependency":
        (Path(fake.spec["dependency_roots"][0]) / "module.py").write_text("changed after preparation")
    elif kind == "candidate_source":
        (driver.backend / "code.py").write_text("changed source")
    elif kind == "roster_source":
        with (fake.bundle.root / "source-roster.json").open("ab") as stream:
            stream.write(b" ")
    elif kind == "candidate_environment":
        Path(driver.config["candidate_backend_environment"]).write_bytes(b"BILUN_SESSION_SECRET=changed\0")
    else:
        monkeypatch.setattr(paired, "fetch_successful_release_ci", lambda **kw: {"status": "stale"})
    with pytest.raises((ValueError, KeyError)):
        transaction.activate()
    assert fake.events == []
    assert json.loads(transaction.journal_path.read_text())["state"] == "prepared"
    assert fake.bundle.live.read_bytes() == fake.bundle.old_bytes


def test_external_ledger_can_evolve_through_real_transaction_without_reset(host):
    fake, _, transaction = host
    ledger = Path(fake.spec["external_state_paths"][0])
    identity = ledger.stat().st_ino
    ledger.write_bytes(b"new live records after preparation")
    transaction.activate()
    assert ledger.read_bytes() == b"new live records after preparation"
    assert ledger.stat().st_ino == identity
    transaction.rollback()
    assert ledger.read_bytes() == b"new live records after preparation"
    assert ledger.stat().st_ino == identity


@pytest.mark.parametrize("interrupt_after_wal_removal", [False, True])
def test_real_crash_wal_derives_commits_and_restores_exact_pair(host, monkeypatch, interrupt_after_wal_removal):
    fake, driver, transaction = host
    stop = driver.stop_pair
    original_unlink = Path.unlink
    saved = {}
    wal = Path(str(fake.bundle.live) + ".wal")

    def stopped():
        stop()
        if not saved:
            # A local artifact-producing subprocess exits without checkpointing.
            # It never launches a server or touches a real service/network.
            subprocess.run([sys.executable, "-c", "import duckdb,os,sys; "
                            "c=duckdb.connect(sys.argv[1]); c.execute(\"SET wal_autocheckpoint='1TB'\"); "
                            "c.execute(\"INSERT INTO annotations VALUES (2,'committed only in WAL')\"); "
                            "os._exit(0)", str(fake.bundle.live)], check=True, env=os.environ.copy())
            saved.update(database=fake.bundle.live.read_bytes(), wal=wal.read_bytes())

    def unlink(path, *args, **kwargs):
        original_unlink(path, *args, **kwargs)
        if path == wal and interrupt_after_wal_removal and not saved.get("interrupted"):
            saved["interrupted"] = True
            raise KeyboardInterrupt("after WAL removal")

    monkeypatch.setattr(driver, "stop_pair", stopped)
    monkeypatch.setattr(Path, "unlink", unlink)
    if interrupt_after_wal_removal:
        with pytest.raises(KeyboardInterrupt, match="WAL removal"):
            transaction.activate()
        assert not wal.exists()
        recovered_driver = paired.SingleVpsDriver(json.loads(fake.bundle.manifest.read_text()))
        transaction = PairedReleaseTransaction(state_dir=driver.root, lock_path=driver.paths["lock_path"],
                                               manifest_sha256=sha(fake.bundle.manifest), driver=recovered_driver)
        assert transaction.activate()["state"] == "rolled_back"
    else:
        assert transaction.activate()["state"] == "active"
        assert not wal.exists()
        with duckdb.connect(str(fake.bundle.live), read_only=True) as con:
            assert con.execute("SELECT note FROM annotations WHERE id=2").fetchone() == ("committed only in WAL",)
        assert transaction.rollback()["state"] == "rolled_back"
    assert fake.bundle.live.read_bytes() == saved["database"]
    assert wal.read_bytes() == saved["wal"]
    assert transaction.status()["live_readiness"] == "verified"


def test_second_real_release_preserves_first_then_rolls_back_to_first_with_same_key(host, tmp_path, monkeypatch):
    fake, first_driver, first = host
    assert first.activate()["state"] == "active"
    first_bytes = fake.bundle.live.read_bytes()
    key_bytes = first_driver.key.read_bytes()
    first_receipt = (first_driver.root / "serving-receipt.json").read_bytes()
    second_dir = tmp_path / "second-machine"
    second_dir.mkdir(mode=0o700)
    second_bundle = make_bundle(second_dir, monkeypatch, previous=host)
    second_driver = paired.SingleVpsDriver(json.loads(second_bundle.manifest.read_text()))
    second = PairedReleaseTransaction(state_dir=second_driver.root, lock_path=second_driver.paths["lock_path"],
                                      manifest_sha256=sha(second_bundle.manifest), driver=second_driver)
    assert second.prepare()["state"] == "prepared"
    assert second.activate()["state"] == "active"
    assert second.status()["live_readiness"] == "verified"
    assert first_driver.key.read_bytes() == key_bytes
    assert (first_driver.root / "serving-receipt.json").read_bytes() == first_receipt
    with duckdb.connect(str(fake.bundle.live), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM build_meta").fetchone() == (17,)
        assert con.execute("SELECT status FROM build_meta WHERE build_id='candidate'").fetchone() == ("superseded",)
        assert con.execute("SELECT status FROM build_meta WHERE build_id='candidate-next'").fetchone() == ("complete",)
        assert con.execute("SELECT note FROM custom.notes ORDER BY note").fetchall() == [("unknown history",), ("user state",)]
    before_stale = list(fake.events)
    with pytest.raises(PairedReleaseError, match="newer release"):
        first.rollback()
    assert fake.events == before_stale
    assert second.rollback()["state"] == "rolled_back"
    assert fake.bundle.live.read_bytes() == first_bytes
    assert second.status()["live_readiness"] == "verified"
    assert fake.working_dirs == {"backend": first_driver.backend, "frontend": first_driver.frontend}


@pytest.mark.parametrize("kind", ["foreign_configuration", "owned_dropin", "frontend_pointer", "database", "wal", "old_source"])
def test_active_rollback_refuses_foreign_state_before_taking_healthy_pair_offline(host, kind):
    fake, driver, transaction = host
    transaction.activate()
    if kind == "foreign_configuration":
        fake.unit_files["backend"].write_text("operator edited base unit")
    elif kind == "owned_dropin":
        driver.paths["backend_dropin"].write_text("operator edited owned dropin")
    elif kind == "frontend_pointer":
        other = driver.root / "other-front"
        other.mkdir()
        driver.paths["frontend_current"].unlink()
        driver.paths["frontend_current"].symlink_to(other)
    elif kind == "database":
        with duckdb.connect(str(fake.bundle.live)) as con:
            con.execute("UPDATE annotations SET note='new external change'")
    elif kind == "wal":
        Path(str(fake.bundle.live) + ".wal").write_bytes(b"new external WAL")
    else:
        (Path(fake.spec["live_backend_runtime"]) / "input.txt").write_text("old runtime changed since preparation")
    before = list(fake.events), fake.bundle.live.read_bytes()
    with pytest.raises(ValueError):
        transaction.rollback()
    assert fake.events == before[0]
    assert fake.bundle.live.read_bytes() == before[1]
    assert json.loads(transaction.journal_path.read_text())["state"] == "active"
    assert all(fake.running.values())


def test_rollback_retry_accepts_legitimate_old_wal_replay_checkpoint(host, monkeypatch):
    fake, driver, transaction = host
    original_stop, original_run = driver.stop_pair, fake.run
    archived = {}
    wal = Path(str(fake.bundle.live) + ".wal")
    failed = False

    def stop():
        original_stop()
        if not archived:
            subprocess.run([sys.executable, "-c", "import duckdb,os,sys; "
                            "c=duckdb.connect(sys.argv[1]); c.execute(\"SET wal_autocheckpoint='1TB'\"); "
                            "c.execute(\"INSERT INTO annotations VALUES (2,'legitimate pending commit')\"); "
                            "os._exit(0)", str(fake.bundle.live)], check=True, env=os.environ.copy())
            archived.update(database=fake.bundle.live.read_bytes(), wal=wal.read_bytes())

    def run(*args):
        nonlocal failed
        result = original_run(*args)
        if args[:2] == ("systemctl", "start") and fake.active_launch is None:
            # Model the existing writable old runtime replaying its restored WAL.
            with duckdb.connect(str(fake.bundle.live)) as con:
                con.execute("CHECKPOINT")
            if not failed:
                failed = True
                raise OSError("injected failure after legitimate old checkpoint")
        return result

    monkeypatch.setattr(driver, "stop_pair", stop)
    monkeypatch.setattr(paired, "_run", run)
    assert transaction.activate()["state"] == "active"
    with pytest.raises(PairedReleaseError, match="Rollback blocked"):
        transaction.rollback()
    assert json.loads(transaction.journal_path.read_text())["state"] == "blocked"
    assert not wal.exists()
    assert fake.bundle.live.read_bytes() != archived["database"]
    assert transaction.rollback()["state"] == "rolled_back"
    assert transaction.status()["live_readiness"] == "verified"
    assert (driver.root / "stopped.duckdb").read_bytes() == archived["database"]
    assert (driver.root / "stopped.duckdb.wal").read_bytes() == archived["wal"]
    with duckdb.connect(str(fake.bundle.live), read_only=True) as con:
        assert con.execute("SELECT note FROM annotations WHERE id=2").fetchone() == ("legitimate pending commit",)
        assert con.execute("SELECT count(*) FROM build_meta").fetchone() == (15,)
