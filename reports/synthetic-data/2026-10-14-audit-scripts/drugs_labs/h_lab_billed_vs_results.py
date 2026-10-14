"""(h) billed lab lines (procedure_category='laboratuvar') vs lab_clean results; names/prices vs EK-2B as of date."""
import polars as pl

from common import ek2b, hdr, headers, labs, proc, save

p = proc().filter(pl.col("procedure_category") == "laboratuvar")
h = headers().select("claim_id", "episode_id", "claim_type", "start")
lb = labs()
e2 = ek2b()

hdr("billed lab lines")
print("billed lab lines:", p.height, "| claims:", p["claim_id"].n_unique(), "| distinct codes:", p["procedure_code"].n_unique(),
      "| quantity values:", p["quantity"].value_counts().rows())
pb = p.join(h, on="claim_id", how="left")
dup = pb.group_by("episode_id", "procedure_code").len().filter(pl.col("len") > 1)
print("same test billed twice in one episode:", dup.height)

hdr("billed test <-> result rows")
res = lb.group_by("basvuru_id", "SUB_CODE").agg(pl.len().alias("result_rows"), pl.col("l_date").first().alias("res_date"))
j = pb.join(res, left_on=["episode_id", "procedure_code"], right_on=["basvuru_id", "SUB_CODE"], how="full", coalesce=False)
print("billed with results:", j.filter(pl.col("procedure_line_id").is_not_null() & pl.col("basvuru_id").is_not_null()).height,
      "| billed without any result:", j.filter(pl.col("basvuru_id").is_null()).height,
      "| results without a billed line:", j.filter(pl.col("procedure_line_id").is_null()).height)
both = j.filter(pl.col("procedure_line_id").is_not_null() & pl.col("basvuru_id").is_not_null())
print("result rows per billed test (quantity=1):", both["result_rows"].value_counts().sort("result_rows").rows(),
      "| total result rows:", both["result_rows"].sum(), "vs billed units:", both["quantity"].sum())
print("procedure_date != result date:", both.filter(pl.col("p_date") != pl.col("res_date")).height)

hdr("billed lab name / price vs EK-2B version valid on the procedure date")
asof = pb.join(e2, left_on="procedure_code", right_on="code", how="left").filter(
    (pl.col("vf") <= pl.col("p_date")) & (pl.col("vt").is_null() | (pl.col("p_date") <= pl.col("vt"))))
asof = asof.sort("vf").unique("procedure_line_id", keep="last")
print("lines matched to an as-of EK-2B row:", asof.height, "of", p.height)
cmp = asof.with_columns(
    (pl.col("procedure_name") != pl.col("name")).alias("name_differs"),
    ((pl.col("unit_price_try") - pl.col("price_try")).abs() > 0.005).alias("unit_ne_asof_price"),
)
print(cmp.select(pl.col("name_differs").sum(), pl.col("unit_ne_asof_price").sum()))
latest = e2.sort("vf").group_by("code").agg(pl.col("price_try").last().alias("price_latest"), pl.col("vf").last().alias("latest_from"))
any_price = e2.select("code", "price_try", "vf").unique()
c2 = cmp.join(latest, left_on="procedure_code", right_on="code", how="left")
print("unit_price equals the LATEST (2026) EK-2B price:", ((c2["unit_price_try"] - c2["price_latest"]).abs() < 0.005).sum(),
      "| equals the as-of price:", ((c2["unit_price_try"] - c2["price_try"]).abs() < 0.005).sum(), "of", c2.height)
first_eff = (c2.join(any_price.rename({"price_try": "p_any", "vf": "vf_any"}), left_on="procedure_code", right_on="code")
             .filter((pl.col("unit_price_try") - pl.col("p_any")).abs() < 0.005)
             .group_by("procedure_line_id").agg(pl.col("vf_any").min().alias("price_first_valid_from")))
print("valid_from of the tariff whose price was used:", first_eff["price_first_valid_from"].value_counts().sort("count", descending=True).rows())
print(c2.select("procedure_line_id", "p_date", "procedure_code", "unit_price_try", "price_try", "price_latest").head(6))
c2 = c2.with_columns((pl.col("unit_price_try") / pl.col("price_try")).alias("overstatement"))
print("unit/as-of price ratio: median", c2["overstatement"].median(), "| min", c2["overstatement"].min(), "| max", c2["overstatement"].max())

hdr("billed lab arithmetic")
ar = p.with_columns((pl.col("quantity") * pl.col("unit_price_try")).alias("q_x_u"))
print(ar.select(pl.len(), ((pl.col("q_x_u") - pl.col("billed_amount_try")).abs() > 0.011).sum().alias("billed_ne_qty_x_unit"),
                (pl.col("billed_amount_try") < pl.col("q_x_u") - 0.011).sum().alias("billed_below"),
                (pl.col("billed_amount_try") > pl.col("q_x_u") + 0.011).sum().alias("billed_above"),
                (pl.col("expected_payable_try") > pl.col("billed_amount_try") + 0.011).sum().alias("payable_gt_billed")))
print(ar.with_columns((pl.col("billed_amount_try") / pl.col("q_x_u")).alias("billed_over_qxu"))
      .select(pl.col("billed_over_qxu").min().alias("min"), pl.col("billed_over_qxu").median().alias("median"), pl.col("billed_over_qxu").max().alias("max")))
print(ar.filter((pl.col("q_x_u") - pl.col("billed_amount_try")).abs() > 0.011)
      .select("procedure_line_id", "procedure_name", "quantity", "unit_price_try", "billed_amount_try", "expected_payable_try").head(6))
save(c2.select("procedure_line_id", "p_date", "procedure_code", "procedure_name", "unit_price_try", "price_try", "price_latest", "latest_from"),
     "h_lab_price_vs_ek2b")
