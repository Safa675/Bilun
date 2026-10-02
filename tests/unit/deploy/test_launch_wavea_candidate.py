"""The private listener launcher requires candidate credentials and pins new routing."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from scripts.deploy.launch_wavea_candidate import _CONFIG_PATHS, candidate_command


def test_signed_candidate_launch_replaces_stale_release_environment(tmp_path: Path) -> None:
    config = {key: str(tmp_path / key) for key in _CONFIG_PATHS}
    config["code_sha"] = "a" * 40
    for key in ("backend_runtime", "frontend_runtime"):
        Path(config[key]).mkdir()
    (Path(config["frontend_runtime"]) / "server.js").write_text("server")
    for key in _CONFIG_PATHS - {
        "backend_runtime", "frontend_runtime", "backend_python", "node",
        "candidate_backend_environment", "candidate_frontend_environment",
    }:
        Path(config[key]).write_text(key)
    config["backend_python"] = sys.executable
    config["node"] = sys.executable
    candidate = (
        b"BILUN_AUTH_USERNAME=private-user\0"
        b"BILUN_AUTH_PASSWORD=fixture-hash\0"
        b"BILUN_SESSION_SECRET=fixture-only-candidate-secret\0"
        b"BILUN_SESSION_TOKEN_PURPOSE=bilun-developer-v1\0"
        b"BILUN_DEV_USERNAMES=private-user\0"
        b"BILUN_STARTUP_POLICY=stale\0"
        b"BILUN_RELEASE_CODE_SHA=stale\0"
        b"BILUN_CACHE_DB_PATH=/old/cache\0"
        b"PYTHONPATH=/old/code\0"
    )
    Path(config["candidate_backend_environment"]).write_bytes(candidate)
    Path(config["candidate_frontend_environment"]).write_bytes(b"NODE_ENV=production\0")
    for name in ("candidate_backend_environment", "candidate_frontend_environment"):
        Path(config[name]).chmod(0o600)

    executable, args, cwd, backend = candidate_command("backend", config)
    assert executable == Path(sys.executable)
    assert args[-4:] == ["--host", "127.0.0.1", "--port", "8002"]
    assert cwd == Path(config["backend_runtime"])
    assert backend["BILUN_AUTH_USERNAME"] == "private-user"
    assert backend["BILUN_STARTUP_POLICY"] == "verified-load-only"
    assert backend["BILUN_CACHE_DB_PATH"] == config["cache_path"]
    assert backend["BILUN_RELEASE_CODE_SHA"] == "a" * 40
    assert backend["BILUN_RELEASE_SOURCE_MANIFEST_SHA256"] == hashlib.sha256(
        Path(config["source_roster_path"]).read_bytes()
    ).hexdigest()
    assert backend["BILUN_WAVEA_ACTIVATION_RECEIPT"] == config[
        "activation_receipt_path"
    ]
    assert "PYTHONPATH" not in backend

    executable, args, cwd, frontend = candidate_command("frontend", config)
    assert executable == Path(sys.executable)
    assert args[-1] == str(cwd / "server.js")
    assert frontend["PORT"] == "3099"
    assert frontend["HOSTNAME"] == "127.0.0.1"
    assert frontend["API_PROXY_TARGET"] == "http://127.0.0.1:8002"
    assert frontend["BILUN_RELEASE_CODE_SHA"] == "a" * 40
    assert "BILUN_STARTUP_POLICY" not in frontend
    assert "BILUN_WAVEA_ACTIVATION_RECEIPT" not in frontend
