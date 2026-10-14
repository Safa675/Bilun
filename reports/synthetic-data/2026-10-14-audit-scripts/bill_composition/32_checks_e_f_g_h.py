"""(e) facility/provider vs complexity; (f) duplicates/quantity/laterality; (g) packages; (h) dates + line counts;
plus header<->line consistency and sex-specific procedures."""
import polars as pl
OUT = "/tmp/claude-1000/-home-safa-Documents-Bilun/a9cf6beb-cd1a-4613-ab9e-bddecbe1db1a/scratchpad/audit/bill_composition"
R = "/home/safa/Documents/Bilun/data/synthetic/sut"
G = "/home/safa/Documents/Bilun/data/gazette/curated"
pl.Config.set_tbl_rows(80); pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(230); pl.Config.set_fmt_str_lengths(60)
L = pl.read_parquet(f"{OUT}/enriched_lines.parquet")
C = pl.read_parquet(f"{OUT}/enriched_claims.parquet")
M = pl.read_parquet(f"{R}/claims/material_claim_lines.parquet")
DR = pl.read_parquet(f"{R}/claims/drug_claim_lines.parquet")
ek2c = pl.read_parquet(f"{G}/ek2c_catalog_history.parquet")
sid = lambda c: pl.col(c).str.replace("ISL-F-SENTETIK-HASTA-", "").str.replace("MLZ-F-SENTETIK-HASTA-", "").str.replace("F-SENTETIK-HASTA-", "")

print("=" * 30, "(e) FACILITY / PROVIDER vs COMPLEXITY")
ct = C.group_by("facility_tier", "provider_type").len().sort("len", descending=True)
print(ct.to_dicts())
contra = C.filter(((pl.col("facility_tier") == "2_basamak_kamu") & (pl.col("provider_type") == "Ozel")) |
                  ((pl.col("facility_tier") == "2_3_basamak_ozel") & (pl.col("provider_type") == "Kamu")))
print("tier name contradicts provider_type (kamu tier + Ozel, or ozel tier + Kamu):", contra.height, "/", C.height,
      contra.select(sid("claim_id")).head(5).to_series().to_list())
pt = C.group_by("patient_id").agg(pl.col("facility_tier").n_unique().alias("tiers"), pl.col("provider_type").n_unique().alias("ptypes"), pl.len().alias("claims"))
print("patients with >1 claim:", pt.filter(pl.col("claims") > 1).height, "| of which seen at >1 facility tier:", pt.filter((pl.col("claims") > 1) & (pl.col("tiers") > 1)).height)
hc = L.filter(pl.col("is_surgical") & pl.col("surg_group").is_in(["A1", "A2", "A3"]))
print("A1-A3 operations by facility_tier:", hc.group_by("facility_tier").agg(pl.len().alias("lines"), pl.col("claim_id").n_unique().alias("claims")).sort("facility_tier").to_dicts())
print(hc.filter(pl.col("facility_tier") == "2_basamak_kamu").select(sid("procedure_line_id").alias("line"), "provider_type", "department", "surg_group", "procedure_name"))
restr = L.filter(pl.col("cat_desc").str.contains(r"(?i)basamak|uzman hekim|Referans Laboratuvar|meslek hastalıkları|eğitim ve araştırma|üniversite"))
print("lines whose catalog description carries a facility/specialist restriction:", restr.height)
print(restr.select(sid("procedure_line_id").alias("line"), "procedure_code", "facility_tier", "department", pl.col("cat_desc").str.slice(0, 120)))
ch10 = L.filter(pl.col("chapter") == "10")
print("ch.10 codes (catalog: only billable by the national reference lab):", ch10.height, ch10.select(sid("procedure_line_id").alias("line"), "procedure_name", "facility_tier").to_dicts())
print("facility tiers present:", C["facility_tier"].unique().sort().to_list(), "| tıp/dal merkezi tier present:",
      C.filter(pl.col("facility_tier").str.contains("(?i)tip|tıp|dal|merkez")).height)
per = L.group_by("claim_id").agg(
    (pl.col("is_surgical") & pl.col("surg_group").is_in(["A1", "A2", "A3", "B"])).any().alias("major"),
    (pl.col("procedure_category") == "yatak").any().alias("bed"))
oc = C.select("claim_id", "claim_type").join(per, on="claim_id", how="left").fill_null(False)
compat = oc.filter(pl.col("claim_type").is_in(["poliklinik", "gunubirlik", "koruyucu"]) & ~pl.col("major") & ~pl.col("bed"))
print("claims whose content a tıp/dal merkezi could produce (poliklinik/günübirlik/koruyucu, no bed, no A1-B surgery):", compat.height, "/", C.height,
      compat["claim_type"].value_counts().to_dicts())

