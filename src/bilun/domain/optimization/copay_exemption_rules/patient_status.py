"""Patient status copay exemptions (SGK class, veteran, age allowance)."""

from __future__ import annotations

from typing import Any

from src.bilun.domain.claims.models import PatientCopayProfile


def _normalize_token(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def evaluate_patient_status_exemptions(
    profile: PatientCopayProfile | None,
    *,
    age_at_latest_claim: float | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (sources, categories_not_evaluated)."""
    sources: list[dict[str, Any]] = []
    not_evaluated: list[dict[str, Any]] = []

    if profile is None:
        for category, fields in (
            ("yesil_kart", ["sgk_benefit_class"]),
            ("sehit_gazi", ["veteran_martyr_status"]),
            ("vatani_hizmet", ["national_service_status"]),
            ("kanun_2022_65", ["elderly_allowance_2022", "birth_year"]),
        ):
            not_evaluated.append(
                {
                    "category": category,
                    "required_inputs_missing": fields,
                }
            )
        return sources, not_evaluated

    benefit = _normalize_token(profile.sgk_benefit_class)
    if benefit in {"yesil_kart", "green_card", "yesilkart"}:
        sources.append(
            {
                "category": "yesil_kart",
                "rule_source": "SGK green card benefit class",
                "evidence": {"sgk_benefit_class": profile.sgk_benefit_class},
            }
        )

    veteran = _normalize_token(profile.veteran_martyr_status)
    if veteran in {"sehit", "gazi", "yakin", "martyr", "veteran_relative"}:
        sources.append(
            {
                "category": "sehit_gazi",
                "rule_source": "Martyr / veteran / relative status",
                "evidence": {"veteran_martyr_status": profile.veteran_martyr_status},
            }
        )
    elif veteran == "none":
        pass
    else:
        not_evaluated.append(
            {
                "category": "sehit_gazi",
                "required_inputs_missing": ["veteran_martyr_status"],
            }
        )

    national = _normalize_token(profile.national_service_status)
    if national in {"vatani_hizmet", "national_service"}:
        sources.append(
            {
                "category": "vatani_hizmet",
                "rule_source": "National service beneficiary status",
                "evidence": {"national_service_status": profile.national_service_status},
            }
        )

    age = age_at_latest_claim
    if age is None and profile.birth_year is not None:
        age = None

    allowance = bool(profile.elderly_allowance_2022)
    if allowance and age is not None and age >= 65:
        sources.append(
            {
                "category": "kanun_2022_65",
                "rule_source": "Law 2022 elderly allowance (65+)",
                "evidence": {
                    "elderly_allowance_2022": True,
                    "age_at_latest_claim": age,
                },
            }
        )
    elif allowance and age is None:
        not_evaluated.append(
            {
                "category": "kanun_2022_65",
                "required_inputs_missing": ["age_at_latest_claim"],
            }
        )

    return sources, not_evaluated
