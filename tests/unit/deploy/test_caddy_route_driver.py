"""The Caddy adapter must observe a loaded route, not trust a reload return code."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from scripts.deploy.caddy_route_driver import CaddyRouteDriver, _digest
from scripts.deploy.release_transaction import TransactionError


def _fixture(tmp_path: Path):
    files = {}
    expected = {}
    file_digests = {}
    for route, upstream in (("old", 3000), ("barrier", 0), ("candidate", 3099)):
        file = tmp_path / f"{route}.caddy"
        value = {"apps": {"http": {"upstream": upstream}}}
        file.write_text(json.dumps(value))
        files[route] = file
        expected[route] = _digest(value)
        file_digests[route] = hashlib.sha256(file.read_bytes()).hexdigest()
    live = tmp_path / "Caddyfile"
    live.write_bytes(files["old"].read_bytes())
    serving = {"value": json.loads(live.read_text())}

    def reload(target: Path):
        serving["value"] = json.loads(target.read_text())

    driver = CaddyRouteDriver(
        config_path=live,
        route_files=files,
        expected_digests=expected,
        expected_file_digests=file_digests,
        adapt=lambda source: json.loads(source.read_text()),
        validate=lambda source: None,
        reload=reload,
        loaded=lambda url: serving["value"],
    )
    return driver, files, expected, file_digests, serving


def test_route_switch_reads_loaded_config_and_restores_exact_old_route(tmp_path: Path):
    driver, _, expected, _, _ = _fixture(tmp_path)
    assert driver.loaded_route_sha256() == expected["old"]
    driver.install("barrier")
    assert driver.loaded_route_sha256() == expected["barrier"]
    driver.install("candidate")
    assert driver.loaded_route_sha256() == expected["candidate"]
    driver.install("old")
    assert driver.loaded_route_sha256() == expected["old"]


def test_tampered_template_never_reloads(tmp_path: Path):
    driver, files, expected, _, _ = _fixture(tmp_path)
    files["candidate"].write_text('{"apps":{"http":{"upstream":3100}}}')
    with pytest.raises(TransactionError, match="bytes differ from release manifest"):
        driver.install("candidate")
    assert driver.loaded_route_sha256() == expected["old"]


def test_reload_that_does_not_change_loaded_config_is_rejected(tmp_path: Path):
    driver, _, expected, _, _ = _fixture(tmp_path)
    driver.reload = lambda target: None
    with pytest.raises(TransactionError, match="did not serve"):
        driver.install("candidate")
    assert driver.loaded_route_sha256() == expected["old"]


def test_symlink_template_and_non_loopback_admin_are_rejected(tmp_path: Path):
    driver, files, expected, file_digests, _ = _fixture(tmp_path)
    link = tmp_path / "linked.caddy"
    link.symlink_to(files["candidate"])
    with pytest.raises(ValueError, match="independent file"):
        CaddyRouteDriver(
            config_path=driver.config_path,
            route_files={**files, "candidate": link}, expected_digests=expected,
            expected_file_digests=file_digests,
        )
    with pytest.raises(ValueError, match="loopback"):
        CaddyRouteDriver(
            config_path=driver.config_path, route_files=files,
            expected_digests=expected, expected_file_digests=file_digests,
            admin_url="http://0.0.0.0:2019/config/",
        )
