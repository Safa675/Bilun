"""(f) expected_rule_outputs: distribution, referential integrity, consistency with
line content, and how much of it simply echoes generator fields (circular truth).
"""
from common import *

e = claims("expected_rule_outputs")
h = claims("claim_headers")
p = claims("procedure_claim_lines")
d = claims("drug_claim_lines")
m = claims("material_claim_lines")

print("rows:", e.height, " distinct expected_output_id:", e["expected_output_id"].n_unique())
print(e.group_by("rule_family", "expected_status", "line_type").len().sort("len", descending=True))

# --- referential integrity ---
print("\nclaim_id not in headers:", e.join(h, on="claim_id", how="anti").height)
print("patient_id mismatch with header:",
      e.join(h.select("claim_id", pl.col("patient_id").alias("hp")), on="claim_id").filter(pl.col("patient_id") != pl.col("hp")).height)
print("scenario_tag mismatch with header:",
      e.join(h.select("claim_id", pl.col("scenario_tag").alias("hs")), on="claim_id").filter(pl.col("scenario_tag") != pl.col("hs")).height)

lt = {
    "islem": p.select(pl.col("procedure_line_id").alias("lid"), pl.col("claim_id").alias("lclaim"),
                      pl.col("billed_amount_try").alias("l_billed"), pl.col("expected_payable_try").alias("l_pay"),
                      pl.col("denial_reason_expected").alias("l_reason"), pl.col("rule_trace_expected").alias("l_trace"),
                      pl.lit(None, pl.Boolean).alias("l_preauth"), pl.col("is_package_included").alias("l_incl")),
    "ilac": d.select(pl.col("drug_claim_line_id").alias("lid"), pl.col("claim_id").alias("lclaim"),
                     pl.col("billed_amount_try").alias("l_billed"), pl.col("expected_payable_try").alias("l_pay"),
                     pl.col("denial_reason_expected").alias("l_reason"), pl.col("rule_trace_expected").alias("l_trace"),
                     pl.lit(None, pl.Boolean).alias("l_preauth"), pl.lit(None, pl.Boolean).alias("l_incl")),
    "malzeme": m.select(pl.col("material_line_id").alias("lid"), pl.col("claim_id").alias("lclaim"),
                        pl.col("billed_amount_try").alias("l_billed"), pl.col("expected_payable_try").alias("l_pay"),
                        pl.col("denial_reason_expected").alias("l_reason"), pl.col("rule_trace_expected").alias("l_trace"),
                        pl.col("requires_pre_auth").alias("l_preauth"), pl.col("is_bundled").alias("l_incl")),
    "fatura": h.select(pl.col("claim_id").alias("lid"), pl.col("claim_id").alias("lclaim"),
                       pl.col("expected_total_billed_try").alias("l_billed"), pl.col("expected_total_payable_try").alias("l_pay"),
                       pl.col("expected_denial_reason").alias("l_reason"), pl.col("scenario_tag").alias("l_trace"),
                       pl.lit(None, pl.Boolean).alias("l_preauth"), pl.lit(None, pl.Boolean).alias("l_incl")),
}
parts = []
for k, ldf in lt.items():
    sub = e.filter(pl.col("line_type") == k)
    # fatura rows carry an empty line_id; they key on claim_id
    j = sub.join(ldf, left_on="claim_id" if k == "fatura" else "line_id", right_on="lid", how="left")
    if k == "fatura":
        print(f"[fatura] empty line_id rows: {sub.filter(pl.col('line_id').fill_null('') == '').height}")
    print(f"\n[{k}] rows={sub.height} line_id found={j.filter(pl.col('lclaim').is_not_null()).height} "
          f"claim matches line's claim={j.filter(pl.col('lclaim') == pl.col('claim_id')).height}")
    parts.append(j.with_columns(pl.col("l_preauth").cast(pl.Boolean), pl.col("l_incl").cast(pl.Boolean)))
