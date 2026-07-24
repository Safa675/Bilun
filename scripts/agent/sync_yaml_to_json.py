#!/usr/bin/env python3
"""Sync YAML rule sources to match committed JSON rule files.

The previous run modified JSON files directly (clause ref replacements +
superseded_sources). This script propagates those changes back to the YAML
source files so that compile_rules.py --check and the YAML↔JSON parity tests
pass.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
_SOURCES_DIR = _PROJECT_ROOT / "data/gazette/prose_rule_sources"

# rule_set_id → YAML family subdirectory
FAMILY_MAP: dict[str, str] = {
    "anti_vegf_prose": "anti_vegf",
    "definitions_2_6": "definitions_2_6",
    "drug_combination_4_2": "drug_combination_4_2",
    "drug_indication_prose": "drug_indication",
    "gap_closing_misc": "gap_closing_misc",
    "gap_closing_treatment_2": "gap_closing_treatment_2",
    "material_bundling_prose": "material_bundling",
    "specialty_materials_prose": "specialty_materials",
    "treatment_pricing_2_4": "treatment_pricing_2_4",
}


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:
        return True


def _dump_yaml(payload: dict) -> str:
    return yaml.dump(
        payload,
        Dumper=_NoAliasDumper,
        sort_keys=False,
        allow_unicode=True,
        width=120,
        default_flow_style=False,
    )


def sync_family(rule_set_id: str, family_dir: str) -> dict:
    """Update YAML files so their rules match the committed JSON."""
    json_path = _RULES_DIR / f"{rule_set_id}.json"
    yaml_dir = _SOURCES_DIR / family_dir

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    json_rules = payload.get("rules") or []

    # Build rule_id → rule lookup from JSON
    json_by_id: dict[str, dict] = {}
    for rule in json_rules:
        rid = str(rule.get("rule_id") or "")
        if rid:
            json_by_id[rid] = dict(rule)

    # Group JSON rules by sut_section for file-level writes
    json_by_section: dict[str, list[dict]] = defaultdict(list)
    for rule in json_rules:
        section = str(rule.get("sut_section") or "")
        json_by_section[section].append(dict(rule))

    updated_files = 0
    updated_rules = 0
    missing_from_yaml: list[str] = []

    for yaml_path in sorted(yaml_dir.glob("*.yaml")):
        raw = yaml_path.read_text(encoding="utf-8")
        yaml_data = yaml.safe_load(raw)
        if not isinstance(yaml_data, dict):
            continue

        section_id = str(yaml_data.get("section_id") or "")
        old_rules = yaml_data.get("rules") or []

        # Match each YAML rule to its JSON counterpart by rule_id.
        # Only UPDATE field values — never append. The YAML already contains
        # the canonical rule_id set; appending would create cross-file duplicates.
        new_rules: list[dict] = []
        file_changed = False
        for rule in old_rules:
            rid = str(rule.get("rule_id") or "")
            if rid in json_by_id:
                json_rule = json_by_id[rid]
                if dict(rule) != json_rule:
                    file_changed = True
                    updated_rules += 1
                new_rules.append(json_rule)
            else:
                new_rules.append(dict(rule))

        if file_changed:
            out_data: dict = {"section_id": yaml_data.get("section_id", section_id)}
            if "source_note" in yaml_data:
                out_data["source_note"] = yaml_data["source_note"]
            out_data["rules"] = new_rules
            yaml_path.write_text(_dump_yaml(out_data), encoding="utf-8")
            updated_files += 1
            print(f"  ✓ {family_dir}/{yaml_path.name}: synced")

    # Report any JSON rules not found in any YAML file
    all_yaml_rids: set[str] = set()
    for yaml_path in sorted(yaml_dir.glob("*.yaml")):
        yaml_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        for rule in (yaml_data.get("rules") or []):
            all_yaml_rids.add(str(rule.get("rule_id") or ""))

    for rid in json_by_id:
        if rid not in all_yaml_rids:
            missing_from_yaml.append(rid)

    return {
        "updated_files": updated_files,
        "updated_rules": updated_rules,
        "missing_from_yaml": missing_from_yaml,
    }


def main() -> None:
    print("Syncing YAML sources to match committed JSON...")
    total_files = 0
    total_rules = 0
    all_missing: list[str] = []
    for rule_set_id, family_dir in sorted(FAMILY_MAP.items()):
        stats = sync_family(rule_set_id, family_dir)
        total_files += stats["updated_files"]
        total_rules += stats["updated_rules"]
        if stats["missing_from_yaml"]:
            all_missing.extend(
                f"{rule_set_id}:{rid}" for rid in stats["missing_from_yaml"]
            )
        if stats["updated_files"]:
            print(
                f"  {rule_set_id}: {stats['updated_files']} files, "
                f"{stats['updated_rules']} rules synced"
            )
    print(f"\nTotal: {total_files} files, {total_rules} rules synced")
    if all_missing:
        print(f"WARNING: {len(all_missing)} JSON rules not found in YAML:")
        for rid in all_missing[:20]:
            print(f"  {rid}")
        if len(all_missing) > 20:
            print(f"  ... {len(all_missing) - 20} more")


if __name__ == "__main__":
    main()
