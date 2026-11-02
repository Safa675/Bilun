"""The procedure-code cleaning the prose rules share."""

from __future__ import annotations

import pytest

from src.bilun.domain.prose_rules.claim_utils import PackagePrefix, clean_procedure_code

pytestmark = pytest.mark.unit


def test_the_three_package_prefix_readings_differ() -> None:
    assert [clean_procedure_code("p510.010", p) for p in PackagePrefix] == ["P510010", "510010", "510010"]
    assert [clean_procedure_code("PAKET", p) for p in PackagePrefix] == ["PAKET", "PAKET", "AKET"]
