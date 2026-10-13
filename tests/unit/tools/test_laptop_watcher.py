"""The laptop CI watcher starts runners only while jobs are queued, one at a time."""
from __future__ import annotations

import importlib.util
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "laptop_watcher", Path(__file__).resolve().parents[3] / "tools" / "ci" / "laptop_watcher.py")
watcher = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(watcher)

NOW = datetime(2026, 10, 12, 19, 0, tzinfo=UTC)
LABELS = ["self-hosted", "Linux", "X64", "bilun-laptop-ci"]
FRESH = "2026-10-12T18:50:00Z"
ACTIONS = f"repos/{watcher.REPOSITORY}/actions/"


class Clock:
    def __init__(self):
        self.time = 0.0

    def sleep(self, seconds):
        self.time += seconds

    def monotonic(self):
        return self.time


class FakeProcess:
    """A runner process that finishes `runs_for` fake seconds after it started."""

    def __init__(self, clock, runs_for, status, on_exit, ignores_terminate=False):
        self.clock = clock
        self.started = clock.time
        self.runs_for = runs_for
        self.status = status
        self.on_exit = on_exit
        self.ignores_terminate = ignores_terminate
        self.returncode = None
        self.terminated = False
        self.killed = False
        self.waits = []

    def poll(self):
        if self.returncode is None and self.clock.time >= self.started + self.runs_for:
            self.returncode = self.status
            self.on_exit(served=True)
        return self.returncode

    def terminate(self):
        if self.returncode is None:
            self.terminated = True
            if not self.ignores_terminate:
                self.returncode = -15
                self.on_exit(served=False)

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self.returncode is None:
            raise subprocess.TimeoutExpired("runner", timeout)
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9
        self.on_exit(served=False)


def runner(*, busy=False, status="online", labels=LABELS):
    return {"name": "bilun-ci-0123456789ab", "status": status, "busy": busy,
            "labels": [{"name": name} for name in labels]}


class Harness:
    """GitHub as the watcher sees it, plus the runner process it starts."""

    def __init__(self, queued=1, *, online=(), busy=True, runs_for=120, status=0, problem=None):
        self.clock = Clock()
        self.logs = []
        self.queue = queued
        self.online = list(online)
        self.busy = busy
        self.runs_for = runs_for
        self.status = status
        self.problem = problem
        self.api_down = False
        self.processes = []

    @property
    def starts(self):
        return len(self.processes)

    def read(self, path):
        if path.startswith(ACTIONS + "runs?status=queued"):
            return {"workflow_runs": [{"id": 1, "updated_at": FRESH}] if self.queue else []}
        if path.startswith(ACTIONS + "runs?status=in_progress"):
            return {"workflow_runs": []}
        if path.startswith(ACTIONS + "runs/1/jobs"):
            return {"jobs": [{"status": "queued", "labels": LABELS}] * self.queue}
        if path.startswith(ACTIONS + "runners"):
            if self.api_down:
                raise RuntimeError("GitHub API failed for runners: connection reset")
            return {"runners": self.online}
        raise AssertionError(path)

    def start(self):
        def finished(served):
            self.online = []
            self.api_down = False
            if served:
                self.queue = max(0, self.queue - 1)

        process = FakeProcess(self.clock, self.runs_for, self.status, finished)
        self.processes.append(process)
        self.online = [runner(busy=self.busy)]
        return process

    def run(self, **overrides):
        options = dict(ready=lambda: self.problem, max_runs=6, pickup_timeout=300, dry_run=False,
                       now=lambda: NOW, sleep=self.clock.sleep, monotonic=self.clock.monotonic,
                       log=self.logs.append)
        options.update(overrides)
        return watcher.run_once(self.read, self.start, **options)


# --- which jobs and runners count -------------------------------------------------------------

