"""Public Git fixtures for the finite shared-interpreter rollback profile.

No private cache or payload is copied. Synthetic histories exercise actual Git
mode/type/blob and ancestry checks; archived sources preserve historical pins.
The profile binds exactly nine reviewed paths on the immutable mainc44 parent.
"""
from __future__ import annotations

import ast
import base64
import copy
import hashlib
import json
import subprocess
import zlib
from pathlib import Path

import pytest

from scripts.deploy import verify_final_source_refresh_transition as final
from tests.unit.deploy.test_final_source_refresh_transition import (
    _amend_public_squash, _commit, _digest, _final_report, _git,
    _historical_main00128_tooling_bytes, _old_replay_public_report, _public_blob,
    _public_final_pair,
    normal_squash as normal_squash,
    old_replay_squash as old_replay_squash,
    public_history as public_history,
)
from tests.unit.deploy.test_raw_report_transport_source_profile import (
    _historical_mainf28_tooling_bytes, _raw_report_public_report,
    raw_report_squash as raw_report_squash,
)

_PUBLIC_SHARED_PATHS = (
    "docs/operations/single-vps-wavea-release.md",
    "scripts/deploy/capture_release_preflight.py",
    "scripts/deploy/issue_wavea_activation.py",
    "scripts/deploy/verify_final_source_refresh_transition.py",
    "tests/unit/deploy/fixtures/final_source_refresh_mainc44_tooling.json",
    "tests/unit/deploy/test_final_source_refresh_transition.py",
    "tests/unit/deploy/test_raw_report_transport_source_profile.py",
    "tests/unit/deploy/test_shared_interpreter_rollback_preflight.py",
    "tests/unit/deploy/test_shared_interpreter_source_profile.py",
)
_VERIFIER_PATH = "scripts/deploy/verify_final_source_refresh_transition.py"
_ISSUER_PATH = "scripts/deploy/issue_wavea_activation.py"
_PROFILE = "bilun-shared-interpreter-rollback-mainc44-v1"
_BASE_SHA = "c44aa78c6e0f530ab3d585c32d3daacdc80b3876"
_BASE_TREE = "80c7ab861aa252b01e863c5fd0465c7c8cc09136"
_HISTORICAL_MAINC44_TOOLING = {
    _ISSUER_PATH: (
        "1cc55863aecbbf0f165a05c8dc7ba4dcd4d72b76",
        "de7bb91ac3ef7d7f14cb9ffc34b7b95e15e4244f6665e80fbb090a975d6bcdbf",
        32930,
    ),
    _VERIFIER_PATH: (
        "14467686c20f90843f9f560285f9a99fb6da3cd3",
        "65f10ba9d90fa954788bee7caff2924fe7ffe0e9a04484aa71e1942d6160c555",
        106585,
    ),
    "tests/unit/deploy/test_final_source_refresh_transition.py": (
        "be0fdc19af342759c0d4750ede33ac06572a7b44",
        "3aec881fd5159bff5b4c0e07be7f7c895bc7ac5ed0ca5cc612c0c63362a7b785",
        133295,
    ),
    "tests/unit/deploy/test_raw_report_transport_source_profile.py": (
        "3ae5060e9bd2f23ec9f3bdc5f342d0fe2b39a579",
        "eed75fe23117804561aa01d94e3eceae2fb87f4fa1166ea7f6822e3411d33e4a",
        23781,
    ),
}


