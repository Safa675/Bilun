"""Byte closure is not clinical, semantic or deployment authorization."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import subprocess
import sys
import sysconfig
import zlib
from pathlib import Path

import pytest

from scripts.deploy import verify_final_source_refresh_transition as historical
from scripts.deploy import verify_integration_byte_profile as profile
from scripts.deploy.rehearse_wavea_same_port import project_report_transport
from tests.unit.deploy.integration_historical_sources import load_historical_sources
from tests.unit.deploy.test_same_port_rehearsal import (
    isolated_projection_source as isolated_projection_source,
)

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = Path(__file__).parent / "fixtures/integration_historical_sources.json"


def _git(root, *arguments):
    return subprocess.run(
        ["git", "-C", str(root), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(root, message, *, amend=False):
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", message, *(["--amend"] if amend else []))
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def byte_history(tmp_path, monkeypatch):
    checkout = tmp_path / "public-history"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.name", "Public Byte Profile Test")
    _git(checkout, "config", "user.email", "byte-profile@example.invalid")
    _git(checkout, "config", "commit.gpgsign", "false")
    (checkout / "product.py").write_text("amount = 0.0\n")
    base = _commit(checkout, "public baseline")
    base_tree = _git(checkout, "rev-parse", "HEAD^{tree}")
    (checkout / "product.py").write_text("amount = None\n")
    product = _commit(checkout, "public reviewed product")
    product_tree = _git(checkout, "rev-parse", "HEAD^{tree}")
    paths = frozenset({profile.VERIFIER_PATH, "tests/reviewed.py"})
    monkeypatch.setattr(profile, "TOOLING_PATHS", paths)
    closure = hashlib.sha256(profile.product_closure(checkout, product)).hexdigest()
    for path, body in (
        (profile.VERIFIER_PATH, Path(profile.__file__).read_bytes()),
        ("tests/reviewed.py", b"# reviewed negative controls\n"),
    ):
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    candidate = _commit(checkout, "public reviewed tooling")
    for name, value in {
        "BASE_SHA": base,
        "BASE_TREE": base_tree,
        "PRODUCT_SHA": product,
        "PRODUCT_TREE": product_tree,
        "PRODUCT_CLOSURE_SHA256": closure,
        "REVIEWED_TOOLING": {
            "tests/reviewed.py": profile.disk_entry(checkout / "tests/reviewed.py")
        },
        "REVIEWED_CHANGED_PATHS": tuple(sorted({"product.py", *paths})),
    }.items():
        monkeypatch.setattr(profile, name, value)
    return checkout, base, product, candidate


def test_finite_history_is_explicitly_byte_only(byte_history):
    root, _, _, candidate = byte_history
    result = profile.verify_candidate_history(root, candidate)
    assert result["history_form"] == "reviewed_product_plus_tooling"
    assert result["deployment_admitted"] is False
    assert result["clinical_source_extended"] is False
    assert result["semantic_release_admission"] == "blocked"


def test_normal_squash_does_not_require_discarded_product_object(byte_history, tmp_path):
    root, base, product, candidate = byte_history
    _git(root, "checkout", "-qb", "squashed", base)
    _git(root, "merge", "--squash", candidate)
    squash = _commit(root, "public real normal squash")
    fresh = tmp_path / "fresh"
    _git(
        tmp_path,
        "clone",
        "--no-local",
        "--single-branch",
        "--branch",
        "squashed",
        str(root),
        str(fresh),
    )
    missing = subprocess.run(
        ["git", "-C", str(fresh), "cat-file", "-e", product], capture_output=True
    )
    assert missing.returncode != 0
    assert profile.verify_candidate_history(fresh, squash)["history_form"] == "normal_squash"


@pytest.mark.parametrize(
    "mutation",
    [
        "product_money",
        "product_mode",
        "tooling_bytes",
        "tooling_mode",
        "tooling_symlink",
        "missing_tooling",
        "extra_path",
        "similarly_named_path",
        "missing_pin",
        "extra_pin",
        "base_tree",
        "product_tree",
        "closure",
        "wrong_sha",
        "two_parents",
        "future_commit",
        "mutate_revert",
    ],
)
def test_finite_profile_rejects_unreviewed_bytes_roster_and_history(
    byte_history, monkeypatch, mutation
):
    root, base, product, candidate = byte_history
    if mutation == "missing_pin":
        monkeypatch.setattr(profile, "REVIEWED_TOOLING", {})
    elif mutation == "extra_pin":
        monkeypatch.setattr(
            profile,
            "REVIEWED_TOOLING",
            {**profile.REVIEWED_TOOLING, "tests/extra.py": ("100644", "blob", "f" * 40)},
        )
    elif mutation in {"base_tree", "product_tree", "closure"}:
        name = {
            "base_tree": "BASE_TREE",
            "product_tree": "PRODUCT_TREE",
            "closure": "PRODUCT_CLOSURE_SHA256",
        }[mutation]
        monkeypatch.setattr(profile, name, "f" * (64 if mutation == "closure" else 40))
    elif mutation == "wrong_sha":
        candidate = "f" * 40
    elif mutation == "two_parents":
        candidate = _git(
            root,
            "commit-tree",
            candidate + "^{tree}",
            "-p",
            base,
            "-p",
            product,
            "-m",
            "unreviewed merge",
        )
        _git(root, "checkout", "-q", "--detach", candidate)
    elif mutation in {"future_commit", "mutate_revert"}:
        target = root / "tests/reviewed.py"
        body = target.read_bytes()
        target.write_bytes(body + b"# unreviewed intermediate\n")
        candidate = _commit(root, "unreviewed future")
        if mutation == "mutate_revert":
            target.write_bytes(body)
            candidate = _commit(root, "reverted tree with unreviewed history")
    else:
        if mutation.startswith("product"):
            target = root / "product.py"
            if mutation == "product_money":
                target.write_text("amount = 0.0\n")
            else:
                target.chmod(0o755)
        elif mutation in {"extra_path", "similarly_named_path"}:
            (
                root / ("extra.py" if mutation == "extra_path" else "tests/reviewed_extra.py")
            ).write_text("x\n")
        else:
            target = root / "tests/reviewed.py"
            if mutation == "tooling_bytes":
                target.write_text("# changed negative controls\n")
            elif mutation == "tooling_mode":
                target.chmod(0o755)
            else:
                target.unlink()
                if mutation == "tooling_symlink":
                    target.symlink_to("../product.py")
        candidate = _commit(root, "unreviewed bytes", amend=True)
    with pytest.raises(ValueError):
        profile.verify_candidate_history(root, candidate)


@pytest.mark.parametrize("mutation", ["body", "resealed", "missing_slot", "duplicate_slot"])
def test_byte_self_pin_is_not_self_authorized(mutation):
    source = Path(profile.__file__).read_bytes()
    digest = profile.REVIEWED_SELF_SHA256.encode()
    if mutation == "missing_slot":
        source = source.replace(b"REVIEWED_SELF_SHA256 =", b"UNREVIEWED_SELF_SHA256 =")
    elif mutation == "duplicate_slot":
        source += b'\nREVIEWED_SELF_SHA256 = "' + digest + b'"\n'
    else:
        source += b"# unreviewed source\n"
        if mutation == "resealed":
            start, end = next(profile._SELF_SLOT.finditer(source)).span(1)
            replacement = (
                hashlib.sha256(source[:start] + b"0" * 64 + source[end:]).hexdigest().encode()
            )
            source = source[:start] + replacement + source[end:]
    with pytest.raises(ValueError):
        profile.verify_self_source(source)


def test_current_tree_and_tooling_have_their_own_frozen_byte_profile():
    assert (
        hashlib.sha256(profile.product_closure(ROOT, "HEAD")).hexdigest()
        == profile.PRODUCT_CLOSURE_SHA256
    )
    assert set(profile.REVIEWED_TOOLING) == profile.TOOLING_PATHS - {profile.VERIFIER_PATH}
    for path, expected in profile.REVIEWED_TOOLING.items():
        assert profile.disk_entry(ROOT / path) == expected
    profile.verify_self_source(Path(profile.__file__).read_bytes())


def test_integration_byte_contract_cannot_enable_historical_activation():
    request = {
        "contract": profile.CONTRACT,
        "expected_candidate_sha": "a" * 40,
        "expected_verifier_sha": "a" * 40,
    }
    with pytest.raises(ValueError):
        historical.validate_transition_request(request)
    historical_sources = load_historical_sources()["shared_interpreter"]
    for path in (
        "scripts/deploy/verify_final_source_refresh_transition.py",
        "scripts/deploy/issue_wavea_activation.py",
    ):
        assert (ROOT / path).read_bytes() == historical_sources[path]
    # The unchanged historical profile rejects this actual integrated tree,
    # even in shallow CI where a missing historical object is itself a blocker.
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        historical._verify_candidate_history(ROOT, _git(ROOT, "rev-parse", "HEAD"))


@pytest.mark.parametrize(
    "mutation",
    [
        "body",
        "rehashed_body",
        "trailing_stream",
        "mode",
        "type",
        "commit",
        "tree",
        "extra_group",
        "missing_source",
        "extra_source",
        "extra_field",
        "schema_bool",
        "size_bool",
        "missing_chunks",
        "duplicate_field",
    ],
)
def test_historical_archive_does_not_trust_rehashed_or_forged_metadata(tmp_path, mutation):
    value = json.loads(ARCHIVE.read_text())
    group = value["archives"]["clinical_baseline"]
    path = "src/bilun/api/schemas.py"
    row = group["sources"][path]
    if mutation in {"body", "rehashed_body", "trailing_stream"}:
        compressed = base64.b64decode("".join(row["zlib_base64_chunks"]))
        body = zlib.decompress(compressed) + b"# forged historical source\n"
        compressed = (
            compressed + zlib.compress(b"trailing")
            if mutation == "trailing_stream"
            else zlib.compress(body)
        )
        encoded = base64.b64encode(compressed).decode()
        row["zlib_base64_chunks"] = [
            encoded[index : index + 76] for index in range(0, len(encoded), 76)
        ]
        if mutation == "rehashed_body":
            row.update(
                size_bytes=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                blob_sha1=hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest(),
            )
    elif mutation in {"mode", "type"}:
        row[mutation] = "100755" if mutation == "mode" else "tree"
    elif mutation in {"commit", "tree"}:
        group["source_" + mutation] = "f" * 40
    elif mutation == "extra_group":
        value["archives"]["unreviewed"] = copy.deepcopy(group)
    elif mutation == "missing_source":
        del group["sources"][path]
    elif mutation == "extra_source":
        group["sources"]["src/extra.py"] = copy.deepcopy(row)
    elif mutation == "extra_field":
        row["admit_new_heads"] = True
    elif mutation == "schema_bool":
        value["schema_version"] = True
    elif mutation == "size_bool":
        row["size_bytes"] = True
    elif mutation == "missing_chunks":
        row["zlib_base64_chunks"] = []
    target = tmp_path / "forged-archive.json"
    raw = json.dumps(value)
    if mutation == "duplicate_field":
        raw = raw.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1', 1)
    target.write_text(raw)
    with pytest.raises(ValueError):
        load_historical_sources(target)


@pytest.mark.parametrize("kind", ["missing", "null", "zero"])
def test_current_transport_computes_unknown_and_real_zero_from_actual_source(
    kind, isolated_projection_source
):
    repository, code_sha = isolated_projection_source
    report = {"patient_id": "P1"}
    if kind != "missing":
        amount = None if kind == "null" else 0.0
        report.update(
            sgk_uplift_try=amount,
            total_recoverable_try=amount,
            copay={"patient_copay_try": amount},
            lab={"normative_cost_try": amount},
        )
    patient = "/api/billing-report/P1"
    bill = patient + "/bills/C1"
    package = project_report_transport(
        {patient: report, bill: {**copy.deepcopy(report), "claim_id": "C1", "scope": "bill"}},
        {
            "mode": "synthetic_demo",
            "is_synthetic": True,
            "label": "Public authored fixture",
            "notice": "Synthetic only",
            "claim_source": "claims",
            "clinical_source": "clean",
        },
        repository=repository,
        expected_code_sha=code_sha,
        python_executable=Path(sys.executable),
        dependency_roots=(Path(sys.base_prefix), Path(sysconfig.get_path("purelib"))),
        cache_sha256="a" * 64,
        build_id="public-null-fixture",
        contract="wavea-evidence-v2",
    )
    package.validate()
    for row in package.complete_reports.values():
        expected = 0.0 if kind == "zero" else None
        for value in (
            row["sgk_uplift_try"],
            row["total_recoverable_try"],
            row["copay"]["patient_copay_try"],
            row["lab"]["normative_cost_try"],
        ):
            assert value is None if expected is None else type(value) is float and value == expected