print("\n" + "=" * 30, "(f) DUPLICATES / QUANTITY / LATERALITY")
dup = L.group_by("claim_id", "procedure_code", "pdate").agg(pl.len().alias("n"), pl.col("procedure_name").first(), pl.col("scenario_tag").first()).filter(pl.col("n") > 1)
print("same code repeated on one claim+date:", dup.with_columns(sid("claim_id")).to_dicts())
q = L.filter((pl.col("quantity") > 1) & (pl.col("procedure_category") != "yatak"))
print("quantity>1 on non-bed lines:", q.height, "| quantity distribution non-bed:", L.filter(pl.col("procedure_category") != "yatak")["quantity"].value_counts().to_dicts())
print("sag_sol values:", L["sag_sol"].value_counts().to_dicts())
side_in_name = L.filter(pl.col("procedure_name").str.contains(r"(?i)\bsağ\b|\bsol\b|tek taraf|iki taraf|bilateral"))
print("lines whose name itself states a side/both sides:", side_in_name.height, "| with sag_sol set:", side_in_name.filter(pl.col("sag_sol").fill_null("") != "").height)
print(side_in_name.select(sid("procedure_line_id").alias("line"), "procedure_name", "department").head(30))
paired = L.filter(pl.col("is_surgical") & pl.col("procedure_name").str.contains(r"(?i)diz|omuz|kalça|dirsek|bilek|ekstremite|uzuv|parmak|göz|orbit|kulak|aurikula|meme|mammo|testis|testik|sürrenal|böbrek|üreter|torakotomi|akciğer|amputasyon|safena|eklem|brakiyal|greft, ekstremite|pleksus|uyluk|kol"))
print("surgical lines on paired organs/limbs (name keyword match):", paired.height, "| with sag_sol set:", paired.filter(pl.col("sag_sol").fill_null("") != "").height)

print("\n" + "=" * 30, "(g) PACKAGES")
pk = L.filter(pl.col("procedure_category") == "paket")
print("paket lines:", pk.height, "| code kinds:", pk["code_kind"].value_counts().to_dicts())
ek2c_d = ek2c.with_columns(pl.col("valid_from").str.to_date(), pl.col("valid_to").str.to_date())
pk2 = pk.select("procedure_line_id", "claim_id", "procedure_code", "procedure_name", "pdate", "claim_type", "department", "primary_icd10", "chapter").join(
    ek2c_d.select(pl.col("package_code").alias("procedure_code"), pl.col("name").alias("cat_name"), "group", "valid_from", "valid_to"), on="procedure_code", how="left")
pk2 = pk2.with_columns(((pl.col("valid_from") <= pl.col("pdate")) & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= pl.col("pdate")))).fill_null(False).alias("valid"))
pkv = pk2.group_by("procedure_line_id").agg(pl.col("valid").any().alias("in_ek2c_on_date"), pl.col("cat_name").filter(pl.col("valid")).first().alias("cat_name"),
                                           pl.col("group").filter(pl.col("valid")).first().alias("group"))
pk3 = pk.join(pkv, on="procedure_line_id")
print("paket lines whose code is in EK-2C on the line date:", pk3.filter("in_ek2c_on_date").height, "/", pk3.height)
print("not in EK-2C:", pk3.filter(~pl.col("in_ek2c_on_date")).select(sid("procedure_line_id").alias("line"), "procedure_code", "procedure_name", "rule_trace_expected").to_dicts())
print("P609270 in EK-2C at all:", ek2c.filter(pl.col("package_code") == "P609270").height, "| 609270 in EK-2C:", ek2c.filter(pl.col("package_code") == "609270").height)
print("paket name == catalog name:", pk3.filter(pl.col("procedure_name").str.strip_chars() == pl.col("cat_name").str.strip_chars()).height, "/", pk3.filter("in_ek2c_on_date").height,
      "| name equals code:", pk3.filter(pl.col("procedure_name") == pl.col("procedure_code")).select(sid("procedure_line_id")).to_series().to_list())
