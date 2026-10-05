#!/usr/bin/env python3
"""Download and extract a new SUT consolidated package from an SGK duyuru.

Usage:
    python scripts/sut/sut_fetch.py <DUYURU_URL> <TEBLİĞ_DATE>

The duyuru detail page contains a static zip download link:
    /Download/DownloadFile?f=<guid>.zip&d=<guid>
Verified 2026-07-12: HTTP 200, 30MB, application/x-zip-compressed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

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
PACKAGE_INVENTORY_FILENAME = ".sut_package_inventory.json"


def _safe_extractall(zf: zipfile.ZipFile, target_dir: Path) -> list[zipfile.ZipInfo]:
    """Extract all members, rejecting any path that escapes ``target_dir``.

    Guards against zip-slip (path traversal via ``../`` entries) on zips
    downloaded from external sources.
    """
    members = zf.infolist()
    paths: dict[str, bool] = {}
    for member in members:
        name = member.filename
        path = PurePosixPath(name)
        if (
            not name
            or "\x00" in member.orig_filename
            or "\\" in name
            or path.is_absolute()
            or PureWindowsPath(name).drive
            or ".." in path.parts
            or str(path) == "."
            or name.rstrip("/") != str(path)
            or str(path) == PACKAGE_INVENTORY_FILENAME
        ):
            raise ValueError(f"Refusing unsafe ZIP member: {name!r}")
        normalized = str(path)
        if normalized in paths:
            raise ValueError(f"Duplicate ZIP member: {name!r}")
        mode = stat.S_IFMT(member.external_attr >> 16)
        if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError(f"Refusing non-regular ZIP member: {name!r}")
        if (mode == stat.S_IFDIR and not member.is_dir()) or (
            mode == stat.S_IFREG and member.is_dir()
        ):
            raise ValueError(f"Invalid ZIP directory member: {name!r}")
        paths[normalized] = member.is_dir()
    for name in paths:
        if any(paths.get(str(parent)) is False for parent in PurePosixPath(name).parents):
            raise ValueError(f"ZIP member has a file parent: {name!r}")
    if not any(not member.is_dir() for member in members):
        raise ValueError("SUT ZIP contains no source files")
    zf.extractall(target_dir)
    return members


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _validate_existing(target_dir: Path, files: dict[str, dict], receipt: bytes) -> None:
    """Require an existing capture to be a byte-identical subset of the ZIP."""
    if target_dir.is_symlink() or not target_dir.is_dir():
        raise ValueError(f"SUT target is not a regular directory: {target_dir}")
    for path in target_dir.rglob("*"):
        relative = path.relative_to(target_dir).as_posix()
        if path.is_symlink():
            raise ValueError(f"Refusing existing symlink: {relative!r}")
        if path.is_dir():
            if relative in files:
                raise ValueError(f"Existing directory conflicts with ZIP file: {relative!r}")
            continue
        if not path.is_file():
            raise ValueError(f"Refusing non-regular existing entry: {relative!r}")
        if relative == PACKAGE_INVENTORY_FILENAME:
            if path.read_bytes() != receipt:
                raise ValueError("Existing SUT package inventory does not match downloaded ZIP")
        elif relative not in files:
            raise ValueError(f"Existing file absent from ZIP inventory: {relative!r}")
        elif (
            path.stat().st_size != files[relative]["size_bytes"]
            or _sha256(path) != files[relative]["sha256"]
        ):
            raise ValueError(f"Existing source file differs from downloaded ZIP: {relative!r}")


def _hydrate_existing(staged: Path, target: Path, files: dict[str, dict]) -> None:
    """Install missing files only; roll back any interrupted installation."""
    created_files: list[Path] = []
    created_dirs: list[Path] = []
    try:
        # Write the receipt last: its presence must never certify a partial copy.
        for name in [*files, PACKAGE_INVENTORY_FILENAME]:
            destination = target / name
            if destination.exists():
                if destination.is_symlink() or not destination.is_file():
                    raise ValueError(f"Existing destination is not a regular file: {name!r}")
                if name == PACKAGE_INVENTORY_FILENAME:
                    if destination.read_bytes() != (staged / name).read_bytes():
                        raise ValueError("Existing SUT package inventory changed during hydration")
                elif _sha256(destination) != files[name]["sha256"]:
                    raise ValueError(f"Existing source file changed during hydration: {name!r}")
                continue
            missing_dirs: list[Path] = []
            parent = destination.parent
            while parent != target and not parent.exists():
                missing_dirs.append(parent)
                parent = parent.parent
            for directory in reversed(missing_dirs):
                directory.mkdir()
                created_dirs.append(directory)
            # Exclusive creation also prevents overwriting a concurrently added file.
            with destination.open("xb") as output:
                created_files.append(destination)
                with (staged / name).open("rb") as source:
                    shutil.copyfileobj(source, output)
    except Exception:
        for path in reversed(created_files):
            path.unlink(missing_ok=True)
        for path in reversed(created_dirs):
            path.rmdir()
        raise


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
    source = urlsplit(zip_url)
    if (
        source.scheme != "https"
        or source.hostname not in {"sgk.gov.tr", "www.sgk.gov.tr"}
        or source.port not in (None, 443)
        or source.username is not None
        or source.password is not None
        or source.path != "/Download/DownloadFile"
        or source.fragment
    ):
        raise ValueError("SUT ZIP must use the official SGK HTTPS download endpoint")
    if date.fromisoformat(tebliğ_date).isoformat() != tebliğ_date:
        raise ValueError("SUT package date must use YYYY-MM-DD")
    folder_name = (
        f"{tebliğ_date.replace('-', '.')}-{_CONSOLIDATED_SUT_DIR_SUFFIX}"
    )
    target_dir = raw_data_root / folder_name

    resp = requests.get(zip_url, timeout=120, stream=True, allow_redirects=False)
    try:
        resp.raise_for_status()
        if resp.status_code != 200:
            raise ValueError("SUT ZIP download must return a complete HTTP 200 response without redirects")
        total = int(resp.headers.get("content-length", 0))
        print(f"Downloading {total / 1e6:.1f} MB from {zip_url}")
        raw_data_root.mkdir(parents=True, exist_ok=True)
        # Download, validate every member and extract completely before touching
        # an existing capture. Staging shares the target filesystem for rename.
        with tempfile.TemporaryDirectory(prefix=".sut-fetch-", dir=raw_data_root) as temporary:
            temporary_dir = Path(temporary)
            zip_path = temporary_dir / "package.zip"
            with zip_path.open("wb") as output:
                shutil.copyfileobj(resp.raw, output)
            staged = temporary_dir / "contents"
            with zipfile.ZipFile(zip_path) as zf:
                members = _safe_extractall(zf, staged)
            files = {
                member.filename: {
                    "path": member.filename,
                    "sha256": _sha256(staged / member.filename),
                    "size_bytes": member.file_size,
                }
                for member in sorted(members, key=lambda item: item.filename)
                if not member.is_dir()
            }
            inventory = {
                "schema_version": 1,
                "teblig_date": tebliğ_date,
                "download_url": zip_url,
                "zip_sha256": _sha256(zip_path),
                "files": list(files.values()),
            }
            receipt = (json.dumps(inventory, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            (staged / PACKAGE_INVENTORY_FILENAME).write_bytes(receipt)
            if target_dir.exists() or target_dir.is_symlink():
                _validate_existing(target_dir, files, receipt)
                _hydrate_existing(staged, target_dir, files)
            else:
                staged.rename(target_dir)
            print(f"Verified {len(files)} source files in: {target_dir}")
    finally:
        resp.close()
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
    if output_path := os.environ.get("GITHUB_OUTPUT"):
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write(f"input_dir={target.resolve()}\n")
            output.write(f"inventory_path={(target / PACKAGE_INVENTORY_FILENAME).resolve()}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
