"""The Caddy adapter must observe a loaded route, not trust a reload return code."""

from __future__ import annotations

import json
import hashlib
import os
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
    driver.verify_sealed_routes()
    assert driver.loaded_route_sha256() == expected["old"]
    assert driver.installed_route_sha256() == expected["old"]
    driver.install("barrier")
    assert driver.loaded_route_sha256() == expected["barrier"]
    assert driver.installed_route_sha256() == expected["barrier"]
    driver.install("candidate")
    assert driver.loaded_route_sha256() == expected["candidate"]
    driver.install("old")
    assert driver.loaded_route_sha256() == expected["old"]
    assert driver.installed_route_sha256() == expected["old"]


def test_disk_route_is_observed_independently_from_loaded_route(tmp_path: Path):
    driver, files, expected, _, _ = _fixture(tmp_path)
    driver.config_path.write_bytes(files["candidate"].read_bytes())
    assert driver.loaded_route_sha256() == expected["old"]
    assert driver.installed_route_sha256() == expected["candidate"]
    driver.config_path.write_text("tampered")
    assert driver.installed_route_sha256() is None


def test_tampered_template_never_reloads(tmp_path: Path):
    driver, files, expected, _, _ = _fixture(tmp_path)
    files["candidate"].write_text('{"apps":{"http":{"upstream":3100}}}')
    with pytest.raises(TransactionError, match="bytes differ from release manifest"):
        driver.install("candidate")
    assert driver.loaded_route_sha256() == expected["old"]


def test_unloadable_old_route_blocks_preflight_before_switch(tmp_path: Path):
    driver, files, expected, _, _ = _fixture(tmp_path)
    files["old"].write_text('{"apps":{"http":{"upstream":3001}}}')
    with pytest.raises(TransactionError, match="old recovery route differs"):
        driver.verify_sealed_routes()
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


def test_maintenance_install_preserves_restart_file_ownership_and_permissions(tmp_path, monkeypatch):
    driver, _, _, _, _ = _fixture(tmp_path)
    driver.config_path.chmod(0o640)
    before = driver.config_path.stat()
    calls = []
    real = os.fchown
    def capture(fd, uid, gid):
        calls.append((uid, gid))
        real(fd, uid, gid)
    monkeypatch.setattr(os, "fchown", capture)
    driver.install("barrier")
    assert calls == [(before.st_uid, before.st_gid)]
    after = driver.config_path.stat()
    assert (after.st_uid, after.st_gid, after.st_mode & 0o777) == (before.st_uid, before.st_gid, 0o640)


def test_same_port_maintenance_supports_only_old_and_barrier(tmp_path):
    old, files, expected, digests, serving = _fixture(tmp_path)
    names = {"old", "barrier"}
    driver = CaddyRouteDriver(
        config_path=old.config_path, route_files={key: files[key] for key in names},
        expected_digests={key: expected[key] for key in names},
        expected_file_digests={key: digests[key] for key in names},
        adapt=old.adapt, validate=old.validate, reload=old.reload, loaded=old.loaded,
    )
    driver.install("barrier")
    assert driver.loaded_route_sha256() == expected["barrier"]
    driver.install("old")
    assert driver.installed_route_sha256() == expected["old"]
    with pytest.raises(TransactionError): driver.install("candidate")


@pytest.mark.parametrize("foreign", ["installed", "loaded"])
def test_paired_rollback_does_not_overwrite_foreign_caddy(tmp_path, monkeypatch, foreign):
    from scripts.deploy.paired_release import SingleVpsDriver
    route, files, expected, digests, serving = _fixture(tmp_path)
    driver = object.__new__(SingleVpsDriver)
    driver.paths = {"caddy_config": route.config_path}
    saved = route.config_path.stat()
    prepared = {
        "routes": {name: {"path": str(files[name]), "route_sha256": expected[name], "file_sha256": digests[name]}
                   for name in ("old", "barrier")},
        "caddy_metadata": {"mode": saved.st_mode & 0o777, "uid": saved.st_uid, "gid": saved.st_gid},
    }
    monkeypatch.setattr(driver, "_prepared", lambda: prepared)
    monkeypatch.setattr(driver, "_routes", lambda: route)
    monkeypatch.setattr(driver, "_check_restore_targets", lambda: pytest.fail("Should not reach restore"))
    if foreign == "installed":
        route.config_path.write_text("operator Caddy edit")
    else:
        serving["value"] = {"apps": {"http": {"operator": True}}}
    file_before, loaded_before = route.config_path.read_bytes(), serving["value"]
    with pytest.raises(ValueError, match="Unrelated Caddy"):
        driver.rollback_gate()
    with pytest.raises(ValueError, match="Unrelated Caddy"):
        driver.maintenance()
    assert route.config_path.read_bytes() == file_before
    assert serving["value"] == loaded_before
