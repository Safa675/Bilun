"""Mechanical migration proof rejects re-pinned content/context and identity drift."""
from __future__ import annotations

import hashlib
import json
import subprocess

import polars as pl
import pytest

from scripts.sut import verify_clinical_corpus_migration as migration
from scripts.sut import verify_clinical_source_authority as verifier
from src.bilun.domain.prose_rules._drug_indication import source_authority as authority

pytestmark = pytest.mark.unit
_OLD_COMMIT, _NEW_COMMIT = "a" * 40, "b" * 40


@pytest.fixture
def installed_assets(tmp_path, monkeypatch):
    """Real binding/closure evidence; isolate every installed asset under tmp_path."""
    original_root = authority._ROOT
    closure = verifier.verify()
    for relative in closure["assets"]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((original_root / relative).read_bytes())
    catalog_path = tmp_path / "data/gazette/source_authority/clinical_versions.json"
    monkeypatch.setattr(authority, "_ROOT", tmp_path)
    monkeypatch.setattr(authority, "_CATALOG", catalog_path)
    monkeypatch.setattr(verifier, "_ROOT", tmp_path)
    monkeypatch.setattr(verifier, "_CATALOG", catalog_path)
    old_path = tmp_path / migration._CORPUS_PATH
    candidate_path = tmp_path / "candidate.parquet"
    pl.read_parquet(old_path).with_columns(
        pl.col("clause_id").str.replace("^C", "F"),
        (pl.col("paragraph_index") + 25).alias("paragraph_index"),
        pl.lit("candidate.docx").alias("source_docx"),
    ).write_parquet(candidate_path)
    blobs = {_OLD_COMMIT: old_path.read_bytes(), _NEW_COMMIT: candidate_path.read_bytes()}
    monkeypatch.setattr(migration, "_git_corpus_bytes", lambda commit, root: blobs[commit])
    catalog_relative = "data/gazette/source_authority/clinical_versions.json"
    git_assets = {(_OLD_COMMIT, catalog_relative): catalog_path.read_bytes()}
    monkeypatch.setattr(migration, "_git_blob_bytes",
                        lambda commit, path, root: git_assets[(commit, path)])
    # The audit tests isolate semantic contracts from Git transport. Actual blob
    # extraction/commit validation is covered independently below.
    source_sha = json.loads(catalog_path.read_text())["versions"][0]["source_docx_sha256"]
    monkeypatch.setattr(migration, "_source_documents", lambda frame, commit, root: [
        {"path": path, "sha256": source_sha} for path in frame["source_docx"].unique()
    ])
    return {"old": old_path, "new": candidate_path, "blobs": blobs,
            "root": tmp_path, "catalog": catalog_path, "git_assets": git_assets}


def _audit(assets):
    return migration.audit_corpus_migration(
        assets["old"], assets["new"], baseline_commit=_OLD_COMMIT,
        candidate_commit=_NEW_COMMIT, git_root=assets["root"],
    )


def _replace_candidate(assets, frame):
    frame.write_parquet(assets["new"])
    assets["blobs"][_NEW_COMMIT] = assets["new"].read_bytes()


def _first_binding(assets):
    catalog = authority.load_source_authority()
    evidence = authority.SourceBindings.model_validate_json(
        authority._read_evidence(catalog.versions[0].evidence),
    )
    return evidence.bindings[0]


