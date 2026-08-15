"""Line-scoped SUT copay waiver applicators (§1.8.5 / EK-1A / EK-4/D)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import Any

from src.bilun.domain.billing.line_decomposition import (
    decompose_drug_line,
    decompose_procedure_line,
    drug_surcharge_prohibition_clause,
    emergency_surcharge_exemption_clause,
)
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine, ProcedureClaimLine
from src.bilun.domain.drugs.ek4d_exempt import match_ek4d_copay_exempt_drug
from src.bilun.domain.sut.clause_reference import (
    RULE_TYPE_COPAY_WAIVER,
    SutClauseReference,
    sut_clause_reference,
)

_INPATIENT_CLAIM_TYPES = frozenset({"yatis", "gunubirlik"})
_EMERGENCY_TYPES = frozenset(
    {"acil", "acil_servis", "emergency", "emergency_department"}
)
_PREVENTIVE_TYPES = frozenset(
    {"koruyucu", "koruyucu_saglik", "preventive", "preventive_health"}
)
_OCCUPATIONAL_VISIT_TYPES = frozenset(
    {"is_kazasi", "meslek_hastaligi", "work_accident", "occupational_disease"}
)
_OCCUPATIONAL_CONTEXTS = frozenset(
    {"is_kazasi", "meslek_hastaligi", "work_accident", "occupational_disease"}
)
_GREEN_ZONE_EXAM_CODE = "520021"
_FULL_COMPOSITE_SECTIONS = frozenset({"1.8.1", "1.8.2", "1.8.3"})
_COMPOSITE_PATIENT_STATUS_CATEGORIES = frozenset(
    {"yesil_kart", "sehit_gazi", "vatani_hizmet"}
)


@lru_cache(maxsize=8)
def _copay_waiver_clause_ref(coordinate: str, annex: str = "") -> SutClauseReference:
    """Cached Track E reference for a copay-waiver clause (per coordinate)."""
    return sut_clause_reference(coordinate, rule_type=RULE_TYPE_COPAY_WAIVER, annex=annex)


@dataclass(frozen=True)
class WaiverResult:
    """Savings or insight for one claim line under a specific waiver ground."""

    component_try: Decimal
    exemption_ground: str
    sut_section_id: str
    rule_id: str
    annex: str
    detail: str
    code: str = ""
    name: str = ""
    billed_try: float | None = None
    payable_try: float | None = None
    insight_only: bool = False
    ilave_ucret_try: Decimal = Decimal("0")
    clause_ref: SutClauseReference | None = None
    drug_waiver: bool = False

    def to_rate_correction(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "exemption_ground": self.exemption_ground,
            "sut_section": self.sut_section_id,
            "rule_id": self.rule_id,
            "detail": self.detail,
        }
        if self.annex:
            row["annex"] = self.annex
        if self.code:
            row["code"] = self.code
        if self.name:
            row["name"] = self.name
        if self.billed_try is not None:
            row["billed_try"] = self.billed_try
        if self.payable_try is not None:
            row["payable_try"] = self.payable_try
        if self.component_try > 0:
            row["copay_component_try"] = float(self.component_try)
        if self.ilave_ucret_try > 0:
            row["ilave_ucret_try"] = float(self.ilave_ucret_try)
        if self.clause_ref is not None:
            row["clause_ref"] = self.clause_ref.to_dict()
        if self.drug_waiver:
            row["ilave_ucret_status"] = "drug_prohibited"
            row["ilave_clause_ref"] = drug_surcharge_prohibition_clause().to_dict()
        elif self.exemption_ground.startswith("composite_acil"):
            row["ilave_ucret_status"] = "emergency_exempt"
            row["ilave_clause_ref"] = emergency_surcharge_exemption_clause().to_dict()
        elif self.exemption_ground == "ek1a_muayene":
            row["ilave_ucret_status"] = "none"
        return row


def copay_component(billed: Decimal, payable: Decimal) -> Decimal:
    if billed <= payable:
        return Decimal("0")
    return billed - payable


def _waivable_copay_parts(
    line: ProcedureClaimLine | DrugClaimLine,
) -> tuple[Decimal, Decimal]:
    if isinstance(line, ProcedureClaimLine):
        decomp = decompose_procedure_line(line)
    else:
        decomp = decompose_drug_line(line)

    if decomp.status != "missing_inputs":
        return decomp.patient_copay_try, decomp.ilave_ucret_try

    return copay_component(line.billed_amount_try, line.expected_payable_try), Decimal("0")


def waives_section(section: str, sources: list[dict[str, Any]]) -> bool:
    return any(section in (source.get("waives_sections") or ()) for source in sources)


def _normalize_token(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _is_full_composite_source(source: dict[str, Any]) -> bool:
    sections = set(source.get("waives_sections") or ())
    return _FULL_COMPOSITE_SECTIONS.issubset(sections)


def find_ek1a_source(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    for source in sources:
        if source.get("category") == "ek1a_chronic":
            return source
    return None


def _composite_applies_to_claim(
    source: dict[str, Any],
    claim: ClaimHeader,
    procedure_codes: set[str],
) -> bool:
    category = source.get("category")
    claim_type = _normalize_token(claim.claim_type)

    if category == "acil_servis":
        if claim_type not in _EMERGENCY_TYPES:
            return False
        if procedure_codes and procedure_codes <= {_GREEN_ZONE_EXAM_CODE}:
            return False
        return True

    if category == "koruyucu_saglik":
        return claim_type in _PREVENTIVE_TYPES

    if category == "is_kazasi_meslek":
        occupational = _normalize_token(claim.occupational_context)
        return (
            claim_type in _OCCUPATIONAL_VISIT_TYPES
            or occupational in _OCCUPATIONAL_CONTEXTS
        )

    if category in _COMPOSITE_PATIENT_STATUS_CATEGORIES:
        return bool(source.get("counts_toward_exempt", True))

    return False


def waiver_ek1a_muayene(
    line: ProcedureClaimLine,
    claim: ClaimHeader,
    ek1a_source: dict[str, Any] | None,
    *,
    has_health_report: bool | None,
) -> WaiverResult | None:
    """§1.8.5(7)+EK-1A: ayaktan poliklinik uzman muayenesi only."""

    if not line.copay_rate_applicable:
        return None
    if line.procedure_category != "muayene":
        return None
    if claim.claim_type != "poliklinik":
        return None
    if ek1a_source is None or not ek1a_source.get("counts_toward_exempt"):
        return None
    if has_health_report is False:
        return None

    component, ilave = _waivable_copay_parts(line)
    if component <= 0 and ilave <= 0:
        return None

    return WaiverResult(
        component_try=component,
        ilave_ucret_try=ilave,
        exemption_ground="ek1a_muayene",
        sut_section_id="1.8.5(7)",
        rule_id="copay_exemption_ek1a",
        annex="EK-1A",
        detail="EK-1A chronic disease may waive §1.8.1 on outpatient specialist examination",
        code=line.procedure_code,
        name=line.procedure_name,
        billed_try=float(line.billed_amount_try),
        payable_try=float(line.expected_payable_try),
        clause_ref=_copay_waiver_clause_ref("1.8.5.(7)", "EK-1/A"),
    )


def waiver_inpatient_drug(
    line: DrugClaimLine,
    claim: ClaimHeader,
) -> WaiverResult | None:
    """§1.8.5(8)(b) proxy: all drugs on yatis/gunubirlik claims."""

    if claim.claim_type not in _INPATIENT_CLAIM_TYPES:
        return None

    component, ilave = _waivable_copay_parts(line)
    if component <= 0 and ilave <= 0:
        return None

    return WaiverResult(
        component_try=component,
        ilave_ucret_try=ilave,
        exemption_ground="inpatient_drug_1_8_5_8",
        sut_section_id="1.8.5(8)",
        rule_id="copay_inpatient_drug_1_8_5_8",
        annex="",
        detail=(
            "§1.8.5(8) may waive §1.8.2 drug copay for inpatient/day-case drugs on this claim"
        ),
        code=line.drug_code,
        name=line.drug_name,
        billed_try=float(line.billed_amount_try),
        payable_try=float(line.expected_payable_try),
        clause_ref=_copay_waiver_clause_ref("1.8.5.(8)"),
        drug_waiver=True,
    )


def waiver_ek4d_drug(
    line: DrugClaimLine,
    diagnoses: list[str],
    *,
    has_health_report: bool | None,
    savings_already_applied: bool,
) -> WaiverResult | None:
    """§1.8.2(3)+EK-4/D drug match — always evaluated for attribution rows."""

    ek4d = match_ek4d_copay_exempt_drug(
        diagnoses,
        drug_name=str(line.drug_name or ""),
        drug_code=str(line.drug_code or ""),
        barkod=str(line.barkod or ""),
        has_health_report=has_health_report,
    )
    if ek4d is None:
        return None

    component, ilave = _waivable_copay_parts(line)
    drug_label = ek4d["evidence"].get("drug_name_tr") or line.drug_name
    section_title = ek4d["evidence"].get("section_title", "listed disease")

    if ek4d.get("partial_without_report"):
        return WaiverResult(
            component_try=Decimal("0"),
            exemption_ground="ek4d_partial",
            sut_section_id="1.8.2.(3)",
            rule_id="copay_exemption_ek4d",
            annex="EK-4/D",
            detail=(
                "EK-4/D drug match without health report — §1.8.2(3) savings not asserted"
            ),
            code=line.drug_code,
            name=line.drug_name,
            insight_only=True,
            clause_ref=_copay_waiver_clause_ref("1.8.2.(3)", "EK-4/D"),
            drug_waiver=True,
        )

    if not ek4d.get("counts_toward_exempt"):
        return None

    if savings_already_applied:
        return WaiverResult(
            component_try=Decimal("0"),
            exemption_ground="ek4d_drug",
            sut_section_id="1.8.2.(3)",
            rule_id="copay_exemption_ek4d",
            annex="EK-4/D",
            detail=(
                f"EK-4/D listed drug ({drug_label}) for {section_title} — "
                "copay already waived under a higher-priority ground on this line"
            ),
            code=line.drug_code,
            name=line.drug_name,
            billed_try=float(line.billed_amount_try),
            payable_try=float(line.expected_payable_try),
            insight_only=True,
            clause_ref=_copay_waiver_clause_ref("1.8.2.(3)", "EK-4/D"),
            drug_waiver=True,
        )

    if component <= 0:
        return None

    return WaiverResult(
        component_try=component,
        ilave_ucret_try=ilave,
        exemption_ground="ek4d_drug",
        sut_section_id="1.8.2.(3)",
        rule_id="copay_exemption_ek4d",
        annex="EK-4/D",
        detail=(
            f"EK-4/D exempt drug ({drug_label}) for {section_title}"
        ),
        code=line.drug_code,
        name=line.drug_name,
        billed_try=float(line.billed_amount_try),
        payable_try=float(line.expected_payable_try),
        clause_ref=_copay_waiver_clause_ref("1.8.2.(3)", "EK-4/D"),
        drug_waiver=True,
    )


def _first_composite_source_for_claim(
    sources: list[dict[str, Any]],
    claim: ClaimHeader,
    claim_procedure_codes: dict[str, set[str]],
) -> dict[str, Any] | None:
    procedure_codes = claim_procedure_codes.get(claim.claim_id, set())
    for source in sources:
        if not _is_full_composite_source(source):
            continue
        if not source.get("counts_toward_exempt", True):
            continue
        if _composite_applies_to_claim(source, claim, procedure_codes):
            return source
    return None


def waiver_composite_procedure(
    line: ProcedureClaimLine,
    claim: ClaimHeader,
    sources: list[dict[str, Any]],
    claim_procedure_codes: dict[str, set[str]],
) -> WaiverResult | None:
    if not line.copay_rate_applicable:
        return None
    if not waives_section("1.8.1", sources):
        return None

    source = _first_composite_source_for_claim(sources, claim, claim_procedure_codes)
    if source is None:
        return None

    component, ilave = _waivable_copay_parts(line)
    if component <= 0 and ilave <= 0:
        return None

    category = str(source.get("category") or "composite")
    return WaiverResult(
        component_try=component,
        ilave_ucret_try=ilave,
        exemption_ground=f"composite_{category}",
        sut_section_id="1.8.5",
        rule_id=f"copay_exemption_{category}",
        annex="",
        detail=str(source.get("rule_source") or "Composite visit copay waiver"),
        code=line.procedure_code,
        name=line.procedure_name,
        billed_try=float(line.billed_amount_try),
        payable_try=float(line.expected_payable_try),
        clause_ref=_copay_waiver_clause_ref("1.8.5"),
    )


def waiver_composite_drug(
    line: DrugClaimLine,
    claim: ClaimHeader,
    sources: list[dict[str, Any]],
    claim_procedure_codes: dict[str, set[str]],
) -> WaiverResult | None:
    if not waives_section("1.8.2", sources):
        return None

    source = _first_composite_source_for_claim(sources, claim, claim_procedure_codes)
    if source is None:
        return None

    component, ilave = _waivable_copay_parts(line)
    if component <= 0 and ilave <= 0:
        return None

    category = str(source.get("category") or "composite")
    return WaiverResult(
        component_try=component,
        ilave_ucret_try=ilave,
        exemption_ground=f"composite_{category}",
        sut_section_id="1.8.5",
        rule_id=f"copay_exemption_{category}",
        annex="",
        detail=str(source.get("rule_source") or "Composite visit drug copay waiver"),
        code=line.drug_code,
        name=line.drug_name,
        billed_try=float(line.billed_amount_try),
        payable_try=float(line.expected_payable_try),
        clause_ref=_copay_waiver_clause_ref("1.8.5"),
        drug_waiver=True,
    )
