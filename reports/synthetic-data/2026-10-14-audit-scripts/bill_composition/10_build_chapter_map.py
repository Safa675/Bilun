"""Build EK-2B code -> SUT chapter map from every raw EK-2B snapshot by forward-filling
numbered heading rows (code column null or an amendment marker, name like '6.4. ...')."""
import glob, re
import polars as pl
B = "/home/safa/Documents/Bilun/data/gazette/raw/annex=EK-2B"
OUT = "/tmp/claude-1000/-home-safa-Documents-Bilun/a9cf6beb-cd1a-4613-ab9e-bddecbe1db1a/scratchpad/audit/bill_composition"
HEAD_RE = r'(?s)^\s*"?\s*(\d+(?:\.[0-9A-ZÇĞİÖŞÜ]+)*)\.\s+(\S.*)$'
CODE_RE = r'^[A-Z]?\d{6}$'
frames = []
for f in sorted(glob.glob(f"{B}/effective_date=*/*.parquet")):
    df = pl.read_parquet(f)
    c0, c1 = df.columns[0], "Unnamed: 1"
    eff = f.split("effective_date=")[1].split("/")[0]
    d = (df.select(pl.col(c0).cast(pl.Utf8).str.strip_chars().alias("raw_code"),
                   pl.col(c1).cast(pl.Utf8).str.strip_chars().alias("raw_name"),
                   pl.col("Unnamed: 2").cast(pl.Utf8).str.strip_chars().alias("raw_desc"),
                   pl.col("Unnamed: 3").cast(pl.Utf8).str.strip_chars().alias("raw_puan"))
           .with_row_index("row"))
    is_head = (pl.col("raw_code").is_null() | pl.col("raw_code").str.starts_with("(")) & pl.col("raw_name").str.contains(HEAD_RE)
    num = pl.col("raw_name").str.extract(HEAD_RE, 1)
    # chapter = first two numeric/letter components (e.g. 6.4, 8.1, 9.C); top-level stays as-is
    parts = num.str.split(".")
    chap = pl.when(parts.list.len() >= 2).then(parts.list.get(0, null_on_oob=True) + "." + parts.list.get(1, null_on_oob=True)).otherwise(parts.list.get(0, null_on_oob=True))
    d = d.with_columns(
        pl.when(is_head).then(chap).otherwise(None).alias("chapter"),
        pl.when(is_head & (parts.list.len() <= 2)).then(pl.col("raw_name")).otherwise(None).alias("chapter_title"),
    ).with_columns(pl.col("chapter").forward_fill(), pl.col("chapter_title").forward_fill())
    # code may carry trailing amendment text e.g. '550200   (Değişik...' -> take leading token
    d = d.with_columns(pl.col("raw_code").str.extract(r'^([A-Z]?\d{6})', 1).alias("code"))
    d = d.filter(pl.col("code").is_not_null()).with_columns(pl.lit(eff).alias("snapshot"), pl.lit(f.split("/")[-1].startswith("MULGA")).alias("mulga"))
    frames.append(d.select("snapshot","mulga","code","raw_name","raw_desc","raw_puan","chapter","chapter_title"))
allm = pl.concat(frames)
allm.write_parquet(f"{OUT}/ref_ek2b_code_chapter_all_snapshots.parquet")
print("rows", allm.height, "snapshots", allm["snapshot"].n_unique())
# conflicts: same code mapped to >1 chapter across snapshots
conf = allm.group_by("code").agg(pl.col("chapter").unique().alias("chs")).filter(pl.col("chs").list.len() > 1)
print("codes with >1 chapter across snapshots:", conf.height)
print(conf.head(15).to_dicts())
# unique code->chapter: prefer non-mulga newest snapshot that is not 'unknown'
pref = (allm.with_columns(pl.when(pl.col("snapshot")=="unknown").then(pl.lit("0000")).otherwise(pl.col("snapshot")).alias("snap_sort"))
             .sort(["code","snap_sort"], descending=[False, True])
             .group_by("code", maintain_order=True).first())
pref.write_parquet(f"{OUT}/ref_ek2b_code_chapter.parquet")
print("unique codes mapped:", pref.height, "chapters:", pref["chapter"].n_unique())
print(pref.group_by("chapter","chapter_title").len().sort("chapter").to_dicts())
