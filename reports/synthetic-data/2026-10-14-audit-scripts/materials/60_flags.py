"""(e) The 78 boolean fault flags on material lines: coverage pattern, per-line load, contradictions.

For every TRUE flag cell we test
  * MATERIAL DOMAIN : is this line the kind of material the flag (and the engine rule it triggers) is about?
                      checked on BOTH the code's EK-3 annex and the displayed name; a cell is counted as a
                      domain contradiction only if NEITHER fits (conservative).
  * CONTEXT         : claim type (yatış/ayakta/acil), provider country, patient age (anadata), claim ICD-10.
  * CATALOG         : flags asserting 'code undefined / unlisted / no list price' vs the as-of EK-3 snapshot.
Engine message + outcome come from data/gazette/prose_rules/*.json (rules keyed on the flag alone).
Domain/context tables are JUDGMENT about what each flag means (the flag names + engine messages define them).
Needs identity.parquet (20_identity.py) and patient_fit.parquet (45_patient_fit.py).
"""
import json
import os

import polars as pl

from common import HERE, load, flag_cols, norm_expr

pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_rows(120)
pl.Config.set_fmt_str_lengths(70)
pl.Config.set_tbl_width_chars(260)

m, p, h, a, cp = load()
FC = flag_cols(m)
idn = pl.read_parquet(os.path.join(HERE, "identity.parquet")).select(
    "material_line_id", "annex", "listed_asof", "asof_price", "annexes_ever")
pf = pl.read_parquet(os.path.join(HERE, "patient_fit.parquet")).select(
    "material_line_id", "family", "age", "dx", "claim_type", "department")

# ---------- engine rules keyed on each flag ----------
rules = []
for fn in ("specialty_materials_prose.json", "material_bundling_prose.json"):
    for r in json.load(open(f"/home/safa/Documents/Bilun/data/gazette/prose_rules/{fn}"))["rules"]:
        cond, act = r.get("condition") or {}, r.get("action") or {}
        for k, v in cond.items():
            if v is True and k in FC:
                rules.append({"flag": k, "rule_id": r.get("rule_id"), "sut_section": r.get("sut_section"),
                              "outcome": act.get("material_outcome", "no_pay"), "message": act.get("message_tr", "")})
R = pl.DataFrame(rules).unique("flag", keep="first")

