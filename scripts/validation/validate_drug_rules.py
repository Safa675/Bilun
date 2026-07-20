"""Validate Bilun's drug_indication rules against real ILAY prescriptions.

Runs every matched prescription (≈44K) through the 967 drug_indication rules
and records what fires. Produces a violation log + per-rule compliance report.

Usage:
    cd /home/safa/Documents/Bilun
    python -m scripts.validation.validate_drug_rules

Runtime: ~5-10 minutes (pure Python regex matching, ~10ms per prescription).
No GPU, no cloud, no external services.

Output:
    data/synthetic/sut/claims/ilay_validation/
    ├── violation_log.parquet       # one row per prescription × fired rule
    └── rule_compliance.csv         # per-rule summary
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import polars as pl

from src.bilun.domain.prose_rules.drug_indication import (
    evaluate_drug_indication_line,
    list_drug_indication_rules,
)

from scripts.validation.claim_builder import build_claim, build_drug_line
from scripts.validation.rx_loader import load_drug_diagnosis_pairs


# ──────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────

BILUN_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BILUN_ROOT / "data/synthetic/sut/claims/ilay_validation"


# ──────────────────────────────────────────────────────────────────────────
# Main validation loop
# ──────────────────────────────────────────────────────────────────────────


def run_validation() -> None:
    t_start = time.time()

    # 1. Load all drug-diagnosis pairs from ILAY
    print("=" * 60)
    print("LOADING ILAY DATA")
    print("=" * 60)
    pairs = load_drug_diagnosis_pairs()
    print(f"\nLoaded {pairs.height:,} drug-diagnosis pairs")

    # 2. Load all drug_indication rules (cached after first call)
    print("\n" + "=" * 60)
    print("LOADING RULES")
    print("=" * 60)
    rules = list_drug_indication_rules()
    print(f"Loaded {len(rules):,} drug_indication rules")

    # 3. Run every prescription through the rules
    print("\n" + "=" * 60)
    print("VALIDATING")
    print("=" * 60)

    rows = pairs.to_dicts()
    violations: list[dict] = []
    pass_count = 0
    no_rule_count = 0
    error_count = 0

    t0 = time.time()
    for i, row in enumerate(rows):
        if i > 0 and i % 5000 == 0:
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(rows) - i) / rate if rate > 0 else 0
            print(
                f"  [{i:>6}/{len(rows):,}] {rate:.0f}/s, ETA {eta:.0f}s | "
                f"violations={len(violations)} pass={pass_count} no_rule={no_rule_count}",
                flush=True,
            )

        claim_id = f"C-{i}"
        drug_line_id = f"D-{i}"

        try:
            claim = build_claim(
                claim_id=claim_id,
                patient_id=row["patient_id"],
                primary_icd10=row["primary_icd10"],
                department=row.get("department") or "bilinmiyor",
            )
            drug_line = build_drug_line(
                drug_claim_line_id=drug_line_id,
                claim_id=claim_id,
                patient_id=row["patient_id"],
                drug_name=row["drug_name"],
                drug_claim_date=row.get("prescription_date"),
            )

            result = evaluate_drug_indication_line(
                drug_line=drug_line,
                claim=claim,
                diagnoses=[],
                rules=rules,
            )

            if result is None:
                # Two cases: no rule matched, or rule matched and passed
                # We can't distinguish cheaply here; treat as pass
                pass_count += 1
            else:
                violations.append(
                    {
                        "drug_name": row["drug_name"],
                        "primary_icd10": row["primary_icd10"],
                        "department": row.get("department"),
                        "patient_id": row["patient_id"],
                        "episode_id": row.get("episode_id"),
                        **result,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            error_count += 1
            if error_count <= 5:
                print(f"  ERROR on row {i} ({row['drug_name']} / {row['primary_icd10']}): {exc}")

    elapsed = time.time() - t0
    print(f"\nValidation complete in {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    print(f"  Total prescriptions: {len(rows):,}")
    print(f"  Passed (no violation): {pass_count:,}")
    print(f"  Violations/reviews: {len(violations):,}")
    print(f"  Errors: {error_count:,}")

    # 4. Write outputs
    print("\n" + "=" * 60)
    print("WRITING OUTPUTS")
    print("=" * 60)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if violations:
        vdf = pl.DataFrame(violations)
        violation_path = OUTPUT_DIR / "violation_log.parquet"
        vdf.write_parquet(violation_path)
        print(f"  Violation log: {violation_path} ({vdf.height:,} rows)")

        # Per-rule compliance summary
        rule_summary = _build_rule_compliance(vdf, len(rows))
        # Cast List columns to pipe-joined strings for CSV compatibility
        for col in rule_summary.columns:
            if isinstance(rule_summary.schema[col], pl.List):
                rule_summary = rule_summary.with_columns(
                    pl.col(col).list.eval(pl.element().cast(pl.Utf8)).list.join(" | ").alias(col)
                )
        rule_path = OUTPUT_DIR / "rule_compliance.csv"
        rule_summary.write_csv(rule_path)
        print(f"  Rule compliance: {rule_path} ({rule_summary.height} rules)")
    else:
        print("  No violations found — nothing to write.")

    # 5. Print headline summary
    print("\n" + "=" * 60)
    print("HEADLINE SUMMARY")
    print("=" * 60)
    if violations:
        vdf = pl.DataFrame(violations)
        print(f"\nViolation breakdown:")
        print(vdf.group_by("violation_kind").len().sort("len", descending=True))
        print(f"\nSeverity breakdown:")
        print(vdf.group_by("severity").len().sort("len", descending=True))
        print(f"\nTop 10 drugs by violation count:")
        print(vdf.group_by("drug_name").len().sort("len", descending=True).head(10))

    print(f"\nTotal runtime: {(time.time() - t_start) / 60:.1f} minutes")


def _build_rule_compliance(
    vdf: pl.DataFrame, total_prescriptions: int
) -> pl.DataFrame:
    """Build a per-rule summary: how many prescriptions matched, what fired."""
    rules = list_drug_indication_rules()
    # Count violations per rule_id
    per_rule = vdf.group_by("rule_id").agg(
        pl.len().alias("violation_count"),
        pl.col("violation_kind").unique().alias("violation_kinds"),
        pl.col("severity").unique().alias("severities"),
        pl.col("drug_name").n_unique().alias("n_drugs_affected"),
    )

    # Build full rule table
    rule_rows = []
    for rule in rules:
        rid = rule.get("rule_id", "?")
        section = rule.get("sut_section", "?")
        drug_tokens = rule.get("drug_names", [])
        has_icd = bool(rule.get("icd10_codes") or rule.get("icd10_ranges"))
        report_required = bool(rule.get("report_required"))
        rule_rows.append(
            {
                "rule_id": rid,
                "sut_section": section,
                "n_drug_tokens": len(drug_tokens),
                "drug_tokens_sample": ", ".join(drug_tokens[:3]),
                "has_icd_constraint": has_icd,
                "report_required": report_required,
            }
        )

    rules_df = pl.DataFrame(rule_rows)
    merged = rules_df.join(per_rule, on="rule_id", how="left").with_columns(
        pl.when(pl.col("violation_count").is_not_null())
        .then(pl.col("violation_count"))
        .otherwise(0)
        .alias("violation_count")
    )

    # Flag rules that never fired
    merged = merged.with_columns(
        (pl.col("violation_count") == 0).alias("never_fired")
    )

    return merged.sort("violation_count", descending=True)


if __name__ == "__main__":
    run_validation()
