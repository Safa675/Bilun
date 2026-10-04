"""Section config table — data-driven replacement for 14 gate_b modules.

Each GateBSection captures the irreducible per-section logic as data:
section matching, drug keywords, tier promotions, clause overrides, bespoke flags.
The generic engine (gate_b_generic.py) reads this table and produces identical
output to the 14 legacy modules.

Keys map to the manifest/corpus paths the legacy modules wrote.
"""

from __future__ import annotations

from scripts.sut.prose.gate_b_generic import (
    GateBSection,
    SectionMatch,
    TierOverride,
    TokenPromotion,
)

_CORPUS_DIR = "data/gazette/prose_corpus"
_MANIFEST_DIR = "data/gazette/prose_manifests"

# ── §4.2.1 — rheumatology/biologic (most complex: regex match + signal_score + audit) ──

SECTION_4201 = GateBSection(
    name="4201",
    match=SectionMatch(prefixes=("4.2.1",), use_regex_boundary=True),
    drug_keywords=(
        "leflunomid", "altin preparat", "altın preparat", "anti-tnf", "anti tnf",
        "rituksimab", "abatasept", "ustekinumab", "tofacitinib", "kanakinumab",
        "anakinra", "tosilizumab", "infliksimab", "adalimumab", "etanersept",
        "golimumab", "sertolizumab", "sekukinumab", "vedolizumab", "apremilast",
        "romatoid", "psoriatik", "ankilozan", "spondilit", "crohn", "ulseratif",
        "kolit", "uveit", "psoriazis", "biyolojik", "ilaç", "ilac", "rapor",
        "reçete", "recete",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.1",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4201.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4201_manifest.json",
    token_promotions=(
        TokenPromotion(
            tokens=(
                "leflunomid", "altin preparat", "altın preparat", "infliksimab",
                "adalimumab", "etanersept", "golimumab", "sertolizumab",
                "rituksimab", "abatasept", "tosilizumab", "ustekinumab",
                "tofacitinib", "barisitinib", "upadasitinib", "anakinra",
                "kanakinumab", "vedolizumab", "apremilast", "sekukinumab",
                "anti-tnf", "anti tnf",
            ),
            target_tier="A",
            inn_label="biyolojik_ajan",
        ),
    ),
    in_force_filtering=True,
    in_force_section_filter="4.2.1",
    requires_signal_for_export=False,
    in_force_pass_through=True,
    signal_score=True,
    sort_keys=("signal_score", "clause_id"),
    sort_descending=(True,),
    has_audit=True,
)

# ── §4.2.6 — growth hormone (clause overrides + board-signal tier B) ──────────

SECTION_4206 = GateBSection(
    name="4206",
    match=SectionMatch(prefixes=("4.2.6.",)),
    # These explicitly encoded stop predicates do not repeat drug keywords.
    # Pin full identities: repeated a/b/c coordinates include initiation clauses.
    force_include_ids={
        "4.2.6.A-1": frozenset({
            "4.2.6.A-1.a#9787d587",
            "4.2.6.A-1.(1)#72e47d24",
            "4.2.6.A-1.(2)#30e012d8",
            "4.2.6.A-1.(3)#89477346",
            "4.2.6.A-1.(4)#dcfc2909",
            "4.2.6.A-1.b#3b2664e6",
            "4.2.6.A-1.(1)#8539914f",
            "4.2.6.A-1.(2)#13f4b28c",
            "4.2.6.A-1.(3)#0c2b0e3f",
            "4.2.6.A-1.(1)#52b1f15a",
            "4.2.6.A-1.(2)#75f092ee",
            "4.2.6.A-1.d#378dc004",
            "4.2.6.A-1.(3)#b3d97c76", "4.2.6.A-1.a#592aef98",
            "4.2.6.A-1.b#bbd37380", "4.2.6.A-1.c#b5a513b6",
        }),
        "4.2.6.B-1": frozenset({"4.2.6.B-1.(2)#df3e5cd0"}),
        "4.2.6.B-3": frozenset({
            "4.2.6.B-3.(1)#f26d9b57", "4.2.6.B-3#dde3c8f6",
            "4.2.6.B-3#11e1f077", "4.2.6.B-3#de2f2b31",
            "4.2.6.B-3.ç#269f3195",
        }),
        "4.2.6.A-5": frozenset({
            "4.2.6.A-5.a#7420864e",
            "4.2.6.A-5.b#7b829f92",
            "4.2.6.A-5.c#843b4071",
            "4.2.6.A-5.(2)#583eda78", "4.2.6.A-5.(3)#a8cf7ca9",
        }),
        "4.2.6.A-4": frozenset({
            "4.2.6.A-4.b#c166b1e4", "4.2.6.A-4.(5)#b34205e7", "4.2.6.A-4.(6)#b1fc17e1",
        }),
        "4.2.6.A-3": frozenset({
            "4.2.6.A-3.(2)#7ed65fce", "4.2.6.A-3.a#ae56e068",
            "4.2.6.A-3.b#30c6f092", "4.2.6.A-3.c#62c61a16",
            "4.2.6.A-3.ç#89b3cb7c",
        }),
    },
    drug_keywords=(
        "buyume hormonu", "büyüme hormonu", "somatropin", "somatrogon",
        "mecasermin", "rhigf", "igf-1", "igf1", "increlex", "turner",
        "laron", "somatotropin", "ilaç", "ilac", "rapor", "reçete", "recete",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.6",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4206.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4206_manifest.json",
    tier_a_overrides=(
        TierOverride(
            clause_ids=frozenset({
                "4.2.6.A-2.(5)#2cdeafe7", "4.2.6.A-3.(1)#df7dccc5", "4.2.6.B-2.(1)#e92a7dce", "4.2.6.A.(1)#e2d1c50d", "C003965",
                "4.2.6.A-1.(1)#e947d7a0", "C003964", "4.2.6.A-1.(2)#a3b772ff", "4.2.6.A-4.(2)#e8666e0c", "4.2.6.A-5.(4)#5cdc40bd",
                "4.2.6.B.(1)#ec207e24",
            }),
            tier="A",
            inn_label="buyume_hormonu",
        ),
    ),
    token_promotions=(
        TokenPromotion(
            tokens=("endokrinoloji", "saglik kurulu", "sağlık kurulu"),
            target_tier="B",
            inn_label="buyume_hormonu",
            require_token_match=True,
        ),
    ),
    skip_base_classifier=True,
)

# ── §4.2.9 + §4.2.27 — ESA + coagulation (multi-section, clause overrides) ────

SECTION_4209_4227 = GateBSection(
    name="4209_4227",
    match=SectionMatch(prefixes=("4.2.9", "4.2.27")),
    drug_keywords=(
        "eritropoietin", "epoetin", "darbepoetin", "roksadustat",
        "etelkalsedid", "etelcalcetide", "hemofil", "faktör", "factor vii",
        "factor viii", "factor ix", "von willebrand", "feiba", "protrombin",
        "anti rh", "anti-rh", "emicizumab", "albumin", "ilaç", "ilac",
        "rapor", "reçete", "recete", "anemi", "hematoloji", "nefroloji",
        "diyaliz",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.9,4.2.27",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4209_4227.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4209_4227_manifest.json",
    tier_a_overrides=(
        TierOverride(
            clause_ids=frozenset({
                "4.2.9.A.(3)#a9d0cf5b", "4.2.9.A.(4)#ed1d5fdf", "4.2.9.A-1.(1)#bb9d603f", "4.2.9.A-1.(2)#685f1394", "C004143",
                "C004145", "4.2.9.E.(6)#70e7cc67",
            }),
            tier="A",
            inn_label="esa",
        ),
        TierOverride(
            clause_ids=frozenset({
                "4.2.27.A.b#dd809964", "4.2.27.A.(2)#3dee23b2", "C006255", "4.2.27.A.a#0248d98e", "4.2.27.A.b#7aead70a",
                "C006264", "4.2.27.A.a#3d54d6c8", "4.2.27.A.b#bbc2b66c", "4.2.27.A.(6)#3794fbde", "4.2.27.A.a#dab473f2",
                "4.2.27.A.(7)#94ac5cb1", "4.2.27.B.(1)#2e11fcb9", "4.2.27.B.(2)#5548f8d0",
            }),
            tier="A",
            inn_label="koagulasyon_faktoru",
        ),
    ),
    tier_b_overrides=(
        TierOverride(
            clause_ids=frozenset({
                "C006235", "C006244", "4.2.27.A.a#64f0fd2c", "C006266", "4.2.27.A.(2)#23e717e6",
                "4.2.27.D.(2)#16954b24",
            }),
            tier="B",
            inn_label="koagulasyon_faktoru",
        ),
    ),
    token_promotions=(
        TokenPromotion(
            tokens=("eritropoietin", "epoetin", "darbepoetin", "roksadustat", "etelkalsedid"),
            target_tier="A",
            inn_label="esa",
            section_prefix="4.2.9",
        ),
        TokenPromotion(
            tokens=("hemofil", "faktör", "factor", "von willebrand", "feiba", "protrombin", "anti rh", "immün tolerans"),
            target_tier="A",
            inn_label="koagulasyon_faktoru",
            section_prefix="4.2.27",
        ),
    ),
    in_force_filtering=True,
    in_force_section_filter="4.2.27",
    requires_signal_for_export=True,
    in_force_pass_through=True,
    per_subsection_totals=True,
)

# ── §4.2.10 — lysosomal storage disease (demote_a_to_c + clause overrides) ───

SECTION_4210 = GateBSection(
    name="4210",
    match=SectionMatch(prefixes=("4.2.10",), exclude_prefixes=("4.2.100",)),
    drug_keywords=(
        "gaucher", "fabry", "pompe", "niemann", "mukopolisakkaridoz",
        "mukopolis", "lizozomal", "depo hastalık", "enzim replasman",
        "enzim tedavi", "eliglustat", "miglustat", "migalastat",
        "imiglukerase", "agalsidase", "laronidase", "idursulfase",
        "galsulfase", "elosulfase", "alglukosidase", "ilaç", "ilac",
        "rapor", "reçete", "recete",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.10",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4210.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4210_manifest.json",
    tier_a_overrides=(
        TierOverride(
            clause_ids=frozenset({
                "4.2.10.A.(2)#4d260861", "4.2.10.A-3.(2)#92224da8", "C004265", "4.2.10.A-4.(1)#7ce6180e", "C004307",
                "4.2.10.B-3.(1)#3e5d6616", "4.2.10.C-2.(3)#f3cd0246", "C004371", "4.2.10.C-3.(1)#7cd99d26", "C004379",
                "4.2.10.Ç-2.(1)#cdd9ecde", "C004387", "4.2.10.D-2.(1)#ad1b5117",
            }),
            tier="A",
            inn_label="lsd_ilac",
        ),
    ),
    demote_a_to_c=True,
    in_force_filtering=True,
    in_force_section_filter="4.2.10",
    requires_signal_for_export=False,
    in_force_pass_through=True,
    has_audit=True,
)

# ── §4.2.13 — viral hepatitis (regex tier-B + clause overrides + shared merge) ──

SECTION_4213 = GateBSection(
    name="4213",
    match=SectionMatch(prefixes=("4.2.13",)),
    drug_keywords=(
        "ilaç", "ilac", "antiviral", "interferon", "ribavirin", "entekavir",
        "tenofovir", "lamivudin", "sofosbuvir", "ledipasvir", "glekaprevir",
        "pibrentasvir", "velpatasvir", "pegile", "peginterferon", "hepatit",
        "endikasyon", "rapor", "reçete", "recete",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.13",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4213.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4213_manifest.json",
    tier_b_overrides=(
        TierOverride(
            clause_ids=frozenset({"4.2.13.1.e#50a8edb0", "4.2.13.1.(5)#6281d4b1"}),
            tier="B",
            inn_label="hepatit_ilac",
        ),
    ),
    token_promotions=(
        TokenPromotion(
            tokens=(
                "entekavir", "tenofovir", "lamivudin", "sofosbuvir",
                "ledipasvir", "glekaprevir", "pibrentasvir", "pegile interferon",
                "peginterferon",
            ),
            target_tier="A",
            inn_label="hepatit_ilac",
        ),
    ),
    in_force_filtering=True,
    in_force_section_filter="4.2.13",
    requires_signal_for_export=False,
    in_force_pass_through=True,
    has_audit=True,
)

# ── §4.2.13 + §4.2.16 — hepatitis + formula/metabolic (dual regex gating) ────

SECTION_4213_4216 = GateBSection(
    name="4213_4216",
    match=SectionMatch(prefixes=("4.2.13", "4.2.16")),
    drug_keywords=(
        "ilaç", "ilac", "antiviral", "interferon", "ribavirin", "entekavir",
        "tenofovir", "lamivudin", "sofosbuvir", "ledipasvir", "glekaprevir",
        "pibrentasvir", "velpatasvir", "pegile", "peginterferon", "mama",
        "formül", "formul", "metabolik", "kistik fibrozis", "çölyak",
        "coelyak", "hepatit", "endikasyon", "rapor", "reçete", "recete",
        "biyobenzer", "biosimilar",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.13,4.2.16",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4213_4216.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4213_4216_manifest.json",
    token_promotions=(
        TokenPromotion(
            tokens=(
                "entekavir", "tenofovir", "lamivudin", "sofosbuvir",
                "ledipasvir", "glekaprevir", "pibrentasvir", "pegile interferon",
                "peginterferon",
            ),
            target_tier="A",
            inn_label="hepatit_ilac",
            section_prefix="4.2.13",
        ),
        TokenPromotion(
            tokens=("mama", "formül", "formul", "metabolik", "kistik fibrozis", "çölyak", "coelyak", "gluten"),
            target_tier="A",
            inn_label="metabolik_mama",
            section_prefix="4.2.16",
        ),
    ),
    per_subsection_totals=True,
)

# ── §4.2.15 — antithrombotic (signal_score + in_force pass-through) ──────────

SECTION_4215 = GateBSection(
    name="4215",
    match=SectionMatch(prefixes=("4.2.15.",)),
    drug_keywords=(
        "klopidogrel", "plavix", "dabigatran", "rivaroksaban", "apiksaban",
        "edoksaban", "tikagrelor", "prasugrel", "ranolazin",
        "asetilsalisilik", "aspirin", "antikoagülan", "antikoagulan",
        "antiplatelet", "stent", "koroner", "miyokard", "angina",
        "kardiyoloji", "ilaç", "ilac", "rapor", "reçete", "recete",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.15",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4215.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4215_manifest.json",
    token_promotions=(
        TokenPromotion(
            tokens=(
                "klopidogrel", "dabigatran", "rivaroksaban", "apiksaban",
                "edoksaban", "tikagrelor", "prasugrel", "ranolazin",
                "asetilsalisilik", "stent", "koroner",
            ),
            target_tier="A",
            inn_label="antitrombotik",
        ),
    ),
    in_force_filtering=True,
    in_force_section_filter="4.2.15",
    in_force_pass_through=True,
    signal_score=True,
    sort_keys=("signal_score", "clause_id"),
    sort_descending=(True,),
)

# ── §4.2.17 — osteoporosis (standard token promotion, uses gate_b_core) ──────

SECTION_4217 = GateBSection(
    name="4217",
    match=SectionMatch(prefixes=("4.2.17",)),
    drug_keywords=(
        "osteoporoz", "bifosfonat", "alendronat", "risedronat", "zoledronat",
        "denosumab", "kalsitonin", "teriparatid", "romosozumab", "raloksifen",
        "stronsiyum", "kmy", "kemik mineral", "ilaç", "ilac", "rapor",
        "reçete", "recete",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.17",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4217.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4217_manifest.json",
    token_promotions=(
        TokenPromotion(
            tokens=(
                "bifosfonat", "denosumab", "kalsitonin", "teriparatid",
                "romosozumab", "raloksifen", "stronsiyum", "osteoporoz",
            ),
            target_tier="A",
            inn_label="osteoporoz_ilac",
        ),
    ),
)

# ── §4.2.18 + §4.2.36 — obesity + Parkinson (phrase promotion) ────────────────

SECTION_4218_4236 = GateBSection(
    name="4218_4236",
    match=SectionMatch(prefixes=("4.2.18", "4.2.36")),
    drug_keywords=(
        "orlistat", "obez", "obesity", "parkinson", "apomorfin", "kabergolin",
        "entakapon", "tolkapon", "tolcapone", "amantadin", "rasajilin",
        "rasagilin", "pergolid", "pramipexol", "ropinirol", "bornaprin",
        "nöroloji", "geriatri", "endokrinoloji", "metabolizma", "bmi",
        "ilaç", "ilac", "rapor", "reçete", "recete", "ekstrapiramidal",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.18,4.2.36",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4218_4236.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4218_4236_manifest.json",
    token_promotions=(
        TokenPromotion(
            tokens=("orlistat", "birer aylık"),
            target_tier="A",
            inn_label="orlistat",
            section_prefix="4.2.18",
        ),
        TokenPromotion(
            tokens=(
                "apomorfin", "kabergolin", "entakapon", "tolkapon", "amantadin",
                "rasajilin", "pergolid", "pramipexol", "ropinirol", "bornaprin",
            ),
            target_tier="A",
            inn_label="parkinson_ilac",
            section_prefix="4.2.36",
        ),
    ),
    requires_signal_for_export=False,
    per_subsection_totals=True,
)

# ── §4.2.19 — migraine (simplest standard pattern) ───────────────────────────

SECTION_4219 = GateBSection(
    name="4219",
    match=SectionMatch(prefixes=("4.2.19",)),
    drug_keywords=(
        "migren", "triptan", "topiramat", "topiramate", "sumatriptan",
        "zolmitriptan", "rizatriptan", "ilaç", "ilac", "rapor", "reçete",
        "recete", "nöroloji",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.19",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4219.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4219_manifest.json",
    token_promotions=(
        TokenPromotion(
            tokens=("triptan", "topiramat", "topiramate", "migren"),
            target_tier="A",
            inn_label="migren_ilac",
        ),
    ),
)

# ── §4.2.24 — asthma/COPD/allergy (signal_score + in_force) ───────────────────

SECTION_4224 = GateBSection(
    name="4224",
    match=SectionMatch(prefixes=("4.2.24.",)),
    drug_keywords=(
        "formeterol", "salmeterol", "vilanterol", "montelukast", "zafirlukast",
        "mepolizumab", "benralizumab", "omalizumab", "dupilumab", "tezepelumab",
        "indakaterol", "tiotropium", "glikopironyum", "flutikazon", "budesonid",
        "beclometazon", "laba", "lama", "inhale kortikosteroid",
        "nasal kortikosteroid", "antihistaminik", "azelastin", "astım", "astim",
        "koah", "obstrüktif", "alerji", "ilaç", "ilac", "rapor", "reçete",
        "recete",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.24",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4224.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4224_manifest.json",
    token_promotions=(
        TokenPromotion(
            tokens=(
                "formeterol", "salmeterol", "vilanterol", "montelukast",
                "zafirlukast", "mepolizumab", "benralizumab", "omalizumab",
                "indakaterol", "tiotropium", "flutikazon", "budesonid", "azelastin",
            ),
            target_tier="A",
            inn_label="solunum_ilac",
        ),
    ),
    in_force_filtering=True,
    in_force_section_filter="4.2.24",
    in_force_pass_through=True,
    signal_score=True,
    sort_keys=("signal_score", "clause_id"),
    sort_descending=(True,),
)

# ── §4.2.34 — multiple sclerosis (in_force floor fallback) ────────────────────

SECTION_4234 = GateBSection(
    name="4234",
    match=SectionMatch(prefixes=("4.2.34",)),
    drug_keywords=(
        "multipl skleroz", "ms hast", "beta interferon", "interferon",
        "glatiramer", "teriflunomid", "dimetil fumarat", "fingolimod",
        "natalizumab", "okrelizumab", "ocrelizumab", "kladribin", "cladribine",
        "alemtuzumab", "fampiridin", "ilaç", "ilac", "rapor", "reçete",
        "recete", "nöroloji", "edss",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.34",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4234.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4234_manifest.json",
    token_promotions=(
        TokenPromotion(
            tokens=(
                "beta interferon", "glatiramer", "teriflunomid", "dimetil fumarat",
                "fingolimod", "natalizumab", "okrelizumab", "kladribin",
                "alemtuzumab", "fampiridin",
            ),
            target_tier="A",
            inn_label="ms_ilac",
        ),
    ),
    in_force_filtering=True,
    in_force_section_filter="4.2.34",
    in_force_pass_through=True,
)

# ── §4.2.35 + §4.2.37 — neuropathic pain + acromegaly (most bespoke) ─────────

SECTION_4235_4237 = GateBSection(
    name="4235_4237",
    match=SectionMatch(prefixes=("4.2.35", "4.2.37")),
    drug_keywords=(
        "nöropatik", "neuropatik", "fibromiyalji", "gabapentin", "pregabalin",
        "duloksetin", "lipoik", "kapsaisin", "akromegali", "pegvisomant",
        "oktreotid", "octreotide", "lanreotid", "lanreotide", "somatostatin",
        "igf-1", "ilaç", "ilac", "rapor", "reçete", "recete", "endikasyon",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.35,4.2.37",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4235_4237.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4235_4237_manifest.json",
    tier_a_overrides=(
        TierOverride(
            clause_ids=frozenset({
                "4.2.35.A.(3)#4810c819", "4.2.35.A.b#9b19ef45", "4.2.37.A.(2)#ef5cfc78", "4.2.37.A.(3)#4be6d8e5", "4.2.37.A.(5)#b9399d4b",
            }),
            tier="A",
            inn_label="akromegali_ilac",
        ),
    ),
    tier_b_overrides=(
        TierOverride(
            clause_ids=frozenset({"4.2.35.B.(2)#56d94324"}),
            tier="B",
            inn_label="pregabalin",
        ),
    ),
    force_c_sections=("4.2.35", "4.2.37"),  # both sections force C on keyword branches
    superseded_ids=frozenset({
        "C006707", "C006708", "C006709", "C006710", "C006711",
        "C006714", "C006715", "C006726",
    }),
    force_include_ids={
        "4.2.35": frozenset({
            "C006706", "C006712", "C006713", "C006716", "C006723",
            "C006725", "C006727", "C006729",
        }),
    },
    force_include_section="4.2.37",
    per_subsection_totals=True,
)

# ── §4.2.38 — diabetes (simplest passthrough, reconciled manifest) ───────────

SECTION_4238 = GateBSection(
    name="4238",
    match=SectionMatch(prefixes=("4.2.38",)),
    drug_keywords=(
        "diyabet", "metformin", "sulfonil", "insülin", "insulin", "pioglitazon",
        "sglt2", "sglt-2", "dpp-4", "dpp4", "gliptin", "eksenatid", "exenatide",
        "liksisenatid", "lixisenatide", "degludec", "repaglinid", "nateglinid",
        "akarboz", "glukozidaz", "ilaç", "ilac", "rapor", "reçete", "recete",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.38",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4238.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4238_manifest.json",
    in_force_filtering=True,
    in_force_section_filter="4.2.38",
    in_force_pass_through=True,
)


# ── §4.2.14.C — oncology specials (was phase5 / a1 repair) ───────────────────

SECTION_4214C = GateBSection(
    name="4214c",
    match=SectionMatch(prefixes=("4.2.14.C",)),
    drug_keywords=(),
    manifest_version="canonical-v1",
    manifest_section_id="4.2.14.C",
    corpus_csv=f"{_CORPUS_DIR}/L4.2_drug_indication_4.2.14.C.csv",
    manifest_path=f"{_MANIFEST_DIR}/L4.2_drug_indication_4.2.14.C_manifest.json",
    requires_signal_for_export=False,
    parquet_in_force_only=True,
    filter_rules_by_section_prefix=False,
)


# ── Track F — non-drug Gate B (same engine as drug) ───────────────────────────

SECTION_PAYMENT_22 = GateBSection(
    name="payment_22",
    match=SectionMatch(prefixes=("2.2",)),
    drug_keywords=(
        "tanıya dayalı işlem",
        "hizmet başına ödeme",
        "hizmet başı",
        "ek-2/c",
        "ek-2/b",
        "ek-2/a",
        "faturalandır",
        "ödeme yöntemi",
        "yatarak tedavi",
        "ayakta tedavi",
        "basamak",
        "gündüz yatak",
        "yatak bedeli",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="2.2",
    corpus_csv=f"{_CORPUS_DIR}/L2.2_payment_method_prose.csv",
    manifest_path=f"{_MANIFEST_DIR}/L2.2_payment_method_encoded_manifest.json",
    rule_set_id="payment_method_2_2",
    extra_manifest="payment_cross_refs",
    parquet_in_force_only=True,
    requires_signal_for_export=True,
    filter_rules_by_section_prefix=False,
)

SECTION_MATERIAL_31_32 = GateBSection(
    name="material_31_32",
    match=SectionMatch(prefixes=("3.1", "3.2")),
    drug_keywords=(
        "ayrıca faturalandır",
        "faturalandırılmayacak",
        "faturalandırılamaz",
        "ayrı faturalandır",
        "ayrıca faturalandırılamaz",
        "ayrıca faturalandırılmaz",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="3.1,3.2",
    corpus_csv=f"{_CORPUS_DIR}/L1.4_material_bundling_prose.csv",
    manifest_path=f"{_MANIFEST_DIR}/L1.4_material_bundling_encoded_manifest.json",
    rule_set_id="material_bundling_prose",
    extra_manifest="material_buckets",
    parquet_in_force_only=True,
    requires_signal_for_export=True,
    filter_rules_by_section_prefix=False,
    admit_deontic_modalities=frozenset({"MANDATORY"}),
)

SECTION_COPAY_18 = GateBSection(
    name="copay_18",
    match=SectionMatch(prefixes=("1.8",)),
    drug_keywords=(
        "katılım payı",
        "katilim payi",
        "muayene",
        "eczane",
        "ek-1/a",
        "ek-4/d",
        "istisna",
        "muaf",
    ),
    manifest_version="canonical-v1",
    manifest_section_id="1.8",
    corpus_csv=f"{_CORPUS_DIR}/L1.8_copay_exemption_prose.csv",
    manifest_path=f"{_MANIFEST_DIR}/L1.8_copay_exemption_encoded_manifest.json",
    rule_set_id="copay_general_1_8",
    extra_manifest="copay_compositor",
    parquet_in_force_only=True,
    requires_signal_for_export=False,
    filter_rules_by_section_prefix=False,
)


# ── Registry ─────────────────────────────────────────────────────────────────

ALL_SECTIONS: dict[str, GateBSection] = {
    s.name: s
    for s in [
        SECTION_4201,
        SECTION_4206,
        SECTION_4209_4227,
        SECTION_4210,
        SECTION_4213,
        SECTION_4213_4216,
        SECTION_4214C,
        SECTION_4215,
        SECTION_4217,
        SECTION_4218_4236,
        SECTION_4219,
        SECTION_4224,
        SECTION_4234,
        SECTION_4235_4237,
        SECTION_4238,
        SECTION_PAYMENT_22,
        SECTION_MATERIAL_31_32,
        SECTION_COPAY_18,
    ]
}