# ---------- material domain table (regex over 'ANNEX CODE NAME TYPE', normalised) ----------
D = {
    "WOUND": r"YARA|PANSUMAN|ORTU|DERI ESDEGER|DERI TAKLIT|DERI YEDEG|DERMAL",
    "SKIN_SUB": r"DERI ESDEGER|DERI TAKLIT|DERI YEDEG|DERMAL MATRIKS|YAPAY DERI",
    "OPTICAL": r"EK 3D|GOZLUK|\bCAM\b|LENS|TELESKOP|CERCEVE|OPTIK|\bTV\d",
    "HEARING": r"ISITME|KULAK KALIB|KULAK ICI",
    "COCHLEAR": r"KOKLEAR|KONUSMA ISLEMCI|SES ISLEMCI|BEYIN SAPI",
    "INCONT": r"HIDROFILIK|INKONTINANS|HASTA BEZI|ALT BEZI|NELATON",
    "GRAFT": r"EK 3N|GREFT|DOKU|KEMIK MATRIKS|DBM",
    "BONE_STIM": r"EK 3N|GREFT|STIMULAT|KEMIK UYARI|KEMIK YAPIMINI|DBM|BMP",
    "GLUCOSE": r"GLUKOZ|GLUKOMETRE|KAN SEKERI",
    "WHEELCHAIR": r"TEKERLEKLI SANDALYE|WHEELCHAIR",
    "PARAPLEGIA_DEVICE": r"TEKERLEKLI SANDALYE|STANDING|AYAKTA DIK",
    "RETURNABLE_DEVICE": r"EK 3C [235]|TEKERLEKLI|CIHAZ|ISITME|PROTEZ|ORTEZ",
    "DENTAL": r"\bDIS\b|DENTAL|PROTEZ YAPISTIRICI|PROTEZ BAKIM|ADEZIV",
    "MESH": r"YAMA|MESH|FITIK",
    "EK3C": r"EK 3C",
    "ORTEZ_PROTEZ": r"EK 3C [23]|ORTEZ|PROTEZ",
    "GARMENT": r"BASI GIYSI|BASINC GIYSI|LENFODEM|CORAP|MANSON",
    "ISMARLAMA": r"EK 3C [235]|ISMARLAMA|KISIYE OZEL",
    "LAB": r"LABORATUVAR|\bTEST\b|\bKIT\b|PIPET|KAN ALMA|NUMUNE",
    "EK3A": r"EK 3A",
}
FLAG_DOMAIN = {
    "specialty_wound_care_excluded": "WOUND", "skin_substitute_non_burn_use": "SKIN_SUB",
    "immunobullous_wound_care_patient_supply": "WOUND", "immunobullous_wound_care_non_moh_facility": "WOUND",
    "optical_patient_access_deadline_missed": "OPTICAL", "emergency_poliklinik_glasses_claim": "OPTICAL",
    "optical_lens_upgrade_difference_claim": "OPTICAL", "optical_telescopic_with_cap_claim": "OPTICAL",
    "contact_lens_with_spectacle_billing": "OPTICAL", "tv5680_with_tv1080_tv1090_combo": "OPTICAL",
    "hearing_in_ear_under_age_limit": "HEARING", "hearing_ear_mold_with_initial_device": "HEARING",
    "cochlear_implant_under_12_months": "COCHLEAR", "speech_processor_under_5_years": "COCHLEAR",
    "brainstem_implant_under_12_months": "COCHLEAR", "incontinence_hydrophilic_catheter_diaper_only": "INCONT",
    "tissue_bank_unauthorized_product": "GRAFT", "bone_stimulator_combined_use": "BONE_STIM",
    "bone_stimulator_hypertrophic_nonunion": "BONE_STIM", "bone_stimulator_with_autograft": "BONE_STIM",
    "bone_stimulator_benign_tumor_use": "BONE_STIM", "open_physis_primary_fracture_graft": "GRAFT",
    "adult_primary_fracture_bone_stimulator": "BONE_STIM", "hip_arthroplasty_graft_claim": "GRAFT",
    "graft_allograft_xenograft_combined": "GRAFT", "primary_ligament_tendon_injury_graft": "GRAFT",
    "glucose_meter_early_renewal": "GLUCOSE", "wheelchair_stand_device_duplicate_billing": "PARAPLEGIA_DEVICE",
    "stand_up_wheelchair_early_renewal": "WHEELCHAIR", "paraplegia_standing_table_over_age_limit": "PARAPLEGIA_DEVICE",
    "paraplegia_wheelchair_separate_billing": "WHEELCHAIR", "spinal_mobility_device_duplicate_billing": "PARAPLEGIA_DEVICE",
    "returned_device_without_kurum_approval": "RETURNABLE_DEVICE", "dental_prosthesis_adhesive_claim": "DENTAL",
    "dual_mesh_primary_hernia_repair": "MESH",
    "ortez_protez_contract_billing_invalid": "ORTEZ_PROTEZ", "maintenance_cost_exceeds_sut_cap": "ORTEZ_PROTEZ",
    "protez_repair_documentation_incomplete": "ORTEZ_PROTEZ", "warranty_maintenance_procedure_incomplete": "ORTEZ_PROTEZ",
    "ortez_protez_maintenance_unverified": "ORTEZ_PROTEZ", "ek3c_inpatient_external_supply_invalid": "EK3C",
    "ek3c_list_price_missing": "EK3C", "ek3c_miat_early_renewal_unauthorized": "EK3C",
    "ek3c_custom_order_billing_invalid": "ISMARLAMA", "ek3c_medical_appropriateness_incomplete": "EK3C",
    "ek3c_custom_garment_contract_invalid": "GARMENT", "ek3c_force_majeure_renewal_claim": "EK3C",
    "ek3c_outpatient_material_scope": "EK3C", "lab_material_separate_billing": "LAB",
    "shared_consumable_wrong_branch_billing": "EK3A", "material_prescription_quantity_exceeded": "EK3C",
    "material_report_prescription_invalid": "EK3C", "wheelchair_dual_prescription_invalid": "WHEELCHAIR",
    "outpatient_contract_center_supply_required": "EK3C", "child_growth_miat_renewal_claim": "EK3C",
    "ismarlama_device_component_titubb_incomplete": "ISMARLAMA",
}
# context checks: (description, polars predicate that must hold for the flag to make sense)
age, dx, ct = pl.col("age"), pl.col("dx").fill_null(""), pl.col("claim_type")
CTX = {
    "ek3c_inpatient_external_supply_invalid": ("inpatient claim", ct == "yatis"),
    "inpatient_material_facility_supply_violation": ("inpatient claim", ct == "yatis"),
    "non_reimbursed_inpatient_patient_charge": ("inpatient claim", ct == "yatis"),
    "ek3c_outpatient_material_scope": ("outpatient claim", ct != "yatis"),
    "outpatient_contract_center_supply_required": ("outpatient claim", ct != "yatis"),
    "emergency_uncontracted_facility_material": ("emergency claim", ct == "acil"),
    "emergency_poliklinik_glasses_claim": ("emergency claim", ct == "acil"),
    "foreign_facility": ("foreign provider", pl.lit(False)),  # every claim header is Kamu/Universite/Ozel (TR)
    "child_growth_miat_renewal_claim": ("child <18", age < 18),
    "open_physis_primary_fracture_graft": ("open physis (<18) + fracture dx", (age < 18) & dx.str.contains(r"S\d2|T0[28]|T1[0-4]")),
    "hearing_in_ear_under_age_limit": ("child + hearing-loss dx", (age < 18) & dx.str.contains(r"H9[01]")),
    "cochlear_implant_under_12_months": ("infant <1y + hearing-loss dx", (age < 1) & dx.str.contains(r"H9[01]")),
    "brainstem_implant_under_12_months": ("infant <1y + hearing-loss dx", (age < 1) & dx.str.contains(r"H9[01]")),
    "speech_processor_under_5_years": ("child <5y + hearing-loss dx", (age < 5) & dx.str.contains(r"H9[01]")),
    "hearing_ear_mold_with_initial_device": ("hearing-loss dx", dx.str.contains(r"H9[01]")),
    "adult_primary_fracture_bone_stimulator": ("adult + fracture dx", (age >= 18) & dx.str.contains(r"S\d2|T0[28]|T1[0-4]")),
    "bone_stimulator_hypertrophic_nonunion": ("nonunion dx M84.1", dx.str.contains(r"M84\.1")),
    "bone_stimulator_benign_tumor_use": ("benign bone tumour dx D16", dx.str.contains(r"D16")),
    "primary_ligament_tendon_injury_graft": ("ligament/tendon injury dx", dx.str.contains(r"S\d3|S\d6|M23|M66")),
    "hip_arthroplasty_graft_claim": ("hip arthroplasty context M16/S72", dx.str.contains(r"M16|S72")),
    "paraplegia_standing_table_over_age_limit": ("paraplegia dx", dx.str.contains(r"G8[0-3]|S[123]4|T91\.3|Q05")),
    "paraplegia_wheelchair_separate_billing": ("paraplegia dx", dx.str.contains(r"G8[0-3]|S[123]4|T91\.3|Q05")),
    "dual_mesh_primary_hernia_repair": ("hernia dx K40-K46", dx.str.contains(r"K4[0-6]")),
    "dental_prosthesis_adhesive_claim": ("dental/edentulism dx K00-K14", dx.str.contains(r"K0\d|K1[0-4]")),
    "immunobullous_wound_care_patient_supply": ("immunobullous dx L10-L14/Q81", dx.str.contains(r"L1[0-4]|Q81")),
    "immunobullous_wound_care_non_moh_facility": ("immunobullous dx L10-L14/Q81", dx.str.contains(r"L1[0-4]|Q81")),
    "incontinence_hydrophilic_catheter_diaper_only": ("incontinence/neurogenic bladder dx", dx.str.contains(r"N3[1-9]|R32|R33")),
    "glucose_meter_early_renewal": ("diabetes dx E10-E14", dx.str.contains(r"E1[0-4]")),
    "optical_patient_access_deadline_missed": ("eye dx H", dx.str.contains(r"H[0-5]\d")),
    "optical_lens_upgrade_difference_claim": ("eye dx H", dx.str.contains(r"H[0-5]\d")),
    "optical_telescopic_with_cap_claim": ("eye dx H", dx.str.contains(r"H[0-5]\d")),
    "contact_lens_with_spectacle_billing": ("eye dx H", dx.str.contains(r"H[0-5]\d")),
}

