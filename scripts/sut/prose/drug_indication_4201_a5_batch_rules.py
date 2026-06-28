"""R5 Epic A5 — combined §4.2.1 tier-A pending batch rules (36 clause IDs)."""

from __future__ import annotations

from typing import Any

from scripts.sut.prose.drug_indication_4201_a5_c10_14_batch_rules import BATCH_A5_C10_14_RULES
from scripts.sut.prose.drug_indication_4201_a5_c2_c5_batch_rules import BATCH_A5_C2_C5_RULES
from scripts.sut.prose.drug_indication_4201_a5_c6_batch_rules import BATCH_A5_C6_RULES
from scripts.sut.prose.drug_indication_4201_a5_c7_batch_rules import BATCH_A5_C7_RULES
from scripts.sut.prose.drug_indication_4201_a5_c8_batch_rules import BATCH_A5_C8_RULES
from scripts.sut.prose.drug_indication_4201_a5_c9_c13_batch_rules import BATCH_A5_C9_C13_RULES

BATCH_A5_RULES: list[dict[str, Any]] = [
    *BATCH_A5_C2_C5_RULES,
    *BATCH_A5_C6_RULES,
    *BATCH_A5_C7_RULES,
    *BATCH_A5_C8_RULES,
    *BATCH_A5_C9_C13_RULES,
    *BATCH_A5_C10_14_RULES,
]
