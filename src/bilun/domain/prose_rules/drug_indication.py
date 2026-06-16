"""SUT §4.2 drug indication / report prose — corpus loader (evaluator Tier 3b)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR

_RULES_PATH = _PROSE_RULES_DIR / "drug_indication_prose.json"
_RULE_SET_ID = "drug_indication_prose"


@lru_cache(maxsize=1)
def load_drug_indication_rules() -> dict[str, Any]:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def list_drug_indication_rules() -> list[dict[str, Any]]:
    """Return encoded §4.2 indication rules (empty until Tier 3b corpus land)."""
    payload = load_drug_indication_rules()
    return list(payload.get("rules") or [])
