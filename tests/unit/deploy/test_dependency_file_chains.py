"""Versioned dependency pins for the complete observed Ubuntu Python inventory."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.deploy import prepare_single_vps_release as module
from tests.unit.deploy import test_prepare_single_vps_release as preparation

machine = preparation.machine
save = preparation.save
SCHEMA = "bilun-single-vps-preparation-v3"
PINS_SCHEMA = "bilun-preparation-pins-v3"


def _observed_inventory(root: Path):
    """Fabricate all observed roles, preserving libpython's literal ../../ hop."""
    stdlib = root / "usr/lib/python3.13"
    config = stdlib / "config-3.13-x86_64-linux-gnu"
    config.mkdir(parents=True)
    library = root / "usr/lib/x86_64-linux-gnu"
    library.mkdir(parents=True)
    final = library / "libpython3.13.so.1.0"
    final.write_bytes(b"fabricated libpython binary\0\x01")
    final.chmod(0o644)
    intermediate = library / "libpython3.13.so.1"
    intermediate.symlink_to("libpython3.13.so.1.0")
    first = config / "libpython3.13.so"
    first.symlink_to("../../x86_64-linux-gnu/libpython3.13.so.1")
    site_target = root / "etc/python3.13/sitecustomize.py"
    site_target.parent.mkdir(parents=True)
    site_target.write_bytes(b"# fabricated system customization\n")
    site_target.chmod(0o644)
    site_link = stdlib / "sitecustomize.py"
    site_link.symlink_to(site_target)
    venv = root / "venv"
    venv.mkdir()
    (venv / "module.py").write_bytes(b"# no external venv links\n")
    roots = (venv, stdlib, site_target, intermediate, final)
    return {"roots": roots, "stdlib": stdlib, "first": first,
            "intermediate": intermediate, "final": final,
            "site_link": site_link, "site_target": site_target, "venv": venv}


@pytest.fixture
def inventory(tmp_path):
    return _observed_inventory(tmp_path / "host")


@pytest.fixture
def chain_machine(machine):
    manifest, spec, _, _ = machine
    inventory = _observed_inventory(manifest.parent / "host")
    spec["schema_version"] = SCHEMA
    spec["dependency_roots"] = [str(path) for path in inventory["roots"]]
    save(manifest, spec)
    return machine, inventory


def _pins(inventory, *, roots=None, paths=None):
    roots = inventory["roots"] if roots is None else roots
    paths = set(roots) if paths is None else paths
    return module._pin_inputs(paths, set(), dependency_roots=tuple(roots),
                              allow_dependency_file_links=True)


def _report(tmp_path, inventory):
    path = tmp_path / "pins.json"
    report = {"schema_version": PINS_SCHEMA,
              "dependency_roots": [str(item) for item in inventory["roots"]],
              "immutable_inputs": _pins(inventory), "external_state": {}}
    save(path, report)
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), report


def _relink(link, target):
    link.unlink()
    link.symlink_to(target)


def _expected_chain(links, final):
    return {"link": os.readlink(links[0]), "link_chain": [
        {"path": str(link), "link": os.readlink(link), "mode": link.lstat().st_mode & 0o7777,
         "target_path": str(target)}
        for link, target in zip(links, [*links[1:], final], strict=True)
    ], "resolved_target": str(final), "target": {
        "file": hashlib.sha256(final.read_bytes()).hexdigest(), "mode": final.stat().st_mode & 0o7777,
    }}


