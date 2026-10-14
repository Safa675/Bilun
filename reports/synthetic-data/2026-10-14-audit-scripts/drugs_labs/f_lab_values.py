"""(f) lab_clean: SUB_CODE catalogue, units, reference ranges, abnormal flag, panel structure, value realism."""
import polars as pl

from common import ek2b, hdr, labs, save

lb = labs()
e2 = ek2b()

hdr("shape")
print("rows", lb.height, "| patients", lb["HASTA_ID"].n_unique(), "| basvuru (episodes)", lb["basvuru_id"].n_unique(),
      "| distinct SUB_CODE", lb["SUB_CODE"].n_unique())
grp = lb.group_by("basvuru_id", "SUB_CODE").agg(pl.len().alias("rows"))
print("(episode, test) groups:", grp.height, "| rows per group:", grp["rows"].value_counts().sort("rows").rows())
print("columns:", lb.columns, "-> no test-name column, no billed/unbilled flag, no sample/specimen, no result time")

hdr("SUB_CODE vs EK-2B catalogue (name, any version)")
names = e2.group_by("code").agg(pl.col("name").last().alias("ek2b_name"))
codes = lb.select("SUB_CODE").unique().join(names, left_on="SUB_CODE", right_on="code", how="left")
print("SUB_CODEs found in EK-2B:", codes["ek2b_name"].is_not_null().sum(), "of", codes.height)

hdr("within one (episode, test): units / ref ranges / organ system / values")
w = lb.group_by("basvuru_id", "SUB_CODE").agg(
    pl.len().alias("rows"),
    pl.col("birim").n_unique().alias("n_units"),
    pl.struct("ref_alt", "ref_ust").n_unique().alias("n_refranges"),
    pl.col("organ_sistemi").n_unique().alias("n_organ"),
    pl.col("sonuc_sayisal").n_unique().alias("n_values"),
    (pl.col("sonuc_sayisal").max() / pl.col("sonuc_sayisal").min()).alias("max_over_min"),
)
print(w.select(
    pl.len().alias("groups"),
    (pl.col("n_units") > 1).sum().alias("groups_with_>1_unit"),
    (pl.col("n_refranges") > 1).sum().alias("groups_with_>1_refrange"),
    (pl.col("n_organ") > 1).sum().alias("groups_with_>1_organ_system"),
    (pl.col("n_values") == pl.col("rows")).sum().alias("groups_all_values_distinct"),
    pl.col("max_over_min").median().alias("median_max/min_same_test_same_day"),
))
c = lb.group_by("SUB_CODE").agg(pl.col("birim").n_unique().alias("units"), pl.col("organ_sistemi").n_unique().alias("organs"))
print("codes:", c.height, "| codes with >1 unit across the cohort:", c.filter(pl.col("units") > 1).height,
      "| with >1 organ system:", c.filter(pl.col("organs") > 1).height)
print("unit vocabulary:", lb["birim"].value_counts().sort("count", descending=True).rows())
print("organ_sistemi vocabulary:", lb["organ_sistemi"].value_counts().sort("count", descending=True).rows())

hdr("reference ranges")
print(lb.select(pl.col("ref_alt").min().alias("ref_alt_min"), pl.col("ref_alt").max().alias("ref_alt_max"),
                pl.col("ref_ust").min().alias("ref_ust_min"), pl.col("ref_ust").max().alias("ref_ust_max"),
                pl.struct("ref_alt", "ref_ust").n_unique().alias("distinct_ranges"),
                (pl.col("ref_alt") >= pl.col("ref_ust")).sum().alias("inverted")))

hdr("abnormal flag and qualitative result")
ab = lb.with_columns(((pl.col("sonuc_sayisal") < pl.col("ref_alt")) | (pl.col("sonuc_sayisal") > pl.col("ref_ust"))).alias("calc_abn"))
print(ab.select(pl.len().alias("rows"), (pl.col("calc_abn") != pl.col("anormal_mi")).sum().alias("flag_inconsistent"),
                pl.col("anormal_mi").sum().alias("abnormal_rows"), pl.col("anormal_mi").mean().alias("abnormal_share"),
                (pl.col("sonuc_sayisal") > pl.col("ref_ust")).sum().alias("high"),
                (pl.col("sonuc_sayisal") < pl.col("ref_alt")).sum().alias("low")))
ep_ab = lb.group_by("basvuru_id").agg(pl.col("anormal_mi").any().alias("any_abn"))
print("episodes with >=1 abnormal result:", ep_ab["any_abn"].sum(), "of", ep_ab.height)
pos = lb.filter(pl.col("sonuc_nitel") != "")
print("sonuc_nitel values:", lb["sonuc_nitel"].value_counts().rows(),
      "| 'Pozitif' rows that also carry a numeric value + quantitative unit:",
      pos.filter(pl.col("sonuc_sayisal").is_not_null()).height)
print(pos.select("basvuru_id", "SUB_CODE", "sonuc_sayisal", "sonuc_nitel", "birim").head(5))

hdr("test-type sanity using EK-2B names (judgment on what the unit should be)")
tl = lb.join(names, left_on="SUB_CODE", right_on="code", how="left")
tl = tl.with_columns(
    pl.when(pl.col("ek2b_name").str.contains(r"(?i)oranı")).then(pl.lit("flow_cytometry_percent"))
    .when(pl.col("ek2b_name").str.contains(r"(?i)kalitatif|tarama")).then(pl.lit("qualitative/screen"))
    .when(pl.col("ek2b_name").str.contains(r"(?i)IgE antikoru")).then(pl.lit("specific_IgE"))
    .otherwise(pl.lit("other")).alias("ttype"))
fc = tl.filter(pl.col("ttype") == "flow_cytometry_percent")
print("flow-cytometry percentage tests: rows", fc.height, "| value > 100:", fc.filter(pl.col("sonuc_sayisal") > 100).height,
      "| unit not '%':", fc.filter(pl.col("birim") != "%").height)
qs = tl.filter(pl.col("ttype") == "qualitative/screen")
print("qualitative/screen tests: rows", qs.height, "| with numeric result + quantitative unit:", qs.filter(pl.col("sonuc_sayisal").is_not_null()).height)
ige = tl.filter(pl.col("ttype") == "specific_IgE")
print("specific IgE tests: rows", ige.height, "| unit kU/L:", ige.filter(pl.col("birim").str.contains("kU")).height,
      "| units used:", ige["birim"].unique().sort().to_list())
print(tl.filter(pl.col("SUB_CODE") == "L107480").select("basvuru_id", "ek2b_name", "sonuc_sayisal", "birim", "ref_alt", "ref_ust", "anormal_mi", "organ_sistemi"))
save(tl.select("HASTA_ID", "basvuru_id", "SUB_CODE", "ek2b_name", "sonuc_sayisal", "sonuc_nitel", "birim", "ref_alt", "ref_ust",
               "anormal_mi", "organ_sistemi", "ttype"), "f_lab_rows_with_names")

hdr("repeats across patients / value uniqueness")
print("distinct numeric values:", lb["sonuc_sayisal"].n_unique(), "of", lb.height)
dupv = lb.group_by("sonuc_sayisal").agg(pl.col("HASTA_ID").n_unique().alias("pts")).filter(pl.col("pts") > 1)
print("numeric values shared by >1 patient:", dupv.height)
print("kohort/donem:", lb.group_by("donem", pl.col("l_date").dt.year().alias("year")).len().sort("year").rows())
