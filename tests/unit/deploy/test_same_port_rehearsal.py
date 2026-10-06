"""Fabricated same-port services: no namespace, listener or host mutation runs."""

from __future__ import annotations

import copy
import hashlib
import shutil
import json
import os
import py_compile
import runpy
import sys
import subprocess
import sysconfig
import tomllib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import duckdb

from scripts.deploy import rehearse_wavea_same_port as rehearsal
from scripts.deploy import probe_auth as probe
from scripts.deploy.launch_wavea_candidate import SAME_PORT_PROFILE, _CONFIG_PATHS, candidate_command
from scripts.deploy.observe_candidate_tuple import _canonical_digest
from scripts.deploy.verify_private_rehearsal import verify_private_rehearsal
from tests.unit.deploy.test_candidate_environment import candidate_auth, write_env
from tests.unit.deploy.probe_auth_fixtures import source_context, source_verifier
from tests.unit.deploy.test_prepare_single_vps_release import old_python_context, old_python_record


def private_json(path: Path, value: dict) -> str:
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    path.chmod(0o600)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frontend(path: Path, port: int = 8001) -> None:
    (path / ".next").mkdir(parents=True)
    (path / "server.js").write_text("fixture server")
    (path / ".next/BUILD_ID").write_text("fixture-front")
    private_json(path / ".next/routes-manifest.json", {"rewrites": {
        "beforeFiles": [], "afterFiles": [{"source": "/api/:path*",
        "destination": f"http://127.0.0.1:{port}/api/:path*"}], "fallback": [],
    }})


def launch_config(tmp_path: Path) -> dict:
    config = {key: str(tmp_path / key) for key in _CONFIG_PATHS}
    config.update(code_sha="a" * 40, profile=SAME_PORT_PROFILE,
                  backend_python=sys.executable, node=sys.executable)
    Path(config["backend_runtime"]).mkdir()
    frontend(Path(config["frontend_runtime"]))
    write_env(Path(config["candidate_backend_environment"]), candidate_auth())
    write_env(Path(config["candidate_frontend_environment"]), {"NODE_ENV": "production"})
    for key in ("cache_path", "source_roster_path", "activation_key_path"):
        Path(config[key]).write_text("fixture")
    private_json(Path(config["activation_receipt_path"]), {"schema_version": "wavea-serving-receipt-v2"})
    return config


def test_signed_same_port_launcher_pins_both_ports_without_rewriting_frontend(tmp_path):
    config = launch_config(tmp_path)
    manifest = Path(config["frontend_runtime"]) / ".next/routes-manifest.json"
    before = manifest.read_bytes()
    _, argv, _, backend = candidate_command("backend", config)
    _, _, _, values = candidate_command("frontend", config)
    assert argv[-4:] == ["--host", "127.0.0.1", "--port", "8001"]
    assert values["PORT"] == "3000"
    assert values["API_PROXY_TARGET"] == "http://127.0.0.1:8001"
    assert backend["BILUN_WAVEA_ACTIVATION_RECEIPT"] == config["activation_receipt_path"]
    assert manifest.read_bytes() == before


@pytest.mark.parametrize("fault", ["profile", "compiled_port", "receipt", "extra_port"])
def test_same_port_launcher_rejects_unknown_or_incoherent_profile(tmp_path, fault):
    config = launch_config(tmp_path)
    if fault == "profile":
        config["profile"] = "guess-the-ports"
    elif fault == "compiled_port":
        manifest = Path(config["frontend_runtime"]) / ".next/routes-manifest.json"
        manifest.write_text(manifest.read_text().replace(":8001/", ":8002/"))
    elif fault == "receipt":
        private_json(Path(config["activation_receipt_path"]), {"schema_version": "wavea-activation-v1"})
    else:
        config["backend_port"] = 8002
    for role in ("backend", "frontend"):
        with pytest.raises(ValueError):
            candidate_command(role, config)


def full_report():
    return {
        "patient_id": "P1", "total_recoverable_try": 12.34,
        "claim_compliance": {"findings": [], "evaluations": []},
        "claim_reviews": {"available": True, "total_rows": 0, "rows": [], "has_more": False},
        "claim_advisories": {"available": True, "total_rows": 0, "rows": [], "has_more": False},
        "financial_findings": {"available": True, "total_rows": 0, "rows": [], "has_more": False},
        "wavea_coverage": {"schema_version": "wavea-evidence-v2"},
        "data_source": {"mode": "synthetic_demo", "is_synthetic": True,
                        "claim_source": "claims", "clinical_source": "clean"},
    }


def fabricated_transport(monkeypatch, reports, *, code_sha="a" * 40, repository=Path("/fixture"), runtime=None):
    """Fabricated orchestration seam; real source workers are covered separately."""
    source = {"repository": str(repository), "code_sha": code_sha, "source_sha256": "c" * 64,
              "source_file_count": 1, "runtime_sha256": runtime}
    monkeypatch.setattr(rehearsal, "_source_binding", lambda root, sha, runtime=None: {
        **source, "repository": str(root), "code_sha": sha, "runtime_sha256": runtime})
    raw = json.dumps(reports, sort_keys=True)
    complete = raw
    draft = json.dumps({path: rehearsal._draft_payload(value) for path, value in reports.items()}, sort_keys=True)
    binding = json.dumps({"source": source, "contract": "wavea-evidence-v2", "cache_sha256": "d" * 64,
        "build_id": "fixture", **{name + "_sha256": hashlib.sha256(value.encode()).hexdigest()
        for name, value in (("raw", raw), ("complete", complete), ("draft", draft))}}, sort_keys=True)
    seal = object()
    rehearsal._TRANSPORT_BINDINGS[seal] = binding
    return rehearsal.PinnedReportTransport(binding, raw, complete, draft, seal)


@pytest.mark.parametrize("capability", ["draft", "complete-25-v1"])
def test_current_api_contract_supports_draft_and_repeat_activated_release(capability, monkeypatch):
    path = "/api/billing-report/P1"
    full = full_report()
    draft = rehearsal._draft_payload(full)
    before = full if capability == "complete-25-v1" else draft
    transport = fabricated_transport(monkeypatch, {path: full})
    rehearsal.compare_reports({path: before}, {path: draft}, contract="wavea-evidence-v2",
                              old_capability=capability, old_persisted={path: full},
                              old_transport=transport, candidate_transport=transport)
    assert full["claim_reviews"]["available"] is True


