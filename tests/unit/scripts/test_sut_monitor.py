"""Unit tests for the SUT tebliğ monitor script."""

from __future__ import annotations

import datetime as dt

import pytest

from scripts.sut.sut_monitor import check_for_new, find_sut_tebliğs

pytestmark = pytest.mark.unit

# Simulated SGK /Duyuru HTML with two SUT tebliğ slugs (matching the real page structure).
MOCK_DUYURU_HTML = """
<html><body>
  <div class="duyuru-list">
    <a href="/duyuru/detay/01072026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-07-01-02-55-17">2026-07-01 SUT</a>
    <a href="/duyuru/detay/29062026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-06-29-04-47-18">2026-06-29 SUT</a>
    <a href="/duyuru/detay/23052026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-05-23-01-00-00">2026-05-23 SUT</a>
    <a href="/duyuru/detay/some-other-duyuru-not-sut-2026-07-10">Not a SUT tebliğ</a>
    <a href="/duyuru/detay/Bedeli-Odenecek-Ilaclar-Listesinde-Yapilan-Duzenlemeler">Drug list duyuru</a>
  </div>
</body></html>
"""

MOCK_EMPTY_HTML = "<html><body><p>No duyurus today.</p></body></html>"


def test_find_sut_tebliğs_extracts_correct_dates() -> None:
    """SUT slug regex correctly parses DDMMYYYY → YYYY-MM-DD."""
    tebliğs = find_sut_tebliğs(MOCK_DUYURU_HTML)
    assert len(tebliğs) == 3  # 3 SUT tebliğs, not the non-SUT ones
    dates = [t["date"] for t in tebliğs]
    assert "2026-07-01" in dates
    assert "2026-06-29" in dates
    assert "2026-05-23" in dates


def test_find_sut_tebliğs_sorted_newest_first() -> None:
    """Tebliğs are returned sorted newest-first for correct 'is there a newer one?' logic."""
    tebliğs = find_sut_tebliğs(MOCK_DUYURU_HTML)
    dates = [t["date"] for t in tebliğs]
    assert dates == sorted(dates, reverse=True)


def test_find_sut_tebliğs_deduplicates() -> None:
    """Duplicate slugs are deduplicated."""
    html_with_dups = MOCK_DUYURU_HTML + MOCK_DUYURU_HTML
    tebliğs = find_sut_tebliğs(html_with_dups)
    assert len(tebliğs) == 3  # still 3, not 6


def test_find_sut_tebliğs_empty_html() -> None:
    """Empty or non-matching HTML returns empty list."""
    assert find_sut_tebliğs(MOCK_EMPTY_HTML) == []
    assert find_sut_tebliğs("") == []


def test_check_for_new_detects_newer_tebliğ() -> None:
    """When state is older than the newest tebliğ, returns the newest."""
    state = {"last_ingested_date": "2026-05-23"}
    tebliğs = find_sut_tebliğs(MOCK_DUYURU_HTML)
    new = check_for_new(state, tebliğs)
    assert new is not None
    assert new["date"] == "2026-07-01"


def test_check_for_new_returns_none_when_up_to_date() -> None:
    """When state date >= newest tebliğ, returns None."""
    state = {"last_ingested_date": "2026-07-01"}
    tebliğs = find_sut_tebliğs(MOCK_DUYURU_HTML)
    assert check_for_new(state, tebliğs) is None


def test_check_for_new_with_future_state() -> None:
    """State from the future correctly returns None."""
    state = {"last_ingested_date": "2099-01-01"}
    tebliğs = find_sut_tebliğs(MOCK_DUYURU_HTML)
    assert check_for_new(state, tebliğs) is None


def test_check_for_new_empty_tebliğs() -> None:
    """Empty tebliğ list always returns None."""
    state = {"last_ingested_date": "2000-01-01"}
    assert check_for_new(state, []) is None


def test_future_publication_is_skipped_for_newest_available() -> None:
    state = {"last_ingested_date": "2026-06-01"}
    tebliğs = find_sut_tebliğs(MOCK_DUYURU_HTML)
    new = check_for_new(state, tebliğs, as_of=dt.date(2026, 6, 29))
    assert new is not None and new["date"] == "2026-06-29"
    assert check_for_new(state, tebliğs, as_of=dt.date(2026, 5, 1)) is None


def test_partial_component_receipt_does_not_suppress_complete_package_retry() -> None:
    state = {"last_ingested_date": "2026-05-23", "pending_full_package_date": "2026-07-01",
        "component_receipts": {"prose": {"source_snapshot_date": "2026-07-01"}}}
    new = check_for_new(state, find_sut_tebliğs(MOCK_DUYURU_HTML), as_of=dt.date(2026, 7, 1))
    assert new is not None and new["date"] == "2026-07-01"
