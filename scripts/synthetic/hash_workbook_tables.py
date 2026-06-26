#!/usr/bin/env python3
"""Golden-hash check for build_workbook_tables output (excludes wall-clock manifest column)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYNTH = ROOT / "scripts" / "synthetic"
for p in (str(ROOT), str(SYNTH)):
    if p not in sys.path:
        sys.path.insert(0, p)

from generators import build_workbook_tables  # noqa: E402

DEFAULT_BASELINE = Path(__file__).resolve().parent / "gen" / "_baseline_workbook_hashes.json"


def workbook_hashes(*, num_patients: int, seed: int) -> dict[str, dict[str, object]]:
    tables = build_workbook_tables(num_patients=num_patients, seed=seed)
    out: dict[str, dict[str, object]] = {}
    for name, df in tables.items():
        if name == "veri_seti_manifestosu":
            cols = [c for c in df.columns if c != "olusturulma_zamani"]
            payload = df[cols].to_json(orient="split")
        else:
            payload = df.to_json(orient="split")
        out[name] = {
            "rows": len(df),
            "hash": hashlib.sha256(payload.encode()).hexdigest(),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-patients", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20260504)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Baseline JSON to compare against (default: gen/_baseline_workbook_hashes.json)",
    )
    parser.add_argument("--write-baseline", action="store_true", help="Overwrite baseline JSON")
    args = parser.parse_args()

    current = workbook_hashes(num_patients=args.num_patients, seed=args.seed)
    if args.write_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(f"wrote baseline {args.baseline} ({len(current)} sheets)")
        return 0

    if not args.baseline.is_file():
        print(f"baseline missing: {args.baseline}", file=sys.stderr)
        return 2

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    mismatches: list[str] = []
    for name, meta in current.items():
        ref = baseline.get(name)
        if not ref:
            mismatches.append(f"{name}: missing in baseline")
            continue
        if ref.get("rows") != meta["rows"] or ref.get("hash") != meta["hash"]:
            mismatches.append(
                f"{name}: rows {ref.get('rows')}->{meta['rows']}, "
                f"hash {str(ref.get('hash'))[:12]}->{str(meta['hash'])[:12]}"
            )

    if mismatches:
        print("HASH MISMATCH", file=sys.stderr)
        for line in mismatches:
            print(line, file=sys.stderr)
        return 1

    print(f"all {len(current)} workbook sheets match baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
