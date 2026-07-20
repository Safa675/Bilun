"""Generate Bilun-format golden test cases from validated ILAY prescriptions.

Reads the violation_log produced by validate_drug_rules.py and extracts
clean, hand-verifiable test cases in the same JSON format Bilun's existing
golden tests use (see data/gazette/prose_rules/golden/drug_indication_4.2.*.json).

These become permanent regression tests for Bilun's CI pipeline — real-world
test cases that replace synthetic data.

Usage:
    cd /home/safa/Documents/Bilun
    python -m scripts.validation.build_golden_dataset
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import polars as pl

BILUN_ROOT = Path(__file__).resolve().parents[2]
VIOLATION_LOG = BILUN_ROOT / "data/synthetic/sut/claims/ilay_validation/violation_log.parquet"
SPECIALTY_VIOLATION_LOG = (
    BILUN_ROOT / "data/synthetic/sut/claims/ilay_validation/specialty_violation_log.parquet"
)
OUTPUT_DIR = BILUN_ROOT / "data/gazette/prose_rules/golden/ilay"

# How many samples per (drug, violation_kind) combination
MAX_SAMPLES_PER_COMBO = 3

# Minimum prescriptions to bother extracting a golden case
MIN_PRESCRIPTIONS_FOR_GOLDEN = 2


def build_golden_dataset() -> None:
    """Extract golden test cases from the violation log."""
    if not VIOLATION_LOG.exists():
        print(f"ERROR: Violation log not found at {VIOLATION_LOG}")
        print("Run validate_drug_rules.py first.")
        return

    vdf = pl.read_parquet(VIOLATION_LOG)
    print(f"Loaded {vdf.height:,} violations from {VIOLATION_LOG.name}")

    # Group by (rule_id, violation_kind) and pick representative samples
    # We want: for each rule, one sample of each violation_kind it produced
    samples_by_rule: dict[str, list[dict]] = defaultdict(list)
    seen_combos: set[tuple[str, str, str]] = set()  # (rule_id, violation_kind, drug_name)

    for row in vdf.to_dicts():
        rule_id = row.get("rule_id", "?")
        vkind = row.get("violation_kind", "?")
        drug = row.get("drug_name", "?")
        combo = (rule_id, vkind, drug)

        if combo in seen_combos:
            continue
        if len(samples_by_rule[rule_id]) >= MAX_SAMPLES_PER_COMBO * 4:
            continue

        seen_combos.add(combo)
        sample = {
            "rule_id": rule_id,
            "drug_name": drug,
            "primary_icd10": row.get("primary_icd10", ""),
            # expect_violation matches what the engine produced
            "expect_violation": vkind,
            "source": "ilay_real_data",
            "department": row.get("department"),
            "severity": row.get("severity"),
        }
        samples_by_rule[rule_id].append(sample)

    # Group samples by SUT section for organized output files
    section_samples: dict[str, list[dict]] = defaultdict(list)
    for rule_id, samples in samples_by_rule.items():
        # Extract section from rule_id (e.g. "4.2.1.xxx" → "4.2.1")
        parts = rule_id.split(".")
        if len(parts) >= 3:
            section = ".".join(parts[:3])
        else:
            section = "misc"
        section_samples[section].extend(samples)

    # Write one golden file per section
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total_written = 0
    for section, samples in sorted(section_samples.items()):
        if len(samples) < MIN_PRESCRIPTIONS_FOR_GOLDEN:
            continue
        safe_section = section.replace(".", "_")
        out_path = OUTPUT_DIR / f"drug_indication_ilay_{safe_section}.json"
        payload = {
            "source": "ILAY real prescription data",
            "generated_by": "scripts/validation/build_golden_dataset.py",
            "section": section,
            "sample_count": len(samples),
            "samples": samples,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        total_written += len(samples)
        print(f"  {out_path.name}: {len(samples)} samples")

    print(f"\nTotal golden samples written: {total_written}")
    print(f"Output directory: {OUTPUT_DIR}")

    # Also write a summary of what we found
    print("\n" + "=" * 60)
    print("GOLDEN DATASET SUMMARY")
    print("=" * 60)
    print(f"Rules with ≥1 golden sample: {len(samples_by_rule)}")
    print(f"Total samples: {total_written}")

    # Violation kind distribution in golden set
    all_samples = [s for samples in samples_by_rule.values() for s in samples]
    kind_counts: dict[str, int] = defaultdict(int)
    for s in all_samples:
        kind_counts[s["expect_violation"]] += 1
    print("\nViolation kind distribution in golden set:")
    for kind, count in sorted(kind_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {kind}: {count}")


def build_specialty_golden_dataset() -> None:
    """Extract golden test cases for prescriber_specialty_mismatch violations.

    Mirrors ``build_golden_dataset`` but reads the specialty violation log
    and emits cases tagged with ``expect_violation: prescriber_specialty_mismatch``.
    Output files are named ``specialty_ilay_*.json`` to distinguish from item 1.

    Usage:
        python -m scripts.validation.build_golden_dataset --specialty
    """
    if not SPECIALTY_VIOLATION_LOG.exists():
        print(f"ERROR: Specialty violation log not found at {SPECIALTY_VIOLATION_LOG}")
        print("Run validate_specialty_rules.py first.")
        return

    vdf = pl.read_parquet(SPECIALTY_VIOLATION_LOG)
    print(f"Loaded {vdf.height:,} specialty violations from {SPECIALTY_VIOLATION_LOG.name}")

    # Group by (rule_id, department) — we want one sample per violating department per rule
    samples_by_rule: dict[str, list[dict]] = defaultdict(list)
    seen_combos: set[tuple[str, str, str]] = set()  # (rule_id, department, drug_name)

    for row in vdf.to_dicts():
        rule_id = row.get("rule_id", "?")
        drug = row.get("drug_name", "?")
        dept = row.get("prescriber_specialty", "?")
        combo = (rule_id, dept, drug)

        if combo in seen_combos:
            continue
        if len(samples_by_rule[rule_id]) >= MAX_SAMPLES_PER_COMBO * 2:
            continue

        seen_combos.add(combo)
        sample = {
            "rule_id": rule_id,
            "drug_name": drug,
            "primary_icd10": row.get("primary_icd10", ""),
            "prescriber_specialty": dept,
            "expect_violation": "prescriber_specialty_mismatch",
            "source": "ilay_real_data",
            "severity": row.get("severity"),
        }
        samples_by_rule[rule_id].append(sample)

    # Group by SUT section for organized output files
    section_samples: dict[str, list[dict]] = defaultdict(list)
    for rule_id, samples in samples_by_rule.items():
        parts = rule_id.split(".")
        if len(parts) >= 3:
            section = ".".join(parts[:3])
        else:
            section = "misc"
        section_samples[section].extend(samples)

    # Write one golden file per section, named specialty_ilay_* to distinguish
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total_written = 0
    for section, samples in sorted(section_samples.items()):
        if len(samples) < 1:
            continue
        safe_section = section.replace(".", "_")
        out_path = OUTPUT_DIR / f"specialty_ilay_{safe_section}.json"
        payload = {
            "source": "ILAY real prescription data (specialty scope audit)",
            "generated_by": "scripts/validation/build_golden_dataset.py --specialty",
            "section": section,
            "violation_kind": "prescriber_specialty_mismatch",
            "sample_count": len(samples),
            "samples": samples,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        total_written += len(samples)
        print(f"  {out_path.name}: {len(samples)} samples")

    print(f"\nTotal specialty golden samples written: {total_written}")
    print(f"Output directory: {OUTPUT_DIR}")

    print("\n" + "=" * 60)
    print("SPECIALTY GOLDEN DATASET SUMMARY")
    print("=" * 60)
    print(f"Rules with ≥1 golden sample: {len(samples_by_rule)}")
    print(f"Total samples: {total_written}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--specialty":
        build_specialty_golden_dataset()
    else:
        build_golden_dataset()
