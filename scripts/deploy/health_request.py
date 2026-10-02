"""Authenticate bounded release health probes without publishing diagnostics."""

from __future__ import annotations

import ipaddress
import json
import os
from collections.abc import Mapping
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


def health_headers(url: str) -> dict[str, str]:
    """Add the operator token only to the known HTTPS app or local probes."""
    token = os.getenv("BILUN_HEALTH_PROBE_TOKEN", "").strip()
    if not token:
        return {}  # Pre-cutover artifacts still serve their original health.
    if len(token) < 32:
        raise ValueError("Health probe token must contain at least 32 characters")
    parsed = urlparse(url)
    try:
        loopback = ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        loopback = parsed.hostname == "localhost"
    trusted = (
        loopback and parsed.scheme in {"http", "https"}
    ) or (
        parsed.scheme == "https" and parsed.hostname == "app.bilun.tech"
        and parsed.port in {None, 443}
    )
    if not trusted or parsed.username or parsed.password or parsed.path != "/health":
        raise ValueError("Refusing to send a health token to an untrusted target")
    return {"X-Bilun-Health-Token": token}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Release probe redirects are not allowed")


def open_probe(request: Request, *, timeout: float = 5):
    """Never forward a probe credential to a redirected destination."""
    return build_opener(_NoRedirect()).open(request, timeout=timeout)


def open_health(url: str, *, timeout: float = 5):
    return open_probe(Request(url, headers=health_headers(url)), timeout=timeout)


def read_loopback_health(environment: Mapping[str, str]) -> dict:
    """Use an already-observed service environment, never a retyped shell secret."""
    token = environment.get("BILUN_HEALTH_PROBE_TOKEN", "").strip()
    if token and len(token) < 32:
        raise ValueError("Health probe token must contain at least 32 characters")
    headers = {"X-Bilun-Health-Token": token} if token else {}
    request = Request("http://127.0.0.1:8001/health", headers=headers)
    with open_probe(request, timeout=5) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("Service health response is malformed")
    return value
