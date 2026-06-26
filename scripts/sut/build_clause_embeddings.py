#!/usr/bin/env python3
"""Build the SUT clause embeddings sidecar parquet.

Reads ``data/gazette/sut_clauses.parquet``, selects the answerable clause
subset (drops headings and superseded markers), embeds ``section + title +
text`` with the configured provider, and writes
``data/gazette/sut_clause_embeddings.parquet``.

Idempotent: clauses whose ``clause_id`` + content hash are unchanged are
reused from any existing sidecar; only new/changed clauses are re-embedded.

Usage:
  python scripts/sut/build_clause_embeddings.py
  EMBEDDING_PROVIDER=openai EMBEDDING_API_KEY=sk-... python scripts/sut/build_clause_embeddings.py
  python scripts/sut/build_clause_embeddings.py --provider local

Provider selection (env): EMBEDDING_PROVIDER=auto|openai|local
  - auto (default): OpenAI when EMBEDDING_API_KEY/OPENAI_API_KEY is set, else local-hash.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.bilun.domain.constants import (  # noqa: E402
    SUT_CLAUSE_EMBEDDINGS_PATH,
    SUT_CLAUSES_PATH,
)
from src.bilun.domain.sut.embeddings import (  # noqa: E402
    EmbeddingProvider,
    LocalHashEmbeddingProvider,
    OpenAIEmbeddingProvider,
    default_build_provider,
)

# Clause types that carry answerable regulatory prose.
_EMBEDDABLE_TYPES = ("fikra", "bent", "prose", "amendment")


def _content_hash(text: str) -> str:
    return hashlib.blake2b((text or "").encode("utf-8"), digest_size=16).hexdigest()


def _embed_text(row: dict) -> str:
    """Prefix structural context so the vector captures section identity."""
    body = str(row.get("in_force_text") or row.get("text_tr") or "")
    parts = [
        str(row.get("section_id") or ""),
        str(row.get("section_title") or ""),
        body,
    ]
    return "\n".join(p for p in parts if p).strip()


def select_embeddable(frame: pl.DataFrame) -> pl.DataFrame:
    text_col = "in_force_text" if "in_force_text" in frame.columns else "text_tr"
    filters = [
        (~pl.col("is_heading")),
        (~pl.col("is_superseded_marker")),
        (pl.col("clause_type").is_in(_EMBEDDABLE_TYPES)),
        (pl.col(text_col).is_not_null()),
        (pl.col(text_col).str.len_chars() > 0),
    ]
    if "is_in_force" in frame.columns:
        filters.append(pl.col("is_in_force"))
    return frame.filter(*filters)


def _load_existing(path: Path) -> dict[str, tuple[str, list[float]]]:
    """Map clause_id -> (content_hash, embedding) from a prior build, if any."""
    if not path.exists():
        return {}
    try:
        prior = pl.read_parquet(path)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "Existing embeddings parquet could not be read; rebuilding from scratch. Cause: %s",
            exc,
        )
        return {}
    needed = {"clause_id", "content_hash", "embedding"}
    if not needed.issubset(set(prior.columns)):
        return {}
    return {
        r["clause_id"]: (r["content_hash"], r["embedding"])
        for r in prior.iter_rows(named=True)
    }


def build(
    clauses_path: Path,
    output_path: Path,
    provider: EmbeddingProvider,
    *,
    force: bool = False,
) -> pl.DataFrame:
    frame = pl.read_parquet(clauses_path)
    text_col = "in_force_text" if "in_force_text" in frame.columns else "text_tr"
    subset = select_embeddable(frame).with_columns(
        pl.struct(["section_id", "section_title", text_col])
        .map_elements(_embed_text, return_dtype=pl.Utf8)
        .alias("_embed_text")
    )
    subset = subset.with_columns(
        pl.col(text_col)
        .map_elements(_content_hash, return_dtype=pl.Utf8)
        .alias("content_hash")
    )

    existing = {} if force else _load_existing(output_path)

    rows = subset.select(
        ["clause_id", "content_hash", "_embed_text"]
    ).to_dicts()

    reuse: dict[str, list[float]] = {}
    to_embed_ids: list[str] = []
    to_embed_texts: list[str] = []
    for r in rows:
        cid, chash = r["clause_id"], r["content_hash"]
        prior = existing.get(cid)
        if prior is not None and prior[0] == chash and prior[1] is not None:
            reuse[cid] = list(prior[1])
        else:
            to_embed_ids.append(cid)
            to_embed_texts.append(r["_embed_text"])

    print(
        f"clauses={frame.height} embeddable={subset.height} "
        f"reused={len(reuse)} to_embed={len(to_embed_ids)} "
        f"provider={provider.model_id} dims={provider.dims}"
    )

    fresh: dict[str, list[float]] = {}
    if to_embed_ids:
        t0 = time.perf_counter()
        vectors = provider.embed(to_embed_texts)
        elapsed = time.perf_counter() - t0
        print(f"embedded {len(to_embed_ids)} clauses in {elapsed:.1f}s")
        for cid, vec in zip(to_embed_ids, vectors):
            fresh[cid] = [float(x) for x in vec]

    embedding_col: list[list[float]] = []
    for r in rows:
        cid = r["clause_id"]
        embedding_col.append(reuse.get(cid) or fresh[cid])

    dims = len(embedding_col[0]) if embedding_col else provider.dims
    out = subset.select(["clause_id", "content_hash"]).with_columns(
        pl.Series("embedding", embedding_col, dtype=pl.List(pl.Float32)),
        pl.lit(provider.model_id).alias("embed_model"),
        pl.lit(dims).alias("embed_dims"),
        pl.lit(time.strftime("%Y-%m-%dT%H:%M:%S")).alias("built_at"),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.write_parquet(output_path)
    print(f"wrote {out.height} embeddings -> {output_path}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SUT clause embeddings sidecar")
    parser.add_argument("--clauses", default=str(SUT_CLAUSES_PATH))
    parser.add_argument("--output", default=str(SUT_CLAUSE_EMBEDDINGS_PATH))
    parser.add_argument(
        "--provider",
        choices=["auto", "openai", "local"],
        default=None,
        help="Override EMBEDDING_PROVIDER env for this run.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed every clause, ignoring any existing sidecar.",
    )
    args = parser.parse_args()

    if args.provider == "local":
        provider: EmbeddingProvider = LocalHashEmbeddingProvider()
    elif args.provider == "openai":
        provider = OpenAIEmbeddingProvider()
    else:
        provider = default_build_provider()

    build(Path(args.clauses), Path(args.output), provider, force=args.force)


if __name__ == "__main__":
    main()