def test_only_recent_jobs_with_our_label_that_are_queued_count():
    runs = {"queued": [{"id": 1, "updated_at": FRESH}, {"id": 2, "updated_at": "2026-08-06T20:10:54Z"}],
            "in_progress": [{"id": 3, "updated_at": FRESH}]}
    jobs = {
        1: [{"status": "queued", "labels": LABELS}, {"status": "queued", "labels": ["ubuntu-latest"]},
            {"status": "in_progress", "labels": LABELS}],
        2: [{"status": "queued", "labels": LABELS}],
        3: [{"status": "completed", "labels": LABELS}, {"status": "queued", "labels": LABELS}],
    }
    fetched = []

    def read(path):
        if "runs?status=queued" in path:
            return {"workflow_runs": runs["queued"]}
        if "runs?status=in_progress" in path:
            return {"workflow_runs": runs["in_progress"]}
        run_id = int(path.split("/runs/")[1].split("/")[0])
        fetched.append(run_id)
        return {"jobs": jobs[run_id]}

    assert len(watcher.queued_jobs(read, NOW)) == 2
    assert fetched == [1, 3]  # the stale record's jobs are never requested


def test_a_job_asking_for_labels_our_runner_lacks_is_not_waiting_for_us():
    assert watcher.takes_our_runner({"labels": LABELS})
    assert watcher.takes_our_runner({"labels": ["Self-Hosted", "linux", "X64", "bilun-laptop-ci"]})
    assert not watcher.takes_our_runner({"labels": [*LABELS, "gpu"]})  # a runner of ours cannot take it
    assert not watcher.takes_our_runner({"labels": ["ubuntu-latest"]})
    assert not watcher.takes_our_runner({"labels": ["self-hosted", "Linux", "X64"]})


def test_only_online_runners_with_our_label_block_a_start():
    decoys = [runner(status="offline"), runner(labels=["self-hosted", "other"])]
    harness = Harness(queued=1, online=decoys)
    assert harness.run() == 0
    assert harness.starts == 1


def test_an_online_runner_is_left_to_serve_the_queue():
    harness = Harness(queued=2, online=[runner()])
    assert harness.run() == 0
    assert harness.starts == 0
    assert "already online" in harness.logs[-1]


# --- the serve loop -----------------------------------------------------------------------------

def test_nothing_queued_starts_nothing():
    harness = Harness(queued=0)
    assert harness.run() == 0
    assert harness.starts == 0
    assert harness.logs == ["no jobs queued for the laptop runner"]


def test_serves_the_queue_one_runner_at_a_time_until_it_is_empty():
    harness = Harness(queued=3)
    assert harness.run() == 0
    assert harness.starts == 3
    assert harness.queue == 0
    assert harness.logs[-1] == "queue is empty"
    assert harness.online == []


def test_one_run_is_bounded_by_max_runs():
    harness = Harness(queued=5)
    assert harness.run(max_runs=2) == 0
    assert harness.starts == 2
    assert harness.queue == 3
    assert "served 2 runner(s)" in harness.logs[-1]


def test_a_failing_runner_ends_the_run_and_leaves_the_queue_for_the_next_one():
    harness = Harness(queued=3, status=3)
    assert harness.run() == 1
    assert harness.starts == 1
    assert "exited with status 3" in harness.logs[-1]


def test_dry_run_reports_without_starting_anything():
    harness = Harness(queued=2)
    assert harness.run(dry_run=True) == 0
    assert harness.starts == 0
    assert harness.logs == ["dry run: 2 job(s) queued; would start one runner"]


def test_a_missing_image_or_docker_is_reported_and_nothing_starts():
    problem = "image bilun-laptop-ci:x is not available locally; build it with laptop_runner.py --build"
    harness = Harness(queued=1, problem=problem)
    assert harness.run() == 1
    assert harness.starts == 0
    assert harness.logs[-1] == problem


def test_a_dry_run_does_not_hide_a_missing_image():
    harness = Harness(queued=1, problem="docker is not usable: daemon down")
    assert harness.run(dry_run=True) == 1
    assert harness.logs[-1] == "docker is not usable: daemon down"


# --- never stop a job, always stop an idle runner ----------------------------------------------

def test_a_runner_that_never_receives_a_job_is_stopped_right_after_the_pickup_timeout():
    harness = Harness(queued=1, busy=False, runs_for=float("inf"))
    assert harness.run(pickup_timeout=100) == 1
    process = harness.processes[0]
    assert process.terminated
    assert not process.killed
    assert 100 < harness.clock.time <= 100 + watcher.POLL_SECONDS
    assert any("received no job" in line for line in harness.logs)


