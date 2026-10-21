"""Twelve showcase stories: clean bill + one injected fault each (S1-S8 a scratch draft, S9, S11, S12 and S14 added 2026-10-21; S10 is a later bill).

Facility: one SGK-contracted private hospital, facility_tier=2_3_basamak_ozel,
provider_type=Ozel (accepted values: src/bilun/domain/prose_rules/facility_tier.py:26-30).
All EK-2B/EK-2C codes, names and prices are read from the curated history in
force on each line date, EK-3/F-1 materials from the curated list and drug names
from the EK-4A row in force (harness.catalog_row / material_row / drug_row fail
loudly otherwise). Drug prices are TBD (Q4) and enter the engine at 0 TL.
Drug quantities count what was used (vials, bottles, syringes, tablets); a part
box is whole units at box price / units per box, because DrugClaimLine.quantity
is an int (MEDULA records the decimal box fraction).
Corrections of the 2026-10-16 review: reports/synthetic-data/2026-10-16-v3-drafts-review.md.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from harness import Bill, D, money

# EK-2A branch codes (data/gazette/curated/ek2a_outpatient_visits.parquet)
ACIL, ANEST, BEYIN, GENCER, GOGUS, DAHILIYE, NORO, ORTO, RAD, COCUK, NEONATOLOJI = (
    "4400", "3100", "2400", "1900", "1171", "1000", "1300", "2600", "3300", "1500", "1561")

# EK-4A barcodes (data/gazette/curated/ek4a_history.parquet; ingredient from the drug crosswalk)
IESEF = "8699508270224"       # IESEF 1 G IV (seftriakson), 1 vial
METRONIDAZOL = "8697637691743"  # NEOFLEKS %0,5 METRONIDAZOL 100 ML (500 mg)
PARTEMOL = "8699844770716"    # PARTEMOL 1 G/100 ML, 1 vial (parasetamol)
PARACEROL = "8699606694649"   # PARACEROL 10 MG/ML 100 ML, 12 vials (parasetamol)
IPRAVENT = "8680741521174"    # IPRAVENT nebules, 20 vials (ipratropium + salbutamol)
PREDNOL_L = "8699541791007"   # PREDNOL-L 40 MG 1 AMP (metilprednizolon)
KLACID_IV = "8699548270482"   # KLACID 500 MG IV 1 FLK (clarithromycin)
CLEXANE = "8699809950696"     # CLEXANE 4000 ANTI-XA IU/0.4 ML, 10 syringes (enoksaparin)
EQIZOLIN = "8699814270253"    # EQIZOLIN 1 GR IM/IV 1 FLK (cefazolin)
NACL_1000 = "8697637690128"   # NEOFLEKS %0,9 SODYUM KLORUR 1000 ML (SETLI)
PKMERZ = "8699708690525"      # PK-MERZ IV INF. COZ. 2x500 ML (amantadin sülfat)
MADOPAR = "8699525094841"     # MADOPAR 125 MG 30 TB (levodopa + benserazid)


def _days(a, b):
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def _beds(b: Bill, a, d, spec: str, skip_last: int = 0, only_first: int | None = None) -> None:
    """One 510010 line per calendar day, admission..discharge inclusive (Kılavuz p.62, p.168)."""
    days = _days(a, d)
    if only_first is not None:
        days = days[:only_first]
    elif skip_last:
        days = days[:-skip_last]
    for day in days:
        b.proc("510010", day, specialty=spec)


def _companion(b: Bill, a, d, spec: str) -> None:
    """One 510121 line per night; the refakatçi belgesi covers these days (refakatci.py counts nights)."""
    for day in _days(a, d)[:-1]:
        b.proc("510121", day, specialty=spec)


def _labs(b: Bill, day, codes, spec: str) -> None:
    for code in codes:
        b.proc(code, day, specialty=spec)


ADMIT_PANEL = ("L107020", "L101850", "L102890", "L104780", "L107420", "L106910", "L106150", "L100300", "L101280")
NA_K = ("L106910", "L106150")  # not billed with the blood gas L103900 (EK-2B açıklama)


# ── S1 ─ package vs itemized ────────────────────────────────────────────────
def s1(variant: str) -> Bill:
    """34 M, acute appendicitis; laparoscopic appendectomy after ER admission."""
    a, op, d = D("2026-07-14"), D("2026-07-14"), D("2026-07-16")
    b = Bill("SH-01", "C-SH01", "yatis", "Genel Cerrahi", a, d, "K35.9", package_candidate=True)
    b.diag("K35.9", primary=True)
    if variant == "clean":
        # Package only: bed, anaesthesia, labs, pathology, drugs and companion are
        # inside P610131 for the C-group 8-day window (SUT §2.2.2.B-1(1),(3)).
        b.proc("P610131", op, specialty=GENCER)
    else:  # the coder keyed the EK-2B code: whole stay hizmet başı instead of the EK-2C package
        b.proc("610131", op, specialty=GENCER)
        b.proc("550170", op, specialty=ANEST)
        _beds(b, a, d, GENCER)
        # 07-14 CBC/CRP were drawn in the ER (its own acil takip); the ward repeats them on 07-15.
        _labs(b, op + timedelta(days=1), ("L107020", "L101850"), GENCER)
        b.proc("910230", op + timedelta(days=1), specialty=GENCER)
        # One pre-operative dose, none after (WSES 2020, uncomplicated appendicitis).
        b.drug(IESEF, op, qty=1, unit="vial")
        b.drug(METRONIDAZOL, op, qty=1, unit="bottle")
        b.drug(PARTEMOL, op, qty=5, unit="vial")
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
    _companion(b, a, d, GOGUS)                      # 6 nights, doctor's order + refakatçi belgesi
    _labs(b, a, tuple(c for c in ADMIT_PANEL if c not in NA_K) + ("L103900", "L106240"), GOGUS)
    b.proc("906020", a, qty=2, specialty=GOGUS)     # two blood-culture sets
    b.proc("905675", a, specialty=GOGUS)            # sputum culture
    b.proc("801720", a, specialty=RAD)              # chest X-ray PA
    for day in _days(a, d)[:-1]:                    # "Günde bir adet faturalandırılır": 6 lines
        b.proc("530350", day, specialty=GOGUS)
    for day in _days(a, a + timedelta(days=1)):     # "Günlük en fazla 16 saat ödenir": 2 x 16 h
        b.proc("530360", day, qty=16, specialty=GOGUS)
    _labs(b, a + timedelta(days=3), ("L107020", "L101850", "L103900"), GOGUS)
    b.proc("801720", a + timedelta(days=4), specialty=RAD)
    b.drug(IESEF, a, qty=7, unit="vial")
    b.drug(KLACID_IV, a, qty=10, unit="vial")       # 500 mg bid x 5 days (ATS/IDSA 2019)
    b.drug(PREDNOL_L, a, qty=5, unit="ampoule")     # 40 mg/day x 5 days (GOLD)
    b.drug(IPRAVENT, a, qty=1)
    b.drug(CLEXANE, a, qty=6, unit="syringe", per_box=10)  # 40 mg/day, 6 days
    return b


# ── S3 ─ anaesthesia line missing on an itemized operation ──────────────────
def s3(variant: str) -> Bill:
    """77 F (ASA 2), lumbar spinal stenosis; unilateral decompression 615931 (EK-2B only)."""
    a, op, d = D("2026-08-18"), D("2026-08-18"), D("2026-08-20")
    b = Bill("SH-03", "C-SH03", "yatis", "Beyin ve Sinir Cerrahisi", a, d, "M48.06")
    for i, icd in enumerate(("M48.06", "I10")):
        b.diag(icd, primary=(i == 0))
    b.proc("615931", op, specialty=BEYIN)
    if variant == "clean":
        b.proc("550160", op, specialty=ANEST)
    _beds(b, a, d, BEYIN)
    _companion(b, a, d, BEYIN)                      # post-op fall risk, doctor's order + belge
    _labs(b, op + timedelta(days=1), ("L107020", "L104780"), BEYIN)
    b.drug(EQIZOLIN, op, qty=2, unit="vial")        # cefazolin 2 g once before incision (ASHP 2013)
    b.drug(PARTEMOL, op, qty=6, unit="vial")
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
        _companion(b, a, d, DAHILIYE)               # daughter stayed; doctor's order + belge
    _labs(b, a, ADMIT_PANEL + ("L107010",), DAHILIYE)
    b.proc("905671", a, specialty=DAHILIYE)         # urine culture
    b.proc("906020", a, qty=2, specialty=DAHILIYE)  # two blood-culture sets
    b.proc("803580", a, specialty=RAD)              # urinary system ultrasound
    _labs(b, a + timedelta(days=2), ("L107020", "L101850", "L104780"), DAHILIYE)
    b.drug(IESEF, a, qty=10, unit="vial")           # ceftriaxone 2 g/day x 5 days (EAU)
    b.drug(PARACEROL, a, qty=1)
    b.drug(CLEXANE, a, qty=5, unit="syringe", per_box=10)
    return b


# ── S5 ─ implant billed without ÜTS notification ────────────────────────────
STEM, HEAD, CEMENT = "AP2000", "AP1880", "AP3220"  # cemented polished steel stem, bipolar head, 40 g cement


def s5(variant: str) -> Bill:
    """84 F, femoral neck fracture after a fall at home; cemented bipolar hemiarthroplasty."""
    a, op, d = D("2026-09-03"), D("2026-09-04"), D("2026-09-08")
    b = Bill("SH-05", "C-SH05", "yatis", "Ortopedi ve Travmatoloji", a, d, "S72.00", package_candidate=True)
    for i, icd in enumerate(("S72.00", "W19", "I10", "M81.09")):
        b.diag(icd, primary=(i == 0))
    pkg = b.proc("P612320", op, specialty=ORTO)
    b.mat(STEM, op, proc_line_id=pkg, titubb_registered=True, uts_registered=(variant == "clean"))
    b.mat(HEAD, op, proc_line_id=pkg, titubb_registered=True, uts_registered=True)
    b.mat(CEMENT, op, qty=2, proc_line_id=pkg, material_type="consumable",
          titubb_registered=True, uts_registered=True)
    return b


# ── S6 ─ drug indication not coded ──────────────────────────────────────────
def s6(variant: str) -> Bill:
    """79 M, advanced Parkinson disease, aspiration pneumonia + dysphagia; IV amantadine bridge."""
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
    b.proc("530100", a, specialty=DAHILIYE)         # ECG: baseline QT before amantadine
    b.proc("520010", a, specialty=NORO)             # neurology consultation
    b.proc("530340", a + timedelta(days=2), specialty=DAHILIYE)  # NG tube, day 3
    _labs(b, a + timedelta(days=3), ("L107020", "L101850"), DAHILIYE)
    b.proc("801720", a + timedelta(days=4), specialty=RAD)
    b.drug(IESEF, a, qty=7, unit="vial")
    b.drug(NACL_1000, a, qty=3, unit="bag")         # 1000 ml a day, days 1-3 (nil by mouth)
    b.drug(CLEXANE, a, qty=6, unit="syringe", per_box=10)
    b.drug(PKMERZ, a + timedelta(days=1), qty=3, unit="bottle", per_box=2,
           drug_specialty_board_report_present=True, prescriber_specialty="İç Hastalıkları",
           drug_inpatient_supply=True)              # one 500 ml bottle a day, days 2-4
    b.drug(MADOPAR, a + timedelta(days=2), qty=20, unit="tablet", per_box=30)  # via NG, days 3-7
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
    b.proc("L107360", day, specialty=ACIL)          # repeat troponin I at 2 h (ESC 2023 0/2 h)
    b.proc("801720", day, specialty=RAD)            # chest X-ray PA
    if variant == "clean":
        b.proc("R101450", day, specialty=RAD)       # CT pulmonary angiography; contrast inside it
    for code in ("530100", "530080", "801720", "R101450"):
        b.perf(code, day, source="emr" if code != "R101450" else "pacs")
    b.drug(PARTEMOL, day, qty=1, unit="vial")
    return b


# ── S8 ─ second operation in the same session billed at full points ─────────
def s8(variant: str) -> Bill:
    """47 F, symptomatic gallstones + umbilical hernia (defect < 1 cm); repair through the umbilical port."""
    a, op, d = D("2026-09-15"), D("2026-09-15"), D("2026-09-16")
    b = Bill("SH-08", "C-SH08", "yatis", "Genel Cerrahi", a, d, "K80.2", package_candidate=True)
    for i, icd in enumerate(("K80.2", "K42.9")):
        b.diag(icd, primary=(i == 0))
    b.proc("P609235", op, specialty=GENCER)
    # MEDULA ayniFarkliKesi = 1 (aynı seans + aynı kesi) on this line; the claim model has no
    # such field, so the list unit price and the 25 % billed amount carry it.
    lid = b.proc("P603840", op, specialty=GENCER)
    factor = Decimal("0.25") if variant == "clean" else Decimal("1")
    i = [p.procedure_line_id for p in b.procs].index(lid)
    p = b.procs[i]
    billed = money(p.unit_price_try * p.quantity * factor)  # unit = SUT list price; amount after §2.2.2.B(3)(a)
    b.procs[i] = replace(p, billed_amount_try=billed, expected_payable_try=billed)
    return b


# ── S9 ─ second operation of the session billed at 25 % instead of 50 % ──────
def s9(variant: str) -> Bill:
    """77 F (ASA 2), lumbar spinal stenosis; unilateral decompression 615931 and minimal-invasive
    foraminoplasty 615995 in one session through two incisions (EK-2B only, same branch)."""
    a, op, d = D("2026-09-21"), D("2026-09-21"), D("2026-09-23")
    b = Bill("SH-09", "C-SH09", "yatis", "Beyin ve Sinir Cerrahisi", a, d, "M48.06")
    for i, icd in enumerate(("M48.06", "I10")):
        b.diag(icd, primary=(i == 0))
    b.proc("615931", op, specialty=BEYIN)
    lid = b.proc("615995", op, specialty=BEYIN)
    # SUT 2.2.2.A(5): the later operation of a session is paid at 30 % (same incision) or 50 %
    # (separate incision) of its list amount. The claim model has no incision field: the billed
    # amount carries it. Clean: separate incision, 50 %. Faulty: 25 %, the package rate, keyed by mistake.
    factor = Decimal("0.5") if variant == "clean" else Decimal("0.25")
    i = [p.procedure_line_id for p in b.procs].index(lid)
    p = b.procs[i]
    billed = money(p.unit_price_try * p.quantity * factor)
    b.procs[i] = replace(p, billed_amount_try=billed, expected_payable_try=billed)
    # Two operations in the session: one multiple-operation anaesthesia line by the total puan
    # (6471.03 + 5113.00 = 11584.03, group A3 from 9001 on 2026-04-16 and from 7584 before).
    b.proc("550220", op, specialty=ANEST)
    _beds(b, a, d, BEYIN)
    _companion(b, a, d, BEYIN)                      # post-op fall risk, doctor's order + belge
    _labs(b, op + timedelta(days=1), ("L107020",), BEYIN)
    b.drug(EQIZOLIN, op, qty=2, unit="vial")        # cefazolin 2 g once before incision (ASHP 2013)
    b.drug(PARTEMOL, op, qty=6, unit="vial")
    return b


# ── S11 ─ ICU package days billed at half the price ──────────────────────────
def s11(variant: str) -> Bill:
    """76 F, urosepsis with septic shock; 5 nights in a medical ICU, second-level (P552002) package days.

    SUT 2.4.4.H.(8): 510090 on the first and on the last ICU day, the EK-2/C package on the days between.
    The ICU days are discharge - admission (icu_puani.py), so the discharge day is the transfer day and
    carries no ICU line. No ward bed, no companion, no drug line (drug prices stay 0 in the demo).
    """
    a, d = D("2026-06-02"), D("2026-06-07")
    b = Bill("SH-11", "C-SH11", "yatis", "Yoğun Bakım", a, d, "A41.9")
    for i, icd in enumerate(("A41.9", "R57.8", "N39.0")):
        b.diag(icd, primary=(i == 0))
    b.proc("510090", a, specialty=DAHILIYE)
    package_days = [b.proc("P552002", day, specialty=DAHILIYE) for day in _days(a + timedelta(days=1), d - timedelta(days=2))]
    b.proc("510090", d - timedelta(days=1), specialty=DAHILIYE)
    if variant != "clean":  # the coder keyed half the package price on each of the three days
        for lid in package_days:
            i = [p.procedure_line_id for p in b.procs].index(lid)
            p = b.procs[i]
            billed = money(p.unit_price_try * p.quantity * Decimal("0.5"))
            b.procs[i] = replace(p, billed_amount_try=billed, expected_payable_try=billed)
    _labs(b, a, ("L107020", "L101850", "L106240", "L104890"), DAHILIYE)
    b.proc("906020", a, qty=2, specialty=DAHILIYE)  # two blood-culture sets
    b.proc("905671", a, specialty=DAHILIYE)         # urine culture
    b.proc("803580", a, specialty=RAD)              # urinary system ultrasound
    return b


# ── S12 ─ incubator days billed on 3 of 6 days ──────────────────────────────
def s12(variant: str) -> Bill:
    """Boy born 2026-07-10 at about 35 weeks, neonatal jaundice; 5 nights in the incubator on the neonatal ward.

    EK-2B 510070 (Kuvöz) is billed once a day, the discharge day included (yenidogan_yatak.py counts
    discharge - admission + 1 days). The bill has no laboratory, drug or procedure line beside the paediatric
    consultation and the companion: laboratory reference ranges are adult (lab_reference.csv).
    """
    a, d = D("2026-07-10"), D("2026-07-15")
    b = Bill("SH-12", "C-SH12", "yatis", "Yenidoğan", a, d, "P07.3")
    for i, icd in enumerate(("P07.3", "P59.9", "Z38.0")):
        b.diag(icd, primary=(i == 0))
    days = _days(a, d)
    for day in days if variant == "clean" else days[3:]:  # the faulty bill lost the first three days
        b.proc("510070", day, specialty=NEONATOLOJI)
    _companion(b, a, d, NEONATOLOJI)                      # 5 nights
    b.proc("520010", a, specialty=COCUK)                  # paediatric consultation on the admission day
    return b


# ── S14 ─ ward bed billed on the day the patient leaves intensive care ──────
def s14(variant: str) -> Bill:
    """76 F, the ward bill of the patient of S11 after her transfer out of the ICU; 3 nights on internal medicine.

    The ICU bill (S11, 2026-06-02 to 06-07) is this patient's history: its 510090 pays the day she leaves
    (EK-2B 510090 covers yemek, yatak, vizit), so the clean ward bill bills 510010 from the next day and the
    faulty one from the transfer day too (src/bilun/domain/prose_rules/yatak_icu_overlap.py). The companion
    covers every night of the bill. No lab, drug or material line: the cross-bill rules read the whole history.
    """
    a, d = D("2026-06-07"), D("2026-06-10")
    b = Bill("SH-11", "C-SH14", "yatis", "İç Hastalıkları", a, d, "A41.9")
    b.history = (s11("faulty"),)
    for i, icd in enumerate(("A41.9", "N39.0")):
        b.diag(icd, primary=(i == 0))
    days = _days(a, d)
    for day in days if variant != "clean" else days[1:]:  # the faulty bill also bills the transfer day
        b.proc("510010", day, specialty=DAHILIYE)
    _companion(b, a, d, DAHILIYE)                         # 3 nights
    return b


STORIES = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6, "S7": s7, "S8": s8, "S9": s9, "S11": s11, "S12": s12, "S14": s14}
