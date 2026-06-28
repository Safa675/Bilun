"""R5 Epic A4 — combined §4.2.1 batch rules (C-1/C-2/C-5/C-7 parallel clusters)."""

from __future__ import annotations

from typing import Any

from scripts.sut.prose.drug_indication_4201_a4_c1_batch_rules import BATCH_A4_C1_RULES
from scripts.sut.prose.drug_indication_4201_a4_c2_batch_rules import BATCH_A4_C2_RULES
from scripts.sut.prose.drug_indication_4201_a4_c5_batch_rules import BATCH_A4_C5_RULES
from scripts.sut.prose.drug_indication_4201_a4_c7_batch_rules import BATCH_A4_C7_RULES

BATCH_A4_RULES: list[dict[str, Any]] = [
    *BATCH_A4_C1_RULES,
    *BATCH_A4_C2_RULES,
    *BATCH_A4_C5_RULES,
    *BATCH_A4_C7_RULES,
]
