"""Exact Caddy route adapter for the journaled Wave A release transaction.

The transaction supplies already-reviewed old, barrier and candidate Caddyfiles.
This adapter compares adapted JSON with Caddy's *loaded* admin configuration;
an on-disk file or a successful reload command alone is not a route proof.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from scripts.deploy.release_transaction import RouteName, TransactionError


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _adapt(path: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["caddy", "adapt", "--config", str(path), "--adapter", "caddyfile"],
            check=True, capture_output=True, text=True, timeout=20,
        )
        value = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise TransactionError("Caddy route adaptation failed") from exc
    if not isinstance(value, dict) or "apps" not in value:
        raise TransactionError("Caddy adapted route is incomplete")
    return value


def _validate(path: Path) -> None:
    try:
        subprocess.run(
            ["caddy", "validate", "--config", str(path), "--adapter", "caddyfile"],
            check=True, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransactionError("Caddy route validation failed") from exc


def _reload(path: Path) -> None:
    try:
        subprocess.run(
            ["caddy", "reload", "--config", str(path), "--adapter", "caddyfile"],
            check=True, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransactionError("Caddy route reload failed") from exc


def _loaded(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=5) as response:
            value = json.load(response)
    except (OSError, ValueError) as exc:
        raise TransactionError("Caddy loaded route cannot be observed") from exc
    if not isinstance(value, dict) or "apps" not in value:
        raise TransactionError("Caddy loaded route is incomplete")
    return value


class CaddyRouteDriver:
    """Install a sealed route file and verify the live Caddy admin config."""

    def __init__(
        self,
        *,
        config_path: Path,
        route_files: Mapping[RouteName, Path],
        expected_digests: Mapping[RouteName, str],
        expected_file_digests: Mapping[RouteName, str],
        admin_url: str = "http://127.0.0.1:2019/config/",
        adapt: Callable[[Path], dict[str, Any]] = _adapt,
        validate: Callable[[Path], None] = _validate,
        reload: Callable[[Path], None] = _reload,
        loaded: Callable[[str], dict[str, Any]] = _loaded,
    ) -> None:
        parsed = urlparse(admin_url)
        if (
            parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.path != "/config/" or parsed.username or parsed.password
            or parsed.query or parsed.fragment
        ):
            raise ValueError("Caddy admin observation must use the loopback config endpoint")
        if (
            set(route_files) != {"old", "barrier", "candidate"}
            or set(expected_digests) != set(route_files)
            or set(expected_file_digests) != set(route_files)
        ):
            raise ValueError("All three Caddy route files and digests are required")
        if len(set(expected_digests.values())) != 3:
            raise ValueError("Caddy release routes must be distinct")
        if not config_path.is_absolute() or config_path.is_symlink():
            raise ValueError("Caddy live config path must be absolute and independent")
        for route, path in route_files.items():
            if not path.is_absolute() or path.is_symlink() or not path.is_file():
                raise ValueError(f"Caddy {route} route must be an independent file")
        self.config_path = config_path
        self.route_files = dict(route_files)
        self.expected_digests = dict(expected_digests)
        self.expected_file_digests = dict(expected_file_digests)
        self.admin_url = admin_url
        self.adapt = adapt
        self.validate = validate
        self.reload = reload
        self.loaded = loaded

    def loaded_route_sha256(self) -> str | None:
        try:
            return _digest(self.loaded(self.admin_url))
        except TransactionError:
            return None

    def installed_route_sha256(self) -> str | None:
        """Only exact sealed Caddyfile bytes count as a restart-safe route."""
        try:
            if self.config_path.is_symlink() or not self.config_path.is_file():
                return None
            digest = hashlib.sha256(self.config_path.read_bytes()).hexdigest()
        except OSError:
            return None
        for route, expected in self.expected_file_digests.items():
            if digest == expected:
                return self.expected_digests[route]
        return None

    def verify_sealed_routes(self) -> None:
        """Prove all three recovery routes can be loaded before changing Caddy."""
        for route, source in self.route_files.items():
            if (
                source.is_symlink() or not source.is_file()
                or hashlib.sha256(source.read_bytes()).hexdigest()
                != self.expected_file_digests[route]
                or _digest(self.adapt(source)) != self.expected_digests[route]
            ):
                raise TransactionError(f"Caddy {route} recovery route differs")
            self.validate(source)
            if hashlib.sha256(source.read_bytes()).hexdigest() != self.expected_file_digests[route]:
                raise TransactionError(f"Caddy {route} recovery route changed during validation")

    def install(self, route: RouteName) -> None:
        if route not in self.route_files:
            raise TransactionError("Unknown Caddy release route")
        source = self.route_files[route]
        before = source.stat()
        contents = source.read_bytes()
        after = source.stat()
        if (
            source.is_symlink()
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or before.st_nlink != 1
        ):
            raise TransactionError("Caddy source route changed during read")
        if hashlib.sha256(contents).hexdigest() != self.expected_file_digests[route]:
            raise TransactionError("Caddy source route bytes differ from release manifest")
        if _digest(self.adapt(source)) != self.expected_digests[route]:
            raise TransactionError("Caddy source route differs from release manifest")
        self.validate(source)
        if source.read_bytes() != contents:
            raise TransactionError("Caddy source route changed during validation")
        target = self.config_path
        if target.is_symlink() or not target.is_file():
            raise TransactionError("Caddy live config is not an independent file")
        descriptor, temporary = tempfile.mkstemp(prefix=".wavea-route-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                os.fchmod(output.fileno(), target.stat().st_mode & 0o777)
                output.write(contents)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
            parent = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
            self.reload(target)
            if self.loaded_route_sha256() != self.expected_digests[route]:
                raise TransactionError("Caddy reload did not serve the expected route")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
