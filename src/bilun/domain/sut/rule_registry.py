"""
Registry mapping SUT rule categories to BILUN domain implementations.

Each entry describes what the codebase currently implements for a slice of
the consolidated SUT prose + annex lists.

This is the canonical home for the registry. The offline prose pipeline under
``scripts/sut/prose/rule_registry.py`` re-exports from here so the production
API never has to import from ``scripts/``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from .fact_check_audit import (
    FactCheckVerdict,
    MedulaOverlap,
    RULE_FACT_CHECK_INDEX,
)

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
    # Turkish display metadata for the Rule Database UI.
    rule_category_tr: str = ""
    description_tr: str = ""
    # June 2026 algorithm fact-check audit (see fact_check_audit.py).
    fact_check_verdict: FactCheckVerdict | None = None
    medula_overlap: MedulaOverlap | None = None
    fact_check_units: tuple[str, ...] = ()
    fact_check_note: str = ""


_BASE_RULE_REGISTRY: tuple[RuleRegistryEntry, ...] = (
    RuleRegistryEntry(
        rule_id="copay_exemption_ek1a",
        rule_category="copay_exemption",
        rule_category_tr="Katılım Payı Muafiyeti",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/optimization/copay_exemptions.py",
            "src/bilun/domain/optimization/copay_exemption_rules/ek1a.py",
            "src/bilun/domain/billing/claim_copay.py",
        ),
        sut_section_prefixes=("1.8.5",),
        annex_refs=("EK-1/A",),
        keywords=("katılım payı alınmaz", "kronik hastalık"),
        description="EK-1A chronic disease copay exemptions",
        description_tr="EK-1/A kronik hastalık katılım payı muafiyetleri",
    ),
    RuleRegistryEntry(
        rule_id="copay_exemption_visit_type",
        rule_category="copay_exemption",
        rule_category_tr="Katılım Payı Muafiyeti",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/optimization/copay_exemption_rules/visit_type.py",
            "src/bilun/domain/optimization/copay_exemption_rules/patient_status.py",
            "src/bilun/domain/optimization/copay_exemption_rules/occupational.py",
        ),
        sut_section_prefixes=("1.8.1", "1.8.5"),
        keywords=("acil servis", "koruyucu sağlık", "katılım payı alınmaz"),
        description="Visit-type and status copay waivers (hand-coded, not parsed from prose)",
        description_tr="Ziyaret tipi ve durum bazlı katılım payı muafiyetleri (elle kodlanmış, prose'den çıkarılmamış)",
    ),
    RuleRegistryEntry(
        rule_id="copay_rate_general",
        rule_category="copay_rate",
        rule_category_tr="Katılım Payı Oranı",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/prose_rules/copay_general.py",
            "src/bilun/domain/billing/claim_copay.py",
        ),
        sut_section_prefixes=("1.8.2", "1.8.3", "1.8.4"),
        keywords=("katılım payı alınır", "%10", "%20"),
        description="General drug/material copay percentages in §1.8 prose — encoded in copay_general_1_8",
        description_tr="§1.8 prose'sindeki genel ilaç/malzeme katılım payı yüzdeleri — copay_general_1_8 içinde kodlanmış",
    ),
    RuleRegistryEntry(
        rule_id="copay_rate_ek2c1",
        rule_category="copay_rate",
        rule_category_tr="Katılım Payı Oranı",
        coverage_status="needs_claim_lines",
        domain_modules=(
            "src/bilun/domain/optimization/copay_rates.py",
            "src/bilun/domain/billing/claim_copay.py",
        ),
        annex_refs=("EK-2/C-1",),
        keywords=("katılım payı",),
        description="Procedure-specific copay rates from EK-2C-1 list",
        description_tr="EK-2/C-1 listesinden işlem bazlı katılım payı oranları",
    ),
    RuleRegistryEntry(
        rule_id="surcharge_ek2g",
        rule_category="surcharge",
        rule_category_tr="İlave Ücret",
        coverage_status="needs_claim_lines",
        domain_modules=("src/bilun/domain/optimization/surcharge.py",),
        sut_section_prefixes=("1.9.3",),
        annex_refs=("EK-2/G",),
        keywords=("ilave ücret",),
        description="EK-2G procedures where surcharge is prohibited",
        description_tr="EK-2/G'de ilave ücretin yasak olduğu işlemler",
    ),
    RuleRegistryEntry(
        rule_id="surcharge_general",
        rule_category="surcharge",
        rule_category_tr="İlave Ücret",
        coverage_status="partial",
        domain_modules=("src/bilun/domain/optimization/surcharge.py",),
        sut_section_prefixes=("1.9",),
        keywords=("ilave ücret",),
        description="General surcharge rules in §1.9 prose",
        description_tr="§1.9 prose'sindeki genel ilave ücret kuralları",
    ),
    RuleRegistryEntry(
        rule_id="payment_method_package",
        rule_category="payment_method",
        rule_category_tr="Ödeme Yöntemi",
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
        description_tr="EK-2/C'deki işlem için paket (DRG) faturalandırma — §2.2 prose + basamak/yıldız motoru",
    ),
    RuleRegistryEntry(
        rule_id="payment_method_itemized",
        rule_category="payment_method",
        rule_category_tr="Ödeme Yöntemi",
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
        description_tr="İşlem yalnızca EK-2/B'deyse kalemsel faturalandırma — §2.2 prose motoru",
    ),
    RuleRegistryEntry(
        rule_id="payment_method_tier_override",
        rule_category="payment_method",
        rule_category_tr="Ödeme Yöntemi",
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
        description_tr="§2.2.2(2) üçüncü basamak isteğe bağlı EK-2/B geçersiz kılma (yıldız olmayan EK-2/C kodları için)",
    ),
    RuleRegistryEntry(
        rule_id="pricing_ek2b",
        rule_category="pricing",
        rule_category_tr="Fiyatlandırma",
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
        description_tr="EK-2/B'den hizmet başı işlem fiyatlandırması",
    ),
    RuleRegistryEntry(
        rule_id="pricing_ek2c",
        rule_category="pricing",
        rule_category_tr="Fiyatlandırma",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/pricing/drg.py",
            "src/bilun/domain/optimization/temporal.py",
        ),
        annex_refs=("EK-2/C",),
        description="DRG package pricing from EK-2C",
        description_tr="EK-2/C'den DRG paket fiyatlandırması",
    ),
    RuleRegistryEntry(
        rule_id="pricing_ek2a",
        rule_category="pricing",
        rule_category_tr="Fiyatlandırma",
        coverage_status="implemented",
        domain_modules=("src/bilun/domain/catalog.py",),
        annex_refs=("EK-2/A",),
        description="Outpatient visit pricing from EK-2A",
        description_tr="EK-2/A'dan ayaktan ziyaret fiyatlandırması",
    ),
    RuleRegistryEntry(
        rule_id="bundling_ek3b1",
        rule_category="bundling",
        rule_category_tr="Paketleme",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/rules/bundling_rules.py",
            "src/bilun/domain/materials/exclusions.py",
        ),
        annex_refs=("EK-3/B", "EK-3/B-1"),
        keywords=("işlem puanına dahil", "ayrıca faturalandırılamaz"),
        description="Bundled consumables that must not be billed separately",
        description_tr="Ayrıca faturalandırılamayacak paket sarf malzemeleri (EK-3/B-1)",
    ),
    RuleRegistryEntry(
        rule_id="exclusion_ek3b2",
        rule_category="material_exclusion",
        rule_category_tr="Malzeme Hariç Tutma",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/rules/exclusion_rules.py",
            "src/bilun/domain/materials/exclusions.py",
        ),
        annex_refs=("EK-3/B", "EK-3/B-2"),
        keywords=("bedelleri Kurumca karşılanmaz", "ödenmez"),
        description="Non-reimbursable materials from EK-3B-2",
        description_tr="EK-3/B-2'den geri ödenmeyen malzemeler",
    ),
    RuleRegistryEntry(
        rule_id="material_preauth_ek3c1",
        rule_category="material_preauth",
        rule_category_tr="Malzeme Ön Onayı",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/billing/materials.py",
            "src/bilun/domain/billing/claim_materials.py",
        ),
        annex_refs=("EK-3/C-1",),
        description="Materials requiring pre-authorization (EK-3C-1)",
        description_tr="Ön onay gerektiren malzemeler (EK-3/C-1)",
    ),
    RuleRegistryEntry(
        rule_id="material_miat_ek3c2",
        rule_category="material_miat",
        rule_category_tr="Malzeme Minimum Uygulama Aralığı",
        coverage_status="partial",
        domain_modules=("src/bilun/domain/billing/materials.py",),
        annex_refs=("EK-3/C-2",),
        keywords=("miat", "minimum uygulama aralığı"),
        description="Materials with minimum inter-application time (EK-3C-2)",
        description_tr="Minimum uygulama aralığı olan malzemeler (EK-3/C-2)",
    ),
    RuleRegistryEntry(
        rule_id="specialty_materials",
        rule_category="specialty_materials",
        rule_category_tr="Branşa Özel Malzemeler",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/materials/specialty.py",
            "src/bilun/domain/materials/cardiac.py",
            "src/bilun/domain/analytics/materials.py",
        ),
        sut_section_prefixes=("3.3",),
        annex_refs=("EK-3/A", "EK-3/F", "EK-3/H", "EK-3/O"),
        description="Branch specialty material pricing catalogs (EK-3A–3T)",
        description_tr="Branşa göre malzeme fiyatlandırma katalogları (EK-3A–3T)",
    ),
    RuleRegistryEntry(
        rule_id="specialty_materials_prose",
        rule_category="specialty_materials",
        rule_category_tr="Branşa Özel Malzemeler",
        coverage_status="implemented",
        domain_modules=("src/bilun/domain/prose_rules/specialty_materials.py",),
        sut_section_prefixes=("3.3",),
        keywords=("karşılanmaz", "yara örtü", "deri taklit"),
        description="§3.3 specialty annex prose engine (L4.4 — 49 rules, partial corpus)",
        description_tr="§3.3 branş ekleri prose motoru (L4.4 — 49 kural, kısmi corpus)",
    ),
    RuleRegistryEntry(
        rule_id="material_bundling_prose",
        rule_category="bundling",
        rule_category_tr="Paketleme",
        coverage_status="implemented",
        domain_modules=("src/bilun/domain/prose_rules/material_bundling.py",),
        sut_section_prefixes=("3.1", "3.2"),
        keywords=("ayrıca faturalandırılamaz", "faturalandırılmayacaktır"),
        description="§3.1 prose engine wired (partial clause coverage); EK-3B-1/3B-2 annex lists primary",
        description_tr="§3.1 prose motoru bağlı (kısmi hüküm kapsamı); EK-3B-1/3B-2 ek listeleri birincil",
    ),
    RuleRegistryEntry(
        rule_id="drug_ek4a",
        rule_category="drug_reimbursement",
        rule_category_tr="İlaç Geri Ödeme",
        coverage_status="non_algorithmic",
        domain_modules=("src/bilun/domain/materials/drugs.py",),
        annex_refs=("EK-4/A",),
        sut_section_prefixes=("4.1", "4.4"),
        description=(
            "EK-4/A catalog lookup (reference data). Drug copay rules live in "
            "copay_general_1_8.json; EK-4/D in drugs/ek4d_exempt.py — not billing optimizers."
        ),
        description_tr=(
            "EK-4/A katalog sorgusu (referans veri). İlaç katılım payı kuralları "
            "copay_general_1_8.json'da; EK-4/D drugs/ek4d_exempt.py'de — fatura optimize edici değil."
        ),
    ),
    RuleRegistryEntry(
        rule_id="drug_discount_prose",
        rule_category="drug_discount",
        rule_category_tr="İlaç İndirimi",
        coverage_status="needs_claim_lines",
        domain_modules=("src/bilun/domain/optimization/drug_discounts.py",),
        sut_section_prefixes=("4.4",),
        annex_refs=("EK-4/A",),
        keywords=("iskonto", "indirim oranı"),
        description="Drug discount tier validation from exact drug claim lines (§4.4 prose + EK-4A tiers)",
        description_tr="Kesin ilaç talep satırlarından ilaç indirim kademesi doğrulaması (§4.4 prose + EK-4/A kademeleri)",
    ),
    RuleRegistryEntry(
        rule_id="lab_billing",
        rule_category="lab_billing",
        rule_category_tr="Laboratuvar Faturalandırma",
        coverage_status="partial",
        domain_modules=("src/bilun/domain/billing/lab.py",),
        annex_refs=("EK-2/B",),
        keywords=("hemogram", "L107020"),
        description="Lab hemogram bundling only (EK-2B L107020; inferred from annex, not docx prose)",
        description_tr="Yalnızca laboratuvar hemogram paketleme (EK-2B L107020; ek listesinden çıkarım, docx prose'den değil)",
    ),
    RuleRegistryEntry(
        rule_id="drg_unbundling",
        rule_category="drg_unbundling",
        rule_category_tr="DRG Ayrıştırma",
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
        description_tr="§2.2 ödeme yöntemi, seans puanı ve paketleme kontrolleriyle DRG ayrıştırma",
    ),
    RuleRegistryEntry(
        rule_id="claim_validation",
        rule_category="claim_validation",
        rule_category_tr="Talep Doğrulama",
        coverage_status="implemented",
        domain_modules=("src/bilun/domain/rule_engine.py",),
        keywords=(),
        description="Pre-submission bundling + exclusion validation orchestrator",
        description_tr="Gönderim öncesi paketleme + hariç tutma doğrulama orkestratörü",
    ),
    RuleRegistryEntry(
        rule_id="billing_documents",
        rule_category="billing_admin",
        rule_category_tr="Fatura Yönetimi",
        coverage_status="missing",
        domain_modules=(),
        sut_section_prefixes=("5.2", "5.3", "5.4"),
        description="Invoice/document compliance rules (§5.2–5.4)",
        description_tr="Fatura/belge uygunluk kuralları (§5.2–5.4)",
    ),
    RuleRegistryEntry(
        rule_id="provizyon_medula",
        rule_category="billing_admin",
        rule_category_tr="Fatura Yönetimi",
        coverage_status="missing",
        domain_modules=(),
        sut_section_prefixes=("1.7", "5.1"),
        keywords=("MEDULA", "provizyon"),
        description="MEDULA provision and billing system rules",
        description_tr="MEDULA provizyon ve fatura sistemi kuralları",
    ),
    RuleRegistryEntry(
        rule_id="referral_admission",
        rule_category="administrative",
        rule_category_tr="İdari",
        coverage_status="non_algorithmic",
        domain_modules=(),
        sut_section_prefixes=("1.5", "1.6"),
        description="Patient admission, referral, identity — operational not billing optimization",
        description_tr="Hasta kabul, sevk, kimlik — operasyonel, fatura optimizasyonu değil",
    ),
    RuleRegistryEntry(
        rule_id="definitions",
        rule_category="administrative",
        rule_category_tr="İdari",
        coverage_status="non_algorithmic",
        domain_modules=(),
        sut_section_prefixes=("1.1", "1.2", "1.3", "1.4"),
        description="Definitions and scope — reference text only",
        description_tr="Tanımlar ve kapsam — yalnızca referans metni",
    ),
)

RULE_REGISTRY: tuple[RuleRegistryEntry, ...] = tuple(
    replace(entry, **RULE_FACT_CHECK_INDEX[entry.rule_id])
    if entry.rule_id in RULE_FACT_CHECK_INDEX
    else entry
    for entry in _BASE_RULE_REGISTRY
)

RULE_BY_ID: dict[str, RuleRegistryEntry] = {entry.rule_id: entry for entry in RULE_REGISTRY}
