# SUT Update Pipeline — Architecture & Implementation Plan (v2, review-corrected)

**Branch:** `feat/sut-update-pipeline`
**Goal:** Automated monitoring + ingestion + delta computation for SUT amendments, triggering on new SGK tebliğ publications.
**v2 changes:** Fixed base URL, verified download link (live test), fixed 4 code bugs, added LFS/rollback/atomic-state design.

---

## External Verification (done 2026-07-12, live)

| Check | Result | Evidence |
|-------|--------|----------|
| `/Duyuru/TumunuGor` (v1 plan URL) | **404, 20KB shell** | `curl -sI` returns 404 |
| `/Duyuru` (correct URL) | **200, 86KB, 16 SUT mentions** | `curl -sI` returns 200 |
| Detail page download link | **EXISTS** | `/Download/DownloadFile?f=<guid>.zip&d=<guid>` found in HTML |
| Zip download works | **HTTP 200, 30.4MB** | `application/x-zip-compressed`, Content-Disposition: attachment |
| SUT tebliğ slugs visible on `/Duyuru` | **2 new tebliğs confirmed** | `01072026-SUT-Degisiklik...` and `29062026-SUT-Degisiklik...` |

**Conclusion: The full auto-fetch pipeline is viable. No manual download needed.**

---

## Current State (verified, unchanged from v1)

### What works
- `convert_xlsx_to_parquet.py` ingests raw .xlsx/.xls → raw parquets + `version_manifest.parquet`
- `build_curated_catalogs.py` builds curated history parquets (EK-2B: 9 versions, 62K rows)
- `_common.py:find_latest_consolidated_sut_dir()` detects newest SUT folder by date prefix
- `compile_rules.py --check` byte-identical gate for prose rules (Branch B only)
- Temporal validity ranges (`valid_from`/`valid_to`) already computed

### What's broken / missing
1. **No ingest state file** — nothing records "last ingested version"
2. **No monitoring** — no one watches sgk.gov.tr for new tebliğ
3. **No delta computation** — no "what changed between v1 and v2"
4. **Absolute paths in version_manifest** — breaks on CI/VPS
5. **No snapshot builder script** — `data/gazette/snapshots/` built off-repo
6. **No Branch A CI gate** — only Branch B (rules) has byte-identical check
7. **Hardcoded katsayı 0.593** — manual edit when it changes

### BILUN is 2 SUT versions behind
- Repo has: `2026.05.23` (RG 33262)
- SGK published: `2026.06.29` (RG 33295), `2026.07.01` (RG 33297)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  GitHub Actions: .github/workflows/sut-monitor.yml                    │
│  Cron: 0 6,18 * * *  (2×/day)                                         │
│  Permissions: contents:write, pull-requests:write                     │
│  Branch protection: chore/sut-auto-update requires human review       │
└─────────────────────┬────────────────────────────────────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │ 1. sut_monitor.py                  │
    │    GET https://www.sgk.gov.tr/Duyuru│  ← FIXED (was /Duyuru/TumunuGor)
    │    Regex: /duyuru/detay/DDMMYYYY-   │
    │      SUT-Degisiklik-Tebligi-...     │
    │    Compare vs ingest_state.json     │
    │    Output: newest tebliğ or skip    │
    └─────────────────┬──────────────────┘
                      │ new tebliğ URL
    ┌─────────────────▼──────────────────┐
    │ 2. sut_fetch.py                    │
    │    GET duyuru detail page          │
    │    Regex: /Download/DownloadFile?  │  ← VERIFIED WORKS
    │      f=<guid>.zip&d=<guid>         │
    │    Download ~30MB zip (verified)   │
    │    Extract to raw data/<DATE>-...  │
    └─────────────────┬──────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │ 3. Existing ingest chain           │
    │    convert_xlsx_to_parquet.py      │
    │    build_curated_catalogs.py       │
    │    --overwrite                     │
    │    (compile_rules.py if docx       │
    │    changed — human authoring       │
    │    needed for new prose rules)     │
    └─────────────────┬──────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │ 4. sut_delta.py                    │
    │    Load old + new curated parquets │
    │    Polars set-ops on as-of slices: │
    │      - new_codes                   │
    │      - removed_codes               │
    │      - price_changes               │
    │      - puan_changes                │
    │      - name_changes                │
    │    Write data/gazette/deltas/      │
    │      <DATE>_delta.json             │
    │    Output summary to GITHUB_OUTPUT │  ← FIXED (was body-path)
    └─────────────────┬──────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │ 5. Atomic state update             │  ← NEW: write only on success
    │    Update ingest_state.json        │
    │    (write temp → os.replace)       │
    └─────────────────┬──────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │ 6. Auto-PR                          │
    │    peter-evans/create-pull-request │
    │    body: delta summary text        │  ← FIXED (body, not body-path)
    │    branch: chore/sut-auto-update   │
    │    labels: sut-update, automated   │
    │    REQUIRES HUMAN REVIEW TO MERGE  │  ← EXPLICIT
    └────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Fix infrastructure debt (prerequisites)