def _historical_mainc44_tooling_bytes(path):
    """Decode four exact historical source bodies, with no admission fallback."""
    def unique_fields(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Historical mainc44 fixture repeats a field")
            value[key] = item
        return value

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_fields)
    if (not isinstance(value, dict)
            or set(value) != {"schema_version", "purpose", "source_commit", "source_tree",
                              "encoding", "sources"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["source_commit"] != "c44aa78c6e0f530ab3d585c32d3daacdc80b3876"
            or value["source_tree"] != "80c7ab861aa252b01e863c5fd0465c7c8cc09136"
            or value["encoding"] != "zlib-base64"
            or value["purpose"] != "Historical reviewed tooling source bytes only; this fixture "
                                   "grants no deployment admission to a later head."
            or not isinstance(value["sources"], dict)
            or set(value["sources"]) != set(_HISTORICAL_MAINC44_TOOLING)):
        raise ValueError("Historical mainc44 fixture has unknown provenance or roles")
    decoded = {}
    for source_path, (blob, sha256, size) in _HISTORICAL_MAINC44_TOOLING.items():
        row = value["sources"][source_path]
        if (not isinstance(row, dict)
                or set(row) != {"mode", "type", "blob_sha1", "sha256", "size_bytes",
                                "zlib_base64_chunks"}
                or row["mode"] != "100644" or row["type"] != "blob"
                or row["blob_sha1"] != blob or row["sha256"] != sha256
                or type(row["size_bytes"]) is not int or row["size_bytes"] != size):
            raise ValueError("Historical mainc44 fixture changes pinned source metadata")
        chunks = row["zlib_base64_chunks"]
        if (not isinstance(chunks, list) or not 1 <= len(chunks) <= 2048
                or any(not isinstance(chunk, str) or not 1 <= len(chunk) <= 76 for chunk in chunks)
                or any(len(chunk) != 76 for chunk in chunks[:-1])):
            raise ValueError("Historical mainc44 fixture encoding is malformed")
        try:
            compressed = base64.b64decode("".join(chunks), validate=True)
            decoder = zlib.decompressobj()
            body = decoder.decompress(compressed, size + 1)
        except (ValueError, zlib.error) as error:
            raise ValueError("Historical mainc44 fixture encoding is malformed") from error
        if (len(body) != size or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data
                or hashlib.sha256(body).hexdigest() != sha256
                or _public_blob(body) != ("100644", "blob", blob)):
            raise ValueError("Historical mainc44 fixture source bytes differ from reviewed pins")
        decoded[source_path] = body
    return decoded


def _fixture_path():
    return Path(__file__).parent / "fixtures/final_source_refresh_mainc44_tooling.json"


# Every rejection of a candidate on the mainc44 base must come from this profile, not from
# an accident of the harness or from another profile's branch.
_SHARED_REJECTION = r"(?i)shared interpreter|Squash tooling entry"


def _public_shared_closure(checkout, sha):
    return b"\0".join(row for row in _git(checkout, "ls-tree", "-r", "-z", sha).encode().split(b"\0")
        if row and row.split(b"\t", 1)[1].decode() not in _PUBLIC_SHARED_PATHS)


def _mutate_entry(target, mutation):
    """Change one tree entry the way a reviewer-visible commit could."""
    if mutation == "body":
        target.write_bytes(target.read_bytes() + b"# unreviewed\n")
    elif mutation == "mode":
        target.chmod(0o755)
    else:
        target.unlink()
        if mutation == "type":
            target.symlink_to("/public-unreviewed-target")


@pytest.fixture
def shared_interpreter_squash(raw_report_squash, monkeypatch):
    """A genuine normal squash shares the reviewed tree, not feature identity."""
    case = raw_report_squash
    checkout, base = case["checkout"], case["candidate"]
    tree = _git(checkout, "rev-parse", base + "^{tree}")
    product = _public_shared_closure(checkout, base)
    tooling = {path: ("PUBLIC_SHARED_TOOL = " + repr(path) + "\n").encode()
               for path in _PUBLIC_SHARED_PATHS if path != _VERIFIER_PATH}
    normalized = (b'_REVIEWED_SHARED_INTERPRETER_SELF_SHA256 = "' + b"0" * 64
                  + b'"\nPUBLIC_SHARED = True\n')
    digest = hashlib.sha256(normalized).hexdigest()
    source = normalized.replace(b"0" * 64, digest.encode(), 1)
    sources = {**tooling, _VERIFIER_PATH: source}
    _git(checkout, "checkout", "-q", "-b", "public-shared-feature", base)
    first = checkout / "scripts/deploy/capture_release_preflight.py"
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_bytes(tooling["scripts/deploy/capture_release_preflight.py"])
    _commit(checkout, "public shared interpreter feature intermediate")
    for path, body in sources.items():
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    feature = _commit(checkout, "public reviewed shared interpreter feature tree")
    _git(checkout, "checkout", "-q", "-b", "public-shared-squash", base)
    for path, body in sources.items():
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    candidate = _commit(checkout, "public independent shared interpreter normal squash")
    pins = {path: _public_blob(body) for path, body in tooling.items()}
    for name, value in {
        "SHARED_INTERPRETER_BASE_SHA": base, "SHARED_INTERPRETER_BASE_TREE": tree,
        "_REVIEWED_SHARED_INTERPRETER_PRODUCT_CLOSURE_SHA256": hashlib.sha256(product).hexdigest(),
        "_REVIEWED_SHARED_INTERPRETER_TOOLING": pins,
        "_REVIEWED_SHARED_INTERPRETER_SELF_SHA256": digest,
    }.items():
        monkeypatch.setattr(final, name, value)
    return {**case, "prior_prior": case["prior_base"], "prior_base": case["base"],
            "base": base, "base_tree": tree, "candidate": candidate, "feature": feature,
            "tooling": tooling, "pins": pins, "source": source, "digest": digest,
            "product_closure": product}


def _public_shared_manifest(case):
    return {"profile": _PROFILE, "base_sha": case["base"], "base_tree": case["base_tree"],
        "product_closure_sha256": hashlib.sha256(case["product_closure"]).hexdigest(),
        "files": case["pins"], "verifier": {"path": _VERIFIER_PATH,
        "mode": "100644", "type": "blob", "normalized_sha256": case["digest"]}}


def test_shared_interpreter_normal_squash_binds_exact_nine_paths_and_whole_tree(
        shared_interpreter_squash):
    case = shared_interpreter_squash
    assert final.SHARED_INTERPRETER_TOOLING_PATHS == frozenset(_PUBLIC_SHARED_PATHS)
    assert len(_PUBLIC_SHARED_PATHS) == 9 and list(_PUBLIC_SHARED_PATHS) == sorted(_PUBLIC_SHARED_PATHS)
    assert case["candidate"] != case["feature"]
    assert _git(case["checkout"], "rev-parse", case["candidate"] + "^{tree}") == _git(
        case["checkout"], "rev-parse", case["feature"] + "^{tree}")
    result = final._verify_candidate_history(case["checkout"], case["candidate"])
    assert result == {
        "product_anchor_sha": case["anchor"], "product_anchor_tree": final.PRODUCT_ANCHOR_TREE,
        "integration_seed_sha": None, "integration_seed_tree": None,
        "candidate_sha": case["candidate"], "descendant_commits": [case["candidate"]],
        "authorized_changed_paths": list(_PUBLIC_SHARED_PATHS),
        "product_closure_sha256": hashlib.sha256(case["product_closure"]).hexdigest(),
        "tooling_profile": _PROFILE,
        "tooling_base_sha": case["base"], "tooling_base_tree": case["base_tree"],
        "reviewed_tooling_sha256": _digest(_public_shared_manifest(case)),
    }


def test_shared_interpreter_squash_accepts_unknown_commit_metadata_for_the_same_tree(
        shared_interpreter_squash):
    case = shared_interpreter_squash
    first = final._verify_candidate_history(case["checkout"], case["candidate"])
    replacement = _git(case["checkout"], "commit-tree", case["candidate"] + "^{tree}",
                       "-p", case["base"], "-m", "unknown normal squash metadata")
    assert replacement not in {case["candidate"], case["feature"]}
    _git(case["checkout"], "checkout", "-q", "--detach", replacement)
    assert final._verify_candidate_history(case["checkout"], replacement) == {
        **first, "candidate_sha": replacement, "descendant_commits": [replacement]}


def test_shared_interpreter_fresh_clone_needs_no_discarded_seed_or_feature(
        shared_interpreter_squash, tmp_path):
    case = shared_interpreter_squash
    clone = tmp_path / "fresh-shared-main"
    _git(tmp_path, "clone", "--no-local", "--single-branch", "--branch", "public-shared-squash",
         str(case["checkout"]), str(clone))
    for absent in (case["feature"], case["seed"]):
        with pytest.raises(ValueError):
            final._git(clone, "cat-file", "-e", absent)
    assert final._verify_candidate_history(clone, case["candidate"])["tooling_profile"] == (
        final.SHARED_INTERPRETER_PROFILE)


def test_shared_interpreter_candidate_dispatch_leaves_earlier_profiles_admitted(
        shared_interpreter_squash):
    """Each earlier synthetic squash still lands on its own profile beside the new dispatch."""
    case = shared_interpreter_squash
    checkout = case["checkout"]
    assert final._verify_candidate_history(checkout, case["candidate"])["tooling_profile"] == _PROFILE
    _git(checkout, "checkout", "-q", "--detach", case["base"])
    assert final._verify_candidate_history(checkout, case["base"])["tooling_profile"] == (
        final.RAW_REPORT_PROFILE)
    _git(checkout, "checkout", "-q", "--detach", case["prior_base"])
    assert final._verify_candidate_history(checkout, case["prior_base"])["tooling_profile"] == (
        final.OLD_REPLAY_PROFILE)
    _git(checkout, "checkout", "-q", "--detach", case["prior_prior"])
    assert "tooling_profile" not in final._verify_candidate_history(checkout, case["prior_prior"])


@pytest.mark.parametrize("path", _PUBLIC_SHARED_PATHS)
@pytest.mark.parametrize("mutation", ["body", "mode", "type", "missing"])
def test_shared_interpreter_squash_rejects_every_changed_reviewed_entry(
        shared_interpreter_squash, path, mutation):
    target = shared_interpreter_squash["checkout"] / path
    assert target.exists()
    _mutate_entry(target, mutation)
    candidate = _amend_public_squash(shared_interpreter_squash)
    with pytest.raises(ValueError, match=_SHARED_REJECTION):
        final._verify_candidate_history(shared_interpreter_squash["checkout"], candidate)


@pytest.mark.parametrize("path", [
    "tests/unit/deploy/test_final_source_refresh_transition.py",
    "tests/unit/deploy/test_raw_report_transport_source_profile.py",
])
def test_shared_interpreter_requires_every_reviewed_path_to_actually_change(
        shared_interpreter_squash, monkeypatch, path):
    """The roster is exact in both directions: a pinned path the squash leaves alone is rejected."""
    case = shared_interpreter_squash
    checkout = case["checkout"]
    _git(checkout, "checkout", "-q", case["base"], "--", path)
    assert (checkout / path).read_bytes() != case["tooling"][path]
    candidate = _amend_public_squash(case)
    # The pin follows the untouched base bytes, so only the path-transition check can object.
    monkeypatch.setattr(final, "_REVIEWED_SHARED_INTERPRETER_TOOLING",
                        {**case["pins"], path: _public_blob((checkout / path).read_bytes())})
    with pytest.raises(ValueError, match="exact reviewed path transition"):
        final._verify_candidate_history(checkout, candidate)


_OUTSIDE_PATHS = (
    "data/public_product.json",
    # Frozen prior seed tooling and files that earlier profiles pin but this one does not touch.
    "scripts/deploy/verify_source_refresh_transition.py",
    "tests/unit/deploy/test_source_refresh_transition.py",
    "scripts/deploy/prepare_single_vps_release.py",
    "scripts/deploy/rehearse_wavea_same_port.py",
    "scripts/deploy/verify_candidate_semantics.py",
    "scripts/deploy/verify_private_rehearsal.py",
    "tests/unit/deploy/test_prepare_single_vps_release.py",
    "tests/unit/deploy/test_same_port_rehearsal.py",
    "tests/unit/deploy/test_raw_report_transport.py",
    "tests/unit/deploy/fixtures/final_source_refresh_main00128_tooling.json",
    "tests/unit/deploy/fixtures/final_source_refresh_mainf28_tooling.json",
)


@pytest.mark.parametrize("path", _OUTSIDE_PATHS)
@pytest.mark.parametrize("mutation", ["body", "mode", "type", "missing"])
def test_shared_interpreter_preserves_outside_roster_modes_types_bodies(
        shared_interpreter_squash, path, mutation):
    case = shared_interpreter_squash
    target = case["checkout"] / path
    assert target.exists() and path not in _PUBLIC_SHARED_PATHS
    _mutate_entry(target, mutation)
    candidate = _amend_public_squash(case)
    with pytest.raises(ValueError, match=_SHARED_REJECTION):
        final._verify_candidate_history(case["checkout"], candidate)


@pytest.mark.parametrize("path", [
    "data/extra.json", "scripts/deploy/extra.py", "docs/operations/extra.md",
    "scripts/deploy/capture_release_preflight_extra.py",
    "tests/unit/deploy/test_shared_interpreter_extra.py",
    "tests/unit/deploy/fixtures/final_source_refresh_mainc44_extra.json",
])
def test_shared_interpreter_rejects_extra_and_similarly_named_paths(shared_interpreter_squash, path):
    target = shared_interpreter_squash["checkout"] / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"PUBLIC = True\n")
    candidate = _amend_public_squash(shared_interpreter_squash)
    with pytest.raises(ValueError, match=_SHARED_REJECTION):
        final._verify_candidate_history(shared_interpreter_squash["checkout"], candidate)


