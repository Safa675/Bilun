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
import hashlib
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
# How many rows per status/side to list in markdown (full detail stays in JSON).
_MD_LIST_CAP = 40


def _load_corpus(parquet_path: Path) -> pl.DataFrame:
    """Load the columns the diff needs from a clause corpus parquet."""
    if not parquet_path.exists():
        raise FileNotFoundError(f"clause corpus parquet missing: {parquet_path}")
    frame = pl.read_parquet(parquet_path)
    cols = [c for c in _DIFF_COLS if c in frame.columns]
    cols += [c for c in ("source_docx", "source_effective_date") if c in frame.columns]
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
    """Diff row counts; AMENDED includes both old and new corpus rows.

    Inferred totals cannot recover new-side STABLE duplicate multiplicity;
    callers with the original corpora should use their actual heights.
    """
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
    amended_old = diff.filter((pl.col("status") == "AMENDED") & (pl.col("side") == "old")).height
    amended_new = diff.filter((pl.col("status") == "AMENDED") & (pl.col("side") == "new")).height
    p(f"- STABLE (old corpus rows; refs survive): **{summary['stable']:,}**")
    p(
        f"- AMENDED (old + new corpus rows → triage): **{summary['amended']:,}** "
        f"(**{amended_old:,} old** + **{amended_new:,} new**)"
    )
    p(f"- NEW (added): **{summary['new']:,}**")
    p(f"- REMOVED (refs may dangle): **{summary['removed']:,}**\n")
    p(
        "_Counts describe corpus rows, not a count of distinct legal amendments. "
        "Multiple rows can share a coordinate; source review must establish the "
        "legal changes._\n"
    )
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
    for status, side, title in (
        ("AMENDED", "old", "## AMENDED — old corpus rows (re-triage references)\n"),
        ("AMENDED", "new", "## AMENDED — new corpus rows (review replacement text)\n"),
        ("REMOVED", "old", "## REMOVED — clause no longer present (re-point references)\n"),
        ("NEW", "new", "## NEW — clause added\n"),
    ):
        sub = diff.filter(
            (pl.col("status") == status) & (pl.col("side") == side)
        ).sort(["section_id", "clause_key"])
        p(title)
        if sub.height == 0:
            p("_(none)_\n")
            p("---\n")
            continue
        p(f"**{sub.height:,}** corpus row(s)" + (f" (showing first {_MD_LIST_CAP})" if sub.height > _MD_LIST_CAP else "") + ":\n")
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
        f"SUT clause diff: {summary['stable']:,} stable old corpus rows, "
        f"{summary['amended']:,} amended corpus rows (old + new), "
        f"{summary['new']:,} new corpus rows, {summary['removed']:,} removed corpus rows; "
        "not distinct legal amendments"
    )


def _corpus_fingerprint(frame: pl.DataFrame) -> str:
    """Hash the seven diff fields and available provenance, not the full corpus.

    Include schema and duplicate rows; parquet encoding and row order are ignored.
    """
    columns = sorted(frame.columns)
    ordered = frame.select(columns)
    serialized = ordered.with_columns(
        pl.col(c).cast(pl.String) for c in columns if ordered.schema[c].is_float()
    )
    content = json.dumps(
        {
            "schema": [(c, str(ordered.schema[c])) for c in columns],
            "rows": serialized.sort(columns).write_json(),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _reuse_existing_report(
    json_path: Path, md_path: Path, payload: dict, legacy_proof: Path | None,
) -> dict | None:
    """Never replace a dated report with a different transition."""
    if not json_path.exists() and not md_path.exists():
        return None
    if not json_path.is_file() or not md_path.is_file():
        raise ValueError(f"Incomplete clause report pair: {json_path} and {md_path}")
    existing = json.loads(json_path.read_text(encoding="utf-8"))
    if (
        not isinstance(existing, dict)
        or existing.get("new_date") != payload["new_date"]
        or not isinstance(existing.get("summary"), dict)
        or not isinstance(existing.get("rows"), list)
    ):
        raise ValueError(f"Invalid existing clause report: {json_path}")
    fingerprints = payload["input_fingerprints"]
    stored = existing.get("input_fingerprints")
    legacy = stored is None
    if legacy and legacy_proof is not None:
        proof = json.loads(legacy_proof.read_text(encoding="utf-8"))
        if (
            not isinstance(proof, dict)
            or proof.get("report_sha256") != hashlib.sha256(json_path.read_bytes()).hexdigest()
        ):
            raise ValueError(f"Legacy input proof does not match the clause report: {legacy_proof}")
        stored = proof.get("input_fingerprints")
        if (
            not isinstance(stored, dict)
            or stored.get("algorithm") != fingerprints["algorithm"]
            or not all(
                isinstance(stored.get(k), str) and len(stored[k]) == 64
                and set(stored[k]) <= set("0123456789abcdef")
                for k in ("old", "new")
            )
        ):
            raise ValueError(f"Invalid legacy input fingerprints: {legacy_proof}")
    self_comparison = fingerprints["old"] == fingerprints["new"]
    if stored == fingerprints or (
        isinstance(stored, dict) and self_comparison
        and stored.get("algorithm") == fingerprints["algorithm"]
        and stored.get("new") == fingerprints["new"]
    ):
        if legacy:
            print("Preserving legacy clause history using verified input fingerprints.")
        return existing
    raise ValueError(
        f"Refusing to overwrite historical clause report for {payload['new_date']}: "
        "the source transition differs or cannot be verified."
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
    parser.add_argument(
        "--legacy-input-fingerprints",
        type=Path,
        default=None,
        help="Previously verified input fingerprints bound to a legacy report SHA256",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    date_tag = args.new_date or date.today().isoformat()

    old = _load_corpus(args.old_parquet)
    new = _load_corpus(args.new_parquet)

    diff = diff_clause_corpora(old, new)
    summary = summarize(diff)
    # Diff emits STABLE only from the old side, which loses any new-side
    # duplicate multiplicity. Corpus totals must come from the inputs.
    summary["total_old_side"] = old.height
    summary["total_new_side"] = new.height

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
        "input_fingerprints": {
            "algorithm": "sha256-clause-diff-inputs-v1",
            "old": _corpus_fingerprint(old),
            "new": _corpus_fingerprint(new),
        },
        "summary": summary,
        "rows": actionable.to_dicts(),
    }
    existing = _reuse_existing_report(json_path, md_path, payload, args.legacy_input_fingerprints)
    if existing is None:
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        md_path.write_text(
            render_markdown(
                diff, summary, old_name=args.old_parquet.name, new_name=args.new_parquet.name
            ),
            encoding="utf-8",
        )
    else:
        summary = existing["summary"]
        print(f"Preserved existing clause report for {date_tag}.")

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