#### 1.1 Fix absolute paths in version_manifest
**File:** `scripts/sut/convert_xlsx_to_parquet.py` (around L283 `build_manifest`)
- Change `parquet_path` to repo-relative (`data/gazette/raw/annex=...`)
- One-time migration: write a `normalize_manifest_paths.py` script that rewrites existing `version_manifest.parquet` with relative paths

#### 1.2 Add ingest_state.json
**File:** `data/gazette/ingest_state.json` (new)
```json
{
  "last_ingested_folder": "2026.05.23-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT",
  "last_ingested_date": "2026-05-23",
  "last_ingested_at": "2026-07-11T21:00:00Z",
  "manifest_row_count": 312,
  "manifest_sha256": "abc123...",
  "pipeline_version": 2
}
```
**Writer:** End of `convert_xlsx_to_parquet.py:main()` — **only after the full pipeline succeeds** (see 1.4).

#### 1.3 Add curated_checksums.json (Branch A byte-identical gate)
**File:** `data/gazette/curated_checksums.json` (new)
- SHA-256 of each curated parquet after build
- CI check: rebuild → compare hashes → fail if unexpected drift

#### 1.4 Atomic state write semantics
**Pattern:**
```python
import json, os, tempfile
from pathlib import Path

STATE_FILE = Path("data/gazette/ingest_state.json")

def write_state_atomically(state: dict) -> None:
    """Write ingest state only after pipeline fully succeeds.
    
    Uses write-temp-then-rename for atomicity. If the pipeline crashes
    mid-ingest, the state file still points at the OLD version — so the
    next run will retry from scratch.
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=STATE_FILE.parent, suffix=".tmp", delete=False
    ) as tmp:
        json.dump(state, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, STATE_FILE)  # atomic on POSIX
```

#### 1.5 Parquet-in-git policy
**Decision needed before first auto-PR:**

Option A — **Git LFS** (recommended):
```gitattributes
data/gazette/curated/*.parquet filter=lfs diff=lfs merge=lfs -text
data/gazette/raw/**/*.parquet filter=lfs diff=lfs merge=lfs -text
```
Pro: repo stays small. Con: LFS has bandwidth quotas on GitHub free tier.

Option B — **Release artifacts**: parquets built in CI, attached as release assets, downloaded at deploy time. Pro: zero repo bloat. Con: more complex deploy.

Option C — **Accept churn** (current): parquets stay in regular git. Pro: simplest. Con: 500MB+ repo within a year.

**Recommendation: Option A (LFS) before the first auto-PR.** Migrate existing parquets in one batch.

---

### Phase 2: Monitoring + fetch

#### 2.1 sut_monitor.py
**File:** `scripts/sut/sut_monitor.py` (new, ~100 LOC)

**v2 fixes:** corrected URL, added `os` import, proper GITHUB_OUTPUT handling.