print("paket lines by claim_type:", pk3.group_by("claim_type").len().to_dicts())
print(pk3.select(sid("procedure_line_id").alias("line"), "claim_type", "department", "primary_icd10", "group", "chapter", "procedure_name"))
inc = L.filter(pl.col("is_package_included"))
pkname = L.filter(pl.col("procedure_category") == "paket").select("claim_id", pl.col("procedure_code").alias("package_code"), pl.col("procedure_name").alias("pkg_name"), pl.col("chapter").alias("pkg_ch"))
inc2 = inc.join(pkname, on=["claim_id", "package_code"], how="left")
print("is_package_included lines:", inc.height, "| package line present on same claim:", inc2.filter(pl.col("pkg_name").is_not_null()).height,
      "| included line in same SUT chapter as package op:", inc2.filter(pl.col("chapter") == pl.col("pkg_ch")).height)
print(inc2.select(sid("procedure_line_id").alias("line"), "pkg_name", "pkg_ch", "chapter", "procedure_name"))
ref = L.filter(pl.col("package_code").is_not_null() & (pl.col("procedure_category") != "paket"))
refj = ref.join(pkname.select("claim_id", "package_code").with_columns(pl.lit(True).alias("pkg_on_claim")), on=["claim_id", "package_code"], how="left")
print("non-paket lines carrying a package_code:", ref.height, "| package not billed on the claim:", refj.filter(pl.col("pkg_on_claim").is_null()).select(sid("procedure_line_id").alias("line"), "package_code", "is_package_included").to_dicts())
ws = L.filter(pl.col("is_surgical") & ~pl.col("is_package_included") & (pl.col("procedure_category") != "paket") & (pl.col("procedure_code") != "612070")).select("claim_id", "chapter").unique()
pkc = pkname.select("claim_id", "pkg_ch").unique()
mix = pkc.join(ws, on="claim_id").filter(pl.col("chapter") != pl.col("pkg_ch"))
print("claims with a package AND a separately billed operation from another SUT chapter:", mix["claim_id"].n_unique(), "/", pkc["claim_id"].n_unique(), mix.with_columns(sid("claim_id")).to_dicts())
pc = C.select("claim_id", "package_candidate").join(pkname.select("claim_id").unique().with_columns(pl.lit(True).alias("has_pkg")), on="claim_id", how="left").fill_null(False)
print("package_candidate x has paket line:", pc.group_by("package_candidate", "has_pkg").len().sort("package_candidate").to_dicts())

print("\n" + "=" * 30, "(h) DATES / LINE COUNTS")
out = L.filter((pl.col("pdate") < pl.col("cstart")) | (pl.col("pdate") > pl.col("cend")))
print("procedure_date outside claim window:", out.height)
y = L.filter(pl.col("claim_type") == "yatis").group_by("claim_id").agg(pl.col("pdate").n_unique().alias("n_dates"), (pl.col("pdate") == pl.col("adm")).all().alias("all_day0"), pl.col("los_nights").first())
print("yatis claims with LOS>=1:", y.filter(pl.col("los_nights") >= 1).height, "| all lines dated on admission day:", y.filter((pl.col("los_nights") >= 1) & pl.col("all_day0")).height,
      "| distinct dates per claim:", y["n_dates"].value_counts().to_dicts())
print("all claims: lines dated on a single day:", L.group_by("claim_id").agg(pl.col("pdate").n_unique().alias("n")).filter(pl.col("n") == 1).height, "/", C.height)
lc = C.select("claim_id", "claim_type", "los_nights").join(L.group_by("claim_id").agg(pl.len().alias("lines"), (pl.col("procedure_category") == "laboratuvar").sum().alias("labs")), on="claim_id", how="left")
print(lc.group_by("claim_type").agg(pl.len().alias("claims"), pl.col("lines").min().alias("min"), pl.col("lines").median().alias("median"), pl.col("lines").max().alias("max"),
                                   pl.col("labs").median().alias("median_labs"), pl.col("los_nights").median().alias("median_los")).sort("claims", descending=True))
ly = lc.filter(pl.col("claim_type") == "yatis")
print("yatis: lab lines per stay min/median/max:", ly["labs"].min(), ly["labs"].median(), ly["labs"].max(), "| stays >=10 nights with <=3 lab lines:", ly.filter((pl.col("los_nights") >= 10) & (pl.col("labs") <= 3)).height, "/", ly.filter(pl.col("los_nights") >= 10).height)
print("lines per claim distribution:", lc["lines"].value_counts().sort("lines").to_dicts())

print("\n" + "=" * 30, "HEADER <-> LINE CONSISTENCY + SEX-SPECIFIC + MATERIALS")
den_lines = pl.concat([L.filter(pl.col("denial_reason_expected") != "").select("claim_id"),
                       M.filter(pl.col("denial_reason_expected") != "").select("claim_id"),
                       DR.filter(pl.col("denial_reason_expected") != "").select("claim_id")]).unique().with_columns(pl.lit(True).alias("has_line_denial"))
