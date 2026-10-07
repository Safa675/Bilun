"""Synthetic signed transition through the real candidate and serving loaders.

The existing fabricated-host integration supplies build/replay and OS/HTTP
boundaries. No activation loader, sidecar verifier, rehearsal verifier, paired
candidate gate, final-artifact signer or API startup handler is substituted.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import json
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.deploy import build_wavea_sidecar as sidecar
from scripts.deploy import issue_wavea_activation as issuer
from scripts.deploy import paired_release as paired
from scripts.deploy import prepare_single_vps_release as preparer
from scripts.deploy import rehearse_wavea_same_port as rehearsal
from scripts.deploy import verify_candidate_semantics as semantics
from scripts.deploy import verify_clinical_semantic_transition as transition
from scripts.deploy.generate_candidate_source_roster import generate_source_roster
from scripts.deploy.paired_release_transaction import PairedReleaseError, PairedReleaseTransaction
from scripts.deploy.rehearse_wavea_pair import env_digest
from scripts.deploy.serving_activation import issue_serving_activation
from scripts.deploy.verify_candidate_cache import _BUILDER_TABLES, verify_candidate_cache
from scripts.deploy.verify_clinical_semantic_transition import TRANSITION_CONTRACT
from scripts.deploy.verify_same_input import _config_hash
from src.bilun.api import release_identity, startup, wavea_activation
from src.bilun.api.public_responses import project_public_response
from src.bilun.cache.builder import SUT_CLAIM_FILENAMES, SUT_CLEAN_FILENAMES
from src.bilun.db.hashing import source_hash_from_files
from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index
from tests.unit.deploy import test_single_vps_release_integration as integration
from tests.unit.deploy.test_candidate_environment import candidate_auth, write_env
from tests.unit.deploy.test_clinical_semantic_transition import (
    _authored_route_pair,
    transport_sources as _transport_sources_fixture,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


def make_signed_transition_bundle(tmp_path, monkeypatch, *, semantic_report_transform=None):
    """Reusable synthetic chain hook for the grouped mode/DTO compatibility test.

