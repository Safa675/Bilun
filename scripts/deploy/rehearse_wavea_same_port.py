"""Rehearse old, draft candidate, then recovered old on the same private ports.

Run only inside a fresh ``unshare -n`` network namespace, with independent
replay artifacts. No public route, host service or compiled frontend is edited.
The versioned output records real sequential observations, not blue/green ports.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import warnings
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from urllib.error import HTTPError
from urllib.request import Request

import duckdb

from scripts.deploy.candidate_environment import _environment as environment, candidate_environments
from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.probe_auth import old_probe_context
from scripts.deploy.http_release_probes import _fetch, _strict_json
from scripts.deploy.health_request import open_probe
from scripts.deploy.launch_wavea_candidate import SAME_PORT_PROFILE
from scripts.deploy.observe_candidate_tuple import (
    CandidateSpec, _canonical_digest, _loopback_listener_pid, _process_observation,
    _static_assets, _verify_frontend_api_rewrite, observe_candidate_tuple,
)
from scripts.deploy.rehearse_wavea_pair import (
    _CODE_SHA, argv_digest, cookie, env_digest, start,
    write_private_json,
)
from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _stable_file_hash
from scripts.deploy.verify_candidate_semantics import (
    _baseline_contract, _build_metadata, _legacy_report, _payload_rows,
)
from scripts.deploy.verify_same_input import (
    _CONFIG_KEYS, normalize_attested_data_source, verify_same_input_rosters,
)
from scripts.deploy.verify_frontend_assets import verify_entrypoint
from scripts.deploy.verify_public_assets import _SECRET_ENV, inspect_assets
from scripts.deploy.verify_public_billing_access import verify as verify_access
from src.bilun.domain.billing.wavea_full_evidence import FULL_EVIDENCE_SCHEMA_VERSION
from scripts.deploy.recover_old_pair import _distinct_roots, _independent_runtime_links

SCHEMA_VERSION = "wavea-same-port-rehearsal-v2"
SAME_PORT_ROUTE_SHA256 = _canonical_digest({
    "profile": SAME_PORT_PROFILE, "backend": "127.0.0.1:8001",
    "frontend": "127.0.0.1:3000",
})
_UNAVAILABLE = {
    "available": False, "unavailable_reason": "wavea_capability_unavailable",
    "total_rows": None, "rows": [], "has_more": False,
}
_HEALTH_TOKEN: ContextVar[str] = ContextVar("same_port_health_token", default="")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MODE_SOURCE_SHA256 = "e79be44cd1cee16cbc301fb2fb207af8e5bbba6aea948fa081a3b0509e983626"
_TRANSPORT_BINDINGS: dict[object, str] = {}


def _projection_source_files(repository: Path) -> set[str]:
    result = {path.relative_to(repository).as_posix() for prefix in ("src", "scripts/sut")
              for path in (repository / prefix).rglob("*.py")}
    if (repository / "scripts/__init__.py").is_file():
        result.add("scripts/__init__.py")
    return result


def _source_binding(repository: Path, code_sha: str, runtime_sha256: str | None = None) -> dict:
    """Compare exact source bytes to independently selected retained Git blobs.

    Snapshot runtimes intentionally have no .git. The reviewed operator's full
    retained Git history supplies their object authority, never the snapshot.
    """
    if (not isinstance(repository, Path) or not repository.is_absolute()
            or repository.resolve(strict=True) != repository or not repository.is_dir()
            or not isinstance(code_sha, str) or not _CODE_SHA.fullmatch(code_sha)):
        raise ValueError("Pinned report source identity is invalid")
    authority = repository if (repository / ".git").exists() else Path(__file__).resolve().parents[2]
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(authority),
        "ls-tree", "-r", "-z", code_sha, "--", "src", "scripts/sut", "scripts/__init__.py"],
        capture_output=True, check=False, timeout=30)
    if result.returncode:
        raise ValueError("Pinned report source requires retained Git objects")
    entries = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        relative = os.fsdecode(name)
        if not relative.endswith(".py"):
            continue
        mode, kind, blob = metadata.decode().split()
        if mode not in {"100644", "100755"} or kind != "blob" or relative in entries:
            raise ValueError("Pinned report source contains unsupported entries")
        entries[relative] = blob
    actual = _projection_source_files(repository)
    if not entries or actual != entries.keys():
        raise ValueError("Pinned report source closure has missing or extra files")
    digest = hashlib.sha256()
    for relative, blob in sorted(entries.items()):
        path = repository / relative
        if (path.resolve(strict=True) != path or not path.is_file()
                or path.stat().st_nlink != 1):
            raise ValueError("Pinned report source is not an independent canonical file")
        before = _stable_file_hash(path)
        raw = path.read_bytes()
        object_id = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if (object_id != blob or hashlib.sha256(raw).hexdigest() != before
                or _stable_file_hash(path) != before):
            raise ValueError("Pinned report source differs from retained Git bytes")
        digest.update(relative.encode() + b"\0" + before.encode() + b"\n")
    if runtime_sha256 is not None and (
        not isinstance(runtime_sha256, str) or not _HASH.fullmatch(runtime_sha256)
        or _runtime_digest(repository, backend=True) != runtime_sha256
    ):
        raise ValueError("Pinned report runtime differs from captured inventory")
    return {"repository": str(repository), "code_sha": code_sha,
            "source_sha256": digest.hexdigest(), "source_file_count": len(entries),
            "runtime_sha256": runtime_sha256}


@dataclass(frozen=True)
class PinnedReportTransport:
    """Independent source-generated DTOs, never expectations from observed HTTP."""

    _binding_json: str
    _raw_json: str = field(repr=False)
    _complete_json: str = field(repr=False)
    _draft_json: str = field(repr=False)
    _seal: object = field(default=None, repr=False, compare=False)

    def validate(self) -> None:
        if _TRANSPORT_BINDINGS.get(self._seal) != self._binding_json:
            raise ValueError("Report transport was not generated by pinned source")
        binding = json.loads(self._binding_json)
        for name in ("raw", "complete", "draft"):
            if hashlib.sha256(getattr(self, f"_{name}_json").encode()).hexdigest() != binding[f"{name}_sha256"]:
                raise ValueError("Report transport payload differs from source evidence")
        source = binding["source"]
        if _source_binding(Path(source["repository"]), source["code_sha"], source["runtime_sha256"]) != source:
            raise ValueError("Report transport source changed after projection")

    @property
    def code_sha(self) -> str:
        return json.loads(self._binding_json)["source"]["code_sha"]

    @property
    def contract(self) -> str:
        return json.loads(self._binding_json)["contract"]

    @property
    def raw_reports(self) -> dict[str, dict]:
        return json.loads(self._raw_json)

    @property
    def complete_reports(self) -> dict[str, dict]:
        return json.loads(self._complete_json)

    @property
    def draft_reports(self) -> dict[str, dict]:
        return json.loads(self._draft_json)

    @property
    def evidence(self) -> dict:
        return json.loads(self._binding_json)


_PROJECTION_WORKER = r'''
import ast, contextlib, dataclasses, importlib, io, json, os, sys, types
from pathlib import Path
sys.dont_write_bytecode = True
root = Path.cwd().resolve()
dependencies = tuple(Path(value).resolve() for value in json.loads(sys.argv[1]))
source_files = set(json.loads(sys.argv[2]))
def audit(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.__new__', 'socket.connect'}:
        raise ValueError('Report projection cannot start processes or connect')
    if event in {'os.mkdir', 'os.remove', 'os.rename', 'os.rmdir', 'os.link', 'os.symlink',
                 'os.chmod', 'os.chown', 'os.truncate', 'os.utime'}:
        raise ValueError('Report projection cannot mutate filesystem entries')
    if event != 'open':
        return
    name, mode, flags = args
    if not isinstance(name, (str, bytes, os.PathLike)):
        return
    path = Path(os.fsdecode(name)).resolve()
    if path.name == '.env' or path.name.startswith('.env.'):
        raise ValueError('Report projection cannot read environment files')
    if (isinstance(mode, str) and any(c in mode for c in 'wax+')
            or isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
        raise ValueError('Report projection cannot write files')
    if not path.exists():
        return  # Only failed fresh-prefix bytecode probes; no bytes can be read.
    if path.is_relative_to(root):
        if path.relative_to(root).as_posix() not in source_files:
            raise ValueError('Report projection read outside pinned source closure')
    elif not any(path == dep or path.is_relative_to(dep) for dep in dependencies):
        raise ValueError('Report projection read outside explicit dependency closure')
sys.addaudithook(audit)
payload = json.load(sys.stdin)
sys.path.insert(0, str(root))
sys.path.extend(str(path) for path in dependencies if path.is_dir())
# Avoid API app construction, route registration and state/log/.env imports.
for name in ('src', 'src.bilun', 'src.bilun.api', 'src.bilun.domain',
             'src.bilun.domain.billing'):
    package = types.ModuleType(name)
    package.__path__ = [str(root / name.replace('.', '/'))]
    package.__package__ = name
    sys.modules[name] = package
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from src.bilun.domain.billing.drug_indication_findings import normalize_drug_indication_payload
    from src.bilun.api.schemas import BillingReportResponse
    from src.bilun.domain.claims.provenance import attach_bilun_data_source_metadata
    tree = ast.parse((root / 'src/bilun/api/routes/billing.py').read_bytes())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == '_serialize_billing_report']
    if len(selected) != 1:
        raise ValueError('Pinned serializer function is absent or repeated')
    module = ast.Module(body=[ast.ImportFrom(module='__future__',
        names=[ast.alias(name='annotations')], level=0), *selected], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {'dataclasses': dataclasses,
                 'normalize_drug_indication_payload': normalize_drug_indication_payload}
    exec(compile(module, '<pinned billing serializer>', 'exec'), namespace)
    complete, draft = {}, {}
    unavailable = {'available': False, 'unavailable_reason': 'wavea_capability_unavailable',
                   'total_rows': None, 'rows': [], 'has_more': False}
    from src.bilun.domain.billing.wavea_evidence import original_five_report_payload
    for path, report in payload['reports'].items():
        serialized = namespace['_serialize_billing_report'](report)
        serialized = attach_bilun_data_source_metadata(serialized, payload['provenance'])
        complete[path] = BillingReportResponse.model_validate(serialized).model_dump(mode='json')
        gated = original_five_report_payload(serialized)
        gated.update(claim_reviews=dict(unavailable), claim_advisories=dict(unavailable),
                     financial_findings=dict(unavailable), wavea_coverage=None)
        draft[path] = BillingReportResponse.model_validate(gated).model_dump(mode='json')
    for name, module in tuple(sys.modules.items()):
        if (name == 'src' or name.startswith('src.') or name == 'bilun' or name.startswith('bilun.')
                or name == 'scripts' or name.startswith('scripts.')):
            file = getattr(module, '__file__', None)
            if file and Path(file).resolve().relative_to(root).as_posix() not in source_files:
                raise ValueError('Report projection imported unpinned source')
    if 'src.bilun.shared.state' in sys.modules or 'src.bilun.api.startup' in sys.modules:
        raise ValueError('Report projection imported runtime state or startup')
print(json.dumps({'complete': complete, 'draft': draft}, sort_keys=True,
                 ensure_ascii=False, separators=(',', ':'), allow_nan=False))
'''


def project_report_transport(raw_reports: dict[str, dict], provenance: dict, *, repository: Path,
                             expected_code_sha: str, python_executable: Path,
                             dependency_roots: tuple[Path, ...], cache_sha256: str,
                             build_id: str, contract: str,
                             expected_runtime_sha256: str | None = None) -> PinnedReportTransport:
    source = _source_binding(repository, expected_code_sha, expected_runtime_sha256)
    if (not isinstance(raw_reports, dict) or not raw_reports
            or any(not isinstance(path, str) or not isinstance(report, dict)
                   for path, report in raw_reports.items())
            or contract not in {"original-five", FULL_EVIDENCE_SCHEMA_VERSION}
            or not isinstance(cache_sha256, str) or not _HASH.fullmatch(cache_sha256)
            or not isinstance(build_id, str) or not build_id
            or not python_executable.is_absolute() or not python_executable.is_file()
            or not dependency_roots or any(not path.is_absolute() or not path.exists()
                                           for path in dependency_roots)):
        raise ValueError("Report projection lacks explicit source/cache/runtime identities")
    raw_json = json.dumps(raw_reports, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    source_files = sorted(_projection_source_files(repository))
    worker_env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC",
                  "PYTHONDONTWRITEBYTECODE": "1", "POLARS_MAX_THREADS": "1"}
    with tempfile.TemporaryDirectory(prefix="bilun-report-projection-") as directory:
        result = subprocess.run([str(python_executable), "-I", "-S", "-B", "-X",
            f"pycache_prefix={directory}/bytecode", "-c", _PROJECTION_WORKER,
            json.dumps([str(path) for path in dependency_roots]), json.dumps(source_files)],
            cwd=repository, env=worker_env,
            input=json.dumps({"reports": raw_reports, "provenance": provenance}, ensure_ascii=False, allow_nan=False).encode(),
            capture_output=True, check=False, timeout=120)
    if _source_binding(repository, expected_code_sha, expected_runtime_sha256) != source:
        raise ValueError("Report projection source changed during isolated serialization")
    if result.returncode:
        raise ValueError("Pinned isolated report serialization failed without accepting HTTP")
    projected = _strict_json(result.stdout)
    if (not isinstance(projected, dict) or set(projected) != {"complete", "draft"}
            or any(not isinstance(projected[name], dict) or projected[name].keys() != raw_reports.keys()
                   for name in ("complete", "draft"))):
        raise ValueError("Pinned report projection has an unknown ownership contract")
    complete_json, draft_json = (json.dumps(projected[name], sort_keys=True, ensure_ascii=False,
                separators=(",", ":"), allow_nan=False) for name in ("complete", "draft"))
    binding = {"source": source, "contract": contract, "cache_sha256": cache_sha256, "build_id": build_id,
               **{name + "_sha256": hashlib.sha256(value.encode()).hexdigest()
                  for name, value in (("raw", raw_json), ("complete", complete_json), ("draft", draft_json))}}
    # `python -m` defines this file as __main__; always return the canonical
    # module's type/seal so the separate clinical normalizer sees one identity.
    canonical = importlib.import_module("scripts.deploy.rehearse_wavea_same_port")
    binding_json = json.dumps(binding, sort_keys=True)
    seal = object()
    canonical._TRANSPORT_BINDINGS[seal] = binding_json
    return canonical.PinnedReportTransport(binding_json, raw_json, complete_json, draft_json, seal)


def fetch(port: int, path: str, session: str | None = None) -> tuple[int, bytes]:
    if path == "/health":
        token = _HEALTH_TOKEN.get()
        if token and len(token) < 32:
            raise ValueError("Private health token must contain at least 32 characters")
        request = Request(
            f"http://127.0.0.1:{port}/health",
            headers={"X-Bilun-Health-Token": token} if token else {},
        )
        try:
            with open_probe(request, timeout=15) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError("Same-port health response is too large")
                return response.status, raw
        except HTTPError as error:
            return error.code, error.read(65537)
    return _fetch(f"http://127.0.0.1:{port}", path, session)


def ready(port: int, path: str) -> None:
    import time

    for _ in range(150):
        try:
            if fetch(port, path)[0] == 200:
                return
        except OSError:
            pass
        time.sleep(.2)
    raise ValueError(f"Private same-port listener {port} did not become ready")


def _json(port: int, path: str, session: str | None = None) -> dict[str, Any]:
    status, raw = fetch(port, path, session)
    value = _strict_json(raw)
    if status != 200 or not isinstance(value, dict):
        raise ValueError(f"Same-port JSON probe failed: {port}{path}")
    return value


def _cache_reports(path: Path, *, candidate_only: bool = False,
                   repository: Path | None = None, expected_code_sha: str | None = None,
                   expected_runtime_sha256: str | None = None,
                   python_executable: Path | None = None, dependency_roots: tuple[Path, ...] = (),
                   transport_out: list[PinnedReportTransport] | None = None
                   ) -> tuple[str, str, str, dict[str, dict], int, int]:
    before = _candidate_db_hash(path)
    with duckdb.connect(str(path), read_only=True) as db:
        pointers = db.execute(
            "SELECT scope, active_build_id FROM build_pointer_scopes"
            + ("" if candidate_only else " WHERE scope = 'bilun'")
        ).fetchall()
        if (len(pointers) != 1 or pointers[0][0] != "bilun"
                or not isinstance(pointers[0][1], str) or not pointers[0][1]):
            raise ValueError("Rehearsal cache requires one Bilun active pointer")
        build = pointers[0][1]
        contract = _baseline_contract(db, build)
        metadata = db.execute(
            "SELECT source_hash FROM build_meta WHERE build_id = ? "
            "AND status = 'complete' AND build_scope = 'bilun'", [build],
        ).fetchall()
        if len(metadata) != 1:
            raise ValueError("Rehearsal cache active build is incomplete")
        patients = _payload_rows(db, "patient_billing_report_rows", build)
        bills = _payload_rows(db, "patient_bill_billing_report_rows", build)
        provenance = None
        if contract == FULL_EVIDENCE_SCHEMA_VERSION:
            from scripts.deploy.verify_candidate_semantics import _singleton
            if _build_metadata(db, build)["code_sha"] != expected_code_sha:
                raise ValueError("Report cache code differs from explicit pinned source")
            # Preserve the source API's exact first-present cohort priority;
            # own-source attachment/normalization executes only in the worker.
            for table in ("cohort_optimization_summary", "cohort_recovery_summary", "cohort_compliance_index"):
                payload = _singleton(db, table, build)
                if "data_source" in payload:
                    provenance = payload["data_source"]
                    break
    if _candidate_db_hash(path) != before:
        raise ValueError("Rehearsal cache changed during inventory")
    reports = {}
    for key, report in patients.items():
        reports[f"/api/billing-report/{quote(key, safe='')}"] = report
    for key, report in bills.items():
        patient, separator, claim = key.partition("::")
        if not separator or not claim or patient not in patients:
            raise ValueError("Rehearsal bill ownership is malformed")
        if contract == FULL_EVIDENCE_SCHEMA_VERSION:
            report = {**report, "patient_id": patient, "claim_id": claim, "scope": "bill"}
        reports[f"/api/billing-report/{quote(patient, safe='')}/bills/{quote(claim, safe='')}"] = report
    if repository is not None:
        transport = project_report_transport(reports, provenance, repository=repository,
            expected_code_sha=expected_code_sha, expected_runtime_sha256=expected_runtime_sha256,
            python_executable=python_executable, dependency_roots=dependency_roots,
            cache_sha256=before, build_id=build, contract=contract)
        if _candidate_db_hash(path) != before:
            raise ValueError("Report cache changed during source projection")
        if transport_out is not None:
            transport_out.append(transport)
        reports = transport.complete_reports
    elif contract == FULL_EVIDENCE_SCHEMA_VERSION:
        raise ValueError("Current report DTOs require an explicit pinned source projection")
    return build, metadata[0][0], contract, reports, len(patients), len(bills)


def _response_payload(report: dict, provenance: dict) -> dict:
    """Build the reviewed API DTO from pinned cache rows, never observed HTTP."""
    from src.bilun.api.routes.billing import _serialize_billing_report
    from src.bilun.api.routes.provenance import attach_bilun_data_source
    from src.bilun.api.schemas import BillingReportResponse

    return BillingReportResponse.model_validate(
        attach_bilun_data_source(_serialize_billing_report(report), provenance)
    ).model_dump(mode="json")


def _draft_payload(report: dict) -> dict:
    return {
        **_legacy_report(report), "claim_reviews": dict(_UNAVAILABLE),
        "claim_advisories": dict(_UNAVAILABLE), "financial_findings": dict(_UNAVAILABLE),
        "wavea_coverage": None,
    }


def _draft_report(report: dict) -> None:
    if (
        report.get("wavea_coverage", "missing") is not None
        or any(report.get(field) != _UNAVAILABLE for field in (
            "claim_reviews", "claim_advisories", "financial_findings",
        ))
        or "wavea_evidence_detail" in report
    ):
        raise ValueError("Draft API exposed an unknown or expanded Wave A contract")


def compare_reports(
    old: dict[str, dict], new: dict[str, dict], *, contract: str,
    old_capability: str | None, old_persisted: dict[str, dict],
    same_input: dict | None = None,
    clinical_transition: Any = None,
    old_transport: PinnedReportTransport | None = None,
    candidate_transport: PinnedReportTransport | None = None,
) -> None:
    """Compare observed DTOs without using API visibility as cache versioning.

    A current activated old pair may expose four extra blocks. Bind those
    exactly to its persisted report before comparing the original-five view.
    The separate mandatory semantic gate compares all unbounded persisted v2
    reports/evidence; this probe never substitutes HTTP visibility for that gate.
    """
    if old.keys() != new.keys() or old.keys() != old_persisted.keys():
        raise ValueError("All-patient/bill API inventory differs")
    if contract not in {"original-five", FULL_EVIDENCE_SCHEMA_VERSION}:
        raise ValueError("Unknown rehearsal baseline contract")
    transports = (old_transport, candidate_transport)
    if contract == FULL_EVIDENCE_SCHEMA_VERSION or any(value is not None for value in transports):
        transport_type = importlib.import_module("scripts.deploy.rehearse_wavea_same_port").PinnedReportTransport
        if any(not isinstance(value, transport_type) for value in transports):
            raise ValueError("Observed HTTP requires both independently pinned source transports")
        for transport in transports:
            transport.validate()
        if (_canonical_digest(old_persisted) != _canonical_digest(old_transport.complete_reports)
                or old.keys() != old_transport.raw_reports.keys()
                or new.keys() != candidate_transport.raw_reports.keys()):
            raise ValueError("HTTP cache inventory differs from pinned source transport")
        expected_old = old_transport.draft_reports if old_capability == "draft" else old_transport.complete_reports
        if (_canonical_digest(old) != _canonical_digest(expected_old)
                or _canonical_digest(new) != _canonical_digest(candidate_transport.draft_reports)):
            raise ValueError("Observed HTTP differs from its own source serializer and cache")
    old_comparable, new_comparable = {}, {}
    for path, before in old.items():
        after = new[path]
        _draft_report(after)
        if contract == FULL_EVIDENCE_SCHEMA_VERSION:
            if old_capability == "draft":
                _draft_report(before)
                left, right = before, after
            elif old_capability == "complete-25-v1":
                if _canonical_digest(before) != _canonical_digest(old_persisted[path]):
                    raise ValueError("Activated old API differs from persisted full-v2 report")
                left, right = _legacy_report(before), _legacy_report(after)
            else:
                raise ValueError("Current old API capability is unknown")
        else:
            left, right = _legacy_report(before), _legacy_report(after)
        old_comparable[path], new_comparable[path] = left, right
    if clinical_transition is not None:
        if contract != FULL_EVIDENCE_SCHEMA_VERSION:
            raise ValueError("Clinical transition requires complete current HTTP/cache ownership")
        from scripts.deploy.verify_source_refresh_transition import normalize_transition_http_reports
        view = "draft" if old_capability == "draft" else "legacy"
        old_comparable = normalize_transition_http_reports(old_comparable, side="baseline", proof=clinical_transition,
            transport=old_transport, baseline_transport=old_transport, view=view)
        new_comparable = normalize_transition_http_reports(new_comparable, side="candidate", proof=clinical_transition,
            transport=candidate_transport, baseline_transport=old_transport, view=view)
    for path, left in old_comparable.items():
        right = new_comparable[path]
        if same_input is not None:
            if same_input.get("status") != "same_input_bytes_verified":
                raise ValueError("HTTP comparison lacks independent same-input proof")
            left = normalize_attested_data_source(left, same_input["paths"]["baseline"])
            right = normalize_attested_data_source(right, same_input["paths"]["candidate"])
        if _canonical_digest(left) != _canonical_digest(right):
            raise ValueError("All-patient/bill API parity differs")


def _same_input_proof(old_db: Path, old_build: str, candidate_db: Path, candidate_build: str,
                      baseline_roster: Path, candidate_roster: Path,
                      baseline_build_config_environment: dict[str, str] | None = None) -> dict:
    with duckdb.connect(str(old_db), read_only=True) as db:
        old_meta = _build_metadata(db, old_build)
    with duckdb.connect(str(candidate_db), read_only=True) as db:
        new_meta = _build_metadata(db, candidate_build)
    return verify_same_input_rosters(
        baseline_roster, candidate_roster, baseline_meta=old_meta,
        candidate_meta=new_meta, build_config_environment=dict.fromkeys(_CONFIG_KEYS, ""),
        baseline_build_config_environment=baseline_build_config_environment,
    )


def _capture_reports(paths: dict[str, dict], session: str) -> dict[str, dict]:
    reports = {}
    for path in paths:
        backend = _json(8001, path, session)
        if _canonical_digest(backend) != _canonical_digest(_json(3000, path, session)):
            raise ValueError("Frontend/backend report pairing differs")
        reports[path] = backend
    return reports


def _public_data_guard(values: dict[str, str], reports: dict[str, dict], *,
                       repository: Path | None = None, expected_code_sha: str | None = None,
                       expected_runtime_sha256: str | None = None,
                       expected_environment_sha256: str | None = None) -> bool:
    if not isinstance(values, dict) or any(not isinstance(key, str) or not isinstance(value, str)
                                           for key, value in values.items()):
        raise ValueError("Public billing environment is malformed")
    public = values.get("BILUN_PUBLIC_BILLING_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    if not public:
        return False
    if (not isinstance(expected_environment_sha256, str) or not _HASH.fullmatch(expected_environment_sha256)
            or env_digest(values) != expected_environment_sha256
            or not isinstance(expected_runtime_sha256, str) or not _HASH.fullmatch(expected_runtime_sha256)):
        raise ValueError("Public billing lacks independently captured environment/runtime identity")
    source = _source_binding(repository, expected_code_sha, expected_runtime_sha256)
    config = repository / "src/bilun/domain/claims/config.py"
    raw = config.read_bytes()
    if hashlib.sha256(raw).hexdigest() != _MODE_SOURCE_SHA256:
        raise ValueError("Public billing has an unknown pinned data-mode resolver")
    tree = ast.parse(raw)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_resolve_mode"]
    if len(functions) != 1:
        raise ValueError("Public billing data-mode resolver is missing or repeated")
    primary, legacy = values.get("BILUN_DATA_MODE"), values.get("SUT_DATA_MODE")
    if primary is not None and legacy is not None and primary.strip() != legacy.strip():
        raise ValueError("Public billing has conflicting explicit data modes")
    namespace = {"warnings": warnings, "BILUN_DATA_MODE_ENV": "BILUN_DATA_MODE",
        "_SUT_DATA_MODE_ENV": "SUT_DATA_MODE", "SYNTHETIC_DEMO_MODE": "synthetic_demo",
        "VALID_SUT_DATA_MODES": frozenset({"synthetic_demo", "real_claims"}),
        "SUTDataSourceConfigError": ValueError}
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")],
                                            level=0), *functions], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, "<pinned data-mode resolver>", "exec"), namespace)
    if (namespace["_resolve_mode"](None, values) != "synthetic_demo"
            or not isinstance(reports, dict) or not reports or any(
            not isinstance(report, dict)
            or
            not isinstance(report.get("data_source"), dict)
            or report["data_source"].get("mode") != "synthetic_demo"
            or report["data_source"].get("is_synthetic") is not True
            for report in reports.values()
    )):
        raise ValueError("Public billing requires synthetic-only environment and every report")
    if (env_digest(values) != expected_environment_sha256
            or _source_binding(repository, expected_code_sha, expected_runtime_sha256) != source):
        raise ValueError("Public billing source/environment moved during provenance verification")
    return public


def _candidate_access(values: dict[str, str], session: str, reports: dict[str, dict], **source_context) -> int:
    public = _public_data_guard(values, reports, **source_context)

    def fetch_json(base: str, path: str, session: str | None):
        status, body = fetch(urlparse(base).port, path, session)
        return status, _strict_json(body) if status == 200 else None

    checks = 0
    for port in (8001, 3000):
        result = verify_access(
            f"http://127.0.0.1:{port}", session, public=public, fetch=fetch_json,
        )
        checks += len(result["checks"])
    return checks


def _old_identity(values: dict[str, str], session: str) -> None:
    for port in (8001, 3000):
        identity = _json(port, "/api/auth/me", session)
        if identity.get("authenticated") is not True or identity.get("username") != values["BILUN_AUTH_USERNAME"]:
            raise ValueError("Protected old probe session is not authenticated")


def _stop(children: list[subprocess.Popen]) -> None:
    for process in reversed(children):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for process in reversed(children):
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
    children.clear()


def _assert_ports_free() -> None:
    for port in (8001, 3000):
        result = subprocess.run(
            ["ss", "-H", "-ltn", f"sport = :{port}"],
            check=True, capture_output=True, text=True,
        )
        if result.stdout.strip():
            raise ValueError("Previous private pair still holds a same-port listener")


def _verify_assets(runtime: Path) -> int:
    from scripts.deploy.prepare_wavea_routes import _assets

    passed, observed = verify_entrypoint("http://127.0.0.1:3000/login", min_assets=10, verbose=False)
    if not passed:
        raise ValueError("Private frontend static assets are incomplete")
    for path, expected in _assets(runtime).items():
        status, body = fetch(3000, f"/_next/static/{path}")
        if status != 200 or hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("Private served frontend asset differs from artifact")
    return observed["assets_total"]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "work-dir", "old-snapshot", "old-replay", "candidate-backend-environment",
        "candidate-frontend-environment", "candidate-checkout", "candidate-db",
        "candidate-roster", "baseline-roster", "frontend-runtime", "backend-python",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--node", type=Path, default=Path("/usr/bin/node"))
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--old-backend-runtime-sha256", required=True)
    parser.add_argument("--old-environment-sha256", required=True)
    parser.add_argument("--candidate-environment-sha256", required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--baseline-build-config-environment", type=Path)
    parser.add_argument("--clinical-transition", type=Path)
    parser.add_argument("--dependency-root", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    if not _CODE_SHA.fullmatch(args.code_sha) or any(
        not value.is_absolute() or value.is_symlink()
        for value in vars(args).values() if isinstance(value, Path)
        and value not in (args.backend_python, args.node)
    ) or any(not path.is_file() or not path.is_absolute() for path in (args.backend_python, args.node)):
        raise ValueError("Same-port rehearsal paths or code SHA are invalid")
    if not args.work_dir.is_dir() or args.work_dir.stat().st_mode & 0o077 or list(args.work_dir.iterdir()):
        raise ValueError("Same-port rehearsal needs an empty 0700 work directory")
    if os.readlink("/proc/self/ns/net") == os.readlink("/proc/1/ns/net"):
        raise ValueError("Same-port rehearsal requires an isolated network namespace")
    producer_sha = _stable_file_hash(Path(__file__))
    if _stable_file_hash(args.candidate_checkout / "scripts/deploy/rehearse_wavea_same_port.py") != producer_sha:
        raise ValueError("Same-port rehearsal producer differs from candidate source")
    replay, frontend = args.old_replay, args.frontend_runtime
    _distinct_roots(args.old_snapshot, replay)
    _distinct_roots(replay, args.candidate_checkout)
    _distinct_roots(replay, frontend)
    for runtime in (replay / "backend", replay / "frontend"):
        _independent_runtime_links(
            runtime, allowed_external_file=(replay / "backend/.venv/bin/python").resolve()
            if runtime.name == "backend" else None,
        )
    old_probe_context(args.old_snapshot / "backend",
                      expected_runtime_sha256=args.old_backend_runtime_sha256)
    old_context = old_probe_context(replay / "backend",
                                    expected_runtime_sha256=args.old_backend_runtime_sha256)
    old_backend_runtime_sha = old_context.runtime_sha256
    old_frontend_runtime_sha = _runtime_digest(replay / "frontend", backend=False)
    old_cache_sha = _candidate_db_hash(replay / "cache.duckdb")
    candidate_cache_sha = _candidate_db_hash(args.candidate_db)
    baseline_source = _strict_json(args.baseline_roster.read_bytes())
    if not isinstance(baseline_source, dict) or not isinstance(baseline_source.get("code_sha"), str):
        raise ValueError("Old transport requires the independently pinned baseline source roster")
    old_code_sha = baseline_source["code_sha"]
    old_source = _source_binding(replay / "backend", old_code_sha, args.old_backend_runtime_sha256)
    candidate_runtime_sha = _runtime_digest(args.candidate_checkout, backend=True)
    old_transports, candidate_transports = [], []
    old_build, _, contract, old_persisted, patients, bills = _cache_reports(replay / "cache.duckdb",
        repository=Path(baseline_source["checkout"]), expected_code_sha=old_code_sha,
        python_executable=args.backend_python, dependency_roots=tuple(args.dependency_root),
        transport_out=old_transports)
    new_build, new_source, new_contract, new_persisted, new_patients, new_bills = _cache_reports(args.candidate_db,
        candidate_only=True, repository=args.candidate_checkout, expected_code_sha=args.code_sha,
        expected_runtime_sha256=candidate_runtime_sha, python_executable=args.backend_python,
        dependency_roots=tuple(args.dependency_root), transport_out=candidate_transports)
    if len(old_transports) != 1 or len(candidate_transports) != 1:
        raise ValueError("Same-port report transport generation is incomplete")
    old_transport, candidate_transport = old_transports[0], candidate_transports[0]
    if old_transport.evidence["source"]["source_sha256"] != old_source["source_sha256"]:
        raise ValueError("Old source serializer differs from independently captured replay runtime")
    if new_contract != FULL_EVIDENCE_SCHEMA_VERSION or old_persisted.keys() != new_persisted.keys():
        raise ValueError("Candidate cache contract or patient/bill inventory differs")
    if (patients, bills) != (new_patients, new_bills):
        raise ValueError("Candidate cache patient/bill counts differ")
    baseline_environment = None
    if args.baseline_build_config_environment is not None:
        from scripts.deploy.release_sidecar import _load_private_json
        baseline_environment, _ = _load_private_json(
            args.baseline_build_config_environment, root=args.baseline_build_config_environment.parent,
        )
    same_input = _same_input_proof(
        replay / "cache.duckdb", old_build, args.candidate_db, new_build,
        args.baseline_roster, args.candidate_roster,
        baseline_build_config_environment=baseline_environment,
    )
    same_input_sha = write_private_json(args.work_dir / "same-input-rehearsal.json", same_input)
    transition_proof = None
    transition_report_sha = None
    if args.clinical_transition is not None:
        from scripts.deploy.release_sidecar import _load_private_json
        from scripts.deploy.verify_source_refresh_transition import (
            validate_transition_request, verify_transition,
        )
        request, _ = _load_private_json(args.clinical_transition, root=args.clinical_transition.parent)
        request = validate_transition_request(request)
        if request["expected_candidate_sha"] != args.code_sha or request["expected_verifier_sha"] != args.code_sha:
            raise ValueError("Namespace transition identities must equal the exact candidate tooling head")
        with duckdb.connect(str(replay / "cache.duckdb"), read_only=True) as db:
            baseline_meta = _build_metadata(db, old_build)
        with duckdb.connect(str(args.candidate_db), read_only=True) as db:
            candidate_meta = _build_metadata(db, new_build)
        transition_proof = verify_transition(
            request=request,
            baseline_roster=args.baseline_roster, candidate_roster=args.candidate_roster,
            baseline_meta=baseline_meta, candidate_meta=candidate_meta, same_input=same_input,
            python_executable=args.backend_python, dependency_roots=tuple(args.dependency_root),
            expected_candidate_sha=request["expected_candidate_sha"],
            expected_verifier_sha=request["expected_verifier_sha"],
        )
        transition_report_sha = write_private_json(
            args.work_dir / "clinical-transition-rehearsal.json", transition_proof.report,
        )
    _verify_frontend_api_rewrite(replay / "frontend", 8001)
    _verify_frontend_api_rewrite(frontend, 8001)
    old_backend = environment(args.old_snapshot / "backend-effective-env.nul")
    old_frontend = environment(args.old_snapshot / "frontend-effective-env.nul")
    old_backend_env_sha, old_frontend_env_sha = env_digest(old_backend), env_digest(old_frontend)
    if old_backend_env_sha != args.old_environment_sha256:
        raise ValueError("Old protected environment differs from independent captured identity")
    old_backend.update(BILUN_CACHE_DB_PATH=str(replay / "cache.duckdb"), PYTHONDONTWRITEBYTECODE="1")
    old_frontend.update(PORT="3000", HOSTNAME="127.0.0.1")
    new_backend, new_frontend = candidate_environments(
        args.candidate_backend_environment, args.candidate_frontend_environment,
    )
    if env_digest(new_backend) != args.candidate_environment_sha256:
        raise ValueError("Candidate protected base environment differs from independent captured identity")
    roster_sha = _stable_file_hash(args.candidate_roster)
    new_backend.update(
        BILUN_CACHE_DB_PATH=str(args.candidate_db), BILUN_RELEASE_CODE_SHA=args.code_sha,
        BILUN_RELEASE_SOURCE_MANIFEST_SHA256=roster_sha,
        BILUN_STARTUP_POLICY="verified-load-only", PYTHONDONTWRITEBYTECODE="1",
    )
    new_frontend.update(PORT="3000", HOSTNAME="127.0.0.1", NODE_ENV="production",
                        API_PROXY_TARGET="http://127.0.0.1:8001", BILUN_RELEASE_CODE_SHA=args.code_sha)
    old_launch_environment_sha, candidate_launch_environment_sha = env_digest(old_backend), env_digest(new_backend)
    old_public_context = {"repository": replay / "backend", "expected_code_sha": old_code_sha,
        "expected_runtime_sha256": args.old_backend_runtime_sha256,
        "expected_environment_sha256": old_launch_environment_sha}
    candidate_public_context = {"repository": args.candidate_checkout, "expected_code_sha": args.code_sha,
        "expected_runtime_sha256": candidate_runtime_sha,
        "expected_environment_sha256": candidate_launch_environment_sha}
    for runtime, values in ((replay / "frontend", {**old_frontend, **old_backend}),
                            (frontend, {**new_frontend, **new_backend})):
        if inspect_assets(runtime, secrets=(values.get(key, "") for key in _SECRET_ENV))["ok"] is not True:
            raise ValueError("Rehearsal public assets contain private files or secrets")
    # Every path/identity/compiled target is checked before namespace commands.
    subprocess.run(["ip", "link", "set", "lo", "up"], check=True, capture_output=True)
    children: list[subprocess.Popen] = []
    old_session = cookie(old_backend, old_context=old_context)
    candidate_session = cookie(new_backend)
    backend_argv = [str(args.backend_python), "-m", "uvicorn", "src.bilun.api:app",
                    "--host", "127.0.0.1", "--port", "8001"]
    frontend_argv = [str(args.node), str(frontend / "server.js")]

    def old_start(label: str) -> None:
        _HEALTH_TOKEN.set(old_backend.get("BILUN_HEALTH_PROBE_TOKEN", ""))
        _assert_ports_free()
        children.append(start(
            [str(replay / "backend/.venv/bin/python"), "-m", "uvicorn", "src.bilun.api:app",
             "--host", "127.0.0.1", "--port", "8001"],
            replay / "backend", old_backend, label + "-backend", args.work_dir,
        ))
        children.append(start([str(args.node), str(replay / "frontend/server.js")],
                              replay / "frontend", old_frontend, label + "-frontend", args.work_dir))
        ready(8001, "/health")
        ready(3000, "/login")

    try:
        old_start("old")
        old_health = _json(8001, "/health")
        if old_health.get("active_build") != old_build:
            raise ValueError("Old rehearsal listener active build differs")
        _old_identity(old_backend, old_session)
        old_reports = _capture_reports(old_persisted, old_session)
        _public_data_guard(old_backend, old_reports, **old_public_context)
        old_capture_sha = write_private_json(args.work_dir / "old-api-capture.json", old_reports)
        old_assets = _verify_assets(replay / "frontend")
        _stop(children)
        _assert_ports_free()
        _HEALTH_TOKEN.set(new_backend.get("BILUN_HEALTH_PROBE_TOKEN", ""))
        children.append(start(backend_argv, args.candidate_checkout, new_backend, "candidate-backend", args.work_dir))
        children.append(start(frontend_argv, frontend, new_frontend, "candidate-frontend", args.work_dir))
        ready(8001, "/health")
        ready(3000, "/login")
        observed_frontend = _process_observation(3000, proc_root=Path("/proc"), listener_pid=_loopback_listener_pid)
        _, assets_sha = _static_assets(frontend)
        spec = CandidateSpec(
            code_sha=args.code_sha, source_manifest_sha256=roster_sha,
            cache_build_id=new_build, cache_source_hash=new_source, cache_path=args.candidate_db,
            cache_sha256=candidate_cache_sha, backend_runtime=args.candidate_checkout,
            backend_runtime_sha256=_runtime_digest(args.candidate_checkout, backend=True),
            backend_executable=args.backend_python.resolve(), backend_argv_sha256=argv_digest(backend_argv),
            backend_environment_sha256=env_digest(new_backend), frontend_runtime=frontend,
            frontend_runtime_sha256=_runtime_digest(frontend, backend=False),
            frontend_executable=args.node.resolve(), frontend_argv_sha256=observed_frontend["argv_sha256"],
            frontend_environment_sha256=env_digest(new_frontend),
            frontend_build_id=(frontend / ".next/BUILD_ID").read_text().strip(),
            frontend_assets_sha256=assets_sha, backend_port=8001, frontend_port=3000,
        )
        observation = observe_candidate_tuple(spec, fetch_health=lambda _url: _json(8001, "/health"))
        tuple_file_sha = write_private_json(args.work_dir / "candidate-tuple-observation.json", observation)
        new_reports = _capture_reports(new_persisted, candidate_session)
        if _canonical_digest(new_reports) != _canonical_digest(candidate_transport.draft_reports):
            raise ValueError("Candidate draft API differs from persisted full-v2 report")
        compare_reports(old_reports, new_reports, contract=contract,
                        old_capability=old_health.get("wavea_capability"), old_persisted=old_persisted,
                        same_input=same_input, clinical_transition=transition_proof,
                        old_transport=old_transport, candidate_transport=candidate_transport)
        access_checks = _candidate_access(new_backend, candidate_session, new_reports, **candidate_public_context)
        for path in ("/api/compliance-index", "/api/revenue-recovery", "/api/wavea-evidence-index"):
            if _canonical_digest(_json(8001, path, candidate_session)) != _canonical_digest(_json(3000, path, candidate_session)):
                raise ValueError("Candidate frontend/backend API pairing differs")
        if fetch(3000, f"/patient/{quote(args.patient_id, safe='')}", candidate_session)[0] != 200:
            raise ValueError("Candidate authenticated patient page is unavailable")
        candidate_assets = _verify_assets(frontend)
        if observe_candidate_tuple(spec, fetch_health=lambda _url: _json(8001, "/health"))["tuple_sha256"] != observation["tuple_sha256"]:
            raise ValueError("Candidate tuple changed during rehearsal")
        _stop(children)
        old_start("recovered-old")
        restored_session = cookie(old_backend, old_context=old_context)
        _old_identity(old_backend, restored_session)
        if _json(8001, "/health") != old_health or _capture_reports(old_persisted, restored_session) != old_reports:
            raise ValueError("Recovered old pair differs from initial captured pair")
        if _verify_assets(replay / "frontend") != old_assets:
            raise ValueError("Recovered old frontend assets differ")
        _stop(children)
        _assert_ports_free()
        if _candidate_db_hash(args.candidate_db) != candidate_cache_sha or _candidate_db_hash(replay / "cache.duckdb") != old_cache_sha:
            raise ValueError("Candidate or old replay cache changed during rehearsal")
        if (_runtime_digest(replay / "backend", backend=True) != old_backend_runtime_sha
                or _runtime_digest(replay / "frontend", backend=False) != old_frontend_runtime_sha):
            raise ValueError("Protected old runtime changed during rehearsal")
        backend_probe_sha = write_private_json(args.work_dir / "old-backend-probe.json", {
            "passed": True, "runtime_sha256": old_backend_runtime_sha,
            "cache_sha256": old_cache_sha, "active_build": old_build,
            "effective_environment_sha256": old_backend_env_sha,
            "private_url": "http://127.0.0.1:8001/health", "checks": ["health", "representative_api", "all_reports_recovered"],
        })
        frontend_probe_sha = write_private_json(args.work_dir / "old-frontend-probe.json", {
            "passed": True, "runtime_sha256": old_frontend_runtime_sha,
            "build_id": (replay / "frontend/.next/BUILD_ID").read_text().strip(),
            "effective_environment_sha256": old_frontend_env_sha,
            "private_url": "http://127.0.0.1:3000/login", "checks": ["login_assets"],
        })
        report = {
            "schema_version": SCHEMA_VERSION, "profile": SAME_PORT_PROFILE,
            "backend_port": 8001, "frontend_port": 3000,
            "passed": True, "network_namespace_isolated": True,
            "producer_script_sha256": producer_sha, "candidate_sha": args.code_sha,
            "candidate_cache_sha256": candidate_cache_sha,
            "candidate_frontend_build_id": spec.frontend_build_id,
            "old_pair_restored": True, "candidate_pair_routing_verified": True,
            "sequential_same_ports_verified": True, "compiled_proxy_verified": True,
            "authentication_verified": True, "public_real_data_guard_verified": True,
            "public_asset_guard_verified": True, "access_checks": access_checks,
            "baseline_contract": contract, "old_api_capture_sha256": old_capture_sha,
            "old_wavea_capability": old_health.get("wavea_capability"),
            "candidate_wavea_capability": "draft", "persisted_api_dtos_verified": True,
            "same_input_proof_sha256": same_input_sha,
            "candidate_tuple_sha256": observation["tuple_sha256"],
            "candidate_tuple_observation_sha256": tuple_file_sha,
            "old_frontend_probe_sha256": frontend_probe_sha, "old_backend_probe_sha256": backend_probe_sha,
            "api_paths_checked": patients + bills + 3,
            "legacy_api_patients_checked": patients, "legacy_api_bills_checked": bills,
            "old_assets_checked": old_assets, "candidate_assets_checked": candidate_assets,
            "old_route_sha256": SAME_PORT_ROUTE_SHA256, "candidate_route_sha256": SAME_PORT_ROUTE_SHA256,
            "public_activation_ready": False, "remaining_gate": "independent_signed_release_attestation",
        }
        if transition_proof is not None:
            report["clinical_transition_report_sha256"] = transition_report_sha
        old_transport.validate()
        candidate_transport.validate()
        if _source_binding(replay / "backend", old_code_sha, args.old_backend_runtime_sha256) != old_source:
            raise ValueError("Old replay source moved during transport verification")
        report["source_transport_evidence"] = {"baseline": old_transport.evidence,
                                                "candidate": candidate_transport.evidence}
        if _stable_file_hash(Path(__file__)) != producer_sha:
            raise ValueError("Same-port rehearsal producer changed during rehearsal")
        write_private_json(args.work_dir / "real-candidate-namespace-rehearsal.json", report)
        print("Sequential same-port candidate and old-pair recovery rehearsal passed")
    finally:
        try:
            _stop(children)
        finally:
            _HEALTH_TOKEN.set("")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"Same-port rehearsal failed closed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
