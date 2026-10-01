from __future__ import annotations

import base64

import pytest

from scripts.deploy.health_request import _NoRedirect, health_headers
from scripts.deploy.probe_auth import probe_cookie


@pytest.mark.parametrize("url", ["http://127.0.0.1:8002/health", "http://[::1]:8199/health", "https://app.bilun.tech/health"])
def test_operator_token_only_for_approved_health_targets(monkeypatch, url):
    monkeypatch.setenv("BILUN_HEALTH_PROBE_TOKEN", "synthetic-token-" * 4)
    assert health_headers(url) == {"X-Bilun-Health-Token": "synthetic-token-" * 4}


@pytest.mark.parametrize("url", ["https://example.com/health", "http://app.bilun.tech/health", "http://127.0.0.1:8002/api/chat", "https://app.bilun.tech:444/health", "https://user@app.bilun.tech/health"])
def test_probe_refuses_credential_forwarding(monkeypatch, url):
    monkeypatch.setenv("BILUN_HEALTH_PROBE_TOKEN", "synthetic-token-" * 4)
    with pytest.raises(ValueError, match="untrusted"):
        health_headers(url)


def test_probe_never_follows_redirects():
    with pytest.raises(ValueError, match="redirect"):
        _NoRedirect().redirect_request(None, None, 302, "moved", {}, "https://example.com")


def test_probe_token_purpose_supports_explicit_new_and_captured_old_targets():
    values = {"BILUN_AUTH_USERNAME": "developer", "BILUN_SESSION_SECRET": "test-secret"}
    legacy = probe_cookie(values, now=1000)
    current = probe_cookie({**values, "BILUN_SESSION_TOKEN_PURPOSE": "bilun-developer-v1"}, now=1000)
    def payload(cookie):
        raw = cookie.split("=", 1)[1].split(".", 1)[0]
        return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
    assert payload(legacy) == "developer.1300"
    assert payload(current) == "bilun-developer-v1:developer.1300"
    assert legacy != current


def test_unknown_probe_token_format_fails_closed():
    with pytest.raises(ValueError, match="Unknown"):
        probe_cookie({"BILUN_AUTH_USERNAME": "dev", "BILUN_SESSION_SECRET": "test", "BILUN_SESSION_TOKEN_PURPOSE": "other"})
