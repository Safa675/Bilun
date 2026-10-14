"""(c) prescription diversity: drug identity vs regimen fields; route vs dosage form; dose vs strength."""
import polars as pl

from common import drugs, hdr, recete, save

d = drugs()
r = recete()

hdr("drug identity diversity")
print("lines", d.height, "| distinct drug_code", d["drug_code"].n_unique(),
      "| distinct barkod", d["barkod"].n_unique())
rep = d.group_by("drug_code").agg(pl.col("drug_name").first(), pl.col("patient_id").n_unique().alias("patients"),
                                  pl.len().alias("lines")).filter(pl.col("lines") > 1)
print("drugs used on >1 line:", rep.height)
print(rep)

hdr("regimen fields in recete_clean")
cols = ["dozaj_ham", "verilis_yolu", "gun", "doz_mg", "doz_birimi", "siklik", "miktar"]
print(pl.DataFrame({"field": cols, "n_distinct": [r[c].n_unique() for c in cols],
                    "values": [str(r[c].unique().sort().to_list()[:6]) for c in cols]}))
sig = r.select(cols[:-1]).unique()
print("distinct regimen signatures (all fields except miktar):", sig.height, "over", r.height, "prescriptions")
print("miktar distribution:", r["miktar"].value_counts().sort("miktar").rows())

hdr("route 'Agizdan (Oral)' vs dosage form parsed from the product name")
name = pl.col("ilac_adi").str.to_uppercase()
form = (
    pl.when(name.str.contains(r"GOZ (DAMLASI|POMADI)|GÖZ"))
    .then(pl.lit("ophthalmic"))
    .when(name.str.contains(r"BURUN"))
    .then(pl.lit("nasal"))
    .when(name.str.contains(r"\bINH\b|INHALASYON|NEBULIZER|NEBULIZASYON"))
    .then(pl.lit("inhaled"))
    .when(name.str.contains(r"VAJINAL|OVUL"))
    .then(pl.lit("vaginal"))
    .when(name.str.contains(r"LAVMAN|ENEMA|REKTAL"))
    .then(pl.lit("rectal"))
    .when(name.str.contains(r"KREM|JEL|MERHEM|POMAD|LOSYON|EMULSIYOJEL"))
    .then(pl.lit("topical"))
    .when(name.str.contains(r"GARGARA"))
    .then(pl.lit("oromucosal_rinse"))
    .when(name.str.contains(r"IRRIGASYON"))
    .then(pl.lit("irrigation"))
    .when(name.str.contains(
        r"ENJ|INFUZYON|\bAMP\b|AMPUL|\bFLK\b|FLAKON|\bI\.?V\.?\b|\bIM\b|S\.C\.|\bSC\b|KALEM|SIRINGA|ENJEKTOR|"
        r"SOL \(|SOL\.|\bSOL\b|COZELTISI|COZELISI|DEKSTROZ|MANNITOL|IZOLEKS|IZODEKS|IZOLEN|NEOFLEKS|TURKFLEKS|PRIMEFLEKS|POLINUTHREE|AMINOASIT|KULL HAZ"))
    .then(pl.lit("parenteral"))
    .when(name.str.contains(r"TABLET|\bTB\b|FTB|\bTAB\b|KAPSUL|\bKAP\b|KAPS|DRJ|SASE|EFERVESAN|SUSP|SURUP|ORAL|COZ\.|SISE|\bML\b"))
    .then(pl.lit("oral"))
    .otherwise(pl.lit("unclassified"))
)
rf = r.with_columns(form.alias("form"))
print(rf.group_by("form").len().sort("len", descending=True))
nonoral = rf.filter(~pl.col("form").is_in(["oral", "unclassified", "oromucosal_rinse"]))
print("prescriptions with route=Oral but non-oral dosage form:", nonoral.height, "of", r.height)
save(rf.select("HASTA_ID", "RECETE_TARIH", "ilac_adi", "verilis_yolu", "form"), "c_route_vs_form")
print(rf.filter(pl.col("form") == "unclassified").select("ilac_adi"))

hdr("doz_mg=500 per dose vs labelled strength (first 'N MG' in name; only single-strength mg products)")
st = rf.with_columns(
    pl.col("ilac_adi").str.replace_all(",", ".").str.extract(r"(\d+(?:\.\d+)?)\s*MG\b", 1).cast(pl.Float64).alias("strength_mg"),
    pl.col("ilac_adi").str.contains(r"\d\s*MG\s*/\s*\d|\d\s*MG\s*\+|/\d+(?:[.,]\d+)?\s*MG").alias("combo_or_conc"),
    pl.col("ilac_adi").str.contains(r"\bIU\b|MCG|%|MMOL|\bG\b|\bGR\b").alias("non_mg_unit"),
)
solid = st.filter((pl.col("form") == "oral") & pl.col("strength_mg").is_not_null() & ~pl.col("combo_or_conc")
                  & pl.col("ilac_adi").str.contains(r"TABLET|\bTB\b|FTB|\bTAB\b|KAPSUL|\bKAP\b|DRJ"))
solid = solid.with_columns((pl.col("doz_mg") / pl.col("strength_mg")).alias("units_per_dose"),
                           (pl.col("doz_mg") * pl.col("siklik")).alias("daily_mg"))
print("single-strength oral solid prescriptions parsed:", solid.height)
print("units per dose (500 mg / strength) distribution:")
print(solid.select(pl.col("units_per_dose").quantile(0.0).alias("min"), pl.col("units_per_dose").median().alias("median"),
                   pl.col("units_per_dose").quantile(1.0).alias("max"),
                   (pl.col("units_per_dose") >= 10).sum().alias("n_ge_10_units_per_dose"),
                   (pl.col("units_per_dose") != pl.col("units_per_dose").round(0)).sum().alias("n_fractional")))
print(solid.sort("units_per_dose", descending=True).select("ilac_adi", "strength_mg", "doz_mg", "siklik", "daily_mg", "units_per_dose").head(12))
save(solid.select("HASTA_ID", "RECETE_TARIH", "ilac_adi", "strength_mg", "doz_mg", "siklik", "gun", "miktar", "units_per_dose"),
     "c_dose_vs_strength")
nm = st.filter(pl.col("non_mg_unit") & (pl.col("form") != "oral"))
print("prescriptions whose product is dosed in IU/mcg/%/mmol/g/mL but regimen says 500 mg:", nm.height)

hdr("pack arithmetic: units needed (gun*siklik*units_per_dose) vs units dispensed (miktar*pack size)")
pk = solid.with_columns(
    pl.col("ilac_adi").str.extract(r"\(?\s*(\d+)\s*(?:FTB|TB|TAB|TABLET|KAP|KAPSUL|DRJ|FILM KAPLI TABLET|ADET|SERT KAPSUL)", 1)
    .cast(pl.Int64).alias("pack_n"))
pk = pk.filter(pl.col("pack_n").is_not_null() & (pl.col("pack_n") != pl.col("strength_mg")))
pk = pk.with_columns((pl.col("gun") * pl.col("siklik") * pl.col("units_per_dose")).alias("needed"),
                     (pl.col("miktar") * pl.col("pack_n")).alias("dispensed"))
pk = pk.with_columns((pl.col("dispensed") / pl.col("needed")).alias("ratio"))
print("parsed:", pk.height, "| dispensed covers <50% of 7-day need:", pk.filter(pl.col("ratio") < 0.5).height,
      "| >200%:", pk.filter(pl.col("ratio") > 2).height)
print(pk.select("ilac_adi", "pack_n", "miktar", "needed", "dispensed", "ratio").sort("ratio").head(8))
