"""Corpus renewal preserves pinned clinical evidence without admitting new dates.

These tests use the installed assets and temporary copies, never Git history or
an external source. The same suite runs against a reviewed candidate overlay.
"""
from copy import deepcopy
import hashlib
import json
import shutil

import polars as pl
import pytest
from pydantic import ValidationError

from scripts.sut import verify_clinical_source_authority as verifier
from scripts.sut.prose.clause_identity import normalize_for_hash, resolve_gate_b_ref_to_clause_ids
from src.bilun.domain.prose_rules._drug_indication import source_authority as authority


FAMILIES = (
    'sma', 'antifungal_micafungin', 'antifungal_other', 'renal', 'enteral',
    'ravulizumab', 'followup', 'indication_sc_ig', 'indication_hbv',
    'indication_hcv', 'indication_bone', 'mecasermin',
)
HISTORICAL_FAMILIES = {
    'sma', 'antifungal_micafungin', 'enteral', 'ravulizumab',
    'indication_sc_ig', 'indication_hbv',
}
HISTORICAL_DAYS = ('2026-08-29', '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04')


@pytest.fixture
def deployed_assets(tmp_path, monkeypatch):
    """Exercise the actual loader and verifier against an isolated asset closure."""
    report = verifier.verify()
    original_root = authority._ROOT
    for relative in report['assets']:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original_root / relative, destination)
    catalog_path = tmp_path / 'data/gazette/source_authority/clinical_versions.json'
    monkeypatch.setattr(authority, '_ROOT', tmp_path)
    monkeypatch.setattr(authority, '_CATALOG', catalog_path)
    monkeypatch.setattr(verifier, '_ROOT', tmp_path)
    monkeypatch.setattr(verifier, '_CATALOG', catalog_path)
    authority._parse_catalog.cache_clear()
    authority._parse_corpus.cache_clear()
    yield tmp_path
    authority._parse_catalog.cache_clear()
    authority._parse_corpus.cache_clear()


def _corpus_path(root):
    return root / 'data/gazette/sut_clauses.parquet'


def _repin_temporary_corpus(root):
    raw = json.loads(authority._CATALOG.read_text())
    raw['deployed_source_corpus_sha256'] = hashlib.sha256(_corpus_path(root).read_bytes()).hexdigest()
    authority._CATALOG.write_text(json.dumps(raw))


def _history_snapshot():
    return {
        (family, day): authority.resolve_source_authority(family, day).model_dump()
        for family in FAMILIES for day in HISTORICAL_DAYS
    }


def _binding_rows(binding, frame):
    if binding.context_anchor:
        ids = frame.filter(
            (pl.col('clause_key') == binding.source_ref) & pl.col('is_in_force')
        )['clause_id'].to_list()
    else:
        ids = resolve_gate_b_ref_to_clause_ids(
            binding.source_ref, frame, encode_eligible_only=False,
        )
    assert len(ids) == 1, binding.source_ref
    rows = frame.filter(pl.col('clause_id') == ids[0])
    assert rows.height == 1, binding.source_ref
    return rows


def _renal_binding_and_rows(root):
    catalog = authority.load_source_authority()
    version = next(row for row in catalog.versions if row.family_id == 'renal')
    proof = authority.SourceBindings.model_validate_json(authority._read_evidence(version.evidence))
    binding = next(row for row in proof.bindings if not row.context_anchor)
    frame = pl.read_parquet(_corpus_path(root))
    return version, proof, frame, _binding_rows(binding, frame)


def test_installed_corpus_closes_all_twelve_families_and_seventy_two_bindings(deployed_assets):
    catalog = authority.load_source_authority()
    report = verifier.verify()
    assert {row.family_id for row in catalog.versions} == set(FAMILIES)
    assert report['family_count'] == 12
    assert report['status'] == 'verified'
    assert report['scope'] == 'named_clinical_report_checks_only'
    assert report['clinical_eligibility_complete'] is False
    assert report['external_runtime_file_dependencies'] == []
    assert report['asset_count'] == len(report['assets'])
    assert report['assets']['data/gazette/sut_clauses.parquet'] == catalog.deployed_source_corpus_sha256
    for relative, digest in report['assets'].items():
        assert hashlib.sha256((deployed_assets / relative).read_bytes()).hexdigest() == digest

    frame = pl.read_parquet(_corpus_path(deployed_assets))
    evidence_files = {row.evidence.path: row.evidence for row in catalog.versions}
    assert len(evidence_files) == 8
    references = set()
    for evidence in evidence_files.values():
        proof = authority.SourceBindings.model_validate_json(authority._read_evidence(evidence))
        for binding in proof.bindings:
            row = _binding_rows(binding, frame).row(0, named=True)
            assert row['is_in_force'] is True
            assert row['section_id'] == binding.section_id
            assert row['clause_coordinate'] == binding.clause_coordinate
            assert hashlib.sha256(normalize_for_hash(row['in_force_text']).encode()).hexdigest() == binding.text_sha256
            assert binding.source_ref not in references
            references.add(binding.source_ref)
    assert len(references) == 72
    for version in catalog.versions:
        assert authority._source_matches(version, catalog.deployed_source_corpus_sha256)


