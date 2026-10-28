"""How many xdist workers `-n auto` may start in the memory this run has."""
from __future__ import annotations

import os
from pathlib import Path

# One worker's share. The laptop's 8 workers in 16 GB fit; 8 in the VPS's 10 GB were OOM-killed (2026-10-28).
WORKER_MEMORY = 2 * 1024**3


def cgroup_memory_limit(proc=Path("/proc/self/cgroup"), sysfs=Path("/sys/fs/cgroup")):
    """The cgroup v2 memory limit of this process in bytes, or None when there is none."""
    try:
        lines = proc.read_text().splitlines()
        path = next(line[3:] for line in lines if line.startswith("0::"))
        value = (sysfs / path.lstrip("/") / "memory.max").read_text().strip()
    except (OSError, StopIteration):
        return None
    return None if value == "max" else int(value)


def auto_workers(workers, environ=os.environ, limit=None):
    """xdist's count, capped at what the memory limit holds; an explicit PYTEST_XDIST_AUTO_NUM_WORKERS wins."""
    if environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS") or limit is None:
        return workers
    return max(1, min(workers, limit // WORKER_MEMORY))
