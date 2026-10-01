from __future__ import annotations

import pytest

from scripts.deploy.verify_public_billing_access import main, verify


def _fetch(*, public=True, leak=False):
    warmed = False
    def fetch(base, path, cookie):
        nonlocal warmed
        dev = cookie == "developer"
        if path == "/api/auth/me":
            return 200, {"authenticated": dev, "capabilities": ["billing", "developer"] if dev else (["billing"] if public else []), "public_billing_enabled": public}
        if path.startswith("/api/rules"):
            return (200, {"domain_modules": ["private"]}) if dev else (401, None)
        if path == "/api/patients":
            return (200, {"patients": ["SYNTHETIC"]}) if public or dev else (401, None)
        if path.startswith("/api/billing-report/"):
            if dev:
                warmed = True
            payload = {"patient_id": "SYNTHETIC", "total_recoverable_try": 12}
            if dev or (leak and warmed):
                payload["domain_modules"] = ["private"]
            return 200, payload
        return 404, None
    return fetch


@pytest.mark.parametrize("public", [True, False])
def test_release_access_probe_accepts_intended_policy(public):
    result = verify("http://localhost:8001", "developer", public=public, retired_cookie="old", fetch=_fetch(public=public))
    assert result["ok"] is True
    assert "retired_session_rejected" in result["checks"]


def test_release_access_probe_detects_developer_cache_leak():
    with pytest.raises(ValueError, match="public_report_after_developer_cache"):
        verify("http://localhost:8001", "developer", public=True, fetch=_fetch(leak=True))


def test_release_access_probe_rejects_remote_plaintext_before_reading_cookie(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main([
            "--base-url", "http://example.com", "--expect-public", "on",
            "--developer-cookie-file", str(tmp_path / "does-not-exist"),
        ])
    assert error.value.code == 2
    assert "require HTTPS" in capsys.readouterr().err
