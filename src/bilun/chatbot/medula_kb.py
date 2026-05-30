"""MEDULA knowledge base — keyword-based retrieval for the BILUN chatbot.

Static editorial content lives under ``data/medula/*.json``. This module loads
those files and exposes search helpers for the chat runtime.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "medula"


@lru_cache(maxsize=1)
def _load_json(name: str) -> Any:
    path = _DATA_DIR / name
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def known_codes() -> dict[str, dict[str, Any]]:
    return _load_json("known_codes.json")


def rejection_categories() -> list[dict[str, Any]]:
    return _load_json("rejection_categories.json")


def workflow_stages() -> dict[str, dict[str, Any]]:
    return _load_json("workflow_stages.json")


def stage_keywords() -> dict[str, list[str]]:
    return _load_json("stage_keywords.json")


def _normalize(text: str) -> str:
    return text.lower().strip()


def _tokenize(text: str) -> set[str]:
    tokens = re.split(r"[\s.,;:!?()\-/]+", _normalize(text))
    return {token for token in tokens if len(token) >= 2}


def search_known_codes(query: str) -> list[dict[str, Any]]:
    """Search known numeric error codes mentioned in the query."""
    codes = re.findall(r"\b(\d{4})\b", query)
    catalog = known_codes()
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for code in codes:
        if code in catalog and code not in seen:
            seen.add(code)
            results.append({"code": code, **catalog[code]})
    return results


def search_rejection_categories(query: str, top_n: int = 3) -> list[dict[str, Any]]:
    """Keyword-match user query against rejection categories."""
    tokens = _tokenize(query)
    scored: list[tuple[int, dict[str, Any]]] = []
    for category in rejection_categories():
        keyword_tokens: set[str] = set()
        for keyword in category.get("keywords", []):
            keyword_tokens |= _tokenize(keyword)
        overlap = len(tokens & keyword_tokens)
        if overlap > 0:
            scored.append((overlap, category))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in scored[:top_n]]


def search_workflow_stage(query: str) -> dict[str, Any] | None:
    """Detect which MEDULA workflow stage the query is about."""
    tokens = _tokenize(query)
    best_stage: str | None = None
    best_score = 0
    stages = workflow_stages()
    for stage, keywords in stage_keywords().items():
        keyword_tokens: set[str] = set()
        for keyword in keywords:
            keyword_tokens |= _tokenize(keyword)
        score = len(tokens & keyword_tokens)
        if score > best_score:
            best_score = score
            best_stage = stage
    if best_stage and best_score > 0:
        return {"stage": best_stage, **stages[best_stage]}
    return None


def search_medula(query: str) -> dict[str, Any]:
    """Main MEDULA search entry point for chat context assembly."""
    return {
        "known_codes": search_known_codes(query),
        "rejection_categories": search_rejection_categories(query, top_n=3),
        "workflow_stage": search_workflow_stage(query),
    }
