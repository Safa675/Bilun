"""(e) drug line money + clinical fields + consistency with Bilun's own SUT 4.2 drug rules."""
import json
import unicodedata

import polars as pl

from common import REPO, SYN, drugs, ek4a, hdr, save
from drug_class_map import MAP

d = drugs()

hdr("arithmetic")
m = d.with_columns(
    ((pl.col("quantity") * pl.col("unit_price_try") - pl.col("billed_amount_try")).abs() > 0.011).alias("qty_x_unit_ne_billed"),
    ((pl.col("billed_amount_try") * (1 - pl.col("discount_tier_expected")) - pl.col("expected_payable_try")).abs() > 0.011)
    .alias("payable_ne_billed_x_(1-discount)"),
    ((pl.col("copay_rate") - pl.col("discount_tier_expected")).abs() < 1e-9).alias("copay_equals_discount"),
)
print(m.select(pl.len().alias("lines"), pl.col("qty_x_unit_ne_billed").sum(), pl.col("payable_ne_billed_x_(1-discount)").sum(),
               pl.col("copay_equals_discount").sum()))
print("copay_rate range:", d["copay_rate"].min(), "-", d["copay_rate"].max(),
      "| lines with copay_rate >= 0.40:", d.filter(pl.col("copay_rate") >= 0.40).height,
      "| float-artifact values (e.g. 0.31000000000000005):",
      d.filter((pl.col("copay_rate") * 1000).round(6) != (pl.col("copay_rate") * 1000).round(0)).height)

hdr("unit price distribution (TRY per pack)")
print(d.select(pl.col("unit_price_try").min().alias("min"), pl.col("unit_price_try").median().alias("median"),
               pl.col("unit_price_try").max().alias("max"),
               (pl.col("unit_price_try") <= 500).sum().alias("n_le_500"),
               (pl.col("unit_price_try") > 500).sum().alias("n_gt_500")))
e = ek4a()
asof = d.join(e, left_on="drug_code", right_on="kamu_no", how="left").filter(
    (pl.col("vf") <= pl.col("d_date")) & (pl.col("vu").is_null() | (pl.col("d_date") < pl.col("vu"))))
print("price range by EK-4A discount_status (as-of rows):")
print(asof.with_columns(pl.col("discount_status").str.to_uppercase().str.replace_all("İ", "I").str.replace("Ş", "S")
                        .str.replace("Ü", "U").alias("st")).group_by("st").agg(
    pl.len(), pl.col("unit_price_try").min().alias("min"), pl.col("unit_price_try").max().alias("max")))
cm = pl.DataFrame([(k, v[0], v[1]) for k, v in MAP.items()], schema=["drug_code", "inn", "cls"], orient="row")
dc = d.join(cm, on="drug_code", how="left")
spec = ["antineoplastic_targeted", "biologic_dmard", "complement_inhibitor", "stem_cell_mobilizer", "antifibrotic",
        "pah", "immunoglobulin", "coagulation_factor", "hiv_arv", "esa", "g_csf"]
print("specialty/biologic/targeted lines vs everything else:")
print(dc.with_columns(pl.col("cls").is_in(spec).fill_null(False).alias("specialty")).group_by("specialty").agg(
    pl.len(), pl.col("unit_price_try").median().alias("median_unit"), pl.col("unit_price_try").min().alias("min_unit"),
    pl.col("unit_price_try").max().alias("max_unit")))
print(dc.filter(pl.col("cls").is_in(spec)).select("drug_code", "drug_name", "unit_price_try").sort("unit_price_try").head(14))
print("most expensive non-specialty packs:")
print(dc.filter(~pl.col("cls").is_in(spec).fill_null(False)).sort("unit_price_try", descending=True)
      .select("drug_name", "unit_price_try").head(6))
same = d.group_by("drug_code").agg(pl.col("drug_name").first(), pl.col("drug_claim_date").sort(),
                                   pl.col("unit_price_try"), pl.len()).filter(pl.col("len") > 1)
print("same product, different unit price:")
print(same)

hdr("clinical / indication fields on drug lines")
clin = ["drug_specialty_board_report_present", "drug_report_duration_months", "drug_inpatient_supply",
        "prescriber_specialty", "annual_application_count", "is_loading_phase", "biomarkers", "prior_therapies",
        "surcharge_rate"]
print(pl.DataFrame({"field": clin, "dtype": [str(d.schema[c]) for c in clin], "null": [d[c].null_count() for c in clin]}))
print("denial_reason_expected non-empty:", d.filter(pl.col("denial_reason_expected") != "").height)
eo = pl.read_parquet(SYN / "claims/expected_rule_outputs.parquet").filter(pl.col("line_type") == "ilac")
print(eo.group_by("rule_family", "expected_status", "expected_denial_reason").len())

