"""Unit tests for hybrid SUT clause retrieval.

These run against whatever ``sut_clause_embeddings.parquet`` sidecar is built
(local-hash by default — fully offline). They validate retrieval quality, the
supersession guard, and metadata filtering.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from src.bilun.domain.constants import (
    SUT_CLAUSE_EMBEDDINGS_PATH,
    SUT_CLAUSES_PATH,
)
from src.bilun.domain.sut import clause_retrieval as cr

pytestmark = pytest.mark.unit

_HAS_INDEX = SUT_CLAUSES_PATH.exists() and SUT_CLAUSE_EMBEDDINGS_PATH.exists()

# Embedding-backed tests need an API key whenever the committed index is a
# remote model (e.g. nvidia/nv-embedqa-e5-v5); local-hash index needs none.
# CI has no .env, so without this guard the retrieval suite fails on key
# absence instead of skipping.
def _index_usable() -> bool:
    if not _HAS_INDEX:
        return False
    import polars as pl

    try:
        embeds = pl.read_parquet(SUT_CLAUSE_EMBEDDINGS_PATH)
        model = str(embeds["embed_model"][0])
    except Exception:
        return False
    if model == "local-hash-v1":
        return True
    from src.bilun.domain.sut.embeddings import _resolve_api_key

    return bool(_resolve_api_key())


_needs_index = pytest.mark.skipif(
    not _index_usable(),
    reason="sut_clause_embeddings.parquet missing or its model needs an "
    "embedding API key not present in this environment",
)

_GOLD_PATH = Path(__file__).resolve().parents[3] / "data" / "sut_retrieval_gold.jsonl"


@pytest.fixture(autouse=True)
def _clear_cache():
    cr.reset_cache()
    yield
    cr.reset_cache()


def _load_gold() -> list[dict]:
    return [json.loads(line) for line in _GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.skipif(not _HAS_INDEX, reason="clause/embedding artifacts missing")
def test_committed_embeddings_match_current_embeddable_corpus() -> None:
    """Reject stale sidecars offline, regardless of the query provider's API key."""
    from scripts.sut.build_clause_embeddings import select_embeddable

    clauses = select_embeddable(pl.read_parquet(SUT_CLAUSES_PATH))
    embeds = pl.read_parquet(SUT_CLAUSE_EMBEDDINGS_PATH)
    assert embeds["clause_id"].n_unique() == embeds.height
    assert set(embeds["clause_id"]) == set(clauses["clause_id"]), (
        "Embedding IDs differ from current embeddable clauses"
    )
    required = embeds.select("clause_id", "content_hash", "embedding", "embed_model", "embed_dims")
    assert required.null_count().sum_horizontal()[0] == 0
    assert embeds["embed_model"].n_unique() == 1 and embeds["embed_model"][0]
    assert embeds["embed_dims"].n_unique() == 1
    dims = embeds["embed_dims"][0]
    assert dims > 0 and embeds["embedding"].list.len().unique().to_list() == [dims]
    assert np.isfinite(np.asarray(embeds["embedding"].to_list(), dtype=np.float32)).all()

    text_col = "in_force_text" if "in_force_text" in clauses.columns else "text_tr"
    expected = clauses.select("clause_id", pl.col(text_col).map_elements(
        lambda text: hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest(),
        return_dtype=pl.String,
    ).alias("expected_body_hash"))
    joined = expected.join(embeds.select("clause_id", "content_hash"), on="clause_id")
    assert joined.filter(pl.col("expected_body_hash") != pl.col("content_hash")).height == 0, (
        "Embedding body hashes differ from current corpus text"
    )


@_needs_index
class TestRetrievalQuality:
    def test_recall_at_5_meets_bar(self) -> None:
        gold = _load_gold()
        assert gold, "gold set is empty"
        hits = 0
        misses: list[str] = []
        for item in gold:
            results = cr.search_clauses(item["query"], top_k=5)
            prefix = item["expected_section_prefix"]
            if any((r["section_id"] or "").startswith(prefix) for r in results):
                hits += 1
            else:
                misses.append(item["query"])
        recall = hits / len(gold)
        assert recall >= 0.8, f"recall@5={recall:.2f} below 0.8; misses={misses}"

    def test_results_carry_citation_fields(self) -> None:
        results = cr.search_clauses("katılım payı", top_k=3)
        assert results
        for r in results:
            for key in (
                "clause_id",
                "section_id",
                "text_tr",
                "annex_refs",
                "source_effective_date",
                "score",
            ):
                assert key in r
            assert isinstance(r["annex_refs"], list)
            assert len(r["text_tr"]) <= 720  # _TEXT_CAP + ellipsis

    def test_top_k_respected(self) -> None:
        assert len(cr.search_clauses("sağlık hizmeti", top_k=2)) <= 2


@_needs_index
class TestSupersessionGuard:
    def test_never_returns_superseded_clauses(self) -> None:
        superseded = set(
            pl.read_parquet(SUT_CLAUSES_PATH)
            .filter(pl.col("is_superseded_marker"))["clause_id"]
            .to_list()
        )
        assert superseded, "fixture expects some superseded clauses present"
        queries = [
            "katılım payı",
            "ilave ücret",
            "fizik tedavi",
            "tıbbi malzeme",
            "yurt dışı tedavi",
        ]
        returned_ids: set[str] = set()
        for q in queries:
            returned_ids.update(r["clause_id"] for r in cr.search_clauses(q, top_k=10))
        assert returned_ids.isdisjoint(superseded)


@_needs_index
class TestMetadataFilters:
    def test_annex_filter_restricts_results(self) -> None:
        results = cr.search_clauses("liste", top_k=10, annex="EK-2/C")
        assert results
        for r in results:
            norm = {cr._norm_annex(a) for a in r["annex_refs"]}
            assert "ek2c" in norm

    def test_section_prefix_filter_restricts_results(self) -> None:
        results = cr.search_clauses("katılım payı", top_k=10, section_prefix="1.8")
        assert results
        for r in results:
            assert (r["section_id"] or "").startswith("1.8")

    def test_inline_annex_reference_is_detected(self) -> None:
        results = cr.search_clauses("EK-2/C kapsamındaki işlemler", top_k=10)
        assert results
        for r in results:
            norm = {cr._norm_annex(a) for a in r["annex_refs"]}
            assert "ek2c" in norm


@_needs_index
class TestEdgeCases:
    def test_empty_query_returns_empty(self) -> None:
        assert cr.search_clauses("   ", top_k=5) == []

    def test_artifacts_available(self) -> None:
        assert cr.artifacts_available() is True


class TestMissingArtifactDegradation:
    def test_missing_embeddings_returns_empty(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(cr, "SUT_CLAUSE_EMBEDDINGS_PATH", tmp_path / "absent.parquet")
        cr.reset_cache()
        assert cr.artifacts_available() is False
        assert cr.search_clauses("katılım payı", top_k=5) == []