hd = C.select("claim_id", "expected_denial_reason").join(den_lines, on="claim_id", how="left").fill_null(False)
print("header denial 'Kismi paket ici satir reddi' claims:", hd.filter(pl.col("expected_denial_reason") == "Kismi paket ici satir reddi").height,
      "| of which have any line-level denial:", hd.filter((pl.col("expected_denial_reason") == "Kismi paket ici satir reddi") & pl.col("has_line_denial")).height)
tot = C.select("claim_id", "expected_total_billed_try").join(
    pl.concat([L.select("claim_id", "billed_amount_try"), M.select("claim_id", "billed_amount_try"), DR.select("claim_id", "billed_amount_try")]).group_by("claim_id").agg(pl.col("billed_amount_try").sum().alias("lines_sum")),
    on="claim_id", how="left").with_columns((pl.col("expected_total_billed_try") - pl.col("lines_sum")).abs().alias("diff"))
print("header expected_total_billed == sum(proc+drug+material billed) within 1 TRY:", tot.filter(pl.col("diff") <= 1).height, "/", tot.height,
      "| examples:", tot.sort("diff", descending=True).head(3).with_columns(sid("claim_id")).to_dicts())
calc = L.with_columns((pl.col("quantity") * pl.col("unit_price_try")).alias("qxu")).with_columns(((pl.col("billed_amount_try") - pl.col("qxu")).abs() / pl.col("qxu")).alias("rel"))
print("lines where billed == quantity x unit_price (±1%):", calc.filter(pl.col("rel") <= 0.01).height, "/", calc.height,
      "| billed < 0.9 x (qxu):", calc.filter(pl.col("billed_amount_try") < 0.9 * pl.col("qxu")).height, "| billed > 1.1 x (qxu):", calc.filter(pl.col("billed_amount_try") > 1.1 * pl.col("qxu")).height,
      "| payable > billed:", calc.filter(pl.col("expected_payable_try") > pl.col("billed_amount_try") + 0.01).height)
fem = r"(?i)vajin|histerektomi|douglas|myomektomi|uterus\b|inseminasyon|anne sütü|sezaryen"
mal = r"(?i)penil|penektomi|testis|testik|skrotum|prostat|orşi|varikosel"
sx = L.filter(pl.col("procedure_name").str.contains(fem) | pl.col("procedure_name").str.contains(mal) | pl.col("chapter").is_in(["6.13", "6.14", "7.11"]))
sx = sx.with_columns(pl.when(pl.col("procedure_name").str.contains(fem) | pl.col("chapter").is_in(["6.13", "7.11"])).then(pl.lit("K")).otherwise(pl.lit("E")).alias("needs_sex"))
print("sex-specific lines:", sx.height, "| patient sex contradicts:", sx.filter(pl.col("needs_sex") != pl.col("sex")).height)
print(sx.select(sid("procedure_line_id").alias("line"), "sex", "age", "needs_sex", "chapter", "department", "procedure_name"))
print("cohort sex split (claims):", C["sex"].value_counts().to_dicts())
agew = L.filter(pl.col("procedure_name").str.contains(r"(?i)2 yaş altı|bebek için|çocuklarda|yenidoğan|pediyatrik") & (pl.col("age") >= 18))
print("age-bounded (infant/child) procedure names on patients >=18:", agew.height, agew.select(sid("procedure_line_id").alias("line"), "age", "procedure_name").to_dicts())
mj = M.select("material_line_id", "procedure_line_id", "material_name", "material_type").join(L.select("procedure_line_id", "procedure_category", "is_surgical", "procedure_name", "department"), on="procedure_line_id", how="left")
print("material lines:", mj.height, "| attached to surgical/package line:", mj.filter(pl.col("is_surgical")).height,
      "| attached to muayene/lab/bed:", mj.filter(pl.col("procedure_category").is_in(["muayene", "laboratuvar", "yatak"])).height,
      "| procedure line missing:", mj.filter(pl.col("procedure_category").is_null()).height)
print(mj.filter(pl.col("procedure_category").is_in(["muayene", "laboratuvar", "yatak"])).select(sid("material_line_id").alias("mat"), "material_name", "procedure_category", "procedure_name").head(12))
nm = L.filter(pl.col("procedure_name") == pl.col("procedure_code"))
print("lines whose name is just the code:", nm.select(sid("procedure_line_id").alias("line"), "procedure_code").to_dicts())
