"""SUT §2.6 definitions prose — descriptive gates (non_algorithmic).

These rules encode §2.6 definitional scope (travel/daily/companion allowances,
documentation windows, expense caps). Their ``action`` carries
``enforcement: "gate"`` + a free-text ``message_tr`` rather than a billable
verdict, so there is no ``check_*`` executor: the rules cannot be evaluated
against claim lines. The loader exists so the rule set is inventoried,
traceable to its SUT clauses via the manifest, and surfaced honestly in the
rule database with ``coverage_status = non_algorithmic``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR

_RULES_PATH = _PROSE_RULES_DIR / "definitions_2_6.json"


@lru_cache(maxsize=1)
def load_definitions_2_6_rules() -> dict[str, Any]:
    """Load the §2.6 definitions prose rule set (descriptive gates)."""
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)
