"""Combined §4.2.13 Tier B + §4.2.16 A2b/Tier B tail batches for merge."""

from __future__ import annotations

from typing import Any

from scripts.sut.prose.drug_indication_4213_tier_b_batch_rules import BATCH_4213_TIER_B_RULES
from scripts.sut.prose.drug_indication_4216_a2b_batch_rules import BATCH_A2B_4216_RULES
from scripts.sut.prose.drug_indication_4216_tier_b_batch_rules import BATCH_4216_TIER_B_RULES

BATCH_4213_4216_TAIL_RULES: list[dict[str, Any]] = [
    *BATCH_A2B_4216_RULES,
    *BATCH_4213_TIER_B_RULES,
    *BATCH_4216_TIER_B_RULES,
]
