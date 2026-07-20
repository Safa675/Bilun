"""Validate Bilun's specialty-restricted drug_indication rules against real ILAY data.

Mirrors ``validate_drug_rules`` but tests the prescriber_specialty dimension
instead of the diagnosis dimension. Uses ILAY's SERVISADI column as the
prescriber specialty on each DrugClaimLine.

Usage:
    cd /home/safa/Documents/Bilun
    python -m scripts.validation.validate_specialty_rules

Runtime: ~3-5 minutes (15K prescriptions, ~10ms each).
No GPU, no cloud, no external services.

Output:
    data/synthetic/sut/claims/ilay_validation/
    ├── specialty_violation_log.parquet    # one row per specialty mismatch
    └── specialty_rule_compliance.csv      # per-rule summary with top violating departments
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import date
from pathlib import Path

import polars as pl

from src.bilun.domain.prose_rules.drug_indication import (
    evaluate_drug_indication_line,
    list_drug_indication_rules,
)

from scripts.validation.claim_builder import build_claim, build_drug_line
from scripts.validation.rx_loader import load_specialty_pairs


# ──────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────

BILUN_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BILUN_ROOT / "data/synthetic/sut/claims/ilay_validation"


# ──────────────────────────────────────────────────────────────────────────
# Rule filtering — only specialty-restricted rules can fire on this dimension
# ──────────────────────────────────────────────────────────────────────────


def _filter_specialty_rules(rules: list[dict]) -> list[dict]:
    """Keep only rules with non-empty prescriber_specialties."""
    return [r for r in rules if r.get("prescriber_specialties")]


# ──────────────────────────────────────────────────────────────────────────
# Main validation loop
# ──────────────────────────────────────────────────────────────────────────


def run_validation() -> None:
    t_start = time.time()

    # 1. Load specialty pairs (prescription + department + diagnosis)
    print("=" * 60)
    print("LOADING ILAY SPECIALTY PAIRS")
    print("=" * 60)
    pairs = load_specialty_pairs()
    print(f"\nLoaded {pairs.height:,} prescription-department pairs")

    # 2. Load only specialty-restricted rules
    print("\n" + "=" * 60)
    print("LOADING SPECIALTY-RESTRICTED RULES")
    print("=" * 60)
    all_rules = list_drug_indication_rules()
    rules = _filter_specialty_rules(all_rules)
    print(f"  Total drug_indication rules: {len(all_rules):,}")
    print(f"  Specialty-restricted rules: {len(rules):,}")

    # 3. Run every prescription through the specialty rules
    print("\n" + "=" * 60)
    print("VALIDATING")
    print("=" * 60)

    rows = pairs.to_dicts()
    violations: list[dict] = []
    pass_count = 0
    error_count = 0

    t0 = time.time()
    for i, row in enumerate(rows):
        if i > 0 and i % 2000 == 0:
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(rows) - i) / rate if rate > 0 else 0
            print(
                f"  [{i:>6}/{len(rows):,}] {rate:.0f}/s, ETA {eta:.0f}s | "
                f"violations={len(violations)} pass={pass_count}",
                flush=True,
            )

        claim_id = f"SC-{i}"
        drug_line_id = f"SD-{i}"

        try:
            primary_dx = row.get("primary_icd10") or "Z00.0"  # fallback for rules without dx gate
            claim = build_claim(
                claim_id=claim_id,
                patient_id=row["patient_id"],
                primary_icd10=primary_dx,
                department=row.get("prescriber_specialty") or "bilinmiyor",
            )
            drug_line = build_drug_line(
                drug_claim_line_id=drug_line_id,
                claim_id=claim_id,
                patient_id=row["patient_id"],
                drug_name=row["drug_name"],
                drug_claim_date=row.get("prescription_date"),
                prescriber_specialty=row.get("prescriber_specialty"),
            )

            result = evaluate_drug_indication_line(
                drug_line=drug_line,
                claim=claim,
                diagnoses=[],
                rules=rules,
            )

            if result is None:
                pass_count += 1
                continue

            # Only keep prescriber_specialty_mismatch violations (this harness's scope)
            vkind = result.get("violation_kind")
            if vkind == "prescriber_specialty_mismatch":
                violations.append(
                    {
                        "drug_name": row["drug_name"],
                        "primary_icd10": primary_dx,
                        "prescriber_specialty": row.get("prescriber_specialty"),
                        "patient_id": row["patient_id"],
                        "episode_id": row.get("episode_id"),
                        **result,
                    }
                )
            else:
                # Other violation kinds (indication_mismatch, needs_report_verification)
                # are captured by item 1; we don't duplicate them here.
                pass_count += 1
        except Exception as exc:  # noqa: BLE001
            error_count += 1
            if error_count <= 5:
                print(
                    f"  ERROR on row {i} ({row['drug_name']} / "
                    f"{row.get('prescriber_specialty')}): {exc}"
                )

    elapsed = time.time() - t0
    print(f"\nValidation complete in {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    print(f"  Total prescriptions: {len(rows):,}")
    print(f"  Passed (no specialty mismatch): {pass_count:,}")
    print(f"  Specialty mismatches: {len(violations):,}")
    print(f"  Errors: {error_count:,}")

    # 4. Write outputs
    print("\n" + "=" * 60)
    print("WRITING OUTPUTS")
    print("=" * 60)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if violations:
        vdf = pl.DataFrame(violations)
        violation_path = OUTPUT_DIR / "specialty_violation_log.parquet"
        vdf.write_parquet(violation_path)
        print(f"  Violation log: {violation_path} ({vdf.height:,} rows)")

        rule_summary = _build_specialty_compliance(vdf, rules, len(rows))
        # Cast List columns to pipe-joined strings for CSV compatibility
        for col in rule_summary.columns:
            if isinstance(rule_summary.schema[col], pl.List):
                rule_summary = rule_summary.with_columns(
                    pl.col(col).list.eval(pl.element().cast(pl.Utf8)).list.join(" | ").alias(col)
                )
        rule_path = OUTPUT_DIR / "specialty_rule_compliance.csv"
        rule_summary.write_csv(rule_path)
        print(f"  Rule compliance: {rule_path} ({rule_summary.height} rules)")
    else:
        print("  No specialty mismatches found — nothing to write.")

    # 5. Print headline summary
    print("\n" + "=" * 60)
    print("HEADLINE SUMMARY")
    print("=" * 60)
    if violations:
        vdf = pl.DataFrame(violations)
        print(f"\nSeverity breakdown:")
        print(vdf.group_by("severity").len().sort("len", descending=True))
        print(f"\nTop 10 drugs by specialty-mismatch count:")
        print(vdf.group_by("drug_name").len().sort("len", descending=True).head(10))
        print(f"\nTop 10 prescribing departments by mismatch count:")
        print(
            vdf.group_by("prescriber_specialty")
            .len()
            .sort("len", descending=True)
            .head(10)
        )

    print(f"\nTotal runtime: {(time.time() - t_start) / 60:.1f} minutes")


def _build_specialty_compliance(
    vdf: pl.DataFrame, rules: list[dict], total_prescriptions: int
) -> pl.DataFrame:
    """Per-rule summary with top violating departments."""
    # Aggregate per rule
    per_rule = vdf.group_by("rule_id").agg(
        pl.len().alias("violation_count"),
        pl.col("drug_name").n_unique().alias("n_drugs_affected"),
        pl.col("prescriber_specialty").n_unique().alias("n_violating_departments"),
    )

    # Top violating departments per rule (collected separately then joined as string)
    top_depts = (
        vdf.group_by(["rule_id", "prescriber_specialty"])
        .len()
        .sort(["rule_id", "len"], descending=[False, True])
        .group_by("rule_id")
        .agg(
            pl.col("prescriber_specialty").head(5).alias("top_violating_departments"),
            pl.col("len").head(5).alias("top_dept_counts"),
        )
    )

    # Build rule metadata table
    rule_rows = []
    for rule in rules:
        rid = rule.get("rule_id", "?")
        rule_rows.append(
            {
                "rule_id": rid,
                "sut_section": rule.get("sut_section", "?"),
                "drug_tokens_sample": ", ".join(rule.get("drug_names", [])[:3]),
                "required_specialties": ", ".join(rule.get("prescriber_specialties", [])[:3]),
            }
        )

    rules_df = pl.DataFrame(rule_rows)
    merged = rules_df.join(per_rule, on="rule_id", how="left").join(
        top_depts, on="rule_id", how="left"
    )

    # Fill nulls for rules with zero violations
    merged = merged.with_columns(
        pl.when(pl.col("violation_count").is_not_null())
        .then(pl.col("violation_count"))
        .otherwise(0)
        .alias("violation_count"),
        pl.when(pl.col("n_drugs_affected").is_not_null())
        .then(pl.col("n_drugs_affected"))
        .otherwise(0)
        .alias("n_drugs_affected"),
        pl.when(pl.col("n_violating_departments").is_not_null())
        .then(pl.col("n_violating_departments"))
        .otherwise(0)
        .alias("n_violating_departments"),
    )

    # Violation rate
    merged = merged.with_columns(
        (pl.col("violation_count") / total_prescriptions * 100.0)
        .round(2)
        .alias("violation_rate_pct")
    )

    # Flag never-fired
    merged = merged.with_columns(
        (pl.col("violation_count") == 0).alias("never_fired")
    )

    return merged.sort("violation_count", descending=True)


if __name__ == "__main__":
    run_validation()
