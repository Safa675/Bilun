"""Sensitivity checks: chapter-mixing definitions, 612070 exclusion, misc IDs."""
import polars as pl
OUT = "/tmp/claude-1000/-home-safa-Documents-Bilun/a9cf6beb-cd1a-4613-ab9e-bddecbe1db1a/scratchpad/audit/bill_composition"
L = pl.read_parquet(f"{OUT}/enriched_lines.parquet"); C = pl.read_parquet(f"{OUT}/enriched_claims.parquet")
sid = lambda c: pl.col(c).str.replace("ISL-F-SENTETIK-HASTA-", "").str.replace("F-SENTETIK-HASTA-", "")
def mix(df, label):
    g = df.group_by("claim_id").agg(pl.col("chapter").filter(pl.col("chapter").str.starts_with("6.")).n_unique().alias("s"))
    g = C.select("claim_id").join(g, on="claim_id", how="left").fill_null(0)
    print(f"{label}: >=1 surg ch {g.filter(pl.col('s')>=1).height}, >=2 {g.filter(pl.col('s')>=2).height}, >=3 {g.filter(pl.col('s')>=3).height} /94")
mix(L, "incl. 612070")
mix(L.filter(pl.col("procedure_code") != "612070"), "excl. 612070 (bed misuse)")
for lab, excl in [("all chapters", []), ("excl. ch1 bed, ch2 exams", ["1", "2"]), ("excl. bed/exam/lab(9*,10)", ["1", "2", "9", "9.1", "9.2", "9.A", "9.B", "9.C", "9.D", "9.E", "10"]),
                  ("excl. bed/exam/lab/imaging(8.*)", ["1", "2", "9", "9.1", "9.2", "9.A", "9.B", "9.C", "9.D", "9.E", "10", "8.1", "8.2", "8.3"])]:
    g = L.filter(~pl.col("chapter").is_in(excl)).group_by("claim_id").agg(pl.col("chapter").n_unique().alias("n"))
    g = C.select("claim_id").join(g, on="claim_id", how="left").fill_null(0)
    print(f"one-chapter claims [{lab}]: exactly1={g.filter(pl.col('n')==1).height}, <=1={g.filter(pl.col('n')<=1).height}")
non_surg = ["Gogus Hastaliklari","Noroloji","Kardiyoloji","kardiyoloji","Onkoloji","Ic Hastaliklari","Endokrinoloji","Hematoloji","Gastroenteroloji","Nefroloji"]
s = L.filter(pl.col("is_surgical") & (pl.col("procedure_code") != "612070"))
print("surgical lines excl 612070:", s.height, "| under medical departments:", s.filter(pl.col("department").is_in(non_surg)).height, "lines /",
      s.filter(pl.col("department").is_in(non_surg))["claim_id"].n_unique(), "claims | claims of medical depts:", C.filter(pl.col("department").is_in(non_surg)).height)
print("package_candidate True w/o paket, null flag:", C.filter(pl.col("package_candidate").is_null() | (pl.col("package_candidate")=="True")).join(
    L.filter(pl.col("procedure_category")=="paket").select("claim_id").unique().with_columns(pl.lit(True).alias("p")), on="claim_id", how="left").filter(
    pl.col("p").is_null() | pl.col("package_candidate").is_null()).select(sid("claim_id"), "package_candidate", "p").to_dicts())
agew = L.filter(pl.col("procedure_name").str.contains(r"(?i)2 yaş altı|bebek için|çocuklarda|yenidoğan|pediyatrik") & (pl.col("age") >= 18))
print("age-bounded names on >=18:", agew.height, agew.select(sid("procedure_line_id").alias("l"), "age", "procedure_code").to_dicts())
tiers = pl.read_json("/home/safa/Documents/Bilun/data/synthetic/demo_cohort_tiers.json") if False else None
# claim_type vs admission fields; day-bed placement; wrong bed codes total; exam plausibility IDs
print("admission null by type:", C.group_by("claim_type").agg(pl.col("adm").is_null().sum().alias("adm_null"), pl.len().alias("n"),
      (pl.col("adm") == pl.col("dis")).sum().alias("same_day"), pl.col("los_nights").min().alias("min_los")).sort("claim_type").to_dicts())
bed = L.filter(pl.col("procedure_category") == "yatak")
print("bed lines on non-yatis claims:", bed.filter(pl.col("claim_type") != "yatis").height,
      "| gunubirlik claims with 510120 day-bed:", L.filter((pl.col("claim_type") == "gunubirlik") & (pl.col("procedure_code") == "510120")).height)
wrong = bed.filter((pl.col("procedure_code").is_in(["612070", "530000"])) | ((pl.col("procedure_code") == "510120") & (pl.col("los_nights") >= 1)))
print("bed lines with wrong code for a ward stay (612070, 530000, 510120 on >=1 night):", wrong.height, "/", bed.height)
ex = L.filter(pl.col("procedure_category") == "muayene")
std = ex.filter(((pl.col("procedure_code") == "520030") & pl.col("claim_type").is_in(["poliklinik", "koruyucu", "meslek_hastaligi", "gunubirlik"])) |
                ((pl.col("procedure_code") == "520020") & (pl.col("claim_type") == "acil")) |
                ((pl.col("procedure_code") == "520010") & pl.col("claim_type").is_in(["yatis", "gunubirlik"])) |
                ((pl.col("procedure_code") == "520090") & (pl.col("claim_type") == "poliklinik")))
print("standard exam lines:", std.select(sid("procedure_line_id").alias("l"), "procedure_code", "claim_type").to_dicts())
print("tier of yatis-without-bed claims: see 34_tier_rollup (0002-006 A, 0003-011 A, 0004-016 B, 0005-018 B, 0006-020 A, 0010-024 A)")
# strict anaesthesia definitions (algology ch.5 codes excluded; 612070 bed misuse excluded from 'operation')
ANAES = ["550010", "550090", "550100", "520070"] + [str(c) for c in range(550130, 550270, 10)]
op = (pl.col("is_surgical") & (pl.col("procedure_code") != "612070"))
g = L.group_by("claim_id").agg(op.any().alias("any_op"),
                               (op & (pl.col("code_kind") != "EK-2C_P") & ~pl.col("is_package_included")).any().alias("ffs_op"),
                               pl.col("procedure_code").is_in(ANAES).any().alias("anaes_any"),
                               pl.col("procedure_code").is_in([str(c) for c in range(550130, 550270, 10)]).any().alias("anaes_group"))
print("claims with fee-for-service operation (excl. 612070):", g.filter("ffs_op").height, "| with anaesthesia group line 550130-550260:", g.filter(pl.col("ffs_op") & pl.col("anaes_group")).height)
print("claims with anaesthesia codes (550010/550090/550100/520070/550130-550260):", g.filter("anaes_any").height, "| with no operation at all:", g.filter(pl.col("anaes_any") & ~pl.col("any_op")).height,
      g.filter(pl.col("anaes_any") & ~pl.col("any_op")).select(sid("claim_id")).to_series().sort().to_list())
