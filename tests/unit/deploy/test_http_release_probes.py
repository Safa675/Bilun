"""Public route probes distinguish the old, barrier, and signed candidate pairs."""

from __future__ import annotations

import json

from scripts.deploy.http_release_probes import HttpReleaseProbes


def test_public_http_probe_checks_pairing_assets_and_barrier() -> None:
    state = {"route": "old", "corrupt_asset": False, "retain_old": True, "old_dead": False}
    public = "https://app.bilun.tech"
    assets = {
        pair: [f"/_next/static/{pair}-{number}.js" for number in range(10)]
        + [f"/favicon.ico?v={pair}"]
        for pair in ("old", "candidate")
    }

    def fetch(base: str, path: str, cookie: str | None) -> tuple[int, bytes]:
        pair = (
            state["route"] if base == public
            else "old" if base in ("http://127.0.0.1:8001", "http://127.0.0.1:3000")
            else "candidate"
        )
        if pair == "barrier":
            return 503, b"maintenance"
        if pair == "old" and state["old_dead"] and path == "/health":
            return 503, b"dead"
        if (
            base == public and pair == "candidate" and path in assets["old"]
            and state["retain_old"]
        ):
            pair = "old"
        if path == "/login":
            return 200, (
                "<html>" + "".join(f'<script src="{item}"></script>' for item in assets[pair])
                + "</html>"
            ).encode()
        if path in assets[pair]:
            if state["corrupt_asset"] and base == public:
                return 200, b"wrong asset"
            return 200, f"{pair}:{path}".encode()
        if path.startswith("/patient/"):
            return (200, b"patient") if cookie else (401, b"unauthorized")
        if path == "/health" or path.startswith("/api/"):
            if path.startswith("/api/") and not cookie:
                return 401, b"unauthorized"
            return 200, json.dumps({"pair": pair, "path": path}).encode()
        return 404, b"missing"

    probes = HttpReleaseProbes(
        public_base=public, patient_id="P1",
        old_tuple=lambda: {
            "status": "protected_old_pair_observed", "tuple_sha256": "a" * 64,
        },
        candidate_tuple=lambda: {
            "status": "candidate_tuple_observed", "tuple_sha256": "b" * 64,
            "private_activation_verified": True,
        },
        activation_gate=lambda _: True,
        cookie_factory=lambda: "bilun:session=fixture",
        fetch=fetch,
    )
    assert probes.direct_tuple_sha256("old") == "a" * 64
    assert probes.direct_tuple_sha256("candidate") == "b" * 64
    assert probes.public_tuple_sha256("old") == "a" * 64
    assert probes.public_tuple_sha256("candidate") is None
    state["route"] = "barrier"
    assert probes.public_barrier_ready() is True
    state["old_dead"] = True
    assert probes.public_barrier_ready() is True
    state["old_dead"] = False
    state["route"] = "candidate"
    assert probes.public_tuple_sha256("candidate") == "b" * 64
    state["retain_old"] = False
    assert probes.public_tuple_sha256("candidate") is None
    state["retain_old"] = True
    state["corrupt_asset"] = True
    assert probes.public_tuple_sha256("candidate") is None
    state["corrupt_asset"] = False
    state["route"] = "old"
    assert probes.public_tuple_sha256("old") == "a" * 64
