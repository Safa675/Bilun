"""EK-4/D — Hasta katılım payından muaf ilaçlar (§1.8.2(3), §1.8.5(8))."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

import pandas as pd

from ..constants import EK4A_PARQUET_PATH, EK4D_ENTRIES_PATH, EK4D_SECTIONS_PATH
from ..optimization.shared import _icd10_in_range
from ..utils import fuzzy_match_name

logger = logging.getLogger("bilun.domain.drugs.ek4d")

_DRUG_FUZZY_THRESHOLD = 0.82


def _normalize_drug_name(raw: str) -> str:
    import re
    import unicodedata

    text = str(raw or "").strip()
    text = re.sub(r"\*+", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


@lru_cache(maxsize=1)
def _load_sections() -> pd.DataFrame:
    if not EK4D_SECTIONS_PATH.is_file():
        logger.warning("EK-4/D sections parquet missing: %s", EK4D_SECTIONS_PATH)
        return pd.DataFrame()
    return pd.read_parquet(EK4D_SECTIONS_PATH)


@lru_cache(maxsize=1)
def _load_entries() -> pd.DataFrame:
    if not EK4D_ENTRIES_PATH.is_file():
        logger.warning("EK-4/D entries parquet missing: %s", EK4D_ENTRIES_PATH)
        return pd.DataFrame()
    return pd.read_parquet(EK4D_ENTRIES_PATH)


@lru_cache(maxsize=1)
def _section_index() -> dict[int, dict[str, Any]]:
    sections = _load_sections()
    entries = _load_entries()
    if sections.empty:
        return {}

    by_section: dict[int, dict[str, Any]] = {}
    for row in sections.itertuples(index=False):
        section_id = int(row.section_id)
        ranges = json.loads(str(row.icd_ranges_json or "[]"))
        by_section[section_id] = {
            "section_id": section_id,
            "title_tr": str(row.title_tr),
            "icd_ranges": ranges,
            "icd_codes": frozenset(),
            "drug_names": [],
            "broad_categories": [],
        }

    if not entries.empty:
        for row in entries.itertuples(index=False):
            section_id = int(row.section_id)
            bucket = by_section.get(section_id)
            if bucket is None:
                continue
            entry_type = str(row.entry_type)
            if entry_type == "icd10_code":
                code = str(row.icd10_code or "").strip().upper()
                if code:
                    bucket["icd_codes"] = bucket["icd_codes"] | {code}
            elif entry_type == "drug_name":
                normalized = str(row.drug_name_normalized or "").strip()
                if normalized:
                    bucket["drug_names"].append(
                        {
                            "drug_name_tr": str(row.drug_name_tr),
                            "drug_name_normalized": normalized,
                        }
                    )
            elif entry_type == "drug_category" and bool(row.category_broad):
                bucket["broad_categories"].append(str(row.drug_name_tr))

    return by_section


def _diagnosis_matches_section(diagnosis: str, bucket: dict[str, Any]) -> bool:
    code = str(diagnosis or "").strip().upper()
    if not code:
        return False
    if code in bucket["icd_codes"]:
        return True
    for listed in bucket["icd_codes"]:
        if listed and (code == listed or code.startswith(listed + ".")):
            return True
    for span in bucket["icd_ranges"]:
        start = str(span.get("start", "")).upper()
        end = str(span.get("end", start)).upper()
        if start and _icd10_in_range(code, start, end):
            return True
    return False


def _normalize_drug_query(drug_name: str, drug_code: str, barkod: str) -> str:
    name = str(drug_name or "").strip()
    if name:
        return name

    if not EK4A_PARQUET_PATH.is_file():
        return ""

    try:
        df = pd.read_parquet(EK4A_PARQUET_PATH)
    except Exception:
        return ""

    for token in (str(barkod or "").strip(), str(drug_code or "").strip()):
        if not token:
            continue
        for column in ("barcode", "kamu_no"):
            if column not in df.columns:
                continue
            hits = df[df[column].astype(str).str.strip() == token]
            if not hits.empty:
                resolved = str(hits.iloc[0].get("drug_name", "")).strip()
                if resolved:
                    return resolved
    return ""


def _drug_matches_section(drug_query: str, bucket: dict[str, Any]) -> dict[str, Any] | None:
    normalized = _normalize_drug_name(drug_query)
    if not normalized:
        return None

    candidates = {
        entry["drug_name_normalized"]: entry["drug_name_tr"]
        for entry in bucket["drug_names"]
    }
    if normalized in candidates:
        return {
            "drug_name_tr": candidates[normalized],
            "match_type": "exact",
        }

    fuzzy = fuzzy_match_name(
        normalized,
        list(candidates.items()),
        threshold=_DRUG_FUZZY_THRESHOLD,
    )
    if fuzzy is not None:
        return {
            "drug_name_tr": fuzzy[1],
            "match_type": "fuzzy",
        }
    return None


def match_ek4d_copay_exempt_drug(
    diagnoses: list[str],
    *,
    drug_name: str = "",
    drug_code: str = "",
    barkod: str = "",
    has_health_report: bool | None = None,
) -> dict[str, Any] | None:
    """Return match evidence when §1.8.2(3) EK-4/D drug copay exemption applies.

    Requires health report per SUT when ``has_health_report`` is explicitly False.
    When ``has_health_report`` is unknown (None), returns a partial match without
    asserting savings (same pattern as EK-1/A).
    """
    index = _section_index()
    if not index:
        return None

    drug_query = _normalize_drug_query(drug_name, drug_code, barkod)
    if not drug_query:
        return None

    diag_list = [str(d).strip() for d in diagnoses if str(d).strip()]
    if not diag_list:
        return None

    for section_id, bucket in sorted(index.items()):
        if not any(_diagnosis_matches_section(d, bucket) for d in diag_list):
            continue
        drug_hit = _drug_matches_section(drug_query, bucket)
        if drug_hit is None:
            continue

        counts = has_health_report is not False
        return {
            "category": "ek4d_copay_exempt_drug",
            "rule_source": "SUT §1.8.2(3) + EK-4/D",
            "counts_toward_exempt": counts and has_health_report is True,
            "partial_without_report": has_health_report is None,
            "evidence": {
                "section_id": section_id,
                "section_title": bucket["title_tr"],
                "drug_name_tr": drug_hit["drug_name_tr"],
                "drug_match_type": drug_hit["match_type"],
                "qualifying_diagnosis": next(
                    d
                    for d in diag_list
                    if _diagnosis_matches_section(d, bucket)
                ),
            },
        }
    return None
