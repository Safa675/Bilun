"""One vocabulary for ``ClaimHeader.claim_type``, read by every rule-engine reader (Safa675/Bilun#335).

A claim's ``claim_type`` carries one of two MEDULA fields (docs/medula/medula_capabilities.md §1.3, §1.4):
the treatment type (tedavi türü: ayaktan, yatan, günübirlik) or the provision ground the takip was opened
on (provizyon tipi: acil, koruyucu sağlık, meslek hastalığı; SUT 1.7, C000192, C000193, C000196). A raw
value is folded once (``fold_claim_type``: case, Turkish letters, spaces and hyphens, so "Günübirlik" is
``gunubirlik`` and "Acil Servis" is ``acil_servis``) and looked up as a whole value, never as a substring.

The care setting of each type, from the SUT corpus (``data/gazette/sut_clauses.parquet``):

- ``yatis`` (yatış, yatan, yatarak, inpatient): inpatient. "yatış tarihinden taburcu işlemi yapılıncaya
  kadar uygulanan tedavi" (2.1.2.A, C000490).
- ``poliklinik`` (ayakta, ayaktan, outpatient): outpatient. Care given "yatırılmaksızın" is ayakta tedavi
  (2.1.1, C000482).
- ``gunubirlik`` (günübirlik, günübirlik yatış, day_case): read as outpatient with the day-case flag
  (``is_day_case``), as the engine read the ``gunubirlik`` spelling before #335 (``day_case`` fell to the
  inpatient default, "günübirlik" was not a day case at all). SUT counts it as yatarak tedavi "yatış ve
  taburcu işlemi yapılmadan" (2.1.2.B, C000492; C003484), so the payment-method reader applies the
  yatarak rules to a day case and the two bed motors (``yatak_puani``, ``yenidogan_yatak``) its bed rules
  (§2.2.2.(4), C000649), through ``claim_utils.claim_is_day_case``.
- ``acil`` (acil servis, emergency): outpatient, billed fee for service. An emergency-department service
  is given without admission (2.1.1, C000482); SUT lists "Acil sağlık hizmetleri" among the ayakta
  tedaviler billed "hizmet başına ödeme yöntemi ile" (2.2.1.B-2(2)(a), C000607, C000617), calls them
  "ayaktan acil müracaat" (C006357) and excepts them from the rules of the other outpatient visits
  ("acil servise başvuruları hariç", C000573, C000587). An admission from the emergency department ends
  the emergency (1.9.1(6), C000416): it is a ``yatis`` claim. Two authored gap-closing rules name the
  emergency department as a care setting of its own, ``EMERGENCY_CARE_SETTING`` (1.8.5.(5) "acil
  servislerde verilen sağlık hizmetleri", C000370; 1.9.1.(6) "acil servislerde 24 saat içinde
  stabilizasyonu", C000416): an ``acil`` claim is in it (``is_emergency``) and stays outpatient for every
  other reader. No other type is placed in it, whatever its department: an admission or a polyclinic claim
  may carry services given in the emergency department that the header does not show.
- ``koruyucu`` (koruyucu sağlık, preventive): no care setting. A provision ground (1.7, C000196) whose
  services range from a vaccine (2.4.3-A..D) to a circumcision (2.4.3-F, a day case under anaesthesia,
  2.1.2.B(1)(c)); the type does not say whether the patient was admitted.
- ``meslek_hastaligi`` (meslek hastalığı, occupational disease): no care setting. A provision ground
  (1.7, C000193) treated as an outpatient or an inpatient; the fee-for-service reading of 2.2.1.B-2(2)(c)
  (C000609) holds at an occupational-disease hospital only, which the header does not carry.

A reader that needs the care setting leaves a claim of the last two types, and of an unknown type,
``unavailable`` (``care_setting_gap``) instead of guessing one.
"""

from __future__ import annotations

import unicodedata
from typing import Literal

