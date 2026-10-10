"""Unit tests for the notify-only SGK announcement watcher."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.sut.sgk_watch import (
    MAX_NEW_ISSUES,
    classify,
    issue_body,
    known_slugs,
    parse_listing,
    pending,
)

pytestmark = pytest.mark.unit

# Slugs as they appear on https://www.sgk.gov.tr/duyuru/index/TumBirimler (October 2026).
SUT_PACKAGE = "02102026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-10-02-02-50-06"
OLD_PACKAGE = "29082026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-08-31-03-06-04"
GAZETTE_NOTICE = (
    "02102026-Tarihli-ve-33388-Sayili-Resm-Gazetede-Yayimlanan-Sosyal-Guvenlik-Kurumu-"
    "Saglik-Uygulama-Tebliginde-Degisiklik-Yapilmasina-Dair-Teblig-2026-10-02-02-45-11"
)
DRUG_39 = "Bedeli-Odenecek-Ilaclar-Listesinde-Yapilan-Duzenlemeler-Hakkinda-Duyuru-202639-2026-10-07-04-54-48"
DRUG_33 = "Bedeli-Odenecek-Ilaclar-Listesinde-Yapilan-Duzenlemeler-Hakkinda-Duyuru-202633-2026-08-26-04-34-52"
DRUG_EXTRA = (
    "2026-Yili-2-Olaganustu-Ilac-Geri-Odeme-Komisyonu-Kararina-Istinaden-Bedeli-Odenecek-"
    "Ilaclar-Listesinde-Yapilan-Duzenlemeler-Hakkinda-Duyuru-2026-09-25-10-50-59"
)
BILLING = "Fatura-ve-Eki-Belgelerin-Is-ve-Islemleri-2026-09-21-04-22-33"
UNRELATED = "Gayrimenkul-Satis-Ilani-2026-10-05-11-35-26"

LISTING = "\n".join(
    f'<a href="/duyuru/detay/{slug}">x</a>'
    for slug in (DRUG_39, UNRELATED, SUT_PACKAGE, GAZETTE_NOTICE, DRUG_EXTRA, BILLING, DRUG_39)
)


def test_classify_reads_kind_and_dates() -> None:
    package = classify(SUT_PACKAGE)
    assert package["kind"] == "sut_package"
    assert package["date"] == "2026-10-02"  # the amendment date, compared with last_ingested_date
    assert classify(OLD_PACKAGE)["date"] == "2026-08-29"
    assert classify(OLD_PACKAGE)["published"] == "2026-08-31"
    drug = classify(DRUG_39)
    assert drug["kind"] == "drug_list" and drug["date"] == "2026-10-07"
    assert "2026/39" in drug["title"]
    assert "extraordinary" in classify(DRUG_EXTRA)["title"]
    assert classify(BILLING)["kind"] == "billing"
    assert "Fatura ve Eki Belgelerin Is ve Islemleri" in classify(BILLING)["title"]


def test_classify_ignores_unrelated_and_duplicate_gazette_notice() -> None:
    assert classify(UNRELATED) is None
    # The Official Gazette notice is the same amendment as the consolidated package.
    assert classify(GAZETTE_NOTICE) is None
    assert classify("Planli-Altyapi-Calismasi") is None  # no publication timestamp


def test_parse_listing_keeps_page_order_without_duplicates() -> None:
    slugs = [item["slug"] for item in parse_listing(LISTING)]
    assert slugs == [DRUG_39, SUT_PACKAGE, DRUG_EXTRA, BILLING]
    assert parse_listing("<html></html>") == []


def test_pending_uses_baseline_and_existing_markers_oldest_first() -> None:
    announcements = parse_listing(LISTING) + [classify(DRUG_33), classify(OLD_PACKAGE)]
    known = known_slugs([issue_body(classify(DRUG_EXTRA), "2026-08-29"), "unrelated body", ""])
    assert known == {DRUG_EXTRA}
    fresh = pending(announcements, "2026-08-29", known)
    assert [item["slug"] for item in fresh] == [BILLING, SUT_PACKAGE, DRUG_39]
    assert pending(announcements, "2026-10-07", set()) == []


def test_issue_body_links_announcement_and_carries_marker() -> None:
    body = issue_body(classify(DRUG_39), "2026-08-29")
    assert f"https://www.sgk.gov.tr/duyuru/detay/{DRUG_39}" in body
    assert "2026-08-29" in body and "EK-4A" in body
    assert known_slugs([body]) == {DRUG_39}
    assert MAX_NEW_ISSUES >= 9  # the October 2026 backlog fits in one run


def test_scheduled_runs_only_notify() -> None:
    path = Path(__file__).resolve().parents[3] / ".github/workflows/sut-monitor.yml"
    workflow = yaml.safe_load(path.read_text())
    triggers = workflow[True]  # PyYAML reads the bare `on:` key as boolean True
    assert triggers["workflow_dispatch"]["inputs"]["ingest"]["default"] is False
    notify = workflow["jobs"]["notify"]
    assert notify["permissions"] == {"contents": "read", "issues": "write"}
    assert "if" not in notify
    assert any("scripts/sut/sgk_watch.py" in str(step.get("run", "")) for step in notify["steps"])
    ingest = workflow["jobs"]["monitor"]
    assert ingest["if"] == "github.event_name == 'workflow_dispatch' && inputs.ingest"