```python
"""Monitor sgk.gov.tr for new SUT amendment tebliğ publications.

Usage:
    python scripts/sut/sut_monitor.py
    # Exits 0 always — outputs via GITHUB_OUTPUT or stdout.
    # If run locally (no GITHUB_OUTPUT), prints to stderr.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests

SGK_DUYURU_URL = "https://www.sgk.gov.tr/Duyuru"  # FIXED: was /Duyuru/TumunuGor (404)
SUT_SLUG_PATTERN = re.compile(
    r'href="(/duyuru/detay/(\d{2})(\d{2})(\d{4})-SUT-Degisiklik[^"]*)"',
    re.IGNORECASE,
)
STATE_FILE = Path("data/gazette/ingest_state.json")


def fetch_duyuru_page() -> str:
    """Fetch the SGK duyuru listing (server-rendered HTML, no JS)."""
    resp = requests.get(SGK_DUYURU_URL, timeout=30)
    resp.raise_for_status()
    return resp.text


def find_sut_tebliğs(html: str) -> list[dict]:
    """Extract SUT tebliğ duyuru slugs + dates from the listing."""
    results = []
    for match in SUT_SLUG_PATTERN.finditer(html):
        slug, dd, mm, yyyy = match.groups()
        results.append({
            "url": f"https://www.sgk.gov.tr{slug}",
            "date": f"{yyyy}-{mm}-{dd}",
            "slug": slug,
        })
    return sorted(results, key=lambda t: t["date"], reverse=True)


def check_for_new(state: dict, tebliğs: list[dict]) -> dict | None:
    """Return the newest tebliğ newer than last_ingested_date, or None."""
    last_date = state.get("last_ingested_date", "2000-01-01")
    for t in tebliğs:
        if t["date"] > last_date:
            return t
    return None


def _output(key: str, value: str) -> None:
    """Write to GITHUB_OUTPUT or stderr."""
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"{key}={value}\n")
    else:
        print(f"[monitor] {key}={value}", file=sys.stderr)


def main() -> int:
    if not STATE_FILE.exists():
        print(f"State file not found: {STATE_FILE}", file=sys.stderr)
        return 1

    state = json.loads(STATE_FILE.read_text())
    html = fetch_duyuru_page()
    tebliğs = find_sut_tebliğs(html)

    if not tebliğs:
        print("No SUT tebliğ slugs found on duyuru page.", file=sys.stderr)
        return 0

    new = check_for_new(state, tebliğs)
    if new:
        print(f"NEW SUT tebliğ detected: {new['date']}")
        print(f"URL: {new['url']}")
        _output("new_tebliğ", json.dumps(new))
        _output("new_tebliğ_date", new["date"])
        _output("new_tebliğ_url", new["url"])
    else:
        print("No new SUT tebliğ.")
        _output("new_tebliğ", "")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

#### 2.2 sut_fetch.py
**File:** `scripts/sut/sut_fetch.py` (new, ~100 LOC)

**v2 fixes:** added `sys` import, verified download link regex.

```python
"""Download and extract a new SUT consolidated package from SGK duyuru.

Usage:
    python scripts/sut/sut_fetch.py <DUYURU_URL> <TEBLİĞ_DATE>

The duyuru detail page contains a static zip download link:
    /Download/DownloadFile?f=<guid>.zip&d=<guid>
Verified 2026-07-12: HTTP 200, 30MB, application/x-zip-compressed.
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

from scripts.sut._common import _CONSOLIDATED_SUT_DIR_SUFFIX

DOWNLOAD_LINK_PATTERN = re.compile(
    r'href="(/Download/DownloadFile\?f=[a-f0-9-]+\.zip&d=[a-f0-9-]+)"',
    re.IGNORECASE,
)


def parse_duyuru_detail(duyuru_url: str) -> str:
    """Fetch duyuru detail page, find the zip download link.

    Returns the full download URL.
    """
    resp = requests.get(duyuru_url, timeout=30)
    resp.raise_for_status()
    matches = DOWNLOAD_LINK_PATTERN.findall(resp.text)
    if not matches:
        # Fallback: broader pattern without requiring .zip extension
        broad = re.findall(
            r'href="(/Download/DownloadFile\?f=[a-f0-9-]+[^"]*)"', resp.text
        )
        if broad:
            matches = broad
    if not matches:
        raise ValueError(f"No download link found in duyuru: {duyuru_url}")
    return f"https://www.sgk.gov.tr{matches[0]}"


def download_and_extract(
    zip_url: str, tebliğ_date: str, raw_data_root: str = "raw data"
) -> Path:
    """Download zip and extract to raw data/<DATE>.<suffix>/."""
    folder_name = (
        f"{tebliğ_date.replace('-', '.')}-"
        f"{_CONSOLIDATED_SUT_DIR_SUFFIX}"
    )
    target_dir = Path(raw_data_root) / folder_name
    if target_dir.exists():
        print(f"Target already exists: {target_dir}")
        return target_dir

    resp = requests.get(zip_url, timeout=120, stream=True)
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        shutil.copyfileobj(resp.raw, tmp)
        tmp_path = tmp.name

    try:
        with zipfile.ZipFile(tmp_path) as zf:
            target_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(target_dir)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    print(f"Extracted to: {target_dir}")
    return target_dir


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: sut_fetch.py <DUYURU_URL> <TEBLİĞ_DATE>", file=sys.stderr)
        return 1

    duyuru_url = sys.argv[1]
    tebliğ_date = sys.argv[2]

    zip_url = parse_duyuru_detail(duyuru_url)
    print(f"Download URL: {zip_url}")
    target = download_and_extract(zip_url, tebliğ_date)
    print(f"SUT package extracted to: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

### Phase 3: Delta computation

#### 3.1 sut_delta.py
**File:** `scripts/sut/sut_delta.py` (new, ~150 LOC)

**v2 fixes:** added `sys` import, correct boundary handling (`valid_to >= date` is correct for as-of semantics because `valid_to` is the last day the version is in effect — exclusive boundary would miss the effective date itself).

```python
"""Compute what changed between old and new SUT catalog versions.

