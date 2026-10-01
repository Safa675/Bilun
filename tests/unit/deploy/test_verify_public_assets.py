from __future__ import annotations

import json

import pytest

from scripts.deploy.verify_public_assets import inspect_assets


@pytest.fixture
def artifact(tmp_path):
    static = tmp_path / ".next/static/chunks"
    static.mkdir(parents=True)
    (static / "app.js").write_text("console.log('billing officer');")
    (tmp_path / ".next/required-server-files.json").write_text(json.dumps({"config": {"productionBrowserSourceMaps": False}}))
    (tmp_path / "public").mkdir()
    return tmp_path


def test_normal_browser_code_and_private_server_maps_are_allowed(artifact):
    server = artifact / ".next/server"
    server.mkdir()
    (server / "server.js.map").write_text("server-only")
    assert inspect_assets(artifact)["ok"] is True


@pytest.mark.parametrize("name", ["rules.py", "app.js.map", ".env.local", "source.zip", "cache.duckdb"])
def test_private_files_in_public_root_fail(artifact, name):
    (artifact / "public" / name).write_text("private")
    report = inspect_assets(artifact)
    assert report["ok"] is False
    assert report["problems"][0]["reason"] == "private_file_or_source_map"


def test_inline_maps_and_supplied_secrets_fail_without_printing_secret(artifact):
    secret = "synthetic-secret-never-display"
    (artifact / ".next/static/chunks/app.js").write_text(f"const x='{secret}';\n//# sourceMappingURL=data:application/json;base64,e30=")
    report = inspect_assets(artifact, secrets=[secret])
    assert {item["reason"] for item in report["problems"]} == {"source_map_reference", "secret_content"}
    assert secret not in json.dumps(report)


def test_public_symlink_does_not_escape_inspection(artifact, tmp_path):
    target = tmp_path / "private"
    target.mkdir()
    (target / "source.py").write_text("private")
    (artifact / "public/link").symlink_to(target, target_is_directory=True)
    assert inspect_assets(artifact)["ok"] is False


def test_incomplete_or_map_enabled_build_fails(artifact):
    (artifact / ".next/required-server-files.json").write_text(json.dumps({"config": {"productionBrowserSourceMaps": True}}))
    assert inspect_assets(artifact)["ok"] is False