def test_a_busy_runner_is_never_stopped_even_past_the_pickup_timeout():
    harness = Harness(queued=1, busy=True, runs_for=3600)
    assert harness.run(pickup_timeout=60) == 0
    assert not harness.processes[0].terminated
    assert harness.queue == 0


def test_a_runner_that_gets_its_job_only_after_the_pickup_timeout_is_not_stopped():
    class Late(Harness):
        def read(self, path):
            if path.startswith(ACTIONS + "runners") and self.processes:
                busy = self.clock.time >= self.processes[0].started + 70  # GitHub assigned it late
                return {"runners": [runner(busy=busy)]}
            return super().read(path)

    harness = Late(queued=1, runs_for=3600)
    assert harness.run(pickup_timeout=60) == 0
    assert not harness.processes[0].terminated
    assert harness.queue == 0


def test_an_unreadable_runner_status_does_not_cost_a_running_job():
    class Blip(Harness):
        def start(self):
            process = super().start()
            self.api_down = True  # status reads fail while the job runs
            return process

    harness = Blip(queued=1, busy=True, runs_for=3600)
    assert harness.run(pickup_timeout=60) == 0
    assert not harness.processes[0].terminated
    assert any("could not read runner status" in line for line in harness.logs)


def test_an_unexpected_status_payload_does_not_cost_a_running_job():
    class Odd(Harness):
        def start(self):
            process = super().start()
            self.online = [{"name": "bilun-ci-x", "status": "online",
                            "labels": [{"name": "bilun-laptop-ci"}]}]  # no "busy" key at all
            return process

    harness = Odd(queued=1, runs_for=3600)
    assert harness.run(pickup_timeout=60) == 0
    assert not harness.processes[0].terminated


def test_sigterm_to_the_watcher_stops_its_runner_before_exiting():
    harness = Harness(queued=1, runs_for=float("inf"))

    def interrupted(_seconds):
        raise SystemExit(143)

    with pytest.raises(SystemExit):
        watcher.serve_one(harness.read, harness.start, pickup_timeout=300, sleep=interrupted,
                          monotonic=harness.clock.monotonic, log=harness.logs.append)
    assert harness.processes[0].terminated


def test_a_runner_that_ignores_sigterm_is_killed_after_the_grace_period():
    clock = Clock()
    process = FakeProcess(clock, runs_for=float("inf"), status=0, on_exit=lambda served: None,
                          ignores_terminate=True)
    watcher.stop(process)
    assert process.terminated
    assert process.killed
    assert process.waits[0] == 90


def test_the_sigterm_handler_exits_with_128_plus_the_signal():
    with pytest.raises(SystemExit) as error:
        watcher.raise_exit(signal.SIGTERM, None)
    assert error.value.code == 143


# --- plumbing -----------------------------------------------------------------------------------

def test_the_runner_is_started_for_exactly_one_job_with_the_given_image():
    assert watcher.runner_command("bilun-laptop-ci:x") == [
        sys.executable, str(watcher.RUNNER), "--image", "bilun-laptop-ci:x", "--jobs", "1"]
    assert watcher.RUNNER.name == "laptop_runner.py"


def test_defaults_and_validation(monkeypatch):
    monkeypatch.delenv("BILUN_CI_IMAGE", raising=False)
    args = watcher.parse_args(["--image", "bilun-laptop-ci:x"])
    assert (args.max_runs, args.pickup_timeout, args.dry_run) == (6, 300, False)
    monkeypatch.setenv("BILUN_CI_IMAGE", "from-env")
    assert watcher.parse_args([]).image == "from-env"
    monkeypatch.delenv("BILUN_CI_IMAGE")
    for bad in ([], ["--image", "x", "--max-runs", "0"], ["--image", "x", "--pickup-timeout", "0"]):
        with pytest.raises(SystemExit) as error:
            watcher.parse_args(bad)
        assert error.value.code == 2


