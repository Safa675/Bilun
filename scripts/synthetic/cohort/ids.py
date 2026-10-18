"""Pure ID builders for the synthetic SUT claim dataset: patient, claim, episode, line and diagnosis ids."""

from __future__ import annotations

import re

PATIENT_ID_RE = re.compile(r"^SENTETIK-HASTA-\d{4}$")
CLAIM_ID_RE = re.compile(r"^F-(SENTETIK-HASTA-\d{4})-(\d{3})$")
EPISODE_ID_RE = re.compile(r"^B-SENTETIK-HASTA-\d{4}-\d{3}$")
PROCEDURE_LINE_ID_RE = re.compile(r"^ISL-F-SENTETIK-HASTA-\d{4}-\d{3}-\d{3}$")
MATERIAL_LINE_ID_RE = re.compile(r"^MLZ-F-SENTETIK-HASTA-\d{4}-\d{3}-\d{3}$")
DRUG_CLAIM_LINE_ID_RE = re.compile(r"^ILC-F-SENTETIK-HASTA-\d{4}-\d{3}-\d{3}$")
DIAGNOSIS_ID_RE = re.compile(r"^TANI-SENTETIK-HASTA-\d{4}-\d{3}-\d{3}$")
PERFORMED_LINE_ID_RE = re.compile(r"^EMR-F-SENTETIK-HASTA-\d{4}-\d{3}-\d{3}$")
PRESCRIPTION_ID_RE = re.compile(r"^RCT-F-SENTETIK-HASTA-\d{4}-\d{3}$")


def _check_seq(seq: int, *, width: int = 3, label: str = "seq") -> int:
    if isinstance(seq, bool) or not isinstance(seq, int) or not (1 <= seq < 10**width):
        raise ValueError(f"{label} must be an integer in 1..{10**width - 1}, got {seq!r}")
    return seq


def _check_patient_id(patient: str) -> str:
    if not isinstance(patient, str) or not PATIENT_ID_RE.fullmatch(patient):
        raise ValueError(f"invalid patient_id {patient!r}; expected SENTETIK-HASTA-NNNN")
    return patient


def _check_claim_id(claim: str) -> str:
    if not isinstance(claim, str) or not CLAIM_ID_RE.fullmatch(claim):
        raise ValueError(f"invalid claim_id {claim!r}; expected F-SENTETIK-HASTA-NNNN-NNN")
    return claim


def patient_id(seq: int) -> str:
    """Build a patient identifier: ``SENTETIK-HASTA-NNNN``."""
    n = _check_seq(seq, width=4, label="patient seq")
    return f"SENTETIK-HASTA-{n:04d}"


def claim_id(patient: str, seq: int) -> str:
    """Build a claim identifier: ``F-<patient>-NNN``."""
    pid = _check_patient_id(patient)
    n = _check_seq(seq, width=3, label="claim seq")
    return f"F-{pid}-{n:03d}"


def episode_id(patient: str, seq: int) -> str:
    """Build an episode identifier: ``B-<patient>-NNN``."""
    pid = _check_patient_id(patient)
    n = _check_seq(seq, width=3, label="episode seq")
    return f"B-{pid}-{n:03d}"


def procedure_line_id(claim: str, seq: int) -> str:
    """Build a procedure line identifier: ``ISL-<claim>-NNN``."""
    cid = _check_claim_id(claim)
    n = _check_seq(seq, width=3, label="procedure line seq")
    return f"ISL-{cid}-{n:03d}"


def material_line_id(claim: str, seq: int) -> str:
    """Build a material line identifier: ``MLZ-<claim>-NNN``."""
    cid = _check_claim_id(claim)
    n = _check_seq(seq, width=3, label="material line seq")
    return f"MLZ-{cid}-{n:03d}"


def drug_claim_line_id(claim: str, seq: int) -> str:
    """Build a drug line identifier: ``ILC-<claim>-NNN``."""
    cid = _check_claim_id(claim)
    n = _check_seq(seq, width=3, label="drug line seq")
    return f"ILC-{cid}-{n:03d}"


drug_line_id = drug_claim_line_id


def diagnosis_id(
    patient_or_claim: str,
    claim_seq_or_seq: int,
    seq: int | None = None,
) -> str:
    """Build a diagnosis identifier: ``TANI-<patient>-<claim seq NNN>-NNN``.

    Accepts either ``diagnosis_id(patient_id, claim_seq, seq)`` or ``diagnosis_id(claim_id, seq)``.
    """
    if seq is None:
        match = CLAIM_ID_RE.fullmatch(patient_or_claim if isinstance(patient_or_claim, str) else "")
        if not match:
            raise ValueError(
                f"invalid claim_id {patient_or_claim!r}; expected F-SENTETIK-HASTA-NNNN-NNN"
            )
        pid = match.group(1)
        claim_seq = int(match.group(2))
        line_seq = _check_seq(claim_seq_or_seq, width=3, label="diagnosis seq")
    else:
        pid = _check_patient_id(patient_or_claim)
        claim_seq = _check_seq(claim_seq_or_seq, width=3, label="claim seq")
        line_seq = _check_seq(seq, width=3, label="diagnosis seq")
    return f"TANI-{pid}-{claim_seq:03d}-{line_seq:03d}"


def performed_line_id(claim: str, seq: int) -> str:
    """Build a performed procedure line identifier: ``EMR-<claim>-NNN``."""
    cid = _check_claim_id(claim)
    n = _check_seq(seq, width=3, label="performed line seq")
    return f"EMR-{cid}-{n:03d}"


def prescription_id(claim: str) -> str:
    """Build a prescription identifier: ``RCT-<claim>``."""
    cid = _check_claim_id(claim)
    return f"RCT-{cid}"
