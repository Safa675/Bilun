from __future__ import annotations

import os

import pytest

from scripts.generate_developer_auth_env import render_environment, write_new_environment


def parse(content):
    return {key: value.strip("'") for line in content.splitlines() if not line.startswith("#") for key, value in [line.split("=", 1)]}


def test_cutover_rotates_signing_secret_and_limits_developer_identity():
    from src.bilun.api.auth import verify_password

    password = "new-synthetic-developer-password"
    first = parse(render_environment("developer", password))
    second = parse(render_environment("developer", password))
    assert password not in str(first)
    assert verify_password(password, first["BILUN_AUTH_PASSWORD"])
    assert first["BILUN_SESSION_SECRET"] != second["BILUN_SESSION_SECRET"]
    assert first["BILUN_HEALTH_PROBE_TOKEN"] != second["BILUN_HEALTH_PROBE_TOKEN"]
    assert first["BILUN_DEV_USERNAMES"] == "developer"
    assert first["BILUN_PUBLIC_BILLING_ENABLED"] == "0"
    assert first["BILUN_COOKIE_SECURE"] == "1"
    assert first["BILUN_SESSION_TOKEN_PURPOSE"] == "bilun-developer-v1"


def test_config_write_is_private_and_never_overwrites(tmp_path):
    target = tmp_path / "developer.env"
    write_new_environment(target, "fixture")
    assert os.stat(target).st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_new_environment(target, "replacement")
    assert target.read_text() == "fixture"
    link = tmp_path / "link.env"
    link.symlink_to(target)
    with pytest.raises(FileExistsError):
        write_new_environment(link, "replacement")


@pytest.mark.parametrize("username,password", [("dev'\nBAD=1", "long-synthetic-password"), ("dev", "short")])
def test_invalid_credentials_cannot_inject_environment_lines(username, password):
    with pytest.raises(ValueError):
        render_environment(username, password)
