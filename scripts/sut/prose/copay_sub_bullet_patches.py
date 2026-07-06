"""Phase 4.2 — link §1.8 sub-bullet clauses to existing copay rules.

The 16 unencoded §1.8.2/3/4 clauses are source-text sub-bullets of the 4
existing copay_general rules (fee values, "tahsil edilir" collection-channel
prose). They are not new rules — they detail the rules already in
``copay_general_1_8.json``. Appending their clause_ids to the existing rules'
``gate_b_sources`` marks them encoded (the manifest builder derives
``encoded_clause_ids`` from ``gate_b_sources`` at ``coverage.py:58,143-153``).

Mapping (rule_id → clause_ids to append):
- ``1.8.2.(1)`` (drug copay rate) ← §1.8.2.(4) collection-channel sub-bullets
- ``1.8.2.(2)`` (drug prescription flat fee) ← the literal fee-value clauses
- ``1.8.3.(1)`` / ``1.8.3.(2)`` (material copay rates) ← §1.8.3 collection-channel
- ``1.8.4.(1)`` (IVF copay rate) ← §1.8.4.(2) collection-channel

Run via the orchestrator's sequential ``_apply_source_patches`` (compile_rules.py).
"""

from __future__ import annotations

SOURCE_PATCHES: dict[str, list[str]] = {
    "1.8.2.(1)": ["C000327", "C000328", "C000329", "C000330", "C000331"],
    "1.8.2.(2)": ["C000322", "C000323"],
    "1.8.3.(2)": ["C000334", "C000335", "C000336", "C000340", "C000341", "C000342", "C000346", "C000348"],
    "1.8.4.(1)": ["C000353"],
}
