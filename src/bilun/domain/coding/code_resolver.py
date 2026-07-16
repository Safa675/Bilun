"""Hospital-internal-code → SUT code resolver (Phase 2 coder).

Resolution order:
  1. Frozen mapping table (``data/coding/hospital_to_sut.csv``) — O(1).
  2. Candidate generator — normalized-name match against EK-2B ``by_code``.
  3. LLM-assisted (no-match tail) — produced off-module by subagents; results
     land in ``data/coding/crosswalk_review.csv`` and must be reviewed before
     promotion to the frozen table.

See package docstring and ``plans/data/2026-07-16-finans-cleanup-and-coder-plan.md``.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.bilun.domain.catalog import load_sut_catalog

PROJECT_ROOT = Path(__file__).resolve().parents[4]
FROZEN_MAPPING_PATH = PROJECT_ROOT / "data" / "coding" / "hospital_to_sut.csv"

# ═══════════════════════════════════════════════════════════════════════════
# Public types
# ═══════════════════════════════════════════════════════════════════════════


class ResolutionMethod:
    """How a resolution was reached. Stable string constants."""

    FROZEN = "frozen"          # found in hospital_to_sut.csv (reviewed)
    EXACT = "exact"            # normalized name == EK-2B name exactly
    TOKEN_PREFIX = "token_prefix"  # leading tokens of desc match an EK-2B name
    NO_MATCH = "no_match"      # generator found nothing; candidate for LLM
    LLM_PENDING = "llm_pending"  # LLM result exists but reviewed=FALSE


@dataclass(frozen=True)
class CategoryHint:
    """Optional category hint to narrow the candidate space.

    ``LAB`` restricts to L-prefixed SUT codes (lab tests);
    ``RADIOLOGY`` restricts to R-prefixed SUT codes (imaging);
    ``PROCEDURE``/``DRUG``/``MATERIAL``/``UNCLEAR`` search the full catalog
    (procedures are numeric, drugs/materials use their own catalogs).
    """

    kind: str  # LAB | PROCEDURE | DRUG | MATERIAL | RADIOLOGY | HOTEL | UNCLEAR

    def code_predicate(self) -> str:
        if self.kind == "LAB":
            return "L"
        if self.kind == "RADIOLOGY":
            return "R"
        return ""  # PROCEDURE/DRUG/MATERIAL/UNCLEAR → no prefix filter


@dataclass(frozen=True)
class Resolution:
    """Result of resolving one hospital code to a SUT code.

    For DRUG resolutions, ``drug_identity`` carries the full EK-4A identity
    (kamu_no + barcode + equivalence_group) — the drug_indication motor needs
    all three, not just one code.
    For MATERIAL resolutions mapped to a bundled consumable (no EK-3 code),
    ``sut_code`` is None but ``reviewed`` may be True with rationale recorded.
    """

    hospital_code: str
    description: str
    sut_code: str | None
    method: str                # ResolutionMethod.*
    confidence: float          # 0.0–1.0; frozen/exact=1.0, token_prefix≤0.8
    candidates: list[dict[str, Any]] = field(default_factory=list)
    sut_name: str | None = None
    reviewed: bool = False     # True only if the mapping is in the frozen table
    drug_identity: dict[str, str] | None = None  # {kamu_no, barcode, equivalence_group}
    category: str = ""         # LAB/PROCEDURE/DRUG/MATERIAL/UNCLEAR


# ═══════════════════════════════════════════════════════════════════════════
# Normalizer — Turkish-lower + ASCII-fold + strip non-alphanumerics.
# Proven in the 2026-07-16 probe: bridges "Alanine Aminotransferase" ↔
# "Alanin aminotransferaz" after folding. One canonical normalizer, reused.
# ═══════════════════════════════════════════════════════════════════════════

_TR_LOWER_MAP = str.maketrans("İIŞĞÜÖÇışğüöç", "iisguocisguoc")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
# Turkish suffix stemming for token matching. Clinical names inflect:
# "muayene" (query) vs "muayenesi" (EK-2B name). Stripping common suffixes
# collapses these to the same token. Conservative — only productive suffixes.
_TR_SUFFIXES = ("ler", "lar", "si", "ti", "ni", "lerdir", "larda", "lerinde")


def _stem(token: str) -> str:
    """Crude Turkish stemmer: strip a trailing common suffix if the stem
    remaining is still ≥4 chars. 'muayenesi'→'muayene', 'testleri'→'test'."""
    for suf in _TR_SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 4:
            return token[: -len(suf)]
    return token


def normalize_name(name: str | None) -> str:
    """Normalize a Turkish clinical/procedure name for matching.

    Lowercases (Turkish-aware), folds Turkish chars to ASCII, strips
    punctuation/whitespace-noise. "Alanine Aminotransferase (ALT)" →
    "alanine aminotransferase alt". Does NOT translate English→Turkish —
    that gap is the LLM tier's job.
    """
    if name is None:
        return ""
    s = str(name).strip().translate(_TR_LOWER_MAP).lower()
    s = _NON_ALNUM.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _meaningful_tokens(norm: str, min_len: int = 4) -> list[str]:
    """Tokens long enough to be discriminative, with Turkish stemming applied.

    Drops stop-words ('ve','ile','bir') and stems inflected forms so
    'muayene' (query) matches 'muayenesi' (EK-2B). Tokens <4 chars after
    stemming are dropped.
    """
    stop = {"ve", "ile", "bir", "icin", "gore", "olan", "her", "the", "and", "for"}
    out = []
    for t in norm.split():
        if len(t) < min_len or t in stop:
            continue
        s = _stem(t)
        if len(s) >= min_len and s not in stop:
            out.append(s)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Category classifier (v5, Phase 4) — assigns a finans line to one of
# LAB / PROCEDURE / DRUG / MATERIAL / RADIOLOGY / HOTEL / UNCLEAR.
# v5 recovers 124 codes the v4 classifier left in UNCLEAR: adds RADIOLOGY
# (imaging + nuclear med + physiotherapy → EK-2B R-prefixed), HOTEL (bed
# fees, companion meals — genuinely not SUT items), and broadens MATERIAL
# (sutures, stockings, probes, staplers), LAB (blood gas, PCR, hormones),
# DRUG (Gaviscon, Enox/Oksapar), PROCEDURE (surgical ops).
# ═══════════════════════════════════════════════════════════════════════════

_HOTEL_RE = re.compile(
    r"yatak|refakat|ücret|gelir|müşahede|musahede|hasta takip|"
    r"diğer hizmet|diger hizmet|ek hizmet|fert tamir|bakım hizmeti|"
    r"kafeterya|kahvaltı|yemek|çamaşır|camasir",
    re.IGNORECASE,
)

# RADIOLOGY: imaging (BT/MR/USG/X-ray), nuclear medicine, physiotherapy.
# Physiotherapy C970xxx/C991xxx codes live in EK-2B (not R-prefix, but
# routing through RADIOLOGY keeps them out of the LAB/PROCEDURE buckets
# where they'd misroute). R-prefix filtering only applies when the code
# predicate is used — physiotherapy just won't match an R-prefix and will
# fall through to the no-prefix generator path.
_RADIOLOGY_RE = re.compile(
    r"grafisi|radyografi|\bbt\b|\bmr\b(?!\s*[\d.,]+\s*(?:mg|mcg|gr|iu))|\bmrg\b|\busg\b|röntgen|rontgen|"
    r"floroskop|tomografi|mamografi|dopler|doppler|ekokardiyograf|"
    r"anjiografi|anjiyograf|sintigraf|scintigraf|"
    r"galyum|ga-68|pet-ct|soğuk ve ısıtıcı|ısıtıcı|enfraruj|galvani|"
    r"faradi|tens|diadinami|frekanslı akım|lazer terapi|fizik tedavi|"
    r"ses odyometr|odyometr|panoramik film|panoramik|\brdus\b|nebülazatör|nebulazator",
    re.IGNORECASE,
)

_DRUG_RE = re.compile(
    r"\b\d+\s*(mg|mcg|gr|iu)\b|tablet|ampul|flakon|kapsül|kapsul|film kaplı|"
    r"liyofilize|şurup|surup|merhem|krem|sprey|damla|inhaler|inhalasyon|"
    r"enjeksiyon|infüzyon|infuzyon|perfüzyon|perfuzyon|süspansiyon|suspansiyon|"
    r"çözelti|cozelti|solüsyon|solusyon|pomad|draje|süpozituar|supozituar|"
    # IV solutions / generic fluids
    r"\bpol\.|\bpol |bizotonik|bizoleks|\bdeksroz|rizolen|ringer|"
    r"\bnacl\b|sodyum klorur|%\d|ml pp|ml pvc|ml torba|setsiz|setli|"
    # Phase 4 additions
    r"enox|anti-xa|uluslararası ünite|gaviscon|thilo-tears|\bjel\b|likit|"
    r"sedasyon|aneljezi|analjezi|iv-pca",
    re.IGNORECASE,
)

_MATERIAL_RE = re.compile(
    r"ref:|medtronic|covidien|boston|sorin|teleflex|stryker|pfm|nextech|"
    r"alpheta|octacare|bıçakçılar|bicakcilar|fresenius|bd\b|abbott|"
    r"seti$|seti,|set\b|set,|sistem|sonda|kateter|katater|kanül|kanul|"
    r"trokar|kelepçe|kelepce|vida|plak|mesh|yama|filtre|örgü|torba|poşet|"
    r"süngeri|sungeri|öreü|ortuz|tüp\b|tup\b|tel\b|kılavuz|kilavuz|bandı|"
    r"örtü|örtü$|ortu\b|soket|firman|branül|branul|pansuman|nefleks|neofleks|"
    r"musluk|valf|valfi|iğne|igne|elektrot|stripi|strip\b|bağlama bezi|"
    r"baglama bezi|altı bağlama|maske|oksijen|cap\b|kilit|klip|clip|"
    r"endoskopik ağızlık|endoskopik lineer|forseps|makas|pens|"
    r"reyofil|reyof|basınç|basinc|lineer kesici|"
    # Phase 4 additions: sutures, surgical consumables, brands
    r"sütür|sutur|pegelak|vicryl|ipek|monocryl|ethicon|medeks|rüsch|rusch|"
    r"sarfhan|varimo|varimed|plasti-med|plasti med|hudson|fiab|wisitat|"
    r"cair|tyco|varis çorabı|antiembol|parmank probu|parmak probu|"
    r"oksijensör|oksisensör|aspiratör|stapler|stapleri|cilt stapler|koter|"
    r"disposable|karton ördek|mandren|stylet|perfüzör|enjektör|hortum|"
    r"flowmetre|adaptör|triflo|solunum egzersiz|bandaj|kılıf|numume|"
    # Phase 4.1 additions: PPE, orthopedic splints/braces, gowns, bandages
    r"box önlüğü|onlugu|önlük|onluk|alçı|alcı|terlik|bacaklık|dizlik|"
    r"ateli|atel |sargı|sargi|lavman|enema|laksatif|koruyucu ekipman|"
    r"covid koruyucu|karton sürgü|surgu|kord yüzüklü|imaging systems protector|"
    r"karl storz|karl storz|morsacyberg|morsa|"
    # Phase 5 additions: brand-only consumables (actual source-data spellings,
    # including the "Steri-Stip" typo — source says Stip not Strip)
    r"yara retraktörü|yara retractor|boyunkluk|boyunluk|damar askısı|damar askisi|"
    r"steri-stip|steri-strip|cilt kapatma|penroz|penrose|alet cebi|"
    r"mıs kompresör|mis kompresor|kompresör|kompresor|kılıç|kilic|hook|"
    r"nebulizatör|nebulizator|inhalasyon|spirometre|"
    r"şerit|serit|stripper|venöz|venöz|fire |filtreli|"
    r"punch|biyopsi iğnesi|biyopsi ignesi|tru-cut|trucut|"
    r"retraktör|retractor|distraktör|distraktor|ekspandr|ekspandor|"
    # Phase 5: surgical stapler/cartridge brand names (Ethicon Endo-Surgery)
    r"echelon|reload|rotikulatör|rotikulator|endogia|endo gia|endo clip|"
    r"endocutter|synchroseal|sealer|ligating clip|energy device",
    re.IGNORECASE,
)

_LAB_RE = re.compile(
    r"tam kan|sayımı|sayimi|hemogram|fosfataz|aminotransferase|aminotransferaz|"
    r"transaminaz|reaktif protein|crp|glukoz|glikoz|kolesterol|trigliserid|tsh|"
    r"kreatinin|üre\b|ure\b|albümin|albumin|sodyum|potasyum|kalsiyum|demir\b|"
    r"ferritin|hemoglobin|lenfosit|nötrofil|notrofil|trombosit|eritrosit|"
    r"lokos|mcv|rdw|mpv|bilirubin|ast\b|alt\b|tiroid|tiroksin|tiroglobulin|"
    r"insülin|insulin|hba1c|sedim|koagülasyon|inr|ptz|pt\b|aptt|türbidite|"
    r"immünhistokimyasal|histokimyasal|sitoloji|patoloji|boyama|panel|tetkik|"
    r"testi|analizi|kültür|kultur|antijen|antikor|magnezyum|lipaz|amilaz|"
    r"troponin|ddimer|d-dimer|ggt|gama glutamil|protein|klor\b|\bcl\b|"
    r"vitamin|idrar analizi|ekg|"
    # Phase 4 additions: blood gas, PCR, hormones, crossmatch
    r"folik asit|triiodotironin|\bt3\b|\bt4\b|kinaz|\bck\b|kan grubu|"
    r"crossmatch|kan gazı|kan gazları|beta-hcg|koryonik|fosfor|"
    r"hidroksiprogesteron|pcr|\brna\b|transkriptaz|covid-19|sars-cov|"
    r"mikroskobik inceleme|gaita|"
    # Phase 4.1 additions: virology panels, hormones, co-pathology
    r"\bebv\b|ebna|\bvca\b|shbg|seks hormonu|parathormon|\bpth\b|hpv|"
    r"cotest|düzey hist|düzey hist",
    re.IGNORECASE,
)

_PROCEDURE_RE = re.compile(
    r"muayene|konsültasyon|konsultasyon|manevra|biyopsi|cerrahi|operasyon|"
    r"anestezi|revizyon|eksplorasyon|drenaj|debridman|insizyon|rezeksiyon|"
    r"endoskop|kolonoskop|gastroskop|poliklinik|vizit|kemoterapi|diyaliz|"
    r"radyoterapi|brakiterapi|müşahede|musahede|"
    # Phase 4 additions: surgical operations
    r"diskektomi|füzyon|fuzyon|stabiliz|monitörizasyon|monitorizasyon|"
    r"değerlendirme|degerlendirme|inceleme|sistektomi|mesane|diversiyon|"
    r"sempatektomi|plörektomi|plorektomi|vats|stend yerleştir|stent|"
    r"penil protez|elektrokoterizasyon|kontrollü analjezi|yaklaş\.|yaklas|"
    r"vertebraya|korreks|ortotopik|"
    # Phase 5 additions: abbreviated procedures
    r"serum takma|kan gazı alma|intravenöz\s|kriyoterapi|"
    r"sistoskopi|üretroskopi|uretroskopi|"
    r"dializ|diyaliz|hemodiyaliz|"
    r"reduksiyon|redüksiyon|manipülasyon|manipulasyon|"
    r"ekstraksiyon|ekstraksyon|çekimi|cekimi",
    re.IGNORECASE,
)


def classify_category(description: str) -> str:
    """Classify a finans line description into a SUT category.

    Returns one of: LAB, PROCEDURE, DRUG, MATERIAL, RADIOLOGY, HOTEL, UNCLEAR.

    Order matters (first match wins):
      1. HOTEL — checked first; "Yatak Ücreti" must not match MATERIAL "tel".
      2. RADIOLOGY — before DRUG (some imaging uses contrast "solüsyon").
      3. DRUG — before MATERIAL (a drug "Seti" ≠ a material "Seti").
      4. MATERIAL — before LAB ("Şeker Ölçüm Stripi" = material, not glucose).
      5. LAB, PROCEDURE.
      6. UNCLEAR — residual (stubborn descriptions + genuine edge cases).
    """
    d = str(description or "")
    if _HOTEL_RE.search(d):
        return "HOTEL"
    if _RADIOLOGY_RE.search(d):
        return "RADIOLOGY"
    if _DRUG_RE.search(d):
        return "DRUG"
    if _MATERIAL_RE.search(d):
        return "MATERIAL"
    if _LAB_RE.search(d):
        return "LAB"
    if _PROCEDURE_RE.search(d):
        return "PROCEDURE"
    return "UNCLEAR"


# ═══════════════════════════════════════════════════════════════════════════
# EK-2B name index — built once, cached. Maps normalized-name → list of
# (code, entry). Vectorizable source: the catalog's ``by_code`` dict.
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class _CatalogEntry:
    code: str
    name: str
    norm_name: str
    tokens: frozenset[str]


@lru_cache(maxsize=1)
def _ek2b_index() -> tuple[dict[str, list[_CatalogEntry]], list[_CatalogEntry]]:
    """Return (norm_name→entries index, all-entries list) for EK-2B.

    Cached for the process lifetime. Reuses ``load_sut_catalog`` (the same
    catalog the motors use) so candidate generation and motor lookups agree.
    """
    catalog = load_sut_catalog()
    by_code: dict[str, Any] = catalog["ek2b"]["by_code"]
    index: dict[str, list[_CatalogEntry]] = {}
    all_entries: list[_CatalogEntry] = []
    for code, entry in by_code.items():
        name = entry.get("name") or ""
        norm = normalize_name(name)
        if not norm:
            continue
        ce = _CatalogEntry(
            code=str(code),
            name=name,
            norm_name=norm,
            tokens=frozenset(_meaningful_tokens(norm)),
        )
        index.setdefault(norm, []).append(ce)
        all_entries.append(ce)
    return index, all_entries


# ═══════════════════════════════════════════════════════════════════════════
# Candidate generator (2.2) — the core. Vectorized over the EK-2B index.
# ═══════════════════════════════════════════════════════════════════════════


def build_candidates(
    description: str,
    hint: CategoryHint | None = None,
    *,
    max_candidates: int = 5,
) -> list[dict[str, Any]]:
    """Return ranked SUT candidates for a hospital description.

    Ranking: exact normalized-name match (confidence 1.0) → token-overlap
    Jaccard against EK-2B token sets (confidence = overlap). Capped at
    ``max_candidates``. A ``CategoryHint`` narrows to LAB (L-prefixed) or
    PROCEDURE (numeric) code spaces.

    This is pure catalog matching — no LLM, no network. The output feeds the
    resolver and, for low-confidence cases, the LLM review queue.
    """
    norm = normalize_name(description)
    if not norm:
        return []
    index, all_entries = _ek2b_index()
    prefix = hint.code_predicate() if hint else ""

    def _passes(code: str) -> bool:
        return code.startswith(prefix) if prefix else True

    # 1. Exact normalized-name match.
    exact: list[dict[str, Any]] = []
    for ce in index.get(norm, []):
        if _passes(ce.code):
            exact.append(
                {"code": ce.code, "name": ce.name, "confidence": 1.0, "why": "exact"}
            )
    if exact:
        return exact[:max_candidates]

    # 2. Token match against every EK-2B entry's token set. Two signals:
    #   - containment: all desc tokens appear in the entry (desc ⊆ entry).
    #     Catches "Poliklinik Muayene" ⊆ "Normal poliklinik muayenesi".
    #   - Jaccard overlap: fraction of shared tokens. Catches partial matches.
    # Containment is only trusted when the entry isn't much longer than the
    # query — otherwise a 1-token query ("kreatinin") would match every
    # entry containing that word ("5-Hidroksi.../Kreatinin", wrong). The
    # length-ratio gate keeps containment honest.
    desc_tokens = set(_meaningful_tokens(norm))
    if not desc_tokens:
        return []
    scored: list[tuple[float, _CatalogEntry]] = []
    for ce in all_entries:
        if not _passes(ce.code) or not ce.tokens:
            continue
        inter = desc_tokens & ce.tokens
        if not inter:
            continue
        union = desc_tokens | ce.tokens
        jaccard = len(inter) / len(union)
        # Containment: desc fully inside entry, AND entry has at most ~2.5x
        # desc's token count. For single-token queries, additionally require
        # the entry name to START with that token — "kreatinin" must not match
        # "albümin/kreatinin" (compound, different test). This prevents the
        # most dangerous failure mode: a confident wrong exact match.
        ratio_ok = len(ce.tokens) <= max(len(desc_tokens) * 2.5, len(desc_tokens) + 3)
        if len(desc_tokens) == 1:
            head_ok = ce.norm_name.split()[0] == next(iter(desc_tokens))
        else:
            head_ok = True
        contained = 1.0 if (desc_tokens.issubset(ce.tokens) and ratio_ok and head_ok) else 0.0
        score = max(jaccard, contained)
        if score >= 0.34:
            scored.append((score, ce))
    scored.sort(key=lambda t: (-t[0], t[1].code))
    return [
        {"code": ce.code, "name": ce.name, "confidence": round(s, 3), "why": "token"}
        for s, ce in scored[:max_candidates]
    ]


# ═══════════════════════════════════════════════════════════════════════════
# EK-4A drug index (Phase 3.1) — brand-name match. The catalog carries full
# identity (kamu_no, barcode, equivalence_group) which the drug_indication
# motor needs. finans brand names == EK-4A brand names (both Turkish), so
# brand-token matching is high-yield (84% verified 2026-07-16).
# ═══════════════════════════════════════════════════════════════════════════

_EK4A_PATH = PROJECT_ROOT / "data" / "gazette" / "curated" / "ek4a_drugs.parquet"


@dataclass(frozen=True)
class _DrugEntry:
    kamu_no: str
    barcode: str
    drug_name: str
    equivalence_group: str
    norm_tokens: tuple[str, ...]  # normalized brand+formulation tokens


@lru_cache(maxsize=1)
def _ek4a_index() -> tuple[dict[str, list[_DrugEntry]], list[_DrugEntry]]:
    """Return (brand-token→entries index, all-entries list) for EK-4A.

    Keyed by the FIRST normalized token (the brand name), since both finans
    and EK-4A put the brand first ("PARACEROL 10 MG...", "OSETRON 4 MG...").
    """
    if not _EK4A_PATH.exists():
        return {}, []
    import polars as pl

    df = pl.read_parquet(_EK4A_PATH)
    by_brand: dict[str, list[_DrugEntry]] = {}
    all_entries: list[_DrugEntry] = []
    for r in df.select(
        "kamu_no", "barcode", "drug_name", "equivalence_group"
    ).iter_rows(named=True):
        name = r.get("drug_name") or ""
        norm = normalize_name(name)
        tokens = tuple(_meaningful_tokens(norm))
        if not tokens:
            continue
        de = _DrugEntry(
            kamu_no=str(r.get("kamu_no") or ""),
            barcode=str(r.get("barcode") or ""),
            drug_name=name,
            equivalence_group=str(r.get("equivalence_group") or ""),
            norm_tokens=tokens,
        )
        by_brand.setdefault(tokens[0], []).append(de)
        all_entries.append(de)
    return by_brand, all_entries


def build_drug_candidates(
    description: str, *, max_candidates: int = 5
) -> list[dict[str, Any]]:
    """Return ranked EK-4A drug candidates for a hospital drug description.

    Matching: brand-token (first word) exact → formulation-token overlap for
    dose/form disambiguation (e.g. "OSETRON 8 mg" vs "OSETRON 4 mg"). Each
    candidate carries the full drug_identity so downstream code can populate
    ``DrugClaimLine`` correctly. No LLM, no network.
    """
    norm = normalize_name(description)
    if not norm:
        return []
    tokens = _meaningful_tokens(norm)
    if not tokens:
        return []
    brand = tokens[0]
    by_brand, _ = _ek4a_index()
    entries = by_brand.get(brand, [])
    if not entries:
        return []
    desc_token_set = set(tokens[1:])  # formulation tokens (dose, form, volume)
    # If the brand has exactly one EK-4A entry, it's unambiguous — give it a
    # high baseline even with zero formulation overlap (EK-4A uses heavy
    # abbreviations: "INF" vs "infuzyon", "FLK" vs "flakon" that don't
    # tokenize-match). Only when there are MULTIPLE entries do we need
    # formulation tokens to disambiguate (e.g. OSETRON 4mg vs 8mg).
    n_entries = len(entries)
    scored: list[tuple[float, _DrugEntry]] = []
    for de in entries:
        if desc_token_set and n_entries > 1:
            inter = desc_token_set & set(de.norm_tokens)
            score = len(inter) / len(desc_token_set)
        else:
            # Single entry, or no formulation to compare → brand match alone.
            score = 0.9 if n_entries == 1 else 0.5
        if score >= 0.2:
            scored.append((score, de))
    scored.sort(key=lambda t: (-t[0], t[1].kamu_no))
    return [
        {
            "code": de.kamu_no,
            "name": de.drug_name,
            "confidence": round(s, 3),
            "why": "brand+formulation",
            "drug_identity": {
                "kamu_no": de.kamu_no,
                "barcode": de.barcode,
                "equivalence_group": de.equivalence_group,
            },
        }
        for s, de in scored[:max_candidates]
    ]


# ═══════════════════════════════════════════════════════════════════════════
# EK-3 material index (Phase 3.2) — category match. finans carries SKU detail
# (No:22, BD brand, Ref 391891) that EK-3 collapses into a size-range category
# ("KANÜL, İNTRAVENÖZ, NO:14-22"). The SKU detail is correctly discarded —
# SUT reimburses by category, not manufacturer. ~60% matchable; the rest are
# bundled consumables (dressings, basic tubing) SUT folds into the procedure.
# ═══════════════════════════════════════════════════════════════════════════

_EK3_GLOB = "data/gazette/snapshots/asof_2026-01-31/EK-3*.parquet"


@dataclass(frozen=True)
class _MaterialEntry:
    code: str
    family: str
    category: str
    norm_name: str
    tokens: frozenset[str]


@lru_cache(maxsize=1)
def _ek3_index() -> tuple[list[_MaterialEntry]]:
    """Return a tuple of all EK-3 material entries (code, family, category).

    Loads all 23 EK-3 families, keeps rows whose first column looks like a SUT
    material code (alpha-prefix + digits, e.g. GR1000, OR2510, KD1000).
    Returns a 1-tuple to satisfy ``lru_cache`` (which can't cache a bare list).
    """
    import glob

    paths = sorted(glob.glob(str(PROJECT_ROOT / _EK3_GLOB)))
    entries: list[_MaterialEntry] = []
    for path in paths:
        import polars as pl

        df = pl.read_parquet(path)
        family = Path(path).stem
        code_col = df.columns[0]
        cat_col = df.columns[1] if df.width > 1 else code_col
        for r in df.select(code_col, cat_col).iter_rows(named=True):
            code = str(r[code_col] or "").strip()
            if not re.match(r"^[A-Z]{1,3}\d{3,}", code):
                continue
            cat = str(r[cat_col] or "").strip()
            norm = normalize_name(cat)
            if not norm:
                continue
            entries.append(
                _MaterialEntry(
                    code=code,
                    family=family,
                    category=cat,
                    norm_name=norm,
                    tokens=frozenset(_meaningful_tokens(norm)),
                )
            )
    return (entries,)


# Synonym/alias map for material matching — bridges Turkish/loanword spelling
# variants where finans and EK-3 use different forms for the same device.
# Applied after normalization, before tokenization. Extend as new variants surface.
_MATERIAL_ALIASES: dict[str, str] = {
    "branul": "kanul",       # finans "Branül" ↔ EK-3 "KANÜL"
    "branol": "kanul",
    "katater": "kateter",    # finans typo variant
    "iyneli": "igne",
}

# Material-only stopword set: generic device-class words that appear across
# hundreds of unrelated EK-3 categories and thus carry little discriminative
# signal. Without filtering these, a hospital "Serum Seti" (IV giving set)
# matches every "*SETİ" entry, and "IV Kateter Bandı" matches every "*KATETER"
# entry. These are dropped ONLY in build_material_candidates (not in the
# shared _meaningful_tokens, which other matchers rely on).
_MATERIAL_STOPWORDS: frozenset[str] = frozenset({
    "seti", "set", "sistem", "komple", "tamam", "kullanim", "tek",
    "kullanimlik", "adet", "malzeme", "kateter", "katater", "strip",
    "bandi", "steril", "disposable", "mm", "cm", "fr", "ml",
})


def _apply_material_aliases(tokens: list[str]) -> list[str]:
    return [_MATERIAL_ALIASES.get(t, t) for t in tokens]


def build_material_candidates(
    description: str, *, max_candidates: int = 5
) -> list[dict[str, Any]]:
    """Return ranked EK-3 category candidates for a hospital material SKU.

    Matching: inverse-document-frequency-weighted token overlap + a rare-token
    bonus. Common tokens like "kateter" (395 entries) contribute almost
    nothing; rare tokens like "foley" (12 entries) dominate. A single
    very-rare token match (IDF ≥ 4, i.e. the token appears in ≤~3% of
    categories) is treated as near-determinative. Bridges spelling variants
    via ``_MATERIAL_ALIASES`` (branul→kanul). Discards SKU detail.
    """
    norm = normalize_name(description)
    if not norm:
        return []
    desc_tokens = set(_apply_material_aliases(_meaningful_tokens(norm)))
    # Drop generic device-class words (seti/kateter/strip/...) that appear
    # across hundreds of unrelated EK-3 categories and carry little signal.
    # Without this a "Serum Seti" matches every "*SETİ" entry.
    desc_tokens = {t for t in desc_tokens if t not in _MATERIAL_STOPWORDS}
    if not desc_tokens:
        return []
    (all_entries,) = _ek3_index()

    import math

    n_entries = max(len(all_entries), 1)
    df: dict[str, int] = {}
    for me in all_entries:
        for t in me.tokens:
            df[t] = df.get(t, 0) + 1

    # Per-token IDF over query tokens that appear in the catalog (df >= 1).
    # We exclude catalog-absent tokens (brand names, SKU codes like "16ch" that
    # no EK-3 entry has) so they don't inflate the denominator and suppress
    # otherwise-good matches. The OLD code used df > 1, which also excluded
    # genuinely rare catalog tokens and let a single common word ("seti") score
    # 1.0 — df >= 1 is the correct cutoff (absent-only exclusion).
    query_idf = sum(
        math.log(n_entries / max(df.get(t, 1), 1))
        for t in desc_tokens
        if df.get(t, 0) >= 1
    )

    scored: list[tuple[float, _MaterialEntry]] = []
    for me in all_entries:
        if not me.tokens:
            continue
        inter = desc_tokens & me.tokens
        if not inter:
            continue
        # IDF-weighted overlap.
        idfs = {t: math.log(n_entries / max(df.get(t, 1), 1)) for t in inter}
        shared_idf = sum(idfs.values())
        if query_idf <= 0:
            score = len(inter) / len(desc_tokens) * 0.4
        else:
            score = shared_idf / query_idf
        # Rare-token bonus: a very rare shared token (IDF ≥ 4, ≤~2% of
        # categories) is near-determinative (e.g. "foley" pins the Foley
        # family) — but ONLY boost when the match already explains a good
        # chunk of the query (base ratio ≥ 0.5). This stops a single rare
        # word from rescuing an otherwise-unrelated candidate.
        has_rare = any(idf >= 4.0 for idf in idfs.values())
        if has_rare and score >= 0.5:
            score = min(score + 0.3, 1.0)
        if score >= 0.4:
            scored.append((score, me))
    scored.sort(key=lambda t: (-t[0], t[1].code))
    return [
        {
            "code": me.code,
            "name": me.category,
            "confidence": round(min(s, 1.0), 3),
            "why": "idf-token",
            "family": me.family,
        }
        for s, me in scored[:max_candidates]
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Frozen mapping table (2.5, 2.6) — reviewed-only, the reusable asset.
# ═══════════════════════════════════════════════════════════════════════════


@lru_cache(maxsize=1)
def _frozen_mapping() -> dict[str, dict[str, str]]:
    """Load the reviewed hospital→SUT mapping. Empty dict if file absent.

    Only ``reviewed=TRUE`` rows are loaded — this is the guard that prevents
    an unreviewed LLM mapping from feeding a motor. File is created by
    promoting rows out of ``crosswalk_review.csv``.
    """
    if not FROZEN_MAPPING_PATH.exists():
        return {}
    mapping: dict[str, dict[str, str]] = {}
    with FROZEN_MAPPING_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if str(row.get("reviewed", "")).strip().lower() != "true":
                continue
            hc = (row.get("hospital_code") or "").strip()
            if hc:
                mapping[hc] = {
                    "sut_code": (row.get("sut_code") or "").strip(),
                    "category": (row.get("category") or "").strip(),
                    "verified_by": (row.get("verified_by") or "").strip(),
                    "drug_identity": (row.get("drug_identity") or "").strip(),
                }
    return mapping


def clear_resolver_cache() -> None:
    """Drop all cached indexes + frozen mapping (tests, hot-reload)."""
    _frozen_mapping.cache_clear()
    _ek2b_index.cache_clear()
    _ek4a_index.cache_clear()
    _ek3_index.cache_clear()


# ═══════════════════════════════════════════════════════════════════════════
# Public resolver (2.1, 2.6)
# ═══════════════════════════════════════════════════════════════════════════


def resolve_code(
    hospital_code: str,
    description: str,
    hint: CategoryHint | None = None,
) -> Resolution:
    """Resolve one hospital code to a SUT code.

    Dispatches by category hint:
      - DRUG → ``build_drug_candidates`` (EK-4A, full drug_identity returned)
      - MATERIAL → ``build_material_candidates`` (EK-3, category-level match)
      - LAB/PROCEDURE/None → ``build_candidates`` (EK-2B)

    Order: frozen table → category-specific candidate generator. Returns a
    ``Resolution`` with ``method`` indicating the path. ``sut_code`` is None
    when no candidate clears the confidence floor — those codes belong in the
    LLM review queue.
    """
    hc = (hospital_code or "").strip()
    cat = hint.kind if hint else ""

    # 1. Frozen table (reviewed mappings only).
    frozen = _frozen_mapping()
    if hc in frozen:
        frozen_row = frozen[hc]
        sut = frozen_row["sut_code"]
        # Reconstruct drug_identity if the frozen row carries it.
        drug_identity = None
        if frozen_row.get("drug_identity"):
            import json

            try:
                drug_identity = json.loads(frozen_row["drug_identity"])
            except (json.JSONDecodeError, TypeError):
                drug_identity = None
        return Resolution(
            hospital_code=hc,
            description=description,
            sut_code=sut or None,  # bundled-consumable rows have empty sut_code
            method=ResolutionMethod.FROZEN,
            confidence=1.0,
            candidates=[{"code": sut, "name": "", "confidence": 1.0, "why": "frozen"}],
            reviewed=True,
            drug_identity=drug_identity,
            category=frozen_row.get("category", cat),
        )

    # 2. Category-specific candidate generator.
    if cat == "DRUG":
        cands = build_drug_candidates(description)
    elif cat == "MATERIAL":
        cands = build_material_candidates(description)
    else:
        cands = build_candidates(description, hint)

    # Confidence floors differ by category (see plan §3.1.5 / §3.2.5).
    floor = 0.7 if cat == "DRUG" else 0.7 if cat == "MATERIAL" else 0.5
    if cands and cands[0]["confidence"] >= floor:
        best = cands[0]
        drug_identity = best.get("drug_identity") if cat == "DRUG" else None
        return Resolution(
            hospital_code=hc,
            description=description,
            sut_code=best["code"],
            method=ResolutionMethod.EXACT if best["confidence"] >= 0.9
            else ResolutionMethod.TOKEN_PREFIX,
            confidence=best["confidence"],
            candidates=cands,
            sut_name=best.get("name"),
            drug_identity=drug_identity,
            category=cat,
        )

    # 3. No confident match — caller routes to the LLM review queue.
    return Resolution(
        hospital_code=hc,
        description=description,
        sut_code=None,
        method=ResolutionMethod.NO_MATCH if not cands else ResolutionMethod.LLM_PENDING,
        confidence=cands[0]["confidence"] if cands else 0.0,
        candidates=cands,
        category=cat,
    )


def resolve_codes_bulk(
    rows: list[dict[str, str]],
    *,
    hint_field: str = "category",
) -> list[Resolution]:
    """Resolve many ``(hospital_code, description, category)`` rows.

    ``rows`` items must carry ``hospital_code`` and ``description``; an
    optional ``category`` field becomes the ``CategoryHint``. Returns one
    ``Resolution`` per input row, in order.
    """
    out: list[Resolution] = []
    for r in rows:
        hint = None
        cat = r.get(hint_field)
        if cat:
            hint = CategoryHint(kind=cat)
        out.append(resolve_code(r.get("hospital_code", ""), r.get("description", ""), hint))
    return out
