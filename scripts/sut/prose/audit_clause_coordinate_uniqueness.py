"""Track A0 — uniqueness audit for clause_coordinate (god plan).

Usage:
  python -m scripts.sut.prose.audit_clause_coordinate_uniqueness
  python -m scripts.sut.prose.audit_clause_coordinate_uniqueness --markdown
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from scripts.sut.prose.clause_identity import ENCODE_ELIGIBLE_TYPES, filter_encode_eligible

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CLAUSES = _ROOT / "data" / "gazette" / "sut_clauses.parquet"


def _dup_table(frame: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    return (
        frame.group_by(keys)
        .len()
        .filter(pl.col("len") > 1)
        .sort("len", descending=True)
    )


def run_audit(clauses_path: Path) -> dict[str, object]:
    df = pl.read_parquet(clauses_path)
    null_coord = df.filter(pl.col("clause_coordinate").is_null())
    eligible = filter_encode_eligible(df)
    section_only = df.filter(
        pl.col("clause_coordinate").is_not_null()
        & pl.col("clause_number").is_null()
        & pl.col("clause_letter").is_null()
    )

    def dup_stats(src: pl.DataFrame, keys: list[str]) -> dict[str, int]:
        d = _dup_table(src, keys)
        return {
            "duplicate_key_groups": int(d.height),
            "max_group_size": int(d["len"].max()) if d.height else 0,
            "extra_rows_beyond_one": int(d["len"].sum() - d.height) if d.height else 0,
        }

    eligible_by_type = {
        t: dup_stats(eligible.filter(pl.col("clause_type") == t), ["clause_coordinate"])
        for t in sorted(ENCODE_ELIGIBLE_TYPES)
    }

    top_eligible_dups = (
        _dup_table(eligible, ["clause_coordinate", "clause_type"])
        .head(10)
        .to_dicts()
    )

    in_force_types = (
        df.filter(pl.col("is_in_force") == True)  # noqa: E712
        .group_by("clause_type")
        .len()
        .sort("len", descending=True)
        .to_dicts()
    )

    return {
        "clauses_path": str(clauses_path),
        "total_rows": df.height,
        "null_coordinate_rows": null_coord.height,
        "null_coordinate_types": null_coord.group_by("clause_type").len().to_dicts(),
        "section_only_coordinate_rows": section_only.height,
        "encode_eligible_rows": eligible.height,
        "dup_by_coordinate": dup_stats(df.filter(pl.col("clause_coordinate").is_not_null()), ["clause_coordinate"]),
        "dup_by_coordinate_is_in_force": dup_stats(
            df.filter(pl.col("clause_coordinate").is_not_null()),
            ["clause_coordinate", "is_in_force"],
        ),
        "dup_encode_eligible_by_coordinate": dup_stats(eligible, ["clause_coordinate"]),
        "dup_encode_eligible_by_coordinate_type": dup_stats(
            eligible, ["clause_coordinate", "clause_type"]
        ),
        "dup_encode_eligible_by_type": eligible_by_type,
        "top_encode_eligible_collisions": top_eligible_dups,
        "in_force_clause_type_census": in_force_types,
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# A0 uniqueness audit — `clause_coordinate`",
        "",
        f"Source: `{report['clauses_path']}`",
        "",
        "## Headline counts",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| Total parquet rows | {report['total_rows']} |",
        f"| Null `clause_coordinate` | {report['null_coordinate_rows']} |",
        f"| Section-only coordinates (no fıkra/bent) | {report['section_only_coordinate_rows']} |",
        f"| Encode-eligible (D4) | {report['encode_eligible_rows']} |",
        "",
        "## Duplicate keys",
        "",
        "| Key | Duplicate groups | Max group | Extra rows |",
        "|-----|-----------------:|----------:|-----------:|",
    ]
    for label, key in (
        ("clause_coordinate", "dup_by_coordinate"),
        ("coordinate + is_in_force", "dup_by_coordinate_is_in_force"),
        ("encode-eligible coordinate", "dup_encode_eligible_by_coordinate"),
        ("encode-eligible coordinate + type", "dup_encode_eligible_by_coordinate_type"),
    ):
        d = report[key]  # type: ignore[index]
        lines.append(
            f"| {label} | {d['duplicate_key_groups']} | {d['max_group_size']} | {d['extra_rows_beyond_one']} |"
        )

    lines.extend(
        [
            "",
            "## Encode-eligible collisions by clause_type",
            "",
            "| clause_type | Dup groups | Max |",
            "|-------------|-----------:|----:|",
        ]
    )
    by_type = report["dup_encode_eligible_by_type"]  # type: ignore[assignment]
    assert isinstance(by_type, dict)
    for t, d in by_type.items():
        lines.append(f"| {t} | {d['duplicate_key_groups']} | {d['max_group_size']} |")

    lines.extend(
        [
            "",
            "## Top encode-eligible collisions",
            "",
            "These are why dual-read must **fail loud** on ambiguous coordinates "
            "(Track A3) and why `C*` remains valid for collision-heavy cites "
            "(e.g. §4.2.14.C bent/numbered_item restarts).",
            "",
            "| coordinate | type | n |",
            "|------------|------|--:|",
        ]
    )
    for row in report["top_encode_eligible_collisions"]:  # type: ignore[union-attr]
        lines.append(
            f"| `{row['clause_coordinate']}` | {row['clause_type']} | {row['len']} |"
        )

    lines.extend(
        [
            "",
            "## In-force clause_type census",
            "",
            "| clause_type | n |",
            "|------------|--:|",
        ]
    )
    for row in report["in_force_clause_type_census"]:  # type: ignore[union-attr]
        lines.append(f"| {row['clause_type']} | {row['len']} |")

    lines.extend(
        [
            "",
            "## Policy implications (locked for Track A)",
            "",
            "1. **Encode-eligible (D4):** `is_in_force` ∧ `clause_type ∈ {fikra,bent,numbered_item}` "
            "∧ (`clause_number` OR `clause_letter` set).",
            "2. **Null / chapter / part labels:** out of encode scope.",
            "3. **Section-only coordinates:** not valid `gate_b_sources` cites.",
            "4. **Coordinate resolve:** prefer in-force matches; if >1 row → "
            "`AmbiguousClauseCiteError` (use `C*` until richer cites exist).",
            "5. **`C*` stays** as the unique row key through Track E; public YAML may "
            "use coordinates only when unique under the resolve policy.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clauses",
        type=Path,
        default=_DEFAULT_CLAUSES,
        help="Path to sut_clauses.parquet",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Print markdown report (default: compact summary)",
    )
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        help="Optional path to write markdown report",
    )
    args = parser.parse_args(argv)
    report = run_audit(args.clauses)
    md = render_markdown(report)
    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(md + "\n", encoding="utf-8")
    if args.markdown or args.write is not None:
        print(md)
    else:
        print(
            f"total={report['total_rows']} null_coord={report['null_coordinate_rows']} "
            f"eligible={report['encode_eligible_rows']} "
            f"eligible_dup_coords={report['dup_encode_eligible_by_coordinate']['duplicate_key_groups']}"  # type: ignore[index]
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
