"""Twenty-two showcase stories: clean bill + one injected fault each, except S32, S39 and S48 (S1-S8 a scratch draft, S9, S10, S11, S12, S14, S22, S39 and S40 added 2026-10-21, S32, S20, S47, S48, S33 and S34 on 2026-10-22).

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

from src.bilun.domain.claims.models import MedulaRejectionEvent

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


# ── S10 ─ the manual haematocrit billed beside the hemogram; MEDULA rejects it as a duplicate ──
def s10(variant: str) -> Bill:
    """58 M, melena; ER visit on 2026-05-09 (acil, Acil Tıp): the examination and a blood count.

    The first bill of the patient of S22. The hemogram L107020 is the whole blood count (its result set carries
    the haematocrit); the faulty bill also bills the manual haematocrit L103120, a CBC component billed twice
    (claim_lab.py, #270), and MEDULA has rejected that line with 0901, a duplicate procedure on one day
    (data/medula/rejection_playbook.json). The clean bill has neither the line nor the rejection. The ER bill
    bills no other test, so that the admission two days later (S22) repeats only the blood count.
    """
    day = D("2026-05-09")
    b = Bill("SH-12", "C-SH10", "acil", "Acil Tıp", None, None, "K92.1", start=day, end=day)
    b.diag("K92.1", primary=True, on=day)
    b.proc("520020", day, specialty=ACIL)
    b.proc("L107020", day, specialty=ACIL)
    if variant != "clean":                                # the fault, and the rejection it drew
        lid = b.proc("L103120", day, specialty=ACIL)
        b.medula.append(MedulaRejectionEvent(
            rejection_event_id="C-SH10-RED1", claim_id=b.cid, patient_id=b.pid, episode_id=b.episode,
            medula_stage="fatura_kayit", sonuc_kodu="0901", hata_kodu="",
            hata_mesaji="Mükerrer işlem: aynı gün tekrar faturalandırma", rejection_timestamp=day,
            related_procedure_code="L103120", related_procedure_line_id=lid,
            related_line_type="procedure", related_line_id=lid))
    return b


# ── S22 ─ the polypectomy of a colonoscopy session not billed ──────────────────
def s22(variant: str) -> Bill:
    """58 M, the patient of S10: admitted to general surgery on 2026-05-11 for a second melena, 2 nights.

    A colonoscopy on day 2 (701450) with the polypectomy through it (701460): the later procedure of a session
    is paid at 30 % (the same incision) or 50 % (another) of its list amount (SUT 2.2.2.A(5), C000659 to C000661),
    and the engine expects the add-on beside every colonoscopy (procedure_addon_uplift.py, which cannot know
    whether a polyp existed). The clean bill bills the polypectomy at 50 % (at 100 % the engine shows an audit
    exposure; at 30 % a session review), the faulty bill leaves it out. The ER bill of S10 is the history of this
    bill: the blood count of the admission day repeats one of it within seven days (Tablo 15 #12), a row the
    clean bill shows too. Companion on both nights; no drug line (drug prices stay 0 in the demo).
    """
    a, d = D("2026-05-11"), D("2026-05-13")
    b = Bill("SH-12", "C-SH22", "yatis", "Genel Cerrahi", a, d, "K92.2")
    b.history = (s10("faulty"),)
    b.diag("K92.2", primary=True)
    b.diag("D50.0")
    b.diag("D12.6", on=a + timedelta(days=1))             # found by the colonoscopy
    _beds(b, a, d, GENCER)
    _companion(b, a, d, GENCER)                           # 2 nights
    b.proc("L107020", a, specialty=GENCER)                # the blood count of the admission day
    day = a + timedelta(days=1)
    b.proc("701450", day, specialty=GENCER)               # colonoscopy, total
    if variant == "clean":                                # the polypectomy through the scope, 50 % of its list amount
        lid = b.proc("701460", day, specialty=GENCER)
        i = [p.procedure_line_id for p in b.procs].index(lid)
        p = b.procs[i]
        billed = money(p.unit_price_try * p.quantity * Decimal("0.5"))
        b.procs[i] = replace(p, billed_amount_try=billed, expected_payable_try=billed)
    return b


# ── S20 ─ a day-case package billed itemized ────────────────────────────────
def s20(variant: str) -> Bill:
    """41 M, umbilical hernia; graftless repair as a day case (gunubirlik), 2026-06-17, general surgery.

    A day case is inpatient care (C003484), so the EK-2C code goes by package (C000646): the clean bill bills
    P603840 alone (no day bed, C000649; no companion, C000650), the faulty one the EK-2B operation 603840 with
    its anaesthesia: one operation of 3228.38 puan is group C on both band tables (550170).
    """
    day = D("2026-06-17")
    b = Bill("SH-13", "C-SH20", "gunubirlik", "Genel Cerrahi", None, None, "K42.9",
             package_candidate=True, start=day, end=day)
    b.diag("K42.9", primary=True, on=day)
    if variant == "clean":
        b.proc("P603840", day, specialty=GENCER)
    else:  # the coder keyed the EK-2B operation and its anaesthesia instead of the package
        b.proc("603840", day, specialty=GENCER)
        b.proc("550170", day, specialty=ANEST)
    return b


# ── S47 ─ the day bed of a stay under 24 hours not billed ───────────────────
def s47(variant: str) -> Bill:
    """58 F, the patient of S7: syncope six days after the ER visit; ER observation under 24 hours, 2026-02-25.

    A stay of one date (admission and discharge on 02-25): its bed is the day bed 510120 (C000648), which the
    faulty bill leaves out. The troponin and the D-dimer repeat tests of S7's ER bill within seven days: the
    duplicate-test rule flags them on this bill, clean and faulty alike. S7's bill is its history.
    """
    day = D("2026-02-25")
    b = Bill("SH-07", "C-SH47", "yatis", "Acil Tıp", day, day, "R55")
    b.history = (s7("faulty"),)
    for i, icd in enumerate(("R55", "R07.1")):
        b.diag(icd, primary=(i == 0))
    if variant == "clean":
        b.proc("510120", day, specialty=ACIL)           # the day bed of a stay under 24 hours
    b.proc("520010", day, specialty=ACIL)               # the examination of a stay
    b.proc("530100", day, specialty=ACIL)               # ECG
    _labs(b, day, ("L107360", "L102090"), ACIL)         # troponin I, D-dimer
    return b


# ── S48 ─ the chest-disease follow-up of the patient of S7 (a clean bill) ──
def s48(variant: str) -> Bill:
    """58 F, the patient of S7: chest-disease follow-up three weeks after the ER visit, 2026-03-12, outpatient.

    A clean bill (CLEAN_ONLY). The ER visit of S7 and the observation of S47 are its history; another branch and
    more than ten days later, so no duplicate-exam window applies, and no test is billed.
    """
    if variant != "clean":
        raise ValueError("S48 is a clean bill: it has no faulty variant")
    day = D("2026-03-12")
    b = Bill("SH-07", "C-SH48", "poliklinik", "Göğüs Hastalıkları", None, None, "R07.1", start=day, end=day)
    b.history = (s7("faulty"), s47("faulty"))
    for i, icd in enumerate(("R07.1", "R06.0")):
        b.diag(icd, primary=(i == 0), on=day)
    b.proc("520030", day, specialty=GOGUS)              # the visit
    b.proc("801720", day, specialty=RAD)                # control chest X-ray PA
    return b


# ── S32 ─ the control visit three weeks after the discharge of S2, with the chronic health report (a clean bill) ──
def s32(variant: str) -> Bill:
    """81 M, the patient of S2: control visit after the COPD exacerbation, 2026-04-06, chest diseases, outpatient.

    A clean bill: it has no fault, so there is no faulty variant (CLEAN_ONLY). The examination carries the
    patient's share of the visit, modelled as 20 % (the copay flag, rate 0.20: SGK pays 80 % of the line). The
    patient's chronic health report is on file (a fact of his copay profile, not of the bill), so the EK-1/A
    exemption (SUT 1.8.5.(7)) waives that share: a patient benefit, not a fault. The stay of S2 (2026-03-09 to
    03-15) is its history; it is itemized, so no package period (C000714) applies. No test is billed.
    """
    if variant != "clean":
        raise ValueError("S32 is a clean bill: it has no faulty variant")
    day = D("2026-04-06")
    b = Bill("SH-02", "C-SH32", "poliklinik", "Göğüs Hastalıkları", None, None, "J44.0", start=day, end=day)
    b.history = (s2("faulty"),)
    for i, icd in enumerate(("J44.0", "I10")):
        b.diag(icd, primary=(i == 0), on=day)
    lid = b.proc("520030", day, specialty=GOGUS)          # the visit, with the patient's share
    i = [p.procedure_line_id for p in b.procs].index(lid)
    p, rate = b.procs[i], Decimal("0.20")
    b.procs[i] = replace(p, copay_rate_applicable=True, copay_rate=rate,
                         expected_payable_try=money(p.billed_amount_try * (1 - rate)))
    return b


# ── S33 ─ the readmission of the patient of S2 through the ER: the enoxaparin strength keyed as the count ──
def s33(variant: str) -> Bill:
    """81 M, the patient of S2: readmitted through the ER on 2026-04-20 with a COPD exacerbation and acute respiratory
    failure; followed on the ER's critical bed that day and admitted to chest diseases, 3 nights, itemized.

    The clean bill gives four enoxaparin syringes (one 40 mg syringe a day, the discharge morning included); the faulty
    one keys the strength of the syringe (4000 anti-Xa IU) as the count, 4000 syringes: a parenteral dose belongs in
    the service detail, price and count go by box/unit (C008282, SUT 5.3.1.C(i); El Kitabı Tablo 15 #11). Drug prices
    enter at 0 TL, so the fault has no money. The stay of S2 and the control of S32 are its history.
    """
    a, d = D("2026-04-20"), D("2026-04-23")
    b = Bill("SH-02", "C-SH33", "yatis", "Göğüs Hastalıkları", a, d, "J44.1")
    b.history = (s2("faulty"), s32("clean"))
    for i, icd in enumerate(("J44.1", "J96.0", "I10")):
        b.diag(icd, primary=(i == 0))
    b.proc("530000", a, specialty=ACIL)             # the ER's critical bed on the day of arrival
    b.proc("520010", a, specialty=GOGUS)            # the chest-disease consultation that admits him
    _beds(b, a, d, GOGUS)                           # 4 lines, 20-23 April
    _companion(b, a, d, GOGUS)                      # 3 nights
    b.drug(CLEXANE, a, qty=4 if variant == "clean" else 4000, unit="syringe", per_box=10)
    return b


# ── S34 ─ the control after the readmission: the examination flagged as a package component (vakabaşı) ──
def s34(variant: str) -> Bill:
    """81 M, the patient of S2: control visit six days after the discharge of S33, 2026-04-29, chest diseases.

    S33 is itemized, so no package period (C000714) covers the control: its examination is billed per visit
    (C000572, SUT 2.2.1.B-1.(1)). The faulty bill marks the examination as a component of a package (vakabaşı,
    El Kitabı Tablo 15 #3); the flag moves no money. The three earlier bills of the patient are its history. No test.
    """
    day = D("2026-04-29")
    b = Bill("SH-02", "C-SH34", "poliklinik", "Göğüs Hastalıkları", None, None, "J44.1", start=day, end=day)
    b.history = (s2("faulty"), s32("clean"), s33("faulty"))
    for i, icd in enumerate(("J44.1", "I10")):
        b.diag(icd, primary=(i == 0), on=day)
    b.proc("520030", day, specialty=GOGUS, is_package_included=(variant != "clean"))
    return b


# ── S39 ─ the control visit nine days after the discharge of S4 (a clean bill) ──
def s39(variant: str) -> Bill:
    """86 F, the patient of S4: control visit after the pyelonephritis, 2026-05-25, internal medicine, outpatient.

    A clean bill: it has no fault, so there is no faulty variant (CLEAN_ONLY). The patient's stay (S4, 2026-05-11
    to 05-16) is its history. S4 is billed itemized, so no package period (C000714) applies. The tests are the
    four of S4's admission panel that a control repeats (blood count, creatinine, urinalysis) and the urine
    culture; S4's last ones were 12 days earlier, outside the seven-day window of the duplicate-test rule.
    """
    if variant != "clean":
        raise ValueError("S39 is a clean bill: it has no faulty variant")
    day = D("2026-05-25")
    b = Bill("SH-04", "C-SH39", "poliklinik", "İç Hastalıkları", None, None, "N10", start=day, end=day)
    b.history = (s4("faulty"),)
    for i, icd in enumerate(("N10", "G30.1", "I10")):
        b.diag(icd, primary=(i == 0), on=day)
    b.proc("520030", day, specialty=DAHILIYE)             # the visit
    _labs(b, day, ("L107020", "L104780", "L107010"), DAHILIYE)
    b.proc("905671", day, specialty=DAHILIYE)             # urine culture
    return b


# ── S40 ─ the examination fee of a second visit to the same branch within 10 days ──
def s40(variant: str) -> Bill:
    """86 F, the patient of S4: second visit a week after the control (S39), low-grade fever, urinary ultrasound.

    The control of S39 (2026-05-25) and this visit (2026-06-01) are two outpatient applications to internal
    medicine within 10 days: the examination fee of the second one is not payable (C000573, Tablo 15 #2), so
    the clean bill bills the ultrasound only and the faulty one also the examination 520030. Both earlier bills
    of the patient are its history: the cross-bill rule reads them. No lab line: a test of the control would
    be a duplicate within seven days (Tablo 15 #12).
    """
    day = D("2026-06-01")
    b = Bill("SH-04", "C-SH40", "poliklinik", "İç Hastalıkları", None, None, "N10", start=day, end=day)
    b.history = (s4("faulty"), s39("clean"))
    for i, icd in enumerate(("N10", "G30.1", "I10")):
        b.diag(icd, primary=(i == 0), on=day)
    if variant != "clean":                                # the fault: the fee of the second visit
        b.proc("520030", day, specialty=DAHILIYE)
    b.proc("803580", day, specialty=RAD)                  # urinary system ultrasound
    return b


# Stories without a fault: a clean bill has a clean golden, no faulty golden and no proof.
CLEAN_ONLY: tuple[str, ...] = ("S32", "S39", "S48")

STORIES = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6, "S7": s7, "S8": s8, "S9": s9, "S10": s10, "S11": s11, "S12": s12, "S14": s14, "S20": s20, "S22": s22, "S32": s32, "S33": s33, "S34": s34, "S39": s39, "S40": s40, "S47": s47, "S48": s48}
