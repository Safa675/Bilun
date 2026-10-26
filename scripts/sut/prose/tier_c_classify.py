"""Tier-C drug clause classification and structured signal extraction (A/B/C/D)."""

from __future__ import annotations

import re
from typing import Any

from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes
from src.bilun.domain.turkish_fold import TurkishFold, fold_turkish

# ── Bucket B: biomarker + prior-therapy ───────────────────────────────────────

_BIOMARKER_KEYWORDS = [
    r"her\s*-?\s*2\s*(?:immünhistokimya|ihk|fish|cish|sish)",
    r"her2",
    r"cd\s*20\s*pozitif",
    r"cd\s*20\s*\+",
    r"kras",
    r"braf",
    r"egfr\s*mutasyon",
    r"alk\s*pozitif",
    r"philadelphia\s*kromozomu\s*pozitif",
    r"bcr\s*-?\s*abl",
    r"brca",
    r"hormon\s*reseptörü\s*pozitif",
    r"östrojen\s*reseptörü",
    r"achr\s*antikor",
    r"fish\s*/\s*cish",
    r"genotip\s*\d",
    r"jAK2",
    r"jak\s*2\s*V617F",
    r"17p\s*delesyon",
    r"5q\s*delesyon",
    r"pd-?l1",
    r"ros1",
]
_BIOMARKER_RE = re.compile("|".join(_BIOMARKER_KEYWORDS), re.IGNORECASE)

_PRIOR_THERAPY_KEYWORDS = [
    r"önceki\s+tedavi",
    r"dirençli",
    r"intolere",
    r"birinci\s*basamak\s*tedavisinde",
    r"ikinci\s*basamak",
    r"üçüncü\s*basamak",
    r"ilk\s*sıra\s*tedavi",
    r"ikinci\s*sıra",
    r"önceden\s+.{0,20}kullan",
    r"transplantasyon\s+sonrasında",
    r"otolog\s+kök\s*hücre",
    r"nüks",
    r"kemorezistan",
    r"tedavi\s*sonrasında\s*nüks",
    r"idame\s*tedavisinde",
    r"öncesi\s*tedavi",
    r"sıra\s*tedaviden",
    r"refrakter",
    r"salvage",
]
_PRIOR_THERAPY_RE = re.compile("|".join(_PRIOR_THERAPY_KEYWORDS), re.IGNORECASE)

_COMBO_PROHIBITION_RE = re.compile(
    r"(?:ardışık|kombine|peş\s*peşe|birlikte).{0,40}?(?:kullanılamaz|yasak|karşılanmaz|ödenmez)",
    re.IGNORECASE,
)
_MAX_CYCLE_RE = re.compile(
    r"(?:maksimum|en\s*fazla|toplam).{0,30}?(?:küre|doz|uygulama|kür)",
    re.IGNORECASE,
)
_PRESCRIBER_AUTHORITY_RE = re.compile(
    r"(?:tüm\s+uzman\s+hekimlerce|uzman\s+hekim(?:ler)?ce\s+reçete|"
    r"tıbbi\s+onkoloji|hematoloji\s+uzman|sağlık\s+kurulu\s+raporu)",
    re.IGNORECASE,
)
_REPORT_DURATION_RE = re.compile(r"(\d+)\s*ay\s*süreli", re.IGNORECASE)

_STRICT_EMR_SIGNALS = [
    r"ecog",
    r"performans\s*statüsü",
    r"performans\s*skoru?",
    r"karnofsky",
    r"progresyon",
    r"hastalık\s*ilerlemesi",
    r"cevapsızlık",
    r"yanıt\s*değerlendir",
    r"tedaviye\s*yanıt",
    r"klinik\s+ve/?veya\s+radyolojik",
    r"ishak",
    r"fibroz\s*skoru",
    r"düzeltilmiş\s*kalsiyum",
    r"hematokrit",
    r"dipps",
    r"edss",
    r"endikasyon\s*dışı\s*onay",
    r"bilgilendirilmiş\s*hasta\s*olur",
    r"meningokok",
    r"skorlama\s*sistemi",
    r"minör\s*yanıt",
    r"kısmi\s*yanıt",
    r"\d\s*üncü\s*kür\s*sonunda",
    r"altıncı\s*kür",
    r"6\s*ıncı\s*kür",
    r"ferritin",
    r"satürasyon",
    r"hba1c",
    r"glukoz",
    r"creatinin",
    r"egfr\s*<\s*\d",
]
_EMR_RE = re.compile("|".join(_STRICT_EMR_SIGNALS), re.IGNORECASE)

_ICD_RE = re.compile(r"\b([CD]\d{2}(?:\.\d+)?)\b", re.IGNORECASE)


def extract_drug_tokens(text: str, known_inns: list[str]) -> list[str]:
    norm_text = fold_turkish(text or "", TurkishFold.ACCENTLESS)
    found: list[str] = []
    for inn in known_inns:
        if inn and inn in norm_text:
            found.append(inn)
    if found:
        return found[:8]
    t = str(text or "").strip()
    m = re.match(r"^[\(\[]?(?:\d+|[a-zçğıöşü])[\)\].]\s*", t, re.I)
    rest = t[m.end() :].strip() if m else t
    seg = rest.split(";")[0].split(",")[0].strip()
    if 2 < len(seg) < 80 and not seg.lower().startswith("bu "):
        return [fold_turkish(seg, TurkishFold.ACCENTLESS)]
    return []