@pytest.mark.parametrize("mode", [0o644, 0o4644, 0o2644, 0o1644])
@pytest.mark.parametrize("declare_initial_links", [False, True])
def test_exact_observed_inventory_prepares_and_replays(chain_machine, mode, declare_initial_links):
    machine, inventory = chain_machine
    manifest, spec, events, original = machine
    inventory["final"].chmod(mode)
    if declare_initial_links:
        spec["dependency_roots"].extend(str(inventory[key]) for key in ("first", "site_link"))
        save(manifest, spec)
    assert module.DEPENDENCY_CHAIN_SCHEMA == SCHEMA
    assert os.readlink(inventory["first"]) == "../../x86_64-linux-gnu/libpython3.13.so.1"
    assert os.readlink(inventory["intermediate"]) == "libpython3.13.so.1.0"
    assert not any(path.is_symlink() for path in inventory["venv"].rglob("*"))
    result = module.prepare_release_bundle(manifest)
    path, digest, report = preparation._prepared_pins(result)
    assert result["schema_version"] == SCHEMA
    assert set(report) == {"schema_version", "dependency_roots", "immutable_inputs", "external_state"}
    assert report["schema_version"] == PINS_SCHEMA
    assert report["dependency_roots"] == spec["dependency_roots"]
    assert report["immutable_inputs"][str(inventory["final"])] == {
        "file": hashlib.sha256(inventory["final"].read_bytes()).hexdigest(), "mode": mode,
    }
    stdlib_pin = report["immutable_inputs"][str(inventory["stdlib"])]
    first, intermediate, final = (inventory[key] for key in ("first", "intermediate", "final"))
    assert stdlib_pin[first.relative_to(inventory["stdlib"]).as_posix()] == _expected_chain(
        [first, intermediate], final,
    )
    assert report["immutable_inputs"][str(intermediate)] == {
        "dependency_link": _expected_chain([intermediate], final),
    }
    assert stdlib_pin["sitecustomize.py"] == _expected_chain(
        [inventory["site_link"]], inventory["site_target"],
    )
    if declare_initial_links:
        assert report["immutable_inputs"][str(first)] == {
            "dependency_link": _expected_chain([first, intermediate], final),
        }
        assert report["immutable_inputs"][str(inventory["site_link"])]["dependency_link"] == stdlib_pin["sitecustomize.py"]
    module.verify_preparation_pins(path, digest)
    before = list(events)
    assert module.prepare_release_bundle(manifest) == result
    assert events == before
    assert Path(spec["live_cache_path"]).read_bytes() == original
    paired = json.loads(Path(result["paired_manifest_path"]).read_text())
    assert paired["schema_version"] == "bilun-single-vps-pair-v1"


@pytest.mark.parametrize("schema", [module.SCHEMA, module.DEPENDENCY_FILE_SCHEMA])
def test_legacy_preparations_reject_identical_explicit_chain(chain_machine, schema):
    machine, _ = chain_machine
    manifest, spec, events, _ = machine
    spec["schema_version"] = schema
    save(manifest, spec)
    with pytest.raises(ValueError):
        module.prepare_release_bundle(manifest)
    assert events == []
    assert not Path(spec["bundle_root"]).exists()


@pytest.mark.parametrize("legacy", [True, False])
def test_legacy_pin_api_never_inherits_v3_file_link_permission(inventory, legacy):
    kwargs = {} if legacy else {"dependency_roots": inventory["roots"]}
    with pytest.raises(ValueError):
        module._pin_inputs(set(inventory["roots"]), set(), **kwargs)


@pytest.mark.parametrize("mutation", [
    "bytes", "mode", "setuid", "setgid", "sticky", "equal_bytes_retarget",
    "first_retarget", "first_literal", "intermediate_literal", "lost_intermediate",
    "lost_target", "target_symlink", "new_file", "new_link",
])
@pytest.mark.parametrize("boundary", ["handoff", "repeat_prepare"])
def test_v3_replay_rejects_chain_or_inventory_drift(chain_machine, mutation, boundary):
    machine, inventory = chain_machine
    manifest, _, events, _ = machine
    final, intermediate, first = (inventory[key] for key in ("final", "intermediate", "first"))
    alternate = final.with_name("equivalent.so")
    alternate.write_bytes(final.read_bytes())
    alternate.chmod(0o644)
    # Both equal-byte files are authorized before the original hash is fixed.
    inventory["roots"] += (alternate,)
    spec = machine[1]
    spec["dependency_roots"].append(str(alternate))
    save(manifest, spec)
    path, digest, _ = preparation._prepared_pins(module.prepare_release_bundle(manifest))
    before = list(events)
    if mutation == "bytes":
        final.write_bytes(b"changed library")
    elif mutation in {"mode", "setuid", "setgid", "sticky"}:
        final.chmod({"mode": 0o600, "setuid": 0o4644, "setgid": 0o2644, "sticky": 0o1644}[mutation])
    elif mutation == "equal_bytes_retarget":
        _relink(intermediate, alternate.name)
    elif mutation == "first_retarget":
        _relink(first, final)
    elif mutation == "first_literal":
        _relink(first, intermediate)
    elif mutation == "intermediate_literal":
        _relink(intermediate, final)
    elif mutation == "lost_intermediate":
        intermediate.unlink()
    elif mutation == "lost_target":
        final.unlink()
    elif mutation == "target_symlink":
        final.unlink()
        final.symlink_to(alternate)
    elif mutation == "new_file":
        (inventory["stdlib"] / "injected.py").write_bytes(b"new dependency")
    else:
        (inventory["stdlib"] / "injected.py").symlink_to(inventory["site_target"])
    with pytest.raises((ValueError, OSError)):
        if boundary == "handoff":
            module.verify_preparation_pins(path, digest)
        else:
            module.prepare_release_bundle(manifest)
    assert events == before