@pytest.mark.parametrize("fault", ["old_finance", "old_evidence", "new_finance", "new_gate", "new_unknown", "missing_bill", "old_capability"])
def test_current_api_comparison_never_hides_mutations(fault, monkeypatch):
    path = "/api/billing-report/P1"
    full = full_report()
    transport = fabricated_transport(monkeypatch, {path: full})
    old, new = {path: copy.deepcopy(full)}, {path: rehearsal._draft_payload(full)}
    capability = "complete-25-v1"
    if fault == "old_finance":
        old[path]["total_recoverable_try"] += 1
    elif fault == "old_evidence":
        old[path]["claim_reviews"]["total_rows"] = 1
    elif fault == "new_finance":
        new[path]["total_recoverable_try"] += 1
    elif fault == "new_gate":
        new[path]["claim_reviews"]["available"] = True
    elif fault == "new_unknown":
        new[path]["unknown_amount"] = 1
    elif fault == "missing_bill":
        new.clear()
    else:
        capability = "guess"
    with pytest.raises(ValueError):
        rehearsal.compare_reports(old, new, contract="wavea-evidence-v2",
                                  old_capability=capability, old_persisted={path: full},
                                  old_transport=transport, candidate_transport=transport)


def test_original_five_is_explicit_and_type_sensitive():
    path = "/api/billing-report/P1"
    before = {"patient_id": "P1", "exact": True}
    after = rehearsal._draft_payload(before)
    rehearsal.compare_reports({path: before}, {path: after}, contract="original-five",
                              old_capability=None, old_persisted={path: before})
    after["exact"] = 1
    with pytest.raises(ValueError, match="parity"):
        rehearsal.compare_reports({path: before}, {path: after}, contract="original-five",
                                  old_capability=None, old_persisted={path: before})


def test_expected_draft_dto_matches_real_api_serializer_and_gate():
    from src.bilun.api.routes.billing import _gate_wavea_evidence, _serialize_billing_report
    from src.bilun.api.routes.provenance import attach_bilun_data_source
    from src.bilun.api.schemas import BillingReportResponse

    raw = full_report()
    persisted_dto = rehearsal._response_payload(raw, raw["data_source"])
    gate = _gate_wavea_evidence(_serialize_billing_report(raw), None, "unsigned-fixture-build")
    actual_draft_dto = BillingReportResponse.model_validate(
        attach_bilun_data_source(gate, raw["data_source"])
    ).model_dump(mode="json")
    assert rehearsal._draft_payload(persisted_dto) == actual_draft_dto


def test_only_independently_attested_source_paths_can_differ(monkeypatch):
    path = "/api/billing-report/P1"
    before = full_report()
    after = copy.deepcopy(before)
    after["data_source"].update(claim_source="new-claims", clinical_source="new-clean")
    proof = {"status": "same_input_bytes_verified", "paths": {
        "baseline": {"claim_source": "claims", "clinical_source": "clean"},
        "candidate": {"claim_source": "new-claims", "clinical_source": "new-clean"},
    }}
    arguments = dict(contract="wavea-evidence-v2", old_capability="complete-25-v1",
                     old_persisted={path: before}, old_transport=fabricated_transport(monkeypatch, {path: before}),
                     candidate_transport=fabricated_transport(monkeypatch, {path: after}))
    rehearsal.compare_reports({path: before}, {path: rehearsal._draft_payload(after)}, same_input=proof, **arguments)
    with pytest.raises(ValueError, match="parity"):
        rehearsal.compare_reports({path: before}, {path: rehearsal._draft_payload(after)}, **arguments)
    after["data_source"]["claim_source"] = "unattested"
    arguments["candidate_transport"] = fabricated_transport(monkeypatch, {path: after})
    with pytest.raises(ValueError, match="attested input"):
        rehearsal.compare_reports({path: before}, {path: rehearsal._draft_payload(after)}, same_input=proof, **arguments)


@pytest.mark.parametrize("mode,synthetic", [("real_claims", False), ("synthetic_demo", False), ("unavailable", None)])
def test_public_guard_rejects_real_or_unproven_data_before_access_probes(mode, synthetic):
    report = full_report()
    report["data_source"] = {"mode": mode, "is_synthetic": synthetic}
    with pytest.raises(ValueError, match="identity"):
        rehearsal._public_data_guard({"BILUN_PUBLIC_BILLING_ENABLED": "true",
                                      "BILUN_DATA_MODE": "synthetic_demo"}, {"report": report})
    assert rehearsal._public_data_guard({"BILUN_PUBLIC_BILLING_ENABLED": "false"}, {"report": report}) is False


def fixture_git_commit(root):
    def git(*arguments, **kwargs):
        return subprocess.run(["git", "-C", str(root), *arguments], check=True,
                              capture_output=True, text=True, **kwargs).stdout.strip()
    if not (root / ".git").exists():
        subprocess.run(["git", "init", "-q", "--object-format=sha1", str(root)], check=True)
    git("add", "src")
    if (root / "scripts").is_dir():
        git("add", "scripts")
    tree = git("write-tree")
    env = {**os.environ, "GIT_AUTHOR_NAME": "Unit fixture", "GIT_COMMITTER_NAME": "Unit fixture",
           "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
    sha = git("commit-tree", tree, "-m", "Pinned public fixture", env=env)
    git("update-ref", "HEAD", sha)
    return sha


@pytest.fixture
def isolated_projection_source(tmp_path):
    """Copy the exact Git-bound Python closure, without editable-install metadata."""
    base = Path(rehearsal.__file__).resolve().parents[2]
    base_sha = subprocess.check_output(["git", "-C", str(base), "rev-parse", "HEAD"]).decode().strip()
    expected = rehearsal._source_binding(base, base_sha)
    source = tmp_path / "independent-public-source"
    for relative in sorted(rehearsal._projection_source_files(base)):
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base / relative, destination)
    code_sha = fixture_git_commit(source)
    actual = rehearsal._source_binding(source, code_sha)
    assert actual["source_sha256"] == expected["source_sha256"]
    assert actual["source_file_count"] == expected["source_file_count"]
    assert rehearsal._source_binding(base, base_sha) == expected
    return source, code_sha


@pytest.fixture
def known_mode_source(tmp_path):
    root = tmp_path / "source"
    file = root / "src/bilun/domain/claims/config.py"
    file.parent.mkdir(parents=True)
    file.write_bytes((Path(rehearsal.__file__).parents[2] / "src/bilun/domain/claims/config.py").read_bytes())
    return SimpleNamespace(root=root, config=file, sha=fixture_git_commit(root),
                           runtime=rehearsal._runtime_digest(root, backend=True))


def mode_context(source, values):
    return {"repository": source.root, "expected_code_sha": source.sha,
            "expected_runtime_sha256": source.runtime,
            "expected_environment_sha256": rehearsal.env_digest(values)}


