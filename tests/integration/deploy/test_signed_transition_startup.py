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
from pathlib import Path

import pytest

from scripts.deploy import issue_wavea_activation as issuer
from scripts.deploy import paired_release as paired
from scripts.deploy.paired_release_transaction import PairedReleaseError, PairedReleaseTransaction
from scripts.deploy.serving_activation import issue_serving_activation
from scripts.deploy.verify_clinical_semantic_transition import TRANSITION_CONTRACT
from src.bilun.api import release_identity, startup, wavea_activation
from tests.unit.deploy import test_single_vps_release_integration as integration


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
