"""Build a long, dated index of every EK-3 sub-annex snapshot (read-only on the repo).

Output (scratchpad only): ek3_index.parquet with one row per (snapshot file, code):
  annex, effective_date, is_mulga, source_file, code, primary_name, full_name, section, price

Parsing is generic because the raw snapshots are Excel dumps with 'Unnamed: n' columns:
  * code column  = the data column with the most cells matching the SUT material-code regex
  * header row   = first row containing 'SUT KODU'; price column = header containing 'FİYAT'
  * primary_name = the column right after the code column ('TIBBİ MALZEME ALAN TANIMI' / 'UYGULAMA YERİ')
  * full_name    = all text columns between code and the first AÇIKLAMA/MİAT/ÖZEL/FİYAT column
  * section      = last non-code row with text in the primary-name column (sub-heading)
"""
import glob
import os
import re

import polars as pl

RAW = "/home/safa/Documents/Bilun/data/gazette/raw"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ek3_index.parquet")
CODE_RE = re.compile(r"^[A-ZÇĞİÖŞÜ]{1,4}\d{3,5}[A-Z]{0,2}$")
STOP_HDR = ("AÇIKLAMA", "MİAT", "ÖZEL", "FİYAT")


def _num(s):
    if s is None:
        return None
    t = str(s).strip().replace(" ", "")
    if not t:
        return None
    # Excel dumps are mostly plain floats ('1074.39'); tolerate Turkish '1.074,39'
    if re.fullmatch(r"-?\d+(\.\d+)?([eE]-?\d+)?", t):
        return float(t)
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d+)?", t):
        return float(t.replace(".", "").replace(",", "."))
    if re.fullmatch(r"-?\d+,\d+", t):
        return float(t.replace(",", "."))
    return None


def parse_file(path: str) -> list[dict]:
    df = pl.read_parquet(path)
    meta = {c: df[c][0] for c in df.columns if c.startswith("__")} if df.height else {}
    cols = [c for c in df.columns if not c.startswith("__")]
    if not cols or df.height == 0:
        return []
    d = df.select([pl.col(c).cast(pl.Utf8).str.strip_chars().alias(c) for c in cols])
    # code column: most regex hits (vectorised per column)
    hits = {c: d.select(pl.col(c).str.contains(CODE_RE.pattern).fill_null(False).sum()).item() for c in cols}
    code_col = max(hits, key=hits.get)
    if hits[code_col] == 0:
        return []
    ci = cols.index(code_col)
    rows = d.rows()
    # header row (first ~8 rows), plus the column headers themselves
    header = {c: (c if not c.startswith("Unnamed") else "") for c in cols}
    for r in rows[:8]:
        if any(v and "SUT KODU" in v.upper() for v in r):
            for c, v in zip(cols, r):
                if v:
                    header[c] = (header[c] + " " + v).strip()
            break
    price_col = next((c for c in cols if "FİYAT" in header[c].upper()), None)
    stop_idx = next((i for i, c in enumerate(cols) if i > ci and any(k in header[c].upper() for k in STOP_HDR)),
                    len(cols))
    name_cols = cols[ci + 1: stop_idx]
    if price_col is None:  # fallback: right-most column with numeric values on code rows
        for c in reversed(cols[ci + 1:]):
            vals = [(_num(r[cols.index(c)])) for r in rows if r[ci] and CODE_RE.match(r[ci])]
            if sum(v is not None for v in vals) >= 0.5 * max(1, len(vals)):
                price_col = c
                break
    out, section = [], None
    pidx = cols.index(price_col) if price_col else None
    for r in rows:  # row-wise scan is unavoidable: section headers are positional
        code = r[ci]
        prim = r[ci + 1] if ci + 1 < len(cols) else None
        if code and CODE_RE.match(code):
            full = " | ".join(r[cols.index(c)] for c in name_cols if r[cols.index(c)])
            out.append({
                "code": code, "primary_name": prim, "full_name": full, "section": section,
                "price": _num(r[pidx]) if pidx is not None else None,
            })
        elif prim and not code and (pidx is None or _num(r[pidx]) is None):
            section = prim
    for o in out:
        o.update({
            "annex": meta.get("__annex_code"),
            "effective_date": os.path.basename(os.path.dirname(path)).split("=")[1],
            "is_mulga": bool(meta.get("__is_mulga")),
            "source_file": os.path.relpath(path, RAW),
        })
    return out


rows = []
for f in sorted(glob.glob(f"{RAW}/annex=EK-3*/effective_date=*/*.parquet")):
    rows.extend(parse_file(f))
idx = pl.DataFrame(rows, schema={
    "code": pl.Utf8, "primary_name": pl.Utf8, "full_name": pl.Utf8, "section": pl.Utf8, "price": pl.Float64,
    "annex": pl.Utf8, "effective_date": pl.Utf8, "is_mulga": pl.Boolean, "source_file": pl.Utf8,
})
idx.write_parquet(OUT)
print("rows", idx.height, "files", idx["source_file"].n_unique(), "codes", idx["code"].n_unique())
print(idx.group_by("annex").agg(pl.len(), pl.col("code").n_unique().alias("codes"),
                                pl.col("price").is_null().sum().alias("null_price"),
                                pl.col("effective_date").unique().sort().alias("dates")).sort("annex"))
# annex-label sanity: folder annex vs __annex_code
print(idx.with_columns(pl.col("source_file").str.extract(r"annex=([^/]+)/").alias("folder"))
      .filter(pl.col("folder") != pl.col("annex")).select("folder", "annex").unique())