@pytest.mark.parametrize("settings", [{}, {"BILUN_DATA_MODE": "synthetic_demo"},
    {"SUT_DATA_MODE": "synthetic_demo"},
    {"BILUN_DATA_MODE": "synthetic_demo", "SUT_DATA_MODE": "synthetic_demo"}])
def test_public_guard_uses_exact_known_source_effective_mode_without_rewriting_environment(known_mode_source, settings):
    values = {"BILUN_PUBLIC_BILLING_ENABLED": "true", **settings}
    before = copy.deepcopy(values)
    assert rehearsal._public_data_guard(values, {"patient": full_report(), "bill": full_report()},
                                         **mode_context(known_mode_source, values)) is True
    assert values == before


@pytest.mark.parametrize("settings", [{"BILUN_DATA_MODE": "real_claims"}, {"SUT_DATA_MODE": "real_claims"},
    {"BILUN_DATA_MODE": "unknown"}, {"SUT_DATA_MODE": "unknown"},
    {"BILUN_DATA_MODE": "synthetic_demo", "SUT_DATA_MODE": "real_claims"},
    {"BILUN_DATA_MODE": "real_claims", "SUT_DATA_MODE": "synthetic_demo"}])
def test_public_guard_rejects_real_unknown_and_conflicting_fallback(known_mode_source, settings):
    values = {"BILUN_PUBLIC_BILLING_ENABLED": "true", **settings}
    with pytest.raises(ValueError):
        rehearsal._public_data_guard(values, {"patient": full_report()}, **mode_context(known_mode_source, values))


@pytest.mark.parametrize("fault", ["empty", "missing", "non_object", "real_mode", "unknown_mode", "false", "null", "one"])
def test_public_guard_requires_every_report_strict_synthetic_provenance(known_mode_source, fault):
    values = {"BILUN_PUBLIC_BILLING_ENABLED": "true"}
    reports = {"patient": full_report(), "bill": full_report()}
    if fault == "empty":
        reports.clear()
    elif fault == "missing":
        reports["bill"].pop("data_source")
    elif fault == "non_object":
        reports["bill"]["data_source"] = None
    elif fault.endswith("mode"):
        reports["bill"]["data_source"]["mode"] = "real_claims" if fault == "real_mode" else "unknown"
    else:
        reports["bill"]["data_source"]["is_synthetic"] = {"false": False, "null": None, "one": 1}[fault]
    with pytest.raises(ValueError, match="synthetic-only"):
        rehearsal._public_data_guard(values, reports, **mode_context(known_mode_source, values))


@pytest.mark.parametrize("fault", ["environment", "runtime", "source_bytes", "source_identity", "extra_source", "unknown_resolver"])
def test_public_guard_rejects_stale_independent_identity_and_unknown_resolver(known_mode_source, fault):
    values = {"BILUN_PUBLIC_BILLING_ENABLED": "true"}
    context = mode_context(known_mode_source, values)
    if fault == "environment":
        values["PIPELINE_MODE"] = "changed-after-capture"
    elif fault == "runtime":
        (known_mode_source.root / "untracked-runtime").write_text("changed-after-capture")
    elif fault == "source_identity":
        context["expected_code_sha"] = "0" * 40
    elif fault == "extra_source":
        (known_mode_source.root / "src/extra.py").write_text("extra = True")
    else:
        known_mode_source.config.write_bytes(known_mode_source.config.read_bytes() + b"\n# changed source\n")
        if fault == "unknown_resolver":
            context.update(expected_code_sha=fixture_git_commit(known_mode_source.root),
                           expected_runtime_sha256=rehearsal._runtime_digest(known_mode_source.root, backend=True))
    with pytest.raises(ValueError):
        rehearsal._public_data_guard(values, {"patient": full_report()}, **context)


@pytest.mark.parametrize("flag", ["--old-environment-sha256", "--candidate-environment-sha256"])
def test_same_port_rejects_stale_captured_environment_before_start(tmp_path, monkeypatch, flag):
    arguments, _, events, _ = fixture_rehearsal(tmp_path, monkeypatch)
    arguments[arguments.index(flag) + 1] = "0" * 64
    message = ("identity differs from its frozen observation" if flag == "--old-environment-sha256"
               else "environment differs")
    with pytest.raises(ValueError, match=message):
        rehearsal.main(arguments)
    assert events == []


