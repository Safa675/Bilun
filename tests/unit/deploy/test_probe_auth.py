"""Probe compatibility is proved from source, never guessed from marker absence."""

import base64
import hashlib
from dataclasses import replace

import pytest

from scripts.deploy import probe_auth as probe
from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.rehearse_wavea_pair import env_digest
from tests.unit.deploy.probe_auth_fixtures import auth_source, source_context, source_verifier, write_old_auth
from tests.unit.deploy.test_candidate_environment import candidate_auth, write_env


def payload(cookie):
    value = cookie.split("=", 1)[1].split(".")[0]
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()


@pytest.mark.parametrize("legacy", [False, True])
def test_verified_source_selects_real_old_format_without_changing_env(tmp_path, monkeypatch, legacy):
    values = candidate_auth()
    values.pop("BILUN_SESSION_TOKEN_PURPOSE")
    captured = write_env(tmp_path / "captured.nul", values)
    before = captured.read_bytes(), dict(values), env_digest(values)
    context = source_context(tmp_path / "runtime", legacy=legacy)
    cookie = probe.probe_cookie(values, old_context=context, now=1000)
    assert payload(cookie) == ("" if legacy else "bilun-developer-v1:") + values["BILUN_AUTH_USERNAME"] + ".1300"
    assert (captured.read_bytes(), values, env_digest(values)) == before
    assert context.source_sha256 == hashlib.sha256((context.runtime / "src/bilun/api/auth.py").read_bytes()).hexdigest()
    # Exercise the actual pinned source's issuer and verifier in a fabricated module.
    module = source_verifier(monkeypatch, legacy=legacy)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(module.time, "time", lambda: 1000)
    assert module.verify_session_token(cookie.split("=", 1)[1]).username == values["BILUN_AUTH_USERNAME"]
    assert module.issue_session_token(values["BILUN_AUTH_USERNAME"], ttl_seconds=300) == cookie.split("=", 1)[1]
    from src.bilun.api import auth
    candidate = probe.probe_cookie({**values, "BILUN_SESSION_TOKEN_PURPOSE": "bilun-developer-v1"}, now=1000)
    assert auth.verify_session_token(candidate.split("=", 1)[1]).username == values["BILUN_AUTH_USERNAME"]
    assert (auth.verify_session_token(cookie.split("=", 1)[1]) is None) is legacy


def test_unmarked_environment_alone_never_selects_legacy():
    values = candidate_auth()
    values.pop("BILUN_SESSION_TOKEN_PURPOSE")
    with pytest.raises(ValueError, match="verified source context"):
        probe.probe_cookie(values)


@pytest.mark.parametrize("marker", ["unknown", "bilun-developer-v1"])
def test_unknown_or_source_conflicting_marker_fails_closed(tmp_path, marker):
    context = source_context(tmp_path / "legacy", legacy=True)
    with pytest.raises(ValueError, match="Unknown|conflicts"):
        probe.probe_cookie({**candidate_auth(), "BILUN_SESSION_TOKEN_PURPOSE": marker}, old_context=context)


@pytest.mark.parametrize("change", [
    lambda s: s.replace('SESSION_PURPOSE = "bilun-developer-v1"', 'SESSION_PURPOSE = "unknown"'),
    lambda s: s.replace('SESSION_PURPOSE = "bilun-developer-v1"', 'SESSION_PURPOSE = os.getenv("FORMAT")'),
    lambda s: s + '\nSESSION_PURPOSE = "unknown"\n',
    lambda s: s + '\ndef verify_session_token(token):\n    return True\n',
    lambda s: s.replace('purpose != SESSION_PURPOSE', 'purpose == SESSION_PURPOSE'),
    lambda s: s.replace('f"{SESSION_PURPOSE}:{username}.{expires_at}"', 'f"{username}.{expires_at}"'),
    lambda s: s.replace('hmac.compare_digest(provided_sig, expected_sig)', 'True'),
])
def test_unknown_rebound_or_disagreeing_source_fails_even_with_its_own_digest(tmp_path, change):
    runtime = tmp_path / "runtime"
    path = write_old_auth(runtime)
    path.write_text(change(path.read_text()))
    with pytest.raises(ValueError, match="Unknown old probe"):
        probe.old_probe_context(runtime, expected_runtime_sha256=_runtime_digest(runtime, backend=True))


