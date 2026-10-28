"""A job container's CPU and memory come from the environment, with the laptop's defaults."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "laptop_runner", Path(__file__).resolve().parents[3] / "tools" / "ci" / "laptop_runner.py")
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


def test_defaults_are_the_laptop_limits():
    assert runner.resource_limits({}) == ["--cpus=8", "--memory=16g", "--memory-swap=16g"]


def test_a_shared_host_sets_lower_limits_and_swap_follows_memory():
    environ = {"BILUN_CI_CPUS": "6", "BILUN_CI_MEMORY": "10g"}
    assert runner.resource_limits(environ) == ["--cpus=6", "--memory=10g", "--memory-swap=10g"]