def test_transport_rejects_rehashed_self_consistent_package_mutation(monkeypatch):
    transport = fabricated_transport(monkeypatch, {"/api/billing-report/P1": full_report()})
    changed = transport.complete_reports
    changed["/api/billing-report/P1"]["total_recoverable_try"] = False
    encoded = json.dumps(changed, sort_keys=True)
    evidence = transport.evidence
    evidence["complete_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
    forged = replace(transport, _complete_json=encoded, _binding_json=json.dumps(evidence, sort_keys=True))
    with pytest.raises(ValueError, match="generated by pinned source"):
        forged.validate()


def test_actual_source_worker_keeps_existing_bytecode_and_runtime_untouched(isolated_projection_source, monkeypatch):
    repository, code_sha = isolated_projection_source
    # CI's editable install creates root egg-info. Fresh release source checkouts
    # do not contain it; never allow metadata reads through the source audit.
    schema = repository / "src/bilun/api/schemas.py"
    bytecode = schema.parent / "__pycache__" / f"schemas.{sys.implementation.cache_tag}.pyc"
    bytecode.parent.mkdir()
    py_compile.compile(str(schema), cfile=str(bytecode), doraise=True)
    bytecode_before = hashlib.sha256(bytecode.read_bytes()).hexdigest()
    before = rehearsal._source_binding(repository, code_sha)
    runtime_before = rehearsal._runtime_digest(repository, backend=True)
    provenance = {**full_report()["data_source"], "label": "Public synthetic fixture", "notice": "Fixture only"}
    original = subprocess.run
    observations = []

    def run(argv, **kwargs):
        worker = "-c" in argv and rehearsal._PROJECTION_WORKER in argv
        if worker:
            observations.append((argv, kwargs["env"]))
            assert "BILUN_AUTH_PASSWORD" not in kwargs["env"]
            assert "-I" in argv and "-S" in argv and "-B" in argv
            assert any(value.startswith("pycache_prefix=") for value in argv)
        result = original(argv, **kwargs)
        if worker:
            categories = [line for line in result.stderr.decode(errors="replace").splitlines()
                          if line.startswith(("ValueError: Report projection", "ModuleNotFoundError:",
                                              "ImportError:", "PermissionError:"))]
            assert result.returncode == 0, f"Public source worker exit {result.returncode}: {categories}"
        return result

    monkeypatch.setenv("BILUN_AUTH_PASSWORD", "public-unit-never-forwarded")
    monkeypatch.setattr(rehearsal.subprocess, "run", run)
    cli_namespace = runpy.run_path(rehearsal.__file__, run_name="source_projection_cli_fixture")
    assert cli_namespace["PinnedReportTransport"] is not rehearsal.PinnedReportTransport
    transport = cli_namespace["project_report_transport"]({"/api/billing-report/P1": full_report()}, provenance,
        repository=repository, expected_code_sha=code_sha, python_executable=Path(sys.executable),
        dependency_roots=(Path(sysconfig.get_path("stdlib")), Path(sysconfig.get_path("purelib"))),
        cache_sha256="a" * 64, build_id="public-unit", contract="wavea-evidence-v2",
        expected_runtime_sha256=runtime_before)
    transport.validate()
    assert observations
    assert type(transport) is rehearsal.PinnedReportTransport
    assert rehearsal._source_binding(repository, code_sha) == before
    assert rehearsal._runtime_digest(repository, backend=True) == runtime_before
    assert hashlib.sha256(bytecode.read_bytes()).hexdigest() == bytecode_before


def test_source_worker_rejects_editable_install_metadata(isolated_projection_source, monkeypatch):
    repository, code_sha = isolated_projection_source
    arguments = dict(repository=repository, expected_code_sha=code_sha, python_executable=Path(sys.executable),
        dependency_roots=(Path(sysconfig.get_path("stdlib")), Path(sysconfig.get_path("purelib"))),
        cache_sha256="a" * 64, build_id="public-unit", contract="wavea-evidence-v2")
    provenance = {**full_report()["data_source"], "label": "Public synthetic fixture", "notice": "Fixture only"}
    reports = {"/api/billing-report/P1": full_report()}
    rehearsal.project_report_transport(reports, provenance, **arguments).validate()
    before = rehearsal._source_binding(repository, code_sha)
    # Reproduce pip install -e '.[dev]' metadata using the real public entrypoints.
    project = Path(rehearsal.__file__).resolve().parents[2] / "pyproject.toml"
    entrypoints = tomllib.loads(project.read_text())["project"]["scripts"]
    metadata = repository / "bilun.egg-info" / "entry_points.txt"
    metadata.parent.mkdir()
    metadata.write_text("[console_scripts]\n" + "".join(
        name + " = " + value + "\n" for name, value in sorted(entrypoints.items())))
    metadata_before = hashlib.sha256(metadata.read_bytes()).hexdigest()
    original = subprocess.run
    failures = []

    def run(argv, **kwargs):
        result = original(argv, **kwargs)
        if rehearsal._PROJECTION_WORKER in argv:
            failures.append(result)
        return result

    monkeypatch.setattr(rehearsal.subprocess, "run", run)
    with pytest.raises(ValueError, match="Pinned isolated report serialization failed"):
        rehearsal.project_report_transport(reports, provenance, **arguments)
    assert len(failures) == 1 and failures[0].returncode != 0
    assert b"Report projection read outside pinned source closure" in failures[0].stderr
    assert rehearsal._source_binding(repository, code_sha) == before
    assert hashlib.sha256(metadata.read_bytes()).hexdigest() == metadata_before


@pytest.mark.parametrize("fault", ["environment_file", "filesystem_write", "source_change_after_worker"])
def test_source_worker_rejects_environment_side_effects_and_post_worker_source_drift(tmp_path, monkeypatch, fault):
    base = Path(rehearsal.__file__).resolve().parents[2]
    source = tmp_path / "independent-public-source"
    ignored = shutil.ignore_patterns("__pycache__", "*.pyc", ".env", ".env.*")
    shutil.copytree(base / "src", source / "src", ignore=ignored)
    shutil.copytree(base / "scripts/sut", source / "scripts/sut", ignore=ignored)
    shutil.copyfile(base / "scripts/__init__.py", source / "scripts/__init__.py")
    billing = source / "src/bilun/api/routes/billing.py"
    if fault != "source_change_after_worker":
        action = ('__import__("pathlib").Path(".env").read_text()' if fault == "environment_file"
                  else '__import__("pathlib").Path("worker-created").mkdir()')
        needle = "    if dataclasses.is_dataclass(report):"
        assert billing.read_text().count(needle) == 1
        billing.write_text(billing.read_text().replace(needle, "    " + action + "\n" + needle))
    if fault == "environment_file":
        (source / ".env").write_text("PUBLIC_UNIT_PLACEHOLDER=never_read")
    code_sha = fixture_git_commit(source)
    original = subprocess.run
    failures = []

    def run(argv, **kwargs):
        result = original(argv, **kwargs)
        if rehearsal._PROJECTION_WORKER in argv:
            failures.append(result.stderr.decode())
            if fault == "source_change_after_worker":
                assert result.returncode == 0
                config = source / "src/bilun/domain/claims/config.py"
                config.write_bytes(config.read_bytes() + b"\n# changed after projection\n")
        return result

    monkeypatch.setattr(rehearsal.subprocess, "run", run)
    provenance = {**full_report()["data_source"], "label": "Public synthetic fixture", "notice": "Fixture only"}
    with pytest.raises(ValueError):
        rehearsal.project_report_transport({"/api/billing-report/P1": full_report()}, provenance,
            repository=source, expected_code_sha=code_sha, python_executable=Path(sys.executable),
            dependency_roots=(Path(sysconfig.get_path("stdlib")), Path(sysconfig.get_path("purelib"))),
            cache_sha256="a" * 64, build_id="public-unit", contract="wavea-evidence-v2")
    assert failures
    if fault == "environment_file":
        assert "cannot read environment files" in failures[0]
    elif fault == "filesystem_write":
        assert "cannot mutate filesystem entries" in failures[0]
        assert not (source / "worker-created").exists()


def _old_scope_cache(path, pointers):
    with duckdb.connect(str(path)) as db:
        db.execute("CREATE TABLE build_pointer_scopes(scope VARCHAR, active_build_id VARCHAR)")
        if pointers:
            db.executemany("INSERT INTO build_pointer_scopes VALUES (?, ?)", pointers)
        db.execute("CREATE TABLE build_meta(build_id VARCHAR, source_hash VARCHAR, status VARCHAR, build_scope VARCHAR)")
        db.execute("INSERT INTO build_meta VALUES ('old-build', 'source', 'complete', 'bilun')")
        payload = json.dumps({"patient_id": "P1", "claim_compliance": {"findings": [], "evaluations": []}})
        for table, key in (("patient_billing_report_rows", "P1"), ("patient_bill_billing_report_rows", "P1::B1")):
            db.execute(f"CREATE TABLE {table}(build_id VARCHAR, patient_id VARCHAR, payload_json VARCHAR)")
            db.execute(f"INSERT INTO {table} VALUES ('old-build', ?, ?)", [key, payload])
            db.execute(f"INSERT INTO {table} VALUES ('historic-build', 'history-only', ?)", [payload])


def test_old_inventory_selects_bilun_and_preserves_other_scopes_and_history(tmp_path):
    path = tmp_path / "old.db"
    _old_scope_cache(path, [("bilun", "old-build"), ("other-scope", "other-build")])
    before = path.read_bytes()
    build, source, contract, reports, patients, bills = rehearsal._cache_reports(path)
    assert (build, source, contract, patients, bills) == ("old-build", "source", "original-five", 1, 1)
    assert set(reports) == {"/api/billing-report/P1", "/api/billing-report/P1/bills/B1"}
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="one Bilun active pointer"):
        rehearsal._cache_reports(path, candidate_only=True)