long = (m.select("material_line_id", "claim_id", "material_code", "material_name", "material_type", "quantity",
                 "billed_amount_try", "expected_payable_try", "denial_reason_expected", "is_bundled", *FC)
        .unpivot(index=["material_line_id", "claim_id", "material_code", "material_name", "material_type", "quantity",
                        "billed_amount_try", "expected_payable_try", "denial_reason_expected", "is_bundled"],
                 on=FC, variable_name="flag", value_name="v")
        .filter(pl.col("v")).drop("v")
        .join(idn, on="material_line_id", how="left").join(pf, on="material_line_id", how="left")
        .join(R, on="flag", how="left"))
long = long.with_columns(
    (norm_expr("annex") + " " + pl.col("material_code") + " " + norm_expr("material_name") + " " + norm_expr("material_type")).alias("dom_txt"),
    norm_expr("material_name").alias("k_name"),
    pl.col("flag").replace_strict(FLAG_DOMAIN, default=None).alias("domain"),
)
dom_ok = pl.lit(None, pl.Boolean)
for dname, rx in D.items():
    dom_ok = pl.when(pl.col("domain") == dname).then(pl.col("dom_txt").str.contains(rx)).otherwise(dom_ok)
ctx_ok, ctx_desc = pl.lit(None, pl.Boolean), pl.lit(None, pl.Utf8)
for f, (desc, pred) in CTX.items():
    ctx_ok = pl.when(pl.col("flag") == f).then(pred.fill_null(False)).otherwise(ctx_ok)
    ctx_desc = pl.when(pl.col("flag") == f).then(pl.lit(desc)).otherwise(ctx_desc)
