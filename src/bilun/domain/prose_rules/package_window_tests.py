"""Logged examinations and tests that an EK-2/C package already pays (SUT §2.2.2.B-1, #290).

§2.2.2.B-1(1) (C000685-C000699): "Tanıya dayalı ödeme listesi işlem puanlarına yatarak tedaviler kapsamında takip
alındıktan sonraki, özel hükümler saklı kalmak kaydıyla; ... b) Muayeneler ve konsültasyonlar, ... ğ) Laboratuvar,
patoloji ve radyoloji tetkikleri, ... gibi tanı ve tedavi kapsamında yapılan tüm işlemler dahil olup ayrıca
faturalandırılamaz." (3) (C000701-C000706) counts the package's days from its procedure date (A 15, B 10, C 8, D 5,
E 3) and (4) (C000707) bills what comes after them; (2) (C000700): "SUT eki EK-2/C Listesi 'Açıklama' bölümünde
belirtilen istisnalar dikkate alınacaktır."

So on a yatarak claim (an inpatient stay or a day case, C003484) whose package has an işlem grubu
(``yatak_puani.claim_islem_grubu_package_window``: a billed package or one that must be billed, §2.2.2(1)), an
examination or a test logged from the admission through the window's last day is inside the package: the EMR/OR/PACS
and lab-feed capture gaps report no "performed, not submitted" row for it and price nothing from EK-2/B.

What counts as an examination or a test is read from the EK-2/B list's own headings (the 2026-01-31 and 2026-07-07
lists; ``tests/unit/domain/prose_rules/test_package_window_tests.py`` re-reads the raw lists' heading rows):

- examinations: the muayene and konsültasyon codes of "2. HEKİM MUAYENELERİ VE RAPORLAR" (its reports and the
  remote evaluation 520032 are no examination);
- laboratory: "9. LABORATUVAR İŞLEMLERİ" with 9.1, 9.2, 9.A, 9.B, 9.C and 9.E; pathology: "9.D. PATOLOJİ";
- radiology tests: the imaging headings of 8.2 (every system heading and "Diğer İncelemeler", not "Radyonüklid
  Tedavi"), of 8.3 ("Direkt Grafiler", "Kontrastlı tetkikler", "Anjiyografik tetkikler", "Kemik dansitometresi",
  "Ultrasonografik tetkikler", "Renkli Doppler incelemeleri", not the two "girişimsel radyolojik tedavi" headings),
  of 8.3.1 BT and of 8.3.2 MRG (not their "Kılavuzluğunda Girişimsel İşlemler").

Not inside, so the gap stays as before: a package without an işlem grubu (ICU days, dialysis ...) and an outpatient
claim (the clause is "yatarak"); a day before the admission; a day after the window; an undated lab result on a stay
that runs past the window; a code §2.2.2.A(5)/B(3) prices by session (``session_scope``: e.g. catheter angiography,
whose EK-2/C heading bills 25 % of it next to a therapeutic catheterisation), which may be billed beside the package;
radiotherapy (8.1), the radionuclide and interventional treatments and every other operation or intervention, whose
session reading is open (``session_scope``); the THSK reference laboratory list (10), another provider's; and a test
the package's EK-2/C açıklama bills apart (C000700, ``billed_apart_tests``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from .catalog_membership import get_ek2c_description, normalize_procedure_code
from .claim_utils import claim_is_day_case, infer_care_setting
from .session_scope import is_session_operation_code
from .yatak_puani import claim_islem_grubu_package_window

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

EXAM = "exam"
LAB = "lab"
PATHOLOGY = "pathology"
RADIOLOGY = "radiology"
# Narrower kinds an EK-2/C açıklama names: "BT" (the abbreviation of the heading 8.3.1 BİLGİSAYARLI TOMOGRAFİ (BT))
# and "genetik tetkikler" (9.B SİTOGENETİK TETKİKLER, 9.C MOLEKÜLER GENETİK TETKİKLER).
CT = "ct"
GENETIC = "genetic"
# An açıklama that bills some other test apart, or names its test unclearly: no test is inside that package.
EVERY_TEST = "every_test"

# "2. HEKİM MUAYENELERİ VE RAPORLAR": the muayene and konsültasyon codes (b) names.
_EXAM_CODES = frozenset({"520010", "520020", "520021", "520030", "520070", "520080", "520090"})

# (first code, last code, kinds) of the EK-2/B headings that list tests, in list order.
_TEST_BLOCKS: tuple[tuple[str, str, frozenset[str]], ...] = (
    # 8.2 NÜKLEER TIP GÖRÜNTÜLEME VE TEDAVİ: "Solunum Sistemi" .. "Nükleer Onkoloji"; "Diğer İncelemeler".
    ("800620", "801440", frozenset({RADIOLOGY})),
    ("801550", "801557", frozenset({RADIOLOGY})),
    # 8.3 RADYOLOJİK GÖRÜNTÜLEME VE TEDAVİ: "A-Direkt Grafiler" .. "Venografik tetkikler"; "D-Kemik dansitometresi";
    # "F-Ultrasonografik tetkikler", "G-Renkli Doppler incelemeleri".
    ("801561", "802720", frozenset({RADIOLOGY})),
    ("802900", "802911", frozenset({RADIOLOGY})),
    ("803310", "803861", frozenset({RADIOLOGY})),
    # 8.3.1 BİLGİSAYARLI TOMOGRAFİ (BT) through "BT Anjiyografiler"; 8.3.2 MRG through "MRG Anjiyografiler".
    ("R100000", "R101510", frozenset({RADIOLOGY, CT})),
    ("R103000", "R104780", frozenset({RADIOLOGY})),
    # 9. LABORATUVAR İŞLEMLERİ and 9.A MOLEKÜLER MİKROBİYOLOJİ; 9.D PATOLOJİ; 9.E MESLEK HASTALIKLARI LABORATUVAR
    # TETKİKLERİ; 9.1 BİYOKİMYA and 9.2 YASADIŞI VE KÖTÜYE KULLANILAN MADDE ANALİZLERİ; 9.B and 9.C (genetics).
    ("901980", "908339", frozenset({LAB})),
    ("909210", "911260", frozenset({PATHOLOGY})),
    ("911290", "911441", frozenset({LAB})),
    ("L100000", "L120360", frozenset({LAB})),
    ("G100000", "G101984", frozenset({LAB, GENETIC})),
)
_CODE_SHAPE = re.compile(r"[A-Z]?\d{6}")

# C000700: an açıklama part that bills something apart ("ayrıca faturalandırılır" / "ayrıca ödenir") or excepts it
# ("hariç"); "ayrıca faturalandırılmaz" and "ayrıca ödenmez" say the opposite. Parts are split at . ; , and lines.
# A Doppler test is "renkli Doppler" or "Doppler US" (8.3 G): P700811's "Doppler teli" is a wire.
_BILLED_APART = re.compile(r"ayrıca\s+(?:faturalandırılır|faturalandırılabilir|ödenir)\b|\bhariç", re.IGNORECASE)
_TEST_WORDS = re.compile(
    r"tetkik|tahlil|laboratuvar|patoloji|radyoloji|görüntüleme|grafi|röntgen|x-?ray|\bBT\b|\bMRG?\b|sintigrafi"
    r"|\bPET\b|ultrason|\bUSG\b|renkli\s+doppler|doppler\s+(?:us|usg|ultrason|inceleme)|genetik",
    re.IGNORECASE,
)
_PARTS = re.compile(r"[.;,\n]")


def package_test_kinds(procedure_code: str) -> frozenset[str]:
    """The examination or test kinds of an EK-2/B code (module docstring); empty for any other code."""
    code = normalize_procedure_code(procedure_code).upper()
    if code in _EXAM_CODES:
        return frozenset({EXAM})
    if not _CODE_SHAPE.fullmatch(code):
        return frozenset()
    for first, last, kinds in _TEST_BLOCKS:
        if first <= code <= last:  # by the shape above a letter code sorts after every numeric block
            return kinds
    return frozenset()


def billed_apart_kinds(aciklama: str) -> frozenset[str]:
    """The test kinds an EK-2/C açıklama bills apart (C000700).

    A part that bills apart only "BT" is ``CT``, only "genetik tetkik(ler)" is ``GENETIC``; any other test word in
    such a part (or a "hariç" next to one, e.g. "X-ray hariç") is ``EVERY_TEST``.
    """
    kinds: set[str] = set()
    for part in _PARTS.split(aciklama):
        if not _BILLED_APART.search(part):
            continue
        words = {word.casefold() for word in _TEST_WORDS.findall(part)}
        if not words:
            continue
        if words == {"bt"}:
            kinds.add(CT)
        elif "genetik" in words and words <= {"genetik", "tetkik"}:
            kinds.add(GENETIC)
        else:
            kinds.add(EVERY_TEST)
    return frozenset(kinds)


def billed_apart_tests(package_code: str, *, as_of_date: date | str | None = None) -> frozenset[str]:
    """``billed_apart_kinds`` of the package's EK-2/C açıklama in force on that date. In the 2026 lists: P615010 and
    P615030 "BT ayrıca faturalandırılır", P619950 "Prenatal genetik tetkikler ayrıca faturalandırılır", P614990 and
    P615000 "X-ray hariç ...".
    """
    return billed_apart_kinds(get_ek2c_description(package_code, as_of_date=as_of_date))


@dataclass(frozen=True)
class PackageTestWindow:
    """The days of a yatarak claim whose examinations and tests its EK-2/C package pays.

    ``first_day`` is the admission (the claim's first day when it has none), ``last_day`` the package window's last
    day, ``stay_last_day`` the discharge (the claim's last day); ``billed_apart`` the kinds an açıklama of its
    packages bills apart.
    """

    first_day: date
    last_day: date
    stay_last_day: date
    packages: tuple[str, ...]
    billed_apart: frozenset[str] = frozenset()

    def covers(self, procedure_code: str, day: date | None) -> bool:
        """Whether the package pays ``procedure_code`` done on ``day``; an undated row (a lab result without a
        date) only when the whole stay lies in the window."""
        kinds = package_test_kinds(procedure_code)
        if not kinds or EVERY_TEST in self.billed_apart or kinds & self.billed_apart:
            return False
        if is_session_operation_code(procedure_code):
            return False
        if day is None:
            return self.stay_last_day <= self.last_day
        return self.first_day <= day <= self.last_day


def package_test_window(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
) -> PackageTestWindow | None:
    """The claim's ``PackageTestWindow``, or ``None`` off a yatarak claim or without an işlem grubu package."""
    if infer_care_setting(claim) != "inpatient" and not claim_is_day_case(claim):
        return None
    procs = [line for line in claim_procs if line.claim_id == claim.claim_id]
    window = claim_islem_grubu_package_window(claim, procs)
    if window is None:
        return None
    billed_apart = frozenset().union(*(
        billed_apart_tests(line.procedure_code, as_of_date=line.procedure_date or claim.admission_date)
        for line in window.lines
    ))
    return PackageTestWindow(
        first_day=claim.admission_date or claim.claim_start_date,
        last_day=window.end,
        stay_last_day=claim.discharge_date or claim.claim_end_date,
        packages=tuple(normalize_procedure_code(line.procedure_code) for line in window.lines),
        billed_apart=billed_apart,
    )
