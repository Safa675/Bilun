import sys
import pandas as pd
root = sys.argv[1]
cur = f"{root}/data/gazette/curated"
h = pd.read_parquet(f"{cur}/ek2b_catalog_history.parquet")
print("EK2B cols:", list(h.columns))
print("EK2B rows:", len(h))
print(h["effective_date"].astype(str).value_counts().sort_index().to_string())
# latest snapshot as generator does (catalog.py:_ek2b)
w = h.copy()
w["effective_date_dt"] = pd.to_datetime(w["effective_date"], errors="coerce")
latest = w.sort_values("effective_date_dt").drop_duplicates(subset=["code"], keep="last")
print("latest rows:", len(latest), "max eff:", latest["effective_date_dt"].max(), "min eff among latest:", latest["effective_date_dt"].min())
print(latest["effective_date_dt"].dt.date.astype(str).value_counts().head(10).to_string())
latest["code_str"] = latest["code"].astype(str)
gen = latest[~latest.code_str.str.startswith("L1") & ~latest.code_str.str.startswith("P")]
lab = latest[latest.code_str.str.startswith("L1")]
yat = latest[latest["name"].str.contains("yatak", case=False, na=False)]
mua = latest[latest["name"].str.contains("muayene", case=False, na=False) | latest["name"].str.contains("konsültasyon", case=False, na=False)]
def valid(d): return d[d["price_try"].notna() & (d["price_try"] > 0)]
print("pool sizes (all / priced): general", len(gen), len(valid(gen)), "lab", len(lab), len(valid(lab)), "yatak", len(yat), len(valid(yat)), "muayene", len(mua), len(valid(mua)))
print("--- muayene pool (priced) ---")
for _, r in valid(mua).iterrows():
    print(r["code"], "|", str(r["name"])[:90], "|", r["price_try"])
print("--- yatak pool (priced) ---")
for _, r in valid(yat).iterrows():
    print(r["code"], "|", str(r["name"])[:90], "|", r["price_try"])
print("--- pinned demo codes ---")
for c in ["600150","600160","609270","609300","610070","701450","701460","705371","700390","612070","L116470","G100580","P615440","912550","612160","620030","801510","700620","615430"]:
    m = latest[latest.code_str == c]
    if m.empty:
        print(c, "NOT IN LATEST EK-2B")
    else:
        r = m.iloc[0]
        print(c, "|", str(r["name"])[:100], "|", r["price_try"], "|", r["effective_date"])
