"""(g) medula_rejection_events vs repo MEDULA references, related lines, timing,
and the money impact on the referenced claim.
"""
import json

from common import *

r = claims("medula_rejection_events")
h = claims("claim_headers")
p = claims("procedure_claim_lines")
d = claims("drug_claim_lines")
m = claims("material_claim_lines")
known = json.loads((REPO / "data/medula/known_codes.json").read_text())
play = json.loads((REPO / "data/medula/rejection_playbook.json").read_text())
pb = {e["sonuc_kodu"]: e for e in play["entries"]}

print("events:", r.height)
print("sonuc_kodu == hata_kodu:", r.filter(pl.col("sonuc_kodu") == pl.col("hata_kodu")).height)
print("codes in known_codes.json:", r.filter(pl.col("sonuc_kodu").is_in(list(known))).height,
      "| in playbook:", r.filter(pl.col("sonuc_kodu").is_in(list(pb))).height)
print("timestamp has a time component:", r.filter(pl.col("rejection_timestamp").str.len_chars() > 10).height)
print("distinct claims:", r["claim_id"].n_unique(), " events per claim max:",
      r.group_by("claim_id").len()["len"].max())

hh = h.select("claim_id", "claim_type", "provider_type", "facility_tier", "department", "claim_start_date",
              "claim_end_date", "expected_total_billed_try", "expected_total_payable_try", "scenario_tag")
x = r.join(hh, on="claim_id", how="left").with_columns(
    (pl.col("rejection_timestamp").str.to_date() - pl.col("claim_end_date").str.to_date()).dt.total_days().alias("days_after_end"),
    (pl.col("rejection_timestamp").str.to_date() - pl.col("claim_start_date").str.to_date()).dt.total_days().alias("days_after_start"),
)
# keyword check: message contains at least one playbook keyword (casefold, Turkish-insensitive)
def kw_hit(row):
    e = pb.get(row["sonuc_kodu"])
    if not e:
        return None
    msg = row["hata_mesaji"].replace("İ", "i").replace("I", "ı").lower()
    return any(k.lower() in msg for k in e["hata_mesaji_keywords"])
x = x.with_columns(
    pl.struct("sonuc_kodu", "hata_mesaji").map_elements(kw_hit, return_dtype=pl.Boolean).alias("msg_has_playbook_kw"),
    pl.col("sonuc_kodu").map_elements(lambda c: ",".join(pb.get(c, {}).get("medula_stages", [])), return_dtype=pl.String).alias("playbook_stages"),
)
x = x.with_columns(pl.col("playbook_stages").str.contains(pl.col("medula_stage")).alias("stage_ok"))
print(x.select("sonuc_kodu", "medula_stage", "playbook_stages", "stage_ok", "msg_has_playbook_kw", "claim_type",
               "claim_start_date", "claim_end_date", "rejection_timestamp", "days_after_end"))
print("rejection gaps between consecutive events (days):",
      r.sort("rejection_timestamp").select(pl.col("rejection_timestamp").str.to_date().diff().dt.total_days())
      .to_series().drop_nulls().to_list())

# related line existence + fit
cat = catalog_versions().filter(pl.col("valid_to").is_null()).select("code", pl.col("name").alias("cat_name"))
pj = r.filter(pl.col("related_line_type") == "procedure").join(
    p.select("procedure_line_id", "procedure_code", "procedure_name", "procedure_date", "procedure_category",
             "is_package_included", "package_code", "billed_amount_try", "expected_payable_try",
             "denial_reason_expected", "procedure_specialty_code"),
    left_on="related_line_id", right_on="procedure_line_id", how="left")
print("\nprocedure-linked events:", pj.height, " line found:", pj.filter(pl.col("procedure_code").is_not_null()).height,
      " related_procedure_code == line code:", pj.filter(pl.col("related_procedure_code") == pl.col("procedure_code")).height,
      " related_procedure_line_id == related_line_id:", pj.filter(pl.col("related_procedure_line_id") == pl.col("related_line_id")).height)
print(pj.select("sonuc_kodu", "related_line_id", "procedure_code", "procedure_name", "procedure_category", "procedure_date",
                "is_package_included", "package_code", "billed_amount_try", "expected_payable_try", "denial_reason_expected",
                "procedure_specialty_code"))

# claim-level money of the rejected claims: does payable reflect the rejection?
print("\nrejected claims: billed vs payable, and payable of the related line")
print(x.select("sonuc_kodu", "claim_id", "claim_type", "provider_type", "expected_total_billed_try",
               "expected_total_payable_try"))