@pytest.mark.parametrize("change", ["purpose", "source_sha256", "runtime_sha256"])
def test_fabricated_context_fields_fail_closed(tmp_path, change):
    context = source_context(tmp_path / "runtime")
    bad = replace(context, **{change: "" if change == "purpose" else "a" * 64})
    with pytest.raises(ValueError, match="context changed|differs"):
        probe.probe_cookie(candidate_auth(), old_context=bad)


@pytest.mark.parametrize("change", ["auth", "unrelated"])
def test_runtime_mutation_after_context_capture_is_rejected(tmp_path, change):
    context = source_context(tmp_path / "runtime")
    target = context.runtime / ("src/bilun/api/auth.py" if change == "auth" else "src/other.py")
    target.write_text("changed = True\n")
    with pytest.raises(ValueError, match="differs from captured"):
        probe.probe_cookie(candidate_auth(), old_context=context)


def test_source_replaced_between_digest_checks_is_rejected(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    path = write_old_auth(runtime)
    expected = _runtime_digest(runtime, backend=True)
    calls = 0

    def moving_digest(root, *, backend):
        nonlocal calls
        calls += 1
        result = _runtime_digest(root, backend=backend)
        if calls == 1:
            path.write_text(path.read_text() + "\n# replaced after first inventory\n")
        return result

    monkeypatch.setattr(probe, "_runtime_digest", moving_digest)
    with pytest.raises(ValueError, match="changed during"):
        probe.old_probe_context(runtime, expected_runtime_sha256=expected)


def test_parsed_other_known_source_cannot_inherit_inventoried_runtime(tmp_path, monkeypatch):
    context = source_context(tmp_path / "runtime")
    path = context.runtime / "src/bilun/api/auth.py"
    alternate = auth_source(legacy=True).encode()
    alternate += b" " * (path.stat().st_size - len(alternate))
    assert len(alternate) == path.stat().st_size
    real_read = type(path).read_bytes
    monkeypatch.setattr(type(path), "read_bytes", lambda value:
                        alternate if value == path else real_read(value))
    with pytest.raises(ValueError, match="parsed source differs"):
        probe.old_probe_context(context.runtime, expected_runtime_sha256=context.runtime_sha256)


@pytest.mark.parametrize("change", ["missing", "malformed", "symlink", "hardlink"])
def test_noncanonical_or_unreadable_source_fails_closed(tmp_path, change):
    runtime = tmp_path / "runtime"
    path = write_old_auth(runtime)
    (runtime / "src/other.py").write_text("other = True\n")
    if change == "missing":
        path.unlink()
    elif change == "malformed":
        path.write_text("def broken(:\n")
    else:
        target = tmp_path / "external-auth.py"
        target.write_bytes(path.read_bytes())
        path.unlink()
        if change == "symlink":
            path.symlink_to(target)
        else:
            import os
            os.link(target, path)
    with pytest.raises(ValueError, match="source"):
        probe.old_probe_context(runtime, expected_runtime_sha256=_runtime_digest(runtime, backend=True))


def test_candidate_format_remains_explicit_and_separate_from_legacy(tmp_path):
    values = candidate_auth()
    context = source_context(tmp_path / "legacy", legacy=True)
    old = {key: value for key, value in values.items() if key != "BILUN_SESSION_TOKEN_PURPOSE"}
    assert payload(probe.probe_cookie(old, old_context=context, now=1000)).startswith(values["BILUN_AUTH_USERNAME"] + ".")
    assert payload(probe.probe_cookie(values, now=1000)).startswith("bilun-developer-v1:")
