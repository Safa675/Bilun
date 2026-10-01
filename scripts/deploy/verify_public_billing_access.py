"""Read-only public/developer access smoke checks against a staged release.

Use the same checks against the frontend proxy and the direct backend. Cookie
files are owner-only, never command-line token values. This does not call an LLM
or change the public access switch, credentials, records or deployment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request

from scripts.deploy.health_request import open_probe

_INTERNAL_KEYS = {
    "domain_modules", "engine_filename", "source_file", "fact_check_notes",
    "private_conditions", "implemented_in", "kdv_pricing_module",
    "medula_boundary_doc", "l44_plan_path",
}


def _get(base: str, path: str, cookie: str | None = None) -> tuple[int, object]:
    request = Request(base.rstrip("/") + path, headers={"Cookie": cookie} if cookie else {})
    try:
        with open_probe(request, timeout=30) as response:
            raw = response.read(32 * 1024 * 1024 + 1)
            if len(raw) > 32 * 1024 * 1024:
                raise ValueError("Access probe response too large")
            return response.status, json.loads(raw)
    except HTTPError as error:
        return error.code, None


def _has_internal_keys(value: object) -> bool:
    if isinstance(value, dict):
        return bool(_INTERNAL_KEYS.intersection(value)) or any(_has_internal_keys(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_internal_keys(item) for item in value)
    return False


def verify(base: str, developer_cookie: str, *, public: bool, retired_cookie: str | None = None, fetch=_get) -> dict:
    checks: list[str] = []

    def require(condition: bool, name: str):
        if not condition:
            raise ValueError(f"Access check failed: {name}")
        checks.append(name)

    status, guest = fetch(base, "/api/auth/me", None)
    require(status == 200 and isinstance(guest, dict) and guest.get("authenticated") is False, "anonymous_identity")
    require(guest.get("public_billing_enabled") is public and ("billing" in guest.get("capabilities", [])) is public, "release_switch")
    for path in ("/api/rules", "/api/rules/prose-inventory", "/api/rules/deferrals"):
        for cookie in (None, "bilun:role=dev"):
            require(fetch(base, path, cookie)[0] in {401, 403}, f"protected:{path}:{'forged-role' if cookie else 'guest'}")
    status, dev = fetch(base, "/api/auth/me", developer_cookie)
    require(status == 200 and isinstance(dev, dict) and dev.get("authenticated") is True and "developer" in dev.get("capabilities", []), "developer_identity")
    require(fetch(base, "/api/rules", developer_cookie)[0] == 200, "developer_catalogue")
    if retired_cookie:
        status, old = fetch(base, "/api/auth/me", retired_cookie)
        require(status == 200 and isinstance(old, dict) and old.get("authenticated") is False, "retired_session_rejected")
        require(fetch(base, "/api/rules", retired_cookie)[0] in {401, 403}, "retired_session_denied")
    status, patients = fetch(base, "/api/patients", None)
    require(status == (200 if public else 401), "public_patient_access")
    if public:
        require(isinstance(patients, dict) and bool(patients.get("patients")), "synthetic_patients_available")
        patient = quote(str(patients["patients"][0]), safe="")
        path = f"/api/billing-report/{patient}"
        before_status, before = fetch(base, path, None)
        require(before_status == 200 and isinstance(before, dict), "public_billing_report")
        require(not _has_internal_keys(before), "public_report_has_no_internal_keys")
        require(fetch(base, path, developer_cookie)[0] == 200, "developer_report_warm_cache")
        after_status, after = fetch(base, path, None)
        require(after_status == 200 and before == after and not _has_internal_keys(after), "public_report_after_developer_cache")
    return {"ok": True, "checks": checks}


def _cookie_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError("Probe cookie file must be a private regular file")
    value = path.read_text().strip()
    if not value.startswith("bilun:session=") or "\n" in value or "\r" in value:
        raise ValueError("Malformed probe cookie file")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--developer-cookie-file", type=Path, required=True)
    parser.add_argument("--retired-cookie-file", type=Path)
    parser.add_argument("--expect-public", choices=("on", "off"), required=True)
    args = parser.parse_args(argv)
    parsed = urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        parser.error("base URL must be an HTTP(S) origin without credentials or path")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("remote probes require HTTPS to protect developer cookies")
    try:
        report = verify(
            args.base_url, _cookie_file(args.developer_cookie_file), public=args.expect_public == "on",
            retired_cookie=_cookie_file(args.retired_cookie_file) if args.retired_cookie_file else None,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
