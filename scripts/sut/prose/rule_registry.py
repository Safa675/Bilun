"""
Registry mapping SUT rule categories to BILUN domain implementations.

Each entry describes what the codebase currently implements for a slice of
the consolidated SUT prose + annex lists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CoverageStatus = Literal[
    "implemented",
    "partial",
    "missing",
    "needs_claim_lines",
    "non_algorithmic",
]


@dataclass(frozen=True)
class RuleRegistryEntry:
    rule_id: str
    rule_category: str
    coverage_status: CoverageStatus
    domain_modules: tuple[str, ...]
    sut_section_prefixes: tuple[str, ...] = ()
    annex_refs: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    description: str = ""


RULE_REGISTRY: tuple[RuleRegistryEntry, ...] = (
    RuleRegistryEntry(
        rule_id="copay_exemption_ek1a",
        rule_category="copay_exemption",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/optimization/copay_exemptions.py",
            "src/bilun/domain/optimization/copay_exemption_rules/ek1a.py",
            "src/bilun/domain/billing/copay.py",
        ),
        sut_section_prefixes=("1.8.5",),
        annex_refs=("EK-1/A",),
        keywords=("katılım payı alınmaz", "kronik hastalık"),
        description="EK-1A chronic disease copay exemptions",
    ),
    RuleRegistryEntry(
        rule_id="copay_exemption_visit_type",
        rule_category="copay_exemption",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/optimization/copay_exemption_rules/visit_type.py",
            "src/bilun/domain/optimization/copay_exemption_rules/patient_status.py",
            "src/bilun/domain/optimization/copay_exemption_rules/occupational.py",
        ),
        sut_section_prefixes=("1.8.1", "1.8.5"),
        keywords=("acil servis", "koruyucu sağlık", "katılım payı alınmaz"),
        description="Visit-type and status copay waivers (hand-coded, not parsed from prose)",
    ),
    RuleRegistryEntry(
        rule_id="copay_rate_general",
        rule_category="copay_rate",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/prose_rules/copay_general.py",
            "src/bilun/domain/billing/copay.py",
            "src/bilun/domain/billing/claim_copay.py",
        ),
        sut_section_prefixes=("1.8.2", "1.8.3", "1.8.4"),
        keywords=("katılım payı alınır", "%10", "%20"),
        description="General drug/material copay percentages in §1.8 prose — encoded in copay_general_1_8",
    ),
    RuleRegistryEntry(
        rule_id="copay_rate_ek2c1",
        rule_category="copay_rate",
        coverage_status="needs_claim_lines",
        domain_modules=(
            "src/bilun/domain/optimization/copay_rates.py",
            "src/bilun/domain/billing/claim_copay.py",
        ),
        annex_refs=("EK-2/C-1",),
        keywords=("katılım payı",),
        description="Procedure-specific copay rates from EK-2C-1 list",
    ),
    RuleRegistryEntry(
        rule_id="surcharge_ek2g",
        rule_category="surcharge",
        coverage_status="needs_claim_lines",
        domain_modules=("src/bilun/domain/optimization/surcharge.py",),
        sut_section_prefixes=("1.9.3",),
        annex_refs=("EK-2/G",),
        keywords=("ilave ücret",),
        description="EK-2G procedures where surcharge is prohibited",
    ),
    RuleRegistryEntry(
        rule_id="surcharge_general",
        rule_category="surcharge",
        coverage_status="partial",
        domain_modules=("src/bilun/domain/optimization/surcharge.py",),
        sut_section_prefixes=("1.9",),
        keywords=("ilave ücret",),
        description="General surcharge rules in §1.9 prose",
    ),
    RuleRegistryEntry(
        rule_id="payment_method_package",
        rule_category="payment_method",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/payment_method.py",
            "src/bilun/domain/prose_rules/catalog_membership.py",
            "src/bilun/domain/prose_rules/facility_tier.py",
            "src/bilun/domain/billing/claim_strategy.py",
            "src/bilun/domain/optimization/unbundling.py",
            "src/bilun/domain/pricing/drg.py",
        ),
        sut_section_prefixes=("2.2",),
        annex_refs=("EK-2/C",),
        keywords=("tanıya dayalı işlem", "faturalandırılır"),
        description="Package (DRG) billing when procedure is in EK-2/C — §2.2 prose + tier/star engine",
    ),
    RuleRegistryEntry(
        rule_id="payment_method_itemized",
        rule_category="payment_method",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/payment_method.py",
            "src/bilun/domain/prose_rules/catalog_membership.py",
            "src/bilun/domain/billing/claim_strategy.py",
            "src/bilun/domain/catalog.py",
        ),
        sut_section_prefixes=("2.2",),
        annex_refs=("EK-2/B", "EK-2/A"),
        keywords=("hizmet başı", "ayrıca faturalandır"),
        description="Itemized billing when procedure is only in EK-2/B — §2.2 prose engine",
    ),
    RuleRegistryEntry(
        rule_id="payment_method_tier_override",
        rule_category="payment_method",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/payment_method.py",
            "src/bilun/domain/prose_rules/facility_tier.py",
            "src/bilun/domain/prose_rules/catalog_membership.py",
            "src/bilun/domain/billing/claim_strategy.py",
        ),
        sut_section_prefixes=("2.2.2",),
        annex_refs=("EK-2/B", "EK-2/C"),
        keywords=(
            "(*) işareti bulunmayan",
            "ek-2/b listesinden de faturalandırabilir",
            "üçüncü basamak sağlık kurumları",
        ),
        description="§2.2.2(2) third-tier optional EK-2/B override for non-star EK-2/C codes",
    ),
    RuleRegistryEntry(
        rule_id="pricing_ek2b",
        rule_category="pricing",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/catalog.py",
            "src/bilun/domain/pricing/temporal.py",
            "src/bilun/domain/optimization/temporal.py",
        ),
        annex_refs=("EK-2/B",),
        sut_section_prefixes=("1.1", "2.2"),
        keywords=("puan", "katsayı"),
        description="Fee-for-service procedure pricing from EK-2B",
    ),
    RuleRegistryEntry(
        rule_id="pricing_ek2c",
        rule_category="pricing",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/pricing/drg.py",
            "src/bilun/domain/optimization/temporal.py",
        ),
        annex_refs=("EK-2/C",),
        description="DRG package pricing from EK-2C",
    ),
    RuleRegistryEntry(
        rule_id="pricing_ek2a",
        rule_category="pricing",
        coverage_status="implemented",
        domain_modules=("src/bilun/domain/catalog.py",),
        annex_refs=("EK-2/A",),
        description="Outpatient visit pricing from EK-2A",
    ),
    RuleRegistryEntry(
        rule_id="bundling_ek3b1",
        rule_category="bundling",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/rules/bundling_rules.py",
            "src/bilun/domain/materials/exclusions.py",
        ),
        annex_refs=("EK-3/B", "EK-3/B-1"),
        keywords=("işlem puanına dahil", "ayrıca faturalandırılamaz"),
        description="Bundled consumables that must not be billed separately",
    ),
    RuleRegistryEntry(
        rule_id="exclusion_ek3b2",
        rule_category="material_exclusion",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/rules/exclusion_rules.py",
            "src/bilun/domain/materials/exclusions.py",
        ),
        annex_refs=("EK-3/B", "EK-3/B-2"),
        keywords=("bedelleri Kurumca karşılanmaz", "ödenmez"),
        description="Non-reimbursable materials from EK-3B-2",
    ),
    RuleRegistryEntry(
        rule_id="material_preauth_ek3c1",
        rule_category="material_preauth",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/billing/materials.py",
            "src/bilun/domain/billing/claim_materials.py",
        ),
        annex_refs=("EK-3/C-1",),
        description="Materials requiring pre-authorization (EK-3C-1)",
    ),
    RuleRegistryEntry(
        rule_id="material_miat_ek3c2",
        rule_category="material_miat",
        coverage_status="partial",
        domain_modules=("src/bilun/domain/billing/materials.py",),
        annex_refs=("EK-3/C-2",),
        keywords=("miat", "minimum uygulama aralığı"),
        description="Materials with minimum inter-application time (EK-3C-2)",
    ),
    RuleRegistryEntry(
        rule_id="specialty_materials",
        rule_category="specialty_materials",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/materials/specialty.py",
            "src/bilun/domain/materials/cardiac.py",
            "src/bilun/domain/analytics/materials.py",
        ),
        sut_section_prefixes=("3.3",),
        annex_refs=("EK-3/A", "EK-3/F", "EK-3/H", "EK-3/O"),
        description="Branch specialty material pricing catalogs (EK-3A–3T)",
    ),
    RuleRegistryEntry(
        rule_id="specialty_materials_prose",
        rule_category="specialty_materials",
        coverage_status="partial",
        domain_modules=("src/bilun/domain/prose_rules/specialty_materials.py",),
        sut_section_prefixes=("3.3",),
        keywords=("karşılanmaz", "yara örtü", "deri taklit"),
        description="§3.3 specialty annex prose engine (L4.4 pilot §3.3.1 wound/dressing)",
    ),
    RuleRegistryEntry(
        rule_id="material_bundling_prose",
        rule_category="bundling",
        coverage_status="implemented",
        domain_modules=("src/bilun/domain/prose_rules/material_bundling.py",),
        sut_section_prefixes=("3.1", "3.2"),
        keywords=("ayrıca faturalandırılamaz", "faturalandırılmayacaktır"),
        description="§3.1 prose engine wired (partial clause coverage); EK-3B-1/3B-2 annex lists primary",
    ),
    RuleRegistryEntry(
        rule_id="drug_ek4a",
        rule_category="drug_reimbursement",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/materials/drugs.py",
            "src/bilun/domain/billing/drug.py",
            "src/bilun/domain/optimization/drugs.py",
        ),
        annex_refs=("EK-4/A",),
        sut_section_prefixes=("4.1", "4.4"),
        description="Drug reimbursement catalog and substitution (EK-4A)",
    ),
    RuleRegistryEntry(
        rule_id="drug_discount_prose",
        rule_category="drug_discount",
        coverage_status="needs_claim_lines",
        domain_modules=("src/bilun/domain/optimization/drugs.py",),
        sut_section_prefixes=("4.4",),
        keywords=("indirim oran", "eşdeğer ilaç"),
        description="Drug discount tier validation (§4.4 prose + EK-4A tiers)",
    ),
    RuleRegistryEntry(
        rule_id="lab_billing",
        rule_category="lab_billing",
        coverage_status="partial",
        domain_modules=("src/bilun/domain/billing/lab.py",),
        annex_refs=("EK-2/B",),
        keywords=("hemogram", "L107020"),
        description="Lab hemogram bundling and duplicate detection (inferred from EK-2B, not docx prose)",
    ),
    RuleRegistryEntry(
        rule_id="drg_unbundling",
        rule_category="drg_unbundling",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/optimization/unbundling.py",
            "src/bilun/domain/prose_rules/drg_unbundling.py",
            "src/bilun/domain/prose_rules/session_pricing.py",
            "src/bilun/domain/prose_rules/payment_method.py",
            "src/bilun/domain/prose_rules/facility_tier.py",
        ),
        annex_refs=("EK-2/C",),
        keywords=("paket", "ayrıca faturalandır"),
        description="DRG unbundling with §2.2 payment-method, session point, and bundling checks",
    ),
    RuleRegistryEntry(
        rule_id="claim_validation",
        rule_category="claim_validation",
        coverage_status="implemented",
        domain_modules=("src/bilun/domain/rule_engine.py",),
        keywords=(),
        description="Pre-submission bundling + exclusion validation orchestrator",
    ),
    RuleRegistryEntry(
        rule_id="billing_documents",
        rule_category="billing_admin",
        coverage_status="missing",
        domain_modules=(),
        sut_section_prefixes=("5.2", "5.3", "5.4"),
        description="Invoice/document compliance rules (§5.2–5.4)",
    ),
    RuleRegistryEntry(
        rule_id="provizyon_medula",
        rule_category="billing_admin",
        coverage_status="missing",
        domain_modules=(),
        sut_section_prefixes=("1.7", "5.1"),
        keywords=("MEDULA", "provizyon"),
        description="MEDULA provision and billing system rules",
    ),
    RuleRegistryEntry(
        rule_id="referral_admission",
        rule_category="administrative",
        coverage_status="non_algorithmic",
        domain_modules=(),
        sut_section_prefixes=("1.5", "1.6"),
        description="Patient admission, referral, identity — operational not billing optimization",
    ),
    RuleRegistryEntry(
        rule_id="definitions",
        rule_category="administrative",
        coverage_status="non_algorithmic",
        domain_modules=(),
        sut_section_prefixes=("1.1", "1.2", "1.3", "1.4"),
        description="Definitions and scope — reference text only",
    ),
)

RULE_BY_ID: dict[str, RuleRegistryEntry] = {entry.rule_id: entry for entry in RULE_REGISTRY}