def test_two_watcher_runs_cannot_overlap(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    first = watcher.acquire_lock()
    assert first is not None
    assert watcher.acquire_lock() is None
    os.close(first)
    third = watcher.acquire_lock()
    assert third is not None
    os.close(third)


def _run_returning(monkeypatch, *, returncode=0, stdout="", stderr="", raises=None):
    def fake(arguments, **kwargs):
        assert kwargs.get("timeout"), "every external call must be bounded"
        if raises:
            raise raises
        return subprocess.CompletedProcess(arguments, returncode, stdout, stderr)

    monkeypatch.setattr(watcher.subprocess, "run", fake)


@pytest.mark.parametrize("failure", [
    dict(raises=FileNotFoundError("gh")),
    dict(raises=subprocess.TimeoutExpired("gh", 60)),
    dict(returncode=1, stderr="HTTP 401"),
    dict(stdout="<html>maintenance</html>"),
])
def test_every_github_failure_is_a_runtime_error(monkeypatch, failure):
    _run_returning(monkeypatch, **failure)
    with pytest.raises(RuntimeError):
        watcher.github("repos/Safa675/Bilun/actions/runners?per_page=100")


def _scripted_runs(monkeypatch, outcomes):
    """`gh api` answers from `outcomes` in order; returns the list of calls and sleeps."""
    calls, sleeps = [], []
    queue = list(outcomes)

    def fake(arguments, **kwargs):
        calls.append(arguments)
        returncode, stdout, stderr = queue.pop(0)
        return subprocess.CompletedProcess(arguments, returncode, stdout, stderr)

    monkeypatch.setattr(watcher.subprocess, "run", fake)
    monkeypatch.setattr(watcher.time, "sleep", sleeps.append)
    return calls, sleeps


BLIP = (1, "", "error connecting to api.github.com\ncheck your internet connection")


def test_a_dropped_connection_is_asked_again_before_giving_up(monkeypatch):
    calls, sleeps = _scripted_runs(monkeypatch, [BLIP, BLIP, (0, '{"ok": true}', "")])
    assert watcher.github("repos/Safa675/Bilun/actions/runs?status=queued") == {"ok": True}
    assert len(calls) == 3
    assert sleeps == [watcher.CONNECT_WAIT, watcher.CONNECT_WAIT]


def test_a_connection_that_stays_down_fails_after_the_last_try(monkeypatch):
    calls, sleeps = _scripted_runs(monkeypatch, [BLIP] * watcher.CONNECT_TRIES)
    with pytest.raises(RuntimeError, match="error connecting"):
        watcher.github("repos/Safa675/Bilun/actions/runs")
    assert len(calls) == watcher.CONNECT_TRIES
    assert sleeps == [watcher.CONNECT_WAIT] * (watcher.CONNECT_TRIES - 1)  # no pause after the last try


def test_a_real_api_error_is_not_retried(monkeypatch):
    calls, sleeps = _scripted_runs(monkeypatch, [(1, "", "gh: Bad credentials (HTTP 401)")])
    with pytest.raises(RuntimeError, match="401"):
        watcher.github("repos/Safa675/Bilun/actions/runs")
    assert len(calls) == 1
    assert sleeps == []


def test_a_good_github_answer_is_parsed(monkeypatch):
    _run_returning(monkeypatch, stdout='{"total_count": 0, "runners": []}')
    assert watcher.github("repos/Safa675/Bilun/actions/runners") == {"total_count": 0, "runners": []}


def test_a_missing_image_is_told_apart_from_an_unusable_docker(monkeypatch):
    _run_returning(monkeypatch, returncode=0)
    assert watcher.image_problem("img:1") is None
    _run_returning(monkeypatch, returncode=1, stderr="Error response from daemon: No such image: img:1")
    assert "not available locally" in watcher.image_problem("img:1")
    _run_returning(monkeypatch, returncode=1, stderr="Cannot connect to the Docker daemon")
    assert "docker is not usable" in watcher.image_problem("img:1")
    _run_returning(monkeypatch, raises=FileNotFoundError("docker"))
    assert "docker is not usable" in watcher.image_problem("img:1")
