"""Public source fixtures for the two independently pinned old token formats."""

from pathlib import Path
import sys
import types

from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.probe_auth import old_probe_context


def auth_source(*, legacy=False):
    source = (Path(__file__).resolve().parents[3] / "src/bilun/api/auth.py").read_text()
    if legacy:
        # The complete legacy AST is blob 144f993e8f6fc105e661fb43f93bb3991b61e186;
        # these are its three executable differences from blob 3d27d22c.
        source = source.replace('SESSION_PURPOSE = "bilun-developer-v1"\n', "")
        source = source.replace('f"{SESSION_PURPOSE}:{username}.{expires_at}"', 'f"{username}.{expires_at}"')
        source = source.replace(
            'purpose_username, exp_str = payload.decode("utf-8").rsplit(".", 1)\n'
            '        purpose, username = purpose_username.split(":", 1)\n'
            '        if purpose != SESSION_PURPOSE or not username:\n'
            '            return None',
            'username, exp_str = payload.decode("utf-8").rsplit(".", 1)',
        )
    return source


def write_old_auth(runtime, *, legacy=False):
    path = runtime / "src/bilun/api/auth.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(auth_source(legacy=legacy))
    return path


def source_context(runtime, *, legacy=False):
    write_old_auth(runtime, legacy=legacy)
    return old_probe_context(runtime, expected_runtime_sha256=_runtime_digest(runtime, backend=True))


def source_verifier(monkeypatch, *, legacy=False):
    module = types.ModuleType("fixture_old_auth")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(compile(auth_source(legacy=legacy), "fixture_old_auth.py", "exec"), module.__dict__)
    return module
