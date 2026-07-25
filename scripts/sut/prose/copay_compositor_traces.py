"""Compositor clause traces for §1.8 copay runtime modules (Track F data).

Moved out of ``copay_exemption_gate_b`` so canonical Gate B manifests can attach
these extras without depending on the retired bespoke writer.
"""

from __future__ import annotations

COMPOSITOR_CLAUSE_TRACES: dict[str, list[str]] = {
    "copay_exemption_ek1a": ["C000361"],
    "copay_exemption_ek4d": ["C000326", "C000362"],
    "copay_exemption_visit_type": ["C000359", "C000360"],
    "copay_exemption_occupational": ["C000355"],
    "copay_exemption_patient_status": [
        "C000365",
        "C000366",
        "C000367",
        "C000369",
        "C000370",
        "C000375",
        "C000378",
        "C000379",
    ],
}