@pytest.mark.parametrize("stage", ["build_wavea_sidecar", "issue_wavea_activation"])
@pytest.mark.parametrize("mutation", ["bytes", "mode", "retarget"])
def test_v3_rechecks_whole_chain_before_and_after_signing(chain_machine, monkeypatch, stage, mutation):
    machine, inventory = chain_machine
    manifest, spec, events, original = machine
    operation = getattr(module, stage)

    def change(**kwargs):
        result = operation(**kwargs)
        if mutation == "bytes":
            inventory["final"].write_bytes(b"changed before handoff")
        elif mutation == "mode":
            inventory["final"].chmod(0o4644)
        else:
            _relink(inventory["intermediate"], inventory["final"])
        return result

    monkeypatch.setattr(module, stage, change)
    with pytest.raises(ValueError, match="changed"):
        module.prepare_release_bundle(manifest)
    assert not (Path(spec["bundle_root"]) / "prepared.json").exists()
    assert not (Path(spec["bundle_root"]) / "paired-manifest.json").exists()
    assert Path(spec["live_cache_path"]).read_bytes() == original
    if stage == "build_wavea_sidecar":
        assert "issue" not in events


@pytest.mark.parametrize("missing", ["intermediate", "final"])
@pytest.mark.parametrize("substitute", ["none", "directory", "unrelated_immutable_pin"])
def test_every_chain_hop_and_final_needs_explicit_dependency_role(inventory, missing, substitute):
    missing_path = inventory[missing]
    roots = tuple(path for path in inventory["roots"] if path != missing_path)
    if substitute == "directory":
        roots += (missing_path.parent,)
    paths = set(roots)
    if substitute == "unrelated_immutable_pin":
        paths.add(missing_path)
    with pytest.raises(ValueError):
        _pins(inventory, roots=roots, paths=paths)


@pytest.mark.parametrize("kind", ["dangling_first", "dangling_intermediate", "self_cycle", "two_cycle", "directory", "fifo"])
def test_dependency_chains_reject_invalid_endpoints(inventory, kind):
    first, intermediate, final = (inventory[key] for key in ("first", "intermediate", "final"))
    if kind == "dangling_first":
        _relink(first, final.with_name("absent"))
    elif kind == "dangling_intermediate":
        _relink(intermediate, "absent")
    elif kind == "self_cycle":
        _relink(intermediate, intermediate.name)
    elif kind == "two_cycle":
        second = final.with_name("second-link")
        second.symlink_to(intermediate.name)
        _relink(intermediate, second.name)
        inventory["roots"] += (second,)
    elif kind == "directory":
        _relink(intermediate, final.parent)
    else:
        final.unlink()
        os.mkfifo(final)
    with pytest.raises(ValueError):
        _pins(inventory)


@pytest.mark.parametrize("hops", [1, 2, 8, 9])
def test_chain_hop_limit_counts_initial_inventory_link(tmp_path, hops):
    dependency, library = tmp_path / "dependency", tmp_path / "library"
    dependency.mkdir()
    library.mkdir()
    final = library / "final.py"
    final.write_bytes(b"bounded chain")
    links = [dependency / "entry.py"] + [library / f"hop-{n}.py" for n in range(1, hops)]
    for link, target in zip(links, [*links[1:], final], strict=True):
        link.symlink_to(target)
    inventory = {"roots": (dependency, *links[1:], final)}
    if hops > 8:
        with pytest.raises(ValueError):
            _pins(inventory)
    else:
        pins = _pins(inventory)
        assert all(str(link) in pins for link in links[1:])
        assert str(final) in pins


