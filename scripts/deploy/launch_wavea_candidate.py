"""Exec a signed Wave A candidate listener from explicit candidate environments.

Use this as the ExecStart for private candidate services on :8002 and :3099.
The launch manifest contains paths and identities only. Effective process
environments stay in private NUL files and are never logged or copied to a
systemd unit. This command does not change the public route.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from scripts.deploy.candidate_environment import candidate_environments
from scripts.deploy.release_sidecar import _load_private_json
from scripts.deploy.verify_candidate_cache import _stable_file_hash

_CODE_SHA = re.compile(r"[0-9a-f]{40}\Z")
_CONFIG_PATHS = frozenset({
    "candidate_backend_environment", "candidate_frontend_environment", "backend_runtime",
    "frontend_runtime", "backend_python", "node", "cache_path",
    "source_roster_path", "activation_receipt_path", "activation_key_path",
})


def candidate_command(role: str, config: dict) -> tuple[Path, list[str], Path, dict[str, str]]:
    """Return one exact loopback command and sanitized inherited environment."""
    if (
        role not in {"backend", "frontend"}
        or set(config) != _CONFIG_PATHS | {"code_sha"}
        or not isinstance(config["code_sha"], str)
        or not _CODE_SHA.fullmatch(config["code_sha"])
        or any(
            not isinstance(config[key], str) or not Path(config[key]).is_absolute()
            for key in _CONFIG_PATHS
        )
    ):
        raise ValueError(
            "Signed candidate launch config is malformed; regenerate with the explicit "
            "candidate environment paths used in rehearsal"
        )
    paths = {key: Path(config[key]) for key in _CONFIG_PATHS}
    if any(
        path.is_symlink() for key, path in paths.items()
        if key not in {"backend_python", "node"}
    ) or any(
        not paths[key].is_dir() for key in ("backend_runtime", "frontend_runtime")
    ) or any(
        not paths[key].is_file() for key in _CONFIG_PATHS - {
            "backend_runtime", "frontend_runtime"
        }
    ):
        raise ValueError("Signed candidate launch artifacts are absent or linked")
    source_sha = _stable_file_hash(paths["source_roster_path"])
    backend, frontend = candidate_environments(
        paths["candidate_backend_environment"], paths["candidate_frontend_environment"],
    )
    values = backend if role == "backend" else frontend
    if role == "backend":
        values.update(
            BILUN_CACHE_DB_PATH=str(paths["cache_path"]),
            BILUN_RELEASE_CODE_SHA=config["code_sha"],
            BILUN_RELEASE_SOURCE_MANIFEST_SHA256=source_sha,
            BILUN_STARTUP_POLICY="verified-load-only",
            BILUN_WAVEA_ACTIVATION_RECEIPT=str(paths["activation_receipt_path"]),
            BILUN_WAVEA_ACTIVATION_KEY_FILE=str(paths["activation_key_path"]),
            PYTHONDONTWRITEBYTECODE="1",
        )
        executable = paths["backend_python"]
        argv = [
            str(executable), "-m", "uvicorn", "src.bilun.api:app",
            "--host", "127.0.0.1", "--port", "8002",
        ]
        cwd = paths["backend_runtime"]
    else:
        values.update(
            PORT="3099", HOSTNAME="127.0.0.1", NODE_ENV="production",
            API_PROXY_TARGET="http://127.0.0.1:8002",
            BILUN_RELEASE_CODE_SHA=config["code_sha"],
        )
        executable = paths["node"]
        argv = [str(executable), str(paths["frontend_runtime"] / "server.js")]
        cwd = paths["frontend_runtime"]
        if not (cwd / "server.js").is_file():
            raise ValueError("Signed candidate standalone frontend is missing")
    return executable, argv, cwd, values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("backend", "frontend"))
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config, _ = _load_private_json(args.config, root=args.config.parent)
        executable, command, cwd, values = candidate_command(args.role, config)
        os.chdir(cwd)
        os.execve(executable, command, values)
    except (OSError, ValueError) as exc:
        print(f"Wave A candidate launch failed closed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
