"""Verify deployed source authority and its complete repository-local asset closure.

This is a read-only verification command. It does not fetch sources, change
dates, attest new currentness, update ingestion, or approve reimbursement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.bilun.domain.prose_rules._drug_indication.source_authority import (
    _CATALOG, _ROOT, _read_evidence, _source_matches, AuthorityCatalog,
    SourceReviewReceipt, load_source_authority,
)


def verify() -> dict:
    catalog = load_source_authority()
    assets = {str(_CATALOG.relative_to(_ROOT)): hashlib.sha256(_CATALOG.read_bytes()).hexdigest()}
    schema_path = _CATALOG.with_name('clinical_versions.schema.json')
    if json.loads(schema_path.read_text()) != AuthorityCatalog.model_json_schema():
        raise ValueError('Checked-in strict source-authority schema differs from runtime schema')
    assets[str(schema_path.relative_to(_ROOT))] = hashlib.sha256(schema_path.read_bytes()).hexdigest()

    def include(item):
        _read_evidence(item)
        if item.path in assets and assets[item.path] != item.sha256:
            raise ValueError('Conflicting deployed evidence identity')
        assets[item.path] = item.sha256

    for review in catalog.official_reviews:
        include(review.receipt)
        receipt = SourceReviewReceipt.model_validate_json(_read_evidence(review.receipt))
        for observation in receipt.observations:
            include(observation.capture)
        for item in review.evidence:
            include(item)
    for version in catalog.versions:
        include(version.evidence)
        for item in version.historical_evidence:
            include(item)
        if not _source_matches(version,catalog.deployed_source_corpus_sha256):
            raise ValueError(f'Deployed clause/context evidence differs: {version.family_id}')
    corpus = _ROOT/'data/gazette/sut_clauses.parquet'
    assets[str(corpus.relative_to(_ROOT))] = hashlib.sha256(corpus.read_bytes()).hexdigest()
    return {'status':'verified', 'scope':catalog.scope,
            'family_count':len(catalog.versions), 'asset_count':len(assets),
            'assets':dict(sorted(assets.items())),
            'latest_reviewed_through':max(row.checked_through for row in catalog.official_reviews),
            'legacy_unchanged_modes':catalog.legacy_unchanged_modes,
            'external_runtime_file_dependencies':[],
            'clinical_eligibility_complete':False}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Verify only; this is the default')
    parser.add_argument('--json-output',type=Path,help='Optional verification report destination')
    args=parser.parse_args()
    try:
        report=verify()
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print(f'Clinical source authority verification failed: {exc}')
        return 1
    if args.json_output:
        args.json_output.write_text(json.dumps(report,indent=2)+'\n')
    print(f"Clinical source authority verified: {report['family_count']} families, "
          f"{report['asset_count']} repository-local assets, through {report['latest_reviewed_through']}; "
          'clinical/report scope only.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
