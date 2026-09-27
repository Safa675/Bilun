"""Launch the sealed rollback pair in an isolated network namespace.

This exercises the real recovery launcher, old runtime, cache, and API/asset
parity without touching production listeners or systemd. The public route
transaction and supervised systemd recovery remain separate release gates.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError

from scripts.deploy.observe_candidate_tuple import _loopback_listener_pid, _process_observation
from scripts.deploy.recover_old_pair import (
    _expected_environment,
    _probe_api,
    load_old_recovery_spec,
    verify_staged_old_recovery,
)
from scripts.deploy.rehearse_wavea_pair import fetch
from scripts.deploy.verify_candidate_cache import _stable_file_hash


def _ready(port: int, path: str, process: subprocess.Popen[bytes]) -> None:
    for _ in range(150):
        if process.poll() is not None:
            raise ValueError("Private old recovery listener exited before readiness")
        try:
            if fetch(port, path)[0] == 200:
                return
        except (OSError, URLError):
            pass
        time.sleep(0.2)
    raise ValueError("Private old recovery listener did not become ready")


def rehearse(manifest_path: Path, work_dir: Path) -> dict[str, object]:
    if os.readlink("/proc/self/ns/net") == os.readlink("/proc/1/ns/net"):
        raise ValueError("Old recovery rehearsal requires an isolated network namespace")
    if (
        not work_dir.is_absolute() or work_dir.is_symlink()
        or not work_dir.is_dir() or work_dir.stat().st_mode & 0o077
        or any(work_dir.iterdir())
    ):
        raise ValueError("Old recovery rehearsal needs an empty private directory")
    spec = load_old_recovery_spec(manifest_path, _stable_file_hash(manifest_path))
    verify_staged_old_recovery(spec)
    subprocess.run(["ip", "link", "set", "lo", "up"], check=True, capture_output=True)
    children: list[subprocess.Popen[bytes]] = []
    try:
        for role in ("backend", "frontend"):
            with (work_dir / f"{role}.log").open("xb") as log:
                child = subprocess.Popen(
                    [
                        str(spec.runner_python), str(spec.launcher_path), role,
                        "--spec", str(spec.manifest_path),
                        "--spec-sha256", spec.manifest_sha256,
                    ],
                    cwd=spec.recovery_root / role,
                    env={"PATH": "/usr/bin:/bin"},
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                    start_new_session=True,
                )
            children.append(child)
        _ready(8001, "/health", children[0])
        _ready(3000, "/login", children[1])
        for role, port, child in (("backend", 8001, children[0]), ("frontend", 3000, children[1])):
            observed = _process_observation(
                port, proc_root=Path("/proc"), listener_pid=_loopback_listener_pid
            )
            if (
                observed["listener_pid"] != child.pid
                or observed["cwd"] != str(spec.recovery_root / role)
                or observed["effective_environment_sha256"] != _expected_environment(spec, role)
            ):
                raise ValueError("Private old recovery process identity differs")
        patients, bills, api_sha = _probe_api(spec)
        verify_staged_old_recovery(spec)
        result: dict[str, object] = {
            "status": "private_old_recovery_rehearsed",
            "manifest_sha256": spec.manifest_sha256,
            "baseline_build_id": spec.baseline_build_id,
            "patient_rows": patients,
            "bill_rows": bills,
            "legacy_api_payload_sha256": api_sha,
            "public_activation_ready": False,
        }
        report = work_dir / "old-recovery-rehearsal.json"
        report.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        report.chmod(0o600)
        return result
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = rehearse(args.manifest, args.work_dir)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Private old recovery rehearsal failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
