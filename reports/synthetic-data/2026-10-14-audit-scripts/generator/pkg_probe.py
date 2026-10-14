import sys
import pandas as pd
root = sys.argv[1]
c = pd.read_parquet(f"{root}/data/gazette/curated/ek2c_catalog_history.parquet")
c["eff"] = pd.to_datetime(c["effective_date"], errors="coerce")
lat = c.sort_values("eff").drop_duplicates("package_code", keep="last")
for code in ["P609270","P609300","P615440","609270","609300"]:
    m = lat[lat["package_code"].astype(str)==code]
    print(code, "->", "absent" if m.empty else (str(m.iloc[0]["name"])[:70], m.iloc[0]["group"], m.iloc[0]["price_try"], str(m.iloc[0]["effective_date"])))
# what G-chapter (neurology) A3 packages look like: count & sample of names containing ablasyon / ECMO / kolektomi
for kw in ["ablasyon","ECMO","kolektomi","penektomi","miyomektomi"]:
    m = lat[lat["name"].astype(str).str.contains(kw, case=False, na=False)]
    print("EK2C", kw, len(m), m[["package_code","group"]].head(5).values.tolist())
h = pd.read_parquet(f"{root}/data/gazette/curated/ek2b_catalog_history.parquet")
h["eff"] = pd.to_datetime(h["effective_date"], errors="coerce")
lb = h.sort_values("eff").drop_duplicates("code", keep="last")
lb = lb[~lb["code"].astype(str).str.startswith(("L1","P"))]
for kw in ["ECMO","kolektomi","penektomi","miyomektomi","ablasyon","sığır"]:
    m = lb[lb["name"].astype(str).str.contains(kw, case=False, na=False)]
    print("EK2B general", kw, len(m), m[["code"]].head(4).values.ravel().tolist())
l1 = h.sort_values("eff").drop_duplicates("code", keep="last")
l1 = l1[l1["code"].astype(str).str.startswith("L1")]
m = l1[l1["name"].astype(str).str.contains("sığır|beef", case=False, na=False, regex=True)]
print("EK2B L1 beef/sigir:", m[["code","name"]].head(3).values.tolist())
