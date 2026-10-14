"""Per-claim defect flags rolled up by demo tier (A showcase / B regression / C filler)."""
import json
import polars as pl
OUT = "/tmp/claude-1000/-home-safa-Documents-Bilun/a9cf6beb-cd1a-4613-ab9e-bddecbe1db1a/scratchpad/audit/bill_composition"
R = "/home/safa/Documents/Bilun/data/synthetic/sut"
L = pl.read_parquet(f"{OUT}/enriched_lines.parquet")
C = pl.read_parquet(f"{OUT}/enriched_claims.parquet")
D = pl.read_parquet(f"{R}/claims/claim_diagnoses.parquet")
man = json.load(open("/home/safa/Documents/Bilun/data/synthetic/demo_manifest.json"))
A, B = set(man["tier_a_patient_indices"]), set(man["tier_b_patient_indices"])
MED = ["Gogus Hastaliklari", "Noroloji", "Kardiyoloji", "kardiyoloji", "Onkoloji", "Ic Hastaliklari", "Endokrinoloji", "Hematoloji", "Gastroenteroloji", "Nefroloji"]
NONINP = ["poliklinik", "acil", "koruyucu", "meslek_hastaligi"]
real_surg = pl.col("is_surgical") & (pl.col("procedure_code") != "612070")

# diagnosis compatibility (same table as 31_checks_c_d.py)
import importlib.util
spec = importlib.util.spec_from_file_location("cd", f"{OUT}/31_checks_c_d.py")
src = open(f"{OUT}/31_checks_c_d.py").read()
RULES = eval(src.split("RULES = ", 1)[1].split("\n]\n", 1)[0] + "\n]")
dx = pl.concat([D.select("claim_id", pl.col("icd10_code").alias("icd")), C.select("claim_id", pl.col("primary_icd10").alias("icd"))]).unique()
dx = dx.with_columns(pl.concat_list([pl.when(pl.col("icd").str.contains(rx)).then(pl.lit(ch)).otherwise(pl.lit([], dtype=pl.List(pl.Utf8))) for rx, ch, _ in RULES]).list.unique().alias("ok"))
okc = dx.group_by("claim_id").agg(pl.col("ok").list.explode(keep_nulls=False, empty_as_null=False).unique().alias("okc"))
Lx = L.join(okc, on="claim_id", how="left").with_columns((real_surg & ~pl.col("chapter").is_in(pl.col("okc"))).alias("surg_no_dx"))

fem = r"(?i)vajin|histerektomi|douglas|myomektomi|uterus\b|inseminasyon|anne sütü|sezaryen"
mal = r"(?i)penil|penektomi|testis|testik|skrotum|prostat|orşi|varikosel"
Lx = Lx.with_columns(
    ((pl.col("procedure_name").str.contains(fem) | pl.col("chapter").is_in(["6.13", "7.11"])) & (pl.col("sex") == "E") |
     (pl.col("procedure_name").str.contains(mal) | (pl.col("chapter") == "6.14")) & (pl.col("sex") == "K")).alias("sex_bad"))
flags = Lx.group_by("claim_id").agg(
    (real_surg & pl.col("department").is_in(MED)).any().alias("F1_surgery_in_medical_dept"),
    (pl.col("is_major_surgery") & pl.col("claim_type").is_in(NONINP)).any().alias("F2_major_surgery_outpatient"),
    ((pl.col("procedure_category") == "yatak") & (pl.col("chapter") != "1")).any().alias("F3_bed_code_not_bed"),
    pl.col("sex_bad").any().alias("F4_sex_contradiction"),
    pl.col("surg_no_dx").any().alias("F5_surgery_without_matching_dx"),
    (pl.col("is_package_included") | ((pl.col("procedure_category") == "paket") & (pl.col("code_kind") != "EK-2C_P"))).any().alias("F7_package_incoherent"),
    (pl.col("procedure_code").is_in(["703600", "703720", "P700843"]) & (pl.col("age") >= 18)).any().alias("F8_child_item_on_adult"),
)
F = C.select("claim_id", "patient_id", "claim_type", "department", "primary_icd10", "los_nights").join(flags, on="claim_id", how="left")
bed = L.filter(pl.col("procedure_category") == "yatak").select("claim_id").unique().with_columns(pl.lit(True).alias("hb"))
F = F.join(bed, on="claim_id", how="left").with_columns(((pl.col("claim_type") == "yatis") & pl.col("hb").is_null()).alias("F6_inpatient_no_bed")).drop("hb")
F = F.fill_null(False)
fcols = [c for c in F.columns if c.startswith("F")]
F = F.with_columns(pl.sum_horizontal(fcols).alias("n_flags"),
                   pl.col("patient_id").str.slice(-4).alias("pidx")).with_columns(
    pl.when(pl.col("pidx").is_in(list(A))).then(pl.lit("A")).when(pl.col("pidx").is_in(list(B))).then(pl.lit("B")).otherwise(pl.lit("C")).alias("tier"))
print("flag totals (claims):", {c: int(F[c].sum()) for c in fcols})
print(F.group_by("tier").agg(pl.len().alias("claims"), (pl.col("n_flags") >= 1).sum().alias("claims_with_any_flag"),
                             (pl.col("n_flags") == 0).sum().alias("clean_claims")).sort("tier").to_dicts())
print("claims with >=1 flag overall:", F.filter(pl.col("n_flags") >= 1).height, "/", F.height)
pt = F.group_by("tier", "pidx").agg((pl.col("n_flags") >= 1).any().alias("bad"))
print("patients with >=1 flagged claim, by tier:", pt.group_by("tier").agg(pl.len().alias("patients"), pl.col("bad").sum().alias("flagged")).sort("tier").to_dicts())
print("Tier A claims:")
for r in F.filter(pl.col("tier") == "A").sort("claim_id").iter_rows(named=True):
    print("  ", r["claim_id"].replace("F-SENTETIK-HASTA-", ""), r["claim_type"], r["department"], r["primary_icd10"], "->", [c for c in fcols if r[c]])
print("clean (0-flag) claims:", F.filter(pl.col("n_flags") == 0).select(pl.col("claim_id").str.replace("F-SENTETIK-HASTA-", ""), "claim_type", "department", "tier").to_dicts())
F.write_parquet(f"{OUT}/claim_flags.parquet")
