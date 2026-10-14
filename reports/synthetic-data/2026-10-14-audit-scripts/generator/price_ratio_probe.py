import sys
import pandas as pd
root = sys.argv[1]
h = pd.read_parquet(f"{root}/data/gazette/curated/ek2b_catalog_history.parquet")
h["code"] = h["code"].astype(str)
h["eff"] = pd.to_datetime(h["effective_date"], errors="coerce")
print(h[["effective_date","valid_from","valid_to","source_parquet"]].drop_duplicates(["effective_date","source_parquet"]).to_string())
latest = h.sort_values("eff").drop_duplicates("code", keep="last").set_index("code")["price_try"]
for snap in ["2022-09-03","2023-03-24","2023-09-02","2024-05-11"]:
    s = h[h["effective_date"].astype(str)==snap].drop_duplicates("code", keep="last").set_index("code")["price_try"]
    j = pd.concat([latest.rename("latest"), s.rename("snap")], axis=1, join="inner")
    j = j[(j.snap>0)&(j.latest>0)]
    r = j.latest/j.snap
    print(snap, "n=", len(j), "median latest/snap=", round(r.median(),3), "share ratio==1:", round((r.round(4)==1).mean(),3))
