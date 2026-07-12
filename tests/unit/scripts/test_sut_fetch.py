"""Unit tests for the SUT package fetch script."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.sut.sut_fetch import (
    download_and_extract,
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


def test_download_and_extract_creates_folder(tmp_path: Path) -> None:
    """download_and_extract extracts zip to the correct folder name."""
    # Create a mock zip
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("EK-2 LİSTELERİ/test.xlsx", "fake xlsx content")

    raw_data_root = tmp_path / "raw data"
    tebliğ_date = "2026-06-29"

    with patch("scripts.sut.sut_fetch.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.headers = {"content-length": "1024"}
        mock_resp.raw = open(zip_path, "rb")
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = download_and_extract(
            "https://example.com/test.zip", tebliğ_date, raw_data_root
        )

    assert result.exists()
    assert "2026.06.29" in result.name
    assert "Değişiklik Tebliği İşlenmiş Güncel 2013 SUT" in result.name
    # Verify extraction worked
    assert any(result.rglob("test.xlsx"))
    mock_resp.raw.close()


def test_download_and_extract_skips_existing(tmp_path: Path) -> None:
    """When the target folder already exists, return it without downloading."""
    raw_data_root = tmp_path / "raw data"
    tebliğ_date = "2026-06-29"
    folder_name = f"2026.06.29-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"
    existing = raw_data_root / folder_name
    existing.mkdir(parents=True)

    result = download_and_extract(
        "https://example.com/test.zip", tebliğ_date, raw_data_root
    )
    assert result == existing