@pytest.mark.parametrize("link_role", ["first", "intermediate"])
@pytest.mark.parametrize("path_kind", ["directory_alias", "hidden_alias_parent", "trailing_slash",
                                       "trailing_dot", "file_parent", "file_parent_dotdot"])
def test_chain_walk_never_normalizes_away_invalid_components(inventory, link_role, path_kind):
    final = inventory["final"]
    nested = final.parent / "nested"
    nested.mkdir()
    alias = final.parent.parent / "library-alias"
    alias.symlink_to(nested if path_kind == "hidden_alias_parent" else final.parent,
                     target_is_directory=True)
    target = {
        "directory_alias": f"{alias}/{final.name}",
        "hidden_alias_parent": f"{alias}/../{final.name}",
        "trailing_slash": f"{final}/",
        "trailing_dot": f"{final}/.",
        "file_parent": f"{final}/child.py",
        "file_parent_dotdot": f"{final}/../{final.name}",
    }[path_kind]
    _relink(inventory[link_role], target)
    with pytest.raises(ValueError):
        _pins(inventory)


@pytest.mark.parametrize("source_key", ["baseline_claims_dir", "baseline_clean_dir"])
@pytest.mark.parametrize("target_role", ["intermediate", "final"])
def test_v3_roles_do_not_authorize_external_source_links(chain_machine, source_key, target_role):
    machine, inventory = chain_machine
    manifest, spec, events, _ = machine
    (Path(spec[source_key]) / "source-link.py").symlink_to(inventory[target_role])
    with pytest.raises(ValueError, match="escapes"):
        module.prepare_release_bundle(manifest)
    assert "snapshot" not in events and not Path(spec["bundle_root"]).exists()


@pytest.mark.parametrize("source_key", ["baseline_claims_dir", "baseline_clean_dir"])
@pytest.mark.parametrize("overlap", ["equal", "ancestor", "file", "filesystem_root"])
def test_v3_dependencies_cannot_overlap_source_roles(chain_machine, source_key, overlap):
    machine, _ = chain_machine
    manifest, spec, events, _ = machine
    source = Path(spec[source_key])
    declared = {"equal": source, "ancestor": source.parent,
                "file": source / "input.txt", "filesystem_root": Path("/")}[overlap]
    spec["dependency_roots"].append(str(declared))
    save(manifest, spec)
    with pytest.raises(ValueError, match="source data"):
        module.prepare_release_bundle(manifest)
    assert events == []


@pytest.mark.parametrize("forgery", ["missing_roles", "null_roles", "string_roles", "empty_roles",
                                    "duplicate_role", "undeclared_role", "relative_role", "nonstring_role",
                                    "too_many_roles", "filesystem_root", "lost_intermediate_role",
                                    "lost_final_role", "lost_directory_role", "missing_intermediate_pin",
                                    "missing_final_pin", "malformed_pin", "extra_field", "downgrade_v1",
                                    "downgrade_v2", "malformed_version", "target_mode"])