def extract_icd_hints(text: str) -> list[str]:
    codes = _ICD_RE.findall(str(text or ""))
    uniq = sorted({c.upper().split(".")[0] for c in codes})
    if uniq:
        return uniq
    lower = fold_turkish(text or "", TurkishFold.ACCENTLESS)
    if "prostat" in lower or "psa" in lower:
        return ["C61"]
    if "meme" in lower:
        return ["C50"]
    if "lenfoma" in lower:
        return ["C81", "C82", "C83", "C84", "C85", "C86"]
    if "miyelodisplastik" in lower or re.search(r"\bmds\b", lower):
        return ["D46"]
    if "hepatit" in lower and "c" in lower:
        return ["B18"]
    return []


def extract_report_duration_months(text: str) -> int | None:
    m = _REPORT_DURATION_RE.search(str(text or ""))
    if m:
        return int(m.group(1))
    return None


def classify_bucket(record: dict[str, Any]) -> str:
    """Classify a Tier-C clause into A/B/C/D."""
    text = str(record.get("text_tr") or record.get("in_force_text") or "")
    is_heading = bool(record.get("is_heading"))
    is_amendment = bool(record.get("is_amendment"))
    is_superseded = bool(record.get("is_superseded_marker"))
    char_count = int(record.get("char_count") or len(text))

    if is_heading or is_amendment or is_superseded:
        return "D"
    if char_count < 50:
        return "D"
    if re.fullmatch(r"\s*[a-zçşğüöı)]{1,3}\)?\s*[A-ZÇŞĞÜÖİ][\w\-()]{2,40}\s*[;:.]?\s*", text):
        return "D"

    if _BIOMARKER_RE.search(text) or _PRIOR_THERAPY_RE.search(text):
        return "B"

    if _EMR_RE.search(text):
        return "C"

    if (
        _COMBO_PROHIBITION_RE.search(text)
        or _MAX_CYCLE_RE.search(text)
        or _PRESCRIBER_AUTHORITY_RE.search(text)
        or _REPORT_DURATION_RE.search(text)
    ):
        return "A"

    if char_count > 100:
        return "C"
    return "D"


def extract_signals(text: str) -> dict[str, Any]:
    """Structured signals mined from clause prose."""
    t = str(text or "")
    emr_hits = sorted({m.group(0).lower() for m in _EMR_RE.finditer(t)})
    return {
        "has_biomarker_signal": bool(_BIOMARKER_RE.search(t)),
        "has_prior_therapy_signal": bool(_PRIOR_THERAPY_RE.search(t)),
        "has_combo_prohibition": bool(_COMBO_PROHIBITION_RE.search(t)),
        "has_max_cycle": bool(_MAX_CYCLE_RE.search(t)),
        "has_prescriber_authority": bool(_PRESCRIBER_AUTHORITY_RE.search(t)),
        "report_duration_months_hint": extract_report_duration_months(t),
        "emr_signal_tokens": emr_hits[:12],
        "defer_themes": infer_defer_themes(t),
    }


def build_rule_candidate(
    *,
    clause_id: str,
    section_id: str,
    text: str,
    bucket: str,
    deontic_modality: str | None,
    known_inns: list[str],
    manifest_name: str,
) -> dict[str, Any]:
    """Structured rule stub extracted from a tier-C clause (pre-EMR)."""
    drugs = extract_drug_tokens(text, known_inns)
    icd = extract_icd_hints(text)
    signals = extract_signals(text)
    rule_id = f"{section_id}.tier_c.{clause_id}".replace(" ", "_")

    candidate: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": section_id,
        "clause_id": clause_id,
        "encode_bucket": bucket,
        "manifest_source": manifest_name,
        "gate_b_sources": [clause_id],
        "drug_names": drugs or ["__pathway_unspecified__"],
        "message_tr": " ".join(str(text or "").split())[:480],
        "defer_themes": signals["defer_themes"],
        "extraction_signals": signals,
        "runtime_status": "extracted_pre_emr",
    }
    if deontic_modality:
        candidate["deontic_modality"] = deontic_modality

    if icd:
        if any("-" in c for c in icd):
            candidate["icd10_ranges"] = icd
        else:
            candidate["icd10_codes"] = icd

    if bucket == "A":
        candidate["report_required"] = bool(signals["has_prescriber_authority"])
        if signals["report_duration_months_hint"]:
            candidate["report_duration_months"] = signals["report_duration_months_hint"]
        if deontic_modality in {"NO_PAY", "PROHIBITED"}:
            candidate["pay"] = False
    elif bucket == "B":
        if signals["has_biomarker_signal"]:
            candidate["required_biomarkers"] = [{"marker": "TBD", "status_any": ["positive"]}]
        if signals["has_prior_therapy_signal"]:
            candidate["requires_prior_therapy"] = {"drug_or_class": "TBD", "outcome": "TBD"}
        candidate["report_required"] = True
    elif bucket == "C":
        candidate["emr_blocked"] = True
        candidate["required_emr_fields"] = signals["emr_signal_tokens"] or signals["defer_themes"]
    else:
        candidate["non_actionable"] = True

    return candidate
