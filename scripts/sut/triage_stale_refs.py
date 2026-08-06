#!/usr/bin/env python3
"""TIER-1 stale clause-reference triage for the Reimbursement Engineer.

Builds on ``scripts.agent.stale_clause_refs`` (the reporter). For every
TIER-1 reference — a rule whose cited clause carries a superseded/mülga
marker but is itself still ``is_in_force`` — this script computes the
*repealed content* (``text_tr`` minus ``in_force_text``) and scores how much
the rule's own fields overlap with that repealed content:

  - **A**      — rule fields overlap the repealed content significantly
                 (drug-name hit or overlap ≥ ``A_THRESHOLD``): the rule may be
                 enforcing dead law → re-encode or delete.
  - **REVIEW** — partial overlap: human must look before deciding.
  - **B**      — no overlap with the repealed content: likely benign
                 (provenance note only).

The script is read-only and always exits 0. It writes a markdown report and a
parquet with one row per TIER-1 reference. Proposals are proposals — the
final A/B decision is human (plan K1,
``plans/update/2026-08-06-stale-clause-triage-plan.md``).

Run:
    .venv/bin/python scripts/sut/triage_stale_refs.py
    .venv/bin/python scripts/sut/triage_stale_refs.py --output-dir /tmp/triage
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from datetime import date
from pathlib import Path

import polars as pl

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SUT_CLAUSES_PARQUET = PROJECT_ROOT / "data" / "gazette" / "sut_clauses.parquet"
PROSE_RULES_GLOB = PROJECT_ROOT / "data" / "gazette" / "prose_rules" / "*.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "agent" / "reimbursement"

CLAUSE_TEXT_COLS = [
    "clause_id",
    "clause_coordinate",
    "text_tr",
    "in_force_text",
    "amendment_refs",
]

# Overlap thresholds (plan K1: conservative, wide REVIEW band).
# score = |rule_tokens ∩ diff_tokens| / |diff_tokens|
A_THRESHOLD = 0.30
REVIEW_THRESHOLD = 0.05

# Amendment-metadata tokens that carry no substantive legal content — they
# appear in struck fragments like "(Mülga:RG-16/06/2020-31157/19-c md.
# Yürürlük: 24/06/2020)" and must not inflate overlap scores.
_STOPWORDS = {
    "mülga",
    "değişik",
    "yürürlük",
    "rg",
    "md",
    "maddesi",
    "madde",
    "tarihli",
    "ile",
    "ve",
    "veya",
    "için",
    "bu",
    "da",
    "de",
}
_DATE_RE = re.compile(r"^\d")

# Rule JSON keys whose *names* carry domain semantics absent from their
# values (numeric/bool). Map to the Turkish clause-text tokens they imply.
# Extend deliberately — each entry must correspond to real SUT wording.
KEY_TOKEN_MAP: dict[str, frozenset[str]] = {
    "loading_dose_count": frozenset({"yükleme", "dozu", "doz"}),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Triage TIER-1 stale clause refs (repealed-content overlap)."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Report output directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--date-tag",
        type=str,
        default=None,
        help="Report date tag (default: today, YYYY-MM-DD).",
    )
    return parser


def normalize_tokens(text: str | None) -> list[str]:
    """Turkish-aware tokenize: fold case, strip punctuation, drop stopwords.

    Amendment-metadata tokens (Mülga/RG/Yürürlük/dates/numbers) are removed so
    only substantive content tokens remain.
    """
    if not text:
        return []
    folded = text.replace("İ", "i").replace("I", "ı").lower()
    words = re.findall(r"[a-zçğıöşü0-9]+", folded)
    return [
        w
        for w in words
        if w not in _STOPWORDS and not _DATE_RE.match(w) and len(w) > 1
    ]


def extract_struck_content(text_tr: str | None, in_force_text: str | None) -> str:
    """Return the words present in ``text_tr`` but removed in ``in_force_text``.

    Word-level difflib alignment; insert/replace blocks on the ``text_tr``
    side are the struck fragments. Empty when the two texts are identical
    (marker present but no text actually removed).
    """
    full = (text_tr or "").split()
    current = (in_force_text or "").split()
    matcher = difflib.SequenceMatcher(a=current, b=full, autojunk=False)
    struck: list[str] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        # insert/replace on the b side = words in text_tr missing from
        # in_force_text = the struck fragments.
        if tag in ("insert", "replace"):
            struck.extend(full[j1:j2])
    return " ".join(struck)


def rule_tokens(rule: dict) -> set[str]:
    """Substantive token set of a rule: string values + list-of-string values
    + semantic key-name tokens (``KEY_TOKEN_MAP``). Structural fields
    (rule_id, gate_b_sources, sut_section, provenance) are excluded — they are
    coordinates, not legal content."""
    skip_keys = {
        "rule_id",
        "gate_b_sources",
        "gate_b_sources_extra",
        "sut_section",
        "sut_cross_ref",
        "provenance_note",
        "verification_status",
        "encode_bucket",
        "fatura_inceleme_ref",
    }
    tokens: set[str] = set()
    for key, value in rule.items():
        if key in skip_keys:
            continue
        if key in KEY_TOKEN_MAP and value is not None:
            tokens |= KEY_TOKEN_MAP[key]
        if isinstance(value, str):
            tokens.update(normalize_tokens(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    tokens.update(normalize_tokens(item))
    return tokens


def drug_name_hit(rule: dict, struck_text: str) -> bool:
    """True when any ``drug_names`` entry appears in the struck content."""
    if not struck_text:
        return False
    struck_tokens = set(normalize_tokens(struck_text))
    for name in rule.get("drug_names") or []:
        if not isinstance(name, str):
            continue
        name_tokens = normalize_tokens(name)
        if name_tokens and all(t in struck_tokens for t in name_tokens):
            return True
    return False


def score_overlap(diff_tokens: set[str], rule_token_set: set[str]) -> tuple[float, set[str]]:
    """Fraction of the repealed-content tokens the rule touches."""
    if not diff_tokens:
        return 0.0, set()
    matched = diff_tokens & rule_token_set
    return len(matched) / len(diff_tokens), matched


def propose_class(
    score: float, drug_hit: bool, diff_tokens: set[str]
) -> str:
    """A / REVIEW / B per plan thresholds. Empty diff → B (marker without
    removed text has no dead content to depend on)."""
    if not diff_tokens:
        return "B"
    if drug_hit or score >= A_THRESHOLD:
        return "A"
    if score >= REVIEW_THRESHOLD:
        return "REVIEW"
    return "B"


def load_rules_indexed(glob_pattern: Path) -> dict[tuple[str, str], dict]:
    """{(rule_set_id, rule_id): rule_dict} for every prose rule set."""
    import glob as globmod

    index: dict[tuple[str, str], dict] = {}
    for path in sorted(globmod.glob(str(glob_pattern))):
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        rule_set_id = doc.get("rule_set_id")
        rules = doc.get("rules")
        if not rule_set_id or not isinstance(rules, list):
            continue
        for rule in rules:
            if isinstance(rule, dict) and rule.get("rule_id"):
                index[(rule_set_id, rule["rule_id"])] = rule
    return index


def build_triage(
    classified_t1: pl.DataFrame,
    clauses: pl.DataFrame,
    rules: dict[tuple[str, str], dict] | None = None,
) -> pl.DataFrame:
    """Join TIER-1 refs against clause texts and propose A/REVIEW/B per ref.

    ``classified_t1`` must carry rule_set_id/rule_id/gate_b_ref/clause_id
    (output of ``stale_clause_refs.classify_refs`` filtered to TIER 1).
    ``clauses`` must carry CLAUSE_TEXT_COLS. ``rules`` is the indexed rule
    dict (defaults to loading every prose rule set from disk).
    """
    if rules is None:
        rules = load_rules_indexed(PROSE_RULES_GLOB)

    joined = classified_t1.join(
        clauses.select(CLAUSE_TEXT_COLS), on="clause_id", how="left"
    )

    rows: list[dict] = []
    for row in joined.iter_rows(named=True):
        rule = rules.get((row["rule_set_id"], row["rule_id"]), {})
        struck = extract_struck_content(row.get("text_tr"), row.get("in_force_text"))
        diff_tokens = set(normalize_tokens(struck))
        r_tokens = rule_tokens(rule)
        score, matched = score_overlap(diff_tokens, r_tokens)
        drug_hit = drug_name_hit(rule, struck)
        proposed = propose_class(score, drug_hit, diff_tokens)
        amendment_refs = row.get("amendment_refs") or "[]"
        try:
            amends = json.loads(amendment_refs)
        except (TypeError, json.JSONDecodeError):
            amends = []
        rows.append(
            {
                "rule_set_id": row["rule_set_id"],
                "rule_id": row["rule_id"],
                "gate_b_ref": row["gate_b_ref"],
                "clause_id": row["clause_id"],
                "clause_coordinate": row.get("clause_coordinate"),
                "amendment_refs": "; ".join(amends) if amends else "",
                "struck_content": struck,
                "struck_token_count": len(diff_tokens),
                "overlap_score": round(score, 4),
                "matched_tokens": "; ".join(sorted(matched)),
                "drug_name_hit": drug_hit,
                "proposed_class": proposed,
            }
        )

    if not rows:
        return pl.DataFrame(
            schema={
                "rule_set_id": pl.Utf8,
                "rule_id": pl.Utf8,
                "gate_b_ref": pl.Utf8,
                "clause_id": pl.Utf8,
                "clause_coordinate": pl.Utf8,
                "amendment_refs": pl.Utf8,
                "struck_content": pl.Utf8,
                "struck_token_count": pl.UInt32,
                "overlap_score": pl.Float64,
                "matched_tokens": pl.Utf8,
                "drug_name_hit": pl.Boolean,
                "proposed_class": pl.Utf8,
            }
        )
    return pl.DataFrame(rows).with_columns(
        pl.col("struck_token_count").cast(pl.UInt32)
    )


def _md_table(df: pl.DataFrame) -> str:
    if df.height == 0:
        return "_(none)_"
    cols = df.columns
    rows = df.select([pl.col(c).cast(pl.Utf8).fill_null("") for c in cols]).rows()
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    return f"{header}\n{sep}\n{body}"


def _truncate(text: str | None, limit: int = 160) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").replace("|", "/")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_report(triage: pl.DataFrame, date_tag: str) -> str:
    lines: list[str] = []
    p = lines.append
    counts = {
        c: triage.filter(pl.col("proposed_class") == c).height
        for c in ("A", "REVIEW", "B")
    }
    n_rules = triage.select("rule_set_id", "rule_id").n_unique()

    p("# TIER-1 stale refs — repealed-content triage proposals\n")
    p(f"**Tarih:** {date_tag}  |  **Kaynak:** `scripts/sut/triage_stale_refs.py`\n")
    p("## Özet\n")
    p(f"- TIER-1 referans: **{triage.height}** | unique kural: **{n_rules}**")
    p(f"- **A** (mülga içeriğe bağımlı — re-encode/sil): **{counts['A']}**")
    p(f"- **REVIEW** (kısmi overlap — insan gözü): **{counts['REVIEW']}**")
    p(f"- **B** (zararsız görünüyor): **{counts['B']}**\n")
    p(
        "_Öneriler otomatik skorla üretilmiştir; son karar insan onayıyla "
        "(plan K1). A/REVIEW satırlarının tamamı triage edilmelidir._\n"
    )
    p("---\n")

    detail_cols = [
        "rule_set_id",
        "rule_id",
        "clause_coordinate",
        "overlap_score",
        "matched_tokens",
        "struck_content",
    ]
    for cls, title in (
        ("A", "## Sınıf A — mülga içeriğe bağımlı (re-encode veya sil)\n"),
        ("REVIEW", "## Sınıf REVIEW — kısmi overlap (insan review)\n"),
        ("B", "## Sınıf B — zararsız görünüyor\n"),
    ):
        sub = triage.filter(pl.col("proposed_class") == cls).sort(
            ["rule_set_id", "rule_id"]
        )
        p(title)
        if sub.height == 0:
            p("_(none)_\n")
            p("---\n")
            continue
        if cls == "B":
            p(
                f"**{sub.height}** ref. Yalnızca koordinat + skor özeti "
                "(detay parquet'te):\n"
            )
            summary = (
                sub.group_by("rule_set_id")
                .agg(pl.len().alias("n"))
                .sort("n", descending=True)
            )
            p(_md_table(summary))
            p("")
            p("---\n")
            continue
        shown = sub.select(detail_cols).with_columns(
            pl.col("struck_content").map_elements(
                lambda t: _truncate(t), return_dtype=pl.Utf8
            )
        )
        p(_md_table(shown))
        p("")
        p("---\n")

    am = triage.filter(pl.col("amendment_refs") != "")
    if am.height:
        p("## Amendment RG grupları\n")
        p(
            "Aynı RG değişikliğiyle bayatlayan kurallar birlikte triage "
            "edilebilir:\n"
        )
        groups = (
            am.with_columns(pl.col("amendment_refs").str.split("; ").alias("rg_list"))
            .explode("rg_list")
            .filter(pl.col("rg_list").str.strip_chars() != "")
            .group_by("rg_list")
            .agg(
                n_refs=pl.len(),
                n_rules=pl.struct(["rule_set_id", "rule_id"]).n_unique(),
            )
            .sort("n_refs", descending=True)
            .rename({"rg_list": "amendment_rg"})
        )
        p(_md_table(groups))
        p("")

    return "\n".join(lines)


def main() -> int:
    from scripts.agent.stale_clause_refs import classify_refs, load_rule_refs

    args = _build_parser().parse_args()
    date_tag = args.date_tag or date.today().isoformat()

    refs = load_rule_refs(PROSE_RULES_GLOB)
    staleness = pl.read_parquet(
        SUT_CLAUSES_PARQUET,
        columns=[
            "clause_id",
            "clause_coordinate",
            "is_in_force",
            "is_superseded_marker",
            "had_struck_content",
        ],
    )
    classified = classify_refs(refs, staleness)
    t1 = classified.filter(pl.col("tier") == "TIER 1").filter(
        pl.col("clause_id").is_not_null()
    )

    clauses = pl.read_parquet(SUT_CLAUSES_PARQUET, columns=CLAUSE_TEXT_COLS)
    triage = build_triage(t1, clauses)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.output_dir / f"tier1-triage-{date_tag}.md"
    pq_path = args.output_dir / f"tier1-triage-{date_tag}.parquet"
    md_path.write_text(render_report(triage, date_tag), encoding="utf-8")
    triage.write_parquet(pq_path)

    counts = {
        c: triage.filter(pl.col("proposed_class") == c).height
        for c in ("A", "REVIEW", "B")
    }
    print(
        f"[triage_stale_refs] T1 refs={triage.height} "
        f"(A={counts['A']}, REVIEW={counts['REVIEW']}, B={counts['B']}) "
        f"-> {md_path.relative_to(PROJECT_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
