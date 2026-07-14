#!/usr/bin/env python3
"""Download and extract a new SUT consolidated package from an SGK duyuru.

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

# Matches the verified download link pattern from the detail page HTML.
DOWNLOAD_LINK_PATTERN = re.compile(
    r'href="(/Download/DownloadFile\?f=[a-f0-9-]+\.zip&d=[a-f0-9-]+)"',
    re.IGNORECASE,
)

# Fallback: broader pattern without requiring .zip extension.
DOWNLOAD_LINK_FALLBACK = re.compile(
    r'href="(/Download/DownloadFile\?f=[a-f0-9-]+[^"]*)"',
    re.IGNORECASE,
)

# Suffix from _common.py — duplicated here to avoid importing private
# module constants in a standalone CLI script. Must stay in sync.
_CONSOLIDATED_SUT_DIR_SUFFIX = "Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"

# Default raw data root (repo-relative).
DEFAULT_RAW_DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "raw data"


def _safe_extractall(zf: zipfile.ZipFile, target_dir: Path) -> None:
    """Extract all members, rejecting any path that escapes ``target_dir``.

    Guards against zip-slip (path traversal via ``../`` entries) on zips
    downloaded from external sources.
    """
    target_resolved = target_dir.resolve()
    for member in zf.infolist():
        member_path = (target_dir / member.filename).resolve()
        if not member_path.is_relative_to(target_resolved):
            raise ValueError(
                f"Refusing to extract member outside target dir: {member.filename!r}"
            )
    zf.extractall(target_dir)


def parse_duyuru_detail(duyuru_url: str) -> str:
    """Fetch duyuru detail page, find the zip download link.

    Returns the full download URL.
    """
    resp = requests.get(duyuru_url, timeout=30)
    resp.raise_for_status()

    matches = DOWNLOAD_LINK_PATTERN.findall(resp.text)
    if not matches:
        matches = DOWNLOAD_LINK_FALLBACK.findall(resp.text)
    if not matches:
        raise ValueError(
            f"No download link found in duyuru detail page: {duyuru_url}"
        )

    return f"https://www.sgk.gov.tr{matches[0]}"


def download_and_extract(
    zip_url: str,
    tebliğ_date: str,
    raw_data_root: Path = DEFAULT_RAW_DATA_ROOT,
) -> Path:
    """Download zip and extract to raw data/<DATE>.<suffix>/.

    Args:
        zip_url: Full URL to the zip file.
        tebliğ_date: ISO date string (YYYY-MM-DD).
        raw_data_root: Root directory for raw SUT data.

    Returns:
        Path to the extracted directory.
    """
    folder_name = (
        f"{tebliğ_date.replace('-', '.')}-{_CONSOLIDATED_SUT_DIR_SUFFIX}"
    )
    target_dir = raw_data_root / folder_name

    if target_dir.exists():
        print(f"Target already exists: {target_dir}")
        return target_dir

    resp = requests.get(zip_url, timeout=120, stream=True)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    print(f"Downloading {total / 1e6:.1f} MB from {zip_url}")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        shutil.copyfileobj(resp.raw, tmp)
        tmp_path = tmp.name

    try:
        with zipfile.ZipFile(tmp_path) as zf:
            target_dir.mkdir(parents=True, exist_ok=True)
            _safe_extractall(zf, target_dir)
        print(f"Extracted {len(list(target_dir.rglob('*')))} files to: {target_dir}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

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