def _rechain(case, monkeypatch, level):
    """Rebuild the identical trees on a chain whose `level` link has a foreign parent."""
    checkout = case["checkout"]
    foreign = case["seed"] if level == 0 else case["anchor"]
    links = [case["prior_prior"], case["prior_base"], case["base"], case["candidate"]]
    parent, rebuilt = case["anchor"], []
    for index, sha in enumerate(links):
        parent = _git(checkout, "commit-tree", sha + "^{tree}", "-p",
                      foreign if index == level else parent, "-m", f"rechained link {index}")
        rebuilt.append(parent)
    for name, sha in zip(("OLD_REPLAY_BASE_SHA", "RAW_REPORT_BASE_SHA", "SHARED_INTERPRETER_BASE_SHA"),
                         rebuilt[:3]):
        monkeypatch.setattr(final, name, sha)
    _git(checkout, "checkout", "-q", "--detach", rebuilt[3])
    return rebuilt[3]


@pytest.mark.parametrize("mutation", [
    "wrong_head", "raw_base_parent", "old_replay_base_parent", "two_parents", "future_commit",
    "mutate_revert",
    "base_tree", "raw_base_tree", "old_replay_base_tree", "product_history",
    "chain_c44_parent", "chain_f28_parent", "chain_00128_parent",
    "missing_pin", "extra_pin", "missing_roster_path", "closure_pin",
])
def test_shared_interpreter_rejects_unknown_identity_history_and_roster(
        shared_interpreter_squash, monkeypatch, mutation):
    case = shared_interpreter_squash
    checkout, candidate = case["checkout"], case["candidate"]
    if mutation == "wrong_head":
        candidate = "f" * 40
    elif mutation in {"raw_base_parent", "old_replay_base_parent", "two_parents"}:
        parents = {"raw_base_parent": ["-p", case["prior_base"]],
                   "old_replay_base_parent": ["-p", case["prior_prior"]],
                   "two_parents": ["-p", case["base"], "-p", case["anchor"]]}[mutation]
        candidate = _git(checkout, "commit-tree", candidate + "^{tree}", *parents,
                         "-m", "unreviewed parents")
        _git(checkout, "checkout", "-q", "--detach", candidate)
    elif mutation in {"future_commit", "mutate_revert"}:
        path = checkout / "scripts/deploy/capture_release_preflight.py"
        body = path.read_bytes()
        path.write_bytes(body + b"# future\n")
        candidate = _commit(checkout, "future intermediate")
        if mutation == "mutate_revert":
            path.write_bytes(body)
            candidate = _commit(checkout, "revert preserves unreviewed ancestry")
    elif mutation.startswith("chain_"):
        candidate = _rechain(case, monkeypatch, {"chain_00128_parent": 0, "chain_f28_parent": 1,
                                                   "chain_c44_parent": 2}[mutation])
    elif mutation == "base_tree":
        monkeypatch.setattr(final, "SHARED_INTERPRETER_BASE_TREE", "f" * 40)
    elif mutation == "raw_base_tree":
        monkeypatch.setattr(final, "RAW_REPORT_BASE_TREE", "f" * 40)
    elif mutation == "old_replay_base_tree":
        monkeypatch.setattr(final, "OLD_REPLAY_BASE_TREE", "f" * 40)
    elif mutation == "product_history":
        monkeypatch.setattr(final, "PRODUCT_HISTORY", (*final.PRODUCT_HISTORY[:-1],
            (case["anchor"], final.PRODUCT_ANCHOR_TREE, "f" * 40)))
    elif mutation == "missing_roster_path":
        monkeypatch.setattr(final, "SHARED_INTERPRETER_TOOLING_PATHS",
                            final.SHARED_INTERPRETER_TOOLING_PATHS - {_PUBLIC_SHARED_PATHS[0]})
    elif mutation == "closure_pin":
        monkeypatch.setattr(final, "_REVIEWED_SHARED_INTERPRETER_PRODUCT_CLOSURE_SHA256", "f" * 64)
    else:
        pins = dict(case["pins"])
        if mutation == "missing_pin":
            pins.pop(next(iter(pins)))
        else:
            pins["scripts/deploy/extra.py"] = _public_blob(b"EXTRA\n")
        monkeypatch.setattr(final, "_REVIEWED_SHARED_INTERPRETER_TOOLING", pins)
    reached = mutation.startswith("chain_") or mutation in {
        "base_tree", "raw_base_tree", "old_replay_base_tree", "missing_roster_path", "closure_pin",
        "missing_pin", "extra_pin"}
    with pytest.raises(ValueError, match=_SHARED_REJECTION if reached else None):
        final._verify_candidate_history(checkout, candidate)


