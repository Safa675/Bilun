"""(a) drug_claim_lines vs recete_clean: same events? dates, quantities, names, episodes, claim windows."""
import polars as pl

from common import anadata, drugs, hdr, headers, recete, save

d = drugs()
r = recete()
h = headers()

hdr("row counts / key uniqueness")
print("drug lines", d.height, "| recete rows", r.height)
kd = ["patient_id", "d_date", "drug_name_n"]
kr = ["HASTA_ID", "r_date", "ilac_adi_n"]
print("dup keys in drug lines:", d.height - d.select(kd).unique().height,
      "| dup keys in recete:", r.height - r.select(kr).unique().height)
print("distinct prescription_id:", d["prescription_id"].n_unique(), "of", d.height,
      "(one prescription per drug line)")

hdr("1:1 join on patient+date+name")
j = d.join(r, left_on=kd, right_on=kr, how="full", coalesce=False)
both = j.filter(pl.col("drug_claim_line_id").is_not_null() & pl.col("HASTA_ID").is_not_null())
print("matched", both.height, "| drug-only", j.filter(pl.col("HASTA_ID").is_null()).height,
      "| recete-only", j.filter(pl.col("drug_claim_line_id").is_null()).height)
chk = both.select(
    (pl.col("episode_id") != pl.col("RF_EPISODE")).sum().alias("episode_mismatch"),
    (pl.col("quantity") != pl.col("miktar")).sum().alias("qty_vs_miktar_mismatch"),
    (pl.col("ilac_adi") != pl.col("ilac_adi_ham")).sum().alias("raw_name_differs_from_clean"),
)
print(chk)

hdr("donem vs prescription year; kohort vs anadata kohort")
print(r.group_by("donem", pl.col("r_date").dt.year().alias("year")).len().sort("year"))
a = anadata().select("HASTA_ID", pl.col("kohort").alias("ana_kohort")).unique()
rk = r.join(a, on="HASTA_ID", how="left")
print("recete kohort != anadata kohort:", rk.filter(pl.col("kohort") != pl.col("ana_kohort")).height)

hdr("drug date vs claim window / claim type")
dh = d.join(h.select("claim_id", "claim_type", "department", "start", "end", "primary_icd10"),
            on="claim_id", how="left")
dh = dh.with_columns(
    (pl.col("end") - pl.col("start")).dt.total_days().alias("los_days"),
    (pl.col("d_date") == pl.col("start")).alias("on_first_day"),
    pl.col("d_date").is_between(pl.col("start"), pl.col("end")).alias("in_window"),
)
print(dh.select(pl.len().alias("lines"), pl.col("in_window").sum().alias("in_window"),
                pl.col("on_first_day").sum().alias("dated_on_claim_start")))
multi = dh.filter(pl.col("los_days") >= 1)
print("lines on multi-day claims:", multi.height, "| of which dated on day 1:",
      multi["on_first_day"].sum(), "| claims:", multi["claim_id"].n_unique(),
      "| median LOS days:", multi["los_days"].median(), "| max LOS:", multi["los_days"].max())
print(dh.group_by("claim_type").agg(pl.len().alias("drug_lines"),
                                     pl.col("claim_id").n_unique().alias("claims")).sort("drug_lines", descending=True))
claims_with_drugs = d["claim_id"].n_unique()
print("claims with >=1 drug line:", claims_with_drugs, "of", h.height)
print("drug lines per claim:", d.group_by("claim_id").len()["len"].value_counts().sort("len"))
save(dh.filter(pl.col("los_days") >= 1).select("drug_claim_line_id", "claim_type", "start", "end",
                                               "los_days", "drug_claim_date", "drug_name"),
     "a_multiday_claim_drugs")
