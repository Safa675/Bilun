"""Dependency-v2 preparation reuses the existing paired/serving receipt gates."""

from __future__ import annotations

import asyncio
import hashlib
from types import MethodType

import pytest

from scripts.deploy import paired_release, prepare_single_vps_release
from scripts.deploy.paired_release_transaction import atomic_json
from src.bilun.api import startup, wavea_activation
from tests.unit.deploy import test_serving_activation as serving
from tests.unit.deploy.test_verify_candidate_cache import BUILD_ID

host = serving.host


@pytest.fixture
def pinned_host(host, monkeypatch):
    driver, _, _ = host
    dependency = driver.root / "python-dependencies"
    dependency.mkdir()
    target = driver.root / "sitecustomize.py"
    target.write_bytes(b"# explicitly pinned external dependency\n")
    target.chmod(0o644)
    (dependency / "sitecustomize.py").symlink_to(target)
    roots = (dependency, target)
    pins = driver.root / "preparation-pins.json"
    atomic_json(pins, {
        "schema_version": "bilun-preparation-pins-v2",
        "dependency_roots": [str(path) for path in roots],
        "immutable_inputs": prepare_single_vps_release._pin_inputs(set(roots), set(), dependency_roots=roots),
        "external_state": {},
    })
    driver.paths["preparation_pins_path"] = pins
    driver.manifest["preparation_pins_sha256"] = hashlib.sha256(pins.read_bytes()).hexdigest()
    # The shared real-serving fixture stubs the pin hook. Restore the actual
    # bound production method while keeping its OS/network doubles unchanged.
    monkeypatch.setattr(driver, "_verify_pins", MethodType(paired_release.SingleVpsDriver._verify_pins, driver))
    return host, target


def test_v2_dependency_pins_pass_real_derive_install_startup_and_restore(pinned_host, monkeypatch):
    host, _ = pinned_host
    driver, original, _ = host
    driver._verify_pins()
    old = serving._activate(host, monkeypatch)
    asyncio.run(startup.startup())
    assert startup.is_cache_ready() is True
    activation = wavea_activation.activation_for_build(BUILD_ID)
    assert activation is not None
    assert activation.cache_sha256 != original.cache_sha256
    driver.restore_old()
    assert driver.paths["live_cache_path"].read_bytes() == old


@pytest.mark.parametrize("gate", ["candidate", "start", "listeners"])
@pytest.mark.parametrize("mutation", ["bytes", "mode"])
def test_real_paired_gates_reject_dependency_mutation_before_external_actions(pinned_host, monkeypatch, gate, mutation):
    host, target = pinned_host
    driver, _, _ = host
    driver._verify_pins()
    target.write_bytes(b"changed after prepare") if mutation == "bytes" else target.chmod(0o600)
    calls = []
    monkeypatch.setattr(paired_release, "_run", lambda *args: calls.append(args))
    if gate == "start":
        driver.paths["frontend_current"].unlink()
        driver.paths["frontend_current"].symlink_to(driver.frontend)
        invoke = driver.start_pair
    elif gate == "candidate":
        # Bypass only the shared fixture's candidate-gate stub, using the real
        # method whose first check must reject the dependency drift.
        invoke = lambda: paired_release.SingleVpsDriver._candidate_gate(driver)
    else:
        invoke = lambda: driver._verify_candidate_listeners([])
    with pytest.raises(ValueError, match="dependency bytes"):
        invoke()
    assert calls == []


def test_changed_candidate_dependency_does_not_block_old_pair_recovery(pinned_host, monkeypatch):
    host, target = pinned_host
    driver, _, _ = host
    target.write_bytes(b"broken candidate environment")
    calls = []
    monkeypatch.setattr(paired_release, "_run", lambda *args: calls.append(args))
    assert driver.paths["frontend_current"].resolve() != driver.frontend
    driver.start_pair()
    assert ("systemctl", "start", "bilun-backend.service", "bilun-frontend.service") in calls