def test_v3_hash_bound_replay_rejects_malformed_contract(tmp_path, inventory, forgery):
    path, _, report = _report(tmp_path, inventory)
    roles = report["dependency_roots"]
    final, intermediate = inventory["final"], inventory["intermediate"]
    if forgery == "missing_roles":
        del report["dependency_roots"]
    elif forgery in {"null_roles", "string_roles", "empty_roles"}:
        report["dependency_roots"] = {"null_roles": None, "string_roles": str(final), "empty_roles": []}[forgery]
    elif forgery == "duplicate_role":
        roles.append(str(final))
    elif forgery == "undeclared_role":
        roles.append(str(path))
    elif forgery == "relative_role":
        roles.append("libpython3.13.so.1")
    elif forgery == "nonstring_role":
        roles.append({"path": str(final)})
    elif forgery == "too_many_roles":
        report["dependency_roots"] = [str(final)] * 65
    elif forgery == "filesystem_root":
        roles.append("/")
    elif forgery in {"lost_intermediate_role", "lost_final_role", "lost_directory_role"}:
        roles.remove(str({"lost_intermediate_role": intermediate, "lost_final_role": final,
                          "lost_directory_role": inventory["stdlib"]}[forgery]))
    elif forgery in {"missing_intermediate_pin", "missing_final_pin"}:
        del report["immutable_inputs"][str(intermediate if forgery == "missing_intermediate_pin" else final)]
    elif forgery == "malformed_pin":
        report["immutable_inputs"][str(intermediate)] = None
    elif forgery == "extra_field":
        report["extra_permissions"] = True
    elif forgery in {"downgrade_v1", "downgrade_v2"}:
        report["schema_version"] = "bilun-preparation-pins-" + forgery.removeprefix("downgrade_")
        if forgery == "downgrade_v1":
            del report["dependency_roots"]
    elif forgery == "malformed_version":
        report["schema_version"] = []
    else:
        report["immutable_inputs"][str(final)]["mode"] = 0o600
    save(path, report)
    with pytest.raises(ValueError):
        # Rehash only to test structure; original-hash protection is independent.
        module.verify_preparation_pins(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_v3_roles_remain_bound_to_original_handoff_digest(tmp_path, inventory):
    path, digest, report = _report(tmp_path, inventory)
    report["dependency_roots"].remove(str(inventory["intermediate"]))
    save(path, report)
    with pytest.raises(ValueError, match="contract is malformed or changed"):
        module.verify_preparation_pins(path, digest)


def test_reading_unchanged_links_may_advance_only_access_time(inventory, monkeypatch):
    expected = _pins(inventory)
    first = inventory["first"]
    real_lstat, real_readlink = Path.lstat, os.readlink
    reads = 0

    def readlink(path, *args, **kwargs):
        nonlocal reads
        literal = real_readlink(path, *args, **kwargs)
        if Path(path) == first:
            reads += 1
        return literal

    def lstat(path, *args, **kwargs):
        result = real_lstat(path, *args, **kwargs)
        if path != first:
            return result
        fields = {name: getattr(result, name) for name in dir(result) if name.startswith("st_")}
        fields["st_atime"] += reads
        fields["st_atime_ns"] += reads * 1_000_000_000
        return SimpleNamespace(**fields)

    monkeypatch.setattr(os, "readlink", readlink)
    monkeypatch.setattr(Path, "lstat", lstat)
    assert _pins(inventory) == expected
    assert reads >= 2


@pytest.mark.parametrize("mutation", ["retarget", "replace_equal_literal", "regular_file"])
def test_changed_link_during_readlink_fails_closed(inventory, monkeypatch, mutation):
    first = inventory["first"]
    real_readlink = os.readlink
    changed = False

    def readlink(path, *args, **kwargs):
        nonlocal changed
        literal = real_readlink(path, *args, **kwargs)
        if Path(path) == first and not changed:
            changed = True
            # Keep the original inode alive so equal-literal replacement cannot
            # accidentally reuse it on a fast temporary filesystem.
            first.rename(first.with_name("original-link"))
            if mutation == "regular_file":
                first.write_bytes(b"replacement regular file")
            else:
                first.symlink_to(inventory["final"] if mutation == "retarget" else literal)
        return literal

    monkeypatch.setattr(os, "readlink", readlink)
    with pytest.raises(ValueError, match="changed"):
        _pins(inventory)
    assert changed is True


@pytest.mark.parametrize("missing", [None, "return_link", "final"])
def test_external_chain_returning_inside_root_still_needs_every_role(inventory, missing):
    final = inventory["stdlib"] / "internal-final.so"
    final.write_bytes(b"externally routed back inside")
    returned = inventory["stdlib"] / "return-link.so"
    returned.symlink_to(final.name)
    _relink(inventory["intermediate"], returned)
    inventory["roots"] += tuple(path for name, path in (("return_link", returned), ("final", final)) if name != missing)
    if missing is not None:
        with pytest.raises(ValueError):
            _pins(inventory)
    else:
        pins = _pins(inventory)
        assert pins[str(inventory["intermediate"])] == {
            "dependency_link": _expected_chain([inventory["intermediate"], returned], final),
        }


@pytest.mark.parametrize("record_role", ["initial", "independent"])
@pytest.mark.parametrize("field", ["path", "link", "mode", "target_path", "missing_hop",
                                    "extra_hop", "resolved_target", "target_hash", "target_mode"])
def test_v3_replay_rejects_each_forged_chain_evidence_field(tmp_path, inventory, record_role, field):
    path, _, report = _report(tmp_path, inventory)
    immutable = report["immutable_inputs"]
    if record_role == "initial":
        record = immutable[str(inventory["stdlib"])][inventory["first"].relative_to(inventory["stdlib"]).as_posix()]
    else:
        record = immutable[str(inventory["intermediate"])]["dependency_link"]
    if field in {"path", "link", "mode", "target_path"}:
        record["link_chain"][-1][field] = 0o600 if field == "mode" else "tampered"
    elif field == "missing_hop":
        record["link_chain"].pop()
    elif field == "extra_hop":
        record["link_chain"].append(dict(record["link_chain"][-1]))
    elif field == "resolved_target":
        record["resolved_target"] = str(inventory["site_target"])
    else:
        record["target"]["file" if field == "target_hash" else "mode"] = "0" * 64 if field == "target_hash" else 0o600
    save(path, report)
    with pytest.raises(ValueError):
        module.verify_preparation_pins(path, hashlib.sha256(path.read_bytes()).hexdigest())


@pytest.mark.parametrize("target_role", ["stdlib", "intermediate", "final"])
def test_v3_declaration_cannot_hide_a_directory_link_parent(chain_machine, target_role):
    machine, inventory = chain_machine
    manifest, spec, events, _ = machine
    declared = inventory[target_role]
    alias = manifest.parent / "parent-alias"
    alias.symlink_to(declared.parent, target_is_directory=True)
    spec["dependency_roots"].append(str(alias / declared.name))
    save(manifest, spec)
    with pytest.raises(ValueError, match="canonical"):
        module.prepare_release_bundle(manifest)
    assert events == []


@pytest.mark.parametrize("input_role", ["live_cache_path", "live_backend_runtime", "live_frontend_runtime",
                                       "candidate_backend_environment", "candidate_frontend_environment"])
def test_v3_manifest_never_grants_dependency_link_permission_to_other_inputs(chain_machine, input_role):
    machine, inventory = chain_machine
    manifest, spec, events, _ = machine
    spec[input_role] = str(inventory["intermediate"])
    save(manifest, spec)
    with pytest.raises(ValueError, match="canonical"):
        module.prepare_release_bundle(manifest)
    assert events == []


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_legacy_literal_contract_is_unchanged(tmp_path, version):
    dependency = tmp_path / "dependency"
    dependency.mkdir()
    internal = dependency / "module.py"
    internal.write_bytes(b"legacy bytes")
    internal.chmod(0o640)
    (dependency / "internal.py").symlink_to("module.py")
    immutable = {str(dependency): {
        "module.py": {"sha256": hashlib.sha256(b"legacy bytes").hexdigest(), "mode": 0o640},
        "internal.py": {"link": "module.py"},
    }}
    report = {"schema_version": f"bilun-preparation-pins-{version}",
              "immutable_inputs": immutable, "external_state": {}}
    if version == "v2":
        target = tmp_path / "sitecustomize.py"
        target.write_bytes(b"external bytes")
        target.chmod(0o4644)
        (dependency / "sitecustomize.py").symlink_to(target)
        target_pin = {"file": hashlib.sha256(b"external bytes").hexdigest(), "mode": 0o4644}
        immutable[str(target)] = target_pin
        immutable[str(dependency)]["sitecustomize.py"] = {
            "link": str(target), "resolved_target": str(target), "target": target_pin,
        }
        report["dependency_roots"] = [str(dependency), str(target)]
    path = tmp_path / "legacy-pins.json"
    save(path, report)
    module.verify_preparation_pins(path, hashlib.sha256(path.read_bytes()).hexdigest())
