"""(c) exam (muayene) lines vs department / age / setting; (d) ICD-10 vs surgical SUT chapter."""
import polars as pl
OUT = "/tmp/claude-1000/-home-safa-Documents-Bilun/a9cf6beb-cd1a-4613-ab9e-bddecbe1db1a/scratchpad/audit/bill_composition"
R = "/home/safa/Documents/Bilun/data/synthetic/sut"
pl.Config.set_tbl_rows(80); pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(230); pl.Config.set_fmt_str_lengths(60)
L = pl.read_parquet(f"{OUT}/enriched_lines.parquet")
C = pl.read_parquet(f"{OUT}/enriched_claims.parquet")
D = pl.read_parquet(f"{R}/claims/claim_diagnoses.parquet")
sid = lambda c: pl.col(c).str.replace("ISL-F-SENTETIK-HASTA-", "").str.replace("F-SENTETIK-HASTA-", "")

print("=" * 30, "(c) EXAM LINES")
ex = L.filter(pl.col("procedure_category") == "muayene")
print("muayene lines:", ex.height)
cnt = C.select("claim_id", "claim_type").join(ex.group_by("claim_id").len(), on="claim_id", how="left").fill_null(0)
print("muayene lines per claim:", cnt["len"].value_counts().sort("len").to_dicts())
print("claims with 0 exam lines by type:", cnt.filter(pl.col("len") == 0).group_by("claim_type").len().to_dicts())
print("exam lines by SUT chapter:", ex.group_by("chapter", "chapter_title").len().sort("len", descending=True).to_dicts())
tab = ex.group_by("procedure_code", "procedure_name", "chapter").agg(
    pl.len().alias("n"), pl.col("department").unique().sort().alias("depts"), pl.col("claim_type").unique().sort().alias("types"),
    pl.col("age").min().alias("min_age")).sort("n", descending=True)
print(tab)
# plausibility classes (judgment): standard physician visit codes for the setting
plaus = ((pl.col("procedure_code") == "520030") & pl.col("claim_type").is_in(["poliklinik", "koruyucu", "meslek_hastaligi", "gunubirlik"])) | \
        ((pl.col("procedure_code") == "520020") & (pl.col("claim_type") == "acil")) | \
        ((pl.col("procedure_code") == "520010") & pl.col("claim_type").is_in(["yatis", "gunubirlik"])) | \
        ((pl.col("procedure_code") == "520090") & (pl.col("claim_type") == "poliklinik"))
print("exam lines that are a standard visit code fitting the setting (judgment):", ex.filter(plaus).height, "/", ex.height)
eye = ex.filter(pl.col("chapter") == "7.8")
print("ophthalmology exams (ch 7.8) billed:", eye.height, "lines; departments:", eye["department"].unique().sort().to_list(),
      "| any eye department in cohort:", C.filter(pl.col("department").str.to_lowercase().str.contains("göz|goz")).height)
print("ENT exams (7.9):", ex.filter(pl.col("chapter") == "7.9").height, " dermatology Wood (7.1):", ex.filter(pl.col("chapter") == "7.1").height,
      " EMG/neurophys (7.7):", ex.filter(pl.col("chapter") == "7.7").select("department").to_series().to_list())
child = ex.filter(pl.col("procedure_code").is_in(["703600", "703720"]))
print("child/infant eye exams (703600 'Çocuklarda', 703720 'bebek için'):", child.height, "| on patients aged >=18:",
      child.filter(pl.col("age") >= 18).height, "| ages:", sorted(child["age"].to_list()))
print("cohort age range:", C["age"].min(), "-", C["age"].max(), "| claims age<18:", C.filter(pl.col("age") < 18).height)
donor = ex.filter(pl.col("procedure_code") == "705240")
blood = L.filter(pl.col("procedure_code").str.contains(r"^7053|^7054")).select("claim_id").unique()
tx = L.filter(pl.col("procedure_name").str.to_lowercase().str.contains("transplant|donör|donor|kemik iliği nakli|organ nakli") & (pl.col("procedure_code") != "705240")).select("claim_id", "procedure_name")
print("705240 'Donör muayenesi' (catalog ch", donor["chapter"].unique().to_list(), "):", donor.height, "lines; on claims with blood products:",
      donor.join(blood, on="claim_id").height, "; with transplant/donor procedure:", donor.join(tx.select("claim_id").unique(), on="claim_id").height)
