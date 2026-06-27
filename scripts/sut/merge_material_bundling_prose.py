#!/usr/bin/env python3
"""Merge Gate B batch rules into material_bundling_prose.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.material_bundling_batch_rules import GATE_B_BATCH_RULES  # noqa: E402
from scripts.sut.prose.material_bundling_corpus_batch2_rules import (  # noqa: E402
    CORPUS_BATCH2_RULE_PATCHES,
    CORPUS_BATCH2_RULES,
)
from scripts.sut.prose.material_bundling_faturalandirma_batch_rules import (  # noqa: E402
    FATURALANDIRMA_BATCH_RULES,
)
from scripts.sut.prose.material_bundling_garanti_ihale_batch_rules import (  # noqa: E402
    GARANTI_IHALE_BATCH_RULES,
)
from scripts.sut.prose.material_bundling_ek3_list_batch_rules import (  # noqa: E402
    EK3C_LIST_PRICE_CEILING_CLAUSE_IDS,
    EK3_LIST_BATCH_RULES,
    EK3_SCOPE_ONLY_CLAUSE_IDS,
    load_ek3_annex_header_clause_ids,
)
from scripts.sut.prose.material_bundling_malzeme_general_batch_rules import (  # noqa: E402
    MALZEME_GENERAL_BATCH_RULES,
    MALZEME_SCOPE_ONLY_CLAUSE_IDS,
    SUT_MATERIAL_LIST_PRICE_CEILING_CLAUSE_IDS,
    load_malzeme_general_header_clause_ids,
)
from scripts.sut.prose.material_bundling_titubb_uts_batch_rules import (  # noqa: E402
    TITUBB_UTS_BATCH_RULES,
)
from scripts.sut.prose.material_bundling_deferred_batch_rules import (  # noqa: E402
    GATE_B_DEFERRED_BATCH_RULES,
    GATE_B_RULE_PATCHES,
    GATE_B_STILL_DEFERRED_CLAUSE_IDS,
)
from scripts.sut.prose.material_bundling_tail_batch_rules import (  # noqa: E402
    GATE_B_TAIL_BATCH_RULES,
    KDV_PRICING_CLAUSE_IDS,
)
from scripts.sut.prose.material_bundling_r5_batch_rules import (  # noqa: E402
    R5_AMENDMENT_HEADER_CLAUSE_IDS,
    R5_BATCH_RULES,
    R5_MANIFEST_HEADER_ONLY_CLAUSE_IDS,
    R5_RULE_PATCHES,
)

_PROSE_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/material_bundling_prose.json"
_MANIFEST_PATH = (
    _PROJECT_ROOT / "data/gazette/prose_manifests/L1.4_material_bundling_encoded_manifest.json"
)


def _apply_rule_patches(rules: list[dict]) -> int:
    patched = 0
    by_id = {rule["rule_id"]: rule for rule in rules}
    all_patches = {**GATE_B_RULE_PATCHES, **CORPUS_BATCH2_RULE_PATCHES, **R5_RULE_PATCHES}
    for rule_id, patch in all_patches.items():
        rule = by_id.get(rule_id)
        if not rule:
            continue
        for clause_id in patch.get("gate_b_sources_remove") or []:
            sources = list(rule.get("gate_b_sources") or [])
            if clause_id in sources:
                sources.remove(clause_id)
                rule["gate_b_sources"] = sources
                patched += 1
        for clause_id in patch.get("gate_b_sources_append") or []:
            sources = list(rule.get("gate_b_sources") or [])
            if clause_id not in sources:
                sources.append(clause_id)
                rule["gate_b_sources"] = sources
                patched += 1
        condition_merge = patch.get("condition_merge") or {}
        if condition_merge:
            condition = rule.setdefault("condition", {})
            for key, value in condition_merge.items():
                if condition.get(key) != value:
                    condition[key] = value
                    patched += 1
        for keyword in patch.get("material_name_any_append") or []:
            condition = rule.setdefault("condition", {})
            names = list(condition.get("material_name_any") or [])
            if keyword not in names:
                names.append(keyword)
                condition["material_name_any"] = names
                patched += 1
    return patched


def main() -> None:
    payload = json.loads(_PROSE_PATH.read_text(encoding="utf-8"))
    existing_ids = {rule["rule_id"] for rule in payload.get("rules", [])}
    added = 0
    for rule in [
        *GATE_B_BATCH_RULES,
        *GATE_B_DEFERRED_BATCH_RULES,
        *GATE_B_TAIL_BATCH_RULES,
        *CORPUS_BATCH2_RULES,
        *FATURALANDIRMA_BATCH_RULES,
        *GARANTI_IHALE_BATCH_RULES,
        *EK3_LIST_BATCH_RULES,
        *MALZEME_GENERAL_BATCH_RULES,
        *TITUBB_UTS_BATCH_RULES,
        *R5_BATCH_RULES,
    ]:
        if rule["rule_id"] in existing_ids:
            continue
        payload.setdefault("rules", []).append(rule)
        existing_ids.add(rule["rule_id"])
        added += 1

    patch_count = _apply_rule_patches(payload.get("rules", []))

    sources: set[str] = set()
    for rule in payload["rules"]:
        sources.update(rule.get("gate_b_sources") or [])

    payload["coverage_note"] = (
        "Gate B partial encode: EK-3B-1/2 annex lists plus "
        f"{len(payload['rules'])} §3.1–3.2 prose rules "
        f"({added} added this merge). Full SUT corpus not encoded."
    )
    anchors = set(payload.get("sut_anchors") or [])
    for rule in GATE_B_BATCH_RULES:
        anchors.add(rule["sut_section"])
    payload["sut_anchors"] = sorted(anchors)

    _PROSE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "rules_in_json": len(payload["rules"]),
        "rules_added": added,
        "rules_patched": patch_count,
        "gate_b_sources_encoded": sorted(sources),
        "gate_b_deferred_clause_ids": sorted(GATE_B_STILL_DEFERRED_CLAUSE_IDS),
        "kdv_pricing_clause_ids": sorted(KDV_PRICING_CLAUSE_IDS),
        "separate_billing_allowlist_clause_ids": ["C001823"],
        "ek3c_list_price_ceiling_clause_ids": sorted(EK3C_LIST_PRICE_CEILING_CLAUSE_IDS),
        "sut_material_list_price_ceiling_clause_ids": sorted(
            SUT_MATERIAL_LIST_PRICE_CEILING_CLAUSE_IDS
        ),
        "corpus_ek3_annex_header_clause_ids": sorted(load_ek3_annex_header_clause_ids()),
        "corpus_ek3_scope_clause_ids": sorted(EK3_SCOPE_ONLY_CLAUSE_IDS),
        "corpus_malzeme_general_header_clause_ids": sorted(
            load_malzeme_general_header_clause_ids()
        ),
        "corpus_malzeme_scope_clause_ids": sorted(MALZEME_SCOPE_ONLY_CLAUSE_IDS),
        "r5_amendment_header_clause_ids": sorted(R5_AMENDMENT_HEADER_CLAUSE_IDS),
        "r5_manifest_header_only_clause_ids": sorted(R5_MANIFEST_HEADER_ONLY_CLAUSE_IDS),
    }
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Merged {added} rules, {patch_count} patch ops → {len(payload['rules'])} total; "
        f"{len(GATE_B_STILL_DEFERRED_CLAUSE_IDS)} still deferred"
    )
    print(f"Manifest: {_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
