#!/usr/bin/env python3
"""Track E Phase 5 — clause_key diff between two SUT clause corpora.

Compares an OLD ``sut_clauses.parquet`` (the committed corpus) against a NEW
one (a re-extraction from a newer tebliğ docx) using the stable clause
identity (``clause_key = clause_coordinate#content_hash``).

The point of Track E: a clause whose text did NOT change keeps the same
``content_hash``, so its ``clause_key`` is byte-identical across re-extraction
and every reference to it stays valid.  A clause whose text DID change gets a
new hash, so it lands in the triage list instead of silently breaking refs.

Classification (per clause, keyed by ``clause_key``):

  - **STABLE**  — same ``clause_key`` present in both corpora. References
                  survive the re-extraction untouched.
  - **AMENDED** — same ``clause_coordinate`` present in both, but the content
                  hash differs. The clause text was amended; references to the
                  old ``clause_key`` must be re-triaged.
  - **NEW**     — clause_key/coordinate only in the new corpus.
  - **REMOVED** — clause_key/coordinate only in the old corpus. References to
                  it will dangle; load-bearing cites must be re-pointed.

Coordinate collisions (one coordinate → many clauses) are handled by matching
on the full ``clause_key`` (coord + hash), never on coordinate alone.
NULL-coordinate rows (bare content-hash keys) match by hash only.

Usage:
    python scripts/sut/sut_clause_diff.py <OLD_PARQUET> <NEW_PARQUET>
    python scripts/sut/sut_clause_diff.py <OLD> <NEW> --new-date 2026-07-01

Outputs:
    data/gazette/deltas/<NEW_DATE>_clause_diff.json  — structured diff
    data/gazette/deltas/<NEW_DATE>_clause_diff.md    — markdown triage list
    GITHUB_OUTPUT clause_diff_summary                — human-readable PR body
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

DELTA_DIR = _PROJECT_ROOT / "data" / "gazette" / "deltas"

# Columns carried into the diff (bound payload size; text is truncated in output).
_DIFF_COLS = [
    "clause_id",
    "clause_coordinate",
    "content_hash",
    "clause_key",
    "section_id",
    "is_in_force",
    "in_force_text",
]

# How many snippet characters to show per row in the markdown triage list.
_SNIPPET_LEN = 120
# How many rows per status to list in the markdown (full detail stays in JSON).
_MD_LIST_CAP = 40


def _load_corpus(parquet_path: Path) -> pl.DataFrame:
    """Load the columns the diff needs from a clause corpus parquet."""
    if not parquet_path.exists():
        raise FileNotFoundError(f"clause corpus parquet missing: {parquet_path}")
    frame = pl.read_parquet(parquet_path)
    cols = [c for c in _DIFF_COLS if c in frame.columns]
    out = frame.select(cols)
    # Ensure the identity columns exist (older corpora predate Track E).
    if "content_hash" not in out.columns or "clause_key" not in out.columns:
        raise ValueError(
            f"{parquet_path.name} lacks content_hash/clause_key columns — "
            "run Track E identity backfill before diffing."
        )
    return out


def _normalize_key_cols(frame: pl.DataFrame) -> pl.DataFrame:
    """Cast identity columns to Utf8 and treat empty/blank coordinates as null."""
    return frame.with_columns(
        [
            pl.col("clause_key").cast(pl.Utf8).str.strip_chars(),
            pl.col("clause_coordinate").cast(pl.Utf8).str.strip_chars(),
            pl.col("content_hash").cast(pl.Utf8).str.strip_chars(),
        ]
    ).with_columns(
        pl.when(pl.col("clause_coordinate") == "")
        .then(None)
        .otherwise(pl.col("clause_coordinate"))
        .alias("clause_coordinate")
    )


def _snippet(text: str | None, limit: int = _SNIPPET_LEN) -> str:
    if not text:
        return ""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def diff_clause_corpora(old: pl.DataFrame, new: pl.DataFrame) -> pl.DataFrame:
    """Return one row per clause with a Track E diff ``status``.

    Statuses: STABLE / AMENDED / NEW / REMOVED (see module docstring).
    """
    old = _normalize_key_cols(old)
    new = _normalize_key_cols(new)

    old_keys = set(old["clause_key"].to_list())
    new_keys = set(new["clause_key"].to_list())
    old_coords = {c for c in old["clause_coordinate"].to_list() if c}
    new_coords = {c for c in new["clause_coordinate"].to_list() if c}

    stable_keys = old_keys & new_keys

    def classify_old_row(key: str, coord: str | None) -> str:
        if key in stable_keys:
            return "STABLE"
        # Key gone; if the coordinate anchor still exists in the new corpus the
        # clause was amended (new hash), otherwise it was removed outright.
        if coord and coord in new_coords:
            return "AMENDED"
        return "REMOVED"

    def classify_new_row(key: str, coord: str | None) -> str:
        if key in stable_keys:
            return "STABLE"
        if coord and coord in old_coords:
            return "AMENDED"
        return "NEW"

    rows: list[dict] = []
    for rec in old.iter_rows(named=True):
        status = classify_old_row(rec["clause_key"], rec["clause_coordinate"])
        rows.append(
            {
                "side": "old",
                "status": status,
                "clause_key": rec["clause_key"],
                "clause_coordinate": rec["clause_coordinate"],
                "content_hash": rec["content_hash"],
                "clause_id": rec.get("clause_id"),
                "section_id": rec.get("section_id"),
                "is_in_force": rec.get("is_in_force"),
                "text_snippet": _snippet(rec.get("in_force_text")),
            }
        )
    for rec in new.iter_rows(named=True):
        status = classify_new_row(rec["clause_key"], rec["clause_coordinate"])
        if status == "STABLE":
            continue  # already emitted from the old side; avoid duplicates
        rows.append(
            {
                "side": "new",
                "status": status,
                "clause_key": rec["clause_key"],
                "clause_coordinate": rec["clause_coordinate"],
                "content_hash": rec["content_hash"],
                "clause_id": rec.get("clause_id"),
                "section_id": rec.get("section_id"),
                "is_in_force": rec.get("is_in_force"),
                "text_snippet": _snippet(rec.get("in_force_text")),
            }
        )

    schema = {
        "side": pl.Utf8,
        "status": pl.Utf8,
        "clause_key": pl.Utf8,
        "clause_coordinate": pl.Utf8,
        "content_hash": pl.Utf8,
        "clause_id": pl.Utf8,
        "section_id": pl.Utf8,
        "is_in_force": pl.Boolean,
        "text_snippet": pl.Utf8,
    }
    if not rows:
        return pl.DataFrame(schema=schema)
    return pl.DataFrame(rows, schema_overrides=schema)


def summarize(diff: pl.DataFrame) -> dict[str, int]:
    """Counts per status plus total row counts."""
    counts: dict[str, int] = {}
    for status in ("STABLE", "AMENDED", "NEW", "REMOVED"):
        counts[status.lower()] = diff.filter(pl.col("status") == status).height
    counts["total_old_side"] = diff.filter(pl.col("side") == "old").height
    counts["total_new_side"] = diff.filter(pl.col("side") == "new").height + counts[
        "stable"
    ]
    return counts


def render_markdown(diff: pl.DataFrame, summary: dict[str, int], *, old_name: str, new_name: str) -> str:
    """Markdown triage list — AMENDED/NEW/REMOVED rows humans must look at."""
    lines: list[str] = []
    p = lines.append
    p("# SUT clause corpus diff (Track E clause_key)\n")
    p(f"**Old:** `{old_name}`  |  **New:** `{new_name}`\n")
    p("## Summary\n")
    p(f"- STABLE (refs survive): **{summary['stable']:,}**")
    p(f"- AMENDED (content changed → triage): **{summary['amended']:,}**")
    p(f"- NEW (added): **{summary['new']:,}**")
    p(f"- REMOVED (refs may dangle): **{summary['removed']:,}**\n")
    p(
        "_STABLE clauses keep the same `clause_key` (coord#hash) across "
        "re-extraction — references to them remain valid. Everything else "
        "below needs human triage._\n"
    )
    p("---\n")

    display_cols = [
        "clause_key",
        "clause_coordinate",
        "section_id",
        "is_in_force",
        "text_snippet",
    ]
    for status, title in (
        ("AMENDED", "## AMENDED — content changed (re-triage references)\n"),
        ("REMOVED", "## REMOVED — clause no longer present (re-point references)\n"),
        ("NEW", "## NEW — clause added\n"),
    ):
        sub = diff.filter(
            (pl.col("status") == status) & (pl.col("side") == ("old" if status in ("AMENDED", "REMOVED") else "new"))
        ).sort(["section_id", "clause_key"])
        p(title)
        if sub.height == 0:
            p("_(none)_\n")
            p("---\n")
            continue
        p(f"**{sub.height:,}** clause(s)" + (f" (showing first {_MD_LIST_CAP})" if sub.height > _MD_LIST_CAP else "") + ":\n")
        shown = sub.select([c for c in display_cols if c in sub.columns]).head(_MD_LIST_CAP)
        rows = shown.select([pl.col(c).cast(pl.Utf8).fill_null("") for c in shown.columns]).rows()
        p("| " + " | ".join(shown.columns) + " |")
        p("| " + " | ".join("---" for _ in shown.columns) + " |")
        for row in rows:
            p("| " + " | ".join(str(x).replace("|", "/") for x in row) + " |")
        p("")
        p("---\n")

    return "\n".join(lines)


def format_summary(summary: dict[str, int]) -> str:
    """One-line-ish GITHUB_OUTPUT summary for the auto-PR body."""
    return (
        f"SUT clause diff: {summary['stable']:,} stable, "
        f"{summary['amended']:,} amended, {summary['new']:,} new, "
        f"{summary['removed']:,} removed"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diff two SUT clause corpora by Track E clause_key."
    )
    parser.add_argument("old_parquet", type=Path, help="Old (committed) corpus parquet")
    parser.add_argument("new_parquet", type=Path, help="New (re-extracted) corpus parquet")
    parser.add_argument(
        "--new-date",
        type=str,
        default=None,
        help="Effective date tag for output filenames (default: today)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DELTA_DIR,
        help=f"Output directory (default: {DELTA_DIR})",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    date_tag = args.new_date or date.today().isoformat()

    old = _load_corpus(args.old_parquet)
    new = _load_corpus(args.new_parquet)

    diff = diff_clause_corpora(old, new)
    summary = summarize(diff)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{date_tag}_clause_diff.json"
    md_path = args.output_dir / f"{date_tag}_clause_diff.md"

    # The JSON carries only the actionable (non-STABLE) rows — STABLE clauses
    # are the "refs survive" majority and are reported by count, not listed.
    actionable = diff.filter(pl.col("status") != "STABLE")
    payload = {
        "old_corpus": str(args.old_parquet),
        "new_corpus": str(args.new_parquet),
        "new_date": date_tag,
        "generated_at": date.today().isoformat(),
        "summary": summary,
        "rows": actionable.to_dicts(),
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    md_path.write_text(
        render_markdown(
            diff, summary, old_name=args.old_parquet.name, new_name=args.new_parquet.name
        ),
        encoding="utf-8",
    )

    body = format_summary(summary)
    print(body)
    print(f"  JSON -> {json_path}")
    print(f"  MD   -> {md_path}")

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"clause_diff_summary={body}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