print("   catalog description:", donor["cat_desc"].unique().to_list()[:1])
anaes_ex = ex.filter(pl.col("procedure_code").is_in(["550010", "550090", "550100", "520070"]))
print("anaesthesia codes used as the claim's exam line:", anaes_ex.height, anaes_ex.group_by("procedure_name").len().to_dicts())
gz = L.filter(pl.col("procedure_code") == "520021")
gzc = gz.select("claim_id", "claim_type").join(L.group_by("claim_id").len(), on="claim_id")
print("520021 'Yeşil alan muayenesi' lines:", gz.height, "| claim types:", gz["claim_type"].to_list(),
      "| billed with other lines on same claim (catalog: not billable with any other SUT item):", gzc.filter(pl.col("len") > 1).height,
      "| desc:", gz["cat_desc"].unique().to_list())
fb = L.filter(pl.col("procedure_code") == "520080")
print("520080 'Birinci basamak poliklinik muayenesi' (catalog: 'Birinci basamak sağlık kuruluşlarında'):", fb.height,
      "lines; facility tiers:", fb["facility_tier"].to_list(), "types:", fb["claim_type"].to_list())
ap = L.filter((pl.col("procedure_code") == "520020") & (pl.col("claim_type") != "acil"))
print("520020 'Acil poliklinik muayenesi' on non-acil claims:", ap.height, ap.select(sid("claim_id"), "claim_type").to_dicts())
cbrn = L.filter(pl.col("procedure_code") == "530004")
print("530004 CBRN decontamination exam:", cbrn.select(sid("claim_id"), "claim_type", "department", "primary_icd10").to_dicts())
acil_claims = C.filter(pl.col("claim_type") == "acil").select("claim_id")
acil_ex = acil_claims.join(ex.select("claim_id", "procedure_code", "procedure_name"), on="claim_id", how="left")
print("exam line on the 5 acil claims:", acil_ex.with_columns(sid("claim_id")).to_dicts())
print("claims with >1 exam line (multi-branch visit):", cnt.filter(pl.col("len") > 1).height)

print("\n" + "=" * 30, "(d) ICD-10 vs SURGICAL CHAPTER")
# Coarse, deliberately generous judgment table: ICD block -> SUT 6.x chapters that could treat it surgically.
RULES = [  # (regex on ICD code, compatible chapters, label)
    (r"^C1[5-9]|^C2[0-6]", ["6.6", "6.3", "6.4"], "C15-C26 digestive ca"),
    (r"^C3[0-9]", ["6.5", "6.2", "6.3", "6.4"], "C30-C39 respiratory/intrathoracic ca"),
    (r"^C50", ["6.3", "6.1", "6.4"], "C50 breast ca"),
    (r"^C6[0-3]", ["6.14", "6.12", "6.4"], "C60-C63 male genital ca"),
    (r"^C8[1-9]|^C9[0-6]", ["6.4", "6.7", "6.8"], "C81-C96 lymphoid/haematopoietic"),
    (r"^D5[0-9]|^D6[0-9]|^D7[0-9]|^D8[0-9]", ["6.4", "6.5"], "D50-D89 blood/immune (incl. D86 sarcoid)"),
    (r"^E0[0-7]", ["6.11", "6.2"], "E00-E07 thyroid"),
    (r"^E1[0-4]\.[4-7]", ["6.1", "6.4", "6.7", "6.8"], "E10-E14 with complications"),
    (r"^E6[5-8]", ["6.6", "6.3"], "E65-E68 obesity"),
    (r"^G4[0-1]", ["6.8"], "G40-G41 epilepsy"),
    (r"^G47\.3", ["6.2", "6.5"], "G47.3 sleep apnoea"),
    (r"^G1[0-3]|^G6[0-4]|^G9", ["6.8", "6.6", "6.5"], "G10-G13/G60-G64/G90-G99 neuromuscular/CNS"),
    (r"^H[0-5]", ["6.9"], "H00-H59 eye"),
    (r"^I1[1-3]", ["6.4", "6.12"], "I11-I13 hypertensive heart/renal"),
    (r"^I[2-9]", ["6.4"], "I20-I99 circulatory (excl. I10)"),
    (r"^I6", ["6.8"], "I60-I69 cerebrovascular (adds 6.8)"),
    (r"^J", ["6.5", "6.2", "6.3"], "J respiratory"),
    (r"^K", ["6.6", "6.3"], "K digestive"),
    (r"^M", ["6.7", "6.8", "6.1"], "M musculoskeletal"),
    (r"^N0|^N1|^N2|^N3", ["6.12", "6.4", "6.3"], "N00-N39 urinary/CKD"),
    (r"^S7", ["6.7", "6.1", "6.4"], "S70-S79 hip/thigh injury"),
    (r"^Z90\.4", ["6.6"], "Z90.4 absent GI part"),
    (r"^Z95\.1", ["6.4"], "Z95.1 CABG graft"),
    (r"^Z96\.6", ["6.7"], "Z96.6 joint implant"),
]
NONE = "R05,R51,R53,F32.9,E78.0,E11.9,I10,Z51.1,E02/E03/E05 handled by E0x rule"
dx = pl.concat([D.select("claim_id", pl.col("icd10_code").alias("icd")), C.select("claim_id", pl.col("primary_icd10").alias("icd"))]).unique()
exprs = [pl.when(pl.col("icd").str.contains(rx)).then(pl.lit(ch)).otherwise(pl.lit([], dtype=pl.List(pl.Utf8))) for rx, ch, _ in RULES]
dx = dx.with_columns(pl.concat_list(exprs).list.unique().alias("ok_ch"))
print("ICD codes with no surgical indication in table:", dx.filter(pl.col("ok_ch").list.len() == 0)["icd"].unique().sort().to_list())
ok_claim = dx.group_by("claim_id").agg(pl.col("ok_ch").list.explode(keep_nulls=False, empty_as_null=False).unique().alias("ok_claim"), pl.col("icd").unique().sort().alias("dx_all"))
ok_prim = dx.join(C.select("claim_id", pl.col("primary_icd10").alias("icd")), on=["claim_id", "icd"]).group_by("claim_id").agg(
    pl.col("ok_ch").list.explode(keep_nulls=False, empty_as_null=False).unique().alias("ok_primary"))