@pytest.mark.parametrize("mutation", [
    "missing", "multiple", "malformed", "mismatch", "body", "resealed",
    "other_profile_slot", "indented_slot", "second_slot_in_text",
])
def test_shared_interpreter_self_pin_rejects_changed_slots_and_resealed_bodies(
        shared_interpreter_squash, mutation):
    case = shared_interpreter_squash
    source, digest = case["source"], case["digest"].encode()
    final._verify_shared_interpreter_self_source(source)
    if mutation == "missing":
        source = source.replace(b"_REVIEWED_SHARED_INTERPRETER_SELF_SHA256", b"UNREVIEWED_SLOT")
    elif mutation == "multiple":
        source += source.splitlines(keepends=True)[0]
    elif mutation in {"malformed", "mismatch"}:
        source = source.replace(digest, (b"x" if mutation == "malformed" else b"f") * 64)
    elif mutation == "other_profile_slot":
        source = source.replace(b"_REVIEWED_SHARED_INTERPRETER_SELF_SHA256",
                                b"_REVIEWED_RAW_REPORT_SELF_SHA256")
    elif mutation == "indented_slot":
        source = b" " + source
    elif mutation == "second_slot_in_text":
        source += b'_REVIEWED_SHARED_INTERPRETER_SELF_SHA256 = "' + b"0" * 64 + b'"\n'
    else:
        source += b"# unreviewed source\n"
        if mutation == "resealed":
            source = source.replace(digest, hashlib.sha256(source.replace(digest, b"0" * 64)).hexdigest().encode())
    with pytest.raises(ValueError):
        final._verify_shared_interpreter_self_source(source)