def test_audit_proves_unique_bindings_despite_positional_renumbering(installed_assets):
    report = _audit(installed_assets)
    catalog = authority.load_source_authority()
    assert report["status"] == "verified"
    assert report["family_count"] == 12
    assert report["binding_file_count"] == 8
    assert report["binding_count"] == 72
    assert report["family_binding_membership_count"] == 110
    assert report["currentness_extended"] is False
    assert report["clinical_eligibility_complete"] is False
    assert report["baseline"]["corpus_sha256"] == catalog.deployed_source_corpus_sha256
    assert report["candidate"]["corpus_sha256"] == hashlib.sha256(
        installed_assets["new"].read_bytes(),
    ).hexdigest()
    for group in report["binding_groups"]:
        assert len({row["source_ref"] for row in group["bindings"]}) == len(group["bindings"])
        for row in group["bindings"]:
            assert row["verified_contract"]["is_in_force"] is True
            assert row["old_position"]["clause_id"] != row["new_position"]["clause_id"]
            assert row["old_position"]["paragraph_index"] + 25 == row["new_position"]["paragraph_index"]
    versions = {row.family_id: row for row in catalog.versions}
    for contract in report["family_contracts"]:
        version = versions[contract["family_id"]]
        assert contract["version_contract_sha256"] == hashlib.sha256(json.dumps(
            version.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()


def test_old_corpus_must_match_installed_pin(installed_assets):
    altered = pl.read_parquet(installed_assets["old"]).with_columns(
        pl.lit("different.docx").alias("source_docx"),
    )
    unreviewed_old = installed_assets["root"] / "unreviewed-old.parquet"
    altered.write_parquet(unreviewed_old)
    installed_assets["old"] = unreviewed_old
    installed_assets["blobs"][_OLD_COMMIT] = unreviewed_old.read_bytes()
    with pytest.raises(ValueError, match="installed reviewed catalog pin"):
        _audit(installed_assets)


def test_candidate_bytes_must_match_claimed_commit(installed_assets):
    installed_assets["new"].write_bytes(installed_assets["new"].read_bytes() + b"drift")
    with pytest.raises(ValueError, match="exact Git blob"):
        _audit(installed_assets)


def test_local_catalog_drift_cannot_claim_baseline_commit(installed_assets):
    catalog = json.loads(installed_assets["catalog"].read_text())
    catalog["versions"][0]["lower_bound_basis"] = "Unreviewed local contract edit"
    installed_assets["catalog"].write_text(json.dumps(catalog))
    with pytest.raises(ValueError, match="catalog differs from its exact baseline Git blob"):
        _audit(installed_assets)


@pytest.mark.parametrize("mutation", ["text", "parent", "title", "duplicate", "missing"])
def test_repinning_candidate_does_not_admit_changed_binding(installed_assets, mutation):
    binding = _first_binding(installed_assets)
    frame = pl.read_parquet(installed_assets["new"])
    target = pl.col("clause_key") == binding.source_ref
    if mutation == "missing":
        frame = frame.filter(~target)
    elif mutation == "duplicate":
        frame = pl.concat([frame, frame.filter(target)])
    else:
        column, value = {
            "text": ("in_force_text", "tahrif edilmiş klinik koşul"),
            "parent": ("parent_section_id", "4.2.99"),
            "title": ("section_title", "başka klinik aile"),
        }[mutation]
        frame = frame.with_columns(pl.when(target).then(pl.lit(value))
                                   .otherwise(pl.col(column)).alias(column))
    _replace_candidate(installed_assets, frame)
    with pytest.raises(ValueError):
        _audit(installed_assets)


def test_candidate_source_document_must_match_pinned_evidence(installed_assets, monkeypatch):
    monkeypatch.setattr(migration, "_source_documents", lambda frame, commit, root: [
        {"path": "other.docx", "sha256": "0" * 64},
    ])
    with pytest.raises(ValueError, match="Candidate source document differs"):
        _audit(installed_assets)


def test_unrelated_approved_document_does_not_cover_wrong_binding_provenance(
    installed_assets, monkeypatch,
):
    binding = _first_binding(installed_assets)
    frame = pl.read_parquet(installed_assets["new"]).with_columns(
        pl.when(pl.col("clause_key") == binding.source_ref).then(pl.lit("wrong.docx"))
        .otherwise(pl.col("source_docx")).alias("source_docx"),
    )
    _replace_candidate(installed_assets, frame)
    expected = authority.load_source_authority().versions[0].source_docx_sha256
    monkeypatch.setattr(migration, "_source_documents", lambda frame, commit, root: [
        {"path": "candidate.docx", "sha256": expected},
        {"path": "wrong.docx", "sha256": "0" * 64},
    ])
    with pytest.raises(ValueError, match="Candidate bound row source document differs"):
        _audit(installed_assets)


def test_duplicate_binding_is_rejected_even_with_updated_evidence_sha(installed_assets):
    catalog = json.loads(installed_assets["catalog"].read_text())
    evidence_path = catalog["versions"][0]["evidence"]["path"]
    evidence = installed_assets["root"] / evidence_path
    bindings = json.loads(evidence.read_text())
    bindings["bindings"].append(bindings["bindings"][0])
    evidence.write_text(json.dumps(bindings))
    for version in catalog["versions"]:
        if version["evidence"]["path"] == evidence_path:
            version["evidence"]["sha256"] = hashlib.sha256(evidence.read_bytes()).hexdigest()
    installed_assets["catalog"].write_text(json.dumps(catalog))
    installed_assets["git_assets"][
        (_OLD_COMMIT, "data/gazette/source_authority/clinical_versions.json")
    ] = installed_assets["catalog"].read_bytes()
    with pytest.raises(ValueError, match="Duplicate source binding"):
        _audit(installed_assets)


def test_tampered_installed_evidence_is_rejected_after_warm_audit(installed_assets):
    _audit(installed_assets)
    binding = authority.load_source_authority().versions[0].evidence
    evidence = installed_assets["root"] / binding.path
    evidence.write_bytes(evidence.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Pinned source evidence changed"):
        _audit(installed_assets)


def test_cli_writes_only_explicit_report(installed_assets, capsys):
    arguments = [str(installed_assets["old"]), str(installed_assets["new"]),
                 "--baseline-commit", _OLD_COMMIT, "--candidate-commit", _NEW_COMMIT]
    before = {path.relative_to(installed_assets["root"]) for path in
              installed_assets["root"].rglob("*") if path.is_file()}
    assert migration.main(arguments) == 0
    after = {path.relative_to(installed_assets["root"]) for path in
             installed_assets["root"].rglob("*") if path.is_file()}
    assert before == after
    output = installed_assets["root"] / "migration.json"
    assert migration.main([*arguments, "--json-output", str(output)]) == 0
    assert json.loads(output.read_text())["binding_count"] == 72
    assert "no date/currentness extension" in capsys.readouterr().out


def test_exact_git_corpus_blob_and_document_provenance(tmp_path):
    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(tmp_path), *arguments])

    git("init", "--quiet")
    corpus = tmp_path / migration._CORPUS_PATH
    corpus.parent.mkdir(parents=True)
    document = tmp_path / "source.docx"
    document.write_bytes(b"pinned source document")
    pl.DataFrame({"source_docx": ["source.docx"]}).write_parquet(corpus)
    git("add", ".")
    git("-c", "user.name=Test", "-c", "user.email=test@example.com",
        "commit", "--quiet", "-m", "fixture")
    commit = git("rev-parse", "HEAD").decode().strip()
    assert migration._git_corpus_bytes(commit, tmp_path) == corpus.read_bytes()
    assert migration._source_documents(pl.read_parquet(corpus), commit, tmp_path) == [
        {"path": "source.docx", "sha256": hashlib.sha256(document.read_bytes()).hexdigest()},
    ]
    with pytest.raises(ValueError, match="exact lowercase 40-hex"):
        migration._git_corpus_bytes("HEAD", tmp_path)
    with pytest.raises(ValueError, match="unavailable"):
        migration._git_corpus_bytes("0" * 40, tmp_path)
