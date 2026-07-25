#!/usr/bin/env python3
"""Stale SUT clause-reference reporter for the Reimbursement Engineer.

The Reimbursement Engineer agent uses this as a *reporter* (not a gate): it
checks every ``gate_b_sources`` cite (opaque ``C*/F*`` **or**
``clause_coordinate``) referenced by the prose rule sets in
``data/gazette/prose_rules/*.json`` against the staleness columns of
``data/gazette/sut_clauses.parquet`` and classifies each reference into one of
four severity tiers, then writes a markdown triage report. The script always
exits 0 — the human (or agent) triages the report; nothing here is a blocker.

Tiers (highest severity first):

  - **TIER 1 — superseded:** ``is_superseded_marker == True``. The clause was
    explicitly replaced by a later amendment; the rule still points at it.
  - **TIER 2 — not in force:** ``is_in_force == False``. The clause is no
    longer legally in force (but not flagged as a superseded marker).
  - **TIER 3 — had struck content:** ``had_struck_content == True``. The
    clause's text contains struck/replaced fragments. ~48% of all clauses
    have this (benign historical edits), so it is lower severity and
    *volume-capped* in the report to avoid drowning the signal.
  - **TIER 4 — dangling:** the clause-id is not present in
    ``sut_clauses.parquet`` at all (rule references a clause we never
    extracted).

CAVEAT (AGENTS.md / rule_registry.py:346-358): ``drug_indication_prose`` is
intentionally labeled ``implemented`` and its ~150 tier-3 hits are largely
benign bulk-strike edits. Per rule_set, if tier-3 hits exceed the high-volume
threshold we emit a single "high volume — review a sample" note instead of
listing every row, so the report does not wholesale-flag that rule set.

Run:
    .venv/bin/python scripts/agent/stale_clause_refs.py
    .venv/bin/python scripts/agent/stale_clause_refs.py --rule-set drug_indication_prose
    .venv/bin/python scripts/agent/stale_clause_refs.py --output /tmp/stale.md --quiet
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import polars as pl

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROSE_RULES_GLOB = PROJECT_ROOT / "data" / "gazette" / "prose_rules" / "*.json"
SUT_CLAUSES_PARQUET = PROJECT_ROOT / "data" / "gazette" / "sut_clauses.parquet"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "reports" / "agent" / "reimbursement" / "stale_clause_refs.md"
)

# Output caps. Tier 3 is the bulk-strike tier (~48% of clauses hit it); listing
# every row for a high-volume rule_set would drown the higher-severity tiers.
TIER3_LISTING_CAP = 5            # rows listed per rule_set in tier 3 tables
TIER3_PER_RULESET_THRESHOLD = 50  # > this → summarize instead of per-rule tables
# High-volume guard: a rule_set with tier-3 hits above this gets the
# "do not treat as wholesale-stale" note instead of a row dump. Tuned so
# drug_indication_prose (~150 tier-3 refs) is captured without listing 900 rows.
TIER3_HIGH_VOLUME_THRESHOLD = 100

CLAUSE_STALENESS_COLS = [
    "clause_id",
    "clause_coordinate",
    "is_in_force",
    "is_superseded_marker",
    "had_struck_content",
]

# Display order: highest severity first. TIER 4 (dangling) is technically a
# missing-data signal but is placed last because it usually means the clause
# extractor skipped an annex, not that the rule points at dead law.
TIER_ORDER = ["TIER 1", "TIER 2", "TIER 3", "TIER 4"]
TIER_LABELS = {
    "TIER 1": "superseded marker (clause replaced by amendment)",
    "TIER 2": "not in force (clause no longer legally active)",
    "TIER 3": "had struck content (historical edit; often benign)",
    "TIER 4": "dangling reference (cite not in sut_clauses)",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report stale SUT clause references in prose rule sets."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Markdown report output path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--rule-set",
        type=str,
        default=None,
        help="Optional rule_set_id filter (only report that rule set).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output (the one-line summary always prints).",
    )
    return parser


def load_rule_refs(
    glob_pattern: Path, rule_set_filter: str | None = None
) -> pl.DataFrame:
    """Load (rule_set_id, rule_id, gate_b_ref) tuples from every prose rule file.

    ``gate_b_ref`` may be an opaque ``C*/F*`` id or a ``clause_coordinate``
    (Track E dual-read). Files without a ``rule_set_id`` + ``rules`` array
    (e.g. ``*.schema.json`` or code-list files) are skipped silently.
    """
    rows: list[tuple[str, str, str]] = []
    skipped: list[str] = []
    for path in sorted(glob.glob(str(glob_pattern))):
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped.append(Path(path).name)
            continue
        if not isinstance(doc, dict):
            skipped.append(Path(path).name)
            continue
        rule_set_id = doc.get("rule_set_id")
        rules = doc.get("rules")
        if not rule_set_id or not isinstance(rules, list):
            # schema/code-list files: not a rule set, skip.
            skipped.append(Path(path).name)
            continue
        if rule_set_filter and rule_set_id != rule_set_filter:
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rid = rule.get("rule_id")
            for cid in rule.get("gate_b_sources") or []:
                if cid:
                    rows.append((rule_set_id, rid or "", str(cid)))

    if not rows:
        return pl.DataFrame(
            schema={
                "rule_set_id": pl.Utf8,
                "rule_id": pl.Utf8,
                "gate_b_ref": pl.Utf8,
            }
        )
    return pl.DataFrame(
        rows,
        schema={
            "rule_set_id": pl.Utf8,
            "rule_id": pl.Utf8,
            "gate_b_ref": pl.Utf8,
        },
        orient="row",
    )


def load_clauses(parquet_path: Path) -> pl.DataFrame:
    if not parquet_path.exists():
        raise FileNotFoundError(f"sut_clauses parquet missing: {parquet_path}")
    return pl.read_parquet(parquet_path, columns=CLAUSE_STALENESS_COLS)


def classify_refs(refs: pl.DataFrame, clauses: pl.DataFrame) -> pl.DataFrame:
    """Resolve gate_b cites (C* or coordinate) then assign staleness tiers.

    Coordinates may fan out to multiple parquet rows (collision groups); each
    resolved clause_id is tiered independently. Unresolvable cites → TIER 4.
    """
    from scripts.sut.prose.clause_identity import (
        AmbiguousClauseCiteError,
        NonEncodeEligibleCiteError,
        UnknownClauseCiteError,
        is_clause_id,
        resolve_gate_b_ref_to_clause_ids,
    )

    if refs.is_empty():
        return pl.DataFrame(
            schema={
                "rule_set_id": pl.Utf8,
                "rule_id": pl.Utf8,
                "gate_b_ref": pl.Utf8,
                "clause_id": pl.Utf8,
                "is_in_force": pl.Boolean,
                "is_superseded_marker": pl.Boolean,
                "had_struck_content": pl.Boolean,
                "tier": pl.Utf8,
            }
        )

    # Prefer vectorized C* / unique-coordinate joins; fall back per-ref resolve
    # only for odd cites (keeps the hot path Polars-first).
    id_refs = refs.filter(pl.col("gate_b_ref").str.contains(r"^[CF][0-9]{6}$"))
    other_refs = refs.join(
        id_refs.select(["rule_set_id", "rule_id", "gate_b_ref"]),
        on=["rule_set_id", "rule_id", "gate_b_ref"],
        how="anti",
    )

    by_id = id_refs.join(
        clauses.select(CLAUSE_STALENESS_COLS),
        left_on="gate_b_ref",
        right_on="clause_id",
        how="left",
    )
    # Polars keeps both join keys; unmatched C* have null clause_id → TIER 4.

    by_coord = other_refs.join(
        clauses.select(CLAUSE_STALENESS_COLS),
        left_on="gate_b_ref",
        right_on="clause_coordinate",
        how="left",
    )

    # Cites that looked like coordinates but matched nothing: try identity resolve
    # (handles edge formats); otherwise leave as dangling.
    unresolved = by_coord.filter(pl.col("clause_id").is_null())
    resolved_extra: list[dict] = []
    if not unresolved.is_empty():
        for row in unresolved.iter_rows(named=True):
            ref = str(row["gate_b_ref"])
            ids: list[str] = []
            try:
                ids = resolve_gate_b_ref_to_clause_ids(
                    ref,
                    clauses,
                    in_force_only=False,
                    encode_eligible_only=False,
                    allow_ambiguous=True,
                )
            except (
                AmbiguousClauseCiteError,
                NonEncodeEligibleCiteError,
                UnknownClauseCiteError,
            ):
                ids = [ref] if is_clause_id(ref) else []
            if not ids:
                resolved_extra.append(
                    {
                        "rule_set_id": row["rule_set_id"],
                        "rule_id": row["rule_id"],
                        "gate_b_ref": ref,
                        "clause_id": None,
                        "is_in_force": None,
                        "is_superseded_marker": None,
                        "had_struck_content": None,
                    }
                )
                continue
            hit = clauses.filter(pl.col("clause_id").is_in(ids))
            if hit.is_empty():
                for cid in ids:
                    resolved_extra.append(
                        {
                            "rule_set_id": row["rule_set_id"],
                            "rule_id": row["rule_id"],
                            "gate_b_ref": ref,
                            "clause_id": cid,
                            "is_in_force": None,
                            "is_superseded_marker": None,
                            "had_struck_content": None,
                        }
                    )
            else:
                for crec in hit.iter_rows(named=True):
                    resolved_extra.append(
                        {
                            "rule_set_id": row["rule_set_id"],
                            "rule_id": row["rule_id"],
                            "gate_b_ref": ref,
                            "clause_id": crec.get("clause_id"),
                            "is_in_force": crec.get("is_in_force"),
                            "is_superseded_marker": crec.get("is_superseded_marker"),
                            "had_struck_content": crec.get("had_struck_content"),
                        }
                    )

    by_coord_matched = by_coord.filter(pl.col("clause_id").is_not_null())
    parts = [by_id, by_coord_matched]
    if resolved_extra:
        parts.append(pl.DataFrame(resolved_extra))
    joined = pl.concat(parts, how="diagonal_relaxed")

    tiered = joined.with_columns(
        pl.col("clause_id").is_null().alias("_missing"),
    ).with_columns(
        pl.when(pl.col("is_superseded_marker") == True)  # noqa: E712
        .then(pl.lit("TIER 1"))
        .when(pl.col("is_in_force") == False)  # noqa: E712
        .then(pl.lit("TIER 2"))
        .when(pl.col("had_struck_content") == True)  # noqa: E712
        .then(pl.lit("TIER 3"))
        .when(pl.col("_missing"))
        .then(pl.lit("TIER 4"))
        .otherwise(pl.lit("OK"))
        .alias("tier")
    ).drop("_missing")

    out_cols = [
        "rule_set_id",
        "rule_id",
        "gate_b_ref",
        "clause_id",
        "is_in_force",
        "is_superseded_marker",
        "had_struck_content",
        "tier",
    ]
    return tiered.select([c for c in out_cols if c in tiered.columns])


def _md_table(df: pl.DataFrame) -> str:
    """Render a small dataframe as a GitHub-flavored markdown table.

    Pure-Polars renderer (no pandas / tabulate — AGENTS.md §9 forbids pandas
    and tabulate isn't installed in this venv). Empty input renders as
    ``_(none)_`` so a tier with zero hits stays readable.
    """
    if df.height == 0:
        return "_(none)_"
    cols = df.columns
    # stringify every cell once (booleans, ints, floats all coerce cleanly)
    rows = df.select([pl.col(c).cast(pl.Utf8) for c in cols]).rows()
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    return f"{header}\n{sep}\n{body}"


def render_report(
    classified: pl.DataFrame,
    *,
    rule_set_filter: str | None,
    skipped_files: int,
) -> str:
    n_rules = classified.select("rule_id", "rule_set_id").n_unique()
    n_refs = classified.height
    tier_counts = {
        t: classified.filter(pl.col("tier") == t).height for t in TIER_ORDER
    }
    ok_count = classified.filter(pl.col("tier") == "OK").height

    lines: list[str] = []
    p = lines.append
    p("# Stale SUT clause references — prose rule gate_b_sources\n")
    scope = f"`{rule_set_filter}`" if rule_set_filter else "all rule sets"
    p(f"**Scope:** {scope}  |  **Skipped non-rule files:** {skipped_files}\n")
    p("## Summary\n")
    p(f"- Rule references checked (rule_set_id, rule_id pairs): **{n_rules:,}**")
    p(f"- Total clause references: **{n_refs:,}**")
    for t in TIER_ORDER:
        p(f"- {t} ({TIER_LABELS[t]}): **{tier_counts[t]:,}**")
    p(f"- OK (in force, no struck content, clause present): **{ok_count:,}**\n")
    p(
        "_This is a reporter, not a gate. Tiers are ordered by severity; "
        "tier 3 is volume-capped and intentionally low-priority (≈48% of all "
        "SUT clauses carry struck historical edits)._\n"
    )
    p("---\n")

    # Per-tier sections. Tier 3 is volume-capped per rule_set (see constants).
    rule_sets = (
        classified.select("rule_set_id")
        .unique()
        .sort("rule_set_id")
        .get_column("rule_set_id")
        .to_list()
    )
    for t in TIER_ORDER:
        tier_df = classified.filter(pl.col("tier") == t)
        p(f"## {t} — {TIER_LABELS[t]}\n")
        if tier_df.height == 0:
            p("_(none)_\n")
            p("---\n")
            continue

        per_rule_set = (
            tier_df.group_by("rule_set_id")
            .agg(pl.len().alias("n"))
            .sort("n", descending=True)
        )
        p(f"**{tier_df.height:,}** references across **{per_rule_set.height}** "
          f"rule set(s):\n")
        p(_md_table(per_rule_set))
        p("")

        # Per-rule_set detail tables, with the high-volume guard for tier 3.
        for rsid in rule_sets:
            sub = tier_df.filter(pl.col("rule_set_id") == rsid).select(
                "rule_set_id", "rule_id", "gate_b_ref", "clause_id"
            )
            if sub.height == 0:
                continue

            if (
                t == "TIER 3"
                and sub.height > TIER3_HIGH_VOLUME_THRESHOLD
            ):
                p(
                    f"- **{rsid}** — {sub.height} tier-3 refs "
                    "(high volume — review a sample, do not treat as "
                    f"wholesale-stale; sample first {TIER3_LISTING_CAP}):"
                )
                p("")
                p(_md_table(sub.head(TIER3_LISTING_CAP)))
                p("")
                continue

            if (
                t == "TIER 3"
                and sub.height > TIER3_PER_RULESET_THRESHOLD
            ):
                p(
                    f"- **{rsid}** — {sub.height} tier-3 refs "
                    f"(high count — likely benign bulk-strike, sample first "
                    f"{TIER3_LISTING_CAP}):"
                )
                p("")
                p(_md_table(sub.head(TIER3_LISTING_CAP)))
                p("")
                continue

            p(f"- **{rsid}** ({sub.height} refs):")
            p("")
            p(_md_table(sub))
            p("")

        p("---\n")

    return "\n".join(lines)


def main() -> int:
    args = _build_parser().parse_args()
    log = (lambda *a: None) if args.quiet else (lambda *a: print(*a))

    log("[stale_clause_refs] loading prose rule references …")
    refs = load_rule_refs(PROSE_RULES_GLOB, rule_set_filter=args.rule_set)
    # count skipped files for the report header (independent of filter)
    skipped = 0
    for path in sorted(glob.glob(str(PROSE_RULES_GLOB))):
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue
        if not isinstance(doc, dict) or not doc.get("rule_set_id") or not isinstance(
            doc.get("rules"), list
        ):
            skipped += 1

    log(f"[stale_clause_refs] {refs.height:,} clause refs across "
        f"{refs.select('rule_set_id').n_unique()} rule sets "
        f"({skipped} non-rule files skipped)")

    clauses = load_clauses(SUT_CLAUSES_PARQUET)
    classified = classify_refs(refs, clauses)

    report = render_report(
        classified,
        rule_set_filter=args.rule_set,
        skipped_files=skipped,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")

    parts = [
        f"T1={classified.filter(pl.col('tier') == 'TIER 1').height}",
        f"T2={classified.filter(pl.col('tier') == 'TIER 2').height}",
        f"T3={classified.filter(pl.col('tier') == 'TIER 3').height}",
        f"T4={classified.filter(pl.col('tier') == 'TIER 4').height}",
    ]
    try:
        out_display = str(args.output.relative_to(PROJECT_ROOT))
    except ValueError:
        out_display = str(args.output)
    print(
        f"[stale_clause_refs] refs={classified.height} "
        f"({', '.join(parts)}) -> {out_display}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
