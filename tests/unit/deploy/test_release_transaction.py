"""Disposable route and probe failure injection for the release transaction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.deploy import release_transaction as txn


class Interrupted(BaseException):
    """Model SIGTERM after a durable journal boundary or route reload."""


class FixtureRoute:
    def __init__(self, identity: txn.ReleaseIdentity) -> None:
        self.identity = identity
        self.current: txn.RouteName = "old"
        self.installs: list[txn.RouteName] = []
        self.interrupt_after_install: txn.RouteName | None = None
        self.fail_once: txn.RouteName | None = None
        self.fail_always: txn.RouteName | None = None
        self.noop_install: txn.RouteName | None = None

    def loaded_route_sha256(self) -> str:
        return getattr(self.identity, f"{self.current}_route_sha256")

    def install(self, route: txn.RouteName) -> None:
        self.installs.append(route)
        if self.fail_once == route or self.fail_always == route:
            self.fail_once = None
            raise RuntimeError("Simulated route reload failure")
        if self.noop_install != route:
            self.current = route
        if self.interrupt_after_install == route:
            self.interrupt_after_install = None
            raise Interrupted


class FixtureProbes:
    def __init__(self, identity: txn.ReleaseIdentity, route: FixtureRoute) -> None:
        self.identity = identity
        self.route = route
        self.gate_answers = [True, True]
        self.fail_barrier = False
        self.fail_candidate_public = False
        self.fail_old_public_after_restore = False
        self.fail_old_direct = False

    def activation_gate(self, identity: txn.ReleaseIdentity) -> bool:
        assert identity == self.identity
        return self.gate_answers.pop(0) if self.gate_answers else True

    def direct_tuple_sha256(self, route: str) -> str | None:
        if route == "old" and self.fail_old_direct:
            return None
        return getattr(self.identity, f"{route}_tuple_sha256")

    def public_tuple_sha256(self, route: str) -> str | None:
        if route == "candidate" and self.fail_candidate_public:
            return None
        if route == "old" and self.fail_old_public_after_restore and "old" in self.route.installs:
            return None
        return getattr(self.identity, f"{route}_tuple_sha256")

    def public_barrier_ready(self) -> bool:
        return self.route.current == "barrier" and not self.fail_barrier


def _identity() -> txn.ReleaseIdentity:
    return txn.ReleaseIdentity(
        release_id="wavea-ci-123",
        ci_head_sha="a" * 40,
        ci_run_id="123",
        manifest_sha256="b" * 64,
        legacy_attestation_sha256="c" * 64,
        old_tuple_sha256="d" * 64,
        candidate_tuple_sha256="e" * 64,
        old_route_sha256="1" * 64,
        barrier_route_sha256="2" * 64,
        candidate_route_sha256="3" * 64,
    )


def _fixture(tmp_path: Path):
    identity = _identity()
    route = FixtureRoute(identity)
    probes = FixtureProbes(identity, route)
    transaction = txn.ReleaseTransaction(
        lock_path=tmp_path / "release-state" / "release.lock",
        journal_path=tmp_path / "release-state" / "transaction.json",
    )
    return identity, route, probes, transaction


def _journal(transaction: txn.ReleaseTransaction) -> dict:
    return json.loads(transaction.journal_path.read_text())


def test_switch_and_explicit_rollback_are_exact_and_journaled(tmp_path: Path) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)

    assert transaction.activate(identity, route, probes) == "active"
    assert route.current == "candidate"
    assert route.installs == ["barrier", "candidate"]
    active = _journal(transaction)
    assert active["identity"]["ci_head_sha"] == identity.ci_head_sha
    assert active["identity"]["old_tuple_sha256"] == identity.old_tuple_sha256
    assert active["identity"]["legacy_attestation_sha256"] == identity.legacy_attestation_sha256
    assert [event["state"] for event in active["history"]] == [
        "prepared",
        "barrier_installing",
        "barrier",
        "candidate_installing",
        "active",
    ]
    assert transaction.recover(identity, route, probes) == "active"
    assert route.installs == ["barrier", "candidate"]

    assert transaction.recover(identity, route, probes, rollback_active=True) == "rolled_back"
    assert route.current == "old"
    assert route.installs[-2:] == ["barrier", "old"]
    assert _journal(transaction)["state"] == "rolled_back"
    assert transaction.recover(identity, route, probes) == "rolled_back"


def test_readiness_failure_never_changes_route_or_creates_journal(tmp_path: Path) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    probes.gate_answers = [False]

    with pytest.raises(txn.TransactionError, match="Activation identity gate failed"):
        transaction.activate(identity, route, probes)

    assert route.current == "old"
    assert route.installs == []
    assert not transaction.journal_path.exists()


def test_drift_after_barrier_restores_verified_old_route(tmp_path: Path) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    probes.gate_answers = [True, False]

    with pytest.raises(txn.TransactionError, match="recovery state: rolled_back"):
        transaction.activate(identity, route, probes)

    assert route.installs == ["barrier", "old"]
    assert route.current == "old"
    assert _journal(transaction)["state"] == "rolled_back"


@pytest.mark.parametrize("failing_route", ["barrier", "candidate"])
def test_failed_reload_restores_old_route(tmp_path: Path, failing_route: txn.RouteName) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    route.fail_once = failing_route

    with pytest.raises(txn.TransactionError, match="recovery state: rolled_back"):
        transaction.activate(identity, route, probes)

    assert route.current == "old"
    assert _journal(transaction)["state"] == "rolled_back"


def test_candidate_public_tuple_mismatch_restores_old_route(tmp_path: Path) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    probes.fail_candidate_public = True

    with pytest.raises(txn.TransactionError, match="recovery state: rolled_back"):
        transaction.activate(identity, route, probes)

    assert route.current == "old"
    assert _journal(transaction)["state"] == "rolled_back"


def test_old_public_probe_failure_retains_barrier_and_never_claims_rollback(
    tmp_path: Path,
) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    assert transaction.activate(identity, route, probes) == "active"
    probes.fail_old_public_after_restore = True

    assert transaction.recover(identity, route, probes, rollback_active=True) == "blocked"
    assert route.current == "barrier"
    assert _journal(transaction)["state"] == "blocked"
    assert _journal(transaction)["reason"] == "old_tuple_or_route_unverified"

    probes.fail_old_public_after_restore = False
    assert transaction.recover(identity, route, probes) == "rolled_back"
    assert route.current == "old"


def test_old_direct_probe_failure_retains_barrier(tmp_path: Path) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    assert transaction.activate(identity, route, probes) == "active"
    probes.fail_old_direct = True

    assert transaction.recover(identity, route, probes, rollback_active=True) == "blocked"
    assert route.current == "barrier"
    assert "old" not in route.installs


def test_old_reload_callback_returning_without_switch_keeps_barrier(tmp_path: Path) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    assert transaction.activate(identity, route, probes) == "active"
    route.noop_install = "old"

    assert transaction.recover(identity, route, probes, rollback_active=True) == "blocked"
    assert route.current == "barrier"
    assert _journal(transaction)["state"] == "blocked"


def test_unavailable_barrier_reports_blocked_without_claiming_safe_route(tmp_path: Path) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    assert transaction.activate(identity, route, probes) == "active"
    route.fail_always = "barrier"

    assert transaction.recover(identity, route, probes, rollback_active=True) == "blocked"
    journal = _journal(transaction)
    assert journal["state"] == "blocked"
    assert journal["reason"] == "barrier_unverified"
    assert journal["observed_route_sha256"] == identity.candidate_route_sha256


@pytest.mark.parametrize(
    ("interrupted_state", "expected_route", "expected_recovery"),
    [
        ("prepared", "old", "rolled_back"),
        ("barrier_installing", "old", "rolled_back"),
        ("barrier", "barrier", "rolled_back"),
        ("candidate_installing", "barrier", "rolled_back"),
        ("active", "candidate", "active"),
    ],
)
def test_interruption_after_each_durable_journal_boundary_is_recoverable(
    tmp_path: Path,
    interrupted_state: str,
    expected_route: txn.RouteName,
    expected_recovery: str,
) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)

    class InterruptedTransaction(txn.ReleaseTransaction):
        def _record(self, identity, state, route, *, reason=None):
            super()._record(identity, state, route, reason=reason)
            if state == interrupted_state:
                raise Interrupted

    interrupted = InterruptedTransaction(
        lock_path=transaction.lock_path, journal_path=transaction.journal_path
    )
    with pytest.raises(Interrupted):
        interrupted.activate(identity, route, probes)

    assert route.current == expected_route
    assert _journal(transaction)["state"] == interrupted_state
    assert transaction.recover(identity, route, probes) == expected_recovery
    assert transaction.recover(identity, route, probes) == expected_recovery


@pytest.mark.parametrize("interrupted_route", ["barrier", "candidate"])
def test_interruption_after_route_reload_recovers_via_barrier(
    tmp_path: Path, interrupted_route: txn.RouteName
) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    route.interrupt_after_install = interrupted_route
    with pytest.raises(Interrupted):
        transaction.activate(identity, route, probes)

    assert route.current == interrupted_route
    assert _journal(transaction)["state"] in {"barrier_installing", "candidate_installing"}
    assert transaction.recover(identity, route, probes) == "rolled_back"
    assert route.current == "old"


@pytest.mark.parametrize(
    "interrupted_state",
    ["rollback_barrier_installing", "rollback_barrier", "old_installing", "rolled_back"],
)
def test_interrupted_rollback_boundary_recovery_rechecks_old_public_tuple(
    tmp_path: Path, interrupted_state: str
) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    assert transaction.activate(identity, route, probes) == "active"

    class InterruptedRollback(txn.ReleaseTransaction):
        def _record(self, identity, state, route, *, reason=None):
            super()._record(identity, state, route, reason=reason)
            if state == interrupted_state:
                raise Interrupted

    interrupted = InterruptedRollback(
        lock_path=transaction.lock_path, journal_path=transaction.journal_path
    )
    with pytest.raises(Interrupted):
        interrupted.recover(identity, route, probes, rollback_active=True)

    assert _journal(transaction)["state"] == interrupted_state
    assert transaction.recover(identity, route, probes) == "rolled_back"
    assert route.current == "old"
    assert transaction.recover(identity, route, probes) == "rolled_back"


def test_unknown_or_wrong_identity_journal_fails_closed(tmp_path: Path) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    assert transaction.activate(identity, route, probes) == "active"
    changed = txn.ReleaseIdentity(**{**identity.__dict__, "manifest_sha256": "f" * 64})

    with pytest.raises(txn.TransactionError, match="identity differs"):
        transaction.recover(changed, route, probes)
    assert route.current == "candidate"

    journal = _journal(transaction)
    transaction.journal_path.write_text(
        json.dumps(journal).replace('"state": "active"', '"state": "impossible"')
    )
    with pytest.raises(txn.TransactionError, match="state is invalid"):
        transaction.recover(identity, route, probes)
    assert route.current == "candidate"


def test_second_transaction_cannot_cross_shared_lock(tmp_path: Path) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)

    with transaction._lock(), pytest.raises(txn.TransactionBusy):
        transaction.activate(identity, route, probes)

    assert route.current == "old"
    assert not transaction.journal_path.exists()


def test_non_old_initial_public_route_blocks_before_mutation(tmp_path: Path) -> None:
    identity, route, probes, transaction = _fixture(tmp_path)
    route.current = "candidate"

    with pytest.raises(txn.TransactionError, match="Observed old route differs"):
        transaction.activate(identity, route, probes)

    assert route.installs == []
    assert not transaction.journal_path.exists()
