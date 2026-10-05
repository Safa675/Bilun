"""Unit tests for the SUT package fetch script."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.sut.sut_fetch import (
    PACKAGE_INVENTORY_FILENAME,
    download_and_extract,
    main,
    parse_duyuru_detail,
)

pytestmark = pytest.mark.unit

# HTML matching the real SGK duyuru detail page structure (verified 2026-07-12).
MOCK_DETAIL_HTML = """
<html><body>
  <div class="dosyalar">
    <a href="/Download/DownloadFile?f=b1fd13b3-f5da-4caf-8447-f4a80199f641.zip&d=beb41e77-38a1-4209-9f22-59e7a160b078">SUT.zip</a>
  </div>
</body></html>
"""

MOCK_DETAIL_NO_LINK = "<html><body><p>No download links here.</p></body></html>"


def test_parse_duyuru_detail_extracts_zip_url() -> None:
    """The download link regex correctly extracts the full zip URL."""
    with patch("scripts.sut.sut_fetch.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = MOCK_DETAIL_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        url = parse_duyuru_detail("https://www.sgk.gov.tr/duyuru/detay/test")

    assert "DownloadFile?f=b1fd13b3" in url
    assert ".zip" in url
    assert url.startswith("https://www.sgk.gov.tr")


def test_parse_duyuru_detail_raises_when_no_link() -> None:
    """When the detail page has no download link, raise ValueError."""
    with patch("scripts.sut.sut_fetch.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = MOCK_DETAIL_NO_LINK
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with pytest.raises(ValueError, match="No download link"):
            parse_duyuru_detail("https://www.sgk.gov.tr/duyuru/detay/test")


ZIP_URL = "https://www.sgk.gov.tr/Download/DownloadFile?f=official.zip&d=official"
PACKAGE_DATE = "2026-10-02"
DOCX_MEMBER = "2026.10.02-SUT/Güncel SUT.docx"
XLSX_MEMBER = "2026.10.02-SUT/EK-4 LİSTELERİ/EK-4A.xlsx"
SOURCE_FILES = {DOCX_MEMBER: b"reviewed prose", XLSX_MEMBER: b"official workbook"}


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return data.getvalue()


def _response(data: bytes) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-length": str(len(data))}
    response.raw = io.BytesIO(data)
    response.close.side_effect = response.raw.close
    return response


def _target(tmp_path: Path) -> Path:
    return tmp_path / "raw data" / "2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"


def _fetch(tmp_path: Path, data: bytes) -> Path:
    with patch("scripts.sut.sut_fetch.requests.get", return_value=_response(data)) as request:
        result = download_and_extract(ZIP_URL, PACKAGE_DATE, tmp_path / "raw data")
    request.assert_called_once_with(ZIP_URL, timeout=120, stream=True, allow_redirects=False)
    return result


def _snapshot(target: Path) -> dict[str, tuple[bytes, int]]:
    return {
        file.relative_to(target).as_posix(): (file.read_bytes(), file.stat().st_mtime_ns)
        for file in target.rglob("*")
        if file.is_file()
    }


def test_download_and_extract_creates_exact_inventory(tmp_path: Path) -> None:
    """The receipt pins every file, including repealed annexes, to the downloaded ZIP."""
    files = {**SOURCE_FILES, "2026.10.02-SUT/MÜLGA/EK-4A.xlsx": b"repealed workbook"}
    data = _zip_bytes(files)
    result = _fetch(tmp_path, data)
    assert result == _target(tmp_path)
    receipt = json.loads((result / PACKAGE_INVENTORY_FILENAME).read_text(encoding="utf-8"))
    assert receipt == {
        "schema_version": 1,
        "teblig_date": PACKAGE_DATE,
        "download_url": ZIP_URL,
        "zip_sha256": hashlib.sha256(data).hexdigest(),
        "files": [
            {"path": name, "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
            for name, content in sorted(files.items())
        ],
    }
    for name, content in files.items():
        assert (result / name).read_bytes() == content
    assert not list(result.parent.glob(".sut-fetch-*"))


def test_existing_docx_only_capture_is_hydrated_without_rewriting(tmp_path: Path) -> None:
    target = _target(tmp_path)
    docx = target / DOCX_MEMBER
    docx.parent.mkdir(parents=True)
    docx.write_bytes(SOURCE_FILES[DOCX_MEMBER])
    original = (docx.read_bytes(), docx.stat().st_mtime_ns)
    assert _fetch(tmp_path, _zip_bytes(SOURCE_FILES)) == target
    assert (docx.read_bytes(), docx.stat().st_mtime_ns) == original
    assert (target / XLSX_MEMBER).read_bytes() == SOURCE_FILES[XLSX_MEMBER]
    assert (target / PACKAGE_INVENTORY_FILENAME).is_file()


def test_same_package_rerun_preserves_every_byte_and_mtime(tmp_path: Path) -> None:
    data = _zip_bytes(SOURCE_FILES)
    target = _fetch(tmp_path, data)
    original = _snapshot(target)
    assert _fetch(tmp_path, data) == target
    assert _snapshot(target) == original


@pytest.mark.parametrize("existing_content", [b"same length!!?", b"different longer content"])
def test_divergent_existing_source_is_not_overwritten(tmp_path: Path, existing_content: bytes) -> None:
    target = _target(tmp_path)
    docx = target / DOCX_MEMBER
    docx.parent.mkdir(parents=True)
    docx.write_bytes(existing_content)
    original = _snapshot(target)
    with pytest.raises(ValueError, match="Existing source file differs"):
        _fetch(tmp_path, _zip_bytes(SOURCE_FILES))
    assert _snapshot(target) == original
    assert not (target / XLSX_MEMBER).exists()


def test_existing_unknown_source_is_not_silently_admitted(tmp_path: Path) -> None:
    target = _target(tmp_path)
    target.mkdir(parents=True)
    (target / "unverified.xlsx").write_bytes(b"unknown source")
    original = _snapshot(target)
    with pytest.raises(ValueError, match="absent from ZIP inventory"):
        _fetch(tmp_path, _zip_bytes(SOURCE_FILES))
    assert _snapshot(target) == original


def test_conflicting_existing_receipt_is_not_replaced(tmp_path: Path) -> None:
    data = _zip_bytes(SOURCE_FILES)
    target = _fetch(tmp_path, data)
    (target / PACKAGE_INVENTORY_FILENAME).write_text("{}\n", encoding="utf-8")
    original = _snapshot(target)
    with pytest.raises(ValueError, match="inventory does not match"):
        _fetch(tmp_path, data)
    assert _snapshot(target) == original


@pytest.mark.parametrize(
    "name",
    ["../escape.xlsx", "/absolute.xlsx", "nested/../../escape.xlsx", "C:/drive.xlsx",
     "nested\\..\\escape.xlsx", "./alias.xlsx", "nested//alias.xlsx", PACKAGE_INVENTORY_FILENAME],
)
def test_unsafe_zip_paths_leave_existing_tree_unchanged(tmp_path: Path, name: str) -> None:
    target = _target(tmp_path)
    target.mkdir(parents=True)
    (target / "reviewed.docx").write_bytes(b"keep")
    original = _snapshot(target)
    with pytest.raises(ValueError, match="unsafe ZIP member"):
        _fetch(tmp_path, _zip_bytes({"safe.xlsx": b"safe", name: b"unsafe"}))
    assert _snapshot(target) == original
    assert not (tmp_path / "escape.xlsx").exists()
    assert not list(target.parent.glob(".sut-fetch-*"))


def test_duplicate_zip_member_is_rejected_before_extraction(tmp_path: Path) -> None:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("same.xlsx", b"first")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("same.xlsx", b"second")
    with pytest.raises(ValueError, match="Duplicate ZIP member"):
        _fetch(tmp_path, data.getvalue())
    assert not _target(tmp_path).exists()


def test_zip_file_directory_collision_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="file parent"):
        _fetch(tmp_path, _zip_bytes({"folder": b"file", "folder/source.xlsx": b"nested"}))
    assert not _target(tmp_path).exists()


def test_zip_symlink_is_rejected(tmp_path: Path) -> None:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        member = zipfile.ZipInfo("link.xlsx")
        member.create_system = 3
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(member, "../outside.xlsx")
    with pytest.raises(ValueError, match="non-regular ZIP member"):
        _fetch(tmp_path, data.getvalue())
    assert not _target(tmp_path).exists()


def test_existing_symlink_is_not_followed(tmp_path: Path) -> None:
    target = _target(tmp_path)
    target.mkdir(parents=True)
    outside = tmp_path / "outside.xlsx"
    outside.write_bytes(b"outside")
    (target / "link.xlsx").symlink_to(outside)
    with pytest.raises(ValueError, match="existing symlink"):
        _fetch(tmp_path, _zip_bytes({"link.xlsx": b"outside"}))
    assert outside.read_bytes() == b"outside"
    assert (target / "link.xlsx").is_symlink()
    assert not (target / PACKAGE_INVENTORY_FILENAME).exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://www.sgk.gov.tr/Download/DownloadFile?f=official.zip",
        "https://unofficial.example/Download/DownloadFile?f=official.zip",
        "https://www.sgk.gov.tr.evil.example/Download/DownloadFile?f=official.zip",
        "https://user:pass@www.sgk.gov.tr/Download/DownloadFile?f=official.zip",
        "https://www.sgk.gov.tr:8443/Download/DownloadFile?f=official.zip",
        "https://www.sgk.gov.tr/other/file.zip",
        "https://www.sgk.gov.tr/Download/DownloadFile?f=official.zip#fragment",
    ],
)
def test_unofficial_download_url_is_rejected_before_network(tmp_path: Path, url: str) -> None:
    with patch("scripts.sut.sut_fetch.requests.get") as request:
        with pytest.raises(ValueError, match="official SGK HTTPS"):
            download_and_extract(url, PACKAGE_DATE, tmp_path / "raw data")
    request.assert_not_called()
    assert not (tmp_path / "raw data").exists()


@pytest.mark.parametrize("package_date", ["20261002", "2026-10-02/../../elsewhere", "2026-99-01"])
def test_invalid_package_date_is_rejected_before_network(tmp_path: Path, package_date: str) -> None:
    with patch("scripts.sut.sut_fetch.requests.get") as request:
        with pytest.raises(ValueError):
            download_and_extract(ZIP_URL, package_date, tmp_path / "raw data")
    request.assert_not_called()
    assert not (tmp_path / "raw data").exists()


def test_empty_zip_cannot_create_completion_receipt(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no source files"):
        _fetch(tmp_path, _zip_bytes({}))
    assert not _target(tmp_path).exists()


@pytest.mark.parametrize("existing", [False, True])
def test_failed_extraction_does_not_change_target(tmp_path: Path, existing: bool) -> None:
    target = _target(tmp_path)
    if existing:
        docx = target / DOCX_MEMBER
        docx.parent.mkdir(parents=True)
        docx.write_bytes(SOURCE_FILES[DOCX_MEMBER])
    original = _snapshot(target)

    def incomplete_extraction(archive, destination):
        destination.mkdir()
        (destination / "half-written.xlsx").write_bytes(b"partial")
        raise OSError("extraction interrupted")

    with patch("scripts.sut.sut_fetch.zipfile.ZipFile.extractall", incomplete_extraction):
        with pytest.raises(OSError, match="extraction interrupted"):
            _fetch(tmp_path, _zip_bytes(SOURCE_FILES))
    assert _snapshot(target) == original
    assert target.exists() is existing
    assert not list(target.parent.glob(".sut-fetch-*"))


def test_download_failure_preserves_partial_capture(tmp_path: Path) -> None:
    target = _target(tmp_path)
    target.mkdir(parents=True)
    (target / "reviewed.docx").write_bytes(b"keep")
    original = _snapshot(target)
    response = _response(b"partial zip")
    response.raw = MagicMock()
    response.raw.read.side_effect = OSError("connection interrupted")
    with patch("scripts.sut.sut_fetch.requests.get", return_value=response):
        with pytest.raises(OSError, match="connection interrupted"):
            download_and_extract(ZIP_URL, PACKAGE_DATE, target.parent)
    assert _snapshot(target) == original
    response.close.assert_called_once()
    assert not list(target.parent.glob(".sut-fetch-*"))


@pytest.mark.parametrize("status_code", [206, 301, 302])
def test_partial_or_redirected_response_cannot_complete_package(tmp_path: Path, status_code: int) -> None:
    response = _response(_zip_bytes(SOURCE_FILES))
    response.status_code = status_code
    with patch("scripts.sut.sut_fetch.requests.get", return_value=response) as request:
        with pytest.raises(ValueError, match="complete HTTP 200 response"):
            download_and_extract(ZIP_URL, PACKAGE_DATE, tmp_path / "raw data")
    request.assert_called_once_with(ZIP_URL, timeout=120, stream=True, allow_redirects=False)
    response.close.assert_called_once()
    assert not _target(tmp_path).exists()


def test_failed_missing_file_installation_rolls_back(tmp_path: Path) -> None:
    target = _target(tmp_path)
    docx = target / DOCX_MEMBER
    docx.parent.mkdir(parents=True)
    docx.write_bytes(SOURCE_FILES[DOCX_MEMBER])
    original = _snapshot(target)
    from scripts.sut import sut_fetch

    copyfileobj = sut_fetch.shutil.copyfileobj

    def fail_install(source, output, *args):
        if output.name == str(target / XLSX_MEMBER):
            output.write(b"partial")
            raise OSError("installation interrupted")
        return copyfileobj(source, output, *args)

    with patch("scripts.sut.sut_fetch.shutil.copyfileobj", fail_install):
        with pytest.raises(OSError, match="installation interrupted"):
            _fetch(tmp_path, _zip_bytes(SOURCE_FILES))
    assert _snapshot(target) == original
    assert not (target / "2026.10.02-SUT/EK-4 LİSTELERİ").exists()


def test_main_exports_exact_completed_input_and_inventory(tmp_path: Path, monkeypatch) -> None:
    target = _fetch(tmp_path, _zip_bytes(SOURCE_FILES))
    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(sys, "argv", ["sut_fetch.py", "https://www.sgk.gov.tr/duyuru", PACKAGE_DATE])
    with (
        patch("scripts.sut.sut_fetch.parse_duyuru_detail", return_value=ZIP_URL),
        patch("scripts.sut.sut_fetch.download_and_extract", return_value=target),
    ):
        assert main() == 0
    assert output.read_text(encoding="utf-8") == (
        f"input_dir={target.resolve()}\n"
        f"inventory_path={(target / PACKAGE_INVENTORY_FILENAME).resolve()}\n"
    )


def test_main_does_not_export_failed_input(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(sys, "argv", ["sut_fetch.py", "https://www.sgk.gov.tr/duyuru", PACKAGE_DATE])
    with (
        patch("scripts.sut.sut_fetch.parse_duyuru_detail", return_value=ZIP_URL),
        patch("scripts.sut.sut_fetch.download_and_extract", side_effect=ValueError("bad ZIP")),
    ):
        with pytest.raises(ValueError, match="bad ZIP"):
            main()
    assert not output.exists()
