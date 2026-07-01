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
    "C002833",
}
)

EK3_SCOPE_ONLY_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002708",
    "C002745",
}
)

SUT_MATERIAL_LIST_PRICE_CEILING_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002690",
}
)

MALZEME_SCOPE_ONLY_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002683",
}
)

R5_AMENDMENT_HEADER_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002731",
    "C002738",
    "C002763",
}
)

R5_MANIFEST_HEADER_ONLY_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002822",
    "C002826",
    "C002829",
}
)

KDV_PRICING_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002692",
}
)

WOUND_331_PILOT_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002856",
}
)

SPECIALTY_334_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002934",
    "C002936",
    "C002937",
    "C002939",
    "C002953",
    "C002962",
    "C002964",
    "C002966",
    "C002967",
    "C002970",
}
)

SPECIALTY_338_BATCH_CLAUSE_IDS: frozenset[str] = frozenset()

SPECIALTY_336_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002997",
    "C003030",
}
)

GLUCOSE_METER_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002875",
}
)

SPECIALTY_337_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C003072",
    "C003073",
}
)

OTHER_3_3_TAIL_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C003146",
    "C003159",
}
)

SPECIALTY_R5_HEADER_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002857",
    "C002858",
    "C003124",
}
)

VISION_OPTIK_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
{
    "C002888",
    "C002890",
    "C002893",
    "C002907",
    "C002917",
    "C002918",
    "C003289",
    "C003302",
    "C003346",
    "C003363",
    "C003384",
    "C003394",
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

