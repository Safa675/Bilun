"""Only trusted explicit worker counts may select the expected invocation."""

import inspect
from pathlib import Path

import pytest

from scripts.deploy import build_traced_candidate as builder
from scripts.deploy import issue_wavea_activation as issuer
from scripts.deploy import verify_traced_build_attestation as verifier


@pytest.mark.parametrize("entrypoint", [
    builder.build_traced_candidate, issuer.issue_wavea_activation,
    verifier.verify_traced_build_attestation,
])
@pytest.mark.parametrize("field", ["payload_workers", "billing_workers"])
@pytest.mark.parametrize("invalid", [True, False, 0, 9, -1, "2", 2.0, None])
def test_direct_entry_rejects_invalid_counts_before_any_io(entrypoint, field, invalid):
    arguments = {
        name: Path("/fabricated/never-read")
        for name, value in inspect.signature(entrypoint).parameters.items()
        if value.default is inspect.Parameter.empty
    }
    with pytest.raises(ValueError, match="worker count"):
        entrypoint(**arguments, **{field: invalid})


def _manifest():
    return {
        **{key: f"/fabricated/{key}" for key in issuer._MANIFEST_PATHS},
        **{key: "fixture" for key in issuer._MANIFEST_STRINGS},
        "dependency_roots": ["/fabricated/dependencies"],
    }


@pytest.mark.parametrize("counts", [{}, {"payload_workers": 1, "billing_workers": 3},
                                   {"payload_workers": 3}, {"billing_workers": 1}])
def test_manifest_cli_forwards_explicit_counts_and_legacy_defaults(monkeypatch, counts):
    manifest = {**_manifest(), **counts}
    captured = []
    monkeypatch.setattr(issuer, "_load_private_json", lambda *_a, **_k: (manifest, "fixture"))
    monkeypatch.setattr(issuer, "_github_read_token", lambda: "fixture-only-token")
    monkeypatch.setattr(issuer, "issue_wavea_activation", lambda **kw: captured.append(kw) or {})
    assert issuer.main(["--manifest", "/fabricated/manifest.json"]) == 0
    assert captured[0]["payload_workers"] == counts.get("payload_workers", 2)
    assert captured[0]["billing_workers"] == counts.get("billing_workers", 2)


@pytest.mark.parametrize("extra", [
    {"payload_workers": True}, {"billing_workers": 0}, {"payload_workers": 9},
    {"billing_workers": "3"}, {"billing_workers": 3.0}, {"payload_workers": None},
    {"unknown_workers": 2},
])
def test_manifest_rejects_invalid_fields_before_credentials_or_issuance(monkeypatch, extra):
    manifest = {**_manifest(), **extra}
    monkeypatch.setattr(issuer, "_load_private_json", lambda *_a, **_k: (manifest, "fixture"))
    monkeypatch.setattr(issuer, "_github_read_token", lambda: pytest.fail("credential read"))
    monkeypatch.setattr(issuer, "issue_wavea_activation", lambda **_: pytest.fail("issuance"))
    assert issuer.main(["--manifest", "/fabricated/manifest.json"]) == 1