# catalogue-assertion flags vs the as-of snapshot
cat_ok = (pl.when(pl.col("flag") == "medula_code_undefined_on_date").then(~pl.col("listed_asof").fill_null(False))
          .when(pl.col("flag") == "unlisted_material_surcharge_billing").then(pl.col("asof_price").is_null())
          .when(pl.col("flag") == "ek3c_list_price_missing").then(pl.col("asof_price").is_null())
          .when(pl.col("flag") == "material_prescription_quantity_exceeded").then(pl.col("quantity") > 1)
          .otherwise(None))
long = long.with_columns(dom_ok.alias("domain_ok"), ctx_ok.alias("context_ok"), ctx_desc.alias("context_needed"),
                         cat_ok.alias("catalog_ok"))
long = long.with_columns(
    ((pl.col("domain_ok") == False) | (pl.col("context_ok") == False) | (pl.col("catalog_ok") == False)).fill_null(False)
    .alias("contradiction"),
    pl.when(pl.col("flag") == "barcode_sut_mismatch").then(pl.lit("UNVERIFIABLE: no barcode column"))
    .when(pl.col("domain").is_null() & pl.col("context_ok").is_null() & pl.col("catalog_ok").is_null())
    .then(pl.lit("GENERIC (no domain/context to test)")).otherwise(None).alias("note"))