def test_shared_interpreter_squash_rejects_a_resealed_verifier_with_a_matching_slot(
        shared_interpreter_squash):
    """A self-consistent reseal of the verifier is not the reviewed source."""
    case = shared_interpreter_squash
    body = case["source"] + b"# unreviewed source\n"
    digest = case["digest"].encode()
    resealed = body.replace(digest, hashlib.sha256(body.replace(digest, b"0" * 64)).hexdigest().encode())
    assert resealed != case["source"]
    (case["checkout"] / _VERIFIER_PATH).write_bytes(resealed)
    candidate = _amend_public_squash(case)
    with pytest.raises(ValueError, match="self digest has an unknown literal slot"):
        final._verify_candidate_history(case["checkout"], candidate)


def _shared_interpreter_public_report():
    old, new = _public_final_pair()
    report = _final_report({"baseline": old, "candidate": new})
    report["history"].update(
        integration_seed_sha=None, integration_seed_tree=None,
        descendant_commits=[report["candidate_code_sha"]],
        authorized_changed_paths=list(_PUBLIC_SHARED_PATHS),
        product_closure_sha256=final._REVIEWED_SHARED_INTERPRETER_PRODUCT_CLOSURE_SHA256,
        tooling_profile=final.SHARED_INTERPRETER_PROFILE,
        tooling_base_sha=final.SHARED_INTERPRETER_BASE_SHA,
        tooling_base_tree=final.SHARED_INTERPRETER_BASE_TREE,
        reviewed_tooling_sha256=final._shared_interpreter_tooling_digest())
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
        if key not in {"status", "transition_sha256"}})
    return report


