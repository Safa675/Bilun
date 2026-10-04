"""Manifest clause-ID sets for L1.4 material bundling and L4.4 specialty materials.

Extracted from legacy batch_rules modules during Phase 3 YAML-only cleanup.
"""

from __future__ import annotations

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_EK3_HEADER_IDS_PATH = _PROJECT_ROOT / "data/gazette/prose_manifests/L1.4_ek3_annex_header_clause_ids.json"
_MALZEME_HEADER_IDS_PATH = _PROJECT_ROOT / "data/gazette/prose_manifests/L1.4_malzeme_general_header_clause_ids.json"

GATE_B_STILL_DEFERRED_CLAUSE_IDS: frozenset[str] = frozenset()

EK3C_LIST_PRICE_CEILING_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002841",
}
)

EK3_SCOPE_ONLY_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002716",
    "C002753",
}
)

SUT_MATERIAL_LIST_PRICE_CEILING_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002698",
}
)

MALZEME_SCOPE_ONLY_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002691",
}
)

R5_AMENDMENT_HEADER_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002739",
    "C002746",
    "C002771",
}
)

R5_MANIFEST_HEADER_ONLY_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002830",
    "C002834",
    "C002837",
}
)

KDV_PRICING_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002700",
}
)

WOUND_331_PILOT_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002864",
}
)

SPECIALTY_334_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002942",
    "C002944",
    "C002945",
    "C002947",
    "C002961",
    "C002970",
    "C002972",
    "C002974",
    "C002975",
    "C002978",
}
)

SPECIALTY_338_BATCH_CLAUSE_IDS: frozenset[str] = frozenset()

SPECIALTY_336_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C003005",
    "C003038",
}
)

GLUCOSE_METER_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002883",
}
)

SPECIALTY_337_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C003080",
    "C003081",
}
)

OTHER_3_3_TAIL_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C003154",
    "C003167",
}
)

SPECIALTY_R5_HEADER_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002865",
    "C002866",
    "C003132",
}
)

VISION_OPTIK_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002896",
    "C002898",
    "C002901",
    "C002915",
    "C002925",
    "C002926",
    "C003297",
    "C003310",
    "C003354",
    "C003371",
    "C003392",
    "C003402",
}
)


def load_ek3_annex_header_clause_ids() -> frozenset[str]:
    """Load annex header clause IDs from committed manifest sidecar JSON."""
    if not _EK3_HEADER_IDS_PATH.is_file():
        return frozenset()
    payload = json.loads(_EK3_HEADER_IDS_PATH.read_text(encoding="utf-8"))
    return frozenset(str(item) for item in payload)


def load_malzeme_general_header_clause_ids() -> frozenset[str]:
    """Load malzeme-general header clause IDs from committed manifest sidecar JSON."""
    if not _MALZEME_HEADER_IDS_PATH.is_file():
        return frozenset()
    payload = json.loads(_MALZEME_HEADER_IDS_PATH.read_text(encoding="utf-8"))
    return frozenset(str(item) for item in payload)