@pytest.mark.parametrize("pointers", [[], [("other", "old-build")], [("bilun", "missing")],
                                     [("bilun", "old-build"), ("bilun", "old-build")]])
def test_old_inventory_rejects_missing_wrong_or_duplicate_bilun_pointer(tmp_path, pointers):
    path = tmp_path / "old.db"
    _old_scope_cache(path, pointers)
    with pytest.raises(ValueError):
        rehearsal._cache_reports(path)


def test_candidate_access_checks_both_same_ports_using_candidate_session(monkeypatch):
    candidate_session = "bilun:session=candidate-fixture"
    calls = []

    def fetch(port, path, session=None):
        calls.append((port, path, session))
        valid = session == candidate_session
        if path == "/api/auth/me":
            value = {"authenticated": valid, "public_billing_enabled": False,
                     "capabilities": ["billing", "developer"] if valid else []}
            return 200, json.dumps(value).encode()
        return (200 if valid else 401), b"{}"

    monkeypatch.setattr(rehearsal, "fetch", fetch)
    assert rehearsal._candidate_access({}, candidate_session, {}) > 10
    assert {port for port, _, _ in calls} == {8001, 3000}
    assert (8001, "/api/rules", "bilun:role=dev") in calls
    with pytest.raises(ValueError, match="developer_identity"):
        rehearsal._candidate_access({}, "bilun:session=old-fixture", {})


def fixture_rehearsal(tmp_path, monkeypatch, *, old_capability="draft", failure=None):
    work, snapshot, replay, checkout, front = [tmp_path / name for name in (
        "work", "old-snapshot", "replay", "checkout", "frontend",
    )]
    work.mkdir(mode=0o700)
    snapshot.mkdir()
    (replay / "backend").mkdir(parents=True)
    old_context = source_context(replay / "backend")
    shutil.copytree(replay / "backend", snapshot / "backend")
    (checkout / "scripts/deploy").mkdir(parents=True)
    (checkout / "scripts/deploy/rehearse_wavea_same_port.py").write_bytes(Path(rehearsal.__file__).read_bytes())
    from scripts.deploy import prepare_single_vps_release as preparation
    (checkout / "scripts/deploy/prepare_single_vps_release.py").write_bytes(Path(preparation.__file__).read_bytes())
    frontend(replay / "frontend")
    frontend(front)
    (replay / "cache.duckdb").write_bytes(b"old-cache-fixture")
    cache, roster = tmp_path / "candidate.duckdb", tmp_path / "roster.json"
    cache.write_bytes(b"candidate-cache-fixture")
    roster.write_bytes(b"fixture-roster")
    baseline_roster = tmp_path / "baseline-roster.json"
    baseline_roster.write_text(json.dumps({"code_sha": "b" * 40, "checkout": str(snapshot / "backend")}))
    old = {**candidate_auth(), "BILUN_SESSION_SECRET": "old-fixture-secret",
           "BILUN_HEALTH_PROBE_TOKEN": "o" * 32}
    old.pop("BILUN_SESSION_TOKEN_PURPOSE")
    write_env(snapshot / "backend-effective-env.nul", old)
    old_python = old_python_context(tmp_path, environment_sha256=rehearsal.env_digest(old))
    old_record, old_record_sha = old_python_record(tmp_path, old_python,
                                                  runtime_sha256=old_context.runtime_sha256)
    write_env(snapshot / "frontend-effective-env.nul", {"NODE_ENV": "production"})
    new = {**candidate_auth(), "BILUN_HEALTH_PROBE_TOKEN": "n" * 32}
    backend_env = write_env(tmp_path / "candidate-backend.nul", new)
    frontend_env = write_env(tmp_path / "candidate-frontend.nul", {"NODE_ENV": "production"})
    full = {path: full_report() for path in ("/api/billing-report/P1", "/api/billing-report/P1/bills/B1")}
    fabricated_transport(monkeypatch, full)

    def cache_reports(path, **context):
        context["transport_out"].append(fabricated_transport(monkeypatch, full,
            code_sha=context["expected_code_sha"], repository=context["repository"],
            runtime=context.get("expected_runtime_sha256")))
        return ("old-build" if path.parent == replay else "candidate-build", "source",
                "wavea-evidence-v2", full, 1, 1)

    monkeypatch.setattr(rehearsal, "_cache_reports", cache_reports)
    monkeypatch.setattr(rehearsal, "_same_input_proof", lambda *_, **kwargs: {
        "status": "same_input_bytes_verified", "paths": {
            side: {"claim_source": "claims", "clinical_source": "clean"}
            for side in ("baseline", "candidate")
        },
    })
    real_readlink = os.readlink
    monkeypatch.setattr(rehearsal.os, "readlink", lambda path: (
        "private" if "self" in str(path) else "host"
    ) if str(path).startswith("/proc/") else real_readlink(path))
    monkeypatch.setattr(rehearsal.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout=""))
    monkeypatch.setattr(rehearsal, "ready", lambda *_: None)
    monkeypatch.setattr(rehearsal, "_runtime_digest", lambda root, **_k:
                        old_context.runtime_sha256 if root == replay / "backend" else "b" * 64)
    monkeypatch.setattr(rehearsal, "_static_assets", lambda *_: (10, "c" * 64))
    monkeypatch.setattr(rehearsal, "_verify_assets", lambda *_: 10)
    monkeypatch.setattr(rehearsal, "inspect_assets", lambda *_a, **_k: {"ok": True})
    monkeypatch.setattr(rehearsal, "_process_observation", lambda *_a, **_k: {"argv_sha256": "d" * 64})
    monkeypatch.setattr(rehearsal, "_candidate_access", lambda *_, **__: 20)
    events, processes, contexts = [], [], {}
    state = {"pair": None, "recovered": False}
    clock = SimpleNamespace(now=1000)
    monkeypatch.setattr(probe.time, "time", lambda: clock.now)

    class Process:
        def __init__(self, name):
            self.name, self.stopped = name, False
            self.pid = 10000 + len(processes)

        def terminate(self):
            events.append("stop:" + self.name)
            self.stopped = True

        def wait(self, **_):
            assert self.stopped

    def start(argv, cwd, values, name, _work):
        pair = "candidate" if name.startswith("candidate") else "old"
        state["recovered"] = name.startswith("recovered-old")
        if name == "recovered-old-backend":
            # Recovery must mint a fresh session after the initial one expires.
            clock.now = 1301
        if name.endswith("backend"):
            assert all(process.stopped for process in processes)
            assert argv[-1] == "8001"
            assert argv[0] == (sys.executable if pair == "candidate" else str(old_python.launcher))
            assert cwd == (checkout if pair == "candidate" else replay / "backend")
        assert values.get("PORT", "3000") == "3000"
        assert rehearsal._HEALTH_TOKEN.get() == ("n" * 32 if pair == "candidate" else "o" * 32)
        state["pair"] = pair
        events.append("start:" + name)
        contexts[name] = dict(values)
        process = Process(name)
        processes.append(process)
        return process

    monkeypatch.setattr(rehearsal, "start", start)
    monkeypatch.setattr(rehearsal.os, "killpg", lambda pid, _signal: next(
        process for process in processes if process.pid == pid
    ).terminate())
    old_cookie = rehearsal.cookie(old, old_context=old_context)
    candidate_cookie = rehearsal.cookie(new)
    recovered_old_cookie = probe.probe_cookie(old, old_context=old_context, now=1301)

    def fetch(port, path, session=None):
        assert port in (8001, 3000)
        pair = state["pair"]
        if path == "/health":
            return 200, json.dumps({"active_build": pair + "-build", "wavea_capability":
                                   "draft" if pair == "candidate" else old_capability}).encode()
        expected_old_cookie = recovered_old_cookie if state["recovered"] else old_cookie
        assert session == (candidate_cookie if pair == "candidate" else expected_old_cookie)
        if path == "/api/auth/me":
            return 200, json.dumps({"authenticated": True, "username": old["BILUN_AUTH_USERNAME"]}).encode()
        value = full.get(path, {})
        if path in full and (pair == "candidate" or old_capability == "draft"):
            value = rehearsal._draft_payload(value)
        if failure == "candidate_api" and pair == "candidate" and path in full:
            value = {**value, "total_recoverable_try": 777}
        return 200, json.dumps(value).encode()

    monkeypatch.setattr(rehearsal, "fetch", fetch)

    def observe(spec, **_):
        assert spec.backend_port == 8001 and spec.frontend_port == 3000
        assert spec.backend_environment_sha256 == rehearsal.env_digest(contexts["candidate-backend"])
        assert spec.frontend_environment_sha256 == rehearsal.env_digest(contexts["candidate-frontend"])
        return {"tuple_sha256": "e" * 64}

    monkeypatch.setattr(rehearsal, "observe_candidate_tuple", observe)
    args = ["--work-dir", str(work), "--old-snapshot", str(snapshot), "--old-replay", str(replay),
            "--old-backend-runtime-sha256", old_context.runtime_sha256,
            "--old-backend-python-identity-record", str(old_record),
            "--old-backend-python-identity-record-sha256", old_record_sha,
            "--old-environment-sha256", rehearsal.env_digest(old),
            "--candidate-environment-sha256", rehearsal.env_digest(new),
            "--candidate-backend-environment", str(backend_env), "--candidate-frontend-environment", str(frontend_env),
            "--candidate-checkout", str(checkout), "--candidate-db", str(cache), "--candidate-roster", str(roster),
            "--baseline-roster", str(baseline_roster),
            "--frontend-runtime", str(front), "--code-sha", "a" * 40, "--backend-python", sys.executable,
            "--node", sys.executable, "--patient-id", "P1"]
    for dependency in old_python.dependencies:
        args.extend(("--dependency-root", str(dependency)))
    return args, work, events, processes


