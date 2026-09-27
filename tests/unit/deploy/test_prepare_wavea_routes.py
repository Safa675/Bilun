"""Sealed route preparation preserves old browser assets without touching Caddy."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.deploy.prepare_wavea_routes import OLD_CADDYFILE, prepare_wavea_routes


def test_candidate_route_keeps_old_only_assets_and_rejects_collisions(tmp_path: Path) -> None:
    live = tmp_path / "Caddyfile"
    live.write_bytes(OLD_CADDYFILE)
    old = tmp_path / "old"
    candidate = tmp_path / "candidate"
    for root, unique in ((old, "old.js"), (candidate, "new.js")):
        static = root / ".next" / "static" / "chunks"
        static.mkdir(parents=True)
        (static / unique).write_bytes(unique.encode())
        (static / "shared.js").write_bytes(b"identical")
    routes = tmp_path / "routes"
    routes.mkdir(mode=0o700)
    report = prepare_wavea_routes(
        live_config=live, old_frontend=old, candidate_frontend=candidate,
        output_dir=routes,
        adapt=lambda path: {"apps": {"route": path.read_text()}},
        validate=lambda _: None,
    )
    assert report["retained_old_only_count"] == 1
    assert report["shared_identical_count"] == 1
    assert (routes / "old.caddy").read_bytes() == OLD_CADDYFILE
    candidate_route = (routes / "candidate.caddy").read_text()
    assert "@old_static path /_next/static/chunks/old.js" in candidate_route
    assert "reverse_proxy 127.0.0.1:3000" in candidate_route
    assert "reverse_proxy 127.0.0.1:8002" in candidate_route
    assert "reverse_proxy 127.0.0.1:3099" in candidate_route
    assert "/_next/static/chunks/new.js" not in candidate_route
    (candidate / ".next/static/chunks/shared.js").write_bytes(b"different")
    rejected = tmp_path / "rejected"
    rejected.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="collide"):
        prepare_wavea_routes(
            live_config=live, old_frontend=old, candidate_frontend=candidate,
            output_dir=rejected,
            adapt=lambda path: {"apps": {"route": path.read_text()}},
            validate=lambda _: None,
        )
    assert list(rejected.iterdir()) == []
    assert live.read_bytes() == OLD_CADDYFILE
