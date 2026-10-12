"""Start one-job laptop CI runners while GitHub has jobs waiting for them.

Meant for the systemd user timer in tools/ci/systemd. Each run asks GitHub which jobs are
queued for the ``bilun-laptop-ci`` label. Only while some are, and no runner with that label
is online, it starts the reviewed ``laptop_runner.py`` for exactly one job and asks again. It
registers nothing itself, holds no credentials of its own, and leaves no runner behind once
the queue is empty.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPOSITORY = "Safa675/Bilun"
LABEL = "bilun-laptop-ci"
RUNNER_LABELS = {"self-hosted", "linux", "x64", LABEL}  # what laptop_runner.py registers, lowercase
RUNNER = Path(__file__).with_name("laptop_runner.py")
STALE_AFTER = timedelta(days=1)  # e.g. a 2026-08-06 run that still reads "queued" and has no jobs
POLL_SECONDS = 10
CALL_TIMEOUT = 60  # one gh or docker call; a hung call must not stall the timer for good


def github(path):
    """Read-only GitHub REST call through the existing `gh` login. Any failure is a RuntimeError."""
    name = path.split("?")[0]
    try:
        result = subprocess.run(["gh", "api", path], text=True, capture_output=True,
                                check=False, timeout=CALL_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"gh api {name} did not run: {error}") from error
    if result.returncode:
        raise RuntimeError(f"GitHub API failed for {name}: {result.stderr.strip()[:200]}")
    try:
        return json.loads(result.stdout)
    except ValueError as error:
        raise RuntimeError(f"GitHub API returned something that is not JSON for {name}") from error


def takes_our_runner(job):
    """True when every label the job asks for is one our runner registers."""
    wanted = {label.lower() for label in job["labels"]}
    return LABEL in wanted and wanted <= RUNNER_LABELS


def queued_jobs(read, now):
    """Jobs in recent runs that wait for a runner like ours."""
    waiting = []
    for status in ("queued", "in_progress"):  # a run turns in_progress as soon as one job starts
        for run in read(f"repos/{REPOSITORY}/actions/runs?status={status}&per_page=50")["workflow_runs"]:
            updated = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
            if now - updated > STALE_AFTER:
                continue
            jobs = read(f"repos/{REPOSITORY}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
            waiting += [job for job in jobs if job["status"] == "queued" and takes_our_runner(job)]
    return waiting


def online_runners(read):
    runners = read(f"repos/{REPOSITORY}/actions/runners?per_page=100")["runners"]
    return [runner for runner in runners
            if runner["status"] == "online" and LABEL in {label["name"] for label in runner["labels"]}]


def stop(process):
    """SIGTERM makes laptop_runner.py remove its container, volume and registration."""
    process.terminate()
    try:
        process.wait(timeout=90)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def serve_one(read, start, *, pickup_timeout, sleep, monotonic, log):
    """Run one runner to completion. It is stopped only if no job ever reaches it.

    A runner that has a job is left to finish, and a status that cannot be read never
    counts as "no job": not knowing is not a reason to stop work.
    """
    process = start()
    deadline = monotonic() + pickup_timeout
    picked_up = False
    try:
        while process.poll() is None:
            sleep(POLL_SECONDS)
            if process.poll() is not None or picked_up:
                continue
            try:
                picked_up = any(runner["busy"] for runner in online_runners(read))
            except Exception as error:  # any unreadable status: retry, never stop a possible job
                log(f"could not read runner status ({error}); will retry")
                continue
            if not picked_up and monotonic() > deadline:
                log(f"runner received no job within {pickup_timeout}s; stopping it")
                stop(process)
                return 1
    except (SystemExit, KeyboardInterrupt):  # asked to stop: do not leave a runner registered
        stop(process)
        raise
    return process.returncode


def run_once(read, start, *, ready, max_runs, pickup_timeout, dry_run, now, sleep, monotonic, log):
    """One timer run. Returns the process exit status."""
    for served in range(max_runs):
        waiting = queued_jobs(read, now())
        if not waiting:
            log("queue is empty" if served else "no jobs queued for the laptop runner")
            return 0
        online = online_runners(read)
        if online:
            names = ", ".join(runner["name"] for runner in online)
            log(f"{len(waiting)} job(s) queued; runner {names} is already online")
            return 0
        problem = ready()
        if problem:
            log(problem)
            return 1
        if dry_run:
            log(f"dry run: {len(waiting)} job(s) queued; would start one runner")
            return 0
        log(f"{len(waiting)} job(s) queued; starting runner {served + 1} of at most {max_runs}")
        status = serve_one(read, start, pickup_timeout=pickup_timeout, sleep=sleep,
                           monotonic=monotonic, log=log)
        if status:
            log(f"runner exited with status {status}; leaving the queue for the next timer run")
            return 1
    log(f"served {max_runs} runner(s); the next timer run continues if jobs are still queued")
    return 0


def acquire_lock():
    """Exclusive lock for one watcher run, or None when another run holds it."""
    directory = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    descriptor = os.open(os.path.join(directory, "bilun-ci-watcher.lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(descriptor)
        return None
    return descriptor


def image_problem(image):
    """None when the image can be used, else a one-line reason."""
    try:
        result = subprocess.run(["docker", "image", "inspect", image], text=True, capture_output=True,
                                check=False, timeout=CALL_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"docker is not usable: {error}"
    if result.returncode == 0:
        return None
    if "No such image" in result.stderr:
        return f"image {image} is not available locally; build it with laptop_runner.py --build"
    return f"docker is not usable: {result.stderr.strip()[:200]}"


def runner_command(image):
    return [sys.executable, str(RUNNER), "--image", image, "--jobs", "1"]


def raise_exit(signum, _frame):
    raise SystemExit(128 + signum)


def log(message):
    print(message, flush=True)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=os.environ.get("BILUN_CI_IMAGE"),
                        help="reviewed CI image (default: $BILUN_CI_IMAGE)")
    parser.add_argument("--max-runs", type=int, default=6, help="runners to start in one run")
    parser.add_argument("--pickup-timeout", type=int, default=300,
                        help="seconds a runner may wait for its first job before it is stopped")
    parser.add_argument("--dry-run", action="store_true", help="report what would start; start nothing")
    args = parser.parse_args(argv)
    if not args.image:
        parser.error("--image or BILUN_CI_IMAGE is required")
    if args.max_runs < 1 or args.pickup_timeout < 1:
        parser.error("--max-runs and --pickup-timeout must be positive")
    return args


def main(argv=None):
    args = parse_args(argv)
    signal.signal(signal.SIGTERM, raise_exit)
    lock = acquire_lock()
    if lock is None:
        log("another watcher run is active")
        return 0
    try:
        return run_once(
            github,
            lambda: subprocess.Popen(runner_command(args.image)),
            ready=lambda: image_problem(args.image),
            max_runs=args.max_runs,
            pickup_timeout=args.pickup_timeout,
            dry_run=args.dry_run,
            now=lambda: datetime.now(UTC),
            sleep=time.sleep,
            monotonic=time.monotonic,
            log=log,
        )
    except RuntimeError as error:
        log(str(error))
        return 1
    finally:
        os.close(lock)


if __name__ == "__main__":
    sys.exit(main())