The transition is fabricated evidence for this disposable test host. The
existing fixture still performs real cache structural/content checks; its
detached checkout/replay provenance remains a deliberately fabricated boundary.
"""
    original_record = integration.recorded_rehearsal
    original_issue = issuer.issue_wavea_activation

    def record(root, old_build="baseline"):
        original_record(root, old_build)
        work = root / "rehearsal"
        candidate = integration.candidate_identity(root)
        same_input = _read(work / "same-input-rehearsal.json")
        producer = "scripts/deploy/rehearse_wavea_same_port.py"
        proof = {
            "status": "clinical_semantic_transition_verified", "contract": TRANSITION_CONTRACT,
            "candidate_code_sha": candidate["code_sha"], "same_input": same_input,
            "verifier": {"verifier_sha": candidate["code_sha"], "files": {
                producer: integration.sha(root / "candidate-backend" / producer),
            }},
        }
        source = _read(root / "semantic.json")
        source.update(same_input=same_input, clinical_transition=proof)
        if semantic_report_transform is not None:
            source = semantic_report_transform(source, root)
        integration.save(root / "semantic.json", source)
        integration.save(work / "clinical-transition-rehearsal.json", source["clinical_transition"])
        rehearsal_path = work / "real-candidate-namespace-rehearsal.json"
        rehearsal = _read(rehearsal_path)
        rehearsal["clinical_transition_report_sha256"] = integration.sha(
            work / "clinical-transition-rehearsal.json")
        integration.save(rehearsal_path, rehearsal)

    def issue(**kwargs):
        source_path = kwargs["sidecar_path"].parent.parent / "semantic.json"
        request = {"contract": TRANSITION_CONTRACT,
                   "expected_candidate_sha": _read(source_path)["candidate_identity"]["code_sha"],
                   "expected_verifier_sha": _read(source_path)["candidate_identity"]["code_sha"]}

        def replay(*_args, **arguments):
            assert arguments["clinical_transition"] == request
            return _read(source_path)

        # Only the already-fabricated detached source replay is substituted.
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(issuer, "verify_candidate_semantic_checkpoint", replay)
            return original_issue(**{**kwargs, "clinical_transition": request})

    monkeypatch.setattr(integration, "recorded_rehearsal", record)
    monkeypatch.setattr(issuer, "issue_wavea_activation", issue)
    return integration.make_bundle(tmp_path, monkeypatch)


@pytest.fixture
def signed_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(startup, "_startup_ready", False)
    monkeypatch.setattr(wavea_activation, "_startup_activation", None)
    return make_signed_transition_bundle(tmp_path, monkeypatch)


def _candidate_load(bundle):
    manifest = _read(bundle.manifest)
    config = _read(Path(manifest["candidate_launch_config"]))
    receipt = _read(Path(config["activation_receipt_path"]))
    return wavea_activation.load_startup_activation({
        "BILUN_WAVEA_ACTIVATION_RECEIPT": config["activation_receipt_path"],
        "BILUN_WAVEA_ACTIVATION_KEY_FILE": config["activation_key_path"],
    }, cache_path=Path(config["cache_path"]), active_build_id=receipt["cache_build_id"],
       code_sha=config["code_sha"], source_manifest_sha256=receipt["source_roster_sha256"],
       backend_runtime=Path(config["backend_runtime"]))


def _host(bundle, monkeypatch):
    fake = integration.FabricatedHost(bundle, monkeypatch)
    driver = paired.SingleVpsDriver(_read(bundle.manifest))
    transaction = PairedReleaseTransaction(
        state_dir=driver.root, lock_path=driver.paths["lock_path"],
        manifest_sha256=integration.sha(bundle.manifest), driver=driver,
    )
    transaction.prepare()
    return fake, driver, transaction


def _startup(driver, monkeypatch, *, serving_path=None):
    receipt = _read(driver.candidate_receipt)
    monkeypatch.setattr(release_identity, "STARTUP_RELEASE_IDENTITY", release_identity.ReleaseIdentity(
        receipt["code_sha"], receipt["source_roster_sha256"],
    ))
    monkeypatch.setattr(startup, "_PROJECT_ROOT", driver.backend)
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "verified-load-only")
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(serving_path or driver.paths["live_cache_path"]))
    monkeypatch.setenv("BILUN_WAVEA_ACTIVATION_RECEIPT", str(driver.root / "serving-receipt.json"))
    monkeypatch.setenv("BILUN_WAVEA_ACTIVATION_KEY_FILE", str(driver.key))
    asyncio.run(startup.startup())


def _resign(bundle):
    receipt_path = bundle.root / "candidate-receipt.json"
    receipt = _read(receipt_path)
    receipt["sidecar_sha256"] = integration.sha(Path(receipt["sidecar_path"]))
    receipt["rehearsal_sha256"] = integration.sha(Path(receipt["rehearsal_path"]))
    key = Path(bundle.spec["signing_key_path"]).read_bytes()
    unsigned = {k: v for k, v in receipt.items() if k != "signature_sha256"}
    receipt["signature_sha256"] = hmac.new(
        key, wavea_activation._canonical(unsigned), hashlib.sha256,
    ).hexdigest()
    integration.save(receipt_path, receipt)


def _reseal_semantic(bundle, *, mirror_rehearsal=False):
    """Re-sign synthetic outer artifacts to exercise checks below their digests."""
    source_path = bundle.root / "semantic.json"
    source = _read(source_path)
    if mirror_rehearsal:
        work = bundle.root / "rehearsal"
        integration.save(work / "clinical-transition-rehearsal.json", source["clinical_transition"])
        rehearsal_path = work / "real-candidate-namespace-rehearsal.json"
        rehearsal = _read(rehearsal_path)
        rehearsal["clinical_transition_report_sha256"] = integration.sha(
            work / "clinical-transition-rehearsal.json")
        integration.save(rehearsal_path, rehearsal)
    sidecar_path = bundle.root / "evidence/sidecar.json"
    sidecar = _read(sidecar_path)
    envelope_path = Path(sidecar["evidence"]["semantic_cache"]["path"])
    envelope = _read(envelope_path)
    raw_path = Path(envelope["raw_report_path"])
    raw = _read(raw_path)
    if "source_report_sha256" in raw:
        raw["source_report_sha256"] = integration.sha(source_path)
    integration.save(raw_path, raw)
    envelope["raw_report_sha256"] = integration.sha(raw_path)
    integration.save(envelope_path, envelope)
    sidecar["evidence"]["semantic_cache"]["sha256"] = integration.sha(envelope_path)
    integration.save(sidecar_path, sidecar)
    _resign(bundle)


def test_signed_transition_real_candidate_paired_tuple_serving_and_startup(signed_bundle, monkeypatch):
    bundle = signed_bundle
    activation = _candidate_load(bundle)
    assert activation.receipt_version == wavea_activation.RECEIPT_VERSION
    fake, driver, transaction = _host(bundle, monkeypatch)
    assert driver._candidate_gate()["cache_sha256"] == activation.cache_sha256
    assert transaction.activate()["state"] == "active"
    # The transaction's real tuple observer includes the real serving loader.
    assert transaction.status()["live_readiness"] == "verified"
    activated = wavea_activation.activation_for_build("candidate")
    assert activated.receipt_version == "wavea-serving-receipt-v2"
    assert activated.cache_sha256 == integration.sha(bundle.live) != activation.cache_sha256
    _startup(driver, monkeypatch)
    assert startup.is_cache_ready()
    assert transaction.rollback()["state"] == "rolled_back"
    integration.assert_old_restored(fake, driver, transaction)


@pytest.mark.parametrize("hop", ["sidecar", "envelope", "raw", "source"])
def test_each_signed_semantic_digest_hop_rejects_tamper(signed_bundle, hop):
    bundle = signed_bundle
    sidecar_path = bundle.root / "evidence/sidecar.json"
    sidecar = _read(sidecar_path)
    envelope_path = Path(sidecar["evidence"]["semantic_cache"]["path"])
    envelope = _read(envelope_path)
    paths = {"sidecar": sidecar_path, "envelope": envelope_path,
             "raw": Path(envelope["raw_report_path"]), "source": bundle.root / "semantic.json"}
    value = _read(paths[hop])
    value["tampered"] = True
    integration.save(paths[hop], value)
    with pytest.raises(ValueError):
        _candidate_load(bundle)


@pytest.mark.parametrize("mutation", [
    "missing_source", "relative_source", "partial_source", "digest_without_source",
    "source_status", "source_identity",
    "missing_transition", "null_transition", "malformed_transition", "unauthorized_contract",
    "candidate_sha", "verifier_sha", "missing_closure", "stale_closure", "source_input",
    "rehearsal_input", "downgraded_schema",
])
def test_resealed_transition_cannot_weaken_identity_source_or_input_binding(signed_bundle, mutation):
    bundle = signed_bundle
    source_path = bundle.root / "semantic.json"
    source = _read(source_path)
    proof = source["clinical_transition"]
    mirror = False
    if mutation in {"missing_source", "relative_source", "partial_source", "digest_without_source"}:
        raw_path = bundle.root / "evidence/semantic_cache-raw.json"
        raw = _read(raw_path)
        if mutation == "missing_source":
            raw.pop("source_report_path")
            raw.pop("source_report_sha256")
        elif mutation == "relative_source":
            raw["source_report_path"] = "semantic.json"
        elif mutation == "digest_without_source":
            raw.pop("source_report_path")
        else:
            raw.pop("source_report_sha256")
        integration.save(raw_path, raw)
    elif mutation == "source_status":
        source["status"] = "failed"
    elif mutation == "source_identity":
        source["candidate_identity"]["build_id"] = "unreviewed"
    elif mutation == "missing_transition":
        source.pop("clinical_transition")
    elif mutation == "null_transition":
        source["clinical_transition"] = None
    elif mutation == "malformed_transition":
        source["clinical_transition"] = "unreviewed"
    elif mutation == "unauthorized_contract":
        proof["contract"] = "unreviewed-transition"
        mirror = True
    elif mutation == "candidate_sha":
        proof["candidate_code_sha"] = "f" * 40
        mirror = True
    elif mutation == "verifier_sha":
        proof["verifier"]["verifier_sha"] = "f" * 40
        mirror = True
    elif mutation == "missing_closure":
        proof["verifier"]["files"] = {}
        mirror = True
    elif mutation == "stale_closure":
        proof["verifier"]["files"]["scripts/deploy/rehearse_wavea_same_port.py"] = "f" * 64
        mirror = True
    elif mutation == "source_input":
        source["same_input"] = {"status": "same_input_bytes_verified", "unbound": True}
    elif mutation == "rehearsal_input":
        proof["same_input"] = copy.deepcopy(proof["same_input"])
        proof["same_input"]["candidate"]["roster_sha256"] = "f" * 64
        source["same_input"] = proof["same_input"]
        mirror = True
    else:
        rehearsal_path = bundle.root / "rehearsal/real-candidate-namespace-rehearsal.json"
        rehearsal = _read(rehearsal_path)
        rehearsal["schema_version"] = "wavea-real-pair-rehearsal-v1"
        integration.save(rehearsal_path, rehearsal)
    integration.save(source_path, source)
    _reseal_semantic(bundle, mirror_rehearsal=mirror)
    with pytest.raises(ValueError):
        _candidate_load(bundle)


def test_legacy_sidecar_without_source_locator_keeps_strict_transition_free_default(signed_bundle):
    bundle = signed_bundle
    raw_path = bundle.root / "evidence/semantic_cache-raw.json"
    raw = _read(raw_path)
    raw.pop("source_report_path")
    raw.pop("source_report_sha256")
    integration.save(raw_path, raw)
    rehearsal_path = bundle.root / "rehearsal/real-candidate-namespace-rehearsal.json"
    rehearsal = _read(rehearsal_path)
    rehearsal.pop("clinical_transition_report_sha256")
    integration.save(rehearsal_path, rehearsal)
    _reseal_semantic(bundle)
    assert _candidate_load(bundle).cache_build_id == "candidate"


def test_semantic_source_changed_after_authenticated_read_is_rejected(signed_bundle, monkeypatch):
    bundle = signed_bundle
    source_path = bundle.root / "semantic.json"
    trace_path = bundle.root / "trace-attestation.json"
    original_load = wavea_activation._load_private_json
    altered = False

    def load(path, **kwargs):
        nonlocal altered
        result = original_load(path, **kwargs)
        if path == trace_path and not altered:
            # The real source load has completed; later artifact I/O changes it.
            integration.save(source_path, {**_read(source_path), "changed_during_verification": True})
            altered = True
        return result

    monkeypatch.setattr(wavea_activation, "_load_private_json", load)
    with pytest.raises(ValueError, match="changed during activation"):
        _candidate_load(bundle)
    assert altered


@pytest.mark.parametrize("alias", ["symlink", "hardlink"])
def test_sealed_semantic_source_must_remain_an_independent_private_file(signed_bundle, alias):
    source = signed_bundle.root / "semantic.json"
    other = signed_bundle.root / "semantic-alias.json"
    if alias == "symlink":
        source.rename(other)
        source.symlink_to(other)
    else:
        other.hardlink_to(source)
    with pytest.raises(ValueError, match="private independent|not independent"):
        _candidate_load(signed_bundle)


def test_startup_failure_clears_activation_then_accepts_restored_signed_evidence(signed_bundle, monkeypatch):
    fake, driver, transaction = _host(signed_bundle, monkeypatch)
    assert transaction.activate()["state"] == "active"
    source_path = signed_bundle.root / "semantic.json"
    original = source_path.read_bytes()
    integration.save(source_path, {**_read(source_path), "tampered": True})
    with pytest.raises(SystemExit):
        _startup(driver, monkeypatch)
    assert not startup.is_cache_ready()
    assert wavea_activation.activation_for_build("candidate") is None
    source_path.write_bytes(original)
    _startup(driver, monkeypatch)
    assert startup.is_cache_ready()
    assert wavea_activation.activation_for_build("candidate").receipt_version == "wavea-serving-receipt-v2"
    assert transaction.rollback()["state"] == "rolled_back"
    integration.assert_old_restored(fake, driver, transaction)


def test_final_signing_failure_rolls_back_and_same_key_retry_loads(signed_bundle, monkeypatch):
    fake, driver, transaction = _host(signed_bundle, monkeypatch)
    key_before = driver.key.read_bytes()
    candidate_before = driver.candidate_receipt.read_bytes()
    original_write = issuer._new_private_file

    def fail_final(path, data):
        if path.name == "serving-receipt.json":
            raise OSError("fixture final signing failure")
        return original_write(path, data)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(issuer, "_new_private_file", fail_final)
        with pytest.raises(PairedReleaseError, match="exact old pair restored"):
            transaction.activate()
    integration.assert_old_restored(fake, driver, transaction)
    assert driver.key.read_bytes() == key_before
    assert driver.candidate_receipt.read_bytes() == candidate_before
    assert not (driver.root / "serving-receipt.json").exists()
    signed = issue_serving_activation(
        candidate_receipt_path=driver.candidate_receipt, candidate_cache_path=driver.candidate_db,
        stopped_db_copy=driver.root / "stopped.duckdb", serving_cache_path=driver.root / "serving.duckdb",
        derivation_path=driver.root / "derivation.json", key_path=driver.key,
        receipt_path=driver.root / "serving-receipt.json", backend_runtime=driver.backend,
    )
    assert signed["status"] == "serving_activation_signed"
    _startup(driver, monkeypatch, serving_path=driver.root / "serving.duckdb")
    assert startup.is_cache_ready()
    assert driver.key.read_bytes() == key_before


# Genuine interpreter inputs observed by the original isolated source worker.
# Missing optional modules cannot be read; the worker still rejects uncovered
# reads. No interpreter prefix, filesystem root or copied dependency substitutes.
_TRANSPORT_STDLIB = (
    "__future__.py", "_colorize.py", "_compat_pickle.py", "_compression.py",
    "_pyrepl", "_strptime.py", "argparse.py", "base64.py", "bisect.py",
    "bz2.py", "calendar.py", "concurrent", "contextvars.py", "csv.py",
    "ctypes", "datetime.py", "decimal.py", "difflib.py", "email",
    "fractions.py", "gettext.py", "gzip.py", "hashlib.py", "heapq.py",
    "hmac.py", "importlib", "ipaddress.py", "locale.py", "logging",
    "lzma.py", "numbers.py", "pickle.py", "pkgutil.py", "platform.py",
    "pprint.py", "pydoc.py", "queue.py", "random.py", "secrets.py",
    "selectors.py", "shutil.py", "signal.py", "socket.py", "string.py",
    "struct.py", "subprocess.py", "sysconfig", "tarfile.py", "tempfile.py",
    "textwrap.py", "threading.py", "traceback.py", "urllib", "uuid.py",
    "xml", "zipfile", "zoneinfo",
)


def _transport_dependencies():
    stdlib = Path(sysconfig.get_path("stdlib")).resolve(strict=True)
    roots = {(stdlib / name).resolve(strict=True) for name in _TRANSPORT_STDLIB
             if (stdlib / name).exists()}
    roots.update(path.resolve(strict=True) for path in stdlib.glob("_sysconfigdata*.py")
                 if path.is_file())
    # The -I -S worker needs the genuine package parent on its explicit sys.path.
    roots.add(Path(sysconfig.get_path("purelib")).resolve(strict=True))
    timezone = Path("/usr/share/zoneinfo/Etc/UTC")
    if timezone.exists():
        roots.add(timezone.resolve(strict=True))
    assert roots and len(roots) <= 64 and Path("/") not in roots
    assert all(root.is_file() or root.is_dir() for root in roots)
    return tuple(sorted(roots))


def _fixture_git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def _nonempty_drug_slice():
    with pytest.MonkeyPatch.context() as patch:
        report, _ = _authored_route_pair(patch)
    report.pop("alias_predicates")
    for kind in ("findings", "evaluations"):
        row = report["drug_indication"][kind][0]
        row.update(finding_kind="indication_mismatch", matched_icd10_codes=[],
                   unmatched_icd10_codes=["Z01"], required_inputs=[], missing_inputs=[])
        if kind == "findings":
            row["recommended_action_tr"] = "Review authored synthetic report"
        for route in row["eligible_routes"]:
            route.update(regulatory_summary_tr="Public authored synthetic inventory",
                         report_duration_months=None, report_specialties=[], prescriber_specialties=[],
                         icd10_code_count=0, icd10_codes_truncated=False,
                         icd10_range_count=len(route["icd10_ranges"]), icd10_ranges_truncated=False)
    return report


def _populate_combined_cache(path, *, checkout, code_sha, environment, drug):
    claims, clean = checkout / "data/synthetic/sut/claims", checkout / "data/synthetic/sut/clean"
    provenance = {
        "mode": "synthetic_demo", "is_synthetic": True,
        "label": "Public authored synthetic fixture", "notice": "No patient or production data",
        "claim_source": claims.relative_to(checkout).as_posix(),
        "clinical_source": clean.relative_to(checkout).as_posix(),
    }
    with duckdb.connect(str(path)) as con:
        tables = [table for (table,) in con.execute("SHOW TABLES").fetchall()
                  if "payload_json" in {row[1] for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()}]
        patient = None
        for table in tables:
            for build, raw in con.execute(f'SELECT build_id,payload_json FROM "{table}"').fetchall():
                payload = json.loads(raw)
                payload["data_source"] = copy.deepcopy(provenance)
                if table in {"patient_billing_report_rows", "patient_bill_billing_report_rows"}:
                    payload["drug_indication"] = copy.deepcopy(drug["drug_indication"])
                    payload["recommended_actions"] = [*payload["recommended_actions"],
                                                        *copy.deepcopy(drug["recommended_actions"])]
                    payload["sgk_uplift_try"] = 0.0
                    # An authored known lab total is valid in both frozen DTOs;
                    # current no-claim computation otherwise leaves it unknown.
                    payload["lab"]["normative_cost_try"] = 7.5
                    if table == "patient_billing_report_rows":
                        patient = payload
                con.execute(f'UPDATE "{table}" SET payload_json=? WHERE build_id=? AND payload_json=?',
                            [json.dumps(payload), build, raw])
        assert patient is not None
        cohort = build_cohort_compliance_index({"P1": patient})
        cohort["data_source"] = copy.deepcopy(provenance)
        con.execute("UPDATE cohort_compliance_index SET payload_json=?", [json.dumps(cohort)])
        counts = {table: con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                  for table in _BUILDER_TABLES}
        con.execute("UPDATE build_meta SET code_sha=?,source_hash=?,config_hash=?,row_counts_json=?,checksums_json=?", [
            code_sha, source_hash_from_files([clean / name for name in SUT_CLEAN_FILENAMES]
                                             + [claims / name for name in SUT_CLAIM_FILENAMES]),
            _config_hash(environment, mode="synthetic_demo", claims_dir=provenance["claim_source"],
                         clean_dir=provenance["clinical_source"]),
            json.dumps(counts), json.dumps({"sut_patient_count": "1"}),
        ])
        con.execute("UPDATE build_pointer_scopes SET active_build_id=(SELECT build_id FROM build_meta LIMIT 1) "
                    "WHERE scope='bilun'")
    return provenance


def make_combined_transition_bundle(tmp_path, monkeypatch, source_snapshots):
    """Real source/DTO/mode/receipt chain with one precise synthetic replay seam.

    Only detached clinical replay returns an authored ClinicalTransitionProof.
    Cache build/trace production and OS/process/proxy/HTTP observations are
    fabricated. Source rosters, same-input/config proof, high-level semantic
    table parity, source serializer subprocess/audit, public mode guards, v1
    issuance/load, paired gate, derivation/v2 signatures, tuple and API startup
    execute their original implementations. This is not a clinical production
    replay test. The independent source models reconstruct old blobs in shallow
    CI and commit every fixture source/input before any roster/runtime digest.
    """
    real_baseline = preparer._baseline_roster
    real_semantic = semantics.verify_candidate_semantic_checkpoint
    real_bridge = semantics.verify_serving_baseline_equivalence
    manifest, spec, events, _ = integration.preparation_machine.__wrapped__(tmp_path, monkeypatch)
    root, repository = Path(spec["bundle_root"]), Path(__file__).resolve().parents[3]
    baseline, candidate, _ = integration._current_fixture(tmp_path / "authored-caches")
    sources, dependencies = {}, _transport_dependencies()
    for side, (source, _) in source_snapshots.items():
        checkout = tmp_path / (side + "-source")
        shutil.copytree(source, checkout, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for relative in ("data/gazette", "data/medula", "scripts/bilun", "scripts/deploy"):
            shutil.copytree(repository / relative, checkout / relative,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for relative in ("pyproject.toml", "requirements.txt", "data/synthetic/demo_vignettes.json"):
            (checkout / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repository / relative, checkout / relative)
        claims, clean = checkout / "data/synthetic/sut/claims", checkout / "data/synthetic/sut/clean"
        claims.mkdir(parents=True)
        clean.mkdir()
        for name in SUT_CLAIM_FILENAMES:
            source_input = baseline.parent / "claim" / name
            if source_input.exists():
                shutil.copy2(source_input, claims / name)
            else:
                pq.write_table(pa.table({"authored_synthetic_fixture": pa.array([], type=pa.string())}), claims / name)
        for name in SUT_CLEAN_FILENAMES:
            pq.write_table(pa.table({"authored_synthetic_fixture": pa.array([], type=pa.string())}), clean / name)
        _fixture_git(checkout, "add", "--force", "src", "scripts", "data", "pyproject.toml", "requirements.txt")
        _fixture_git(checkout, "commit", "-qm", "complete isolated synthetic startup inputs")
        sources[side] = checkout, _fixture_git(checkout, "rev-parse", "HEAD")
    old_source, old_sha = sources["baseline"]
    new_source, new_sha = sources["candidate"]
    fixed_backend = {**candidate_auth(), "BILUN_PUBLIC_BILLING_ENABLED": "true"}
    fixed_backend.pop("BILUN_DATA_MODE", None)
    fixed_backend.pop("SUT_DATA_MODE", None)
    fixed_frontend = {"NODE_ENV": "production"}
    config_environment = dict.fromkeys(preparer._CONFIG_KEYS, "")
    runtime_expectations = {side: integration._runtime_digest(source[0], backend=True)
                            for side, source in sources.items()}
    drug = _nonempty_drug_slice()
    old_provenance = _populate_combined_cache(baseline, checkout=old_source, code_sha=old_sha,
                                             environment=config_environment, drug=drug)
    # Fill candidate raw slices now; build callback only rebinds its source hash
    # to the final independently copied checkout, without touching report bytes.
    _populate_combined_cache(candidate, checkout=new_source, code_sha=new_sha,
                             environment=config_environment, drug=drug)
    live = Path(spec["live_cache_path"])
    shutil.copy2(baseline, live)
    spec.update(schema_version=preparer.DEPENDENCY_CHAIN_SCHEMA, repository=str(new_source),
                baseline_checkout=str(old_source), baseline_claims_dir=str(old_source / "data/synthetic/sut/claims"),
                baseline_clean_dir=str(old_source / "data/synthetic/sut/clean"), live_backend_runtime=str(old_source),
                target_sha=new_sha, baseline_code_sha=old_sha, serving_code_sha=old_sha,
                old_build_id="baseline", patient_id="P1", backend_python=sys.executable,
                node=sys.executable, npm=sys.executable, dependency_roots=[str(path) for path in dependencies],
                baseline_build_config_environment=config_environment,
                clinical_transition={"contract": TRANSITION_CONTRACT, "expected_candidate_sha": new_sha,
                                     "expected_verifier_sha": new_sha})
    for role in ("backend", "frontend"):
        dropin = tmp_path / f"bilun-{role}.service.d"
        dropin.mkdir(mode=0o700)
        spec[f"{role}_dropin"] = str(dropin / "bilun-paired-release.conf")
    write_env(Path(spec["candidate_backend_environment"]), fixed_backend)
    write_env(Path(spec["candidate_frontend_environment"]), fixed_frontend)
    Path(spec["caddy_config"]).write_bytes(integration.OLD_CADDYFILE)
    integration.save(manifest, spec)
    machine_snapshot, machine_frontend = preparer._snapshot_old, preparer._build_frontend
    machine_observe = preparer._observe_live
    packages, proofs, http_snapshots = {}, [], {}

    def observe(parsed):
        observation = machine_observe(parsed)
        captured_old_environment = {**fixed_backend, "BILUN_CACHE_DB_PATH": str(live),
                                    "BILUN_HEALTH_PROBE_TOKEN": "fixture-old-health-token-1234567890"}
        observation["backend"]["effective_environment_sha256"] = env_digest(captured_old_environment)
        observation["backend_runtime_sha256"] = runtime_expectations["baseline"]
        return observation

    def snapshot(parsed, before):
        result = machine_snapshot(parsed, before)
        write_env(root / "old-snapshot/backend-effective-env.nul", {
            **fixed_backend, "BILUN_CACHE_DB_PATH": str(live),
            "BILUN_HEALTH_PROBE_TOKEN": "fixture-old-health-token-1234567890",
        })
        return result

    def checkout(_parsed):
        destination = root / "candidate-backend"
        shutil.copytree(new_source, destination)
        return destination, destination / "data/synthetic/sut/claims", destination / "data/synthetic/sut/clean"

    def frontend(parsed, backend):
        path = machine_frontend(parsed, backend)
        (path / ".next/static").mkdir(parents=True)
        (path / ".next/BUILD_ID").write_text("fixture-front")
        integration.save(path / ".next/required-server-files.json", {"config": {"productionBrowserSourceMaps": False}})
        for index in range(10):
            (path / f".next/static/{index}.js").write_text(f"console.log({index})")
        integration.save(path / ".next/routes-manifest.json", {"rewrites": {"beforeFiles": [], "fallback": [],
            "afterFiles": [{"source": "/api/:path*", "destination": "http://127.0.0.1:8001/api/:path*"}]}})
        return path

    def build(**kwargs):
        shutil.copy2(candidate, kwargs["db_path"])
        # Hash stored input paths only after the final real checkout exists.
        claims, clean = kwargs["claims_dir"], kwargs["clean_dir"]
        with duckdb.connect(str(kwargs["db_path"])) as con:
            con.execute("UPDATE build_meta SET source_hash=?", [source_hash_from_files(
                [clean / name for name in SUT_CLEAN_FILENAMES] + [claims / name for name in SUT_CLAIM_FILENAMES])])
        for field in ("trace_path", "log_path"):
            kwargs[field].write_text("fabricated cache process/trace boundary")
        integration.save(kwargs["report_path"], {"build_id": "candidate"})
        return {"build_id": "candidate"}

    def detached_replay(**kwargs):
        assert kwargs["expected_candidate_sha"] == kwargs["expected_verifier_sha"] == new_sha
        projections = {side: {family: {key: copy.deepcopy(drug)}
                             for family, key in (("patients", "P1"), ("bills", "P1::C1"))}
                       for side in ("baseline", "candidate")}
        closure = {path.relative_to(root / "candidate-backend").as_posix(): integration.sha(path)
                   for folder in ("src", "scripts") for path in (root / "candidate-backend" / folder).rglob("*.py")}
        report = {"status": "clinical_semantic_transition_verified", "contract": TRANSITION_CONTRACT,
                  "baseline_code_sha": old_sha, "candidate_code_sha": new_sha, "same_input": kwargs["same_input"],
                  "verifier": {"verifier_sha": new_sha, "files": closure}}
        proof = transition.ClinicalTransitionProof(json.dumps(report, sort_keys=True), json.dumps(projections, sort_keys=True))
        proofs.append(proof)
        return proof

    def trace(**kwargs):
        return {"status": "traced_build_attestation_verified", "release_ready": False,
                "code_sha": new_sha, "build_id": "candidate", "source_roster_sha256": integration.sha(root / "source-roster.json"),
                "cache_sha256": integration.sha(root / "candidate.duckdb")}

    def ci(**kwargs):
        events.append("ci")
        return {"status": "release_ci_verified", "code_sha": kwargs["code_sha"], "ci_run_id": kwargs["run_id"]}

    def record(*_args):
        # Captured I/O expectation is derived from fixture input dictionaries;
        # no launcher, observer or HTTP value supplies the expected environment.
        integration.recorded_rehearsal(root)
        work, identity = root / "rehearsal", integration.candidate_identity(root)
        backend = {**fixed_backend, "BILUN_CACHE_DB_PATH": str(root / "candidate.duckdb"),
                   "BILUN_RELEASE_CODE_SHA": new_sha, "BILUN_RELEASE_SOURCE_MANIFEST_SHA256": identity["source_roster_sha256"],
                   "BILUN_STARTUP_POLICY": "verified-load-only", "PYTHONDONTWRITEBYTECODE": "1"}
        frontend_env = {**fixed_frontend, "PORT": "3000", "HOSTNAME": "127.0.0.1",
                        "API_PROXY_TARGET": "http://127.0.0.1:8001", "BILUN_RELEASE_CODE_SHA": new_sha}
        observed = _read(work / "candidate-tuple-observation.json")
        for role, expected in (("backend", backend), ("frontend", frontend_env)):
            observed["logical_tuple"][role]["effective_environment_sha256"] = env_digest(expected)
        observed["tuple_sha256"] = integration.observer._canonical_digest(observed["logical_tuple"])
        integration.save(work / "candidate-tuple-observation.json", observed)
        for side, cache, build_id, source, sha in (
            ("baseline", root / "baseline.duckdb", "baseline", old_source, old_sha),
            ("candidate", root / "candidate.duckdb", "candidate", root / "candidate-backend", new_sha),
        ):
            collected = []
            _, _, _, reports, _, _ = rehearsal._cache_reports(cache, repository=source,
                expected_code_sha=sha, expected_runtime_sha256=runtime_expectations[side],
                python_executable=Path(sys.executable), dependency_roots=dependencies, transport_out=collected)
            packages[side] = collected[0]
            http_snapshots[side] = json.dumps(collected[0].draft_reports, sort_keys=True)
            captured_environment = ({**fixed_backend, "BILUN_CACHE_DB_PATH": str(live),
                                     "BILUN_HEALTH_PROBE_TOKEN": "fixture-old-health-token-1234567890"}
                                    if side == "baseline" else backend)
            assert rehearsal._public_data_guard(captured_environment, reports, repository=source, expected_code_sha=sha,
                expected_runtime_sha256=runtime_expectations[side],
                expected_environment_sha256=env_digest(captured_environment))
        old_environment = {**fixed_backend, "BILUN_CACHE_DB_PATH": str(live),
                           "BILUN_HEALTH_PROBE_TOKEN": "fixture-old-health-token-1234567890"}
        for role, expected_runtime, expected_environment in (
            ("backend", runtime_expectations["baseline"], old_environment),
            ("frontend", integration._runtime_digest(Path(spec["live_frontend_runtime"]), backend=False), fixed_frontend),
        ):
            probe_path = work / f"old-{role}-probe.json"
            probe = _read(probe_path)
            probe.update(runtime_sha256=expected_runtime, effective_environment_sha256=env_digest(expected_environment))
            integration.save(probe_path, probe)
        proof = proofs[-1]
        def capture_http(side):
            # Fabricated HTTP transport returns bytes for each observed path;
            # immutable source packages supply the independent expectations.
            captured = {}
            for path in packages[side].raw_reports:
                status, raw = 200, json.dumps(json.loads(http_snapshots[side])[path]).encode()
                assert status == 200
                captured[path] = json.loads(raw)
            return captured

        old_observed, new_observed = capture_http("baseline"), capture_http("candidate")
        rehearsal.compare_reports(old_observed, new_observed,
            contract="wavea-evidence-v2", old_capability="draft", old_persisted=packages["baseline"].complete_reports,
            same_input=proof.report["same_input"], clinical_transition=proof,
            old_transport=packages["baseline"], candidate_transport=packages["candidate"])
        integration.save(work / "old-api-capture.json", old_observed)
        integration.save(work / "same-input-rehearsal.json", proof.report["same_input"])
        integration.save(work / "clinical-transition-rehearsal.json", proof.report)
        value = _read(work / "real-candidate-namespace-rehearsal.json")
        value.update(old_wavea_capability="draft", candidate_tuple_sha256=observed["tuple_sha256"],
                     candidate_tuple_observation_sha256=integration.sha(work / "candidate-tuple-observation.json"),
                     old_api_capture_sha256=integration.sha(work / "old-api-capture.json"),
                     same_input_proof_sha256=integration.sha(work / "same-input-rehearsal.json"),
                     clinical_transition_report_sha256=integration.sha(work / "clinical-transition-rehearsal.json"),
                     old_backend_probe_sha256=integration.sha(work / "old-backend-probe.json"),
                     old_frontend_probe_sha256=integration.sha(work / "old-frontend-probe.json"))
        integration.save(work / "real-candidate-namespace-rehearsal.json", value)

    monkeypatch.setattr(transition, "verify_clinical_semantic_transition", detached_replay)
    for name, function in {
        "candidate_environments": integration.candidate_environments, "_baseline_roster": real_baseline,
        "_observe_live": observe, "_snapshot_old": snapshot, "_create_checkout": checkout, "_build_frontend": frontend,
        "generate_source_roster": generate_source_roster, "build_traced_candidate": build,
        "verify_candidate_cache": verify_candidate_cache, "verify_serving_baseline_equivalence": real_bridge,
        "verify_candidate_semantic_checkpoint": real_semantic, "verify_traced_build_attestation": trace,
        "_rehearse": record, "build_wavea_sidecar": sidecar.build_wavea_sidecar,
        "issue_wavea_activation": issuer.issue_wavea_activation, "fetch_successful_release_ci": ci,
    }.items():
        monkeypatch.setattr(preparer, name, function)
    for name, function in {"verify_candidate_semantic_checkpoint": real_semantic,
                           "verify_traced_build_attestation": trace, "fetch_successful_release_ci": ci}.items():
        monkeypatch.setattr(issuer, name, function)
    health = {"status": "ok", "active_build": "baseline", "cache_ready": True, "code_sha": old_sha}
    monkeypatch.setattr(issuer, "_live_health", lambda *_: health)
    monkeypatch.setattr(issuer, "read_loopback_health", lambda *_: health)
    monkeypatch.setattr(issuer, "observe_service", lambda *a: object())
    monkeypatch.setattr(issuer, "assess_release_preflight", lambda *a, **kw: {
        "observed": {"backend": {"observed_checkout_head": old_sha, "serving_code_sha_verified": True, "health_code_sha": old_sha}},
        "rollback": {"blockers": [], "artifacts": {"backend": {"private_probe": {}}, "frontend": {"private_probe": {}},
            "service_and_proxy_configuration": {}, "cache": {"active_build": "baseline", "sha256": integration.sha(root / "old-snapshot/cache.duckdb")}}},
    })
    result = preparer.prepare_release_bundle(manifest)
    return SimpleNamespace(root=root, manifest=Path(result["paired_manifest_path"]), spec=spec, live=live,
                           events=events, old_bytes=live.read_bytes(), candidate=candidate, sources=sources,
                           dependencies=dependencies, packages=packages, proof=proofs[-1],
                           fixed_backend=fixed_backend, old_provenance=old_provenance, http_snapshots=http_snapshots,
                           runtime_expectations=runtime_expectations)


@pytest.fixture(scope="module")
def combined_transport_sources(tmp_path_factory):
    return _transport_sources_fixture.__wrapped__(tmp_path_factory)


class CombinedHost(integration.FabricatedHost):
    """Fabricated OS/HTTP delivery; expectations remain source-sealed beforehand."""

    def __init__(self, bundle, monkeypatch):
        super().__init__(bundle, monkeypatch)
        self.old_environment = {**bundle.fixed_backend, "BILUN_CACHE_DB_PATH": str(bundle.live),
                                "BILUN_HEALTH_PROBE_TOKEN": "fixture-old-health-token-1234567890"}
        self.environments["backend"] = self.old_environment
        self._write_processes()

    def fetch(self, base, path, cookie=None):
        if base == "https://app.bilun.tech" and self.loaded_route != integration.OLD_CADDYFILE:
            return 503, b""
        assert all(self.running.values()), "HTTP exposed a partially running pair"
        if path in self.bundle.packages["baseline"].raw_reports:
            if self.active_launch:
                reports = self.bundle.packages["candidate"].complete_reports
            else:
                reports = json.loads(self.bundle.http_snapshots["baseline"])
            payload = reports[path]
            if cookie is None:
                surface = "get_bill_billing_report" if "/bills/" in path else "get_billing_report"
                payload = project_public_response(payload, surface)
            return 200, json.dumps(payload).encode()
        return super().fetch(base, path, cookie)


def _assert_combined_negative_matrix(bundle):
    """Mutate observed DTOs only; retain genuine sealed source packages/proof."""
    baseline, candidate = bundle.packages["baseline"], bundle.packages["candidate"]
    expected_paths = {"/api/billing-report/P1", "/api/billing-report/P1/bills/C1"}
    assert set(baseline.raw_reports) == set(candidate.raw_reports) == expected_paths
    common = ("unknown_top", "unknown_finding", "money_bool", "money_integer", "money_null")
    checked = 0
    for side in ("baseline", "candidate"):
        for report in bundle.packages[side].raw_reports.values():
            assert type(report["lab"]["normative_cost_try"]) is float
            assert report["lab"]["normative_cost_try"] == 7.5
        mutations = (*common, "old_default") if side == "baseline" else (*common, "missing_authority", "missing_restrictions")
        for path in sorted(expected_paths):
            for mutation in mutations:
                # Observations come through the independently fixed synthetic
                # HTTP delivery snapshot, while expected transports stay sealed.
                old = json.loads(bundle.http_snapshots["baseline"])
                new = json.loads(bundle.http_snapshots["candidate"])
                changed = (old if side == "baseline" else new)[path]
                finding = changed["drug_indication"]["findings"][0]
                assert type(changed["sgk_uplift_try"]) is float and changed["sgk_uplift_try"] == 0.0
                if mutation == "unknown_top":
                    changed["unreviewed_field"] = True
                elif mutation == "unknown_finding":
                    finding["unreviewed_metadata"] = {"authorized": False}
                elif mutation.startswith("money_"):
                    changed["sgk_uplift_try"] = {"money_bool": False, "money_integer": 0, "money_null": None}[mutation]
                elif mutation == "old_default":
                    finding["source_authority"] = None
                else:
                    finding.pop("source_authority" if mutation == "missing_authority" else "clinical_restrictions")
                with pytest.raises(ValueError, match="Observed HTTP differs"):
                    rehearsal.compare_reports(old, new, contract="wavea-evidence-v2", old_capability="draft",
                        old_persisted=baseline.complete_reports, clinical_transition=bundle.proof,
                        old_transport=baseline, candidate_transport=candidate)
                checked += 1
    assert checked == 26
    # DTO defaults never become permission to widen the strict raw cache proof.
    for side, package in (("baseline", baseline), ("candidate", candidate)):
        for table, family in (("patient_billing_report_rows", "patients"),
                              ("patient_bill_billing_report_rows", "bills")):
            key = "P1" if family == "patients" else "P1::C1"
            path = "/api/billing-report/P1" if family == "patients" else "/api/billing-report/P1/bills/C1"
            for field, value in (("source_authority", None), ("unreviewed_metadata", True)):
                raw = {key: copy.deepcopy(package.raw_reports[path])}
                raw[key]["drug_indication"]["findings"][0][field] = value
                with pytest.raises(ValueError, match="cached drug producer replay"):
                    transition.normalize_transition_content(table, raw, side=side, proof=bundle.proof)
    with pytest.raises(ValueError, match="pinned source identity"):
        transition.normalize_transition_http_reports(candidate.draft_reports, side="candidate", proof=bundle.proof,
            transport=baseline, baseline_transport=baseline)
    wrong_report = bundle.proof.report
    wrong_report["candidate_code_sha"] = bundle.sources["baseline"][1]
    wrong_proof = transition.ClinicalTransitionProof(json.dumps(wrong_report), json.dumps(bundle.proof.projections))
    with pytest.raises(ValueError, match="pinned source identity"):
        transition.normalize_transition_http_reports(candidate.draft_reports, side="candidate", proof=wrong_proof,
            transport=candidate, baseline_transport=baseline)
    source, sha = bundle.root / "candidate-backend", bundle.sources["candidate"][1]
    for primary, legacy in (("synthetic_demo", "real_claims"), ("real_claims", "synthetic_demo")):
        independently_captured = {**bundle.fixed_backend, "BILUN_DATA_MODE": primary, "SUT_DATA_MODE": legacy}
        # A fresh matching independent seal ensures the mode resolver itself is
        # reached; this is separate from the stale signed environment rejection.
        with pytest.raises(ValueError, match="conflicting explicit data modes"):
            rehearsal._public_data_guard(independently_captured, candidate.complete_reports,
                repository=source, expected_code_sha=sha,
                expected_runtime_sha256=bundle.runtime_expectations["candidate"],
                expected_environment_sha256=env_digest(independently_captured))
    baseline.validate()
    candidate.validate()


def test_combined_implicit_mode_source_dto_signed_startup_chain(tmp_path, monkeypatch, combined_transport_sources):
    monkeypatch.setattr(startup, "_startup_ready", False)
    monkeypatch.setattr(wavea_activation, "_startup_activation", None)
    monkeypatch.delenv("BILUN_DATA_MODE", raising=False)
    monkeypatch.delenv("SUT_DATA_MODE", raising=False)
    bundle = make_combined_transition_bundle(tmp_path, monkeypatch, combined_transport_sources)
    activation = _candidate_load(bundle)
    assert activation.receipt_version == wavea_activation.RECEIPT_VERSION
    assert "BILUN_DATA_MODE" not in bundle.fixed_backend and "SUT_DATA_MODE" not in bundle.fixed_backend
    assert bundle.fixed_backend["BILUN_PUBLIC_BILLING_ENABLED"] == "true"
    for path in bundle.packages["baseline"].raw_reports:
        for side in ("baseline", "candidate"):
            raw = bundle.packages[side].raw_reports[path]
            assert raw["drug_indication"]["findings"] and raw["drug_indication"]["evaluations"]
            assert any(row.get("surface") == "drug_indication" for row in raw["recommended_actions"])
            assert "source_authority" not in raw["drug_indication"]["findings"][0]
        old = bundle.packages["baseline"].draft_reports[path]["drug_indication"]["findings"][0]
        new = bundle.packages["candidate"].draft_reports[path]["drug_indication"]["findings"][0]
        assert "source_authority" not in old and new["source_authority"] is None
        assert "clinical_restrictions" not in old and new["clinical_restrictions"] == []
    _assert_combined_negative_matrix(bundle)
    fake = CombinedHost(bundle, monkeypatch)
    driver = paired.SingleVpsDriver(_read(bundle.manifest))
    transaction = PairedReleaseTransaction(state_dir=driver.root, lock_path=driver.paths["lock_path"],
        manifest_sha256=integration.sha(bundle.manifest), driver=driver)
    transaction.prepare()
    assert driver._candidate_gate()["cache_sha256"] == activation.cache_sha256
    backend_environment = Path(driver.config["candidate_backend_environment"])
    original_environment = backend_environment.read_bytes()
    assert b"BILUN_DATA_MODE=" not in original_environment and b"SUT_DATA_MODE=" not in original_environment
    effects_before = list(fake.events)
    try:
        backend_environment.write_bytes(original_environment + b"BILUN_DATA_MODE=real_claims\0")
        with pytest.raises(ValueError, match="environment differs from signed rehearsal"):
            driver._candidate_gate()
        assert fake.events == effects_before
    finally:
        backend_environment.write_bytes(original_environment)
    assert transaction.activate()["state"] == "active"
    _, _, _, launch_environment = integration.candidate_command("backend", _read(driver.root / "launch.json"))
    assert "BILUN_DATA_MODE" not in launch_environment and "SUT_DATA_MODE" not in launch_environment
    assert transaction.status()["live_readiness"] == "verified"
    assert wavea_activation.activation_for_build("candidate").receipt_version == "wavea-serving-receipt-v2"
    _startup(driver, monkeypatch)
    assert startup.is_cache_ready()
    assert transaction.rollback()["state"] == "rolled_back"
    integration.assert_old_restored(fake, driver, transaction)
