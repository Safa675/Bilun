"""API tests for the MEDULA rejection queue endpoint."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_queue_returns_ingest_available_and_matched_row() -> None:
    from src.bilun.api.routes.medula_rejections import get_medula_rejection_queue

    result = get_medula_rejection_queue()

    assert result["ingest_available"] is True
    assert result["total"] >= 1
    row = next(
        r
        for r in result["rows"]
        if r["patient_id"] == "SENTETIK-HASTA-0012"
    )
    assert row["claim_id"] == "F-SENTETIK-HASTA-0012-026"
    assert row["sonuc_kodu"] == "1688"
    assert row["playbook_matched"] is True
    assert row["rebill_permitted"] is True
    assert row["corrective_steps_tr"]


def test_queue_filters_by_sonuc_kodu() -> None:
    from src.bilun.api.routes.medula_rejections import get_medula_rejection_queue

    result = get_medula_rejection_queue(sonuc_kodu="1688")
    assert all(r["sonuc_kodu"] == "1688" for r in result["rows"])


def test_queue_pagination_bounds_rows() -> None:
    from src.bilun.api.routes.medula_rejections import get_medula_rejection_queue

    result = get_medula_rejection_queue(page=1, page_size=1)
    assert len(result["rows"]) <= 1
    assert result["page_size"] == 1