def test_shared_interpreter_has_only_existing_closed_twelve_field_addendum():
    report = _shared_interpreter_public_report()
    final.validate_transition_report_contract(report)
    assert set(report["history"]) == {"product_anchor_sha", "product_anchor_tree", "candidate_sha",
        "descendant_commits", "authorized_changed_paths", "integration_seed_sha", "integration_seed_tree",
        "product_closure_sha256", "tooling_profile", "tooling_base_sha", "tooling_base_tree",
        "reviewed_tooling_sha256"}
    assert report["history"]["tooling_profile"] == _PROFILE
    assert report["source_intent"]["followup"]["clinical_eligibility_complete"] is False
    assert report["source_intent"]["copay"]["payment_permission_added"] is False
    assert (report["source_projected_table_count"], report["strict_table_count"]) == (19, 13)


@pytest.mark.parametrize("mutation", [
    "profile", "base", "base_tree", "product_anchor", "product_tree", "closure", "tooling_digest",
    "candidate", "extra_descendant", "old_seed", "seed_sha_only", "seed_tree_only", "false_seed",
    "missing_path", "extra_path", "duplicate_path", "unsorted_paths", "missing_key", "extra_key",
    "wrong_verifier", "wrong_replay", "raw_report_paths", "old_replay_paths", "raw_base", "previous_closure", "previous_digest",
])
def test_shared_interpreter_contract_rejects_resealed_authority(mutation):
    report = _shared_interpreter_public_report()
    final.validate_transition_report_contract(report)
    history = report["history"]
    field = {"profile": "tooling_profile", "base": "tooling_base_sha", "base_tree": "tooling_base_tree",
        "product_anchor": "product_anchor_sha", "product_tree": "product_anchor_tree",
        "closure": "product_closure_sha256", "tooling_digest": "reviewed_tooling_sha256",
        "candidate": "candidate_sha"}.get(mutation)
    if field:
        history[field] = "f" * (64 if mutation in {"closure", "tooling_digest"} else 40)
    elif mutation == "extra_descendant":
        history["descendant_commits"].append("f" * 40)
    elif mutation in {"old_seed", "seed_sha_only", "false_seed"}:
        history["integration_seed_sha"] = False if mutation == "false_seed" else final.INTEGRATION_SEED_SHA
        if mutation == "old_seed":
            history["integration_seed_tree"] = final.INTEGRATION_SEED_TREE
    elif mutation == "seed_tree_only":
        history["integration_seed_tree"] = final.INTEGRATION_SEED_TREE
    elif mutation in {"missing_path", "extra_path", "duplicate_path", "unsorted_paths"}:
        paths = history["authorized_changed_paths"]
        if mutation == "missing_path":
            paths.pop()
        elif mutation == "extra_path":
            paths.append("scripts/deploy/extra.py")
            paths.sort()
        elif mutation == "duplicate_path":
            paths.append(paths[-1])
        else:
            paths.reverse()
    elif mutation == "missing_key":
        history.pop("tooling_base_tree")
    elif mutation == "extra_key":
        history["tooling_permission"] = True
    elif mutation == "wrong_verifier":
        report["verifier"]["verifier_sha"] = "f" * 40
    elif mutation == "raw_report_paths":
        history["authorized_changed_paths"] = sorted(final.RAW_REPORT_TOOLING_PATHS)
    elif mutation == "old_replay_paths":
        history["authorized_changed_paths"] = sorted(final.OLD_REPLAY_TOOLING_PATHS)
    elif mutation == "raw_base":
        history["tooling_base_sha"] = final.RAW_REPORT_BASE_SHA
        history["tooling_base_tree"] = final.RAW_REPORT_BASE_TREE
    elif mutation == "previous_closure":
        history["product_closure_sha256"] = final._REVIEWED_RAW_REPORT_PRODUCT_CLOSURE_SHA256
    elif mutation == "previous_digest":
        history["reviewed_tooling_sha256"] = final._raw_report_tooling_digest()
    else:
        report["replay_checkouts"]["candidate"]["code_sha"] = "f" * 40
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
        if key not in {"status", "transition_sha256"}})
    with pytest.raises(ValueError):
        final.validate_transition_report_contract(report)


@pytest.mark.parametrize("mutation", ["raw_profile", "old_replay_profile", "unprofiled"])
def test_earlier_profiles_cannot_borrow_the_shared_interpreter_roster_by_resealing(mutation):
    """Pairing an earlier profile's identity with this roster or closure is rejected."""
    if mutation == "raw_profile":
        report = _raw_report_public_report()
        report["history"]["authorized_changed_paths"] = list(_PUBLIC_SHARED_PATHS)
    elif mutation == "old_replay_profile":
        report = _old_replay_public_report()
        report["history"]["authorized_changed_paths"] = list(_PUBLIC_SHARED_PATHS)
    else:
        old, new = _public_final_pair()
        report = _final_report({"baseline": old, "candidate": new})
        report["history"]["authorized_changed_paths"] = list(_PUBLIC_SHARED_PATHS)
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
        if key not in {"status", "transition_sha256"}})
    with pytest.raises(ValueError):
        final.validate_transition_report_contract(report)


