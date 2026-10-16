"""Which claim lines form a §2.2.2.A(5) / §2.2.2.B(3) same-session procedure set.

SUT §2.2.2.A(5) (C000659–C000662) prices several işlemler done in one session by
incision: the highest-point one in full, the others at 30 % (aynı kesi) or 50 %
(ayrı kesi), +25 points across specialties; only EK-2/Ç is excluded. §2.2.2.B(3)
(C000669–C000674) does the same for tanıya dayalı işlemler (EK-2/C packages).
A session holds the procedures these clauses price (Safa675/Bilun#261):

- EK-2/B §6 CERRAHİ UYGULAMALAR codes (600000–629999);
- every EK-2/C tanıya dayalı işlem package, i.e. a package with an işlem grubu
  (A1–E), and the EK-2/B code with the same number: pacemaker/ICD, catheter
  angiography and PCI (SUT 2.4.4.E(2), C000993), ERCP, RFT, transplants and
  the other non-§6 packages;
- the EK-2/B §7/§8 codes SGK's Fatura İnceleme guide prices under §2.2.2.A(5):
  endoscopic biliary and GİS procedures (F000066, F000067, and the
  ``procedure_pairing_prose.json`` A(5) pairs) and interventional radiology
  (F000155, F000156, F000157).

Not procedures in this sense, so never session lines: beds and companion (§1),
visits (§2), anaesthesia (§5), labs and pathology (§9), and the per-day EK-2/C
care packages that have no işlem grubu (ICU days, palliative care, dialysis,
FTR, hyperbaric and psychiatric day care, home care). Intraoperative
neuromonitoring (P703365, SUT 2.4.4.M(1), C001389) and neuronavigation (P614981,
2.4.4.Ö(1), C001413) are billed "2.2.2.B (3) ... kurallar uygulanmaksızın", so they
are never session lines either; whether they are payable next to their EK-2/D-4 /
D-5 procedure is the EK-2/D gate's (``conditional_addon_ek2d``). Other interventional
EK-2/B codes outside §6 (e.g. the incisional §3 port, tunnelled or PD catheter,
surgical biopsy and excision codes) and the remaining §7/§8 interventions are
not in scope yet: the clauses do not exclude them, and the include list is
pending Safa's decision.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from typing import TYPE_CHECKING

import polars as pl

from ..constants import EK2C_CURATED_HISTORY_PATH
from .catalog_membership import normalize_procedure_code

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ProcedureClaimLine

_SURGERY_CODE_MIN = 600000
_SURGERY_CODE_MAX = 629999
_ISLEM_GROUPS = ("A1", "A2", "A3", "B", "C", "D", "E")

# EK-2/B codes outside §6 that SGK's Fatura İnceleme guide prices under
# §2.2.2.A(5)/B(3) when billed together (their EK-2/C namesakes are covered by
# the package rule).
_SGK_GUIDE_SESSION_CODES = frozenset({
    # GENEL CERRAHİ-1 (F000066): ERCP-related biliary procedures.
    "701300", "701320", "701360", "701370", "701440",
    # GENEL CERRAHİ-2 (F000067): colonoscopy and upper GİS endoscopy.
    "701450", "701540",
    # procedure_pairing_prose.json A(5) pairs: endoscopic polypectomy, biopsy,
    # foreign-body removal, mucosal resection and GİS stent.
    "701400", "701410", "701411", "701430", "701460", "701530", "701545", "701550",
    # RADYOLOJİ-3/4/5 (F000155–F000157): stent, PTA, nephrostomy, biliary.
    "802780", "802830", "803050", "803120", "803150", "803240", "803250", "803270",
})

# Billed without the §2.2.2.B(3) rules next to the operation they accompany:
# neuromonitoring (C001389) and neuronavigation (C001413).
_BILLED_WITHOUT_SESSION_RULES = frozenset({"703365", "614981"})


@lru_cache(maxsize=1)
def _procedure_package_codes() -> frozenset[str]:
    """EK-2/C codes that carry an işlem grubu (A1–E) in any catalog version."""
    if not EK2C_CURATED_HISTORY_PATH.exists():
        return frozenset()
    codes = (
        pl.read_parquet(EK2C_CURATED_HISTORY_PATH, columns=["package_code", "group"])
        .filter(pl.col("group").str.strip_chars().is_in(_ISLEM_GROUPS))
        .get_column("package_code")
        .str.strip_chars()
        .str.replace(r"^[Pp]", "")
        .unique()
        .to_list()
    )
    return frozenset(code for code in codes if code)


def is_session_operation_code(procedure_code: str) -> bool:
    """True for a procedure that §2.2.2.A(5) / §2.2.2.B(3) prices by session."""
    code = normalize_procedure_code(procedure_code)
    if not code or code in _BILLED_WITHOUT_SESSION_RULES:
        return False
    if len(code) == 6 and code.isdigit() and _SURGERY_CODE_MIN <= int(code) <= _SURGERY_CODE_MAX:
        return True
    return code in _SGK_GUIDE_SESSION_CODES or code in _procedure_package_codes()


def session_operation_lines(
    lines: Iterable[ProcedureClaimLine],
) -> list[ProcedureClaimLine]:
    """The lines of one session that §2.2.2.A(5) / §2.2.2.B(3) price together."""
    return [line for line in lines if is_session_operation_code(line.procedure_code)]


def line_billed_as_package(line: ProcedureClaimLine) -> bool:
    """A line billed as an EK-2/C package (tanıya dayalı işlem), not hizmet başı.

    The package category or a MEDULA package code (``P`` prefix) marks it.
    MEDULA has no "paket" service type, so every consumer reads this predicate,
    never the category alone. A bare "P" is no code at all.
    """
    if line.procedure_category == "paket":
        return True
    code = str(line.procedure_code or "").strip()
    return code[:1] in ("P", "p") and bool(normalize_procedure_code(code))
