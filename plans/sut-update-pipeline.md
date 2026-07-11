# SUT Update Pipeline — Architecture & Implementation Plan

**Branch:** `feat/sut-update-pipeline`
**Goal:** Automated monitoring + ingestion + delta computation for SUT amendments, triggering on new SGK tebliğ publications.

---

## Current State (verified)

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
└─────────────────────┬────────────────────────────────────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │ 1. sut_monitor.py                  │
    │    Fetch sgk.gov.tr/duyuru page 1  │
    │    Regex: SUT tebliği slugs        │
    │    Compare vs ingest_state.json    │
    │    If new → continue; else exit 0  │
    └─────────────────┬──────────────────┘
                      │ new tebliğ found
    ┌─────────────────▼──────────────────┐
    │ 2. sut_fetch.py                    │
    │    Parse duyuru detail page HTML   │
    │    Find DownloadFile?f=<guid>.zip  │
    │    Download ~30MB zip              │
    │    Extract to raw data/<DATE>-...  │
    └─────────────────┬──────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │ 3. Existing ingest chain           │
    │    convert_xlsx_to_parquet.py      │
    │    build_curated_catalogs.py       │
    │    compile_rules.py (if docx       │
    │    changed)                        │
    └─────────────────┬──────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │ 4. sut_delta.py                    │
    │    Load old + new curated parquets │
    │    Polars set-ops:                 │
    │      - new_codes                   │
    │      - removed_codes               │
    │      - price_changes               │
    │      - puan_changes                │
    │      - name_changes                │
    │    Write data/gazette/deltas/      │
    │      <DATE>_delta.json             │
    └─────────────────┬──────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │ 5. Auto-PR                          │
    │    peter-evans/create-pull-request │
    │    PR title: "chore(sut): ingest   │
    │    <DATE> amendment"               │
    │    PR body: delta summary          │
    └────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Fix infrastructure debt (prerequisites)

#### 1.1 Fix absolute paths in version_manifest
**File:** `scripts/sut/convert_xlsx_to_parquet.py` (around L283 `build_manifest`)
- Change `parquet_path` to repo-relative (`data/gazette/raw/annex=...`)
- Migrate existing manifest with a one-time path-normalization script

#### 1.2 Add ingest_state.json
**File:** `data/gazette/ingest_state.json` (new)
```json
{
  "last_ingested_folder": "2026.05.23-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT",
  "last_ingested_date": "2026-05-23",
  "last_ingested_at": "2026-07-11T21:00:00Z",
  "manifest_row_count": 312,
  "manifest_sha256": "abc123...",
  "pipeline_version": 1
}
```
**Writer:** End of `convert_xlsx_to_parquet.py:main()`

#### 1.3 Add curated_checksums.json (Branch A byte-identical gate)
**File:** `data/gazette/curated_checksums.json` (new)
- SHA-256 of each curated parquet after build
- CI check: rebuild → compare hashes → fail if unexpected drift

---

### Phase 2: Monitoring + fetch

#### 2.1 sut_monitor.py
**File:** `scripts/sut/sut_monitor.py` (new, ~100 LOC)
```python
"""Monitor sgk.gov.tr for new SUT amendment tebliğ publications."""
import re, json, sys, requests
from pathlib import Path

SGK_DUYURU_URL = "https://www.sgk.gov.tr/Duyuru/TumunuGor"
SUT_SLUG_PATTERN = re.compile(
    r'href="(/duyuru/detay/[^"]*SUT-Degisiklik-Tebligi[^"]*)"',
    re.IGNORECASE
)
STATE_FILE = Path("data/gazette/ingest_state.json")

def fetch_duyuru_page() -> str:
    """Fetch the SGK duyuru listing (server-rendered HTML, no JS)."""
    resp = requests.get(SGK_DUYURU_URL, timeout=30)
    resp.raise_for_status()
    return resp.text

def find_sut_tebliğs(html: str) -> list[dict]:
    """Extract SUT tebliğ duyuru slugs + dates from the listing."""
    matches = SUT_SLUG_PATTERN.findall(html)
    # Parse date from slug: DDMMYYYY-SUT-Degisiklik-...
    results = []
    for slug in matches:
        date_match = re.search(r'(\d{2})(\d{2})(\d{4})', slug)
        if date_match:
            dd, mm, yyyy = date_match.groups()
            results.append({
                "url": f"https://www.sgk.gov.tr{slug}",
                "date": f"{yyyy}-{mm}-{dd}",
                "slug": slug
            })
    return results

def check_for_new(state: dict, tebliğs: list[dict]) -> dict | None:
    """Return the newest tebliğ newer than last_ingested_date, or None."""
    last_date = state.get("last_ingested_date", "2000-01-01")
    for t in tebliğs:
        if t["date"] > last_date:
            return t
    return None

def main():
    state = json.loads(STATE_FILE.read_text())
    html = fetch_duyuru_page()
    tebliğs = find_sut_tebliğs(html)
    new = check_for_new(state, tebliğs)
    if new:
        print(f"NEW SUT tebliğ detected: {new['date']}")
        print(f"URL: {new['url']}")
        # Output for GitHub Actions to consume
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"new_tebliğ={json.dumps(new)}\n")
        sys.exit(0)
    else:
        print("No new SUT tebliğ.")
        sys.exit(0)  # Exit 0 = no error, just nothing to do

if __name__ == "__main__":
    main()
```