Usage:
    python scripts/sut/sut_delta.py <OLD_DATE> <NEW_DATE>

Outputs:
    data/gazette/deltas/<NEW_DATE>_delta.json
    GITHUB_OUTPUT: delta_summary (human-readable string for PR body)
"""
from __future__ import annotations

import json
import os
import polars as pl
import sys
from datetime import date
from pathlib import Path

CURATED_DIR = Path("data/gazette/curated")
DELTA_DIR = Path("data/gazette/deltas")


def compute_catalog_delta(
    annex: str,
    history_key: str,
    value_cols: list[str],
    old_date: str,
    new_date: str,
) -> dict:
    """Compare two as-of slices of a curated history parquet."""
    parquet_path = CURATED_DIR / f"{annex}_catalog_history.parquet"
    if not parquet_path.exists():
        return {"annex": annex, "error": f"parquet not found: {parquet_path}"}

    df = pl.read_parquet(parquet_path)

    # As-of slice: valid_from <= date AND (valid_to is null OR valid_to >= date)
    # This is correct: valid_to is the LAST day the version is in effect.
    # An exclusive boundary (> date) would miss the exact effective date.
    def asof(d: str) -> pl.DataFrame:
        return df.filter(
            (pl.col("valid_from") <= d)
            & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= d))
        )

    old_slice = asof(old_date)
    new_slice = asof(new_date)

    old_keys = set(old_slice[history_key].to_list())
    new_keys = set(new_slice[history_key].to_list())

    delta = {
        "annex": annex,
        "old_count": len(old_keys),
        "new_count": len(new_keys),
        "new_codes": sorted(new_keys - old_keys),
        "removed_codes": sorted(old_keys - new_keys),
        "common_codes": len(old_keys & new_keys),
        "price_changes": [],
        "name_changes": [],
    }

    old_by_key = {r[history_key]: r for r in old_slice.to_dicts()}
    new_by_key = {r[history_key]: r for r in new_slice.to_dicts()}

    for key in sorted(old_keys & new_keys):
        old_row = old_by_key[key]
        new_row = new_by_key[key]
        for col in value_cols:
            old_val = old_row.get(col)
            new_val = new_row.get(col)
            if old_val != new_val:
                change = {"code": key, "field": col, "old": old_val, "new": new_val}
                if col in ("puan", "price_try"):
                    delta["price_changes"].append(change)
                else:
                    delta["name_changes"].append(change)

    return delta


def format_summary(deltas: list[dict]) -> str:
    """Format delta summary for PR body."""
    lines = ["## SUT Delta Summary", ""]
    for d in deltas:
        if "error" in d:
            lines.append(f"### {d['annex']}: ⚠️ {d['error']}")
            continue
        lines.append(f"### {d['annex'].upper()}")
        lines.append(f"- Codes: {d['old_count']} → {d['new_count']} ({d['new_count'] - d['old_count']:+d})")
        lines.append(f"- New: {len(d['new_codes'])}")
        lines.append(f"- Removed: {len(d['removed_codes'])}")
        lines.append(f"- Price changes: {len(d['price_changes'])}")
        lines.append(f"- Name changes: {len(d['name_changes'])}")
        if d["new_codes"][:5]:
            lines.append(f"  Sample new: {', '.join(d['new_codes'][:5])}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: sut_delta.py <OLD_DATE> <NEW_DATE>", file=sys.stderr)
        return 1

    old_date, new_date = sys.argv[1], sys.argv[2]

    deltas = [
        compute_catalog_delta("ek2b", "code", ["puan", "price_try", "name"], old_date, new_date),
        compute_catalog_delta("ek2c", "package_code", ["puan", "price_try", "name"], old_date, new_date),
        compute_catalog_delta("ek2c_dental", "code", ["puan", "price_try", "name"], old_date, new_date),
    ]

    summary = {
        "old_date": old_date,
        "new_date": new_date,
        "generated_at": date.today().isoformat(),
        "catalogs": deltas,
    }

    DELTA_DIR.mkdir(parents=True, exist_ok=True)
    output = DELTA_DIR / f"{new_date}_delta.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str))

    body = format_summary(deltas)
    print(body)

    # Output for GitHub Actions PR body
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            # Multi-line output uses delimiter syntax
            f.write("delta_summary<<DELIMITER\n")
            f.write(body)
            f.write("\nDELIMITER\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

### Phase 4: GitHub Actions workflow

#### 4.1 sut-monitor.yml
**File:** `.github/workflows/sut-monitor.yml` (new)

**v2 fixes:** `body:` not `body-path:`, explicit human-review gate, atomic state write.

```yaml
name: SUT Monitor

on:
  schedule:
    # 2×/day at 06:00 and 18:00 UTC (09:00/21:00 TRT)
    - cron: "0 6,18 * * *"
  workflow_dispatch: # Manual trigger

jobs:
  monitor:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install deps
        run: pip install polars requests pyarrow openpyxl xlrd

      - name: Check for new SUT tebliğ
        id: monitor
        run: python scripts/sut/sut_monitor.py

      - name: Skip — no new tebliğ
        if: steps.monitor.outputs.new_tebliğ == ''
        run: echo "No new SUT tebliğ detected. Exiting."

      - name: Fetch new SUT package
        if: steps.monitor.outputs.new_tebliğ != ''
        run: |
          python scripts/sut/sut_fetch.py \
            "${{ steps.monitor.outputs.new_tebliğ_url }}" \
            "${{ steps.monitor.outputs.new_tebliğ_date }}"

      - name: Run ingest pipeline
        if: steps.monitor.outputs.new_tebliğ != ''
        run: |
          python scripts/sut/convert_xlsx_to_parquet.py
          python scripts/sut/build_curated_catalogs.py --overwrite

      - name: Compute delta
        if: steps.monitor.outputs.new_tebliğ != ''
        id: delta
        run: |
          OLD_DATE=$(python3 -c "import json; print(json.load(open('data/gazette/ingest_state.json'))['last_ingested_date'])")
          python scripts/sut/sut_delta.py "$OLD_DATE" "${{ steps.monitor.outputs.new_tebliğ_date }}"

      - name: Update ingest state (only on success)
        if: steps.monitor.outputs.new_tebliğ != ''
        run: |
          python3 -c "
          import json, os, tempfile, hashlib
          from datetime import datetime, timezone
          from pathlib import Path

          state = json.load(open('data/gazette/ingest_state.json'))
          new_date = '${{ steps.monitor.outputs.new_tebliğ_date }}'
          new_folder = '${{ steps.monitor.outputs.new_tebliğ }}'

          manifest = Path('data/gazette/version_manifest.parquet')
          sha = hashlib.sha256(manifest.read_bytes()).hexdigest()[:16]

          new_state = {
              **state,
              'last_ingested_date': new_date,
              'last_ingested_at': datetime.now(timezone.utc).isoformat(),
              'manifest_sha256': sha,
              'pipeline_version': 2,
          }

          # Atomic write
          with tempfile.NamedTemporaryFile(mode='w', dir='data/gazette', suffix='.tmp', delete=False) as tmp:
              json.dump(new_state, tmp, indent=2, ensure_ascii=False)
              tmp.flush()
              os.fsync(tmp.fileno())
          os.replace(tmp.name, 'data/gazette/ingest_state.json')
          print('State updated atomically.')
          "

      - name: Create PR
        if: steps.monitor.outputs.new_tebliğ != ''
        uses: peter-evans/create-pull-request@v6
        with:
          title: "chore(sut): ingest ${{ steps.monitor.outputs.new_tebliğ_date }} amendment"
          body: ${{ steps.delta.outputs.delta_summary }}
          branch: chore/sut-auto-update
          labels: sut-update, automated
          commit-message: "chore(sut): auto-ingest ${{ steps.monitor.outputs.new_tebliğ_date }} SUT amendment"
          # NOTE: This PR must NOT auto-merge. Human review required.
          # Branch protection on chore/sut-auto-update enforces this.
```

---

### Phase 5: Tests

#### 5.1 test_sut_monitor.py
- Mock sgk.gov.tr `/Duyuru` HTML response (fixture from saved HTML)
- Test slug parsing: `01072026-SUT-Degisiklik...` → date `2026-07-01`
- Test "no new tebliğ" path (state date ≥ newest tebliğ)
- Test "new tebliğ found" path (state date < newest tebliğ)
- Test malformed HTML (no slugs found)

#### 5.2 test_sut_fetch.py
- Mock duyuru detail page HTML (fixture with verified download link)
- Test `parse_duyuru_detail` extracts correct download URL
- Test `download_and_extract` with a mock zip file
- Test target-dir-already-exists path

#### 5.3 test_sut_delta.py
- Build two small Polars DataFrames with known differences
- Test new_codes detection
- Test removed_codes detection
- Test price_changes detection (same code, different puan)
- Test name_changes detection
- Test no-change case (identical slices)
- Test boundary: valid_to == new_date (should be included)

#### 5.4 test_ingest_state.py
- Test atomic write (temp + rename)
- Test state comparison logic
- Test missing state file error

---

## Out of Scope (deliberately)

- **Scrapy/Selenium** — SGK HTML is server-rendered, plain `requests` suffices
- **Celery/RabbitMQ** — cadence is ≤ few events/month, overkill
- **Resmi Gazete scraping** — SGK duyuru already links the ready-to-ingest zip
- **RSS** — SGK RSS is broken (404), confirmed
- **Katsayı auto-detection** — 0.593 changes annually; leave as manual for now, add a delta alert if the SUT text mentions a different value
- **Snapshot builder** — existing snapshots work; rebuilding is a separate task
- **Branch B (prose rules) auto-update** — extract_sut_prose.py + compile_rules.py changes when the SUT docx changes, but prose-rule authoring is human work; just trigger the compiler, don't auto-author rules

---

## Risk Assessment (updated)

| Risk | Impact | Mitigation |
|------|--------|------------|
| SGK changes duyuru HTML structure | Monitor breaks | Regex is broad; test fixtures catch regressions |
| Download link format changes | Fetch breaks | Verified 2026-07-12; fallback patterns; manual trigger available |
| New SUT breaks ingest (new columns, format change) | Pipeline stalls | CI will catch via existing tests; PR review gate (human must merge) |
| Parquet repo bloat (300+ files/ingest) | Repo grows fast | **Phase 1.5: Git LFS before first auto-PR** |
| Pipeline crashes mid-ingest | Inconsistent state | **Atomic state write — only updates after full pipeline success** |
| Auto-PR merged without review | Bad data deployed | **Branch protection on chore/sut-auto-update — human review required** |
| SGK publishes multiple tebliğ in one day | Edge case | Monitor handles latest-first; one PR per run |

---

## Execution Order

1. **Phase 1.1:** Fix absolute paths in version_manifest (1 hour)
2. **Phase 1.2+1.4:** Add ingest_state.json + atomic writer (1 hour)
3. **Phase 1.3:** Add curated_checksums.json (30 min)
4. **Phase 1.5:** Git LFS setup (30 min)
5. **Phase 2.1:** Write sut_monitor.py (1 hour)
6. **Phase 2.2:** Write sut_fetch.py (1 hour)
7. **Phase 3.1:** Write sut_delta.py (1 hour)
8. **Phase 4.1:** Write sut-monitor.yml (30 min)
9. **Phase 5:** Write tests (2 hours)
10. **Manual validation:** Trigger workflow_dispatch, verify it fetches + ingests + creates PR

**Total: ~1.5 days of implementation.**