long.write_parquet(os.path.join(HERE, "flags_long.parquet"))

N = m.height
per_line = m.select("material_line_id", pl.sum_horizontal([pl.col(c).cast(pl.Int32) for c in FC]).alias("n_flags"))
print(f"[e] fault-flag columns: {len(FC)} | material lines: {N}")
print("    true cells:", long.height, "| lines with >=1 flag:", (per_line["n_flags"] > 0).sum(),
      f"({(per_line['n_flags'] > 0).mean():.1%})")
print("    flags-per-line distribution:", per_line.group_by("n_flags").len().sort("n_flags").rows())
uses = pl.DataFrame({"flag": FC, "lines_true": [int(m[c].sum()) for c in FC]})
print("    flag usage (lines per flag):", uses.group_by("lines_true").agg(pl.len().alias("n_flags"),
                                                                       pl.col("flag").head(3)).sort("lines_true").rows())
print("\n[e] contradiction summary over TRUE cells:")
print(long.select(
    pl.len().alias("true_cells"),
    (pl.col("domain_ok") == False).sum().alias("material_domain_mismatch"),
    (pl.col("context_ok") == False).sum().alias("context_mismatch"),
    (pl.col("catalog_ok") == False).sum().alias("catalog_assertion_false"),
    pl.col("contradiction").sum().alias("any_contradiction"),
    pl.col("note").str.starts_with("GENERIC").sum().alias("generic_untestable"),
    pl.col("note").str.starts_with("UNVERIFIABLE").sum().alias("unverifiable")))
print("lines with >=1 contradicting flag:", long.filter(pl.col("contradiction"))["material_line_id"].n_unique(),
      "of", long["material_line_id"].n_unique(), "flagged lines")
print("\n[e] domain-checked cells by domain:")
print(long.filter(pl.col("domain").is_not_null()).group_by("domain").agg(
    pl.len().alias("cells"), (pl.col("domain_ok") == False).sum().alias("mismatch")).sort("cells", descending=True))
print("\n[e] every contradicting cell (what the demo shows next to which material):")
print(long.filter(pl.col("contradiction")).select(
    pl.col("material_line_id").str.replace("MLZ-F-SENTETIK-HASTA-", ""), pl.col("material_name").str.slice(0, 30),
    "flag", "domain_ok", "context_needed", "context_ok", "catalog_ok", "age",
    pl.col("message").str.slice(0, 60)).sort("material_line_id"))

# ---------- (f-link) flags that say 'not payable' vs expected outputs ----------
nopay = long.filter(pl.col("outcome").is_in(["no_pay", "must_not_bill_separately"]))
nl = nopay.group_by("material_line_id").agg(pl.col("flag"), pl.col("expected_payable_try").first(),
                                             pl.col("billed_amount_try").first(), pl.col("denial_reason_expected").first(),
                                             pl.col("is_bundled").first())
bad = nl.filter((pl.col("expected_payable_try") >= pl.col("billed_amount_try") - 0.005) & (pl.col("denial_reason_expected") == ""))
print(f"\n[f] lines carrying >=1 flag whose engine rule outcome is no_pay/must_not_bill_separately: {nl.height}; "
      f"of these expected_payable == billed and denial_reason_expected empty: {bad.height}")
print(bad.select(pl.col("material_line_id").str.replace("MLZ-F-SENTETIK-HASTA-", ""), "flag", "billed_amount_try",
                 "expected_payable_try"))
flagged_lines = long.group_by("material_line_id").agg(pl.col("expected_payable_try").first(), pl.col("billed_amount_try").first(),
                                                      pl.col("denial_reason_expected").first())
print("[f] flagged lines (any flag) with denial_reason_expected empty:", (flagged_lines["denial_reason_expected"] == "").sum(),
      "of", flagged_lines.height, "| with payable == billed:",
      (flagged_lines["expected_payable_try"] >= flagged_lines["billed_amount_try"] - 0.005).sum())