ClaimTypeKind = Literal["yatis", "poliklinik", "gunubirlik", "acil", "koruyucu", "meslek_hastaligi"]
CareSetting = Literal["inpatient", "outpatient"]
CareSettingGap = Literal["missing", "unrecognized", "not_settled"]

# Folded spellings of each type: the ASCII and Turkish forms, the SUT's own names of the treatment
# categories (2.1.1 "Ayakta tedaviler", 2.1.2 "Yatarak tedaviler", 2.1.2.A "Yatan hasta tedavisi",
# 2.1.2.B "Günübirlik tedavi") and the English names the engine already used.
_SPELLINGS: dict[ClaimTypeKind, frozenset[str]] = {
    "yatis": frozenset(
        {
            "yatis",
            "yatan",
            "yatarak",
            "inpatient",
            "yatan_hasta",
            "yatan_hasta_tedavisi",
            "yatarak_tedavi",
        }
    ),
    "poliklinik": frozenset(
        {"poliklinik", "ayakta", "ayaktan", "outpatient", "ayakta_tedavi", "ayaktan_tedavi"}
    ),
    "gunubirlik": frozenset(
        {"gunubirlik", "gunubirlik_tedavi", "gunubirlik_yatis", "day_case", "daycase"}
    ),
    "acil": frozenset({"acil", "acil_servis", "emergency", "emergency_department"}),
    "koruyucu": frozenset({"koruyucu", "koruyucu_saglik", "preventive", "preventive_health"}),
    "meslek_hastaligi": frozenset({"meslek_hastaligi", "occupational_disease"}),
}
_KIND_BY_SPELLING: dict[str, ClaimTypeKind] = {
    spelling: kind for kind, spellings in _SPELLINGS.items() for spelling in spellings
}

# The emergency-department setting a rule may name beside inpatient and outpatient: ``acil`` only.
EMERGENCY_CARE_SETTING = "emergency"

CARE_SETTING_BY_KIND: dict[ClaimTypeKind, CareSetting | None] = {
    "yatis": "inpatient",
    "poliklinik": "outpatient",
    "gunubirlik": "outpatient",
    "acil": "outpatient",
    "koruyucu": None,
    "meslek_hastaligi": None,
}


def fold_claim_type(value: object) -> str:
    """Case- and Turkish-fold a header value; spaces and hyphens become ``_``."""
    folded = unicodedata.normalize("NFKD", str(value or "").casefold().replace("ı", "i"))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return "_".join(folded.replace("-", " ").split())


def claim_type_kind(value: object) -> ClaimTypeKind | None:
    """The type a raw ``claim_type`` spells, or None for a blank or unknown value."""
    return _KIND_BY_SPELLING.get(fold_claim_type(value))


def claim_type_care_setting(value: object) -> CareSetting | None:
    """The care setting the SUT gives the type; None when the type has none or is unknown."""
    kind = claim_type_kind(value)
    return None if kind is None else CARE_SETTING_BY_KIND[kind]


def care_setting_gap(value: object) -> CareSettingGap | None:
    """Why no care setting can be read from ``value``; None when one can.

    ``missing``: the value is blank. ``unrecognized``: it spells no type of the vocabulary.
    ``not_settled``: a known type the SUT gives no care setting (``koruyucu``, ``meslek_hastaligi``).
    """
    if not fold_claim_type(value):
        return "missing"
    kind = claim_type_kind(value)
    if kind is None:
        return "unrecognized"
    return "not_settled" if CARE_SETTING_BY_KIND[kind] is None else None


def is_day_case(value: object) -> bool:
    """True for a günübirlik (day-case) claim type, in any spelling."""
    return claim_type_kind(value) == "gunubirlik"


def is_emergency(value: object) -> bool:
    """True for an emergency-department claim type (``acil``), in any spelling.

    It is the one type in ``EMERGENCY_CARE_SETTING``.
    """
    return claim_type_kind(value) == "acil"
