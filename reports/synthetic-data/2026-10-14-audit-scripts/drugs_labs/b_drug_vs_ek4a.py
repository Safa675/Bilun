"""(b) drug identity vs EK-4A history as of drug_claim_date."""
import polars as pl

from common import CUR, drugs, ek4a, hdr, save

d = drugs()
e = ek4a()

hdr("EK-4A coverage window")
print("ek4a_history valid_from min/max:", e["vf"].min(), e["vf"].max(),
      "| claim drug dates:", d["d_date"].min(), d["d_date"].max())

# every EK-4A version row for the same kamu_no
j = d.join(e, left_on="drug_code", right_on="kamu_no", how="left", suffix="_ek")
code_known = j.group_by("drug_claim_line_id").agg(pl.col("vf").is_not_null().any().alias("code_in_ek4a"))
asof = j.filter(
    (pl.col("vf") <= pl.col("d_date")) & (pl.col("vu").is_null() | (pl.col("d_date") < pl.col("vu")))
)
dup_asof = asof.group_by("drug_claim_line_id").len().filter(pl.col("len") > 1)
print("lines with >1 as-of EK-4A row (ambiguous):", dup_asof.height)
asof1 = asof.unique("drug_claim_line_id", keep="first")
res = d.join(code_known, on="drug_claim_line_id").join(
    asof1.select("drug_claim_line_id", "barcode", "ek_name_n", pl.col("equivalence_group_ek"),
                 "discount_status", "discount_tier_1", "discount_tier_2", "discount_tier_3",
                 "discount_tier_4", "passivation_date", "activation_date", "entry_date", "vf", "vu", "status"),
    on="drug_claim_line_id", how="left")
res = res.with_columns(
    pl.col("ek_name_n").is_not_null().alias("active_on_date"),
)
first_seen = e.group_by("kamu_no").agg(pl.col("vf").min().alias("first_listed"))
res = res.join(first_seen, left_on="drug_code", right_on="kamu_no", how="left")

hdr("existence / validity on the claim date")
print(res.select(
    pl.len().alias("lines"),
    pl.col("code_in_ek4a").sum().alias("kamu_no_ever_in_ek4a"),
    pl.col("active_on_date").sum().alias("listed_on_claim_date"),
    (~pl.col("active_on_date")).sum().alias("NOT_listed_on_claim_date"),
))
notyet = res.filter(~pl.col("active_on_date"))
print(notyet.with_columns((pl.col("first_listed") > pl.col("d_date")).alias("listed_only_later"))
      .select("drug_claim_line_id", "drug_claim_date", "drug_code", "drug_name", "first_listed", "listed_only_later")
      .sort("drug_claim_date"))
save(notyet.select("drug_claim_line_id", "drug_claim_date", "drug_code", "drug_name", "first_listed"),
     "b_not_listed_on_claim_date")
# delisted (removed) before the claim date?
last_seen = e.group_by("kamu_no").agg(pl.col("vu").max().alias("last_until"),
                                      pl.col("vu").is_null().any().alias("still_open"))
gone = res.join(last_seen, left_on="drug_code", right_on="kamu_no", how="left").filter(
    (~pl.col("still_open")) & (pl.col("last_until") <= pl.col("d_date")))
print("lines whose kamu_no was removed from EK-4A before the claim date:", gone.height)

hdr("field agreement with the as-of EK-4A row (only lines listed on the date)")
ok = res.filter(pl.col("active_on_date"))
cmp = ok.select(
    pl.len().alias("n"),
    (pl.col("barkod") != pl.col("barcode")).sum().alias("barcode_mismatch"),
    (pl.col("drug_name_n") != pl.col("ek_name_n")).sum().alias("name_mismatch"),
    (pl.col("equivalence_group") != pl.col("equivalence_group_ek")).sum().alias("eq_group_mismatch"),
    (pl.col("passivation_date").fill_null("") != "").sum().alias("has_passivation_date"),
)
print(cmp)
print("name mismatches:")
print(ok.filter(pl.col("drug_name_n") != pl.col("ek_name_n")).select("drug_code", "drug_claim_date", "drug_name_n", "ek_name_n"))
print("eq-group mismatches:")
print(ok.filter(pl.col("equivalence_group") != pl.col("equivalence_group_ek")).select(
    "drug_code", "drug_claim_date", "equivalence_group", "equivalence_group_ek"))
print("passivation dates present:")
print(ok.filter(pl.col("passivation_date").fill_null("") != "").select(
    "drug_code", "drug_claim_date", "drug_name", "passivation_date", "activation_date"))

# barcode belongs to which kamu_no anywhere in EK-4A?
bc = e.select("barcode", "kamu_no").unique()
bmap = d.join(bc, left_on="barkod", right_on="barcode", how="left")
print("barkod not found anywhere in EK-4A:", bmap.filter(pl.col("kamu_no").is_null()).height,
      "| barkod mapped to a different kamu_no:", bmap.filter(pl.col("kamu_no").is_not_null() & (pl.col("kamu_no") != pl.col("drug_code"))).height)

hdr("empty equivalence_group on drug lines vs EK-4A")
print("lines with empty equivalence_group:", d.filter(pl.col("equivalence_group") == "").height)

hdr("discount_tier_expected vs EK-4A discount tiers on the date")
ok = ok.with_columns(
    pl.col("discount_tier_1").str.replace(",", ".").cast(pl.Float64, strict=False).alias("t1"),
    pl.col("discount_tier_2").str.replace(",", ".").cast(pl.Float64, strict=False).alias("t2"),
)
print(ok.select(
    pl.len().alias("n"),
    ((pl.col("discount_tier_expected") - pl.col("t1")).abs() < 1e-6).sum().alias("equals_asof_tier1"),
    ((pl.col("discount_tier_expected") - pl.col("t1")).abs() >= 1e-6).sum().alias("differs_from_asof_tier1"),
))
snap = pl.read_parquet(CUR / "ek4a_drugs.parquet").select(
    "kamu_no", pl.col("discount_tier_1").str.replace(",", ".").cast(pl.Float64, strict=False).alias("snap_t1"))
ok2 = ok.join(snap.unique("kamu_no"), left_on="drug_code", right_on="kamu_no", how="left")
print("equals ek4a_drugs.parquet (undated snapshot) tier1:",
      ((ok2["discount_tier_expected"] - ok2["snap_t1"]).abs() < 1e-6).sum(), "of", ok2.height)
print(ok.filter((pl.col("discount_tier_expected") - pl.col("t1")).abs() >= 1e-6).select(
    "drug_code", "drug_claim_date", "discount_status", "discount_tier_expected", "t1", "t2").head(15))
print(d["discount_tier_expected"].value_counts().sort("discount_tier_expected"))
