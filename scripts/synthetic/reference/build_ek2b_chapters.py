"""Build the EK-2B chapter table from the raw list's heading rows.

The curated EK-2B history drops the heading rows (``scripts/sut/catalogs/price_history.py``),
so the code → chapter link exists only in the raw lists. This builder reads the raw EK-2B
lists in force during the demo window (2026-01-31 and 2026-07-07) and writes:

- ``data/synthetic/reference/ek2b_code_chapter.parquet``: one row per code with its
  chapter group (level 1, e.g. ``6``), chapter (level 2 when present, e.g. ``6.4`` or
  ``9.A``) and section (level 3 when present, e.g. ``8.3.1`` or ``9.B.1``);
- ``data/synthetic/reference/ek2b_chapters.csv``: one row per chapter with its code count,
  first and last code in list order, and whether its codes form one block in the list.

Usage:
    python -m scripts.synthetic.reference.build_ek2b_chapters
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

REPO = Path(__file__).resolve().parents[3]
RAW_EK2B = REPO / "data/gazette/raw/annex=EK-2B"
SNAPSHOTS = ("2026-01-31", "2026-07-07")
OUT_DIR = REPO / "data/synthetic/reference"
CODE_MAP_PATH = OUT_DIR / "ek2b_code_chapter.parquet"
CHAPTERS_PATH = OUT_DIR / "ek2b_chapters.csv"

# Numbered headings ("6.4. ...", "8.3.1. ...") and lettered ones ("9.A. ...", "9.B.1. ...");
# some titles span two lines.
_HEADING = r"(?s)^(\d+(?:\.(?:\d+|[A-Z]))*)\.\s+(.+)$"
_CODE = r"^\s*([A-Z]?\d{6})\b"


def _snapshot_path(effective_date: str) -> Path:
    folder = RAW_EK2B / f"effective_date={effective_date}"
    paths = sorted(p for p in folder.glob("*.parquet") if not p.name.startswith("MULGA"))
    if len(paths) != 1:
        raise FileNotFoundError(f"expected one current EK-2B list in {folder}, found {len(paths)}")
    return paths[0]


def _clean(expr: pl.Expr) -> pl.Expr:
    return expr.str.replace_all(r"\s+", " ").str.strip_chars()


def chapters_from_snapshot(path: Path) -> pl.DataFrame:
    """Return one row per code in list order with its heading hierarchy."""
    raw = pl.read_parquet(path)
    frame = raw.select(
        pl.col(raw.columns[0]).cast(pl.String).alias("cell"),
        pl.col(raw.columns[1]).cast(pl.String).alias("name"),
    ).with_row_index("row")
    heading = pl.col("name").str.extract_groups(_HEADING)
    frame = frame.with_columns(
        pl.when(pl.col("cell").is_null()).then(heading.struct.field("1")).alias("heading_id"),
        pl.when(pl.col("cell").is_null()).then(_clean(heading.struct.field("2"))).alias("heading_title"),
    ).with_columns(pl.col("heading_id").str.split(".").list.len().alias("heading_level"))

    def level(n: int, name: str) -> list[pl.Expr]:
        is_level = pl.col("heading_level") == n
        return [
            pl.when(is_level).then(pl.col("heading_id")).forward_fill().alias(f"l{n}_id"),
            pl.when(is_level).then(pl.col("heading_title")).forward_fill().alias(f"l{n}_title"),
        ]

    frame = frame.with_columns(*level(1, "group"), *level(2, "chapter"), *level(3, "section"))
    # A deeper heading only applies inside the heading above it.
    in_l1 = pl.col("l2_id").str.starts_with(pl.col("l1_id") + ".")
    in_l2 = pl.col("l3_id").str.starts_with(pl.col("l2_id") + ".")
    frame = frame.with_columns(
        pl.when(in_l1).then(pl.col("l2_id")).alias("l2_id"),
        pl.when(in_l1).then(pl.col("l2_title")).alias("l2_title"),
    ).with_columns(
        pl.when(in_l2).then(pl.col("l3_id")).alias("l3_id"),
        pl.when(in_l2).then(pl.col("l3_title")).alias("l3_title"),
    )
    return (
        frame.with_columns(pl.col("cell").str.extract(_CODE, 1).alias("code"))
        .filter(pl.col("code").is_not_null())
        .select(
            "row",
            "code",
            pl.col("l1_id").alias("group_id"),
            pl.col("l1_title").alias("group_title"),
            pl.coalesce("l2_id", "l1_id").alias("chapter_id"),
            pl.coalesce("l2_title", "l1_title").alias("chapter_title"),
            pl.coalesce("l3_id", "l2_id", "l1_id").alias("section_id"),
            pl.coalesce("l3_title", "l2_title", "l1_title").alias("section_title"),
        )
    )


def build() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return (code map, chapter summary) for the demo window's EK-2B lists."""
    per_snapshot = [
        chapters_from_snapshot(_snapshot_path(d)).with_columns(pl.lit(d).alias("snapshot"))
        for d in SNAPSHOTS
    ]
    keys = ["code", "group_id", "chapter_id", "section_id"]
    both = pl.concat(per_snapshot)
    conflicts = both.group_by("code").agg(pl.struct(keys[1:]).n_unique().alias("n")).filter(pl.col("n") > 1)
    if conflicts.height:
        raise ValueError(f"codes change chapter between snapshots: {conflicts['code'].to_list()[:10]}")
    latest = per_snapshot[-1]
    code_map = (
        both.group_by("code")
        .agg(
            pl.col("group_id", "group_title", "chapter_id", "chapter_title", "section_id", "section_title").last(),
            pl.col("snapshot").unique().sort().str.join(",").alias("snapshots"),
        )
        .sort("code")
    )
    blocks = latest.group_by("chapter_id").agg(
        pl.col("group_id").first(),
        pl.col("chapter_title").first(),
        pl.len().alias("n_codes"),
        pl.col("row").min().alias("first_row"),
        pl.col("row").max().alias("last_row"),
        pl.col("code").sort_by("row").first().alias("first_code"),
        pl.col("code").sort_by("row").last().alias("last_code"),
    )
    # A chapter is one block when no other chapter's code sits between its first and last row.
    interleaved = (
        blocks.join(latest.select("row", pl.col("chapter_id").alias("other")), how="cross")
        .filter(
            (pl.col("row") > pl.col("first_row"))
            & (pl.col("row") < pl.col("last_row"))
            & (pl.col("other") != pl.col("chapter_id"))
        )
        .group_by("chapter_id")
        .agg(pl.len().alias("n_foreign"))
    )
    chapters = (
        blocks.join(interleaved, on="chapter_id", how="left")
        .with_columns((pl.col("n_foreign").fill_null(0) == 0).alias("one_block_in_list"))
        .sort("first_row")
        .select("group_id", "chapter_id", "chapter_title", "n_codes", "first_code", "last_code", "one_block_in_list")
    )
    return code_map, chapters


def main() -> None:
    code_map, chapters = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    code_map.write_parquet(CODE_MAP_PATH)
    chapters.write_csv(CHAPTERS_PATH)
    print(f"{code_map.height} codes in {chapters.height} chapters -> {CODE_MAP_PATH.relative_to(REPO)}")
    print(f"chapter summary -> {CHAPTERS_PATH.relative_to(REPO)}")


if __name__ == "__main__":
    main()