@pytest.mark.parametrize("capability", ["draft", "complete-25-v1"])
def test_sequential_same_port_old_capture_candidate_and_recovery(tmp_path, monkeypatch, capability):
    args, work, events, processes = fixture_rehearsal(tmp_path, monkeypatch, old_capability=capability)
    rehearsal.main(args)
    assert events == [
        "start:old-backend", "start:old-frontend", "stop:old-frontend", "stop:old-backend",
        "start:candidate-backend", "start:candidate-frontend", "stop:candidate-frontend", "stop:candidate-backend",
        "start:recovered-old-backend", "start:recovered-old-frontend", "stop:recovered-old-frontend", "stop:recovered-old-backend",
    ]
    assert all(process.stopped for process in processes)
    report = json.loads((work / "real-candidate-namespace-rehearsal.json").read_text())
    assert report["schema_version"] == rehearsal.SCHEMA_VERSION
    assert report["old_wavea_capability"] == capability
    assert report["legacy_api_patients_checked"] == report["legacy_api_bills_checked"] == 1
    assert report["old_route_sha256"] == report["candidate_route_sha256"]
    assert len(json.loads((work / "old-api-capture.json").read_text())) == 2
    assert not (tmp_path / "replay/backend/.venv").exists()


@pytest.mark.parametrize("fault", ["candidate_identity", "environment_digest", "omitted_identity",
                                   "omitted_argument", "changed_context", "undeclared_link"])
def test_same_port_rejects_unproven_old_python_before_any_start(tmp_path, monkeypatch, fault):
    args, work, events, processes = fixture_rehearsal(tmp_path, monkeypatch)
    record = Path(args[args.index("--old-backend-python-identity-record") + 1])
    if fault == "omitted_argument":
        index = args.index("--old-backend-python-identity-record")
        del args[index:index + 2]
        error = SystemExit
    elif fault == "changed_context":
        (tmp_path / "old-python/pyvenv.cfg").write_text("home = /changed/python\n")
        error = ValueError
    elif fault == "undeclared_link":
        index = next(index for index, value in enumerate(args)
                     if value == "--dependency-root" and args[index + 1].endswith("/bin/python3"))
        del args[index:index + 2]
        error = ValueError
    else:
        value = json.loads(record.read_bytes())
        if fault == "omitted_identity":
            del value["backend"]["old_backend_python_identity"]
        elif fault == "environment_digest":
            value["backend"]["effective_environment_sha256"] = "0" * 64
        else:
            original = value["backend"]["old_backend_python_identity"]
            other = old_python_context(tmp_path, name="candidate-python",
                                       terminal=Path(original["executable_target"]),
                                       environment_sha256=original["effective_environment_sha256"])
            value["backend"]["old_backend_python_identity"] = other.identity
        digest = private_json(record, value)
        args[args.index("--old-backend-python-identity-record-sha256") + 1] = digest
        error = ValueError
    with pytest.raises(error):
        rehearsal.main(args)
    assert events == [] and processes == []
    assert not (work / "real-candidate-namespace-rehearsal.json").exists()


