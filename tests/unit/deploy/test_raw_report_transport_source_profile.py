"""Public Git fixtures for the finite raw bill transport repair profile.

No private cache or payload is copied. Synthetic histories exercise actual Git
mode/type/blob and ancestry checks; archived sources preserve historical pins.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import zlib
from pathlib import Path

import pytest

from scripts.deploy import verify_final_source_refresh_transition as final
from tests.unit.deploy.test_final_source_refresh_transition import (
    _amend_public_squash, _commit, _digest, _final_report, _git, _public_blob,
    _public_final_pair,
    normal_squash as normal_squash,
    old_replay_squash as old_replay_squash,
    public_history as public_history,
)

_PUBLIC_RAW_PATHS = (
    "scripts/deploy/rehearse_wavea_same_port.py",
    "scripts/deploy/verify_final_source_refresh_transition.py",
    "tests/unit/deploy/fixtures/final_source_refresh_mainf28_tooling.json",
    "tests/unit/deploy/test_final_source_refresh_transition.py",
    "tests/unit/deploy/test_raw_report_transport.py",
    "tests/unit/deploy/test_raw_report_transport_source_profile.py",
)
_VERIFIER_PATH = "scripts/deploy/verify_final_source_refresh_transition.py"
_HISTORICAL_MAINF28_TOOLING = {
    "scripts/deploy/rehearse_wavea_same_port.py": (
        "315aee150f3eb0aeeb696357451e85351a29f79e",
        "920f5b4147199b5f6773fc671419638f33792143be424dd7bdc14a6a161fec44",
        55814,
    ),
    _VERIFIER_PATH: (
        "dfdb49b1944eb5eeb6d5a58fcff03a0a8561a862",
        "845513a6d09bdab5b7de7602646de8c7dc8bbd6593b5a490ee73f45c5ddccc2e",
        99256,
    ),
    "tests/unit/deploy/test_final_source_refresh_transition.py": (
        "b10d84acde9b1845c808d027cf0f02a4a0d19bba",
        "d2b6313d7f3727df3822505e8e40c7a9f3d975161627977e264c98c6540b7608",
        132642,
    ),
}


def _historical_mainf28_tooling_bytes(path):
    """Decode three exact historical source bodies, with no admission fallback."""
    def unique_fields(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Historical mainf28 fixture repeats a field")
            value[key] = item
        return value

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_fields)
    if (not isinstance(value, dict)
            or set(value) != {"schema_version", "purpose", "source_commit", "source_tree",
                              "encoding", "sources"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["source_commit"] != "f28af00ffe6237fe4b6c01d98d15360caa4c6008"
            or value["source_tree"] != "d76b6656730f74a58554558f7a8012fafd8190ff"
            or value["encoding"] != "zlib-base64"
            or value["purpose"] != "Historical reviewed tooling source bytes only; this fixture "
                                   "grants no deployment admission to a later head."
            or not isinstance(value["sources"], dict)
            or set(value["sources"]) != set(_HISTORICAL_MAINF28_TOOLING)):
        raise ValueError("Historical mainf28 fixture has unknown provenance or roles")
    decoded = {}
    for source_path, (blob, sha256, size) in _HISTORICAL_MAINF28_TOOLING.items():
        row = value["sources"][source_path]
        if (not isinstance(row, dict)
                or set(row) != {"mode", "type", "blob_sha1", "sha256", "size_bytes",
                                "zlib_base64_chunks"}
                or row["mode"] != "100644" or row["type"] != "blob"
                or row["blob_sha1"] != blob or row["sha256"] != sha256
                or type(row["size_bytes"]) is not int or row["size_bytes"] != size):
            raise ValueError("Historical mainf28 fixture changes pinned source metadata")
        chunks = row["zlib_base64_chunks"]
        if (not isinstance(chunks, list) or not 1 <= len(chunks) <= 2048
                or any(not isinstance(chunk, str) or not 1 <= len(chunk) <= 76 for chunk in chunks)
                or any(len(chunk) != 76 for chunk in chunks[:-1])):
            raise ValueError("Historical mainf28 fixture encoding is malformed")
        try:
            compressed = base64.b64decode("".join(chunks), validate=True)
            decoder = zlib.decompressobj()
            body = decoder.decompress(compressed, size + 1)
        except (ValueError, zlib.error) as error:
            raise ValueError("Historical mainf28 fixture encoding is malformed") from error
        if (len(body) != size or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data
                or hashlib.sha256(body).hexdigest() != sha256
                or _public_blob(body) != ("100644", "blob", blob)):
            raise ValueError("Historical mainf28 fixture source bytes differ from reviewed pins")
        decoded[source_path] = body
    return decoded


def _fixture_path():
    return Path(__file__).parent / "fixtures/final_source_refresh_mainf28_tooling.json"


def _public_raw_closure(checkout, sha):
    return b"\0".join(row for row in _git(checkout, "ls-tree", "-r", "-z", sha).encode().split(b"\0")
        if row and row.split(b"\t", 1)[1].decode() not in _PUBLIC_RAW_PATHS)


@pytest.fixture
def raw_report_squash(old_replay_squash, monkeypatch):
    """A genuine normal squash shares the reviewed tree, not feature identity."""
    case = old_replay_squash
    checkout, base = case["checkout"], case["candidate"]
    tree = _git(checkout, "rev-parse", base + "^{tree}")
    product = _public_raw_closure(checkout, base)
    tooling = {path: ("PUBLIC_RAW_TOOL = " + repr(path) + "\n").encode()
               for path in _PUBLIC_RAW_PATHS if path != _VERIFIER_PATH}
    normalized = b'_REVIEWED_RAW_REPORT_SELF_SHA256 = "' + b"0" * 64 + b'"\nPUBLIC_RAW = True\n'
    digest = hashlib.sha256(normalized).hexdigest()
    source = normalized.replace(b"0" * 64, digest.encode(), 1)
    sources = {**tooling, _VERIFIER_PATH: source}
    _git(checkout, "checkout", "-q", "-b", "public-raw-feature", base)
    (checkout / "scripts/deploy/rehearse_wavea_same_port.py").write_bytes(tooling[
        "scripts/deploy/rehearse_wavea_same_port.py"])
    _commit(checkout, "public raw transport feature intermediate")
    for path, body in sources.items():
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    feature = _commit(checkout, "public reviewed raw transport feature tree")
    _git(checkout, "checkout", "-q", "-b", "public-raw-squash", base)
    for path, body in sources.items():
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    candidate = _commit(checkout, "public independent raw transport normal squash")
    pins = {path: _public_blob(body) for path, body in tooling.items()}
    for name, value in {
        "RAW_REPORT_BASE_SHA": base, "RAW_REPORT_BASE_TREE": tree,
        "_REVIEWED_RAW_REPORT_PRODUCT_CLOSURE_SHA256": hashlib.sha256(product).hexdigest(),
        "_REVIEWED_RAW_REPORT_TOOLING": pins, "_REVIEWED_RAW_REPORT_SELF_SHA256": digest,
    }.items():
        monkeypatch.setattr(final, name, value)
    return {**case, "prior_base": case["base"], "base": base, "base_tree": tree,
            "candidate": candidate, "feature": feature, "tooling": tooling,
            "pins": pins, "source": source, "digest": digest, "product_closure": product}


def _public_raw_manifest(case):
    return {"profile": "bilun-raw-report-transport-mainf28-v1", "base_sha": case["base"],
        "base_tree": case["base_tree"],
        "product_closure_sha256": hashlib.sha256(case["product_closure"]).hexdigest(),
        "files": case["pins"], "verifier": {"path": _VERIFIER_PATH,
        "mode": "100644", "type": "blob", "normalized_sha256": case["digest"]}}


def test_raw_report_normal_squash_binds_exact_six_paths_and_whole_tree(raw_report_squash):
    case = raw_report_squash
    assert final.RAW_REPORT_TOOLING_PATHS == frozenset(_PUBLIC_RAW_PATHS)
    assert case["candidate"] != case["feature"]
    assert _git(case["checkout"], "rev-parse", case["candidate"] + "^{tree}") == _git(
        case["checkout"], "rev-parse", case["feature"] + "^{tree}")
    result = final._verify_candidate_history(case["checkout"], case["candidate"])
    assert result == {
        "product_anchor_sha": case["anchor"], "product_anchor_tree": final.PRODUCT_ANCHOR_TREE,
        "integration_seed_sha": None, "integration_seed_tree": None,
        "candidate_sha": case["candidate"], "descendant_commits": [case["candidate"]],
        "authorized_changed_paths": list(_PUBLIC_RAW_PATHS),
        "product_closure_sha256": hashlib.sha256(case["product_closure"]).hexdigest(),
        "tooling_profile": "bilun-raw-report-transport-mainf28-v1",
        "tooling_base_sha": case["base"], "tooling_base_tree": case["base_tree"],
        "reviewed_tooling_sha256": _digest(_public_raw_manifest(case)),
    }


def test_raw_report_squash_accepts_unknown_commit_metadata_for_the_same_tree(raw_report_squash):
    case = raw_report_squash
    first = final._verify_candidate_history(case["checkout"], case["candidate"])
    replacement = _git(case["checkout"], "commit-tree", case["candidate"] + "^{tree}",
                       "-p", case["base"], "-m", "unknown normal squash metadata")
    assert replacement not in {case["candidate"], case["feature"]}
    _git(case["checkout"], "checkout", "-q", "--detach", replacement)
    assert final._verify_candidate_history(case["checkout"], replacement) == {
        **first, "candidate_sha": replacement, "descendant_commits": [replacement]}


def test_raw_report_fresh_clone_needs_no_discarded_seed_or_feature(raw_report_squash, tmp_path):
    case = raw_report_squash
    clone = tmp_path / "fresh-raw-main"
    _git(tmp_path, "clone", "--no-local", "--single-branch", "--branch", "public-raw-squash",
         str(case["checkout"]), str(clone))
    for absent in (case["feature"], case["seed"]):
        with pytest.raises(ValueError):
            final._git(clone, "cat-file", "-e", absent)
    assert final._verify_candidate_history(clone, case["candidate"])["tooling_profile"] == final.RAW_REPORT_PROFILE


@pytest.mark.parametrize("path", _PUBLIC_RAW_PATHS)
@pytest.mark.parametrize("mutation", ["body", "mode", "type", "missing"])
def test_raw_report_squash_rejects_every_changed_reviewed_entry(raw_report_squash, path, mutation):
    target = raw_report_squash["checkout"] / path
    if mutation == "body":
        target.write_bytes(target.read_bytes() + b"# unreviewed\n")
    elif mutation == "mode":
        target.chmod(0o755)
    else:
        target.unlink()
        if mutation == "type":
            target.symlink_to("/public-unreviewed-target")
    candidate = _amend_public_squash(raw_report_squash)
    with pytest.raises(ValueError):
        final._verify_candidate_history(raw_report_squash["checkout"], candidate)


@pytest.mark.parametrize("path", ["data/public.json", "scripts/deploy/verify_source_refresh_transition.py"])
@pytest.mark.parametrize("mutation", ["body", "mode", "type", "missing"])
def test_raw_report_preserves_outside_roster_modes_types_bodies(raw_report_squash, path, mutation):
    case = raw_report_squash
    target = case["product"] if path == "data/public.json" else case["checkout"] / path
    if mutation == "body":
        target.write_bytes(target.read_bytes() + b"# unreviewed\n")
    elif mutation == "mode":
        target.chmod(0o755)
    else:
        target.unlink()
        if mutation == "type":
            target.symlink_to("/public-unreviewed-target")
    candidate = _amend_public_squash(case)
    with pytest.raises(ValueError):
        final._verify_candidate_history(case["checkout"], candidate)


@pytest.mark.parametrize("path", [
    "data/extra.json", "scripts/deploy/extra.py", "tests/unit/deploy/test_raw_report_extra.py",
    "tests/unit/deploy/fixtures/final_source_refresh_mainf28_extra.json",
])
def test_raw_report_rejects_extra_and_similarly_named_paths(raw_report_squash, path):
    target = raw_report_squash["checkout"] / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"PUBLIC = True\n")
    candidate = _amend_public_squash(raw_report_squash)
    with pytest.raises(ValueError):
        final._verify_candidate_history(raw_report_squash["checkout"], candidate)


@pytest.mark.parametrize("mutation", [
    "wrong_head", "wrong_parent", "two_parents", "future_commit", "mutate_revert",
    "base_tree", "base_parent", "prior_base_tree", "product_history", "missing_pin", "extra_pin",
])
def test_raw_report_rejects_unknown_identity_history_and_roster(raw_report_squash, monkeypatch, mutation):
    case = raw_report_squash
    checkout, candidate = case["checkout"], case["candidate"]
    if mutation == "wrong_head":
        candidate = "f" * 40
    elif mutation in {"wrong_parent", "two_parents"}:
        parents = ["-p", case["prior_base"]] if mutation == "wrong_parent" else [
            "-p", case["base"], "-p", case["anchor"]]
        candidate = _git(checkout, "commit-tree", candidate + "^{tree}", *parents, "-m", "unreviewed parents")
        _git(checkout, "checkout", "-q", "--detach", candidate)
    elif mutation in {"future_commit", "mutate_revert"}:
        path = checkout / "scripts/deploy/rehearse_wavea_same_port.py"
        body = path.read_bytes()
        path.write_bytes(body + b"# future\n")
        candidate = _commit(checkout, "future intermediate")
        if mutation == "mutate_revert":
            path.write_bytes(body)
            candidate = _commit(checkout, "revert preserves unreviewed ancestry")
    elif mutation == "base_parent":
        base = _git(checkout, "commit-tree", case["base"] + "^{tree}", "-p", case["anchor"], "-m", "wrong base parent")
        monkeypatch.setattr(final, "RAW_REPORT_BASE_SHA", base)
        candidate = _git(checkout, "commit-tree", candidate + "^{tree}", "-p", base, "-m", "wrong base ancestry")
        _git(checkout, "checkout", "-q", "--detach", candidate)
    elif mutation == "base_tree":
        monkeypatch.setattr(final, "RAW_REPORT_BASE_TREE", "f" * 40)
    elif mutation == "prior_base_tree":
        monkeypatch.setattr(final, "OLD_REPLAY_BASE_TREE", "f" * 40)
    elif mutation == "product_history":
        monkeypatch.setattr(final, "PRODUCT_HISTORY", (*final.PRODUCT_HISTORY[:-1],
            (case["anchor"], final.PRODUCT_ANCHOR_TREE, "f" * 40)))
    else:
        pins = dict(case["pins"])
        if mutation == "missing_pin":
            pins.pop(next(iter(pins)))
        else:
            pins["scripts/deploy/extra.py"] = _public_blob(b"EXTRA\n")
        monkeypatch.setattr(final, "_REVIEWED_RAW_REPORT_TOOLING", pins)
    with pytest.raises(ValueError):
        final._verify_candidate_history(checkout, candidate)


@pytest.mark.parametrize("mutation", ["missing", "multiple", "malformed", "mismatch", "body", "resealed"])
def test_raw_report_self_pin_rejects_changed_slots_and_resealed_bodies(raw_report_squash, mutation):
    case = raw_report_squash
    source, digest = case["source"], case["digest"].encode()
    if mutation == "missing":
        source = source.replace(b"_REVIEWED_RAW_REPORT_SELF_SHA256", b"UNREVIEWED_SLOT")
    elif mutation == "multiple":
        source += source.splitlines(keepends=True)[0]
    elif mutation in {"malformed", "mismatch"}:
        source = source.replace(digest, (b"x" if mutation == "malformed" else b"f") * 64)
    else:
        source += b"# unreviewed source\n"
        if mutation == "resealed":
            source = source.replace(digest, hashlib.sha256(source.replace(digest, b"0" * 64)).hexdigest().encode())
    with pytest.raises(ValueError):
        final._verify_raw_report_self_source(source)


def _raw_report_public_report():
    old, new = _public_final_pair()
    report = _final_report({"baseline": old, "candidate": new})
    report["history"].update(
        integration_seed_sha=None, integration_seed_tree=None,
        descendant_commits=[report["candidate_code_sha"]],
        authorized_changed_paths=list(_PUBLIC_RAW_PATHS),
        product_closure_sha256=final._REVIEWED_RAW_REPORT_PRODUCT_CLOSURE_SHA256,
        tooling_profile=final.RAW_REPORT_PROFILE, tooling_base_sha=final.RAW_REPORT_BASE_SHA,
        tooling_base_tree=final.RAW_REPORT_BASE_TREE,
        reviewed_tooling_sha256=final._raw_report_tooling_digest())
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
        if key not in {"status", "transition_sha256"}})
    return report


def test_raw_report_has_only_existing_closed_twelve_field_addendum():
    report = _raw_report_public_report()
    final.validate_transition_report_contract(report)
    assert set(report["history"]) == {"product_anchor_sha", "product_anchor_tree", "candidate_sha",
        "descendant_commits", "authorized_changed_paths", "integration_seed_sha", "integration_seed_tree",
        "product_closure_sha256", "tooling_profile", "tooling_base_sha", "tooling_base_tree",
        "reviewed_tooling_sha256"}
    assert report["source_intent"]["followup"]["clinical_eligibility_complete"] is False
    assert report["source_intent"]["copay"]["payment_permission_added"] is False
    assert (report["source_projected_table_count"], report["strict_table_count"]) == (19, 13)


@pytest.mark.parametrize("mutation", [
    "profile", "base", "base_tree", "product_anchor", "product_tree", "closure", "tooling_digest",
    "candidate", "extra_descendant", "old_seed", "false_seed", "missing_path", "extra_path",
    "duplicate_path", "unsorted_paths", "missing_key", "extra_key", "wrong_verifier", "wrong_replay",
])
def test_raw_report_contract_rejects_resealed_authority(mutation):
    report = _raw_report_public_report()
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
    elif mutation in {"old_seed", "false_seed"}:
        history["integration_seed_sha"] = False if mutation == "false_seed" else final.INTEGRATION_SEED_SHA
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
    else:
        report["replay_checkouts"]["candidate"]["code_sha"] = "f" * 40
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
        if key not in {"status", "transition_sha256"}})
    with pytest.raises(ValueError):
        final.validate_transition_report_contract(report)


def test_raw_report_published_pins_match_current_reviewed_bytes():
    from tests.unit.deploy.test_shared_interpreter_source_profile import _historical_mainc44_tooling_bytes

    checkout = Path(final.__file__).resolve().parents[2]
    historical = _historical_mainc44_tooling_bytes(
        Path(__file__).parent / "fixtures/final_source_refresh_mainc44_tooling.json")
    assert final.RAW_REPORT_BASE_SHA == "f28af00ffe6237fe4b6c01d98d15360caa4c6008"
    assert final.RAW_REPORT_BASE_TREE == "d76b6656730f74a58554558f7a8012fafd8190ff"
    assert final.RAW_REPORT_TOOLING_PATHS == frozenset(_PUBLIC_RAW_PATHS)
    assert set(final._REVIEWED_RAW_REPORT_TOOLING) == set(_PUBLIC_RAW_PATHS) - {_VERIFIER_PATH}
    for path, expected in final._REVIEWED_RAW_REPORT_TOOLING.items():
        body = historical[path] if path in historical else (checkout / path).read_bytes()
        assert _public_blob(body) == expected
    final._verify_raw_report_self_source(historical[_VERIFIER_PATH])


@pytest.mark.parametrize("historical_digest", [
    final._REVIEWED_SQUASH_SELF_SHA256, final._REVIEWED_OLD_REPLAY_SELF_SHA256,
])
def test_raw_report_self_pin_keeps_both_historical_literal_slots_bound(historical_digest):
    from tests.unit.deploy.test_shared_interpreter_source_profile import _historical_mainc44_tooling_bytes

    source = _historical_mainc44_tooling_bytes(
        Path(__file__).parent / "fixtures/final_source_refresh_mainc44_tooling.json")[_VERIFIER_PATH]
    assert historical_digest.encode() in source
    with pytest.raises(ValueError):
        final._verify_raw_report_self_source(source.replace(historical_digest.encode(), b"f" * 64, 1))


def test_mainf28_archive_preserves_old_replay_pins_and_self_source():
    sources = _historical_mainf28_tooling_bytes(_fixture_path())
    for path in set(sources) - {_VERIFIER_PATH}:
        assert _public_blob(sources[path]) == final._REVIEWED_OLD_REPLAY_TOOLING[path]
    final._verify_old_replay_self_source(sources[_VERIFIER_PATH])
    assert final.RAW_REPORT_TOOLING_PATHS - final.OLD_REPLAY_TOOLING_PATHS == {
        "tests/unit/deploy/fixtures/final_source_refresh_mainf28_tooling.json",
        "tests/unit/deploy/test_raw_report_transport.py",
        "tests/unit/deploy/test_raw_report_transport_source_profile.py"}


@pytest.mark.parametrize("source_path", tuple(_HISTORICAL_MAINF28_TOOLING))
@pytest.mark.parametrize("mutation", [
    "body", "rehashed_body", "mode", "type", "missing_role", "extra_role", "commit", "tree",
    "extra_field", "extra_row_field", "schema_bool", "size_bool", "missing_chunks", "trailing_stream",
])
def test_mainf28_archive_rejects_forged_or_rehashed_sources(tmp_path, source_path, mutation):
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
    path = tmp_path / "forged-mainf28.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        _historical_mainf28_tooling_bytes(path)


def test_mainf28_archive_rejects_duplicate_fields(tmp_path):
    value = _fixture_path().read_text()
    path = tmp_path / "duplicate-mainf28.json"
    path.write_text(value.replace('"schema_version": 1,', '"schema_version": 1, "schema_version": 1,', 1))
    with pytest.raises(ValueError, match="repeats a field"):
        _historical_mainf28_tooling_bytes(path)
