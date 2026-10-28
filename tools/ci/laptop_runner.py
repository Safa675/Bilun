"""One-job Docker runners; credentials stay in memory and swap-disabled tmpfs."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path

REPOSITORY = "Safa675/Bilun"
LABEL = "bilun-laptop-ci"
ROOT = Path(__file__).resolve().parents[2]
CACHE = Path.home() / ".cache/bilun-laptop-runner"


def command(arguments, **kwargs):
    return subprocess.run(arguments, check=True, text=True, **kwargs)


def github(arguments, payload=None):
    # API responses can contain runner authentication material. Never log them.
    result = subprocess.run(["gh", "api", *arguments],
                            input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True, check=False)
    if result.returncode:
        status = re.search(r"HTTP (\d{3})", result.stderr)
        code = status.group(1) if status else "unavailable"
        raise RuntimeError(f"GitHub runner API failed: HTTP {code} (response withheld)")
    return json.loads(result.stdout) if result.stdout.strip() else None


def resource_limits(environ=os.environ):
    """CPU and memory of one job container. The defaults fit the laptop; a host that also
    serves the app (the VPS runs staging) sets BILUN_CI_CPUS and BILUN_CI_MEMORY lower."""
    cpus = environ.get("BILUN_CI_CPUS", "8")
    memory = environ.get("BILUN_CI_MEMORY", "16g")
    return [f"--cpus={cpus}", f"--memory={memory}", f"--memory-swap={memory}"]


def build(image):
    CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="image-", dir=CACHE) as directory:
        context = Path(directory)
        for relative in ("requirements-ci.lock", "tools/ci/Dockerfile",
                         "tools/ci/runner-entrypoint.sh"):
            destination = context / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        command(["docker", "build", "--tag", image, "--file",
                 str(context / "tools/ci/Dockerfile"), str(context)])


def serve_one(image, index):
    identity = "bilun-ci-" + uuid.uuid4().hex[:12]
    volume = identity + "-work"
    runner_id = None
    process = None
    command(["docker", "volume", "create", volume], capture_output=True)
    try:
        data = github(["-X", "POST", f"repos/{REPOSITORY}/actions/runners/generate-jitconfig",
                       "--input", "-"], {
            "name": identity, "runner_group_id": 1,
            "labels": ["self-hosted", "Linux", "X64", LABEL], "work_folder": "/workspace",
        })
        runner_id = data["runner"]["id"]
        configuration = data.pop("encoded_jit_config")
        arguments = [
            "docker", "run", "--rm", "--interactive", "--init", "--name", identity,
            "--read-only", "--user", "1001:1001", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", *resource_limits(),
            "--pids-limit=1024", "--shm-size=1g",
            "--mount", f"type=volume,source={volume},target=/workspace",
            "--tmpfs", "/runner:rw,exec,nosuid,nodev,size=2g,uid=1001,gid=1001,mode=0700",
            "--tmpfs", "/workspace/_temp:rw,exec,nosuid,nodev,size=2g,uid=1001,gid=1001,mode=0700",
            "--tmpfs", "/tmp:rw,exec,nosuid,nodev,size=1g,uid=1001,gid=1001,mode=0700",
            image,
        ]
        process = subprocess.Popen(arguments, stdin=subprocess.PIPE, text=True)
        process.stdin.write(configuration + "\n")
        process.stdin.close()
        del configuration
        print(f"Registered isolated one-job runner {runner_id}; job slot {index}", flush=True)
        if process.wait() != 0:
            raise RuntimeError("Isolated runner process failed")
    finally:
        if process is not None and process.poll() is None:
            subprocess.run(["docker", "stop", "--time", "15", identity],
                           capture_output=True, check=False)
            process.wait()
        if runner_id is not None:
            # JIT normally removes itself after one job. Remove an unused runner too.
            subprocess.run(["gh", "api", "-X", "DELETE",
                            f"repos/{REPOSITORY}/actions/runners/{runner_id}"],
                           capture_output=True, check=False)
        subprocess.run(["docker", "volume", "rm", volume], capture_output=True, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="bilun-laptop-ci:20261007")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    def stop(signum, _frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, stop)
    if args.jobs < 0:
        parser.error("--jobs must be non-negative")
    repo = github([f"repos/{REPOSITORY}"])
    if not repo["private"] or not repo["permissions"].get("admin"):
        raise RuntimeError("A private repository and admin permission are required")
    if args.build:
        build(args.image)
    for index in range(1, args.jobs + 1):
        serve_one(args.image, index)


if __name__ == "__main__":
    main()
