"""(d) drug vs diagnosis (lenient indication sets), vs age/sex, vs department / claim context.
Class map and ICD sets are a JUDGMENT table (drug_class_map.py); the counts are measured."""
import polars as pl

from common import anadata, drugs, dx, hdr, headers, proc, save
from drug_class_map import ANESTHESIA_ICU, CONTRAST, MAP, PEDIATRIC_EXPLICIT, PEDIATRIC_LIKELY

d = drugs()
h = headers()
a = anadata()

cmap = pl.DataFrame(
    [(k, *v) for k, v in MAP.items()],
    schema=["drug_code", "inn", "cls", "icd_spec", "sex_only", "peds", "home_spec", "basis"], orient="row")
cmap.write_csv("out/drug_class_map.csv")

# ---- diagnosis sets
cdx = pl.concat([
    dx().select("claim_id", pl.col("icd10_code").alias("icd")),
    h.select("claim_id", pl.col("primary_icd10").alias("icd")),
]).with_columns(pl.col("icd").str.strip_chars().str.to_uppercase()).unique()
claim_pat = h.select("claim_id", "patient_id")
pdx = pl.concat([
    cdx.join(claim_pat, on="claim_id").select("patient_id", "icd"),
    a.select(pl.col("HASTA_ID").alias("patient_id"),
             pl.col("TUM_EPS_TANILAR").str.split(",").alias("icd")).explode("icd"),
    a.select(pl.col("HASTA_ID").alias("patient_id"), pl.col("TANIKODU").alias("icd")),
]).with_columns(pl.col("icd").str.strip_chars().str.to_uppercase()).filter(pl.col("icd") != "").unique()

# ---- explode spec into range / prefix entries
spec = cmap.select("drug_code", pl.col("icd_spec").str.split(";").alias("e")).explode("e").with_columns(
    pl.col("e").str.contains("-").alias("is_range"),
    pl.col("e").str.split("-").list.get(0).alias("lo"),
    pl.col("e").str.split("-").list.get(-1).alias("hi"),
)


def matched(lines: pl.DataFrame, dxs: pl.DataFrame, key: str) -> pl.DataFrame:
    x = lines.select("drug_claim_line_id", "drug_code", key).join(spec, on="drug_code").join(dxs, on=key)
    x = x.with_columns(pl.col("icd").str.slice(0, 3).alias("c3")).with_columns(
        pl.when(pl.col("is_range"))
        .then((pl.col("c3") >= pl.col("lo").str.slice(0, 3)) & (pl.col("c3") <= pl.col("hi").str.slice(0, 3)))
        .otherwise(pl.col("icd").str.starts_with(pl.col("e")))
        .alias("hit"))
    return x.group_by("drug_claim_line_id").agg(pl.col("hit").any().alias("hit"))


L = d.join(h.select("claim_id", "claim_type", "department", "primary_icd10"), on="claim_id").join(cmap, on="drug_code", how="left")
narrow = L.filter(pl.col("cls").is_not_null())
mc = matched(narrow, cdx, "claim_id").rename({"hit": "ind_on_claim"})
mp = matched(narrow, pdx, "patient_id").rename({"hit": "ind_in_patient_history"})
narrow = narrow.join(mc, on="drug_claim_line_id", how="left").join(mp, on="drug_claim_line_id", how="left").with_columns(
    pl.col("ind_on_claim").fill_null(False), pl.col("ind_in_patient_history").fill_null(False))
claim_icds = cdx.group_by("claim_id").agg(pl.col("icd").sort().str.join(",").alias("claim_icds"))
narrow = narrow.join(claim_icds, on="claim_id", how="left")

hdr("indication coverage (lenient ICD sets)")
print("drug lines total:", d.height, "| lines with a narrow-indication drug (in judgment table):", narrow.height)
print(narrow.select(
    (~pl.col("ind_on_claim")).sum().alias("no_indication_on_claim"),
    (~pl.col("ind_in_patient_history")).sum().alias("no_indication_anywhere_in_patient_history"),
    pl.col("ind_on_claim").sum().alias("indication_on_claim"),
))
by = narrow.group_by("cls").agg(pl.len().alias("lines"), (~pl.col("ind_on_claim")).sum().alias("no_ind_claim"),
                                (~pl.col("ind_in_patient_history")).sum().alias("no_ind_patient")).sort("lines", descending=True)
print(by)
save(narrow.select("drug_claim_line_id", "patient_id", "claim_type", "department", "drug_name", "inn", "cls",
                   "icd_spec", "claim_icds", "ind_on_claim", "ind_in_patient_history", "basis"), "d_indication_check")
print(narrow.filter(~pl.col("ind_in_patient_history")).select(
    "drug_claim_line_id", "department", "inn", "claim_icds").head(40))

hdr("high-acuity specialty drugs (oncology/haemophilia/biologic/HIV/transplant/rare) without indication")
hi_cls = ["antineoplastic", "antineoplastic_targeted", "antineoplastic_hormonal", "coagulation_factor",
          "complement_inhibitor", "stem_cell_mobilizer", "hiv_arv", "transplant_immunosuppressant",
          "biologic_dmard", "immunoglobulin", "wilson_chelator", "pah", "antifibrotic"]
