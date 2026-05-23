"""Pytest bootstrap for BILUN tests."""
from __future__ import annotations

import os

os.environ["TESTING"] = "1"

from tests.fixtures.sut import (  # noqa: E402
    cohort_sut_summary_payload,
    sut_single_json_payloads,
)


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run smoke tests against a live server at localhost:8001",
    )