def test_earlier_profile_reports_stay_valid_beside_the_new_profile():
    final.validate_transition_report_contract(_old_replay_public_report())
    final.validate_transition_report_contract(_raw_report_public_report())
    final.validate_transition_report_contract(_shared_interpreter_public_report())


def test_shared_interpreter_published_pins_match_current_reviewed_bytes():
    checkout = Path(final.__file__).resolve().parents[2]
    assert final.SHARED_INTERPRETER_PROFILE == _PROFILE
    assert final.SHARED_INTERPRETER_BASE_SHA == _BASE_SHA
    assert final.SHARED_INTERPRETER_BASE_TREE == _BASE_TREE
    assert final.SHARED_INTERPRETER_TOOLING_PATHS == frozenset(_PUBLIC_SHARED_PATHS)
    assert set(final._REVIEWED_SHARED_INTERPRETER_TOOLING) == set(_PUBLIC_SHARED_PATHS) - {_VERIFIER_PATH}
    for path, expected in final._REVIEWED_SHARED_INTERPRETER_TOOLING.items():
        assert _public_blob((checkout / path).read_bytes()) == expected
    final._verify_shared_interpreter_self_source(Path(final.__file__).read_bytes())


@pytest.mark.parametrize("historical_digest", [
    final._REVIEWED_SQUASH_SELF_SHA256, final._REVIEWED_OLD_REPLAY_SELF_SHA256,
    final._REVIEWED_RAW_REPORT_SELF_SHA256,
])
def test_shared_interpreter_self_pin_keeps_all_three_historical_literal_slots_bound(historical_digest):
    source = Path(final.__file__).read_bytes()
    assert historical_digest.encode() in source
    with pytest.raises(ValueError):
        final._verify_shared_interpreter_self_source(source.replace(historical_digest.encode(), b"f" * 64, 1))


def _top_level_items(source):
    items = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            items[(type(node).__name__, node.name)] = node
        elif isinstance(node, ast.Assign):
            items[("Assign", ", ".join(ast.unparse(target) for target in node.targets))] = node
        elif isinstance(node, ast.AnnAssign):
            items[("AnnAssign", ast.unparse(node.target))] = node
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            items[(type(node).__name__, ast.unparse(node))] = node
    return items


def _without_new_profile(function):
    function = copy.deepcopy(function)
    kept = [statement for statement in function.body
            if "SHARED_INTERPRETER" not in ast.unparse(statement)]
    assert len(function.body) - len(kept) == 1
    function.body = kept
    return ast.dump(function)


def test_new_profile_only_adds_names_and_one_branch_to_two_dispatch_functions():
    """Earlier constants and functions stay byte-for-byte equal in meaning to mainc44."""
    old = _top_level_items(_historical_mainc44_tooling_bytes(_fixture_path())[_VERIFIER_PATH])
    new = _top_level_items(Path(final.__file__).read_bytes())
    changed = {key for key in old if key not in new or ast.dump(new[key]) != ast.dump(old[key])}
    assert changed == {("FunctionDef", "_verify_candidate_history"),
                       ("FunctionDef", "_validate_transition_history")}
    for name in ("_verify_candidate_history", "_validate_transition_history"):
        assert _without_new_profile(new[("FunctionDef", name)]) == ast.dump(old[("FunctionDef", name)])
    assert set(new) - set(old) == {
        ("Assign", "SHARED_INTERPRETER_PROFILE"), ("Assign", "SHARED_INTERPRETER_BASE_SHA"),
        ("Assign", "SHARED_INTERPRETER_BASE_TREE"), ("Assign", "SHARED_INTERPRETER_TOOLING_PATHS"),
        ("Assign", "_REVIEWED_SHARED_INTERPRETER_PRODUCT_CLOSURE_SHA256"),
        ("Assign", "_REVIEWED_SHARED_INTERPRETER_TOOLING"),
        ("Assign", "_REVIEWED_SHARED_INTERPRETER_SELF_SHA256"),
        ("Assign", "_SHARED_INTERPRETER_SELF_SLOT"),
        ("FunctionDef", "_shared_interpreter_product_closure"),
        ("FunctionDef", "_verify_shared_interpreter_self_source"),
        ("FunctionDef", "_shared_interpreter_tooling_digest"),
        ("FunctionDef", "_verify_shared_interpreter_squash_history"),
    }


def test_earlier_profiles_stay_bound_to_their_own_frozen_verifier_bytes():
    """Each earlier self digest still verifies the archived verifier bytes it reviewed."""
    main00128 = _historical_main00128_tooling_bytes(
        Path(__file__).parent / "fixtures/final_source_refresh_main00128_tooling.json")
    mainf28 = _historical_mainf28_tooling_bytes(
        Path(__file__).parent / "fixtures/final_source_refresh_mainf28_tooling.json")
    mainc44 = _historical_mainc44_tooling_bytes(_fixture_path())
    final._verify_squash_self_source(main00128[_VERIFIER_PATH])
    final._verify_old_replay_self_source(mainf28[_VERIFIER_PATH])
    final._verify_raw_report_self_source(mainc44[_VERIFIER_PATH])
    # Each earlier verifier rejects every later source, so none inherits this roster.
    current = Path(final.__file__).read_bytes()
    for verify in (final._verify_squash_self_source, final._verify_old_replay_self_source,
                   final._verify_raw_report_self_source):
        with pytest.raises(ValueError):
            verify(current)


