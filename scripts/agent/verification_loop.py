#!/usr/bin/env python3
"""Finans reimbursement verification loop — gate for the Reimbursement Engineer.

The Reimbursement Engineer agent runs this script as a deterministic health
check at the start of its work session. It re-runs the two finans analysis
pipelines (the hospital-code → SUT resolver, and the pricing audit), then
asserts two gates:

  1. **Crosswalk integrity** — ``finans_pricing_audit.parquet`` must contain
     zero rows flagged ``suspected_wrong_mapping``. A non-zero count means the
     frozen crosswalk has a code whose billed-vs-SUT delta is systematically
     extreme across *all* its rows (a wrong code→price mapping), which is a
     blocker for any downstream reimbursement reasoning.
  2. **Coverage floor** — the reviewed rows in
     ``data/coding/hospital_to_sut.csv`` must cover ≥ 78% of the 924 finans
     codes (the Phase 5 frozen baseline). Below that, too many codes are
     unresolved for the audit numbers to be meaningful.

The script is self-contained: it shells out to the two analysis scripts,
reads their outputs, evaluates the gates, writes a JSON summary to
``reports/agent/reimbursement/finans_loop.json`` and exits 0 (PASS) or 1
(FAIL). It never raises on a gate failure — it records the failure in the
summary so the agent can reason about it.

Run:
    .venv/bin/python scripts/agent/verification_loop.py
    .venv/bin/python scripts/agent/verification_loop.py --quiet
    .venv/bin/python scripts/agent/verification_loop.py --output /tmp/finans_loop.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CODER_SCRIPT = PROJECT_ROOT / "scripts" / "analysis" / "run_finans_coder.py"
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "analysis" / "finans_pricing_audit.py"
AUDIT_PARQUET = PROJECT_ROOT / "data" / "finans_pricing_audit.parquet"
HOSPITAL_CROSSWALK = PROJECT_ROOT / "data" / "coding" / "hospital_to_sut.csv"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "reports" / "agent" / "reimbursement" / "finans_loop.json"
)

PYTHON = sys.executable
FINANS_CODE_UNIVERSE = 924
COVERAGE_FLOOR = 0.78
# Column in finans_pricing_audit.parquet that marks a row as a suspected
# wrong crosswalk mapping (Boolean, populated by flag_wrong_mappings()).
WRONG_MAPPING_COLUMN = "suspected_wrong_mapping"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Finans reimbursement verification loop (Reimbursement agent gate)."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JSON summary output path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-step progress output (the PASS/FAIL summary always prints).",
    )
    return parser


def _run_step(script: Path, quiet: bool) -> tuple[int, str]:
    """Run an analysis script as a subprocess, capturing stdout + exit code.

    Returns (exit_code, stdout_tail). stdout_tail is the last ~2000 chars of
    captured stdout, included in the JSON summary so the agent can inspect the
    pipeline output without re-running it.
    """
    if not script.exists():
        raise FileNotFoundError(f"analysis script missing: {script}")
    proc = subprocess.run(
        [PYTHON, str(script)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    stdout = proc.stdout or ""
    if proc.returncode != 0 and not quiet:
        sys.stderr.write(
            f"[verification_loop] {script.name} exited {proc.returncode}\n"
        )
        if proc.stderr:
            sys.stderr.write(proc.stderr[-2000:] + "\n")
    tail = stdout[-2000:]
    return proc.returncode, tail


def _count_wrong_mappings(parquet_path: Path) -> int:
    """Count rows flagged as suspected wrong crosswalk mappings.

    ``finans_pricing_audit.flag_wrong_mappings()`` populates the boolean
    ``suspected_wrong_mapping`` column. We count True rows (not distinct codes)
    because every flagged row is a billing line whose reimbursement conclusion
    is unreliable until the crosswalk is fixed.
    """
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"audit parquet missing: {parquet_path}. "
            "finans_pricing_audit.py should have written it."
        )
    df = pl.read_parquet(parquet_path, columns=[WRONG_MAPPING_COLUMN])
    if WRONG_MAPPING_COLUMN not in df.columns:
        raise KeyError(
            f"expected '{WRONG_MAPPING_COLUMN}' column in {parquet_path}; "
            f"got {df.columns}"
        )
    if df.schema[WRONG_MAPPING_COLUMN] != pl.Boolean:
        # Defensive: tolerate a stringified bool column without failing the gate
        # on a schema drift — but still surface it loudly via the count.
        return int(df.filter(pl.col(WRONG_MAPPING_COLUMN)).height)
    return int(df.filter(pl.col(WRONG_MAPPING_COLUMN)).height)


def _coverage_pct(crosswalk_csv: Path) -> float:
    """Reviewed-true rows / 924, as a fraction in [0, 1].

    Mirrors finans_pricing_audit.load_frozen_crosswalk's reviewed parsing so
    the two scripts agree on what counts as "reviewed" regardless of how
    polars typed the column.
    """
    if not crosswalk_csv.exists():
        raise FileNotFoundError(f"hospital crosswalk missing: {crosswalk_csv}")
    df = pl.read_csv(crosswalk_csv, columns=["reviewed"])
    if df.schema["reviewed"] == pl.Boolean:
        reviewed = df.filter(pl.col("reviewed")).height
    else:
        reviewed = df.filter(
            pl.col("reviewed").str.to_lowercase() == "true"
        ).height
    return reviewed / FINANS_CODE_UNIVERSE


def main() -> int:
    args = _build_parser().parse_args()
    log = (lambda *a: None) if args.quiet else (lambda *a: print(*a))

    log("[verification_loop] running run_finans_coder.py …")
    coder_rc, coder_tail = _run_step(CODER_SCRIPT, args.quiet)
    log(f"[verification_loop] run_finans_coder.py exited {coder_rc}")

    log("[verification_loop] running finans_pricing_audit.py …")
    audit_rc, _audit_tail = _run_step(AUDIT_SCRIPT, args.quiet)
    log(f"[verification_loop] finans_pricing_audit.py exited {audit_rc}")

    failures: list[str] = []
    if coder_rc != 0:
        failures.append(f"run_finans_coder.py exited {coder_rc}")
    if audit_rc != 0:
        failures.append(f"finans_pricing_audit.py exited {audit_rc}")

    coverage = _coverage_pct(HOSPITAL_CROSSWALK)
    wrong_mappings = _count_wrong_mappings(AUDIT_PARQUET)

    if wrong_mappings != 0:
        failures.append(
            f"suspected_wrong_mappings == {wrong_mappings} (expected 0)"
        )
    if coverage < COVERAGE_FLOOR:
        failures.append(
            f"coverage {coverage:.4f} < floor {COVERAGE_FLOOR}"
        )

    passed = len(failures) == 0
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "coverage_pct": round(coverage, 6),
        "coverage_floor": COVERAGE_FLOOR,
        "suspected_wrong_mappings": wrong_mappings,
        "wrong_mapping_column": WRONG_MAPPING_COLUMN,
        "finans_code_universe": FINANS_CODE_UNIVERSE,
        "coder_exit_code": coder_rc,
        "audit_exit_code": audit_rc,
        "coder_stdout_tail": coder_tail,
        "passed": passed,
        "failures": failures,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    verdict = "PASS" if passed else "FAIL"
    try:
        out_display = str(args.output.relative_to(PROJECT_ROOT))
    except ValueError:
        out_display = str(args.output)
    print(
        f"[verification_loop] {verdict} — "
        f"coverage={coverage:.1%} (floor {COVERAGE_FLOOR:.0%}), "
        f"suspected_wrong_mappings={wrong_mappings}, "
        f"failures={len(failures)} -> {out_display}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