#### 2.2 sut_fetch.py
**File:** `scripts/sut/sut_fetch.py` (new, ~120 LOC)
```python
"""Download and extract a new SUT consolidated package from SGK duyuru."""
import re, json, zipfile, requests, tempfile, shutil
from pathlib import Path
from scripts.sut._common import _CONSOLIDATED_SUT_DIR_SUFFIX

def parse_duyuru_detail(duyuru_url: str) -> str:
    """Fetch duyuru detail page, find the zip download link."""
    html = requests.get(duyuru_url, timeout=30).text
    # Pattern: /Download/DownloadFile?f=<guid>.zip or direct file link
    zip_pattern = re.compile(
        r'(https://www\.sgk\.gov\.tr/Download/DownloadFile\?f=[a-f0-9-]+[^"]*\.zip)',
        re.IGNORECASE
    )
    # Fallback: look for any large file link in the duyuru
    matches = zip_pattern.findall(html)
    if not matches:
        # Try broader pattern for consolidated SUT package
        broad = re.compile(r'(/Download/[^"]*\.(?:zip|ZIP))')
        matches = broad.findall(html)
        matches = [f"https://www.sgk.gov.tr{m}" for m in matches]
    if not matches:
        raise ValueError(f"No download link found in duyuru: {duyuru_url}")
    return matches[0]

def download_and_extract(zip_url: str, tebliğ_date: str, raw_data_root: str = "raw data"):
    """Download zip and extract to raw data/<DATE>-<suffix>/."""
    folder_name = f"{tebliğ_date.replace('-','.')}-{_CONSOLIDATED_SUT_DIR_SUFFIX}"
    target_dir = Path(raw_data_root) / folder_name
    if target_dir.exists():
        print(f"Target already exists: {target_dir}")
        return target_dir
    # Download
    resp = requests.get(zip_url, timeout=120, stream=True)
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
        shutil.copyfileobj(resp.raw, tmp)
        tmp.flush()
        with zipfile.ZipFile(tmp.name) as zf:
            target_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(target_dir)
    print(f"Extracted to: {target_dir}")
    return target_dir

def main():
    # Reads new_tebliğ from GITHUB_OUTPUT or CLI arg
    duyuru_url = sys.argv[1]
    tebliğ_date = sys.argv[2]
    zip_url = parse_duyuru_detail(duyuru_url)
    download_and_extract(zip_url, tebliğ_date)
```

---

### Phase 3: Delta computation

#### 3.1 sut_delta.py
**File:** `scripts/sut/sut_delta.py` (new, ~150 LOC)
```python
"""Compute what changed between old and new SUT catalog versions."""
import json, polars as pl
from pathlib import Path
from datetime import date

CURATED_DIR = Path("data/gazette/curated")
DELTA_DIR = Path("data/gazette/deltas")

def compute_catalog_delta(
    annex: str,  # e.g. "ek2b", "ek2c"
    history_key: str,  # e.g. "code" or "package_code"
    value_cols: list[str],  # e.g. ["puan", "price_try", "name"]
    old_date: str,
    new_date: str,
) -> dict:
    """Compare two as-of slices of a curated history parquet."""
    df = pl.read_parquet(CURATED_DIR / f"{annex}_catalog_history.parquet")
    
    old_slice = df.filter(
        (pl.col("valid_from") <= old_date) & 
        (pl.col("valid_to").is_null() | (pl.col("valid_to") >= old_date))
    )
    new_slice = df.filter(
        (pl.col("valid_from") <= new_date) & 
        (pl.col("valid_to").is_null() | (pl.col("valid_to") >= new_date))
    )
    
    old_keys = set(old_slice[history_key].to_list())
    new_keys = set(new_slice[history_key].to_list())
    
    delta = {
        "annex": annex,
        "old_date": old_date,
        "new_date": new_date,
        "new_codes": sorted(new_keys - old_keys),
        "removed_codes": sorted(old_keys - new_keys),
        "common_codes": len(old_keys & new_keys),
        "price_changes": [],
        "name_changes": [],
    }
    
    # Compare common codes for value changes
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

def main():
    old_date = sys.argv[1]  # e.g. "2026-01-31"
    new_date = sys.argv[2]  # e.g. "2026-06-29"
    
    deltas = []
    
    # EK-2B (hizmet başı)
    deltas.append(compute_catalog_delta(
        "ek2b", "code", ["puan", "price_try", "name"], old_date, new_date
    ))
    
    # EK-2C (tanıya dayalı)
    deltas.append(compute_catalog_delta(
        "ek2c", "package_code", ["puan", "price_try", "name"], old_date, new_date
    ))
    
    # EK-2Ç (dental)
    deltas.append(compute_catalog_delta(
        "ek2c_dental", "code", ["puan", "price_try", "name"], old_date, new_date
    ))
    
    # Summary
    summary = {
        "old_date": old_date,
        "new_date": new_date,
        "generated_at": date.today().isoformat(),
        "catalogs": deltas,
    }
    
    DELTA_DIR.mkdir(parents=True, exist_ok=True)
    output = DELTA_DIR / f"{new_date}_delta.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print(f"Delta written to {output}")
    print(f"  New codes: {sum(len(d['new_codes']) for d in deltas)}")
    print(f"  Removed codes: {sum(len(d['removed_codes']) for d in deltas)}")
    print(f"  Price changes: {sum(len(d['price_changes']) for d in deltas)}")
    print(f"  Name changes: {sum(len(d['name_changes']) for d in deltas)}")
```