j = pl.concat(parts, how="diagonal")
j = j.with_columns(
    ((pl.col("expected_payable_try") - pl.col("l_pay")).abs() <= 0.01).alias("pay_echo"),
    ((pl.col("expected_savings_try") - (pl.col("l_billed") - pl.col("l_pay"))).abs() <= 0.01).alias("sav_is_billed_minus_pay"),
    (pl.col("expected_denial_reason").fill_null("") == pl.col("l_reason").fill_null("")).alias("reason_echo"),
    (pl.col("expected_rule_trace").fill_null("") == pl.col("l_trace").fill_null("")).alias("trace_echo"),
)
print("\nper line_type: payable echoes line, savings == billed-payable, reason echoes, trace echoes")
print(j.group_by("line_type").agg(pl.len(), pl.col("pay_echo").sum(), pl.col("sav_is_billed_minus_pay").sum(),
                                  pl.col("reason_echo").sum(), pl.col("trace_echo").sum()))
full_echo = j.filter(pl.col("pay_echo") & pl.col("trace_echo") & (pl.col("reason_echo") | (pl.col("line_type") == "fatura")))
print("rows whose payable AND trace echo the generator's own line/header fields:", full_echo.height, "/", j.height)
print("rows with payable echo:", j.filter(pl.col("pay_echo")).height, "| trace echo:", j.filter(pl.col("trace_echo")).height)

# fatura rows: reason text vs header text
f = j.filter(pl.col("line_type") == "fatura")
print("\nfatura reason pairs (expected_output vs header):")
print(f.group_by("expected_status", "expected_denial_reason", "l_reason").len())
print("fatura expected_rule_trace == scenario_tag:", f.filter(pl.col("trace_echo")).height, "/", f.height)
pk = pl.read_parquet(OUT / "d_package_label.parquet")
noev = pk.filter(~pl.col("has_package_line_or_code") & ~pl.col("pc_true") & ((pl.col("n_proc_included") + pl.col("n_mat_bundled")) == 0))
print("kismi_red fatura rows on claims with NO package evidence:",
      f.filter(pl.col("expected_status") == "kismi_red").join(noev.select("claim_id"), on="claim_id", how="semi").height)

# malzeme rows: statuses vs line flags
mm = j.filter(pl.col("line_type") == "malzeme")
print("\nmalzeme: status x requires_pre_auth x is_bundled:")
print(mm.group_by("expected_status", "l_preauth", "l_incl").len().sort("len", descending=True))
print("material lines with NO expected output row:", m.height - mm["line_id"].n_unique())
print("procedure lines with NO expected output row:", p.height - j.filter(pl.col("line_type") == "islem")["line_id"].n_unique())
# coverage of the money: what share of the cohort gap is covered by line-level expectations?
c = pl.read_parquet(OUT / "c_lines.parquet")
cov = c.join(e.select(pl.col("line_id")), on="line_id", how="semi")
print(f"line gap covered by a line-level expected row: {cov['gap'].sum():,.2f} of {c['gap'].sum():,.2f}")
proc_cov = c.filter(pl.col("kind") == "procedure").join(e.select("line_id"), on="line_id", how="semi")
print(f"procedure gap covered: {proc_cov['gap'].sum():,.2f} of {c.filter(pl.col('kind') == 'procedure')['gap'].sum():,.2f}")
# ilac rows: status 'discount applied' while line field is called copay_rate
il = j.filter(pl.col("line_type") == "ilac")
print("\nilac rows status values:", il["expected_status"].value_counts().rows(),
      " savings sum:", round(il["expected_savings_try"].sum(), 2))
# expected_savings sign / magnitude
print("\nexpected_savings_try <0:", e.filter(pl.col("expected_savings_try") < 0).height,
      " ==0:", e.filter(pl.col("expected_savings_try") == 0).height,
      " total:", round(e["expected_savings_try"].sum(), 2))
print(e.filter(pl.col("expected_savings_try") < 0).select("claim_id", "line_type", "expected_status", "expected_payable_try", "expected_savings_try").rows())
# trace annex correctness for islem rows: EK-2C trace on a 6-digit EK-2B code?
pt = p.select("procedure_line_id", "procedure_code", "rule_trace_expected").with_columns(
    pl.col("rule_trace_expected").str.split(":").list.get(0).alias("trace_annex"),
    pl.col("rule_trace_expected").str.split(":").list.get(1).alias("trace_code"))
print("\nprocedure rule_trace annex vs code shape:")
print(pt.with_columns(pl.col("procedure_code").str.starts_with("P").alias("is_P")).group_by("trace_annex", "is_P").len())
print("trace code != procedure_code:", pt.filter(pl.col("trace_code") != pl.col("procedure_code")).height)
j.write_parquet(OUT / "f_expected_join.parquet")
