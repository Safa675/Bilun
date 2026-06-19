"""Typed registry for synthetic demo vignettes (P2 scale-out)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
VIGNETTES_PATH = PROJECT_ROOT / "data" / "synthetic" / "demo_vignettes.json"

DemoTier = Literal["A", "B", "C"]
PresentationKind = Literal["package_only", "itemized_only"]


@dataclass(frozen=True)
class ItemizedCodeVignette:
    code: str
    price_try: float

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ItemizedCodeVignette:
        return cls(
            code=str(payload["code"]),
            price_try=float(payload["price_try"]),
        )


@dataclass(frozen=True)
class GoldenExpectation:
    """Frozen billing-strategy bands keyed by scenario_tag (not claim_id)."""

    savings_try: tuple[float, float]
    package_total_try: tuple[float, float] | None = None
    itemized_total_try: tuple[float, float] | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GoldenExpectation:
        return cls(
            savings_try=(float(payload["savings_try"][0]), float(payload["savings_try"][1])),
            package_total_try=(
                (float(payload["package_total_try"][0]), float(payload["package_total_try"][1]))
                if payload.get("package_total_try")
                else None
            ),
            itemized_total_try=(
                (float(payload["itemized_total_try"][0]), float(payload["itemized_total_try"][1]))
                if payload.get("itemized_total_try")
                else None
            ),
        )

    def contains(self, *, savings: float, package_total: float | None = None, itemized_total: float | None = None) -> bool:
        if not (self.savings_try[0] <= savings <= self.savings_try[1]):
            return False
        if package_total is not None and self.package_total_try is not None:
            low, high = self.package_total_try
            if not (low <= package_total <= high):
                return False
        if itemized_total is not None and self.itemized_total_try is not None:
            low, high = self.itemized_total_try
            if not (low <= itemized_total <= high):
                return False
        return True


@dataclass(frozen=True)
class BillingVignette:
    patient_index: str
    scenario_tag: str
    fault: str
    tier: DemoTier = "B"
    department: str | None = None
    primary_icd10: str | None = None
    secondary_icd10: tuple[str, ...] = ()
    package_code: str | None = None
    package_price_try: float | None = None
    itemized_codes: tuple[ItemizedCodeVignette, ...] = ()
    presentation: PresentationKind | None = None
    golden: GoldenExpectation | None = None
    medula: dict[str, Any] = field(default_factory=dict)
    drug_indication_key: str | None = None
    material_prose_key: str | None = None
    claim_readiness_key: str | None = None

    @property
    def patient_id(self) -> str:
        return f"SENTETIK-HASTA-{self.patient_index}"

    @classmethod
    def from_dict(cls, patient_index: str, payload: dict[str, Any]) -> BillingVignette:
        itemized = tuple(
            ItemizedCodeVignette.from_dict(entry)
            for entry in (payload.get("itemized_codes") or [])
        )
        secondary = tuple(str(code) for code in (payload.get("secondary_icd10") or []))
        golden = (
            GoldenExpectation.from_dict(payload["golden"])
            if payload.get("golden")
            else None
        )
        return cls(
            patient_index=str(payload.get("patient_index") or patient_index),
            scenario_tag=str(payload["scenario_tag"]),
            fault=str(payload["fault"]),
            tier=str(payload.get("tier") or "B"),  # type: ignore[arg-type]
            department=payload.get("department"),
            primary_icd10=payload.get("primary_icd10"),
            secondary_icd10=secondary,
            package_code=payload.get("package_code"),
            package_price_try=(
                float(payload["package_price_try"])
                if payload.get("package_price_try") is not None
                else None
            ),
            itemized_codes=itemized,
            presentation=payload.get("presentation"),  # type: ignore[arg-type]
            golden=golden,
            medula=dict(payload.get("medula") or {}),
            drug_indication_key=payload.get("drug_indication_key"),
            material_prose_key=payload.get("material_prose_key"),
            claim_readiness_key=payload.get("claim_readiness_key"),
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "patient_index": self.patient_index,
            "scenario_tag": self.scenario_tag,
            "fault": self.fault,
            "tier": self.tier,
        }
        if self.department:
            payload["department"] = self.department
        if self.primary_icd10:
            payload["primary_icd10"] = self.primary_icd10
        if self.secondary_icd10:
            payload["secondary_icd10"] = list(self.secondary_icd10)
        if self.package_code:
            payload["package_code"] = self.package_code
        if self.package_price_try is not None:
            payload["package_price_try"] = self.package_price_try
        if self.itemized_codes:
            payload["itemized_codes"] = [
                {"code": entry.code, "price_try": entry.price_try}
                for entry in self.itemized_codes
            ]
        if self.presentation:
            payload["presentation"] = self.presentation
        if self.golden:
            payload["golden"] = {
                "savings_try": list(self.golden.savings_try),
            }
            if self.golden.package_total_try:
                payload["golden"]["package_total_try"] = list(self.golden.package_total_try)
            if self.golden.itemized_total_try:
                payload["golden"]["itemized_total_try"] = list(self.golden.itemized_total_try)
        if self.medula:
            payload["medula"] = self.medula
        if self.drug_indication_key:
            payload["drug_indication_key"] = self.drug_indication_key
        if self.material_prose_key:
            payload["material_prose_key"] = self.material_prose_key
        if self.claim_readiness_key:
            payload["claim_readiness_key"] = self.claim_readiness_key
        return payload


@dataclass(frozen=True)
class VignetteRegistry:
    by_index: dict[str, BillingVignette]
    by_scenario_tag: dict[str, BillingVignette]

    def get(self, patient_index: str) -> BillingVignette | None:
        return self.by_index.get(patient_index)

    def get_for_patient_id(self, patient_id: str) -> BillingVignette | None:
        return self.get(patient_id.rsplit("-", 1)[-1])

    def get_by_scenario_tag(self, scenario_tag: str) -> BillingVignette | None:
        return self.by_scenario_tag.get(scenario_tag)

    def indices_for_tier(self, tier: DemoTier) -> list[str]:
        return sorted(
            vignette.patient_index
            for vignette in self.by_index.values()
            if vignette.tier == tier
        )


def load_vignette_registry(path: Path | None = None) -> VignetteRegistry:
    source = path or VIGNETTES_PATH
    if not source.exists():
        return VignetteRegistry(by_index={}, by_scenario_tag={})
    with source.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    by_index: dict[str, BillingVignette] = {}
    by_scenario_tag: dict[str, BillingVignette] = {}
    for patient_index, raw in (payload.get("vignettes") or {}).items():
        vignette = BillingVignette.from_dict(str(patient_index), raw)
        by_index[vignette.patient_index] = vignette
        by_scenario_tag[vignette.scenario_tag] = vignette
    return VignetteRegistry(by_index=by_index, by_scenario_tag=by_scenario_tag)


@lru_cache(maxsize=1)
def get_vignette_registry() -> VignetteRegistry:
    return load_vignette_registry()