---

### Phase 4: GitHub Actions workflow

#### 4.1 sut-monitor.yml
**File:** `.github/workflows/sut-monitor.yml` (new)
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
        run: pip install polars requests pyarrow
      
      - name: Check for new SUT tebliğ
        id: monitor
        run: python scripts/sut/sut_monitor.py
      
      - name: Fetch new SUT package
        if: steps.monitor.outputs.new_tebliğ
        run: |
          TEBLIG='${{ steps.monitor.outputs.new_tebliğ }}'
          URL=$(echo "$TEBLIG" | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])")
          DATE=$(echo "$TEBLIG" | python3 -c "import json,sys; print(json.load(sys.stdin)['date'])")
          python scripts/sut/sut_fetch.py "$URL" "$DATE"
      
      - name: Run ingest pipeline
        if: steps.monitor.outputs.new_tebliğ
        run: |
          python scripts/sut/convert_xlsx_to_parquet.py
          python scripts/sut/build_curated_catalogs.py --overwrite
      
      - name: Compute delta
        if: steps.monitor.outputs.new_tebliğ
        run: |
          OLD_DATE=$(python3 -c "import json; print(json.load(open('data/gazette/ingest_state.json'))['last_ingested_date'])")
          NEW_DATE=$(echo '${{ steps.monitor.outputs.new_tebliğ }}' | python3 -c "import json,sys; print(json.load(sys.stdin)['date'])")
          python scripts/sut/sut_delta.py "$OLD_DATE" "$NEW_DATE"
      
      - name: Create PR
        if: steps.monitor.outputs.new_tebliğ
        uses: peter-evans/create-pull-request@v6
        with:
          title: "chore(sut): ingest ${{ steps.monitor.outputs.new_tebliğ }} amendment"
          body-path: data/gazette/deltas/*_delta.json
          branch: chore/sut-auto-update
          commit-message: "chore(sut): auto-ingest new SUT amendment"
```

---

### Phase 5: Tests

#### 5.1 test_sut_monitor.py
- Mock sgk.gov.tr HTML response
- Test slug parsing
- Test "no new tebliğ" exit path
- Test "new tebliğ found" output

#### 5.2 test_sut_delta.py
- Build two small curated parquets with known differences
- Test new_codes / removed_codes / price_changes detection
- Test no-change case

#### 5.3 test_ingest_state.py
- Test state file read/write
- Test version comparison logic

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

## Execution Order

1. **Phase 1.1:** Fix absolute paths in version_manifest (1 hour)
2. **Phase 1.2:** Add ingest_state.json + writer (30 min)
3. **Phase 2.1:** Write sut_monitor.py (1 hour)
4. **Phase 2.2:** Write sut_fetch.py (1 hour)
5. **Phase 3.1:** Write sut_delta.py (1 hour)
6. **Phase 4.1:** Write sut-monitor.yml (30 min)
7. **Phase 5:** Write tests (2 hours)
8. **Manual validation:** Trigger workflow_dispatch, verify it fetches + ingests + creates PR

**Total: ~1 day of implementation.**

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| SGK changes duyuru HTML structure | Monitor breaks | Regex is broad; add HTML structure snapshot to delta |
| Download link format changes | Fetch breaks | Fallback patterns; manual trigger available |
| New SUT breaks ingest (new columns, format change) | Pipeline stalls | CI will catch via existing tests; PR review gate |
| 309 parquet files regenerated per ingest | PR noise | `.gitattributes` LFS or accept metadata churn |
| SGK publishes multiple tebliğ in one day | Edge case | Monitor handles latest-first; one PR per run |
