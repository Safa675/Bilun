"""tests/unit/deploy/test_verify_frontend_assets.py

Unit and regression tests for scripts/deploy/verify_frontend_assets.py.
"""

from __future__ import annotations

import http.server
import socketserver
import threading
from urllib.parse import urlparse

import pytest

from scripts.deploy.verify_frontend_assets import (
    extract_assets_from_html,
    is_local_asset,
    verify_entrypoint,
)


ESCAPED_FLIGHT_HTML = r'''<html>
<script src="/_next/static/chunks/main.js"></script>
<script>self.__next_f.push([1,"4:I[100,[\"/_next/static/chunks/main.js\",\"/_next/static/chunks/flight-only.js\"],\"Entry\"]"])</script>
</html>'''

MULTIPLY_ESCAPED_FLIGHT_HTML = r'''<html>
<script src="/_next/static/chunks/main.js"></script>
<script>self.__next_f.push([1,"x:[\\\"/_next/static/chunks/missing.js\\\"]"])</script>
</html>'''


def test_extract_assets_from_standard_html():
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <link rel="stylesheet" href="/_next/static/css/app.css">
        <link rel="preload" href="/_next/static/media/font.woff2" as="font">
        <link rel="icon" href="/favicon.ico">
      </head>
      <body>
        <script src="/_next/static/chunks/main.js"></script>
        <script src="https://cdn.example.com/external.js"></script>
      </body>
    </html>
    """
    assets = extract_assets_from_html(html)
    assert "/_next/static/css/app.css" in assets
    assert "/_next/static/media/font.woff2" in assets
    assert "/favicon.ico" in assets
    assert "/_next/static/chunks/main.js" in assets
    assert "https://cdn.example.com/external.js" in assets


def test_extract_assets_from_nextjs_flight_payload():
    html = """
    <!DOCTYPE html>
    <html>
      <body>
        <script>
          self.__next_f.push([1, "10:I[48130,[\"/_next/static/chunks/27dwgj7lkl2ks.js\",\"/_next/static/chunks/336xos0r1ud0d.js\"],\"ConfigProvider\"]"]);
        </script>
      </body>
    </html>
    """
    assets = extract_assets_from_html(html)
    assert "/_next/static/chunks/27dwgj7lkl2ks.js" in assets
    assert "/_next/static/chunks/336xos0r1ud0d.js" in assets


def test_is_local_asset_filtering():
    base_url = "http://127.0.0.1:3000/login"
    assert is_local_asset("/_next/static/chunks/main.js", base_url) is True
    assert is_local_asset("http://127.0.0.1:3000/_next/static/app.css", base_url) is True
    assert is_local_asset("https://cdn.thirdparty.com/lib.js", base_url) is False
    assert is_local_asset("https://analytics.google.com/tag.js", base_url) is False


class MockHandler(http.server.BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, bytes, str]] = {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path in self.routes:
            status, body, ctype = self.routes[path]
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logging in test runner


@pytest.fixture
def mock_server():
    server = socketserver.TCPServer(("127.0.0.1", 0), MockHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_verify_entrypoint_success(mock_server):
    MockHandler.routes = {
        "/login": (
            200,
            b'<html><head><link rel="stylesheet" href="/style.css"></head><body><script src="/app.js"></script></body></html>',
            "text/html",
        ),
        "/style.css": (200, b"body { margin: 0; }", "text/css"),
        "/app.js": (200, b"console.log('hello');", "application/javascript"),
    }

    success, report = verify_entrypoint(f"{mock_server}/login", timeout=2.0)
    assert success is True
    assert report["assets_total"] == 2
    assert report["assets_passed"] == 2
    assert report["assets_failed"] == 0


def test_verify_entrypoint_accepts_escaped_flight_assets(mock_server):
    MockHandler.routes = {
        "/login": (200, ESCAPED_FLIGHT_HTML.encode(), "text/html"),
        "/_next/static/chunks/main.js": (200, b"main();", "application/javascript"),
        "/_next/static/chunks/flight-only.js": (200, b"flight();", "application/javascript"),
    }

    success, report = verify_entrypoint(f"{mock_server}/login", timeout=2.0, verbose=False)

    assert success is True
    assert report["assets_total"] == 2
    assert report["assets_passed"] == 2
    assert report["failed_assets"] == []
    assert {urlparse(asset["url"]).path for asset in report["passed_assets"]} == {
        "/_next/static/chunks/main.js",
        "/_next/static/chunks/flight-only.js",
    }


def test_verify_entrypoint_rejects_missing_escaped_flight_asset(mock_server):
    MockHandler.routes = {
        "/login": (200, ESCAPED_FLIGHT_HTML.encode(), "text/html"),
        "/_next/static/chunks/main.js": (200, b"main();", "application/javascript"),
    }

    success, report = verify_entrypoint(f"{mock_server}/login", timeout=2.0, verbose=False)

    assert success is False
    assert report["assets_total"] == 2
    assert report["assets_passed"] == 1
    assert report["assets_failed"] == 1
    assert report["failed_assets"][0]["url"] == (
        f"{mock_server}/_next/static/chunks/flight-only.js"
    )
    assert report["failed_assets"][0]["status"] == 404


def test_verify_entrypoint_rejects_missing_multiply_escaped_flight_asset(mock_server):
    MockHandler.routes = {
        "/login": (200, MULTIPLY_ESCAPED_FLIGHT_HTML.encode(), "text/html"),
        "/_next/static/chunks/main.js": (200, b"main();", "application/javascript"),
    }

    success, report = verify_entrypoint(f"{mock_server}/login", timeout=2.0, verbose=False)

    assert success is False
    assert report["assets_total"] == 2
    assert report["assets_passed"] == 1
    assert report["assets_failed"] == 1
    assert report["failed_assets"][0]["url"] == f"{mock_server}/_next/static/chunks/missing.js"
    assert report["failed_assets"][0]["status"] == 404


def test_verify_entrypoint_incident_regression_chunk_mismatch(mock_server):
    """Regression test for the 2026-09-21 incident.

    The HTML returns 200 and references an old chunk (2-av3zy2nw4oj.js)
    which returns 404/500 because the disk only contains newer chunks.
    The verifier must fail closed and identify the exact missing chunk.
    """
    MockHandler.routes = {
        "/login": (
            200,
            b'<html><head></head><body><script src="/_next/static/chunks/2-av3zy2nw4oj.js"></script></body></html>',
            "text/html",
        ),
        # Notice: /_next/static/chunks/2-av3zy2nw4oj.js is NOT in routes, so it returns 404
    }

    success, report = verify_entrypoint(f"{mock_server}/login", timeout=2.0)
    assert success is False
    assert report["assets_total"] == 1
    assert report["assets_failed"] == 1
    failed_url = report["failed_assets"][0]["url"]
    assert "2-av3zy2nw4oj.js" in failed_url


def test_verify_entrypoint_empty_asset_body(mock_server):
    MockHandler.routes = {
        "/login": (
            200,
            b'<html><body><script src="/empty.js"></script></body></html>',
            "text/html",
        ),
        "/empty.js": (200, b"", "application/javascript"),  # Empty body
    }

    success, report = verify_entrypoint(f"{mock_server}/login", timeout=2.0)
    assert success is False
    assert report["assets_failed"] == 1
    assert "empty" in report["failed_assets"][0]["error"].lower()


def test_verify_entrypoint_fails_when_under_min_assets(mock_server):
    MockHandler.routes = {
        "/login": (
            200,
            b"<html><body><h1>Simple Page Without Assets</h1></body></html>",
            "text/html",
        ),
    }

    success, report = verify_entrypoint(f"{mock_server}/login", timeout=2.0, min_assets=1)
    assert success is False
    assert "expected at least" in str(report["error"])
