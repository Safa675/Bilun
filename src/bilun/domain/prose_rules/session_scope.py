"""Which claim lines form a §2.2.2.A(5) / §2.2.2.B(3) same-session procedure set.

SUT §2.2.2.A(5) (C000659–C000662) prices several işlemler in one session by
incision: the highest-point one in full, the others at 30 % (aynı kesi) or 50 %
(ayrı kesi), +25 points across specialties, EK-2/Ç excluded; §2.2.2.B(3) does the
same for EK-2/C packages. The EK-2/B §5 note takes these reduced totals from
"yapılan cerrahi işlemlerin (Aynı veya ayrı kesiden yapılan işlemlerin indirimli
toplam puanları, %100+%50+....veya %100+%30...)". A session therefore holds only
EK-2/B §6 CERRAHİ UYGULAMALAR codes (600000–629999) and the EK-2/C packages with
the same code, the scope #230 uses for anaesthesia (Safa675/Bilun#261).

Never session lines: beds and companion (§1), visits (§2), ER and general
interventions such as nebuliser or IV line (§3), anaesthesia (§5), non-OR medical
procedures such as endoscopy and catheterisation (§7), imaging (§8), lab and
pathology (§9), blood components, ICU day packages (P552xxx) and EK-2/Ç dental
codes (40xxxx).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from .catalog_membership import normalize_procedure_code

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ProcedureClaimLine

_SURGERY_CODE_MIN = 600000
_SURGERY_CODE_MAX = 629999


def is_session_operation_code(procedure_code: str) -> bool:
    """True for an EK-2/B §6 surgical code or the EK-2/C package with that code."""
    code = normalize_procedure_code(procedure_code)
    return (
        len(code) == 6
        and code.isdigit()
        and _SURGERY_CODE_MIN <= int(code) <= _SURGERY_CODE_MAX
    )


def session_operation_lines(
    lines: Iterable[ProcedureClaimLine],
) -> list[ProcedureClaimLine]:
    """The lines of one session that §2.2.2.A(5) / §2.2.2.B(3) price together."""
    return [line for line in lines if is_session_operation_code(line.procedure_code)]
