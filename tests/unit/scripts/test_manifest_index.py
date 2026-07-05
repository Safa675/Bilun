"""Tests for manifest_index.py — single drug manifest parsing path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST_DIR = _REPO / "data/gazette/prose_manifests"


def test_trace_index_list_shape() -> None:
    from scripts.sut.prose.manifest_index import trace_index

    payload = {
        "clause_traces": [
            {"clause_id": "C000001", "manifest_status": "encoded", "encode_tier": "A"},
            {"clause_id": "C000002", "manifest_status": "tier_c_deferred", "encode_tier": "C"},
        ]
    }
    indexed = trace_index(payload)
    assert set(indexed) == {"C000001", "C000002"}
    assert indexed["C000001"]["manifest_status"] == "encoded"


def test_traced_clause_ids_unions_buckets_and_traces() -> None:
    from scripts.sut.prose.manifest_index import traced_clause_ids

    payload = {
        "encoded_clause_ids": ["C000001"],
        "tier_c_deferred_clause_ids": ["C000002"],
        "clause_traces": [{"clause_id": "C000003", "manifest_status": "encoded"}],
    }
    traced = traced_clause_ids(payload)
    assert traced == frozenset({"C000001", "C000002", "C000003"})


def test_encoded_like_clause_ids_excludes_deferred_lists() -> None:
    from scripts.sut.prose.manifest_index import encoded_like_clause_ids

    payload = {
        "encoded_clause_ids": ["C000001", "C000003"],
        "tier_c_deferred_clause_ids": ["C000002"],
        "tier_a_pending_clause_ids": ["C000004"],
    }
    encoded = encoded_like_clause_ids(payload)
    assert "C000001" in encoded
    assert "C000003" in encoded
    assert "C000002" not in encoded
    assert "C000004" not in encoded


def test_build_drug_manifest_index_loads_repo_manifests() -> None:
    from scripts.sut.prose.manifest_index import build_drug_manifest_index

    index = build_drug_manifest_index(_MANIFEST_DIR)
    assert len(index.manifests_loaded) >= 10
    assert len(index.all_clause_ids) >= 500
    assert index.get("C000001") is not None or len(index.by_clause) > 0


def test_load_all_drug_clause_ids_matches_4214c_manifest_subset() -> None:
    from scripts.sut.prose.manifest_index import (
        load_all_drug_clause_ids,
        manifest_clause_ids_and_tiers,
    )

    manifest_path = _MANIFEST_DIR / "L4.2_drug_indication_4.2.14.C_manifest.json"
    if not manifest_path.is_file():
        pytest.skip("4214C manifest not on disk")
    single_ids, _ = manifest_clause_ids_and_tiers(manifest_path)
    all_ids, _ = load_all_drug_clause_ids(_MANIFEST_DIR)
    assert single_ids.issubset(all_ids)
