"""Fail-closed route transaction core for a staged Bilun release.

This module deliberately has no command-line entry point or Caddy adapter. A
future adapter must supply independently attested route, tuple, and release
observations; tests exercise the exact same transition and recovery code on
disposable fixtures.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

RouteName = Literal["old", "barrier", "candidate"]
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CODE_SHA = re.compile(r"[0-9a-f]{40}\Z")
_RELEASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_STATES = frozenset(
    {
        "prepared",
        "barrier_installing",
        "barrier",
        "candidate_installing",
        "active",
        "rollback_barrier_installing",
        "rollback_barrier",
        "old_recovering",
        "old_recovered",
        "old_installing",
        "rolled_back",
        "blocked",
    }
)


class TransactionError(RuntimeError):
    """A release transaction failed without claiming an unverified route."""


class TransactionBusy(TransactionError):
    """Another release or rollback holds the shared lock."""


@dataclass(frozen=True)
class ReleaseIdentity:
    release_id: str
    ci_head_sha: str
    ci_run_id: str
    manifest_sha256: str
    legacy_attestation_sha256: str
    old_tuple_sha256: str
    candidate_tuple_sha256: str
    old_route_sha256: str
    barrier_route_sha256: str
    candidate_route_sha256: str
    old_recovery_manifest_sha256: str

    def __post_init__(self) -> None:
        if not _RELEASE_ID.fullmatch(self.release_id):
            raise ValueError("Invalid release ID")
        if not _CODE_SHA.fullmatch(self.ci_head_sha):
            raise ValueError("Invalid CI head SHA")
        if not self.ci_run_id.isdecimal() or int(self.ci_run_id) < 1:
            raise ValueError("Invalid CI run ID")
        for name in (
            "manifest_sha256",
            "legacy_attestation_sha256",
            "old_tuple_sha256",
            "candidate_tuple_sha256",
            "old_route_sha256",
            "barrier_route_sha256",
            "candidate_route_sha256",
            "old_recovery_manifest_sha256",
        ):
            if not _SHA256.fullmatch(getattr(self, name)):
                raise ValueError(f"Invalid {name}")
        if (
            len(
                {
                    self.old_route_sha256,
                    self.barrier_route_sha256,
                    self.candidate_route_sha256,
                }
            )
            != 3
        ):
            raise ValueError("Old, barrier, and candidate routes must be distinct")


class RouteDriver(Protocol):
    def loaded_route_sha256(self) -> str | None:
        """Return the currently serving route digest, not a file's digest."""

    def installed_route_sha256(self) -> str | None:
        """Return the sealed route saved for a future Caddy restart."""

    def install(self, route: RouteName) -> None:
        """Install and reload one already validated route configuration."""


class ReleaseProbes(Protocol):
    def activation_gate(self, identity: ReleaseIdentity) -> bool:
        """Recheck CI head, manifest, artifacts, inputs, and rollback evidence."""

    def direct_tuple_sha256(self, route: Literal["old", "candidate"]) -> str | None:
        """Probe both private service listeners and their complete tuple."""

    def public_tuple_sha256(self, route: Literal["old", "candidate"]) -> str | None:
        """Probe the public route and both service/build/cache identities."""

    def public_barrier_ready(self) -> bool:
        """Verify public API and pages are blocked, even if a listener died."""

    def recover_old_tuple(self) -> dict[str, str] | None:
        """Under the barrier, restore and attest the protected old pair."""


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise TransactionError("Duplicate journal field")
        value[key] = item
    return value


