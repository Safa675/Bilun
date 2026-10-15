"""Eight showcase stories: clean bill + one injected fault each (scratch draft).

Facility: one SGK-contracted private hospital, facility_tier=2_3_basamak_ozel,
provider_type=Ozel (accepted values: src/bilun/domain/prose_rules/facility_tier.py:26-30).
All EK-2B/EK-2C codes, names and prices are read from the curated history in
force on each line date (harness.catalog_row fails loudly otherwise).
Drug prices are TBD (Q4) and enter the engine at 0 TL.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from harness import Bill, D, money

# EK-2A branch codes (data/gazette/curated/ek2a_outpatient_visits.parquet)
ACIL, ANEST, BEYIN, GENCER, GOGUS, DAHILIYE, NORO, ORTO, RAD = (
    "4400", "3100", "2400", "1900", "1171", "1000", "1300", "2600", "3300")


def _days(a, b):
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def _beds(b: Bill, a, d, spec: str, skip_last: int = 0, only_first: int | None = None) -> None:
    """One 510010 line per calendar day, admission..discharge inclusive (engine convention)."""
    days = _days(a, d)
    if only_first is not None:
        days = days[:only_first]
    elif skip_last:
        days = days[:-skip_last]
    for day in days:
        b.proc("510010", day, specialty=spec)


def _companion(b: Bill, a, d, spec: str) -> None:
    """One 510121 line per night (admission IN, discharge OUT; refakatci.py:154)."""
    for day in _days(a, d)[:-1]:
        b.proc("510121", day, specialty=spec)


def _labs(b: Bill, day, codes, spec: str) -> None:
    for code in codes:
        b.proc(code, day, specialty=spec)


ADMIT_PANEL = ("L107020", "L101850", "L102890", "L104780", "L107420", "L106910", "L106150", "L100300", "L101280")


# ── S1 ─ package vs itemized ────────────────────────────────────────────────
def s1(variant: str) -> Bill:
    """34 M, acute appendicitis; laparoscopic appendectomy after ER admission."""
    a, op, d = D("2026-07-14"), D("2026-07-14"), D("2026-07-16")
    b = Bill("SH-01", "C-SH01", "yatis", "Genel Cerrahi", a, d, "K35.8", package_candidate=True)
    b.diag("K35.8", primary=True)
    if variant == "clean":
        # Package only: bed, anaesthesia, labs, pathology, drugs and companion are
        # inside P610131 for the C-group 8-day window (SUT §2.2.2.B-1(1),(3)).
        b.proc("P610131", op, specialty=GENCER)
    else:  # whole stay billed hizmet başı (EK-2B) instead of the EK-2C package
        b.proc("610131", op, specialty=GENCER)
        b.proc("550170", op, specialty=ANEST)
        _beds(b, a, d, GENCER)
        _labs(b, op, ("L107020", "L101850"), GENCER)
        _labs(b, op + timedelta(days=1), ("L107020", "L101850"), GENCER)
        b.proc("910230", op + timedelta(days=1), specialty=GENCER)
        b.drug("IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU", op, barkod="8699508270224", qty=3)
        b.drug("NEOFLEKS %0,5 METRONIDAZOL I.V. ENJ COZ 100 ML (SETLI)", op, barkod="8697637691743", qty=6)
        b.drug("PARACEROL 10 MG/ML IV INF ICIN COZ ICEREN 100 ML 12 FLK", op, barkod="8699606694649", qty=1)
    return b


# ── S2 ─ bed days under-billed ──────────────────────────────────────────────
def s2(variant: str) -> Bill:
    """81 M, COPD with acute lower respiratory infection + pneumonia; 6 nights."""
    a, d = D("2026-03-09"), D("2026-03-15")
    b = Bill("SH-02", "C-SH02", "yatis", "Gogus Hastaliklari", a, d, "J44.0")
    for i, icd in enumerate(("J44.0", "J18.9", "I10")):
        b.diag(icd, primary=(i == 0))
    if variant == "clean":
        _beds(b, a, d, GOGUS)                       # 7 lines, 9–15 March
    else:
        _beds(b, a, d, GOGUS, only_first=4)         # bed charge stopped after 12 March
    _companion(b, a, d, GOGUS)                      # 6 nights, doctor's order (81 y, COPD)
    _labs(b, a, ADMIT_PANEL + ("L103900", "L106240"), GOGUS)
    b.proc("906020", a, specialty=GOGUS)            # blood culture
    b.proc("905675", a, specialty=GOGUS)            # sputum culture
    b.proc("801720", a, specialty=RAD)              # chest X-ray PA
    b.proc("530350", a, qty=18, specialty=GOGUS)    # nebulizer 3/day x 6 days (one line)
    b.proc("530360", a, qty=48, specialty=GOGUS)    # O2, hourly, first 48 h
    _labs(b, a + timedelta(days=3), ("L107020", "L101850", "L103900"), GOGUS)
    b.proc("801720", a + timedelta(days=4), specialty=RAD)
    b.drug("IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU", a, barkod="8699508270224", qty=7)
    b.drug("IPRAVENT 0.5MG/2.5ML + 2.5MG/2.5ML NEBULIZAYON ICIN INHALASYON COZELITISI (20 FLAKON)", a, barkod="8680741521174", qty=1)
    return b


# ── S3 ─ anaesthesia line missing on an itemized operation ──────────────────
def s3(variant: str) -> Bill:
    """77 F (ASA 2), lumbar spinal stenosis; unilateral decompression 615931 (EK-2B only)."""
    a, op, d = D("2026-08-18"), D("2026-08-18"), D("2026-08-20")
    b = Bill("SH-03", "C-SH03", "yatis", "Beyin ve Sinir Cerrahisi", a, d, "M48.0")
    for i, icd in enumerate(("M48.0", "I10")):
        b.diag(icd, primary=(i == 0))
    b.proc("615931", op, specialty=BEYIN)
    if variant == "clean":
        b.proc("550160", op, specialty=ANEST)
    _beds(b, a, d, BEYIN)
    _companion(b, a, d, BEYIN)                      # post-op fall risk, doctor's order
    _labs(b, op + timedelta(days=1), ("L107020", "L104780"), BEYIN)
    b.drug("PARACEROL 10 MG/ML IV INF ICIN COZ ICEREN 100 ML 12 FLK", op, barkod="8699606694649", qty=1)
    return b


# ── S4 ─ companion bed not billed ───────────────────────────────────────────
def s4(variant: str) -> Bill:
    """86 F, Alzheimer dementia + delirium, acute pyelonephritis; 5 nights."""
    a, d = D("2026-05-11"), D("2026-05-16")
    b = Bill("SH-04", "C-SH04", "yatis", "Ic Hastaliklari", a, d, "N10")
    for i, icd in enumerate(("N10", "F05.1", "G30.1", "I10")):
        b.diag(icd, primary=(i == 0))
    _beds(b, a, d, DAHILIYE)
    if variant == "clean":
        _companion(b, a, d, DAHILIYE)               # daughter stayed; doctor's order
    _labs(b, a, ADMIT_PANEL + ("L107010",), DAHILIYE)
    b.proc("905671", a, specialty=DAHILIYE)         # urine culture
    b.proc("906020", a, specialty=DAHILIYE)         # blood culture
    _labs(b, a + timedelta(days=2), ("L107020", "L101850", "L104780"), DAHILIYE)
    b.drug("IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU", a, barkod="8699508270224", qty=5)
    b.drug("PARACEROL 10 MG/ML IV INF ICIN COZ ICEREN 100 ML 12 FLK", a, barkod="8699606694649", qty=1)
    return b


# ── S5 ─ implant billed without ÜTS notification ────────────────────────────
STEM = ("AP2070", "KALÇA | PRİMER | FEMORAL STEM | ÇİMENTOSUZ | CoCr/TİTANYUM | KAPLAMALI - KUMLAMA", 12630.993375)
HEAD = ("AP1880", "KALÇA | PRİMER | FEMORAL BIPOLAR BAŞ ( SHELL + İNSERT) | TÜM BOYLAR | CoCr", 5391.8865)


def s5(variant: str) -> Bill:
    """84 F, femoral neck fracture after a fall at home; bipolar hemiarthroplasty."""
    a, op, d = D("2026-09-03"), D("2026-09-04"), D("2026-09-08")
    b = Bill("SH-05", "C-SH05", "yatis", "Ortopedi ve Travmatoloji", a, d, "S72.0", package_candidate=True)
    for i, icd in enumerate(("S72.0", "I10", "M81.0")):
        b.diag(icd, primary=(i == 0))
    pkg = b.proc("P612320", op, specialty=ORTO)
    src = "EK-3F-1 (Yür. 13.12.2025, consolidated SUT 2026-10-02; curated ek3f1_arthroplasty_materials)"
    b.mat(STEM[0], STEM[1], op, float(money(STEM[2])), proc_line_id=pkg, specialty_category="EK-3F-1",
          titubb_registered=True, uts_registered=(variant == "clean"), source=src)
    b.mat(HEAD[0], HEAD[1], op, float(money(HEAD[2])), proc_line_id=pkg, specialty_category="EK-3F-1",
          titubb_registered=True, uts_registered=True, source=src)
    return b


# ── S6 ─ drug indication not coded ──────────────────────────────────────────
PKMERZ = ("PK-MERZ IV INF. COZ. 2x500 ML", "8699708690525")


def s6(variant: str) -> Bill:
    """79 M, advanced Parkinson disease, aspiration pneumonia + dysphagia; IV amantadine."""
    a, d = D("2026-06-08"), D("2026-06-14")
    b = Bill("SH-06", "C-SH06", "yatis", "Ic Hastaliklari", a, d, "J69.0")
    icds = ("J69.0", "R13", "G20", "I10") if variant == "clean" else ("J69.0", "R13", "I10")
    for i, icd in enumerate(icds):
        b.diag(icd, primary=(i == 0))
    _beds(b, a, d, DAHILIYE)
    _companion(b, a, d, DAHILIYE)
    _labs(b, a, ADMIT_PANEL, DAHILIYE)
    b.proc("906020", a, specialty=DAHILIYE)
    b.proc("801720", a, specialty=RAD)
    b.proc("520010", a, specialty=NORO)             # neurology consultation
    _labs(b, a + timedelta(days=3), ("L107020", "L101850"), DAHILIYE)
    b.proc("801720", a + timedelta(days=4), specialty=RAD)
    b.drug("IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU", a, barkod="8699508270224", qty=7)
    b.drug("NEOFLEKS %0,5 METRONIDAZOL I.V. ENJ COZ 100 ML (SETLI)", a, barkod="8697637691743", qty=21)
    b.drug(PKMERZ[0], a + timedelta(days=1), barkod=PKMERZ[1], qty=2,
           drug_specialty_board_report_present=True, prescriber_specialty="İç Hastalıkları",
           drug_inpatient_supply=True)
    return b


# ── S7 ─ ER: CT angiography performed but not billed ────────────────────────
def s7(variant: str) -> Bill:
    """58 F, pleuritic chest pain + dyspnoea after a long flight; PE ruled out; ER only."""
    day = D("2026-02-19")
    b = Bill("SH-07", "C-SH07", "acil", "Acil Tip", None, None, "R07.1", start=day, end=day)
    for i, icd in enumerate(("R07.1", "R06.0")):
        b.diag(icd, primary=(i == 0), on=day)
    b.proc("520020", day, specialty=ACIL)
    b.proc("530100", day, specialty=ACIL)           # ECG
    b.proc("530080", day, specialty=ACIL)           # IV line
    _labs(b, day, ("L107020", "L107360", "L102090", "L104780", "L102890", "L106910", "L106150"), ACIL)
    b.proc("L107360", day, specialty=ACIL)          # repeat troponin I at 3 h
    b.proc("801720", day, specialty=RAD)            # chest X-ray PA
    if variant == "clean":
        b.proc("R101450", day, specialty=RAD)       # CT pulmonary angiography
    for code in ("530100", "530080", "801720", "R101450"):
        b.perf(code, day, source="emr" if code != "R101450" else "pacs")
    b.drug("OMNIPAQUE 350 MGL/ML 100 ML FLK", day, barkod="8699688771559", qty=1)
    b.drug("PARACEROL 10 MG/ML IV INF ICIN COZ ICEREN 100 ML 12 FLK", day, barkod="8699606694649", qty=1)
    return b


# ── S8 ─ second operation in the same session billed at full points ─────────
def s8(variant: str) -> Bill:
    """47 F, symptomatic gallstones + small umbilical hernia; lap chole + hernia repair via umbilical port."""
    a, op, d = D("2026-09-15"), D("2026-09-15"), D("2026-09-16")
    b = Bill("SH-08", "C-SH08", "yatis", "Genel Cerrahi", a, d, "K80.2", package_candidate=True)
    for i, icd in enumerate(("K80.2", "K42.9")):
        b.diag(icd, primary=(i == 0))
    b.proc("P609235", op, specialty=GENCER)
    lid = b.proc("P603840", op, specialty=GENCER)
    factor = Decimal("0.25") if variant == "clean" else Decimal("1")
    i = [p.procedure_line_id for p in b.procs].index(lid)
    p = b.procs[i]
    billed = money(p.unit_price_try * p.quantity * factor)  # unit = SUT list price; amount after §2.2.2.B(3)(a)
    b.procs[i] = replace(p, billed_amount_try=billed, expected_payable_try=billed)
    return b


STORIES = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6, "S7": s7, "S8": s8}
