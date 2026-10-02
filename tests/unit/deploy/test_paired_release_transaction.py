"""Disposable fault injection over the production transaction state machine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.deploy.paired_release_transaction import PairedReleaseError, PairedReleaseTransaction


class Driver:
    def __init__(self, failure=None, interrupt=False):
        self.failure, self.interrupt = failure, interrupt
        self.calls = []
        self.pair, self.route = "old", "old"

    def step(self, name):
        self.calls.append(name)
        if name == self.failure:
            self.failure = None
            raise KeyboardInterrupt() if self.interrupt else ValueError(name)

    def prepare(self): self.step("prepare"); return {}
    def activation_gate(self): self.step("gate")
    def maintenance(self): self.route = "barrier"; self.step("maintenance")
    def stop_pair(self): self.step("stop")
    def snapshot(self): self.step("snapshot")
    def derive_and_sign(self): self.step("derive"); return {"derivation": 1}
    def install_candidate(self): self.pair = "candidate"; self.step("install")
    def start_pair(self): self.step("start")
    def restore_old(self): self.pair = "old"; self.step("restore")
    def restore_route(self): self.route = "old"; self.step("publish")
    def rollback_gate(self): self.step("rollback-gate")
    def verify_pair(self, *, candidate, public):
        assert self.pair == ("candidate" if candidate else "old")
        self.step("verify-public" if public else "verify-private")


def transaction(tmp_path: Path, driver: Driver, *, name="release", identity="a" * 64):
    state = tmp_path / name
    state.mkdir(mode=0o700)
    lock_dir = tmp_path / "machine"
    lock_dir.mkdir(mode=0o700, exist_ok=True)
    return PairedReleaseTransaction(state_dir=state, lock_path=lock_dir / "release.lock",
                                    manifest_sha256=identity, driver=driver)


def test_happy_pair_activation_and_exact_rollback(tmp_path):
    driver = Driver()
    release = transaction(tmp_path, driver)
    assert release.prepare()["state"] == "prepared"
    assert release.activate()["state"] == "active"
    assert driver.calls.index("snapshot") < driver.calls.index("derive") < driver.calls.index("install")
    assert release.status()["live_readiness"] == "verified"
    assert release.rollback()["state"] == "rolled_back"
    assert (driver.pair, driver.route) == ("old", "old")
    assert release.rollback()["state"] == "rolled_back"
    with pytest.raises(PairedReleaseError, match="closed"):
        release.activate()


@pytest.mark.parametrize("failure", ["maintenance", "stop", "snapshot", "derive", "install",
                                     "start", "verify-private", "publish", "verify-public"])
def test_failure_at_every_boundary_restores_old_pair(tmp_path, failure):
    driver = Driver(failure)
    release = transaction(tmp_path, driver)
    release.prepare()
    with pytest.raises(PairedReleaseError, match="exact old pair restored"):
        release.activate()
    assert release.status()["state"] == "rolled_back"
    assert (driver.pair, driver.route) == ("old", "old")


@pytest.mark.parametrize("failure", ["maintenance", "stop", "snapshot", "derive", "install",
                                     "start", "verify-private", "publish", "verify-public"])
def test_interruption_retry_never_guesses_success(tmp_path, failure):
    driver = Driver(failure, interrupt=True)
    release = transaction(tmp_path, driver)
    release.prepare()
    with pytest.raises(KeyboardInterrupt):
        release.activate()
    assert release.activate()["state"] == "rolled_back"
    assert driver.pair == "old"


def test_gate_failure_never_enters_maintenance(tmp_path):
    driver = Driver("gate")
    release = transaction(tmp_path, driver)
    release.prepare()
    with pytest.raises(ValueError): release.activate()
    assert driver.calls == ["prepare", "gate"]
    assert release.status()["state"] == "prepared"


def test_repeated_prepare_rechecks_gate_and_status_reports_failed_observation(tmp_path):
    driver = Driver()
    release = transaction(tmp_path, driver)
    release.prepare()
    driver.failure = "gate"
    with pytest.raises(ValueError): release.prepare()
    driver.failure = "verify-public"
    assert release.status()["live_readiness"] == "unverified"


def test_rollback_failure_stays_blocked_and_retry_recovers(tmp_path):
    driver = Driver()
    release = transaction(tmp_path, driver)
    release.prepare(); release.activate()
    driver.failure = "restore"
    with pytest.raises(PairedReleaseError, match="Rollback blocked"):
        release.rollback()
    assert release.status()["state"] == "blocked"
    assert driver.route == "barrier"
    assert release.rollback()["state"] == "rolled_back"


def test_invalid_journal_history_fails_closed(tmp_path):
    release = transaction(tmp_path, Driver())
    release.prepare()
    journal = json.loads(release.journal_path.read_text())
    journal.update(state="active", events=["prepared", "active"])
    release.journal_path.write_text(json.dumps(journal))
    with pytest.raises(PairedReleaseError, match="transition"):
        release.activate()


def test_newer_release_prevents_stale_rollback(tmp_path):
    first = transaction(tmp_path, Driver())
    first.prepare(); first.activate()
    second = transaction(tmp_path, Driver(), name="release2", identity="b" * 64)
    second.prepare(); second.activate()
    with pytest.raises(PairedReleaseError, match="newer release"):
        first.rollback()


def test_explicit_rollback_preflight_refuses_foreign_change_without_outage(tmp_path):
    driver = Driver()
    release = transaction(tmp_path, driver)
    release.prepare(); release.activate()
    before = list(driver.calls)
    driver.failure = "rollback-gate"
    with pytest.raises(ValueError): release.rollback()
    assert driver.calls == before + ["rollback-gate"]
    assert (driver.pair, driver.route) == ("candidate", "old")


def test_claim_crash_before_maintenance_does_not_strand_machine(tmp_path):
    first = transaction(tmp_path, Driver())
    first.prepare()
    with first._locked(): first._claim()
    second = transaction(tmp_path, Driver(), name="next", identity="b" * 64)
    second.prepare()
    assert second.activate()["state"] == "active"