def test_reencoded_corpus_requires_repin_and_preserves_all_historical_results(deployed_assets):
    before_catalog = authority.load_source_authority().model_dump()
    before = _history_snapshot()
    for family in FAMILIES:
        for day in ('2026-10-02', '2026-10-03', '2026-10-04'):
            assert before[family, day]['status'] == 'admitted'
        assert (before[family, '2026-10-01']['status'] == 'admitted') is (family in HISTORICAL_FAMILIES)
    assert before['mecasermin', '2026-08-29']['status'] == 'admitted'

    corpus = _corpus_path(deployed_assets)
    pl.read_parquet(corpus).write_parquet(corpus, compression='uncompressed')
    assert hashlib.sha256(corpus.read_bytes()).hexdigest() != before_catalog['deployed_source_corpus_sha256']
    for family in FAMILIES:
        result = authority.resolve_source_authority(family, '2026-10-02')
        assert result.status == 'review_required'
        assert result.reason == 'source_authority_unavailable'

    _repin_temporary_corpus(deployed_assets)
    after_catalog = authority.load_source_authority().model_dump()
    assert after_catalog.pop('deployed_source_corpus_sha256') != before_catalog.pop('deployed_source_corpus_sha256')
    assert after_catalog == before_catalog
    assert _history_snapshot() == before
    assert verifier.verify()['family_count'] == 12


@pytest.mark.parametrize('asset', ['corpus', 'binding', 'receipt', 'capture'])
@pytest.mark.parametrize('mutation', ['missing', 'tampered'])
def test_warm_caches_reject_missing_or_tampered_assets(deployed_assets, asset, mutation):
    catalog = authority.load_source_authority()
    for family in FAMILIES:
        assert authority.resolve_source_authority(family, '2026-10-02').status == 'admitted'
    review = catalog.official_reviews[0]
    receipt = authority.SourceReviewReceipt.model_validate_json(authority._read_evidence(review.receipt))
    version = next(row for row in catalog.versions if row.family_id == 'renal')
    paths = {
        'corpus': _corpus_path(deployed_assets),
        'binding': deployed_assets / version.evidence.path,
        'receipt': deployed_assets / review.receipt.path,
        'capture': deployed_assets / receipt.observations[0].capture.path,
    }
    target = paths[asset]
    if mutation == 'missing':
        target.unlink()
    else:
        target.write_bytes(target.read_bytes() + b'\nmodified after cache warmup\n')
    for family in FAMILIES:
        result = authority.resolve_source_authority(family, '2026-10-02')
        assert result.status == 'review_required'
        assert result.reason == 'source_authority_unavailable'
        assert result.clinical_eligibility_complete is False
    with pytest.raises((OSError, ValueError)):
        verifier.verify()


@pytest.mark.parametrize('mutation', ['changed_text', 'duplicate_resolution'])
def test_repin_cannot_admit_changed_or_ambiguous_clinical_binding(deployed_assets, mutation):
    version, _, frame, rows = _renal_binding_and_rows(deployed_assets)
    assert authority.resolve_source_authority('renal', '2026-10-02').status == 'admitted'
    clause_id = rows['clause_id'][0]
    if mutation == 'changed_text':
        changed = frame.with_columns(
            pl.when(pl.col('clause_id') == clause_id)
            .then(pl.lit('changed necessary clinical criterion'))
            .otherwise(pl.col('in_force_text')).alias('in_force_text'),
        )
    else:
        duplicate = rows.with_columns(pl.lit('MIGRATION-DUPLICATE-CLAUSE-ID').alias('clause_id'))
        changed = pl.concat([frame, duplicate])
    changed.write_parquet(_corpus_path(deployed_assets))
    _repin_temporary_corpus(deployed_assets)
    catalog = authority.load_source_authority()
    assert not authority._source_matches(version, catalog.deployed_source_corpus_sha256)
    result = authority.resolve_source_authority('renal', '2026-10-02')
    assert result.status == 'review_required'
    assert result.reason == 'source_content_changed'
    assert result.clinical_eligibility_complete is False
    with pytest.raises(ValueError, match='Deployed clause/context evidence differs: renal'):
        verifier.verify()


def test_duplicate_binding_proof_is_rejected(deployed_assets):
    _, proof, _, _ = _renal_binding_and_rows(deployed_assets)
    raw = proof.model_dump()
    raw['bindings'].append(deepcopy(raw['bindings'][0]))
    with pytest.raises(ValidationError, match='Duplicate source binding'):
        authority.SourceBindings.model_validate(raw)