hi = narrow.filter(pl.col("cls").is_in(hi_cls))
print("lines:", hi.height, "| no indication on claim:", hi.filter(~pl.col("ind_on_claim")).height,
      "| none in whole patient history:", hi.filter(~pl.col("ind_in_patient_history")).height,
      "| patients affected:", hi.filter(~pl.col("ind_in_patient_history"))["patient_id"].n_unique())

hdr("sex / age")
demo = a.select(pl.col("SQ_EPISODE").alias("episode_id"), "TANI_YASI", "CINSIYET")
Ld = L.join(demo, on="episode_id", how="left")
print("lines without demographics:", Ld.filter(pl.col("CINSIYET").is_null()).height)
sexbad = Ld.filter(((pl.col("sex_only") == "F") & (pl.col("CINSIYET") == "E")) |
                   ((pl.col("sex_only") == "M") & (pl.col("CINSIYET") == "K")))
print("sex-restricted drugs on the wrong sex:", sexbad.height, "of", Ld.filter(pl.col("sex_only").is_in(["F", "M"])).height)
print(sexbad.select("drug_claim_line_id", "CINSIYET", "TANI_YASI", "drug_name", "department"))
pe = Ld.filter(pl.col("drug_code").is_in(list(PEDIATRIC_EXPLICIT)))
pl_ = Ld.filter(pl.col("drug_code").is_in(list(PEDIATRIC_LIKELY)))
print("explicit pediatric products:", pe.height, "| given to adults (>=18):", pe.filter(pl.col("TANI_YASI") >= 18).height)
print(pe.select("drug_claim_line_id", "TANI_YASI", "drug_name"))
print("likely-pediatric oral liquids:", pl_.height, "| to adults:", pl_.filter(pl.col("TANI_YASI") >= 18).height)
print("cohort age range:", a["TANI_YASI"].min(), "-", a["TANI_YASI"].max(), "| patients < 18:",
      a.filter(pl.col("TANI_YASI") < 18)["HASTA_ID"].n_unique())

hdr("contrast media vs imaging procedure on the same claim")
p = proc()
img = p.filter(pl.col("procedure_name").str.contains(
    r"(?i)tomografi|\bBT\b|\bMR\b|MRG|rezonans|anjiyo|ürografi|urografi|kontrast|DSA|histerosalpingo|kolanjio|venografi|sintigrafi"))
cc = L.filter(pl.col("drug_code").is_in(list(CONTRAST)))
cc = cc.join(img.group_by("claim_id").agg(pl.col("procedure_name").alias("imaging")), on="claim_id", how="left")
print(cc.select("drug_claim_line_id", "claim_type", "department", "drug_name", "imaging"))
print("contrast lines:", cc.height, "| with no imaging procedure on claim:", cc.filter(pl.col("imaging").is_null()).height)
for cid in cc["claim_id"].to_list():
    print(cid, p.filter(pl.col("claim_id") == cid)["procedure_name"].to_list())

hdr("anaesthesia/ICU/parenteral-nutrition drugs vs claim type")
ai = L.filter(pl.col("drug_code").is_in(list(ANESTHESIA_ICU)))
print(ai.select("drug_claim_line_id", "claim_type", "department", "drug_name"))

hdr("claim type: take-home packs / drugs on outpatient claims")
outp = L.filter(pl.col("claim_type").is_in(["poliklinik", "koruyucu", "meslek_hastaligi"]))
print("drug lines on outpatient (poliklinik/koruyucu/meslek) claims:", outp.height, "of", L.height)
iv = outp.filter(pl.col("drug_name").str.contains(r"INFUZYON|I\.V\.|\bIV\b|SETLI|SETSIZ|DEKSTROZ|MANNITOL|IZOLEKS|IZODEKS|TURKFLEKS|NEOFLEKS|PRIMEFLEKS|AMINOASIT|POLINUTHREE"))
print("of which IV infusion products:", iv.height)
print(iv.select("drug_claim_line_id", "claim_type", "department", "drug_name"))

hdr("departments present in the cohort vs home specialties of the drug classes")
print(h["department"].value_counts().sort("count", descending=True))
absent = {"psikiyatri", "goz", "dermatoloji", "kadin dogum", "dis", "uroloji", "romatoloji", "enfeksiyon", "immunoloji"}
nd = narrow.with_columns(pl.col("home_spec").str.split("/").list.eval(pl.element().is_in(list(absent))).list.all().alias("home_absent"))
print("narrow-class lines whose prescribing specialty is absent from the cohort's departments:",
      nd.filter(pl.col("home_absent")).height)
print(nd.filter(pl.col("home_absent")).group_by("home_spec").len().sort("len", descending=True))
onc = narrow.filter(pl.col("cls").is_in(["antineoplastic", "antineoplastic_targeted", "antineoplastic_hormonal",
                                         "coagulation_factor", "stem_cell_mobilizer", "complement_inhibitor"]))
print("onco/haem drugs billed under non-onco/haem departments:",
      onc.filter(~pl.col("department").is_in(["Onkoloji", "Hematoloji"])).height, "of", onc.height)
print(onc.filter(~pl.col("department").is_in(["Onkoloji", "Hematoloji"])).select("drug_claim_line_id", "department", "inn", "claim_icds"))
