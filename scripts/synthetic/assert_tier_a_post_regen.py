#!/usr/bin/env python3
"""Post-regeneration Tier A showcase asserts (P1.1 acceptance + golden bands).

Run after:
  python scripts/synthetic/generate_sut_synthetic_data_v2.py
  python scripts/synthetic/validate_sut_synthetic_data.py

Optional cache rebuild:
  python scripts/bilun/build_cache.py --activate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_SYNTHETIC = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPTS_SYNTHETIC) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_SYNTHETIC))

from demo_config import (  # noqa: E402
    load_demo_manifest,
    tier_a_patient_ids,
    vignette_for_scenario_tag,
)
from fault_injection import is_ghost_package_line  # noqa: E402

DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "synthetic" / "sut"
TOLERANCE_TRY = 0.02


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assert Tier A showcase credibility after synthetic regen",
    )
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Synthetic SUT data directory (parquet claims/)",
    )
    return parser.parse_args()


def _error(errors: list[str], message: str) -> None:
    errors.append(message)
    print(f"ERROR: {message}")


def _strings(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _claim_by_scenario_tag(ctx, scenario_tag: str):
    for claim in ctx.claims:
        if claim.scenario_tag == scenario_tag:
            return claim
    return None


def _assert_default_landing(manifest: dict, errors: list[str]) -> None:
    landing = str(manifest.get("default_landing_index") or "").strip()
    if not landing:
        _error(errors, "demo_manifest.json missing default_landing_index")
        return
    scenario_by_index = manifest.get("scenario_by_index") or {}
    if landing not in scenario_by_index:
        _error(
            errors,
            f"default_landing_index {landing!r} not in scenario_by_index",
        )
    vignette = vignette_for_scenario_tag(scenario_by_index.get(landing, ""))
    if vignette is None and landing in scenario_by_index:
        _error(errors, f"No vignette for default landing index {landing}")


def _assert_showcase_claim_lines(
    *,
    patient_id: str,
    scenario_tag: str,
    claim_id: str,
    procedures: pd.DataFrame,
    materials: pd.DataFrame,
    drugs: pd.DataFrame,
    claim_header: pd.Series,
    errors: list[str],
) -> None:
    claim_procs = procedures[_strings(procedures["claim_id"]) == claim_id]
    claim_mats = materials[_strings(materials["claim_id"]) == claim_id]
    claim_drugs = drugs[_strings(drugs["claim_id"]) == claim_id]

    for _, row in claim_procs.iterrows():
        billed = float(row.get("billed_amount_try") or 0)
        payable = float(row.get("expected_payable_try") or 0)
        if is_ghost_package_line(
            procedure_category=str(row.get("procedure_category", "")),
            billed_amount_try=billed,
            expected_payable_try=payable,
        ):
            _error(
                errors,
                f"{patient_id} showcase {claim_id}: ghost package line {row.get('procedure_code')}",
            )
        if billed <= 0 and payable > TOLERANCE_TRY:
            _error(
                errors,
                f"{patient_id} showcase {claim_id}: billed=0 payable>0 on "
                f"{row.get('procedure_code')} ({payable})",
            )

    header_billed = float(claim_header.get("expected_total_billed_try") or 0)
    header_payable = float(claim_header.get("expected_total_payable_try") or 0)
    line_billed = (
        float(claim_procs["billed_amount_try"].fillna(0).sum())
        + float(claim_mats["billed_amount_try"].fillna(0).sum())
        + float(claim_drugs["billed_amount_try"].fillna(0).sum())
    )
    line_payable = (
        float(claim_procs["expected_payable_try"].fillna(0).sum())
        + float(claim_mats["expected_payable_try"].fillna(0).sum())
        + float(claim_drugs["expected_payable_try"].fillna(0).sum())
    )
    if abs(header_billed - line_billed) > TOLERANCE_TRY:
        _error(
            errors,
            f"{patient_id} showcase {claim_id}: header billed {header_billed} != lines {line_billed}",
        )
    if abs(header_payable - line_payable) > TOLERANCE_TRY:
        _error(
            errors,
            f"{patient_id} showcase {claim_id}: header payable {header_payable} != lines {line_payable}",
        )


def _assert_expected_rule_output_sync(
    expected: pd.DataFrame,
    claim_id: str,
    header_payable: float,
    errors: list[str],
) -> None:
    claim_expected = expected[
        (_strings(expected["claim_id"]) == claim_id)
        & (_strings(expected["line_type"]) == "fatura")
        & (_strings(expected["line_id"]) == "")
    ]
    if claim_expected.empty:
        _error(errors, f"Missing claim-level expected_rule_output for {claim_id}")
        return
    row = claim_expected.iloc[0]
    expected_payable = float(row.get("expected_payable_try") or 0)
    if abs(expected_payable - header_payable) > TOLERANCE_TRY:
        _error(
            errors,
            f"expected_rule_outputs payable {expected_payable} != header {header_payable} "
            f"for {claim_id}",
        )


def _assert_optional_override_strategy(
    patient_id: str,
    scenario_tag: str,
    dataset,
    errors: list[str],
) -> None:
    from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
    from src.bilun.domain.claims import build_patient_claim_context

    vignette = vignette_for_scenario_tag(scenario_tag)
    if vignette is None or vignette.golden is None:
        return

    ctx = build_patient_claim_context(patient_id, dataset)
    if ctx is None:
        _error(errors, f"Could not build claim context for {patient_id}")
        return

    demo_claim = _claim_by_scenario_tag(ctx, scenario_tag)
    if demo_claim is None:
        _error(errors, f"{patient_id} missing showcase claim for {scenario_tag}")
        return

    api_procs = [
        line
        for line in ctx.procedure_lines
        if line.claim_id == demo_claim.claim_id
    ]
    for line in api_procs:
        if float(line.billed_amount_try) <= 0 and float(line.expected_payable_try) > TOLERANCE_TRY:
            _error(
                errors,
                f"API parity: {patient_id} {line.procedure_code} billed=0 payable>0",
            )

    report = compute_patient_billing_report(
        patient_id,
        claim_context=ctx,
        copay_exemption={"exempt": False},
    )
    rows = [
        row
        for row in report.billing_strategy.optional_override_opportunities
        if row.get("claim_id") == demo_claim.claim_id
    ]
    if not rows:
        _error(errors, f"{patient_id} missing optional_override strategy row")
        return
    row = rows[0]
    savings = float(row.get("savings_try") or 0)
    if savings <= 0:
        _error(errors, f"{patient_id} optional_override savings_try must be > 0")
    if not vignette.golden.contains(
        savings=savings,
        package_total=float(row.get("package_total_try") or 0),
        itemized_total=float(row.get("itemized_total_try") or 0),
    ):
        _error(
            errors,
            f"{patient_id} golden band mismatch: savings={savings}, "
            f"package={row.get('package_total_try')}, itemized={row.get('itemized_total_try')}",
        )


def run_assertions(data_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest = load_demo_manifest()
    scenario_by_index = manifest.get("scenario_by_index") or {}

    _assert_default_landing(manifest, errors)

    claims_dir = data_dir / "claims"
    headers = pd.read_parquet(claims_dir / "claim_headers.parquet")
    procedures = pd.read_parquet(claims_dir / "procedure_claim_lines.parquet")
    materials = pd.read_parquet(claims_dir / "material_claim_lines.parquet")
    drugs = pd.read_parquet(claims_dir / "drug_claim_lines.parquet")
    expected = pd.read_parquet(claims_dir / "expected_rule_outputs.parquet")

    from src.bilun.domain.claims import load_sut_claim_dataset

    dataset = load_sut_claim_dataset(claims_dir=claims_dir)

    for patient_id in sorted(tier_a_patient_ids()):
        index = patient_id.rsplit("-", 1)[-1]
        scenario_tag = scenario_by_index.get(index)
        if not scenario_tag:
            _error(errors, f"Tier A patient {patient_id} missing scenario_by_index entry")
            continue

        patient_claims = headers[_strings(headers["patient_id"]) == patient_id]
        showcase = patient_claims[_strings(patient_claims["scenario_tag"]) == scenario_tag]
        if showcase.empty:
            _error(errors, f"Tier A patient {patient_id} missing showcase claim {scenario_tag!r}")
            continue

        claim_row = showcase.iloc[0]
        claim_id = str(claim_row["claim_id"])
        _assert_showcase_claim_lines(
            patient_id=patient_id,
            scenario_tag=scenario_tag,
            claim_id=claim_id,
            procedures=procedures,
            materials=materials,
            drugs=drugs,
            claim_header=claim_row,
            errors=errors,
        )
        _assert_expected_rule_output_sync(
            expected,
            claim_id,
            float(claim_row.get("expected_total_payable_try") or 0),
            errors,
        )

        if scenario_tag.startswith("sgk_optional_override_"):
            _assert_optional_override_strategy(patient_id, scenario_tag, dataset, errors)

    return errors


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    print("=" * 72)
    print(f"Tier A post-regen asserts: {data_dir}")
    errors = run_assertions(data_dir)
    print("=" * 72)
    if errors:
        print(f"FAILED with {len(errors)} error(s)")
        raise SystemExit(1)
    print("All Tier A post-regen asserts passed")


if __name__ == "__main__":
    main()
