"""Render clean-bill tables (markdown) from results/*.json."""
import json, os
from collections import OrderedDict
HERE = os.path.dirname(os.path.abspath(__file__))
KAMU = {"8699508270224": "A03721", "8680741521174": "A17700", "8697637691743": "A15078",
        "8699606694649": "A14359", "8699708690525": "A12140", "8699688771559": "A05705"}

def fmt(x):
    s = f"{float(x):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def dates(ds):
    ds = sorted(set(ds))
    if len(ds) <= 3:
        return ", ".join(x[5:] for x in ds)
    return f"{ds[0][5:]}…{ds[-1][5:]} (daily)"

def table(rows):
    agg = OrderedDict()
    for r in rows:
        k = (r["code"], r["name"], r["unit"], r["source"])
        a = agg.setdefault(k, {"dates": [], "qty": 0, "billed": 0.0, "lines": 0})
        a["dates"].append(r["date"]); a["qty"] += r["qty"]; a["billed"] += float(r["billed"]); a["lines"] += 1
    out = ["| Date (2026) | Code | Name (catalog) | Qty | Unit TL | Billed TL | Source (row in force) |", "|---|---|---|---|---|---|---|"]
    for (code, name, unit, src), a in agg.items():
        is_drug = src == "EK-4A"
        unit_s = "TBD (Q4)" if is_drug else fmt(unit)
        billed_s = "TBD (Q4)" if is_drug else fmt(a["billed"])
        q = f"{a['qty']}" + (f" ({a['lines']} lines)" if a["lines"] > 1 else "")
        src_s = src.replace("valid_from", "from")
        if is_drug:
            src_s = "EK-4A " + KAMU.get(code, "") + " from 2025-04-26"
        out.append(f"| {dates(a['dates'])} | {code} | {name} | {q} | {unit_s} | {billed_s} | {src_s} |")
    return "\n".join(out)

for s in ["S1","S2","S3","S4","S5","S6","S7","S8"]:
    d = json.load(open(os.path.join(HERE, "results", f"{s}.json")))
    with open(os.path.join(HERE, "results", f"{s}_tables.md"), "w", encoding="utf-8") as fh:
        for v in ("clean", "faulty"):
            fh.write(f"### {s} {v} — total {fmt(d[v]['total_billed'])} TL (drugs excluded)\n\n")
            fh.write(table(d[v]["rows"]) + "\n\n")
print("ok")
