"""One durable maintenance transaction for an existing :8001/:3000 pair.

Every mutation follows a durable intent. Interrupted attempts recover the exact
stopped pair on retry; they never infer a successful activation from processes.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from scripts.deploy.issue_wavea_activation import _new_private_file
from scripts.deploy.release_sidecar import _load_private_json


class PairedReleaseError(RuntimeError):
    pass


class PairDriver(Protocol):
    def prepare(self) -> dict: ...
    def activation_gate(self) -> None: ...
    def maintenance(self) -> None: ...
    def stop_pair(self) -> None: ...
    def snapshot(self) -> None: ...
    def derive_and_sign(self) -> dict: ...
    def install_candidate(self) -> None: ...
    def start_pair(self) -> None: ...
    def verify_pair(self, *, candidate: bool, public: bool) -> None: ...
    def restore_old(self) -> None: ...
    def restore_route(self) -> None: ...
    def rollback_gate(self) -> None: ...


_FORWARD = (
    "prepared", "entering_maintenance", "stopping", "snapshotting", "deriving",
    "installing", "starting", "verifying", "publishing", "active",
)
_RECOVERY = (
    "rollback_maintenance", "rollback_stopping", "restoring", "rollback_starting",
    "rollback_verifying", "rollback_publishing", "rolled_back",
)


def atomic_json(path: Path, value: dict) -> None:
    """Durably replace a private journal; never follow a link."""
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise PairedReleaseError("Journal target is not an independent regular file")
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    _new_private_file(temporary, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode())
    try:
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


class PairedReleaseTransaction:
    def __init__(self, *, state_dir: Path, lock_path: Path, manifest_sha256: str,
                 driver: PairDriver, snapshot_journal_path: Path | None = None,
                 snapshot_journal_identity_sha256: str | None = None):
        self.state_dir, self.lock_path = state_dir, lock_path
        self.journal_path = state_dir / "transaction.json"
        self.owner_path = lock_path.parent / "paired-release-owner.json"
        self.manifest_sha256, self.driver = manifest_sha256, driver
        if (snapshot_journal_path is None) != (snapshot_journal_identity_sha256 is None):
            raise PairedReleaseError("Snapshot handoff requires its exact journal and identity")
        self.snapshot_handoff = ({"journal_path": str(snapshot_journal_path),
                                  "identity_sha256": snapshot_journal_identity_sha256}
                                 if snapshot_journal_path is not None else None)
        if hasattr(driver, "bind_owner_check"):
            driver.bind_owner_check(self._assert_owner, {
                "manifest_sha256": self.manifest_sha256, "state_dir": str(self.state_dir),
            })

    def _owner(self) -> dict | None:
        if not os.path.lexists(self.owner_path):
            return None
        value, _ = _load_private_json(self.owner_path, root=self.owner_path.parent)
        if set(value) != {"manifest_sha256", "state_dir"}:
            raise PairedReleaseError("Machine release ownership record is malformed")
        return value

    def _assert_owner(self) -> None:
        if self._owner() != {"manifest_sha256": self.manifest_sha256,
                             "state_dir": str(self.state_dir)}:
            raise PairedReleaseError("A newer release owns this pair; refusing stale rollback")

    def _claim(self) -> None:
        if self.snapshot_handoff is not None:
            from scripts.deploy.snapshot_maintenance import adopt_held_snapshot
            adopt_held_snapshot(
                Path(self.snapshot_handoff["journal_path"]),
                expected_identity_sha256=self.snapshot_handoff["identity_sha256"],
                expected_manifest_sha256=self.manifest_sha256, state_dir=self.state_dir,
            )
            self._assert_owner()
            return
        owner = self._owner()
        if owner and owner["manifest_sha256"] != self.manifest_sha256:
            directory = Path(owner["state_dir"])
            previous, _ = _load_private_json(directory / "transaction.json", root=directory)
            if (previous.get("state") not in {"prepared", "active", "rolled_back"}
                    or (previous.get("state") == "prepared" and previous.get("snapshot_handoff"))):
                raise PairedReleaseError("Another interrupted release needs recovery first")
        atomic_json(self.owner_path, {"manifest_sha256": self.manifest_sha256,
                                     "state_dir": str(self.state_dir)})

    @contextmanager
    def _locked(self):
        for path in (self.state_dir, self.lock_path.parent):
            if (not path.is_absolute() or path.is_symlink() or not path.is_dir()
                    or path.stat().st_mode & 0o077):
                raise PairedReleaseError("Release state and lock directories must be private")
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise PairedReleaseError("Another paired release holds the machine lock") from exc
            yield
        finally:
            os.close(fd)

    def _read(self) -> dict | None:
        if not os.path.lexists(self.journal_path):
            return None
        value, _ = _load_private_json(self.journal_path, root=self.state_dir)
        fields = {"schema_version", "manifest_sha256", "state", "events", "timings_seconds", "reason"}
        if self.snapshot_handoff is not None:
            fields.add("snapshot_handoff")
        if (set(value) != fields
                or value["schema_version"] != "bilun-paired-transaction-v1"
                or value["manifest_sha256"] != self.manifest_sha256
                or not isinstance(value["events"], list)
                or not value["events"] or value["events"][-1] != value["state"]
                or not isinstance(value["timings_seconds"], dict)):
            raise PairedReleaseError("Paired release journal identity/schema differs")
        if self.snapshot_handoff is not None and value["snapshot_handoff"] != self.snapshot_handoff:
            raise PairedReleaseError("Paired snapshot handoff identity differs")
        if value["state"] not in {
            "prepared", "entering_maintenance", "stopping", "snapshotting",
            "deriving", "installing", "starting", "verifying", "publishing",
            "active", "rollback_maintenance", "rollback_stopping", "restoring",
            "rollback_starting", "rollback_verifying", "rollback_publishing",
            "rolled_back", "blocked",
        }:
            raise PairedReleaseError("Unknown paired release journal state")
        if value["events"][0] != "prepared":
            raise PairedReleaseError("Release journal does not begin at preparation")
        for previous, current in zip(value["events"], value["events"][1:]):
            normal = any((previous, current) in tuple(zip(chain, chain[1:]))
                         for chain in (_FORWARD, _RECOVERY))
            recovery = current == "rollback_maintenance" and previous != "rolled_back"
            blocked = current == "blocked" and previous in _RECOVERY
            if not (normal or recovery or blocked):
                raise PairedReleaseError("Release journal transition history is invalid")
        return value

    def _record(self, state: str, *, reason: str | None = None,
                timings: dict | None = None) -> dict:
        value = self._read() or {
            "schema_version": "bilun-paired-transaction-v1",
            "manifest_sha256": self.manifest_sha256,
            "events": [], "timings_seconds": {},
        }
        value.update(state=state, reason=reason)
        if self.snapshot_handoff is not None:
            value["snapshot_handoff"] = self.snapshot_handoff
        value["events"].append(state)
        value["timings_seconds"].update(timings or {})
        atomic_json(self.journal_path, value)
        return value

    def status(self) -> dict:
        with self._locked():
            value = self._read()
            if value is None:
                return {"state": "unprepared", "manifest_sha256": self.manifest_sha256,
                        "live_readiness": "not_checked"}
            result = {**value, "live_readiness": "maintenance_or_recovery_required"}
            if value["state"] == "prepared" and self.snapshot_handoff is not None:
                from scripts.deploy.snapshot_maintenance import inspect_snapshot
                result["snapshot"] = inspect_snapshot(Path(self.snapshot_handoff["journal_path"]))
                result["live_readiness"] = "not_checked"
                return result
            if value["state"] in {"prepared", "active", "rolled_back"}:
                try:
                    self.driver.verify_pair(candidate=value["state"] == "active", public=True)
                    result["live_readiness"] = "verified"
                except Exception as exc:
                    result["live_readiness"] = "unverified"
                    result["observation_error"] = type(exc).__name__
            return result

    def prepare(self) -> dict:
        with self._locked():
            previous = self._read()
            if previous is not None:
                if previous["state"] == "prepared":
                    self.driver.activation_gate()
                return previous
            self.driver.prepare()
            return self._record("prepared")

    def _rollback(self) -> dict:
        try:
            self._record("rollback_maintenance")
            self._assert_owner()
            self.driver.maintenance()
            self._record("rollback_stopping")
            self._assert_owner()
            self.driver.stop_pair()
            self._record("restoring")
            self._assert_owner()
            self.driver.restore_old()
            self._record("rollback_starting")
            self._assert_owner()
            self.driver.start_pair()
            self._record("rollback_verifying")
            self._assert_owner()
            self.driver.verify_pair(candidate=False, public=False)
            self._record("rollback_publishing")
            self._assert_owner()
            self.driver.restore_route()
            self._assert_owner()
            self.driver.verify_pair(candidate=False, public=True)
            return self._record("rolled_back")
        except Exception as exc:
            # Ownership loss forbids even a defensive stop of someone else's pair.
            try:
                self._assert_owner()
                self.driver.maintenance()
            except Exception:
                pass
            try:
                self._assert_owner()
                self.driver.stop_pair()
            except Exception:
                pass
            self._record("blocked", reason=f"{type(exc).__name__}: {str(exc)[:500]}")
            raise PairedReleaseError("Rollback blocked; inspect private state, maintenance remains required") from exc

    def activate(self) -> dict:
        with self._locked():
            value = self._read()
            if value is None:
                raise PairedReleaseError("Prepare this release first")
            if value["state"] == "active":
                self._assert_owner()
                self.driver.verify_pair(candidate=True, public=True)
                return value
            if value["state"] == "rolled_back":
                raise PairedReleaseError("Rolled-back bundle is closed; prepare a fresh release directory")
            if value["state"] != "prepared":
                self._assert_owner()
                return self._rollback()
            # A failed pre-maintenance gate leaves the current pair untouched.
            self.driver.activation_gate()
            self._claim()
            started = time.monotonic()
            try:
                for state, action in (
                    ("entering_maintenance", self.driver.maintenance),
                    ("stopping", self.driver.stop_pair),
                    ("snapshotting", self.driver.snapshot),
                ):
                    self._record(state)
                    self._assert_owner()
                    action()
                self._record("deriving")
                self._assert_owner()
                timings = self.driver.derive_and_sign()
                self._record("installing", timings=timings)
                self._assert_owner()
                self.driver.install_candidate()
                self._record("starting")
                self._assert_owner()
                readiness_started = time.monotonic()
                self.driver.start_pair()
                self._record("verifying", timings={"service_readiness": time.monotonic() - readiness_started})
                self._assert_owner()
                self.driver.verify_pair(candidate=True, public=False)
                self._record("publishing")
                self._assert_owner()
                self.driver.restore_route()
                self._assert_owner()
                self.driver.verify_pair(candidate=True, public=True)
                return self._record("active", timings={"maintenance_total": time.monotonic() - started})
            except Exception:
                self._rollback()
                raise PairedReleaseError("Activation failed; exact old pair restored") from None

    def rollback(self) -> dict:
        with self._locked():
            value = self._read()
            if value is None or (value["state"] == "prepared" and self.snapshot_handoff is None):
                raise PairedReleaseError("No activation has started")
            if value["state"] == "prepared":
                self._claim()
            self._assert_owner()
            if value["state"] == "rolled_back":
                self.driver.verify_pair(candidate=False, public=True)
                return value
            if value["state"] == "active":
                # Reject unrelated operator changes without causing an outage.
                self.driver.rollback_gate()
            return self._rollback()
