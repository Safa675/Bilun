"""Lines added and deleted per area over the last N days, and the test/code ratio (read-only).

    python tools/size_report.py            # last 7 days of origin/main
    python tools/size_report.py --days 28
"""
from __future__ import annotations

import argparse
import subprocess

AREAS = ("src/", "tests/", "scripts/", "frontend/src/", "data/", "plans/", "tasks/", "reports/")


def area_of(path):
    if path.startswith("frontend/src/") and (".test." in path or "/__tests__/" in path):
        return "frontend tests"
    return next((area.rstrip("/") for area in AREAS if path.startswith(area)), "other")


def tally(numstat):
    """{area: [added, deleted]} from `git log --numstat` output; binary files ("-") are skipped."""
    totals = {}
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        row = totals.setdefault(area_of(parts[2]), [0, 0])
        row[0] += int(parts[0])
        row[1] += int(parts[1])
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--ref", default="origin/main")
    args = parser.parse_args()
    numstat = subprocess.run(
        ["git", "log", args.ref, f"--since={args.days} days ago", "--no-merges", "--numstat", "--format="],
        capture_output=True, text=True, check=True,
    ).stdout
    totals = tally(numstat)
    print(f"{'area':<16}{'added':>9}{'deleted':>9}{'net':>9}")
    for area, (added, deleted) in sorted(totals.items(), key=lambda item: -item[1][0]):
        print(f"{area:<16}{added:>9}{deleted:>9}{added - deleted:>9}")
    code = totals.get("src", [0, 0])[0]
    tests = totals.get("tests", [0, 0])[0]
    ratio = f"{tests / code:.1f}:1" if code else "n/a (no src lines added)"
    print(f"\nPython test lines added per src line added, last {args.days} days: {ratio} (budget: 2:1)")


if __name__ == "__main__":
    main()