def test_mainc44_archive_preserves_earlier_pins_and_self_source():
    sources = _historical_mainc44_tooling_bytes(_fixture_path())
    assert set(sources) < final.SHARED_INTERPRETER_TOOLING_PATHS
    assert _public_blob(sources[_ISSUER_PATH]) == final._REVIEWED_SQUASH_TOOLING[_ISSUER_PATH]
    for path in set(sources) - {_VERIFIER_PATH, _ISSUER_PATH}:
        assert _public_blob(sources[path]) == final._REVIEWED_RAW_REPORT_TOOLING[path]
    final._verify_raw_report_self_source(sources[_VERIFIER_PATH])
    assert final.SHARED_INTERPRETER_TOOLING_PATHS - final.RAW_REPORT_TOOLING_PATHS == {
        "docs/operations/single-vps-wavea-release.md",
        "scripts/deploy/capture_release_preflight.py",
        "scripts/deploy/issue_wavea_activation.py",
        "tests/unit/deploy/fixtures/final_source_refresh_mainc44_tooling.json",
        "tests/unit/deploy/test_shared_interpreter_rollback_preflight.py",
        "tests/unit/deploy/test_shared_interpreter_source_profile.py"}


def _real_history_has(sha):
    root = Path(final.__file__).resolve().parents[2]
    return subprocess.run(["git", "-C", str(root), "cat-file", "-e", sha + "^{tree}"],
                          capture_output=True).returncode == 0


@pytest.mark.skipif(not _real_history_has(_BASE_SHA),
                    reason="needs the full mainc44 history; shallow CI clones cannot prove this")
def test_real_mainc44_history_matches_the_closure_pin_and_the_archived_bytes():
    """Only runs where the real c44aa78c object exists; recomputes the pins from Git itself."""
    root = Path(final.__file__).resolve().parents[2]
    assert _git(root, "rev-parse", _BASE_SHA + "^{tree}") == final.SHARED_INTERPRETER_BASE_TREE
    assert _git(root, "show", "-s", "--format=%P", _BASE_SHA) == final.RAW_REPORT_BASE_SHA
    assert hashlib.sha256(final._shared_interpreter_product_closure(root, _BASE_SHA)).hexdigest() == (
        final._REVIEWED_SHARED_INTERPRETER_PRODUCT_CLOSURE_SHA256)
    for path, body in _historical_mainc44_tooling_bytes(_fixture_path()).items():
        assert subprocess.check_output(["git", "-C", str(root), "show", f"{_BASE_SHA}:{path}"]) == body


@pytest.mark.parametrize("source_path", tuple(_HISTORICAL_MAINC44_TOOLING))
@pytest.mark.parametrize("mutation", [
    "body", "rehashed_body", "mode", "type", "missing_role", "extra_role", "commit", "tree",
    "extra_field", "extra_row_field", "schema_bool", "size_bool", "missing_chunks", "trailing_stream",
])
def test_mainc44_archive_rejects_forged_or_rehashed_sources(tmp_path, source_path, mutation):
    value = json.loads(_fixture_path().read_text())
    row = value["sources"][source_path]
    if mutation in {"body", "rehashed_body", "trailing_stream"}:
        original = base64.b64decode("".join(row["zlib_base64_chunks"]))
        body = zlib.decompress(original) + b"# unreviewed\n"
        compressed = original + zlib.compress(b"trailing") if mutation == "trailing_stream" else zlib.compress(body)
        encoded = base64.b64encode(compressed).decode()
        row["zlib_base64_chunks"] = [encoded[i:i + 76] for i in range(0, len(encoded), 76)]
        if mutation == "rehashed_body":
            row.update(size_bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), blob_sha1=_public_blob(body)[2])
    elif mutation in {"mode", "type"}:
        row[mutation] = "100755" if mutation == "mode" else "tree"
    elif mutation == "missing_role":
        del value["sources"][source_path]
    elif mutation == "extra_role":
        value["sources"]["scripts/deploy/extra.py"] = copy.deepcopy(row)
    elif mutation in {"commit", "tree"}:
        value["source_" + mutation] = "f" * 40
    elif mutation == "extra_field":
        value["admit_future_heads"] = True
    elif mutation == "extra_row_field":
        row["admit_future_heads"] = True
    elif mutation == "schema_bool":
        value["schema_version"] = True
    elif mutation == "size_bool":
        row["size_bytes"] = True
    else:
        row["zlib_base64_chunks"] = []
    path = tmp_path / "forged-mainc44.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        _historical_mainc44_tooling_bytes(path)


def test_mainc44_archive_rejects_duplicate_fields(tmp_path):
    value = _fixture_path().read_text()
    path = tmp_path / "duplicate-mainc44.json"
    path.write_text(value.replace('"schema_version": 1,', '"schema_version": 1, "schema_version": 1,', 1))
    with pytest.raises(ValueError, match="repeats a field"):
        _historical_mainc44_tooling_bytes(path)
