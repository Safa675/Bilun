#!/usr/bin/env python3
"""verify_frontend_assets.py

Reusable frontend asset verifier for Bilun Next.js deployments.
Verifies an HTML entry point (e.g. /login) and all referenced local scripts,
stylesheets, and static chunks to guarantee complete chunk availability.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


class AssetResult(NamedTuple):
    url: str
    status: int
    content_length: int
    elapsed_ms: float
    error: str | None = None


class HtmlAssetExtractor(HTMLParser):
    """Extracts script[src], link[href], and inline Next.js chunk references from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.asset_urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        if tag == "script":
            src = attr_dict.get("src")
            if src and src.strip():
                self.asset_urls.add(src.strip())
        elif tag == "link":
            rel = (attr_dict.get("rel") or "").lower()
            href = attr_dict.get("href")
            if href and href.strip():
                # Check stylesheets, preloads, modulepreloads, icons
                if any(k in rel for k in ("stylesheet", "preload", "icon", "modulepreload")):
                    self.asset_urls.add(href.strip())


def extract_assets_from_html(html: str) -> list[str]:
    """Parse HTML and discover referenced local asset paths, including Next.js flight data."""
    extractor = HtmlAssetExtractor()
    extractor.feed(html)
    found_urls = set(extractor.asset_urls)

    # Next.js App Router flight/RSC payloads in inline scripts often reference static chunks:
    # e.g. "/_next/static/chunks/27dwgj7lkl2ks.js" or "static/chunks/..."
    flight_pattern = re.compile(r'["\'](/_next/static/[^"\'\s>]+)["\']')
    for match in flight_pattern.findall(html):
        found_urls.add(match)

    # Clean query parameters / hashes for pure asset paths while maintaining query if needed
    cleaned: list[str] = sorted(found_urls)
    return cleaned


def is_local_asset(asset_url: str, base_url: str) -> bool:
    """Determine whether an asset belongs to the same origin / local host."""
    parsed_asset = urlparse(asset_url)
    parsed_base = urlparse(base_url)

    # Relative path or root-relative path (e.g. /_next/static/...)
    if not parsed_asset.netloc:
        return True

    # Same host and port
    if parsed_asset.netloc.lower() == parsed_base.netloc.lower():
        return True

    return False


def verify_url(url: str, timeout: float = 10.0) -> AssetResult:
    """Fetch a single URL and check for 200 OK and non-empty body."""
    start_time = time.monotonic()
    req = Request(
        url,
        headers={"User-Agent": "Bilun-Asset-Verifier/1.0", "Accept": "*/*"},
    )

    try:
        with urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            content = response.read()
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            content_len = len(content)

            if status < 200 or status >= 300:
                return AssetResult(
                    url=url,
                    status=status,
                    content_length=content_len,
                    elapsed_ms=elapsed_ms,
                    error=f"Unexpected status HTTP {status}",
                )

            if content_len == 0:
                return AssetResult(
                    url=url,
                    status=status,
                    content_length=0,
                    elapsed_ms=elapsed_ms,
                    error="Asset body is empty (0 bytes)",
                )

            return AssetResult(
                url=url,
                status=status,
                content_length=content_len,
                elapsed_ms=elapsed_ms,
            )
    except HTTPError as e:
        elapsed_ms = (time.monotonic() - start_time) * 1000.0
        return AssetResult(
            url=url,
            status=e.code,
            content_length=0,
            elapsed_ms=elapsed_ms,
            error=f"HTTP {e.code}: {e.reason}",
        )
    except URLError as e:
        elapsed_ms = (time.monotonic() - start_time) * 1000.0
        return AssetResult(
            url=url,
            status=0,
            content_length=0,
            elapsed_ms=elapsed_ms,
            error=f"URL Error: {e.reason}",
        )
    except Exception as e:
        elapsed_ms = (time.monotonic() - start_time) * 1000.0
        return AssetResult(
            url=url,
            status=0,
            content_length=0,
            elapsed_ms=elapsed_ms,
            error=f"Request error: {e}",
        )


