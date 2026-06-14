"""Hybrid in-memory retrieval over SUT clauses for the chatbot.

Loads ``sut_clauses.parquet`` (metadata) joined with
``sut_clause_embeddings.parquet`` (vectors) into a single cached frame plus a
normalized float32 matrix. Retrieval blends three signals:

1. **Hard metadata filters** — explicit ``§section``, ``EK-x/y`` annex, or
   ``P######`` procedure-code references in the query restrict candidates.
   Superseded clauses never enter the index (the build skips them).
2. **Lexical** — idf-weighted query/clause token overlap (BM25-lite).
3. **Vector** — cosine similarity in the corpus embedding space (query embedded
   with the *same* provider recorded in the sidecar).

Final score is a weighted blend, with newer ``source_effective_date`` as a
tiebreak. Missing artifacts degrade gracefully: search returns ``[]``.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

from ..constants import SUT_CLAUSE_EMBEDDINGS_PATH, SUT_CLAUSES_PATH
from .embeddings import normalize, resolve_provider, tokenize

logger = logging.getLogger("bilun.sut.clause_retrieval")

_META_COLUMNS = (
    "clause_id",
    "section_id",
    "section_title",
    "section_path",
    "chapter",
    "clause_type",
    "text_tr",
    "annex_refs",
    "procedure_codes",
    "deontic_modality",
    "amendment_refs",
    "source_effective_date",
    "is_superseded_marker",
)

# Blend weights (vector + lexical). Structural matches are applied as hard filters.
_W_VECTOR = 0.55
_W_LEXICAL = 0.45

_TEXT_CAP = 700  # chars per clause in the LLM payload

_SECTION_REF_RE = re.compile(r"\b\d+(?:\.\d+){1,6}\b")
_ANNEX_REF_RE = re.compile(r"ek[\s\-]?\d+[\s\-/]?[a-z]?(?:[\s\-/]?\d)?", re.IGNORECASE)
_PROC_CODE_RE = re.compile(r"\b[plr]\d{6}\b", re.IGNORECASE)


def _norm_annex(raw: str) -> str:
    return re.sub(r"[^a-z0-9]", "", raw.lower())


def _json_list(raw: Any) -> list[str]:
    if not raw or raw == "[]":
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw]
    try:
        parsed = json.loads(raw)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


@dataclass
class _Index:
    frame: pl.DataFrame
    matrix: np.ndarray  # (N, dims) L2-normalized
    token_sets: list[set[str]]
    annex_sets: list[set[str]]
    proc_sets: list[set[str]]
    section_ids: list[str]
    idf: dict[str, float]
    embed_model: str
    embed_dims: int


_index: _Index | None = None
_index_loaded = False


def reset_cache() -> None:
    """Clear the cached index (test seam)."""
    global _index, _index_loaded
    _index = None
    _index_loaded = False


def _build_index() -> _Index | None:
    if not SUT_CLAUSES_PATH.exists() or not SUT_CLAUSE_EMBEDDINGS_PATH.exists():
        logger.warning(
            "SUT clause retrieval unavailable (clauses=%s embeddings=%s)",
            SUT_CLAUSES_PATH.exists(),
            SUT_CLAUSE_EMBEDDINGS_PATH.exists(),
        )
        return None

    clauses_full = pl.read_parquet(SUT_CLAUSES_PATH)
    clauses = clauses_full.select(
        [c for c in _META_COLUMNS if c in clauses_full.columns]
    )
    embeds = pl.read_parquet(SUT_CLAUSE_EMBEDDINGS_PATH)

    joined = clauses.join(embeds, on="clause_id", how="inner")
    # Defensive: never serve a superseded clause even if one slipped into the sidecar.
    if "is_superseded_marker" in joined.columns:
        joined = joined.filter(~pl.col("is_superseded_marker"))
    if joined.height == 0:
        logger.warning("SUT clause retrieval index is empty after join")
        return None

    embed_model = str(joined["embed_model"][0])
    embed_dims = int(joined["embed_dims"][0])

    matrix = np.asarray(joined["embedding"].to_list(), dtype=np.float32)
    matrix = normalize(matrix)

    texts = joined["text_tr"].to_list()
    titles = joined["section_title"].to_list()
    token_sets: list[set[str]] = []
    for text, title in zip(texts, titles):
        token_sets.append(set(tokenize(f"{title or ''} {text or ''}")))

    annex_sets = [
        {_norm_annex(a) for a in _json_list(v)} for v in joined["annex_refs"].to_list()
    ]
    proc_sets = [
        {p.upper() for p in _json_list(v)} for v in joined["procedure_codes"].to_list()
    ]
    section_ids = [str(s or "") for s in joined["section_id"].to_list()]

    n = joined.height
    df: dict[str, int] = {}
    for ts in token_sets:
        for tok in ts:
            df[tok] = df.get(tok, 0) + 1
    idf = {tok: math.log(1.0 + n / count) for tok, count in df.items()}

    logger.info(
        "SUT clause retrieval index: %d clauses | model=%s dims=%d",
        n,
        embed_model,
        embed_dims,
    )
    return _Index(
        frame=joined,
        matrix=matrix,
        token_sets=token_sets,
        annex_sets=annex_sets,
        proc_sets=proc_sets,
        section_ids=section_ids,
        idf=idf,
        embed_model=embed_model,
        embed_dims=embed_dims,
    )


def _get_index() -> _Index | None:
    global _index, _index_loaded
    if _index_loaded:
        return _index
    _index_loaded = True
    try:
        _index = _build_index()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to build SUT clause retrieval index: %s", exc)
        _index = None
    return _index


def artifacts_available() -> bool:
    return _get_index() is not None


def _parse_refs(query: str) -> tuple[list[str], list[str], list[str]]:
    """Extract explicit (section_ids, normalized_annexes, procedure_codes)."""
    sections = _SECTION_REF_RE.findall(query)
    procs = [m.upper() for m in _PROC_CODE_RE.findall(query)]
    annexes: list[str] = []
    for m in _ANNEX_REF_RE.findall(query):
        norm = _norm_annex(m)
        if norm.startswith("ek") and len(norm) > 2:
            annexes.append(norm)
    return sections, annexes, procs


def _lexical_scores(idx: _Index, query_tokens: list[str]) -> np.ndarray:
    qset = set(query_tokens)
    total_idf = sum(idx.idf.get(t, math.log(2.0)) for t in qset) or 1.0
    scores = np.zeros(idx.frame.height, dtype=np.float32)
    for i, ts in enumerate(idx.token_sets):
        matched = qset & ts
        if matched:
            scores[i] = sum(idx.idf.get(t, 0.0) for t in matched) / total_idf
    return scores


def search_clauses(
    query: str,
    *,
    top_k: int = 5,
    annex: str | None = None,
    section_prefix: str | None = None,
) -> list[dict[str, Any]]:
    """Return up to ``top_k`` cited, non-superseded clauses ranked by hybrid score."""
    idx = _get_index()
    if idx is None or not (query or "").strip():
        return []

    n = idx.frame.height
    candidate = np.ones(n, dtype=bool)

    sections, annexes, procs = _parse_refs(query)
    if section_prefix:
        sections = [section_prefix, *sections]
    if annex:
        annexes = [_norm_annex(annex), *annexes]

    if sections:
        sec_mask = np.zeros(n, dtype=bool)
        for i, sid in enumerate(idx.section_ids):
            if sid and any(sid == s or sid.startswith(s + ".") for s in sections):
                sec_mask[i] = True
        if sec_mask.any():
            candidate &= sec_mask
    if annexes:
        ann_mask = np.array(
            [bool(s & set(annexes)) for s in idx.annex_sets], dtype=bool
        )
        if ann_mask.any():
            candidate &= ann_mask
    if procs:
        proc_mask = np.array(
            [bool(s & set(procs)) for s in idx.proc_sets], dtype=bool
        )
        if proc_mask.any():
            candidate &= proc_mask

    # Vector score (cosine, clamped at 0).
    provider = resolve_provider(idx.embed_model, idx.embed_dims)
    qvec = normalize(provider.embed([query]))[0]
    vec_scores = np.clip(idx.matrix @ qvec, 0.0, None)

    lex_scores = _lexical_scores(idx, tokenize(query))

    final = _W_VECTOR * vec_scores + _W_LEXICAL * lex_scores
    final = np.where(candidate, final, -1.0)

    order = np.argsort(-final)
    results: list[dict[str, Any]] = []
    rows = idx.frame
    for i in order[: max(top_k, 0)]:
        if final[i] <= 0.0:
            break
        row = rows.row(int(i), named=True)
        text = row.get("text_tr") or ""
        if len(text) > _TEXT_CAP:
            text = text[:_TEXT_CAP].rstrip() + " …"
        results.append(
            {
                "clause_id": row.get("clause_id"),
                "section_id": row.get("section_id"),
                "section_title": row.get("section_title"),
                "section_path": row.get("section_path"),
                "clause_type": row.get("clause_type"),
                "text_tr": text,
                "annex_refs": _json_list(row.get("annex_refs")),
                "procedure_codes": _json_list(row.get("procedure_codes")),
                "amendment_refs": _json_list(row.get("amendment_refs")),
                "source_effective_date": row.get("source_effective_date"),
                "score": round(float(final[i]), 4),
            }
        )
    return results
