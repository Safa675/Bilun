"""Side checks for defects reported in the draft (read-only)."""
import json
from harness import Bill, D, run_engine
from stories import s1
from src.bilun.domain.prose_rules.drg_unbundling import analyze_claim_unbundling
from src.bilun.domain.prose_rules.anestezi_puani import detect_anestezi_puani_opportunities

# 1. S1 faulty audit exposure decomposition
ctx = s1("faulty").ctx()
f = analyze_claim_unbundling(ctx.claims[0], list(ctx.procedure_lines), same_incision=True)
pm = sum(v["risk_amount_try"] for v in f.payment_method_violations)
se = sum(v["risk_amount_try"] for v in f.session_violations)
print("S1 faulty audit exposure: payment-method", round(pm, 2), "| session", round(se, 2), "| lines", [(v["procedure_code"], v["risk_amount_try"]) for v in f.session_violations])

# 2. Hemogram unbundling false positive: CBC + HbA1c same day
b = Bill("SH-X9", "C-X9", "yatis", "Ic Hastaliklari", D("2026-08-03"), D("2026-08-05"), "E11.9")
b.diag("E11.9", primary=True)
for code in ("L107020", "L102820", "L106650"):
    b.proc(code, D("2026-08-03"))
rep, _ = run_engine(b.ctx())
print("hemogram check:", rep.lab.flagged_tests)

# 3. Anaesthesia band switch date: 615995 (puan 5113) on 2026-05-10, hospital billed group C (new band since 16/04/2026)
b = Bill("SH-X10", "C-X10", "yatis", "Beyin ve Sinir Cerrahisi", D("2026-05-10"), D("2026-05-11"), "M48.06")
b.diag("M48.06", primary=True)
b.proc("615995", D("2026-05-10")); b.proc("550170", D("2026-05-10"))
c = b.ctx()
print("band check 2026-05-10:", [(o["procedure_puan"], o["anestezi_group"], o["anestezi_code"], o["expected_try"], o["actual_billed_try"], o["recoverable_uplift_try"]) for o in detect_anestezi_puani_opportunities(list(c.claims), list(c.procedure_lines))])
b2 = Bill("SH-X11", "C-X11", "yatis", "Beyin ve Sinir Cerrahisi", D("2026-07-20"), D("2026-07-21"), "M48.06")
b2.diag("M48.06", primary=True)
b2.proc("615995", D("2026-07-20")); b2.proc("550170", D("2026-07-20"))
c2 = b2.ctx()
print("band check 2026-07-20:", [(o["procedure_puan"], o["anestezi_group"], o["anestezi_code"], o["expected_try"], o["actual_billed_try"], o["recoverable_uplift_try"]) for o in detect_anestezi_puani_opportunities(list(c2.claims), list(c2.procedure_lines))])

# 17. S8 clean: time-overlap row present?
HERE = "/tmp/claude-1000/-home-safa-Documents-Bilun/a9cf6beb-cd1a-4613-ab9e-bddecbe1db1a/scratchpad/showcase_stories"
d = json.load(open(f"{HERE}/results/S8.json"))
print("S8 clean validate rows:", sorted({x[2] for x in d["noise_in_clean"] if x[0] == "validate"}))
d7 = json.load(open(f"{HERE}/results/S7.json"))
print("S7 clean validate rows:", sorted({str(x[2]) for x in d7["noise_in_clean"] if x[0] == "validate"}))