def verify_entrypoint(
    entry_url: str,
    timeout: float = 10.0,
    min_assets: int = 1,
    verbose: bool = True,
) -> tuple[bool, dict[str, object]]:
    """Verify entrypoint HTML and all discovered local assets.

    Returns (is_ok, report_dict).
    """
    if verbose:
        print(f"[verifier] Fetching entrypoint: {entry_url}")

    entry_res = verify_url(entry_url, timeout=timeout)
    if entry_res.error:
        if verbose:
            print(f"[verifier] ERROR: Entrypoint failed: {entry_res.error}", file=sys.stderr)
        return False, {
            "entrypoint": entry_url,
            "entrypoint_status": entry_res.status,
            "error": entry_res.error,
            "assets_checked": 0,
            "failed_assets": [],
        }

    # Fetch body to extract assets
    try:
        req = Request(entry_url, headers={"User-Agent": "Bilun-Asset-Verifier/1.0"})
        with urlopen(req, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
    except Exception as e:
        if verbose:
            print(f"[verifier] ERROR: Failed reading HTML: {e}", file=sys.stderr)
        return False, {
            "entrypoint": entry_url,
            "error": f"Failed reading HTML: {e}",
            "assets_checked": 0,
            "failed_assets": [],
        }

    raw_assets = extract_assets_from_html(html)
    local_asset_urls: list[str] = []

    for raw in raw_assets:
        if is_local_asset(raw, entry_url):
            resolved = urljoin(entry_url, raw)
            if resolved not in local_asset_urls:
                local_asset_urls.append(resolved)

    if verbose:
        print(f"[verifier] Found {len(local_asset_urls)} local assets referenced by {entry_url}")

    if len(local_asset_urls) < min_assets:
        msg = f"Found {len(local_asset_urls)} local assets, expected at least {min_assets}"
        if verbose:
            print(f"[verifier] ERROR: {msg}", file=sys.stderr)
        return False, {
            "entrypoint": entry_url,
            "error": msg,
            "assets_checked": len(local_asset_urls),
            "failed_assets": [],
        }

    failed: list[dict[str, object]] = []
    passed: list[dict[str, object]] = []

    for asset_url in local_asset_urls:
        res = verify_url(asset_url, timeout=timeout)
        if res.error:
            failed.append({
                "url": res.url,
                "status": res.status,
                "error": res.error,
                "elapsed_ms": res.elapsed_ms,
            })
            if verbose:
                print(f"  [FAIL] {res.url} -> {res.error} (HTTP {res.status})", file=sys.stderr)
        else:
            passed.append({
                "url": res.url,
                "status": res.status,
                "bytes": res.content_length,
                "elapsed_ms": res.elapsed_ms,
            })
            if verbose:
                print(f"  [OK]   {res.url} ({res.content_length} bytes, {res.elapsed_ms:.1f}ms)")

    success = len(failed) == 0
    report = {
        "entrypoint": entry_url,
        "entrypoint_status": entry_res.status,
        "assets_total": len(local_asset_urls),
        "assets_passed": len(passed),
        "assets_failed": len(failed),
        "failed_assets": failed,
        "passed_assets": passed,
    }

    if verbose:
        if success:
            print(f"[verifier] SUCCESS: All {len(local_asset_urls)} assets verified successfully.")
        else:
            print(
                f"[verifier] FAILURE: {len(failed)} of {len(local_asset_urls)} assets failed verification!",
                file=sys.stderr,
            )

    return success, report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify frontend HTML entrypoint and referenced static assets."
    )
    parser.add_argument("url", help="URL of the entrypoint page (e.g. http://127.0.0.1:3000/login)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds (default: 10)")
    parser.add_argument("--min-assets", type=int, default=1, help="Minimum number of assets required (default: 1)")
    parser.add_argument("--json", action="store_true", help="Print result as JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose logging")

    args = parser.parse_args()
    verbose = not args.quiet and not args.json

    success, report = verify_entrypoint(
        entry_url=args.url,
        timeout=args.timeout,
        min_assets=args.min_assets,
        verbose=verbose,
    )

    if args.json:
        print(json.dumps(report, indent=2))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