# 0901 duplicate: is there another line with the same code on the same claim/day?
dup = p.join(r.filter(pl.col("sonuc_kodu") == "0901").select("claim_id"), on="claim_id", how="semi") \
    .group_by("claim_id", "procedure_code", "procedure_date").agg(pl.len().alias("n"), pl.col("quantity").sum().alias("qty"))
print("\n0901 claim: same code/day groups with n>1 or qty>1:", dup.filter((pl.col("n") > 1) | (pl.col("qty") > 1)).rows())
print("0901 claim: code 615430 rows:", p.filter((pl.col("claim_id") == "F-SENTETIK-HASTA-0028-042") & (pl.col("procedure_code") == "615430"))
      .select("procedure_line_id", "procedure_date", "quantity", "billed_amount_try", "expected_payable_try").rows())

# 1205 date mismatch: related line date vs claim window
print("1205 related line date vs claim window:",
      pj.filter(pl.col("sonuc_kodu") == "1205").select("procedure_date").rows(),
      x.filter(pl.col("sonuc_kodu") == "1205").select("claim_start_date", "claim_end_date").rows())

# 0704 UTS: material line flags
mj = r.filter(pl.col("related_line_type") == "material").join(
    m.select("material_line_id", "material_code", "material_name", "uts_registered", "titubb_registered",
             "titubb_uts_barcode_documentation_missing", "billed_amount_try", "expected_payable_try", "denial_reason_expected"),
    left_on="related_line_id", right_on="material_line_id", how="left")
print("\n0704 related material:", mj.select("related_line_id", "material_code", "material_name", "uts_registered",
                                           "titubb_registered", "titubb_uts_barcode_documentation_missing",
                                           "billed_amount_try", "expected_payable_try", "denial_reason_expected").rows())
print("material lines with uts_registered == False in whole cohort:", m.filter(~pl.col("uts_registered")).select(
    "material_line_id", "material_name", "billed_amount_try", "expected_payable_try").rows())

# 0411 drug report: claim-level link only; do drug lines exist / carry report flags?
dl = d.filter(pl.col("claim_id") == "F-SENTETIK-HASTA-0031-045").select(
    "drug_claim_line_id", "drug_name", "billed_amount_try", "expected_payable_try", "drug_specialty_board_report_present",
    "denial_reason_expected")
print("\n0411 claim drug lines:", dl.rows())
print("drug_specialty_board_report_present non-null in cohort:", d["drug_specialty_board_report_present"].drop_nulls().len())

# 1102 uncontracted facility: same provider/claim type paid elsewhere? claim payable
print("\n1102 claim header:", x.filter(pl.col("sonuc_kodu") == "1102").select(
    "claim_id", "claim_type", "provider_type", "facility_tier", "expected_total_billed_try", "expected_total_payable_try").rows())
print("0521 claim header:", x.filter(pl.col("sonuc_kodu") == "0521").select(
    "claim_id", "claim_type", "claim_start_date", "rejection_timestamp", "expected_total_billed_try", "expected_total_payable_try").rows())
# 0315 specialty: department vs specialty code
print("0315 claim department / line specialty:", x.filter(pl.col("sonuc_kodu") == "0315").select("department").rows(),
      pj.filter(pl.col("sonuc_kodu") == "0315").select("procedure_name", "procedure_specialty_code").rows())
print("procedure_specialty_code fill rate:", p.filter(pl.col("procedure_specialty_code").fill_null("") != "").height, "/", p.height)
# 1688: is 912550 a molecular microbiology test?
print("1688 code name in current EK-2B:", cat.filter(pl.col("code") == "912550").rows())
x.write_parquet(OUT / "g_medula.parquet")

# ---- money still flowing on rejected lines ----
lp = pl.concat([
    pj.select("sonuc_kodu", "related_line_id", "billed_amount_try", "expected_payable_try"),
    mj.select("sonuc_kodu", "related_line_id", "billed_amount_try", "expected_payable_try"),
])
print("\nline-linked events:", lp.height, "| rejected line still payable>0:", lp.filter(pl.col("expected_payable_try") > 0).height,
      "| payable == billed:", lp.filter((pl.col("expected_payable_try") - pl.col("billed_amount_try")).abs() <= 0.01).height)
print(lp.rows())
print("events not linked to any line (related_line_id empty):", r.filter(pl.col("related_line_id").fill_null("") == "").select("sonuc_kodu", "related_line_type").rows())
print("claim types / provider types of rejected claims:", x["claim_type"].value_counts().rows(), x["provider_type"].value_counts().rows())
print("days between service and rejection:", x["days_after_end"].to_list())
