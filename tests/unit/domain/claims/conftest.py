"""Shared fixtures for claim loader tests."""

from __future__ import annotations

import pytest

from src.bilun.domain.claims import clear_sut_claim_dataset_cache


@pytest.fixture(autouse=True)
def _clear_loader_cache_after_test() -> None:
    """Prevent in-process loader cache from leaking between tests."""

    yield
    clear_sut_claim_dataset_cache()