hdr("molecules that Bilun's own SUT 4.2 rule set marks report_required=true")
rules = json.load(open(REPO / "data/gazette/prose_rules/drug_indication_prose.json"))["rules"]


def norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower().translate(str.maketrans("çğıöşüâîû", "cgiosuaiu")))


rule_names = [(norm(n), bool(r.get("report_required")), r["sut_section"]) for r in rules for n in (r.get("drug_names") or [])]
TR = {  # INN (judgment table) -> Turkish INN token used in the SUT text
    "abatacept SC": "abatasept", "adalimumab": "adalimumab", "daratumumab": "daratumumab", "pomalidomide": "pomalidomid",
    "dasatinib": "dasatinib", "trametinib": "trametinib", "dacomitinib": "dakomitinib", "erlotinib": "erlotinib",
    "selinexor": "selineksor", "eculizumab": "ekulizumab", "pegfilgrastim": "pegfilgrastim", "darbepoetin alfa": "darbepoetin",
    "pirfenidone": "pirfenidon", "paliperidone": "paliperidon", "aripiprazole": "aripiprazol", "risperidone": "risperidon",
    "risperidone LAI": "risperidon", "quetiapine": "ketiapin", "olanzapine": "olanzapin", "pregabalin": "pregabalin",
    "gabapentin": "gabapentin", "duloxetine": "duloksetin", "vildagliptin": "vildagliptin", "linagliptin/metformin": "linagliptin",
    "apixaban 2.5": "apiksaban", "edoxaban 60": "edoksaban", "macitentan/tadalafil": "masitentan", "paricalcitol IV": "parikalsitol",
    "albumin 20%": "albumin", "immunoglobulin SC + hyaluronidase": "immunglobulin", "factor VIII/vWF (plasma)": "faktor viii",
    "factor VIII (moroctocog)": "faktor viii", "factor VIII (turoctocog)": "faktor viii", "factor IX (nonacog)": "faktor ix",
    "protein C concentrate": "protein c", "voriconazole IV": "vorikonazol", "anidulafungin": "anidulafungin",
    "trientine": "trientin", "cabergoline": "kabergolin", "ibandronate 150 mg": "ibandron", "tenofovir disoproxil": "tenofovir",
    "ezetimibe": "ezetimib", "atorvastatin": "atorvastatin", "alpha-lipoic acid": "alfa lipoik", "zonisamide": "zonisamid",
    "levetiracetam oral sol.": "levetirasetam", "doxorubicin": "doksorubisin", "paclitaxel": "paklitaksel",
    "hydroxyurea": "hidroksiure", "montelukast": "montelukast", "desloratadine/montelukast": "montelukast",
}
tok = pl.DataFrame({"inn": list(TR), "tok": list(TR.values())})
tok = tok.with_columns(
    pl.col("tok").map_elements(lambda t: any(t in n and rep for n, rep, _ in rule_names), return_dtype=pl.Boolean).alias("report_rule"),
    pl.col("tok").map_elements(lambda t: ",".join(sorted({s for n, _, s in rule_names if t in n}))[:40], return_dtype=pl.String).alias("sections"),
)
x = dc.join(tok, on="inn", how="inner").filter(pl.col("report_rule"))
print("drug lines whose molecule has >=1 report_required SUT 4.2 rule in Bilun's corpus:", x.height,
      "| patients:", x["patient_id"].n_unique())
print("of those, lines with report flag present / denial reason set:",
      x.filter(pl.col("drug_specialty_board_report_present").is_not_null()).height, "/",
      x.filter(pl.col("denial_reason_expected") != "").height)
save(x.select("drug_claim_line_id", "drug_name", "inn", "sections"), "e_report_required_molecules")
print(x.group_by("inn").agg(pl.len(), pl.col("sections").first()).sort("len", descending=True))

hdr("MEDULA 0411 'drug indication report missing' scenario (patient 0031) vs its drug lines")
ev = pl.read_parquet(SYN / "claims/medula_rejection_events.parquet").filter(pl.col("hata_kodu") == "0411")
print(ev.select("rejection_event_id", "claim_id", "related_line_type", "related_line_id", "hata_mesaji"))
dl = d.filter(pl.col("claim_id").is_in(ev["claim_id"].to_list())).join(cm, on="drug_code", how="left")
print(dl.select("drug_claim_line_id", "drug_name", "inn", "denial_reason_expected", "drug_specialty_board_report_present"))
print("tolterodine named in any SUT 4.2 rule of Bilun's corpus:", any("tolterodin" in n for n, _, _ in rule_names))
print(eo.filter(pl.col("claim_id").is_in(ev["claim_id"].to_list())).select("line_id", "expected_status", "expected_payable_try"))
