"""Stable source identities for §1.8 copay compositor trace metadata.

Clause IDs are extraction-order keys and move when the SUT corpus is rebuilt.
Use coordinate-plus-content identities here; the generic Gate B writer resolves
them against the current in-force corpus before emitting trace IDs.

Only clauses with a corresponding runtime path are listed. In particular,
§1.8.5(21)'s time-bounded injury pathway and §1.8.5(22)(b)'s benefit groups are
not in the patient-status compositor and remain outside its trace mapping.
"""

from __future__ import annotations

COMPOSITOR_CLAUSE_TRACE_KEYS: dict[str, tuple[str, ...]] = {
    "copay_exemption_ek1a": ("1.8.5.(7)#fb187fbe",),
    "copay_exemption_ek4d": (
        "1.8.2.(3)#04043a39",
        "1.8.5.(8)#2c30921a",
    ),
    "copay_exemption_visit_type": (
        "1.8.5.(5)#424f9787",
        "1.8.5.(6)#989e2ee8",
    ),
    "copay_exemption_occupational": ("1.8.5.(1)#27612764",),
    "copay_exemption_patient_status": (
        "1.8.5.(11)#4c5d2bce",
        "1.8.5.(12)#b67e143b",
        "1.8.5.(13)#3697a89c",
        "1.8.5.(15)#05de89cd",
        "1.8.5.(16)#89cd1467",
        "1.8.5.a#a2615b26",
    ),
}

# Supplement rule-backed manifest encoding only for these clauses, whose full
# conditions and waived service scope are handled by the runtime paths. Other
# traced clauses have broader or time-bounded conditions and stay pending unless
# their Gate B source rules independently encode them.
COMPOSITOR_FULLY_ENCODED_SOURCE_KEYS = frozenset(
    {
        "1.8.2.(3)#04043a39",  # EK-4/D match requires the listed diagnosis, drug, and report.
        "1.8.5.(7)#fb187fbe",  # EK-1/A outpatient specialist exam; report gates savings.
    }
)
