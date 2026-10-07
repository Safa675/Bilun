#!/usr/bin/env python3
"""Monitor sgk.gov.tr for new SUT amendment tebliğ publications.

Usage:
    python scripts/sut/sut_monitor.py

Exits 0 always (detection result is output, not an error condition).
Outputs via GITHUB_OUTPUT (in CI) or stderr (local).
"""
from __future__ import annotations

import json
import datetime as dt
import os
import re
import sys
from pathlib import Path

import requests

# FIXED: v1 plan used /Duyuru/TumunuGor which 404s. /Duyuru is the real page.
SGK_DUYURU_URL = "https://www.sgk.gov.tr/Duyuru"

# Matches: href="/duyuru/detay/01072026-SUT-Degisiklik-Tebligi-..."
# Captures: slug, DD, MM, YYYY
SUT_SLUG_PATTERN = re.compile(
    r'href="(/duyuru/detay/(\d{2})(\d{2})(\d{4})-SUT-Degisiklik[^"]*)"',
    re.IGNORECASE,
)

STATE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "gazette" / "ingest_state.json"


def fetch_duyuru_page() -> str:
    """Fetch the SGK duyuru listing (server-rendered HTML, no JS)."""
    resp = requests.get(SGK_DUYURU_URL, timeout=30)
    resp.raise_for_status()
    return resp.text


def find_sut_tebliğs(html: str) -> list[dict]:
    """Extract SUT tebliğ duyuru slugs + dates from the listing.

    Returns list of dicts sorted newest-first:
        {"url": str, "date": "YYYY-MM-DD", "slug": str}
    """
    results = []
    for match in SUT_SLUG_PATTERN.finditer(html):
        slug, dd, mm, yyyy = match.groups()
        results.append(
            {
                "url": f"https://www.sgk.gov.tr{slug}",
                "date": f"{yyyy}-{mm}-{dd}",
                "slug": slug,
            }
        )
    # Deduplicate by slug, sort newest-first
    seen = set()
    unique = []
    for t in results:
        if t["slug"] not in seen:
            seen.add(t["slug"])
            unique.append(t)
    return sorted(unique, key=lambda t: t["date"], reverse=True)


def check_for_new(state: dict, tebliğs: list[dict], *, as_of: dt.date | None = None) -> dict | None:
    """Select a published amendment; future listings never activate ingestion early."""
    last_date = state.get("last_ingested_date", "2000-01-01")
    today = (as_of or dt.datetime.now(dt.UTC).date()).isoformat()
    for t in tebliğs:
        if last_date < t["date"] <= today:
            return t
    return None


def _output(key: str, value: str) -> None:
    """Write to GITHUB_OUTPUT (CI) or stderr (local)."""
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"{key}={value}\n")
    else:
        print(f"[monitor] {key}={value}", file=sys.stderr)


def main() -> int:
    if not STATE_FILE.exists():
        print(f"State file not found: {STATE_FILE}", file=sys.stderr)
        _output("new_teblig", "")
        return 0

    state = json.loads(STATE_FILE.read_text())
    print(f"Last ingested date: {state.get('last_ingested_date', '?')}")

    try:
        html = fetch_duyuru_page()
    except requests.RequestException as exc:
        print(f"Failed to fetch SGK duyuru page: {exc}", file=sys.stderr)
        _output("new_teblig", "")
        return 0

    tebliğs = find_sut_tebliğs(html)
    print(f"Found {len(tebliğs)} SUT tebliğ(s) on the duyuru page.")

    if not tebliğs:
        print("No SUT tebliğ slugs found.")
        _output("new_teblig", "")
        return 0

    new = check_for_new(state, tebliğs)
    if new:
        print(f"NEW SUT tebliğ detected: {new['date']}")
        print(f"  URL: {new['url']}")
        _output("new_teblig", json.dumps(new))
        _output("new_teblig_date", new["date"])
        _output("new_teblig_url", new["url"])
    else:
        print("No new SUT tebliğ. Up to date.")
        _output("new_teblig", "")

    return 0


if __name__ == "__main__":
    sys.exit(main())
