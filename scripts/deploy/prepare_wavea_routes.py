"""Prepare reviewed old, barrier, and candidate Caddy routes without reloading.

The old route is an exact copy of the currently serving Caddyfile. Old-only
Next.js assets continue to use the protected old frontend during activation;
shared asset names must have identical bytes across both releases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.deploy.caddy_route_driver import _adapt, _digest, _validate

OLD_CADDYFILE = b"""app.bilun.tech {
    bind 169.58.50.165
    encode gzip

    handle /api/* {
        reverse_proxy 127.0.0.1:8001
    }
    handle /health {
        reverse_proxy 127.0.0.1:8001
    }

    reverse_proxy 127.0.0.1:3000
}
"""
_ASSET_PATH = re.compile(r"[A-Za-z0-9_./-]+\Z")


def _assets(frontend: Path) -> dict[str, str]:
    root = frontend / ".next" / "static"
    if not frontend.is_absolute() or frontend.is_symlink() or not root.is_dir():
        raise ValueError("Wave A frontend static root is unavailable")
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Wave A static assets cannot be symlinks")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if not _ASSET_PATH.fullmatch(relative) or ".." in Path(relative).parts:
            raise ValueError("Wave A static asset path is unsafe for Caddy")
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not result:
        raise ValueError("Wave A frontend has no static assets")
    return result


def _write_new(path: Path, data: bytes) -> str:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return hashlib.sha256(data).hexdigest()


def prepare_wavea_routes(
    *,
    live_config: Path,
    old_frontend: Path,
    candidate_frontend: Path,
    output_dir: Path,
    adapt: Callable[[Path], dict[str, Any]] = _adapt,
    validate: Callable[[Path], None] = _validate,
) -> dict[str, Any]:
    """Seal route files and their adapted digests in a fresh private directory."""
    if (
        not live_config.is_absolute() or live_config.is_symlink()
        or not live_config.is_file() or live_config.read_bytes() != OLD_CADDYFILE
    ):
        raise ValueError("Serving Caddyfile differs from reviewed old route")
    if (
        not output_dir.is_absolute() or output_dir.is_symlink()
        or not output_dir.is_dir() or list(output_dir.iterdir())
        or stat.S_IMODE(output_dir.stat().st_mode) & 0o077
    ):
        raise ValueError("Wave A routes need an empty private directory")
    old_assets = _assets(old_frontend)
    candidate_assets = _assets(candidate_frontend)
    conflicts = {
        name for name in old_assets.keys() & candidate_assets.keys()
        if old_assets[name] != candidate_assets[name]
    }
    if conflicts:
        raise ValueError("Old and candidate static assets collide with different bytes")
    old_only = sorted(old_assets.keys() - candidate_assets.keys())
    matcher = ""
    if old_only:
        matcher = (
            "    @old_static path "
            + " ".join(f"/_next/static/{name}" for name in old_only)
            + "\n    handle @old_static {\n"
            "        reverse_proxy 127.0.0.1:3000\n"
            "    }\n"
        )
    candidate_route = (
        "app.bilun.tech {\n"
        "    bind 169.58.50.165\n"
        "    encode gzip\n\n"
        + matcher
        + "    handle /api/* {\n"
        "        reverse_proxy 127.0.0.1:8002\n"
        "    }\n"
        "    handle /health {\n"
        "        reverse_proxy 127.0.0.1:8002\n"
        "    }\n\n"
        "    reverse_proxy 127.0.0.1:3099\n"
        "}\n"
    ).encode()
    barrier = (
        b"app.bilun.tech {\n"
        b"    bind 169.58.50.165\n"
        b"    respond \"Release in progress\" 503\n"
        b"}\n"
    )
    files = {"old": OLD_CADDYFILE, "barrier": barrier, "candidate": candidate_route}
    routes: dict[str, dict[str, str]] = {}
    for name, data in files.items():
        path = output_dir / f"{name}.caddy"
        file_sha = _write_new(path, data)
        validate(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != file_sha:
            raise ValueError("Wave A Caddy route changed during validation")
        routes[name] = {
            "path": str(path), "file_sha256": file_sha,
            "route_sha256": _digest(adapt(path)),
        }
    if len({route["route_sha256"] for route in routes.values()}) != 3:
        raise ValueError("Wave A old, barrier, and candidate routes are not distinct")
    report = {
        "schema_version": "wavea-route-preparation-v1",
        "routes": routes,
        "old_assets": old_assets,
        "candidate_assets": candidate_assets,
        "retained_old_only_count": len(old_only),
        "shared_identical_count": len(old_assets.keys() & candidate_assets.keys()),
    }
    _write_new(
        output_dir / "route-preparation.json",
        (json.dumps(report, sort_keys=True, indent=2) + "\n").encode(),
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-config", type=Path, required=True)
    parser.add_argument("--old-frontend", type=Path, required=True)
    parser.add_argument("--candidate-frontend", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare_wavea_routes(
            live_config=args.live_config,
            old_frontend=args.old_frontend,
            candidate_frontend=args.candidate_frontend,
            output_dir=args.output_dir,
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Wave A route preparation failed closed: {exc}\n")
    print(json.dumps({
        "routes": result["routes"],
        "retained_old_only_count": result["retained_old_only_count"],
        "shared_identical_count": result["shared_identical_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
