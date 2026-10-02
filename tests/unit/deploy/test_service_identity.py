from __future__ import annotations

import pytest

from scripts.deploy.service_identity import stable_environment_sha256


def test_systemd_invocation_identity_can_change_across_restart():
    old = b"BILUN_SESSION_SECRET=private\0INVOCATION_ID=old\0SYSTEMD_EXEC_PID=123\0JOURNAL_STREAM=2:1\0"
    new = b"JOURNAL_STREAM=8:2\0BILUN_SESSION_SECRET=private\0INVOCATION_ID=new\0SYSTEMD_EXEC_PID=999\0"
    assert stable_environment_sha256(old) == stable_environment_sha256(new)


@pytest.mark.parametrize("key", ["BILUN_SESSION_SECRET", "OPENAI_API_KEY", "BILUN_PUBLIC_BILLING_ENABLED", "UNKNOWN"])
def test_every_application_or_unknown_setting_stays_bound(key):
    old = f"{key}=old\0INVOCATION_ID=one\0".encode()
    new = f"{key}=new\0INVOCATION_ID=two\0".encode()
    assert stable_environment_sha256(old) != stable_environment_sha256(new)


@pytest.mark.parametrize("raw", [b"", b"NO_NULL=value", b"NO_EQUALS\0", b"KEY=a\0KEY=b\0", b"=value\0"])
def test_ambiguous_environment_is_rejected(raw):
    with pytest.raises(ValueError): stable_environment_sha256(raw)


@pytest.mark.parametrize("unit_user,effective_uid", [("bilun", "1000"), ("root", "1000"), ("bilun", "0")])
def test_private_release_profile_rejects_nonroot_service_before_mutation(tmp_path, monkeypatch, unit_user, effective_uid):
    from types import SimpleNamespace
    from scripts.deploy import paired_release
    process = tmp_path / "123"
    process.mkdir()
    (process / "status").write_text("Uid:\t" + "\t".join([effective_uid] * 4) + "\n")
    monkeypatch.setattr(paired_release.os, "geteuid", lambda: 0)
    monkeypatch.setattr(paired_release, "_run", lambda *args: unit_user if "--property=User" in args else "no")
    service = SimpleNamespace(unit="bilun-backend.service", listener_pid=123)
    with pytest.raises(ValueError, match="identity"):
        paired_release.SingleVpsDriver._service_access_gate([service], proc_root=tmp_path)


def test_existing_root_service_context_is_supported(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scripts.deploy import paired_release
    process = tmp_path / "123"
    process.mkdir()
    (process / "status").write_text("Uid:\t0\t0\t0\t0\n")
    monkeypatch.setattr(paired_release.os, "geteuid", lambda: 0)
    monkeypatch.setattr(paired_release, "_run", lambda *args: "root" if "--property=User" in args else "no")
    paired_release.SingleVpsDriver._service_access_gate(
        [SimpleNamespace(unit="bilun-backend.service", listener_pid=123)], proc_root=tmp_path,
    )
