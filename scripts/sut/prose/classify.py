"""Classify SUT prose clauses into rule categories using registry signals."""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from .rule_registry import RULE_REGISTRY, RuleRegistryEntry

_MATCH_SCORE_ANNEX = 100
_MATCH_SCORE_SECTION = 50
_MATCH_SCORE_KEYWORD = 20
_BARE_SECTION_ID_RE = re.compile(r"^\d+$")


def _json_list(raw: str) -> list[str]:
    if not raw or raw == "[]":
        return []
    return json.loads(raw)


def _normalize_text(text: str) -> str:
    return text.casefold()


def _as_optional_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _sanitize_section_refs(
    section_path: str | None,
    section_id: str | None,
) -> tuple[str | None, str | None]:
    """Drop bogus extractor artifacts like section_path='1' from fikra '1) …' lines."""
    path = section_path.strip() if section_path else None
    sid = section_id.strip() if section_id else None
    if path and _BARE_SECTION_ID_RE.fullmatch(path):
        path = None
    if sid and _BARE_SECTION_ID_RE.fullmatch(sid):
        sid = None
    return path, sid


def _section_matches(section_path: str | None, section_id: str | None, prefix: str) -> bool:
    section_path, section_id = _sanitize_section_refs(section_path, section_id)
    if section_id and _BARE_SECTION_ID_RE.fullmatch(section_id):
        return False
    if section_path:
        parts = section_path.split("/")
        if any(part == prefix or part.startswith(prefix + ".") for part in parts):
            return True
    if section_id:
        return section_id == prefix or section_id.startswith(prefix + ".")
    return False


def _score_entry_match(
    entry: RuleRegistryEntry,
    *,
    section_path: str | None,
    section_id: str | None,
    annex_refs: list[str],
    text_norm: str,
) -> int:
    score = 0

    annex_set = set(annex_refs)
    registry_annexes = set(entry.annex_refs)
    if registry_annexes and annex_set & registry_annexes:
        score += _MATCH_SCORE_ANNEX

    for prefix in entry.sut_section_prefixes:
        if _section_matches(section_path, section_id, prefix):
            score += _MATCH_SCORE_SECTION
            break

    for keyword in entry.keywords:
        if keyword.casefold() in text_norm:
            score += _MATCH_SCORE_KEYWORD
            break

    if score == 0 and not entry.sut_section_prefixes and not entry.annex_refs and not entry.keywords:
        return 0

    return score


def _match_entries(
    *,
    section_path: str | None,
    section_id: str | None,
    annex_refs: list[str],
    text_tr: str,
) -> list[tuple[str, int]]:
    text_norm = _normalize_text(text_tr)
    matches: list[tuple[str, int]] = []

    for entry in RULE_REGISTRY:
        if entry.rule_id == "claim_validation":
            continue
        score = _score_entry_match(
            entry,
            section_path=section_path,
            section_id=section_id,
            annex_refs=annex_refs,
            text_norm=text_norm,
        )
        if score > 0:
            matches.append((entry.rule_id, score))

    matches.sort(key=lambda item: item[1], reverse=True)
    return matches


def _fallback_rule_id(
    *,
    section_path: str | None,
    section_id: str | None,
    deontic_modality: str | None,
    clause_type: str,
) -> str | None:
    if clause_type in {"chapter", "amendment"} and not deontic_modality:
        return None

    prefixes = [
        ("1.8.5", "copay_exemption_ek1a"),
        ("1.8", "copay_rate_general"),
        ("1.9", "surcharge_general"),
        ("4.2.9.A-2", "lab_billing"),
        ("2.2.2.A", "procedure_pairing"),
        ("2.2.1.B", "drg_package_adequacy"),
        ("3.1.1", "material_pairing"),
        ("2.2", "payment_method_package"),
        ("2.", "pricing_ek2b"),
        ("3.3", "specialty_materials"),
        ("3.", "material_bundling_prose"),
        ("4.2", "drug_indication_prose"),
        ("4.4", "drug_ek4a"),
        ("4.1", "drug_ek4a"),
        ("5.", "billing_documents"),
        ("1.7", "medula_rejection_playbook"),
        ("1.5", "referral_admission"),
        ("1.4", "definitions"),
        ("1.1", "definitions"),
    ]
    prefixes.sort(key=lambda item: len(item[0]), reverse=True)

    for prefix, rule_id in prefixes:
        if _section_matches(section_path, section_id, prefix.rstrip(".")):
            return rule_id

    if deontic_modality and clause_type in {"fikra", "bent", "prose"}:
        return "material_bundling_prose" if deontic_modality in {"MUST_NOT_BILL", "NO_PAY"} else None

    return None


def classify_clause_row(row: pd.Series) -> dict[str, Any]:
    annex_refs = _json_list(row.get("annex_refs", "[]"))
    section_path = _as_optional_str(row.get("section_path"))
    section_id = _as_optional_str(row.get("section_id"))
    section_path, section_id = _sanitize_section_refs(section_path, section_id)
    deontic_modality = _as_optional_str(row.get("deontic_modality"))
    clause_type = str(row.get("clause_type") or "")

    matches = _match_entries(
        section_path=section_path,
        section_id=section_id,
        annex_refs=annex_refs,
        text_tr=str(row.get("text_tr") or ""),
    )

    if not matches:
        fallback = _fallback_rule_id(
            section_path=section_path,
            section_id=section_id,
            deontic_modality=deontic_modality,
            clause_type=clause_type,
        )
        if fallback:
            matches = [(fallback, _MATCH_SCORE_SECTION)]

    matched_rule_ids = [rule_id for rule_id, _ in matches]
    match_scores = {rule_id: score for rule_id, score in matches}

    primary_rule_id = matched_rule_ids[0] if matched_rule_ids else None
    is_classified = primary_rule_id is not None

    return {
        "matched_rule_ids": json.dumps(matched_rule_ids, ensure_ascii=False),
        "match_scores": json.dumps(match_scores, ensure_ascii=False),
        "primary_rule_id": primary_rule_id,
        "is_classified": is_classified,
    }


def classify_clauses(clauses: pd.DataFrame) -> pd.DataFrame:
    if clauses.empty:
        return clauses.copy()

    classified = clauses.copy()
    extras = classified.apply(classify_clause_row, axis=1, result_type="expand")
    return pd.concat([classified, extras], axis=1)