S = L.filter(pl.col("is_surgical") & (pl.col("procedure_code") != "612070")).join(ok_claim, on="claim_id", how="left").join(ok_prim, on="claim_id", how="left")
S = S.with_columns(pl.col("chapter").is_in(pl.col("ok_claim")).alias("ok_any_dx"), pl.col("chapter").is_in(pl.col("ok_primary")).alias("ok_prim_dx"))
print("surgical lines checked (6.x incl. packages, excl. 612070 used as bed):", S.height, "on", S["claim_id"].n_unique(), "claims")
print("lines with NO compatible dx (any dx on claim):", S.filter(~pl.col("ok_any_dx")).height, "| vs primary only:", S.filter(~pl.col("ok_prim_dx")).height)
bad_claims = S.filter(~pl.col("ok_any_dx"))["claim_id"].n_unique()
print(f"claims with >=1 surgical line lacking any compatible dx: {bad_claims} / {S['claim_id'].n_unique()} surgical claims (/ {C.height} all)")
print("claims where NO surgical line matches any dx:", S.group_by("claim_id").agg(pl.col("ok_any_dx").any().alias("a")).filter(~pl.col("a")).height)
w = S.filter(~pl.col("ok_any_dx")).group_by("claim_id").agg(
    pl.len().alias("n_bad"), pl.col("billed_amount_try").sum().round(0).alias("bad_billed"),
    pl.col("procedure_name").str.slice(0, 40).alias("bad_ops"), pl.col("chapter").alias("chs")).join(
    C.select("claim_id", "claim_type", "department", "primary_icd10"), on="claim_id").join(ok_claim.select("claim_id", "dx_all"), on="claim_id"
).sort(["n_bad", "bad_billed"], descending=True)
print(w.with_columns(sid("claim_id")).select("claim_id", "claim_type", "department", "dx_all", "n_bad", "bad_billed", "bad_ops").head(15))
inc612 = L.filter(pl.col("is_surgical")).join(ok_claim, on="claim_id", how="left").with_columns(pl.col("chapter").is_in(pl.col("ok_claim")).alias("ok"))
print("sensitivity incl. 612070:", inc612.filter(~pl.col("ok"))["claim_id"].n_unique(), "claims")
prim_mismatch = C.select("claim_id", "primary_icd10").join(D.filter(pl.col("diagnosis_role") == "birincil").select("claim_id", pl.col("icd10_code").alias("birincil")), on="claim_id").filter(pl.col("primary_icd10") != pl.col("birincil"))
print("header primary_icd10 != claim_diagnoses birincil:", prim_mismatch.height, prim_mismatch.with_columns(sid("claim_id")).to_dicts())
