"""(f) is_bundled / requires_pre_auth / titubb_registered / uts_registered, denial_reason_expected,
rule_trace_expected, expected_rule_outputs and medula_rejection_events on material lines.

Needs identity.parquet (20), link.parquet (32), flags_long.parquet (60).
"""
import os

import polars as pl

from common import B, HERE, load

pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_rows(80)
pl.Config.set_fmt_str_lengths(60)
pl.Config.set_tbl_width_chars(240)

m, p, h, a, cp = load()
ero = pl.read_parquet(B + "expected_rule_outputs.parquet")
rej = pl.read_parquet(B + "medula_rejection_events.parquet")
idn = pl.read_parquet(os.path.join(HERE, "identity.parquet")).select("material_line_id", "annex", "in_ek3c1_asof")
lnk = pl.read_parquet(os.path.join(HERE, "link.parquet")).select(
    "material_line_id", "family", "procedure_category", "package_code", "procedure_name")
fl = pl.read_parquet(os.path.join(HERE, "flags_long.parquet"))
pkg_claims = p.filter(pl.col("procedure_category") == "paket").select("claim_id").unique().with_columns(pl.lit(True).alias("claim_has_package_line"))
x = (m.select("material_line_id", "claim_id", "material_code", "material_name", "is_bundled", "requires_pre_auth",
              "titubb_registered", "uts_registered", "denial_reason_expected", "rule_trace_expected",
              "billed_amount_try", "expected_payable_try")
     .join(idn, on="material_line_id", how="left").join(lnk, on="material_line_id", how="left")
     .join(pkg_claims, on="claim_id", how="left").join(h.select("claim_id", "package_candidate", "claim_type"), on="claim_id", how="left")
     .with_columns(pl.col("claim_has_package_line").fill_null(False)))
N = x.height

# ---------- is_bundled ----------
b = x.filter(pl.col("is_bundled"))
print(f"[f] is_bundled: {b.height}/{N} ({b.height / N:.0%}); bundled TRY {b['billed_amount_try'].sum():,.2f}")
print("    bundled lines whose LINKED procedure is a package line:", (b["procedure_category"] == "paket").sum(),
      "| whose claim has any package line:", b["claim_has_package_line"].sum(),
      "| claim header package_candidate:", b.group_by("package_candidate").len().rows())
nb = x.filter(~pl.col("is_bundled") & (pl.col("procedure_category") == "paket"))
print("    NON-bundled lines linked directly to a package line:", nb.height, nb["material_line_id"].to_list())
print("    bundled lines by family (all called 'Paket kapsamindaki SARF malzeme'):",
      b.group_by("family").agg(pl.len(), pl.col("billed_amount_try").sum().round(2)).sort("len", descending=True).rows())
mixed = x.group_by("claim_id").agg(pl.col("is_bundled").n_unique().alias("n")).filter(pl.col("n") > 1)
print("    claims where some materials are bundled and others not:", mixed.height, "of", x["claim_id"].n_unique())
same_link = x.group_by("claim_id", "procedure_name").agg(pl.col("is_bundled").n_unique().alias("n"), pl.len().alias("lines")).filter(pl.col("lines") > 1)
print("    (claim, linked procedure) groups with >1 material:", same_link.height, "| with mixed bundling:", (same_link["n"] > 1).sum())

# ---------- requires_pre_auth ----------
pa = x["requires_pre_auth"]
print(f"\n[f] requires_pre_auth True: {pa.sum()}/{N} ({pa.mean():.0%})")
inc = x.group_by("material_code").agg(pl.col("requires_pre_auth").unique().alias("vals"), pl.len().alias("lines"),
                                      pl.col("claim_id").unique().alias("claims")).filter(pl.col("vals").list.len() > 1)
print("    codes appearing on >1 line:", x.group_by("material_code").len().filter(pl.col("len") > 1).height,
      "| of which with contradictory pre-auth values:", inc.height)
print(inc.sort("material_code"))
same_claim = x.group_by("claim_id", "material_code").agg(pl.col("requires_pre_auth").n_unique().alias("n"), pl.len().alias("lines")).filter(pl.col("lines") > 1)
print("    same code twice on the SAME claim:", same_claim.rows())
print("    pre-auth vs EK-3C-1 'tıbbi uygunluk aranacak' membership (as-of):",
      x.group_by("requires_pre_auth", "in_ek3c1_asof").len().sort("requires_pre_auth", "in_ek3c1_asof").rows())

# ---------- registration ----------
print(f"\n[f] titubb_registered False: {(~x['titubb_registered']).sum()} | uts_registered False: {(~x['uts_registered']).sum()}")
reg = x.filter(~pl.col("titubb_registered") | ~pl.col("uts_registered")).select(
    "material_line_id", "material_code", "titubb_registered", "uts_registered", "billed_amount_try",
    "expected_payable_try", "denial_reason_expected")
print(reg)
print("    unregistered lines expected to be paid in full:",
      reg.filter((pl.col("expected_payable_try") - pl.col("billed_amount_try")).abs() < 0.005).height, "/", reg.height)

# ---------- denial reasons & rule traces ----------
print("\n[f] denial_reason_expected values:", x.group_by("denial_reason_expected").len().rows())
print("    rule_trace_expected prefixes:", x.with_columns(pl.col("rule_trace_expected").str.extract(r"^([^:]+):").alias("pfx"))
      .group_by("pfx").len().rows())
print("    rule_trace_expected == 'EK-3:'+material_code:",
      (x["rule_trace_expected"] == ("EK-3:" + x["material_code"])).sum(), "/", N)
flagged = fl.select("material_line_id").unique()
fx = x.join(flagged, on="material_line_id", how="inner")
print("    flagged lines:", fx.height, "| whose denial reason is non-empty:", (fx["denial_reason_expected"] != "").sum(),
      "| whose rule trace names a flag/SUT §:", fx["rule_trace_expected"].str.contains(r"§|3\.\d|flag|_").sum())

# ---------- expected_rule_outputs on material lines ----------
em = ero.filter(pl.col("line_type") == "malzeme")
print(f"\n[f] expected_rule_outputs rows on material lines: {em.height} covering {em['line_id'].n_unique()}/{N} lines;"
      f" rule_family: {em['rule_family'].unique().to_list()}; statuses: {em.group_by('expected_status').len().rows()}")
j = x.join(em.select(pl.col("line_id").alias("material_line_id"), "expected_status"), on="material_line_id", how="left")
print("    lines without any expected output:", j["expected_status"].is_null().sum(),
      "| flagged lines whose expected output reflects a flag:",
      j.join(flagged, on="material_line_id").filter(pl.col("expected_status").is_in(["pakete_dahil_red", "on_onay_gerekli_odenebilir"]).not_()
                                                     & pl.col("expected_status").is_not_null()).height)
print("    status vs fields:", j.group_by("expected_status", "is_bundled", "requires_pre_auth").len().sort("expected_status").rows())

# ---------- MEDULA rejection events touching materials ----------
rm = rej.filter(pl.col("related_line_type") == "material")
print(f"\n[f] medula_rejection_events on material lines: {rm.height}")
print(rm.join(x.select(pl.col("material_line_id").alias("related_line_id"), "titubb_registered", "uts_registered",
                       "billed_amount_try", "expected_payable_try", "denial_reason_expected"), on="related_line_id", how="left")
      .select("related_line_id", "hata_kodu", "hata_mesaji", "uts_registered", "billed_amount_try", "expected_payable_try",
              "denial_reason_expected"))
