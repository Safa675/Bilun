#!/usr/bin/env python3
"""Open one GitHub issue per new SGK announcement that Bilun has to act on.

Usage:
    python scripts/sut/sgk_watch.py [--pages 3] [--dry-run]

Watches the SGK announcement listing for three kinds of publications:
    sut_package  consolidated SUT amendment packages (what sut_fetch.py ingests)
    drug_list    EK-4A reimbursable drug list changes (Bedeli Ödenecek İlaçlar Listesi)
    billing      invoice and MEDULA procedure announcements

Only announcements newer than ingest_state.json's last_ingested_date are reported,
and each at most once: every issue body carries a marker with the SGK slug, and
slugs that already have an issue in any state are skipped. Nothing is ingested,
committed or merged. Standard library only, so the scheduled job installs nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

LISTING_URL = "https://www.sgk.gov.tr/duyuru/index/TumBirimler?page={page}"
DETAIL_URL = "https://www.sgk.gov.tr/duyuru/detay/{slug}"
USER_AGENT = "Bilun-SGK-watch/1.0 (+https://github.com/Safa675/Bilun)"
STATE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "gazette" / "ingest_state.json"
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Safa675/Bilun")
LABEL = "sgk-update"
# A parser bug must not flood the tracker; the 2026-10 backlog is nine announcements.
MAX_NEW_ISSUES = 12

SLUG_PATTERN = re.compile(r'href="/[Dd]uyuru/[Dd]etay/([^"/?#]+)"')
# Every detail slug ends with its publication timestamp: ...-YYYY-MM-DD-HH-MM-SS
STAMP_PATTERN = re.compile(r"-(\d{4})-(\d{2})-(\d{2})-\d{2}-\d{2}-\d{2}$")
SUT_PACKAGE_PATTERN = re.compile(r"^(\d{2})(\d{2})(\d{4})-SUT-Degisiklik", re.IGNORECASE)
DRUG_LIST_PATTERN = re.compile(r"Bedeli-Odenecek-Ilaclar-Listesinde", re.IGNORECASE)
DRUG_LIST_NUMBER = re.compile(r"-Duyuru-(\d{4})(\d{1,3})-\d{4}-\d{2}-\d{2}-")
BILLING_PATTERN = re.compile(r"Fatura|Medula", re.IGNORECASE)
MARKER_PATTERN = re.compile(r"<!-- sgk-duyuru: ([^ ]+) -->")

ACTIONS = {
    "sut_package": (
        "Review the amendment, then ingest the package with a manual run of the SUT Monitor "
        "workflow (`ingest: true`); its pull request needs human review."
    ),
    "drug_list": (
        "Apply the EK-4A changes with their effective dates. The runtime EK-4A catalog is "
        "still the 2026-08-29 one; see the EK-4A receipt in `data/gazette/ingest_state.json`."
    ),
    "billing": "Check whether the announcement changes Bilun's billing or MEDULA rules.",
}


def classify(slug: str) -> dict | None:
    """Return the announcement kind, date and title for a relevant slug, else None."""
    stamp = STAMP_PATTERN.search(slug)
    if stamp is None:
        return None
    published = "-".join(stamp.groups())
    package = SUT_PACKAGE_PATTERN.match(slug)
    if package:
        day, month, year = package.groups()
        date = f"{year}-{month}-{day}"
        return {"kind": "sut_package", "slug": slug, "date": date, "published": published,
                "title": f"SGK: SUT amendment package {date}"}
    if DRUG_LIST_PATTERN.search(slug):
        number = DRUG_LIST_NUMBER.search(slug)
        name = f" {number.group(1)}/{number.group(2)}" if number else ""
        if "Olaganustu" in slug:
            name += " (extraordinary reimbursement commission decision)"
        return {"kind": "drug_list", "slug": slug, "date": published, "published": published,
                "title": f"SGK: EK-4A drug list change{name}, published {published}"}
    if BILLING_PATTERN.search(slug):
        topic = slug[: stamp.start()].replace("-", " ")
        return {"kind": "billing", "slug": slug, "date": published, "published": published,
                "title": f"SGK: billing announcement '{topic}', published {published}"}
    return None


def parse_listing(html: str) -> list[dict]:
    """Relevant announcements on one listing page, in page order, without duplicates."""
    found = []
    for slug in dict.fromkeys(SLUG_PATTERN.findall(html)):
        item = classify(slug)
        if item is not None:
            found.append(item)
    return found


def known_slugs(issue_bodies: list[str]) -> set[str]:
    """Slugs that already have an issue, read from the markers in issue bodies."""
    return {slug for body in issue_bodies for slug in MARKER_PATTERN.findall(body or "")}


def pending(announcements: list[dict], baseline: str, known: set[str]) -> list[dict]:
    """New announcements after the baseline date, oldest first."""
    unique = {item["slug"]: item for item in announcements}
    fresh = [item for item in unique.values() if item["date"] > baseline and item["slug"] not in known]
    return sorted(fresh, key=lambda item: (item["published"], item["slug"]))


def issue_body(item: dict, baseline: str) -> str:
    return "\n".join([
        f"SGK published a `{item['kind']}` announcement on {item['published']}.",
        "",
        f"- Announcement: {DETAIL_URL.format(slug=item['slug'])}",
        f"- Last fully ingested SUT package: {baseline}",
        f"- Next step: {ACTIONS[item['kind']]}",
        "",
        "Opened by the scheduled SUT Monitor (`scripts/sut/sgk_watch.py`). Close this issue "
        "once Bilun reflects the announcement or a reviewer decides it does not apply.",
        "",
        f"<!-- sgk-duyuru: {item['slug']} -->",
    ])


def fetch(url: str, attempts: int = 3) -> str:
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except OSError as exc:
            if attempt == attempts:
                raise
            print(f"Fetch failed ({exc}); retrying {url}", file=sys.stderr)
            time.sleep(10 * attempt)
    raise AssertionError("unreachable")


def gh(*arguments: str) -> str:
    return subprocess.run(["gh", *arguments], check=True, text=True, capture_output=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pages", type=int, default=3, help="listing pages to scan (10 per page)")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, create nothing")
    args = parser.parse_args()

    baseline = json.loads(STATE_FILE.read_text())["last_ingested_date"]
    announcements = []
    for page in range(1, args.pages + 1):
        announcements += parse_listing(fetch(LISTING_URL.format(page=page)))
    issues = json.loads(gh("issue", "list", "--repo", REPOSITORY, "--label", LABEL,
                           "--state", "all", "--limit", "1000", "--json", "body"))
    new = pending(announcements, baseline, known_slugs([issue["body"] for issue in issues]))
    print(f"Baseline {baseline}: {len(announcements)} relevant announcements, "
          f"{len(issues)} existing issues, {len(new)} new.")
    for item in new:
        print(f"  {item['kind']:<11} {item['date']}  {item['title']}")
    if len(new) > MAX_NEW_ISSUES:
        print(f"Refusing to open {len(new)} issues (limit {MAX_NEW_ISSUES}); check the parser.",
              file=sys.stderr)
        return 1
    if args.dry_run or not new:
        return 0
    gh("label", "create", LABEL, "--repo", REPOSITORY, "--force", "--color", "D93F0B",
       "--description", "New SGK announcement that Bilun must review")
    for item in new:
        url = gh("issue", "create", "--repo", REPOSITORY, "--label", LABEL,
                 "--title", item["title"], "--body", issue_body(item, baseline)).strip()
        print(f"Opened {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