class ReleaseTransaction:
    """One locked, journaled public route switch with deterministic recovery."""

    def __init__(self, *, lock_path: Path, journal_path: Path) -> None:
        if lock_path == journal_path or lock_path.parent != journal_path.parent:
            raise ValueError("Lock and journal must be distinct files in one directory")
        self.lock_path = lock_path
        self.journal_path = journal_path

    @contextmanager
    def _lock(self):
        directory = self.lock_path.parent
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink():
            raise TransactionError("Release state directory is a symlink")
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise TransactionBusy("Release transaction lock is held") from exc
            yield
        finally:
            os.close(fd)

    def _read(self, identity: ReleaseIdentity) -> dict | None:
        if not self.journal_path.exists() and not self.journal_path.is_symlink():
            return None
        if self.journal_path.is_symlink() or not self.journal_path.is_file():
            raise TransactionError("Release journal is not a regular file")
        try:
            value = json.loads(self.journal_path.read_text(), object_pairs_hook=_unique_pairs)
        except (OSError, ValueError) as exc:
            raise TransactionError("Release journal is unreadable") from exc
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "sequence",
            "identity",
            "state",
            "observed_route_sha256",
            "old_target_tuple_sha256",
            "old_recovery_artifact_sha256",
            "reason",
            "updated_at_utc",
            "history",
        }:
            raise TransactionError("Release journal has an unexpected schema")
        if value["schema_version"] != 2 or value["identity"] != asdict(identity):
            raise TransactionError("Release journal identity differs from requested release")
        if (
            type(value["sequence"]) is not int
            or value["sequence"] < 1
            or not isinstance(value["state"], str)
            or value["state"] not in _STATES
        ):
            raise TransactionError("Release journal state is invalid")
        route = value["observed_route_sha256"]
        if route is not None and (not isinstance(route, str) or not _SHA256.fullmatch(route)):
            raise TransactionError("Release journal route identity is invalid")
        if (
            not isinstance(value["old_target_tuple_sha256"], str)
            or not _SHA256.fullmatch(value["old_target_tuple_sha256"])
        ):
            raise TransactionError("Release journal old target identity is invalid")
        artifact = value["old_recovery_artifact_sha256"]
        if artifact is not None and (not isinstance(artifact, str) or not _SHA256.fullmatch(artifact)):
            raise TransactionError("Release journal old recovery artifact is invalid")
        if artifact is not None and artifact != identity.old_recovery_manifest_sha256:
            raise TransactionError("Release journal old recovery artifact differs")
        if (value["old_target_tuple_sha256"] == identity.old_tuple_sha256) != (artifact is None):
            raise TransactionError("Release journal old target lacks matching recovery evidence")
        if value["reason"] is not None and not isinstance(value["reason"], str):
            raise TransactionError("Release journal reason is invalid")
        if not isinstance(value["updated_at_utc"], str):
            raise TransactionError("Release journal timestamp is invalid")
        if not isinstance(value["history"], list) or len(value["history"]) != value["sequence"]:
            raise TransactionError("Release journal history is invalid")
        for number, event in enumerate(value["history"], 1):
            if not isinstance(event, dict) or set(event) != {
                "sequence",
                "state",
                "observed_route_sha256",
                "old_target_tuple_sha256",
                "old_recovery_artifact_sha256",
                "reason",
                "updated_at_utc",
            }:
                raise TransactionError("Release journal event is invalid")
            if (
                type(event["sequence"]) is not int
                or event["sequence"] != number
                or not isinstance(event["state"], str)
                or event["state"] not in _STATES
                or not isinstance(event["updated_at_utc"], str)
                or event["observed_route_sha256"] is not None
                and (
                    not isinstance(event["observed_route_sha256"], str)
                    or not _SHA256.fullmatch(event["observed_route_sha256"])
                )
                or not isinstance(event["old_target_tuple_sha256"], str)
                or not _SHA256.fullmatch(event["old_target_tuple_sha256"])
                or event["old_recovery_artifact_sha256"] is not None
                and (
                    not isinstance(event["old_recovery_artifact_sha256"], str)
                    or not _SHA256.fullmatch(event["old_recovery_artifact_sha256"])
                )
                or (event["old_target_tuple_sha256"] == identity.old_tuple_sha256)
                != (event["old_recovery_artifact_sha256"] is None)
                or event["old_recovery_artifact_sha256"] not in (
                    None, identity.old_recovery_manifest_sha256
                )
                or event["reason"] is not None
                and not isinstance(event["reason"], str)
            ):
                raise TransactionError("Release journal event sequence is invalid")
        if any(
            value[key] != value["history"][-1][key]
            for key in (
                "sequence", "state", "observed_route_sha256", "old_target_tuple_sha256",
                "old_recovery_artifact_sha256", "reason", "updated_at_utc",
            )
        ):
            raise TransactionError("Release journal head differs from its last event")
        return value

    def _record(
        self,
        identity: ReleaseIdentity,
        state: str,
        route: RouteDriver,
        *,
        reason: str | None = None,
        old_target_tuple_sha256: str | None = None,
        old_recovery_artifact_sha256: str | None = None,
    ) -> None:
        previous = self._read(identity)
        loaded = route.loaded_route_sha256()
        if loaded is not None and not _SHA256.fullmatch(loaded):
            raise TransactionError("Loaded route identity is invalid")
        old_target = old_target_tuple_sha256 or (
            identity.old_tuple_sha256 if previous is None
            else previous["old_target_tuple_sha256"]
        )
        artifact = old_recovery_artifact_sha256
        if artifact is None and previous is not None and old_target == previous["old_target_tuple_sha256"]:
            artifact = previous["old_recovery_artifact_sha256"]
        if (
            not _SHA256.fullmatch(old_target)
            or (old_target == identity.old_tuple_sha256) != (artifact is None)
            or artifact is not None and not _SHA256.fullmatch(artifact)
            or artifact is not None and artifact != identity.old_recovery_manifest_sha256
        ):
            raise TransactionError("Old rollback target or recovery evidence is invalid")
        event = {
            "sequence": 1 if previous is None else previous["sequence"] + 1,
            "state": state,
            "observed_route_sha256": loaded,
            "old_target_tuple_sha256": old_target,
            "old_recovery_artifact_sha256": artifact,
            "reason": reason,
            "updated_at_utc": datetime.now(UTC).isoformat(),
        }
        journal = {
            "schema_version": 2,
            "sequence": event["sequence"],
            "identity": asdict(identity),
            "state": state,
            "observed_route_sha256": loaded,
            "old_target_tuple_sha256": old_target,
            "old_recovery_artifact_sha256": artifact,
            "reason": reason,
            "updated_at_utc": event["updated_at_utc"],
            "history": ([] if previous is None else previous["history"]) + [event],
        }
        contents = json.dumps(journal, sort_keys=True, separators=(",", ":")) + "\n"
        descriptor, temporary = tempfile.mkstemp(
            prefix=".release-journal-", dir=self.journal_path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(contents)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.journal_path)
            parent = os.open(self.journal_path.parent, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _verify_tuple(
        identity: ReleaseIdentity,
        route: RouteDriver,
        probes: ReleaseProbes,
        name: Literal["old", "candidate"],
        *,
        public: bool,
        expected_tuple: str | None = None,
    ) -> None:
        expected = expected_tuple or getattr(identity, f"{name}_tuple_sha256")
        observed = probes.public_tuple_sha256(name) if public else probes.direct_tuple_sha256(name)
        if observed != expected:
            raise TransactionError(f"{name} {'public' if public else 'direct'} tuple unverified")
        if public and (
            route.loaded_route_sha256() != getattr(identity, f"{name}_route_sha256")
            or route.installed_route_sha256() != getattr(identity, f"{name}_route_sha256")
        ):
            raise TransactionError(f"{name} public route unverified")

    @staticmethod
    def _verify_barrier(
        identity: ReleaseIdentity, route: RouteDriver, probes: ReleaseProbes
    ) -> None:
        if (
            route.loaded_route_sha256() != identity.barrier_route_sha256
            or route.installed_route_sha256() != identity.barrier_route_sha256
            or not probes.public_barrier_ready()
        ):
            raise TransactionError("Public maintenance barrier unverified")

    def _rollback_locked(
        self, identity: ReleaseIdentity, route: RouteDriver, probes: ReleaseProbes
    ) -> str:
        try:
            self._record(identity, "rollback_barrier_installing", route)
            route.install("barrier")
            self._verify_barrier(identity, route, probes)
            self._record(identity, "rollback_barrier", route)
            previous = self._read(identity)
            assert previous is not None
            old_target = previous["old_target_tuple_sha256"]
            observed_old = probes.direct_tuple_sha256("old")
            if observed_old == identity.old_tuple_sha256:
                old_target = identity.old_tuple_sha256
                old_artifact = None
            elif observed_old == old_target and previous["old_recovery_artifact_sha256"] is not None:
                old_artifact = previous["old_recovery_artifact_sha256"]
            else:
                self._record(identity, "old_recovering", route)
                recovered = probes.recover_old_tuple()
                if (
                    not isinstance(recovered, dict)
                    or set(recovered) != {"tuple_sha256", "artifact_sha256"}
                    or not all(
                        isinstance(value, str) and _SHA256.fullmatch(value)
                        for value in recovered.values()
                    )
                    or recovered["tuple_sha256"] == identity.old_tuple_sha256
                    or recovered["artifact_sha256"] != identity.old_recovery_manifest_sha256
                    or probes.direct_tuple_sha256("old") != recovered["tuple_sha256"]
                ):
                    raise TransactionError("Protected old recovery tuple unverified")
                old_target = recovered["tuple_sha256"]
                old_artifact = recovered["artifact_sha256"]
                self._record(
                    identity, "old_recovered", route,
                    old_target_tuple_sha256=old_target,
                    old_recovery_artifact_sha256=old_artifact,
                )
            self._verify_tuple(
                identity, route, probes, "old", public=False, expected_tuple=old_target
            )
            self._record(
                identity, "old_installing", route,
                old_target_tuple_sha256=old_target,
                old_recovery_artifact_sha256=old_artifact,
            )
            route.install("old")
            self._verify_tuple(
                identity, route, probes, "old", public=True, expected_tuple=old_target
            )
            self._record(identity, "rolled_back", route)
            return "rolled_back"
        except Exception:
            # An old-route callback can return successfully while serving the
            # wrong tuple. Reinstall the barrier and verify it before recording
            # a blocked outcome; never call that a successful rollback.
            try:
                self._record(identity, "rollback_barrier_installing", route)
                route.install("barrier")
                self._verify_barrier(identity, route, probes)
                self._record(identity, "blocked", route, reason="old_tuple_or_route_unverified")
            except Exception:
                self._record(identity, "blocked", route, reason="barrier_unverified")
            return "blocked"

    def activate(self, identity: ReleaseIdentity, route: RouteDriver, probes: ReleaseProbes) -> str:
        """Switch only after exact preflight; rollback on ordinary failures."""
        with self._lock():
            previous = self._read(identity)
            if previous is not None:
                if previous["state"] == "active":
                    self._verify_tuple(identity, route, probes, "candidate", public=True)
                    return "active"
                raise TransactionError("Existing transaction requires recovery or a new release")
            if (
                route.loaded_route_sha256() != identity.old_route_sha256
                or route.installed_route_sha256() != identity.old_route_sha256
            ):
                raise TransactionError("Observed old route differs from release manifest")
            if not probes.activation_gate(identity):
                raise TransactionError("Activation identity gate failed")
            self._verify_tuple(identity, route, probes, "old", public=False)
            self._verify_tuple(identity, route, probes, "old", public=True)
            self._verify_tuple(identity, route, probes, "candidate", public=False)
            self._record(identity, "prepared", route)
            try:
                self._record(identity, "barrier_installing", route)
                route.install("barrier")
                self._verify_barrier(identity, route, probes)
                self._record(identity, "barrier", route)
                if not probes.activation_gate(identity):
                    raise TransactionError("Activation identity drifted after barrier")
                self._verify_tuple(identity, route, probes, "old", public=False)
                self._verify_tuple(identity, route, probes, "candidate", public=False)
                self._record(identity, "candidate_installing", route)
                route.install("candidate")
                self._verify_tuple(identity, route, probes, "candidate", public=True)
                self._record(identity, "active", route)
                return "active"
            except Exception as exc:
                outcome = self._rollback_locked(identity, route, probes)
                raise TransactionError(f"Activation failed; recovery state: {outcome}") from exc

    def recover(
        self,
        identity: ReleaseIdentity,
        route: RouteDriver,
        probes: ReleaseProbes,
        *,
        rollback_active: bool = False,
    ) -> str:
        """Reconcile an interrupted transaction or explicitly roll back active."""
        with self._lock():
            previous = self._read(identity)
            if previous is None:
                raise TransactionError("No release transaction journal exists")
            if previous["state"] == "active" and not rollback_active:
                try:
                    self._verify_tuple(identity, route, probes, "candidate", public=True)
                    return "active"
                except TransactionError:
                    pass
            if previous["state"] == "rolled_back" and not rollback_active:
                try:
                    self._verify_tuple(
                        identity, route, probes, "old", public=True,
                        expected_tuple=previous["old_target_tuple_sha256"],
                    )
                    return "rolled_back"
                except TransactionError:
                    pass
            if (
                previous["state"] in {"prepared", "barrier_installing"}
                and route.loaded_route_sha256() == identity.old_route_sha256
            ):
                try:
                    route.install("old")
                    self._verify_tuple(identity, route, probes, "old", public=True)
                    self._record(identity, "rolled_back", route)
                    return "rolled_back"
                except Exception:
                    pass
            return self._rollback_locked(identity, route, probes)
