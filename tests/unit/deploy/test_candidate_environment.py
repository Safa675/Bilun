"""Candidate auth is explicit, purpose-bound and already developer-authorized."""

from pathlib import Path

import pytest

from scripts.deploy.candidate_environment import candidate_environments
from scripts.deploy.launch_wavea_candidate import candidate_command


def candidate_auth():
    return {
        "BILUN_AUTH_USERNAME": "fixture-developer",
        "BILUN_AUTH_PASSWORD": "fixture-password-hash",
        "BILUN_SESSION_SECRET": "fixture-candidate-secret",
        "BILUN_SESSION_TOKEN_PURPOSE": "bilun-developer-v1",
        "BILUN_DEV_USERNAMES": "other-user, Fixture-Developer",
    }


def write_env(path: Path, values):
    path.write_bytes(b"\0".join(f"{key}={value}".encode() for key, value in values.items()) + b"\0")
    path.chmod(0o600)
    return path


def test_candidate_auth_preserved_without_frontend_credentials_or_role_grant(tmp_path):
    auth = candidate_auth()
    backend = write_env(tmp_path / "backend.nul", {
        **auth, "BILUN_STARTUP_POLICY": "stale", "PYTHONPATH": "/fabricated/stale",
        "BILUN_WAVEA_ACTIVATION_KEY_FILE": "/fabricated/stale.key",
    })
    frontend = write_env(tmp_path / "frontend.nul", {
        "NODE_ENV": "production", "API_PROXY_TARGET": "http://127.0.0.1:8001",
        "BILUN_SESSION_SECRET": "optional-frontend-value-unchanged",
    })
    before = backend.read_bytes(), frontend.read_bytes()
    actual_backend, actual_frontend = candidate_environments(backend, frontend)
    assert actual_backend == auth
    assert actual_frontend == {
        "NODE_ENV": "production", "BILUN_SESSION_SECRET": "optional-frontend-value-unchanged",
    }
    assert (backend.read_bytes(), frontend.read_bytes()) == before


@pytest.mark.parametrize("change", [
    {"BILUN_SESSION_TOKEN_PURPOSE": ""}, {"BILUN_SESSION_TOKEN_PURPOSE": "wrong"},
    {"BILUN_AUTH_USERNAME": ""}, {"BILUN_AUTH_PASSWORD": ""},
    {"BILUN_SESSION_SECRET": ""}, {"BILUN_SESSION_SECRET": " padded "},
    {"BILUN_DEV_USERNAMES": ""}, {"BILUN_DEV_USERNAMES": "somebody-else"},
])
def test_candidate_auth_rejects_invalid_context_without_mutating_it(tmp_path, change):
    backend = write_env(tmp_path / "backend.nul", {**candidate_auth(), **change})
    frontend = write_env(tmp_path / "frontend.nul", {"NODE_ENV": "production"})
    before = backend.read_bytes()
    with pytest.raises(ValueError) as error:
        candidate_environments(backend, frontend)
    assert "fixture-candidate-secret" not in str(error.value)
    assert backend.read_bytes() == before


@pytest.mark.parametrize("raw", [b"", b"A=b", b"A=b\0A=c\0", b"=value\0", b"missing-equals\0"])
def test_candidate_environment_rejects_malformed_nul_files(tmp_path, raw):
    backend = write_env(tmp_path / "backend.nul", candidate_auth())
    frontend = write_env(tmp_path / "frontend.nul", {"NODE_ENV": "production"})
    frontend.write_bytes(raw)
    with pytest.raises(ValueError, match="Candidate environment"):
        candidate_environments(backend, frontend)


def test_old_launch_manifest_requires_explicit_candidate_regeneration():
    with pytest.raises(ValueError, match="regenerate.*candidate environment paths used in rehearsal"):
        candidate_command("backend", {"old_backend_environment": "/fabricated/old.nul"})
