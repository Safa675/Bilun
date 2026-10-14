"""Lines whose code has no EK-2B row valid on the service date; trace first appearance + amendment note in raw annex snapshots."""
import glob, polars as pl
OUT = "/tmp/claude-1000/-home-safa-Documents-Bilun/a9cf6beb-cd1a-4613-ab9e-bddecbe1db1a/scratchpad/audit/bill_composition"
B = "/home/safa/Documents/Bilun/data/gazette/raw/annex=EK-2B"
L = pl.read_parquet(f"{OUT}/enriched_lines.parquet")
nv = L.filter(pl.col("ek2b_puan").is_null() & (pl.col("code_kind") != "EK-2C_P"))
codes = nv["base_code"].unique().to_list()
notes = []
for f in sorted(glob.glob(f"{B}/effective_date=*/*.parquet")):
    df = pl.read_parquet(f); c0 = df.columns[0]
    x = df.select(pl.col(c0).cast(pl.Utf8).alias("raw")).with_columns(pl.col("raw").str.extract(r"^\s*([A-Z]?\d{6})", 1).alias("code")).filter(pl.col("code").is_in(codes))
    for r in x.iter_rows(named=True):
        notes.append({"snapshot": f.split("effective_date=")[1].split("/")[0], "file": f.split("/")[-1][:6], "code": r["code"], "raw": r["raw"]})
N = pl.DataFrame(notes)
first = N.filter(pl.col("snapshot") != "unknown").sort("snapshot").group_by("code").agg(pl.col("snapshot").first().alias("first_snapshot"),
        pl.col("raw").filter(pl.col("raw").str.contains(r"Ek:|Değişik")).first().alias("amendment_note"))
print(nv.select(pl.col("procedure_line_id").str.replace("ISL-F-SENTETIK-HASTA-", "").alias("line"), "procedure_code", "pdate", "procedure_name").join(
    first.rename({"code": "procedure_code"}), on="procedure_code", how="left").to_dicts())
print("lines billed with a code not yet in EK-2B on the service date:", nv.height)
