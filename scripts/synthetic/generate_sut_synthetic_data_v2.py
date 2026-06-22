#!/usr/bin/env python3
"""Generate the v2 SUT synthetic reimbursement dataset.

Parameterized, scalable generator producing claim data that exercises all
BILUN reimbursement surfaces: billing (lab, drug, copay, materials), alerts
(surcharge, copay rates), optimizer per-row data, and DRG pricing.

Outputs:
    data/synthetic/sut/sentetik_sut_v2.xlsx
    data/synthetic/sut/clean/*.parquet
    data/synthetic/sut/claims/*.parquet
    data/synthetic/demo_cohort_tiers.json
    data/synthetic/DEMO_COHORT.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from constants import DEFAULT_OUTPUT_DIR, SEED
from cohort_tiers import build_cohort_tier_report, write_cohort_tier_artifacts
from generators import build_workbook_tables
from exporters import _write_claim_exports, _write_clean_exports, _write_workbook


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate SUT synthetic v2 data")
    parser.add_argument("--num-patients", type=int, default=50)
    parser.add_argument("--min-claims-per-patient", type=int, default=1)
    parser.add_argument("--max-claims-per-patient", type=int, default=5)
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip validate_sut_synthetic_data and assert_tier_a_post_regen",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = build_workbook_tables(
        num_patients=args.num_patients,
        min_claims_per_patient=args.min_claims_per_patient,
        max_claims_per_patient=args.max_claims_per_patient,
        seed=args.seed,
    )

    dataset_id = f"sentetik_sut_v2_{args.num_patients}_hasta"
    workbook_path = output_dir / f"{dataset_id}.xlsx"
    _write_workbook(tables, workbook_path)
    _write_clean_exports(tables, output_dir)
    _write_claim_exports(tables, output_dir)

    tier_report = build_cohort_tier_report(
        num_patients=args.num_patients,
        seed=args.seed,
        dataset_id=dataset_id,
    )
    tier_json, tier_md = write_cohort_tier_artifacts(
        synthetic_root=output_dir.parent,
        report=tier_report,
    )

    print("=" * 72)
    print(f"Dataset: {dataset_id}")
    print(f"Workbook: {workbook_path}")
    print(f"Clean exports: {output_dir / 'clean'}")
    print(f"Claim exports: {output_dir / 'claims'}")
    print(f"Patients: {len(tables['hastalar'])}")
    print(f"Episodes: {len(tables['basvurular'])}")
    print(f"Claims: {len(tables['fatura_basliklari'])}")
    print(f"Procedure lines: {len(tables['islem_fatura_satirlari'])}")
    print(f"Material lines: {len(tables['malzeme_fatura_satirlari'])}")
    print(f"Drug lines: {len(tables['ilac_fatura_satirlari'])}")
    print(f"Lab rows: {len(tables['laboratuvar_sonuclari'])}")
    print(f"Diagnoses: {len(tables['tani_satirlari'])}")
    print(f"Expected outputs: {len(tables['beklenen_kural_ciktilari'])}")
    print(f"Prescriptions: {len(tables['receteler'])}")
    print(f"Demo cohort tiers: {tier_json}")
    print(f"Demo cohort guide: {tier_md}")
    print("=" * 72)

    if not args.skip_checks:
        import subprocess

        validate_script = Path(__file__).resolve().parent / "validate_sut_synthetic_data.py"
        assert_script = Path(__file__).resolve().parent / "assert_tier_a_post_regen.py"
        subprocess.run(
            [sys.executable, str(validate_script), "--data-dir", str(output_dir)],
            check=True,
            timeout=600,
        )
        subprocess.run(
            [sys.executable, str(assert_script), "--data-dir", str(output_dir)],
            check=True,
            timeout=600,
        )
        print("Post-regen checks passed (validate + Tier A assert)")


if __name__ == "__main__":
    main()