def test_same_port_revalidates_old_context_before_recovered_start(tmp_path, monkeypatch):
    args, work, events, processes = fixture_rehearsal(tmp_path, monkeypatch)
    start = rehearsal.start

    def mutate_after_candidate(argv, cwd, values, name, directory):
        process = start(argv, cwd, values, name, directory)
        if name == "candidate-frontend":
            (tmp_path / "old-python/lib/python3.13/site-packages/old_dependency.py").write_text(
                "CONTEXT = 'mutated while candidate rehearsed'\n"
            )
        return process

    monkeypatch.setattr(rehearsal, "start", mutate_after_candidate)
    with pytest.raises(ValueError):
        rehearsal.main(args)
    assert "start:old-backend" in events and "start:candidate-backend" in events
    assert "start:recovered-old-backend" not in events
    assert all(process.stopped for process in processes)
    assert not (work / "real-candidate-namespace-rehearsal.json").exists()


@pytest.mark.parametrize("alias", ["symlink", "hardlink"])
def test_verified_external_old_python_keeps_independent_runtime_alias_gate(tmp_path, monkeypatch, alias):
    args, _, events, processes = fixture_rehearsal(tmp_path, monkeypatch)
    external = tmp_path / "external-source.py"
    external.write_text("mutable source outside replay\n")
    path = tmp_path / "replay/backend/aliased-source.py"
    if alias == "symlink":
        path.symlink_to(external)
    else:
        os.link(external, path)
    with pytest.raises(ValueError, match="external source|hardlinked"):
        rehearsal.main(args)
    assert events == [] and processes == []


def test_recovered_old_session_is_reminted_with_same_verified_context(tmp_path, monkeypatch):
    args, _, _, _ = fixture_rehearsal(tmp_path, monkeypatch)
    mint = rehearsal.cookie
    contexts = []
    sessions = []

    def record(values, *, old_context=None):
        contexts.append(old_context)
        session = mint(values, old_context=old_context)
        sessions.append((dict(values), session.split("=", 1)[1]))
        return session

    monkeypatch.setattr(rehearsal, "cookie", record)
    rehearsal.main(args)
    assert len(contexts) == 3
    assert contexts[0] is contexts[2]
    assert contexts[0].purpose == "bilun-developer-v1"
    assert contexts[1] is None
    old_values, initial_token = sessions[0]
    _, recovered_token = sessions[2]
    assert initial_token != recovered_token
    assert "BILUN_SESSION_TOKEN_PURPOSE" not in old_values
    for key, value in old_values.items():
        monkeypatch.setenv(key, value)
    module = source_verifier(monkeypatch)
    with monkeypatch.context() as initial_clock:
        initial_clock.setattr(probe.time, "time", lambda: 1000)
        assert module.verify_session_token(initial_token) == module.TokenClaims(
            old_values["BILUN_AUTH_USERNAME"], 1300,
        )
        assert module.issue_session_token(old_values["BILUN_AUTH_USERNAME"], ttl_seconds=300) == initial_token
    assert module.verify_session_token(initial_token) is None
    assert module.verify_session_token(recovered_token) == module.TokenClaims(
        old_values["BILUN_AUTH_USERNAME"], 1601,
    )
    assert module.issue_session_token(old_values["BILUN_AUTH_USERNAME"], ttl_seconds=300) == recovered_token
    with monkeypatch.context() as wrong_purpose:
        wrong_purpose.setattr(module, "SESSION_PURPOSE", "wrong-purpose")
        wrong_token = module.issue_session_token(old_values["BILUN_AUTH_USERNAME"], ttl_seconds=300)
    assert module.verify_session_token(wrong_token) is None
    payload, signature = recovered_token.split(".")
    tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    assert module.verify_session_token(payload + "." + tampered_signature) is None
    with monkeypatch.context() as candidate_secret:
        candidate_secret.setenv("BILUN_SESSION_SECRET", sessions[1][0]["BILUN_SESSION_SECRET"])
        assert module.verify_session_token(recovered_token) is None
    with monkeypatch.context() as expired_clock:
        expired_clock.setattr(probe.time, "time", lambda: 1602)
        assert module.verify_session_token(recovered_token) is None


def test_failed_candidate_stops_children_and_never_emits_pass(tmp_path, monkeypatch):
    args, work, _, processes = fixture_rehearsal(tmp_path, monkeypatch, failure="candidate_api")
    with pytest.raises(ValueError, match="differs from persisted"):
        rehearsal.main(args)
    assert all(process.stopped for process in processes)
    assert not (work / "real-candidate-namespace-rehearsal.json").exists()


def test_rehearsal_forwards_explicit_nonempty_baseline_build_environment(tmp_path, monkeypatch):
    args, work, _, _ = fixture_rehearsal(tmp_path, monkeypatch)
    values = dict.fromkeys(rehearsal._CONFIG_KEYS, "")
    values.update(BILUN_DATA_MODE="synthetic_demo", BILUN_CLAIMS_DIR="/retained/claims",
                  BILUN_CLEAN_DIR="/retained/clean")
    path = tmp_path / "baseline-config.json"
    private_json(path, values)
    old = rehearsal._same_input_proof
    received = []

    def proof(*args, **kwargs):
        received.append(kwargs["baseline_build_config_environment"])
        return old(*args, **kwargs)

    monkeypatch.setattr(rehearsal, "_same_input_proof", proof)
    rehearsal.main([*args, "--baseline-build-config-environment", str(path)])
    assert received == [values]
    assert (work / "real-candidate-namespace-rehearsal.json").is_file()


def test_rehearsal_rejects_host_namespace_before_any_command(tmp_path, monkeypatch):
    args, work, _, _ = fixture_rehearsal(tmp_path, monkeypatch)
    monkeypatch.setattr(rehearsal.os, "readlink", lambda *_: "host")
    monkeypatch.setattr(rehearsal.subprocess, "run", lambda *_a, **_k: pytest.fail("host command executed"))
    with pytest.raises(ValueError, match="isolated network namespace"):
        rehearsal.main(args)
    assert not list(work.iterdir())


