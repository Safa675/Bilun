import sys
import pandas as pd
root = sys.argv[1]
cur = f"{root}/data/gazette/curated"
c = pd.read_parquet(f"{cur}/ek2c_catalog_history.parquet")
print("EK2C cols:", list(c.columns))
c["eff"] = pd.to_datetime(c["effective_date"], errors="coerce")
lat = c.sort_values("eff").drop_duplicates("package_code", keep="last")
print("EK2C latest rows:", len(lat), "eff dates:", lat["effective_date"].astype(str).value_counts().to_dict())
print("group values:", lat["group"].astype(str).value_counts().to_dict())
for g in ["A3","B","C","D","E"]:
    sub = lat[lat["group"].astype(str)==g]
    print("group", g, "n=", len(sub), "examples:", [(r.package_code, str(r.name)[:50]) for r in sub.head(4).itertuples()])
for fn in ["ek3c2_materials.parquet","ek3f1_arthroplasty_materials.parquet","ek3o_hematology_oncology_materials.parquet","ek3r_gastroenterology_materials.parquet","ek3s_pulmonology_materials.parquet","ek3p_nephrology_materials.parquet"]:
    d = pd.read_parquet(f"{cur}/{fn}")
    v = d[d["price_try"].notna() & (d["price_try"]>0) & d["sut_code"].notna()] if "sut_code" in d.columns else d
    print("==", fn, "cols:", list(d.columns)[:12], "rows:", len(d), "valid:", len(v))
    if "category" in d.columns:
        print("   category values:", v["category"].astype(str).value_counts().head(8).to_dict())
    if "price_try" in v.columns:
        print("   price min/median/max:", v["price_try"].min(), v["price_try"].median(), v["price_try"].max())
    print("   sample names:", [str(x)[:45] for x in v["material_name"].head(6)] if "material_name" in v.columns else "")
for code in ["OP1592","OP1000","OP2000","AP1030","OR2640"]:
    hits = []
    import glob, os
    for p in glob.glob(f"{cur}/ek3*_materials.parquet"):
        d = pd.read_parquet(p)
        if "sut_code" in d.columns and (d["sut_code"].astype(str)==code).any():
            r = d[d["sut_code"].astype(str)==code].iloc[0]
            hits.append((os.path.basename(p), str(r.get("material_name"))[:60], r.get("price_try")))
    print(code, hits or "NOT FOUND in any ek3*_materials.parquet")
a = pd.read_parquet(f"{cur}/ek4a_drugs.parquet")
print("EK4A cols:", list(a.columns))
print("EK4A rows:", len(a))
