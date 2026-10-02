from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scripts.deploy import paired_release, prepare_single_vps_release, snapshot_maintenance


@pytest.fixture(params=["bilun-single-vps-preparation-v1", "bilun-single-vps-preparation-v2",
                        "bilun-single-vps-preparation-v3"])
def manifest(tmp_path, request):
    path = tmp_path / "machine.json"
    path.write_text(json.dumps({"schema_version": request.param,
                                "bundle_root": str(tmp_path / "absent")}))
    path.chmod(0o600)
    return path


@pytest.mark.parametrize("action", ["prepare", "rollback", "status", "activate"])
def test_snapshot_recovery_precedes_all_candidate_parsing(manifest, monkeypatch, capsys, action):
    calls = []
    monkeypatch.setattr(prepare_single_vps_release, "inspect_preparation_snapshot",
                        lambda _: {"state": "snapshot_blocked", "recovery_needed": True})
    monkeypatch.setattr(prepare_single_vps_release, "recover_preparation_snapshot",
                        lambda _: calls.append("recover") or {"state": "restored", "fresh_bundle_required": True})
    monkeypatch.setattr(prepare_single_vps_release, "prepare_release_bundle",
                        lambda _: pytest.fail("Candidate build/CI must not run during snapshot recovery"))
    code = paired_release.main([action, "--manifest", str(manifest)])
    assert code == (1 if action == "activate" else 0)
    assert calls == (["recover"] if action in {"prepare", "rollback"} else [])
    if action != "activate": assert json.loads(capsys.readouterr().out)["state"] in {"restored", "snapshot_blocked"}


@pytest.mark.parametrize("action", ["status", "rollback"])
def test_snapshot_journal_recovers_without_any_candidate_manifest(tmp_path, monkeypatch, action):
    path = tmp_path / "journal.json"
    calls = []
    monkeypatch.setattr(snapshot_maintenance, "inspect_snapshot", lambda value: calls.append(("inspect", value)) or {})
    monkeypatch.setattr(snapshot_maintenance, "recover_snapshot", lambda value: calls.append(("recover", value)) or {})
    assert paired_release.main([action, "--snapshot-journal", str(path)]) == 0
    assert calls == [("inspect" if action == "status" else "recover", path)]


def test_preparation_status_is_read_only_before_bundle_exists(manifest, monkeypatch, capsys):
    monkeypatch.setattr(prepare_single_vps_release, "inspect_preparation_snapshot", lambda _: None)
    assert paired_release.main(["status", "--manifest", str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "unprepared"
    assert not (manifest.parent / "absent").exists()


def test_preparation_dispatches_bundle_handoff_to_paired_prepare(manifest, monkeypatch, capsys):
    calls = []
    paired_path = manifest.parent / "paired-manifest.json"
    paired_manifest = {"schema_version": "bilun-single-vps-pair-v1", "release_id": "dispatch-test"}
    paired_path.write_text(json.dumps(paired_manifest))
    paired_path.chmod(0o600)
    monkeypatch.setattr(prepare_single_vps_release, "inspect_preparation_snapshot", lambda _: None)
    monkeypatch.setattr(prepare_single_vps_release, "prepare_release_bundle", lambda path:
                        calls.append(("bundle", path)) or {"paired_manifest_path": str(paired_path)})

    def driver(value):
        calls.append(("driver", value))
        return SimpleNamespace(root=manifest.parent, paths={"lock_path": manifest.parent / "lock"})

    def transaction(**kwargs):
        assert kwargs["state_dir"] == manifest.parent
        assert kwargs["lock_path"] == manifest.parent / "lock"
        assert kwargs["manifest_sha256"] == paired_release._stable_file_hash(paired_path)
        return SimpleNamespace(prepare=lambda: calls.append(("prepare", None)) or {"state": "prepared"})

    monkeypatch.setattr(paired_release, "SingleVpsDriver", driver)
    monkeypatch.setattr(paired_release, "PairedReleaseTransaction", transaction)
    assert paired_release.main(["prepare", "--manifest", str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out) == {"state": "prepared"}
    assert calls == [("bundle", manifest), ("driver", paired_manifest), ("prepare", None)]