def sealed_rehearsal(tmp_path: Path, *, same_port=True):
    candidate = {"code_sha": "a" * 40, "backend_runtime_sha256": "b" * 64,
                 "frontend_runtime_sha256": "c" * 64, "frontend_build_id": "front",
                 "frontend_assets_sha256": "d" * 64, "build_id": "build", "cache_sha256": "e" * 64,
                 "source_hash": "source", "source_roster_sha256": "f" * 64,
                 "patient_count": 1, "bill_count": 1}
    runtime = tmp_path / "backend"
    producer = runtime / "scripts/deploy" / ("rehearse_wavea_same_port.py" if same_port else "rehearse_wavea_pair.py")
    producer.parent.mkdir(parents=True)
    producer.write_text("sealed producer fixture")
    ports = (8001, 3000) if same_port else (8002, 3099)
    logical = {key: candidate[key] for key in ("backend_runtime_sha256", "frontend_runtime_sha256",
                                             "frontend_build_id", "frontend_assets_sha256")}
    logical.update(backend={"port": ports[0]}, frontend={"port": ports[1]},
                   cache={"build_id": "build", "sha256": candidate["cache_sha256"], "source_hash": "source",
                          "patient_count": 1, "bill_count": 1, "evidence_capability": "draft"},
                   health={"active_build": "build", "code_sha": candidate["code_sha"],
                           "source_manifest_sha256": candidate["source_roster_sha256"], "wavea_capability": "draft",
                           "cache_ready": True, "status": "ok"})
    observation = {"status": "candidate_tuple_observed", "activation_ready": False, "logical_tuple": logical,
                   "tuple_sha256": _canonical_digest(logical), "backend_listener": {"port": ports[0]},
                   "frontend_listener": {"port": ports[1]}}
    tuple_path = tmp_path / "tuple.json"
    report = {"schema_version": rehearsal.SCHEMA_VERSION if same_port else "wavea-real-pair-rehearsal-v1",
              "passed": True, "network_namespace_isolated": True,
              "producer_script_sha256": hashlib.sha256(producer.read_bytes()).hexdigest(),
              "public_activation_ready": False, "candidate_pair_routing_verified": True, "old_pair_restored": True,
              "candidate_sha": candidate["code_sha"], "candidate_cache_sha256": candidate["cache_sha256"],
              "candidate_frontend_build_id": "front", "candidate_tuple_sha256": observation["tuple_sha256"],
              "candidate_tuple_observation_sha256": private_json(tuple_path, observation),
              "legacy_api_patients_checked": 1, "legacy_api_bills_checked": 1,
              "api_paths_checked": 5, "old_assets_checked": 10, "candidate_assets_checked": 10,
              "old_route_sha256": "1" * 64, "candidate_route_sha256": "2" * 64}
    for role in ("backend", "frontend"):
        probe = {"passed": True, "runtime_sha256": "3" * 64, "effective_environment_sha256": "4" * 64,
                 "private_url": "http://127.0.0.1:8001/health" if role == "backend" else "http://127.0.0.1:3000/login",
                 "checks": ["health", "representative_api"] if role == "backend" else ["login_assets"]}
        probe.update({"cache_sha256": "5" * 64, "active_build": "old"} if role == "backend" else {"build_id": "old-front"})
        report[f"old_{role}_probe_sha256"] = private_json(tmp_path / f"old-{role}-probe.json", probe)
    if same_port:
        report.update(profile=SAME_PORT_PROFILE, backend_port=8001, frontend_port=3000,
                      sequential_same_ports_verified=True, compiled_proxy_verified=True,
                      authentication_verified=True, public_real_data_guard_verified=True,
                      public_asset_guard_verified=True, persisted_api_dtos_verified=True,
                      old_wavea_capability="draft", candidate_wavea_capability="draft",
                      access_checks=20, baseline_contract="wavea-evidence-v2",
                      old_route_sha256=rehearsal.SAME_PORT_ROUTE_SHA256,
                      candidate_route_sha256=rehearsal.SAME_PORT_ROUTE_SHA256,
                      old_api_capture_sha256=private_json(tmp_path / "old-api-capture.json", {
                          "/api/billing-report/P1": {}, "/api/billing-report/P1/bills/B1": {},
                      }), same_input_proof_sha256=private_json(tmp_path / "same-input-rehearsal.json", {
                          "status": "same_input_bytes_verified", "candidate": {
                              "roster_sha256": candidate["source_roster_sha256"], "source_hash": "source",
                          },
                      }))
    path = tmp_path / "rehearsal.json"
    private_json(path, report)
    return path, tuple_path, candidate, runtime, report, observation


@pytest.mark.parametrize("same_port", [False, True])
def test_private_rehearsal_verifies_both_known_versions(tmp_path, same_port):
    path, observed, candidate, runtime, _, _ = sealed_rehearsal(tmp_path, same_port=same_port)
    result = verify_private_rehearsal(path, observed, candidate=candidate, backend_runtime=runtime)
    assert result["status"] == "private_pair_rehearsal_verified"


@pytest.mark.parametrize("fault", ["schema", "profile", "port", "tuple_port", "tuple_digest", "capture", "guard", "producer"])
def test_private_rehearsal_rejects_unknown_profiles_and_resealed_incoherence(tmp_path, fault):
    path, tuple_path, candidate, runtime, report, observed = sealed_rehearsal(tmp_path)
    if fault == "schema":
        report["schema_version"] = "wavea-same-port-rehearsal-v3"
    elif fault == "profile":
        report["profile"] = "dynamic-ports"
    elif fault == "port":
        report["backend_port"] = 8002
    elif fault == "tuple_port":
        observed["logical_tuple"]["backend"]["port"] = 8002
        observed["tuple_sha256"] = _canonical_digest(observed["logical_tuple"])
        report["candidate_tuple_sha256"] = observed["tuple_sha256"]
        report["candidate_tuple_observation_sha256"] = private_json(tuple_path, observed)
    elif fault == "tuple_digest":
        observed["logical_tuple"]["backend"]["cwd"] = "/tampered"
        report["candidate_tuple_observation_sha256"] = private_json(tuple_path, observed)
    elif fault == "capture":
        report["old_api_capture_sha256"] = private_json(tmp_path / "old-api-capture.json", {"wrong": {}, "paths": {}})
    elif fault == "guard":
        report["public_real_data_guard_verified"] = False
    else:
        (runtime / "scripts/deploy/rehearse_wavea_same_port.py").write_text("changed")
    private_json(path, report)
    with pytest.raises(ValueError):
        verify_private_rehearsal(path, tuple_path, candidate=candidate, backend_runtime=runtime)
