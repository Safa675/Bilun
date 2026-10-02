"""Dependency-v3 file-link chains retain the existing real serving gates."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from types import MethodType

import pytest

from scripts.deploy import paired_release, prepare_single_vps_release
from scripts.deploy.paired_release_transaction import atomic_json
from scripts.deploy.serving_activation import SERVING_RECEIPT_VERSION
from src.bilun.api import startup, wavea_activation
from tests.unit.deploy import test_serving_activation as serving
from tests.unit.deploy.test_verify_candidate_cache import BUILD_ID

host = serving.host


@pytest.fixture
def chain_pinned_host(host, monkeypatch):
    driver, _, _ = host
    dependency = driver.root / "usr/lib/python3.12"
    config = dependency / "config-3.12-x86_64-linux-gnu"
    library = driver.root / "usr/lib/x86_64-linux-gnu"
    customizations = driver.root / "etc/python3.12"
    for directory in (config, library, customizations):
        directory.mkdir(parents=True)

    target = library / "libpython3.12.so.1.0"
    target.write_bytes(b"explicitly pinned libpython fixture\n")
    target.chmod(0o755)
    alternate = library / "libpython3.12.so.alternate"
    alternate.write_bytes(target.read_bytes())
    alternate.chmod(0o755)
    intermediate = library / "libpython3.12.so.1"
    intermediate.symlink_to(target.name)
    entry = config / "libpython3.12.so"
    entry.symlink_to("../../x86_64-linux-gnu/libpython3.12.so.1")

    sitecustomize = customizations / "sitecustomize.py"
    sitecustomize.write_bytes(b"# explicitly pinned direct external dependency\n")
    sitecustomize.chmod(0o644)
    (dependency / "sitecustomize.py").symlink_to(sitecustomize)

    # Declaring the alternate up front proves retarget rejection is caused by
    # pinned chain identity, even when every destination is declared and equal.
    roots = (dependency, intermediate, target, alternate, sitecustomize)
    pins = driver.root / "preparation-pins.json"
    atomic_json(pins, {
        "schema_version": "bilun-preparation-pins-v3",
        "dependency_roots": [str(path) for path in roots],
        "immutable_inputs": prepare_single_vps_release._pin_inputs(
            set(roots), set(), dependency_roots=roots, allow_dependency_file_links=True,
        ),
        "external_state": {},
    })
    driver.paths["preparation_pins_path"] = pins
    driver.manifest["preparation_pins_sha256"] = hashlib.sha256(pins.read_bytes()).hexdigest()
    # Keep the shared fixture's OS/network doubles, but restore the actual
    # production verification hook used by the paired transaction.
    monkeypatch.setattr(
        driver, "_verify_pins", MethodType(paired_release.SingleVpsDriver._verify_pins, driver),
    )
    return host, target, intermediate, alternate, entry


def _mutate_chain(chain_pinned_host, mutation):
    _, target, intermediate, alternate, entry = chain_pinned_host
    if mutation == "target-bytes":
        target.write_bytes(b"changed after preparation\n")
    elif mutation == "target-mode":
        target.chmod(0o600)
    elif mutation == "intermediate-retarget":
        before = entry.read_bytes()
        intermediate.unlink()
        intermediate.symlink_to(alternate.name)
        assert entry.read_bytes() == before
        assert target.stat().st_mode == alternate.stat().st_mode
        assert intermediate.resolve() != target
    else:
        assert mutation == "intermediate-literal"
        before = entry.read_bytes()
        intermediate.unlink()
        intermediate.symlink_to(f"./{target.name}")
        assert entry.read_bytes() == before
        assert intermediate.resolve() == target


def test_v3_chain_passes_real_derive_install_startup_and_restore(chain_pinned_host, monkeypatch):
    host, target, intermediate, _, entry = chain_pinned_host
    driver, original, _ = host
    assert os.readlink(entry) == "../../x86_64-linux-gnu/libpython3.12.so.1"
    assert intermediate.is_symlink() and intermediate.resolve() == target
    assert entry.resolve() == target
    driver._verify_pins()
    candidate_receipt = driver.candidate_receipt.read_bytes()
    signing_key = driver.key.read_bytes()

    old = serving._activate(host, monkeypatch)
    asyncio.run(startup.startup())
    assert startup.is_cache_ready() is True
    activation = wavea_activation.activation_for_build(BUILD_ID)
    assert activation is not None
    assert activation.cache_sha256 == hashlib.sha256(
        driver.paths["live_cache_path"].read_bytes(),
    ).hexdigest()
    assert activation.cache_sha256 != original.cache_sha256
    receipt = json.loads((driver.root / "serving-receipt.json").read_text())
    assert receipt["schema_version"] == SERVING_RECEIPT_VERSION
    assert driver.candidate_receipt.read_bytes() == candidate_receipt
    assert driver.key.read_bytes() == signing_key

    driver.restore_old()
    assert driver.paths["live_cache_path"].read_bytes() == old
    assert driver.paths["live_cache_path"].stat().st_mode & 0o777 == 0o640
    assert driver.paths["frontend_current"].resolve().name == "old-frontend"
    assert not driver.paths["backend_dropin"].exists()
    assert not driver.paths["frontend_dropin"].exists()
    driver._verify_pins()


@pytest.mark.parametrize("gate", ["candidate", "preflight", "install", "start", "listeners"])
@pytest.mark.parametrize("mutation", [
    "target-bytes", "target-mode", "intermediate-retarget", "intermediate-literal",
])
def test_real_paired_gates_reject_chain_drift_before_external_actions(
    chain_pinned_host, monkeypatch, gate, mutation,
):
    host, _, _, _, _ = chain_pinned_host
    driver, _, _ = host
    driver._verify_pins()
    _mutate_chain(chain_pinned_host, mutation)
    # The fixture deliberately stubs candidate attestation for real cache
    # derivation. These negative cases use its actual fail-closed entry point.
    monkeypatch.setattr(
        driver, "_candidate_gate", MethodType(paired_release.SingleVpsDriver._candidate_gate, driver),
    )
    if gate == "start":
        driver.paths["frontend_current"].unlink()
        driver.paths["frontend_current"].symlink_to(driver.frontend)
    old_cache = driver.paths["live_cache_path"].read_bytes()
    old_link = os.readlink(driver.paths["frontend_current"])
    calls = []

    def external_action(*args, **kwargs):
        calls.append(args)
        pytest.fail("Dependency chain drift reached an external action")

    for name in ("_run", "observe_service", "fetch_successful_release_ci", "_replace_file", "_replace_link"):
        monkeypatch.setattr(paired_release, name, external_action)
    monkeypatch.setattr(driver, "stop_pair", external_action)
    monkeypatch.setattr(driver, "_require_maintenance", external_action)
    invoke = {
        "candidate": driver._candidate_gate,
        "preflight": driver.activation_gate,
        "install": driver.install_candidate,
        "start": driver.start_pair,
        "listeners": lambda: driver._verify_candidate_listeners([]),
    }[gate]
    with pytest.raises(ValueError, match="dependency bytes"):
        invoke()
    assert calls == []
    assert driver.paths["live_cache_path"].read_bytes() == old_cache
    assert os.readlink(driver.paths["frontend_current"]) == old_link
    assert not driver.paths["backend_dropin"].exists()
    assert not driver.paths["frontend_dropin"].exists()


@pytest.mark.parametrize("mutation", [
    "target-bytes", "target-mode", "intermediate-retarget", "intermediate-literal",
])
def test_changed_chain_does_not_block_real_old_pair_recovery(
    chain_pinned_host, monkeypatch, mutation,
):
    host, _, _, _, _ = chain_pinned_host
    driver, _, _ = host
    old = serving._activate(host, monkeypatch)
    _mutate_chain(chain_pinned_host, mutation)
    with pytest.raises(ValueError, match="dependency bytes"):
        driver._verify_pins()

    driver.restore_old()
    assert driver.paths["live_cache_path"].read_bytes() == old
    assert driver.paths["frontend_current"].resolve().name == "old-frontend"
    assert not driver.paths["backend_dropin"].exists()
    assert not driver.paths["frontend_dropin"].exists()
    calls = []
    monkeypatch.setattr(paired_release, "_run", lambda *args: calls.append(args))
    driver.start_pair()
    assert calls == [
        ("systemctl", "daemon-reload"),
        ("systemctl", "start", "bilun-backend.service", "bilun-frontend.service"),
    ]
