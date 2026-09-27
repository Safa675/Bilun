"""Public and private HTTP probes for the journaled Wave A route transaction."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any, Literal
from urllib.error import HTTPError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

from scripts.deploy.release_transaction import ReleaseIdentity
from scripts.deploy.verify_frontend_assets import (
    extract_assets_from_html,
    is_local_asset,
)

Pair = Literal["old", "candidate"]
Fetch = Callable[[str, str, str | None], tuple[int, bytes]]
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _fetch(base: str, path: str, cookie: str | None) -> tuple[int, bytes]:
    request = Request(
        urljoin(base + "/", path.lstrip("/")),
        headers={"Cookie": cookie} if cookie else {},
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.geturl() != request.full_url:
                raise ValueError("Release HTTP route redirected away from its exact path")
            body = response.read(20_000_001)
            if len(body) > 20_000_000:
                raise ValueError("Release HTTP response is too large")
            return response.status, body
    except HTTPError as error:
        body = error.read(65537)
        if len(body) > 65536:
            raise ValueError("Release HTTP error response is too large")
        return error.code, body


def _strict_json(raw: bytes) -> Any:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate release HTTP JSON field")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise ValueError(f"Nonfinite release HTTP JSON value: {value}")

    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def _asset_paths(base: str, body: bytes) -> set[str]:
    paths: set[str] = set()
    for item in extract_assets_from_html(body.decode("utf-8")):
        if not is_local_asset(item, base):
            continue
        parsed = urlparse(urljoin(base + "/", item))
        if parsed.fragment or not parsed.path.startswith("/"):
            raise ValueError("Release frontend asset URL is not a stable local path")
        paths.add(parsed.path + (f"?{parsed.query}" if parsed.query else ""))
    if len(paths) < 10 or len(paths) > 100:
        raise ValueError("Release frontend asset set is incomplete or unbounded")
    return paths


class HttpReleaseProbes:
    """Verify actual public forwarding while listeners remain on loopback."""

    def __init__(
        self,
        *,
        public_base: str,
        patient_id: str,
        old_tuple: Callable[[], dict[str, Any]],
        candidate_tuple: Callable[[], dict[str, Any]],
        activation_gate: Callable[[ReleaseIdentity], bool],
        cookie_factory: Callable[[], str],
        old_recovery: Callable[[], dict[str, str]] | None = None,
        fetch: Fetch = _fetch,
    ) -> None:
        parsed = urlparse(public_base)
        if (
            parsed.scheme != "https" or parsed.hostname != "app.bilun.tech"
            or parsed.path not in ("", "/") or parsed.port is not None
            or parsed.username or parsed.password or parsed.query or parsed.fragment
        ):
            raise ValueError("Release public base must be the Bilun HTTPS origin")
        if not patient_id or "/" in patient_id or not patient_id.strip():
            raise ValueError("Release patient probe identity is malformed")
        self.public_base = public_base.rstrip("/")
        self.patient_id = patient_id
        self.old_tuple = old_tuple
        self.candidate_tuple = candidate_tuple
        self.check_gate = activation_gate
        self.cookie_factory = cookie_factory
        self.old_recovery = old_recovery
        self.fetch = fetch

    def recover_old_tuple(self) -> dict[str, str] | None:
        if self.old_recovery is None:
            return None
        try:
            return self.old_recovery()
        except Exception:
            return None

    @staticmethod
    def _backend_base(pair: Pair) -> str:
        return "http://127.0.0.1:8001" if pair == "old" else "http://127.0.0.1:8002"

    @staticmethod
    def _frontend_base(pair: Pair) -> str:
        return "http://127.0.0.1:3000" if pair == "old" else "http://127.0.0.1:3099"

    def activation_gate(self, identity: ReleaseIdentity) -> bool:
        try:
            return self.check_gate(identity) is True
        except Exception:
            return False

    def direct_tuple_sha256(self, route: Pair) -> str | None:
        try:
            result = (self.old_tuple if route == "old" else self.candidate_tuple)()
            digest = result.get("tuple_sha256")
            expected_statuses = (
                {"protected_old_pair_observed", "recovered_old_pair_observed"}
                if route == "old" else {"candidate_tuple_observed"}
            )
            return digest if (
                result.get("status") in expected_statuses
                and (route == "old" or result.get("private_activation_verified") is True)
                and isinstance(digest, str) and _SHA256.fullmatch(digest)
            ) else None
        except Exception:
            return None

    def _equal_json(self, public_path: str, direct_base: str, cookie: str | None) -> None:
        public_status, public_body = self.fetch(self.public_base, public_path, cookie)
        direct_status, direct_body = self.fetch(direct_base, public_path, cookie)
        if (
            public_status != 200 or direct_status != 200
            or _strict_json(public_body) != _strict_json(direct_body)
        ):
            raise ValueError(f"Public route JSON differs from private pair: {public_path}")

    def _equal_assets(self, direct_frontend: str) -> None:
        public_status, public_html = self.fetch(self.public_base, "/login", None)
        direct_status, direct_html = self.fetch(direct_frontend, "/login", None)
        if public_status != 200 or direct_status != 200:
            raise ValueError("Public or direct login is unavailable")
        paths = _asset_paths(self.public_base, public_html)
        if paths != _asset_paths(direct_frontend, direct_html):
            raise ValueError("Public frontend references the wrong build assets")
        for path in sorted(paths):
            public_status, public_body = self.fetch(self.public_base, path, None)
            direct_status, direct_body = self.fetch(direct_frontend, path, None)
            if (
                public_status != 200 or direct_status != 200 or not public_body
                or hashlib.sha256(public_body).digest()
                != hashlib.sha256(direct_body).digest()
            ):
                raise ValueError(f"Public frontend asset differs: {path}")

    def _retained_old_assets(self) -> None:
        old_frontend = self._frontend_base("old")
        status, html = self.fetch(old_frontend, "/login", None)
        if status != 200:
            raise ValueError("Protected old frontend is unavailable")
        for path in sorted(_asset_paths(old_frontend, html)):
            public_status, public_body = self.fetch(self.public_base, path, None)
            old_status, old_body = self.fetch(old_frontend, path, None)
            if (
                public_status != 200 or old_status != 200 or not public_body
                or hashlib.sha256(public_body).digest()
                != hashlib.sha256(old_body).digest()
            ):
                raise ValueError(f"Retained old frontend asset differs: {path}")

    def public_tuple_sha256(self, route: Pair) -> str | None:
        try:
            digest = self.direct_tuple_sha256(route)
            if digest is None:
                return None
            backend = self._backend_base(route)
            frontend = self._frontend_base(route)
            self._equal_json("/health", backend, None)
            cookie = self.cookie_factory()
            patient_path = f"/api/billing-report/{quote(self.patient_id, safe='')}"
            for path in (
                patient_path, "/api/compliance-index", "/api/revenue-recovery",
            ):
                self._equal_json(path, backend, cookie)
            if route == "candidate":
                self._equal_json("/api/wavea-evidence-index", backend, cookie)
            self._equal_assets(frontend)
            if route == "candidate":
                self._retained_old_assets()
            page_path = f"/patient/{quote(self.patient_id, safe='')}"
            if any(
                self.fetch(base, page_path, cookie)[0] != 200
                for base in (self.public_base, frontend)
            ):
                raise ValueError("Public authenticated patient page is unavailable")
            return digest if self.direct_tuple_sha256(route) == digest else None
        except Exception:
            return None

    def public_barrier_ready(self) -> bool:
        try:
            if any(
                self.fetch(self.public_base, path, None)[0] != 503
                for path in ("/health", "/login", "/api/compliance-index")
            ):
                return False
            return True
        except Exception:
            return False
