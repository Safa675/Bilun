"""SUT-specific seeded payload helpers for test cache fixtures."""

from __future__ import annotations

from typing import Any


def cohort_sut_summary_payload() -> dict[str, Any]:
    return {"n_patients": 1}


def sut_single_json_payloads() -> dict[str, dict[str, Any]]:
    return {
        "cohort_sut_exposure": {
            "BILUN_summary": {
                "n_patients": 1,
            },
        },
        "cohort_optimization_summary": {
            "copay_exemptions": {
                "n_exempt_patients": 1,
                "n_total_patients": 1,
                "exemption_rate": 1.0,
                "top_diseases": [{"disease": "Diabetes", "count": 1}],
                "methodology": "seeded smoke payload",
            },
            "surcharge_exposure": {
                "n_patients_with_flags": 1,
                "n_total_patients": 1,
                "flag_rate": 1.0,
                "top_rules": [{"code": "A1", "count": 1}],
                "methodology": "seeded smoke payload",
            },
            "copay_rate_exposure": {
                "n_patients_with_flags": 1,
                "n_total_patients": 1,
                "flag_rate": 1.0,
                "cohort_mean_rate": 37.5,
                "rate_distribution": {"20": 1},
                "methodology": "seeded smoke payload",
            },
            "temporal_price_validation": {
                "ek2b": {"n_changed_codes": 0},
                "ek2c": {"n_changed_codes": 0},
                "methodology": "seeded smoke payload",
            },
            "drg_unbundling": {
                "n_patients_checked": 1,
                "n_patients_with_risk": 0,
                "risk_rate": 0.0,
                "total_potential_savings": 0.0,
                "top_risky_chapters": [],
                "methodology": "seeded smoke payload",
            },
        },
        "patient_alerts_payload": {
            "patients": [
                {
                    "patient_id": "P1",
                    "n_diagnoses": 1,
                    "icd10_chapters": ["E"],
                    "copay_exemption": {
                        "exempt": True,
                        "n_qualifying": 1,
                        "qualifying_diagnoses": [
                            {
                                "icd10": "E11.9",
                                "disease": "Diabetes",
                                "range": "E10-E14",
                            }
                        ],
                        "action": "Waive outpatient copay",
                    },
                    "surcharge_exposure": {
                        "n_applicable": 1,
                        "exposure_rate": 0.1,
                        "top_rules": [
                            {"code": "A1", "name": "Rule A", "matched_chapters": ["E"]}
                        ],
                        "action": "Do not charge surcharge",
                    },
                    "copay_rate_exposure": {
                        "n_applicable": 1,
                        "mean_rate": 37.5,
                        "top_procedures": [
                            {
                                "code": "500",
                                "name": "Proc 500",
                                "rate_pct": 50.0,
                                "matched_chapters": ["E"],
                            }
                        ],
                        "action": "Apply capped copay rate",
                    },
                }
            ],
            "summary": {
                "n_total_patients": 1,
                "n_exempt_patients": 1,
                "exemption_rate": 1.0,
                "n_patients_with_surcharge_flags": 1,
                "n_patients_with_copay_rate_flags": 1,
                "total_surcharge_flags": 1,
                "total_copay_rate_flags": 1,
            },
        },
        "patient_billing_reports": {
            "P1": {
                "patient_id": "P1",
                "lab": {"normative_cost_try": 10.0, "flagged_tests": []},
                "copay": {
                    "is_exempt": True,
                    "exemption_disease": "Diabetes",
                    "exemption_range": "E10-E14",
                    "visit_copay_savings_try": 5.0,
                    "rx_copay_savings_try": 7.5,
                    "total_copay_savings_try": 5.0,
                    "patient_copay_waived_total_try": 12.5,
                    "savings_beneficiary": "patient_and_sgk",
                    "gap_kind": "exemption_correction",
                    "rate_corrections": [],
                },
                "billing_strategy": {"recommendations": []},
                "materials": {
                    "pre_auth_required": [],
                    "miat_restricted": [],
                    "gazette_ceiling_by_specialty": {},
                },
                "total_recoverable_try": 0.0,
                "action_count": 1,
                "priority": "high",
            }
        },
        "cohort_recovery_summary": {
            "n_patients": 1,
            "total_lab_savings": 0.0,
            "total_copay_savings": 12.5,
            "total_strategy_savings": 0.0,
            "total_material_flags": 0,
            "grand_total_recoverable": 0.0,
            "top_patients": [{"patient_id": "P1", "total_recoverable_try": 0.0}],
            "savings_by_category": {"copay": 12.5},
            "priority_distribution": {"high": 1},
        },
    }
