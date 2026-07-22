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
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/optimization/copay_exemption_rules/visit_type.py",
            "src/bilun/domain/optimization/copay_exemption_rules/patient_status.py",
            "src/bilun/domain/optimization/copay_exemption_rules/occupational.py",
            "src/bilun/domain/billing/claim_copay.py",
        ),
        sut_section_prefixes=("1.8.1", "1.8.5"),
        keywords=("acil servis", "koruyucu sağlık", "katılım payı alınmaz"),
        description="Visit-type, status, and occupational copay waivers (hand-coded §1.8.5)",
        description_tr="Ziyaret tipi, durum ve meslek bazlı katılım payı muafiyetleri (§1.8.5 elle kodlu)",
    ),
    RuleRegistryEntry(
        rule_id="copay_rate_general",
        rule_category="copay_rate",
        rule_category_tr="Katılım Payı Oranı",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/copay_general.py",
            "src/bilun/domain/billing/claim_copay.py",
            "data/gazette/prose_rules/copay_general_1_8.json",
        ),
        sut_section_prefixes=("1.8.2", "1.8.3", "1.8.4"),
        keywords=("katılım payı alınır", "%10", "%20"),
        description="General drug/material/IVF copay rates from copay_general_1_8.json (4 rules)",
        description_tr="copay_general_1_8.json'dan genel ilaç/malzeme/tüp bebek katılım payı oranları (4 kural)",
    ),
    RuleRegistryEntry(
        rule_id="copay_rate_ek2c1",
        rule_category="copay_rate",
        rule_category_tr="Katılım Payı Oranı",
        coverage_status="implemented",
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
        coverage_status="implemented",
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
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/optimization/surcharge.py",
            "src/bilun/domain/billing/claim_copay.py",
        ),
        sut_section_prefixes=("1.9",),
        keywords=("ilave ücret",),
        description="General §1.9 surcharge prose + exact claim-line exposure (with EK-2G list)",
        description_tr="Genel §1.9 ilave ücret prose + kesin talep satırı maruziyeti (EK-2/G listesi ile)",
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
            "src/bilun/domain/analytics/drg.py",
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
            "src/bilun/domain/analytics/drg.py",
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
        coverage_status="implemented",
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
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/billing/materials.py",
            "src/bilun/domain/billing/claim_materials.py",
            "src/bilun/domain/billing/miat_interval.py",
        ),
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
            "EK-4/A catalog lookup (reference data). Drug copay percentages in "
            "copay_general_1_8.json — not a billing optimizer."
        ),
        description_tr=(
            "EK-4/A katalog sorgusu (referans veri). İlaç katılım payı yüzdeleri "
            "copay_general_1_8.json'da — fatura optimize edici değil."
        ),
    ),
    RuleRegistryEntry(
        rule_id="drug_indication_prose",
        rule_category="drug_indication",
        rule_category_tr="İlaç Endikasyon",
        # Phase 5: flipped back to implemented. The motor IS implemented
        # (919 rules, evaluate_drug_indication_line runs in production). The
        # partial label (commit ec33851) was honest about the ~50% encoding
        # ratio, but it caused 984 encoded clauses to count as gaps (partial
        # status counts unconditionally per coverage.py:381-382), overstating
        # real encode-debt by ~6x. Under implemented status, only the genuinely
        # unencoded clauses count as gaps (~178, dropping toward ~128 after
        # Phase 5 PROMOTE encodings). The remaining unencoded clauses are
        # honestly tracked via the tier_c_deferred / emr_blocked manifest lists.
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/drug_indication.py",
            "src/bilun/domain/billing/claim_drug_indication.py",
            "data/gazette/prose_rules/drug_indication_prose.json",
            "data/gazette/prose_rules/anti_vegf_prose.json",
        ),
        sut_section_prefixes=("4.2",),
        annex_refs=("EK-4/A",),
        keywords=("endikasyon", "rapor", "reçete", "tanıya dayalı", "kullanımı"),
        description=(
            "§4.2 drug indication / report prose — §4.2.14.C oncology (131 rules) + "
            "§4.2.33 anti-VEGF / ophthalmology (21 rules, dose protocol). "
            "ICD+report matcher, Tier B duration/prescriber/inpatient + §4.2.33 dose enforcement. "
            "Wave 4: substantive gaps encoded or tier-C deferred; registry promoted to implemented."
        ),
        description_tr=(
            "§4.2 ilaç endikasyon / rapor prose — §4.2.14.C onkoloji (131 kural) + "
            "§4.2.33 anti-VEGF / göz (21 kural, doz protokolü). "
            "ICD+rapor eşleştirici, Tier B süre/reçete/yatarak + §4.2.33 doz kontrolü."
        ),
    ),
    RuleRegistryEntry(
        rule_id="copay_exemption_ek4d",
        rule_category="copay_exemption",
        rule_category_tr="Katılım Payı Muafiyeti",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/drugs/ek4d_exempt.py",
            "src/bilun/domain/billing/claim_copay.py",
            "data/gazette/curated/ek4d_copay_exempt_entries.parquet",
        ),
        sut_section_prefixes=("1.8.2", "1.8.5"),
        annex_refs=("EK-4/D",),
        keywords=("katılım payından muaf", "sağlık raporu"),
        description="EK-4/D drug copay exemptions (§1.8.2(3), §1.8.5(8))",
        description_tr="EK-4/D ilaç katılım payı muafiyetleri (§1.8.2(3), §1.8.5(8))",
    ),
    RuleRegistryEntry(
        rule_id="drug_discount_prose",
        rule_category="drug_discount",
        rule_category_tr="İlaç İndirimi",
        coverage_status="implemented",
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
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/billing/lab_bill_merge.py",
            "src/bilun/domain/prose_rules/lab_capture_gap.py",
            "src/bilun/domain/billing/claim_procedure_capture_gap.py",
        ),
        sut_section_prefixes=("4.2.9.A-2",),
        annex_refs=(),
        keywords=("hemogram", "L107020", "hemoglobin"),
        description="Lab hemogram bundling + clinical-lab vs claim capture gap detection",
        description_tr="Laboratuvar hemogram paketleme + klinik lab / talep yakalama boşluğu tespiti",
    ),
    RuleRegistryEntry(
        rule_id="drg_package_adequacy",
        rule_category="drg_coding",
        rule_category_tr="DRG Paket Kodu Yeterliliği",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/drg_package_adequacy.py",
            "src/bilun/domain/billing/claim_drg_package_adequacy.py",
            "data/gazette/prose_rules/drg_package_adequacy_prose.json",
        ),
        sut_section_prefixes=("2.2.1.B", "2.2.2"),
        annex_refs=("EK-2/C",),
        keywords=("609270", "609300", "paket kodu", "tanıya dayalı işlem paketi"),
        description="EK-2/C package code adequacy review (pilot JSON rules)",
        description_tr="EK-2/C paket kodu yeterliliği gözden geçirmesi (pilot JSON kuralları)",
    ),
    RuleRegistryEntry(
        rule_id="gazette_repricing",
        rule_category="pricing",
        rule_category_tr="Tebliğ Sonrası Yeniden Fiyatlama",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/gazette_repricing.py",
            "src/bilun/domain/billing/claim_gazette_repricing.py",
            "data/gazette/prose_rules/gazette_repricing_prose.json",
            "data/gazette/prose_manifests/L2.2_gazette_repricing_encoded_manifest.json",
        ),
        sut_section_prefixes=("1.1", "2.2"),
        annex_refs=("EK-2/B", "EK-2/C"),
        keywords=("yeniden faturalandır", "tebliğde değiştirilen", "liste fiyat"),
        description="Prospective gazette repricing gate (display-only; excluded from SGK headline)",
        description_tr="Tebliğ sonrası prospektif yeniden fiyatlama kapısı (gösterim amaçlı; SGK toplamına dahil değil)",
    ),
    RuleRegistryEntry(
        rule_id="procedure_pairing",
        rule_category="procedure_pairing",
        rule_category_tr="İşlem Eşleştirme (Add-on)",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/procedure_addon_uplift.py",
            "src/bilun/domain/billing/claim_procedure_addon_uplift.py",
            "data/gazette/prose_rules/procedure_pairing_prose.json",
            "data/gazette/prose_manifests/L2.2_procedure_pairing_encoded_manifest.json",
        ),
        sut_section_prefixes=("2.2.2.A",),
        annex_refs=("EK-2/B",),
        keywords=("aynı seans", "polipektomi"),
        description="Same-session procedure add-on pairing uplift (6 pilot rules)",
        description_tr="Aynı seans işlem eklentisi eşleştirme artışı (6 pilot kural)",
    ),
    RuleRegistryEntry(
        rule_id="material_pairing",
        rule_category="material_pairing",
        rule_category_tr="Malzeme Eşleştirme (Artış)",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/prose_rules/material_uplift.py",
            "src/bilun/domain/billing/claim_material_uplift.py",
            "data/gazette/prose_rules/material_pairing_uplift.json",
            "data/gazette/prose_manifests/L3.1_material_pairing_encoded_manifest.json",
        ),
        sut_section_prefixes=("3.1.1", "3.3.1", "3.3.2", "3.3.4"),
        annex_refs=("EK-3/C", "EK-3/H", "EK-3/I", "EK-3/F"),
        keywords=("eksik veya sıfır faturalanmış", "ayrıca faturalandırılabilir"),
        description="Procedure-to-material pairing uplift (12 pilot rules; inverse EK-3B-1)",
        description_tr="İşlem-malzeme eşleştirme artışı (12 pilot kural; EK-3B-1 tersi)",
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
        rule_id="ek2c_prose_drg_locked",
        rule_category="payment_method",
        rule_category_tr="Ödeme Yöntemi",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/ek2c_prose_drg_locked.py",
            "src/bilun/domain/prose_rules/payment_method.py",
            "src/bilun/domain/prose_rules/catalog_membership.py",
            "data/gazette/prose_rules/ek2c_prose_drg_locked_codes.json",
        ),
        sut_section_prefixes=("2.2.2",),
        annex_refs=("EK-2/C",),
        keywords=(
            "yalnızca",
            "faturalandırılamaz",
            "ek-2/c listesinden",
            "üçüncü basamak",
        ),
        description="§2.2.2 prose-mandated EK-2/C package codes (51-code seed; override barred)",
        description_tr="§2.2.2 prose zorunlu EK-2/C paket kodları (51 kod seed; override yasak)",
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
        coverage_status="non_algorithmic",
        domain_modules=(),
        sut_section_prefixes=("5.2", "5.3", "5.4"),
        keywords=("fatura", "belge"),
        description="Invoice/document format compliance (§5.2–5.4) — administrative, not billing optimization",
        description_tr="Fatura/belge şekil uygunluğu (§5.2–5.4) — idari, fatura optimizasyonu değil",
    ),
    RuleRegistryEntry(
        rule_id="medula_rejection_playbook",
        rule_category="medula_rejection",
        rule_category_tr="MEDULA Red Playbook",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/prose_rules/medula_rejection.py",
            "src/bilun/domain/billing/claim_medula_rejection.py",
            "data/medula/rejection_playbook.json",
        ),
        sut_section_prefixes=(),
        keywords=("fatura kayıt red", "sonuç kodu", "hata mesajı", "yeniden fatura"),
        description="MEDULA rejection → corrective rebill playbook (event-driven; partial template corpus)",
        description_tr="MEDULA red → düzeltici yeniden fatura playbook (olay güdümlü; kısmi şablon corpus)",
    ),
    RuleRegistryEntry(
        rule_id="provizyon_medula",
        rule_category="billing_admin",
        rule_category_tr="Fatura Yönetimi",
        coverage_status="non_algorithmic",
        domain_modules=(),
        sut_section_prefixes=("1.7", "1.10", "1.11", "5.1"),
        keywords=("MEDULA", "provizyon"),
        description="MEDULA provision and billing system prose (playbook wired separately)",
        description_tr="MEDULA provizyon ve fatura sistemi prose (playbook ayrı kuralda)",
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
    RuleRegistryEntry(
        rule_id="definitions_2_6",
        rule_category="administrative",
        rule_category_tr="Tanımlar (§2.6)",
        coverage_status="non_algorithmic",
        domain_modules=(
            "src/bilun/domain/prose_rules/definitions_2_6.py",
            "data/gazette/prose_rules/definitions_2_6.json",
            "data/gazette/prose_manifests/L2.6_definitions_manifest.json",
        ),
        sut_section_prefixes=("2.6",),
        annex_refs=(),
        keywords=(),
        description="§2.6 definitions — descriptive scope gates (travel/daily/companion allowances, documentation windows). Non-algorithmic: rules carry free-text enforcement messages, not billable verdicts.",
        description_tr="§2.6 tanımları — açıklayıcı kapsamı kapıları (yol/gündelik/refakatçi ödemeleri, belge süreleri). Algorithmik değil: kurallar faturalanabilir karar değil, serbest metin uygulama mesajları taşır.",
    ),
    RuleRegistryEntry(
        rule_id="gap_closing_misc",
        rule_category="gap_closing",
        rule_category_tr="Boşluk Kapatma (§1/§3-§6)",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/gap_closing.py",
            "data/gazette/prose_rules/gap_closing_misc.json",
            "data/gazette/prose_manifests/gap_closing_misc_manifest.json",
        ),
        sut_section_prefixes=("1.5", "1.6", "1.8", "3.3", "4.1", "4.2", "5.1", "6.1"),
        annex_refs=(),
        keywords=("sözleşmesiz", "ödenmez", "acil haller dışında"),
        description="Cross-section gap-closing gates (§1.5/§1.6 provider contracting, §3-§6 cross-cutting no-pay). Partial: rules execute against claim-context flags; rules needing unsurfaced clinical data are skipped honestly.",
        description_tr="Bölümler arası boşluk kapatma kapıları (§1.5/§1.6 sunucu sözleşmesi, §3-§6 genel ödenmez). Kısmi: kurallar talep-bağlam bayraklarına göre çalışır; yüzeylenmemiş klinik veri gerektiren kurallar dürüstçe atlanır.",
    ),
    RuleRegistryEntry(
        rule_id="gap_closing_treatment_2",
        rule_category="gap_closing",
        rule_category_tr="Boşluk Kapatma (§2)",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/gap_closing.py",
            "data/gazette/prose_rules/gap_closing_treatment_2.json",
            "data/gazette/prose_manifests/gap_closing_treatment_2_manifest.json",
        ),
        sut_section_prefixes=("2.2", "2.3", "2.4", "2.5"),
        annex_refs=(),
        keywords=("ayrıca faturalandırılamaz", "paket kapsamında", "ödenmez"),
        description="§2 treatment gap-closing gates (§2.2 payment method, §2.3/§2.5 emergency/overseas bundling). Partial: executes against claim-context flags; rules needing hours_since_onset/stem_cell_type/overseas_treatment_days are skipped.",
        description_tr="§2 tedavi boşluk kapatma kapıları (§2.2 ödeme yöntemi, §2.3/§2.5 acil/yurtdışı paketleme). Kısmi: talep-bağlam bayraklarına göre çalışır; hours_since_onset/stem_cell_type/overseas_treatment_days gerektiren kurallar atlanır.",
    ),
    RuleRegistryEntry(
        rule_id="dental_2_4_1",
        rule_category="dental",
        rule_category_tr="Diş (§2.4.1)",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/dental_2_4_1.py",
            "data/gazette/prose_rules/dental_2_4_1.json",
            "data/gazette/prose_manifests/dental_2_4_1_manifest.json",
        ),
        sut_section_prefixes=("2.4.1",),
        annex_refs=(),
        keywords=("kıymetli maden", "ödenmez", "diş"),
        description="§2.4.1 dental rules — partial: 3 of 10 rules wire (precious-metal no-pay, implant board-report gate, treating-physician continuity). Remaining 7 need patient_age/years_since_last_prosthesis/facility_type not on the claim model.",
        description_tr="§2.4.1 diş kuralları — kısmi: 10 kuralın 3'ü çalışır (kıymetli maden ödenmez, implant kurul raporu kapısı, tedavi hekimi sürekliliği). Kalan 7'si claim modelinde olmayan patient_age/years_since_last_prosthesis/facility_type gerektirir.",
    ),
    RuleRegistryEntry(
        rule_id="treatment_pricing_2_4",
        rule_category="treatment_pricing",
        rule_category_tr="Tedavi Fiyatlandırması (§2.4)",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/prose_rules/treatment_pricing.py",
            "data/gazette/prose_rules/treatment_pricing_2_4.json",
        ),
        sut_section_prefixes=("2.4",),
        annex_refs=("EK-2/C",),
        keywords=("seans", "ödenmez", "paket kapsamında", "ayrıca faturalandırılamaz"),
        description="§2.4 treatment-pricing prose — partial: 17 of 182 rules fire on condition keys derivable from PatientClaimContext (procedure_category, procedure_code_any, provider_type, facility_tier, diagnosis_any/in with ICD-10 prefix match, health_board_report_present). The remaining 165 need session counters / IVF cycle history / temporal windows / clinical scores (BMI, testosterone, risk scores) absent from the claim model and honest-skip via the predicate guard.",
        description_tr="§2.4 tedavi fiyatlandırması prose — kısmi: 182 kuralın 17'si PatientClaimContext'ten türetilebilen anahtarlarla çalışır. Kalan 165, claim modelinde olmayan seans sayacı / IVF döngü geçmişi / zamansal pencere / klinik skor (BMI, testosteron, risk skorları) gerektirir ve predicate guard ile dürüstçe atlanır.",
    ),
    RuleRegistryEntry(
        rule_id="drug_combination_4_2",
        rule_category="drug_combination",
        rule_category_tr="İlaç Kombinasyonu (§4.2)",
        coverage_status="partial",
        domain_modules=(
            "src/bilun/domain/prose_rules/drug_combination.py",
            "data/gazette/prose_rules/drug_combination_4_2.json",
        ),
        sut_section_prefixes=("4.2",),
        annex_refs=("EK-4/A", "EK-4/B"),
        keywords=("birlikte kullanım", "kombinasyon", "ödenmez", "aynı anda"),
        description="§4.2 drug-combination prose — partial: 6 of 53 rules fire (DOAC combo, cinacalcet/etelcalsetid, myeloma PI combo, active-vitamin-D/osteoporosis, MS-DMT combo) via drug_name_any / drug_name_set_any_two / drug_name_set_all + ICD-10 prefix diagnosis_any. The remaining 47 need a drug→class map (~18 rules), PD-L1/ECOG/Child-Pugh clinical fields (~14 oncology), or EMR prior-therapy/progression timelines (~15) and honest-skip via skipped_no_data.",
        description_tr="§4.2 ilaç kombinasyonu prose — kısmi: 53 kuralın 6'sı çalışır (DOAC kombinasyonu, sinakalsiet/etelkalsetid, miyelom PI kombinasyonu, aktif-D vitamini/osteoporoz, MS-DMT kombinasyonu). Kalan 47, ilaç→sınıf haritası, PD-L1/ECOG/Child-Pugh klinik alanları veya EMR önceki-tedavi/ilerişim zaman çizelgesi gerektirir ve skipped_no_data ile dürüstçe atlanır.",
    ),
    RuleRegistryEntry(
        rule_id="fatura_inceleme_prose",
        rule_category="fatura_inceleme",
        rule_category_tr="Fatura İnceleme Usul ve Esasları",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/fatura_inceleme.py",
            "data/gazette/prose_rules/fatura_inceleme_prose.json",
            "data/gazette/prose_manifests/fatura_inceleme_prose_manifest.json",
            "data/gazette/fatura_inceleme_clauses.parquet",
        ),
        sut_section_prefixes=(),
        annex_refs=(),
        keywords=(),
        description="SGK Fatura İnceleme Usul ve Esasları — 91 algorithmic denial rules from 28 branches + Ortak Kriterler. NOT SUT. Separate regulatory corpus (dayanak: 5510 md. 63/73). 11 of 29 SUT-referencing rules cross-linked to SUT clause_ids via sut_cross_ref field. Keywords intentionally empty — this motor must NOT classify SUT clauses (separate corpus).",
        description_tr="SGK Fatura İnceleme Usul ve Esasları — 28 branş + Ortak Kriterler'den 91 algoritmik ret kuralı. SUT değil. Ayrı mevzuat (dayanak: 5510 md. 63/73). 29 SUT referansı içeren kuralın 11'i sut_cross_ref ile SUT clause_id'lere bağlanmıştır. Anahtar kelimeler boş — bu motor SUT clause'larını sınıflandırmamalıdır (ayrı mevzuat).",
    ),
    RuleRegistryEntry(
        rule_id="fatura_inceleme_checklist",
        rule_category="fatura_inceleme",
        rule_category_tr="Fatura İnceleme Doküman Kontrol",
        coverage_status="implemented",
        domain_modules=(
            "src/bilun/domain/prose_rules/fatura_inceleme_checklist.py",
            "data/gazette/prose_rules/fatura_inceleme_checklist.json",
        ),
        sut_section_prefixes=(),
        annex_refs=(),
        keywords=(),
        description="SGK Fatura İnceleme — 63 documentation requirement rules. Produces pre-submission checklist items (not violations). Fires when a procedure is billed without the required report/epikriz content.",
        description_tr="SGK Fatura İnceleme — 63 doküman gereksinim kuralı. Gönderim öncesi kontrol listesi öğeleri üretir (ihlal değil). Bir işlem faturalandığında gerekli rapor/epikriz içeriği yoksa devreye girer.",
    ),
)

RULE_REGISTRY: tuple[RuleRegistryEntry, ...] = tuple(
    replace(entry, **RULE_FACT_CHECK_INDEX[entry.rule_id])
    if entry.rule_id in RULE_FACT_CHECK_INDEX
    else entry
    for entry in _BASE_RULE_REGISTRY
)

RULE_BY_ID: dict[str, RuleRegistryEntry] = {entry.rule_id: entry for entry in RULE_REGISTRY}
