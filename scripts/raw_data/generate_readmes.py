#!/usr/bin/env python3
"""Generate README.md catalog files under raw data/ for every folder."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[2] / "raw data"
TODAY = "2026-06-12"

EK_META: dict[str, dict[str, str]] = {
    "EK-1A": {
        "title": "Ayakta tedavide hekim / diş hekimi muayenesinde katılım payı alınmayacak kronik hastalıklar listesi",
        "sut": "§1.8.1 — kronik hastalık katılım payı muafiyeti",
        "bilun": "ek1a_chronic_exemptions.parquet — copay exemption checker (L2.1)",
        "typical_cols": "ICD-10 kod aralıkları, hastalık adı, harf indeksi",
    },
    "EK-1B": {
        "title": "Hastane sunulan hizmetler ve ilave ücret gösterge belgesi",
        "sut": "§1.5 — özel hastanelerde ilave ücret şeffaflığı",
        "bilun": "Form şablonu; makine okumalı katalog değil",
        "typical_cols": "—",
    },
    "EK-1C": {
        "title": "İstisnai sağlık hizmetleri listesi",
        "sut": "§1.5 — Kurumca karşılanmayan istisnai hizmetler",
        "bilun": "Ham kaynak; curated katmanda ayrı parquet yok",
        "typical_cols": "SIRA NO, KODU, İŞLEM ADI",
    },
    "EK-1D": {
        "title": "Acil halin sona ermesine ilişkin bilgi formu",
        "sut": "§1.4 — acil hal bildirimi",
        "bilun": "Form şablonu",
        "typical_cols": "—",
    },
    "EK-2A": {
        "title": "Ayaktan başvurularda ödeme listesi (poliklinik / muayene ücretleri)",
        "sut": "§2.2.2.A — ayakta ziyaret fiyatlandırması",
        "bilun": "ek2a_outpatient_visits.parquet",
        "typical_cols": "KODU, uzmanlık dalları, ÖH3/U1/U2/U3 fiyat sütunları",
    },
    "EK-2A-1": {
        "title": "Sağlık hizmeti sunucularının ayakta tedavilerde sınıflandırılması listesi",
        "sut": "§2.2 — kurum sınıfı (ÖH3, U1, U2, U3)",
        "bilun": "Referans tablo; EK-2A fiyat sütunlarıyla eşleşir",
        "typical_cols": "Kurum türü, sınıf",
    },
    "EK-2A-2": {
        "title": "Ayaktan başvuruda ilave olarak faturalandırılabilecek işlemler listesi",
        "sut": "§2.2.2.A(5) — ziyarete ek işlem",
        "bilun": "Ham kaynak",
        "typical_cols": "İŞLEM KODU, İŞLEM ADI, AÇIKLAMA",
    },
    "EK-2B": {
        "title": "Hizmet başı işlem puan listesi (fee-for-service tarife)",
        "sut": "§2.2.2 — işlem bazlı ödeme; ana prosedür kataloğu",
        "bilun": "ek2b_catalog_history.parquet (~7.500 kod) — birincil fiyat motoru",
        "typical_cols": "İŞLEM KODU, İŞLEM ADI, İŞLEM PUANI",
    },
    "EK-2C": {
        "title": "Tanıya dayalı işlem puan listesi (DRG / paket fiyatlandırma)",
        "sut": "§2.2.2.B — ICD-10 bölümüne göre paket kodları",
        "bilun": "ek2c_catalog_history.parquet — DRG unbundling, paket vs kalem",
        "typical_cols": "İŞLEM KODU, İŞLEM GRUBU, İŞLEM PUANI",
    },
    "EK-2C-1": {
        "title": "İlave oran uygulanacak işlemler listesi",
        "sut": "§2.2.2(20) — kurum sınıfına göre puan/katılım oranı",
        "bilun": "ek2c1_copay_rates.parquet — copay rate exposure (L2.4)",
        "typical_cols": "İŞLEM KODU, ORAN (%)",
    },
    "EK-2Ç": {
        "title": "Diş tedavileri puan listesi",
        "sut": "§2.2 — ağız diş sağlığı işlemleri",
        "bilun": "Ham kaynak (diş prosedürleri EK-2B'den ayrı)",
        "typical_cols": "Diş işlem kodları ve puanları",
    },
    "EK-2Ç-1": {
        "title": "Diş tedavileri puan listesine ilişkin açıklamalar",
        "sut": "EK-2Ç yorumlama notları",
        "bilun": "Prose/açıklama belgesi",
        "typical_cols": "—",
    },
    "EK-2Ç-2": {
        "title": "Diş tedavileri kontrol formu",
        "sut": "Diş tedavisi denetim formu",
        "bilun": "Form şablonu",
        "typical_cols": "—",
    },
    "EK-2Ç-3": {
        "title": "Tanıya dayalı ortodontik tedavi kontrol formu",
        "sut": "Ortodonti ön onay",
        "bilun": "Form şablonu",
        "typical_cols": "—",
    },
    "EK-2D-1": {
        "title": "PET görüntüleme klinik uygulama kriterleri",
        "sut": "§2.2 — PET endikasyonları",
        "bilun": "Klinik kriter prose",
        "typical_cols": "—",
    },
    "EK-2D-2": {
        "title": "Fizik tedavi ve rehabilitasyon tanı listesi",
        "sut": "§2.2 — FTR endikasyon ICD kodları",
        "bilun": "Ham kaynak",
        "typical_cols": "ICD-10 kodu, tanı adı",
    },
    "EK-2D-3": {
        "title": "Hiperbarik oksijen tedavisi uygulama listesi",
        "sut": "§2.2 — HBO endikasyonları",
        "bilun": "Ham kaynak",
        "typical_cols": "Endikasyon kodları",
    },
    "EK-2D-4": {
        "title": "İntraoperatif nöromonitöring — ayrı faturalandırılabilir işlemler",
        "sut": "§2.2 — EK-2/C paketinden ayrı EK-2/B kalemleri",
        "bilun": "Ham kaynak — paket/kalem ayrımı",
        "typical_cols": "EK-2/C Kodu, EK-2/B Kodu, İşlem Adı",
    },
    "EK-2D-5": {
        "title": "İntraoperatif nöronavigasyon — ayrı faturalandırılabilir işlemler",
        "sut": "§2.2 — nöronavigasyon eşlemesi",
        "bilun": "Ham kaynak",
        "typical_cols": "İşlem kod eşlemeleri",
    },
    "EK-2E-1": {
        "title": "Yurt dışına tedaviye gönderileceklere ilişkin belge",
        "sut": "§2.3 — yurt dışı tedavi",
        "bilun": "Form şablonu",
        "typical_cols": "—",
    },
    "EK-2E-2": {
        "title": "Yurt dışı tetkike ilişkin sağlık kurulu raporu",
        "sut": "§2.3",
        "bilun": "Form şablonu",
        "typical_cols": "—",
    },
    "EK-2E-3": {
        "title": "Yurt dışı tedavi/tetkik hasta izleme çizelgesi",
        "sut": "§2.3",
        "bilun": "Form şablonu",
        "typical_cols": "—",
    },
    "EK-2F": {
        "title": "Hasta sevk formu",
        "sut": "§2.1 — sevk zinciri",
        "bilun": "Form şablonu",
        "typical_cols": "—",
    },
    "EK-2G": {
        "title": "İlave ücret uygulanmayacak işlemler listesi",
        "sut": "§1.5 — ilave ücret yasağı",
        "bilun": "ek2g_no_surcharge.parquet — surcharge eligibility (L2.3)",
        "typical_cols": "KODU, İŞLEM ADI",
    },
    "EK-2K": {
        "title": "PGT ile IVF yapılan kalıtsal hastalıklar listesi",
        "sut": "§2.2 — tüp bebek / PGT endikasyonları",
        "bilun": "Ham kaynak",
        "typical_cols": "Hastalık / ICD kodları",
    },
    "EK-2L": {
        "title": "Mutat taşıt yol ücreti listesi",
        "sut": "§2.2 — sevk yol ücreti",
        "bilun": "Ham kaynak",
        "typical_cols": "SUT Kodu, Mesafe (km), Ücret (TL)",
    },
    "EK-2Y": {
        "title": "Yasa dışı ve kötüye kullanılan madde doğrulama analiz formu",
        "sut": "§2.2 — madde bağımlılığı tarama",
        "bilun": "Form şablonu",
        "typical_cols": "—",
    },
    "EK-3A": {
        "title": "Birden fazla branşta kullanılan tıbbi malzemeler",
        "sut": "§3.3 — çok disiplinli sarf/implant",
        "bilun": "ek3a_multibranch_materials.parquet",
        "typical_cols": "SUT KODU, malzeme tanımı, FİYAT (TL)",
    },
    "EK-3B": {
        "title": "Kurumca bedeli karşılanmayan tıbbi malzemeler (ana liste)",
        "sut": "§3.1.1(7)/(9) — EK-3/B üst liste",
        "bilun": "Üst katalog; alt listeler 3B-1 ve 3B-2",
        "typical_cols": "Malzeme kodu ve adı",
    },
    "EK-3B-1": {
        "title": "İşlem puanına dahil basit sıhhi sarf malzemeler",
        "sut": "§3.1.1 — paket içi sarf; ayrı faturalandırılamaz",
        "bilun": "ek3b1_bundled_consumables.parquet (54 kalem) — bundling rule (L1.1)",
        "typical_cols": "Sarf kategorisi / malzeme adı",
    },
    "EK-3B-2": {
        "title": "Kurumca bedeli karşılanmayan diğer tıbbi malzemeler",
        "sut": "§3.1.1 — SGK ödemez",
        "bilun": "ek3b2_non_reimbursable.parquet (13 kalem) — exclusion rule (L1.2)",
        "typical_cols": "Malzeme adı",
    },
    "EK-3C": {
        "title": "Ayakta tedavilerde kullanılan tıbbi malzemeler (üst liste)",
        "sut": "§3.1.2 — ayakta malzeme ödeme kuralları",
        "bilun": "Alt listeler C-1..C-5 + formlar",
        "typical_cols": "SUT kodu, fiyat",
    },
    "EK-3C-1": {
        "title": "Tıbbi uygunluk aranacak tıbbi malzemeler",
        "sut": "§3.1.2 — ön onay / rapor zorunluluğu",
        "bilun": "ek3c1_materials.parquet — material pre-check",
        "typical_cols": "SUT kodu, malzeme, koşullar",
    },
    "EK-3C-2": {
        "title": "Eksternal alt/üst ekstremite ve gövde protez-ortezler",
        "sut": "§3.1.2 — protez/ortez + MIAT aralıkları",
        "bilun": "ek3c2_materials.parquet — MIAT interval checks (L3.5)",
        "typical_cols": "SUT kodu, MIAT, fiyat",
    },
    "EK-3C-3": {
        "title": "Diğer protez-ortezler",
        "sut": "§3.1.2",
        "bilun": "ek3c3_materials.parquet",
        "typical_cols": "SUT kodu, fiyat",
    },
    "EK-3C-4": {
        "title": "Tıbbi sarf malzemeler",
        "sut": "§3.1.2",
        "bilun": "ek3c4_materials.parquet",
        "typical_cols": "SUT kodu, fiyat",
    },
    "EK-3C-5": {
        "title": "Özel hallerde karşılanan tıbbi malzemeler",
        "sut": "§3.1.2",
        "bilun": "ek3c5_materials.parquet",
        "typical_cols": "SUT kodu, koşul, fiyat",
    },
    "EK-3C-6": {
        "title": "Ampute mobilite ölçeği formu",
        "sut": "§3.1.2 — protez değerlendirme",
        "bilun": "Form şablonu (2026 tebliğinde yeni)",
        "typical_cols": "—",
    },
    "EK-3D": {
        "title": "Görmeye yardımcı tıbbi malzemeler (gözlük, lens vb.)",
        "sut": "§3.3.3.A",
        "bilun": "ek3d_vision_materials.parquet",
        "typical_cols": "SPH, SUT KODU, FİYAT",
    },
    "EK-3E-1": {
        "title": "Omurga cerrahisi alan grubuna ait tıbbi malzemeler",
        "sut": "§3.3 — branş/alan bazlı implant fiyat tavanı",
        "bilun": "ek3e1_spine_materials.parquet",
        "typical_cols": "SUT KODU, alan tanımı, FİYAT (TL)",
    },
    "EK-3E-2": {
        "title": "Beyin cerrahisi / kraniyal cerrahi malzemeleri",
        "sut": "§3.3",
        "bilun": "ek3e2_cranial_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT (TL)",
    },
    "EK-3F-1": {
        "title": "Ortopedi — artroplasti (kalça/diz protezi vb.)",
        "sut": "§3.3",
        "bilun": "ek3f1_arthroplasty_materials.parquet — L4.4 prose (kalça)",
        "typical_cols": "Hiyerarşik implant ağacı + SUT kodu",
    },
    "EK-3F-2": {
        "title": "Ortopedi — artroskopi ve eklem cerrahisi",
        "sut": "§3.3",
        "bilun": "ek3f2_arthroscopy_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3F-3": {
        "title": "Ortopedi — tümör rezeksiyonu",
        "sut": "§3.3",
        "bilun": "ek3f3_tumor_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3F-4": {
        "title": "Ortopedi — travma ve rekonstrüksiyon",
        "sut": "§3.3",
        "bilun": "ek3f4_trauma_materials.parquet",
        "typical_cols": "SUT KODU, plak/vida hiyerarşisi",
    },
    "EK-3G": {
        "title": "Göz sağlığı ve hastalıkları branşı malzemeleri",
        "sut": "§3.3",
        "bilun": "ek3g_ophthalmology_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3H": {
        "title": "Kardiyoloji branşı malzemeleri (stent, balon vb.)",
        "sut": "§3.3",
        "bilun": "ek3h_cardiology_materials.parquet — PCI stent prose",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3I": {
        "title": "Kalp damar cerrahisi malzemeleri (ICD, kapak, greft)",
        "sut": "§3.3",
        "bilun": "ek3i_cv_surgery_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3J": {
        "title": "KBB branşı malzemeleri",
        "sut": "§3.3",
        "bilun": "ek3j_ent_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3K": {
        "title": "Kadın hastalıkları ve doğum malzemeleri",
        "sut": "§3.3",
        "bilun": "ek3k_obgyn_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3L": {
        "title": "Üroloji malzemeleri",
        "sut": "§3.3",
        "bilun": "ek3l_urology_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3M": {
        "title": "Radyoloji ve endovasküler girişim malzemeleri",
        "sut": "§3.3",
        "bilun": "ek3m_radiology_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3N-1": {
        "title": "Allogreft ürün grubu",
        "sut": "§3.3",
        "bilun": "ek3n1_allograft_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3N-2": {
        "title": "Xenogreft ürün grubu",
        "sut": "§3.3",
        "bilun": "ek3n2_xenograft_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3N-3": {
        "title": "Sentetik greft ürün grubu",
        "sut": "§3.3",
        "bilun": "ek3n3_synthetic_graft_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3O": {
        "title": "Hematoloji-onkoloji malzemeleri",
        "sut": "§3.3",
        "bilun": "ek3o_hematology_oncology_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3P": {
        "title": "Nefroloji malzemeleri (diyaliz vb.)",
        "sut": "§3.3",
        "bilun": "ek3p_nephrology_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3R": {
        "title": "Gastroenteroloji malzemeleri",
        "sut": "§3.3",
        "bilun": "ek3r_gastroenterology_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3S": {
        "title": "Göğüs hastalıkları ve göğüs cerrahisi malzemeleri",
        "sut": "§3.3",
        "bilun": "ek3s_pulmonology_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-3T": {
        "title": "Anesteziyoloji, reanimasyon ve ağrı tedavisi malzemeleri",
        "sut": "§3.3",
        "bilun": "ek3t_anesthesiology_materials.parquet",
        "typical_cols": "SUT KODU, FİYAT",
    },
    "EK-4A": {
        "title": "Bedeli ödenecek ilaçlar listesi",
        "sut": "§4 — SGK ilaç geri ödeme kataloğu",
        "bilun": "ek4a_drugs.parquet (~8.400 ilaç) — drug optimizer, discount validation",
        "typical_cols": "Kamu No, Barkod, İlaç Adı, fiyat kademeleri",
    },
    "EK-4B": {
        "title": "Hasta özel diyet ürünleri / tıbbi mamalar (PKU, kistik fibroz, süt alerjisi)",
        "sut": "§4 — özel beslenme",
        "bilun": "Ham kaynak (curated yok)",
        "typical_cols": "Kamu No, Barkod, Ürün Adı",
    },
    "EK-4C": {
        "title": "Yurt dışı ilaç fiyat listesi",
        "sut": "§4 — ithal / ruhsatsız ilaç fiyat referansı",
        "bilun": "Ham kaynak",
        "typical_cols": "BARKOD, İLACIN ADI, ETKEN MADDE",
    },
    "EK-4Ç": {
        "title": "Teşhis kısaltmaları listesi",
        "sut": "§4 — laboratuvar kısaltmaları",
        "bilun": "Prose referans",
        "typical_cols": "—",
    },
    "EK-4D": {
        "title": "Hasta katılım payından muaf ilaçlar",
        "sut": "§1.8 — ilaç copay muafiyeti",
        "bilun": "Ham kaynak / ek4d extractor",
        "typical_cols": "İlaç listesi",
    },
    "EK-4E": {
        "title": "Sistemik antimikrobik ve diğer ilaçların reçeteleme kuralları",
        "sut": "§4 — antibiyotik kısıtları",
        "bilun": "Prose kurallar",
        "typical_cols": "—",
    },
    "EK-4F": {
        "title": "Ayakta tedavide sağlık raporu ile verilebilen ilaçlar",
        "sut": "§4 — rapor zorunluluğu",
        "bilun": "Prose liste",
        "typical_cols": "—",
    },
    "EK-4G": {
        "title": "Sadece yatarak tedavide ödenen ilaçlar",
        "sut": "§4 — yatarak kısıtı",
        "bilun": "Prose liste",
        "typical_cols": "—",
    },
}

GROUP_INTRO = {
    "EK-1 LİSTELERİ": "EK-1 — Hasta hakları, katılım payı muafiyetleri ve istisnai hizmetler (SUT Bölüm 1).",
    "EK-2 LİSTELERİ": "EK-2 — İşlem fiyatlandırma, DRG paketleri, diş tedavileri ve formlar (SUT Bölüm 2). BILUN'un ana fiyat motoru EK-2B ve EK-2C'den beslenir.",
    "EK-3 LİSTELERİ": "EK-3 — Tıbbi malzeme, sarf, protez ve branş bazlı implant tavan fiyatları (SUT Bölüm 3). En çok dosya burada; B/C alt listeleri ödeme kurallarını, E–T alt listeleri branş kataloglarını taşır.",
    "EK-4 LİSTELERİ": "EK-4 — İlaç geri ödeme kataloğu ve reçeteleme kuralları (SUT Bölüm 4). EK-4A ana ilaç listesidir.",
}

EK3_CHEATSHEET = """
## EK-3 hızlı harita

SGK malzeme eklerini iki aileye ayırır:

| Aile | Ekler | Soru |
|------|-------|------|
| **Ödeme kuralları** | EK-3B, EK-3B-1, EK-3B-2, EK-3C (+ C-1..C-5) | Bu malzeme faturalanabilir mi? SGK öder mi? Rapor gerekir mi? |
| **Branş fiyat tavanları** | EK-3A, EK-3D, EK-3E..3T | Bu implant/sarf için SGK tavan fiyatı ne? |

- **EK-3B-1** → işlem paketine dahil sarf (ayrı satır faturalandırılamaz)
- **EK-3B-2** → SGK hiç ödemez
- **EK-3C-*** → ayakta tedavide protez/sarf; C-1 ön onay, C-2 MIAT aralığı
- **EK-3H / EK-3I** → kardiyoloji / kalp cerrahisi (stent, ICD, kapak)
- **EK-3F-*** → ortopedi alt alanları (artroplasti, artroskopi, tümör, travma)
"""


def extract_ek_code(filename: str) -> str | None:
    # 2025 tebliğ: EK-4-A, EK-4-B (harf önce tire ile)
    m = re.match(r"(EK-\d+)-([A-ZÇ])", filename)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    m = re.match(r"(EK-[0-9]+(?:[A-ZÇ])?(?:-[0-9]+)?)", filename)
    return m.group(1) if m else None


def extract_effective_date(filename: str) -> str | None:
    m = re.search(r"Yür\.?\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", filename)
    if m:
        return m.group(1)
    m = re.search(r"Yürürlük\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4})", filename)
    return m.group(1) if m else None


def file_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xls"):
        return "spreadsheet"
    if ext in (".docx", ".doc"):
        return "word"
    if ext == ".pdf":
        return "pdf"
    return "other"


def count_rows(path: Path) -> int | None:
    ext = path.suffix.lower()
    if ext not in (".xlsx", ".xls"):
        return None
    engine = "openpyxl" if ext == ".xlsx" else "xlrd"
    try:
        xl = pd.ExcelFile(path, engine=engine)
    except Exception:
        return None
    name = xl.sheet_names[0]
    preview = xl.parse(name, header=None, nrows=10)
    hdr = max(
        range(min(10, len(preview))),
        key=lambda i: int(preview.iloc[i].notna().sum()),
        default=0,
    )
    df = xl.parse(name, header=hdr).dropna(how="all")
    return len(df)


def describe_file(path: Path) -> dict:
    ek = extract_ek_code(path.name)
    return {
        "name": path.name,
        "ek": ek,
        "effective": extract_effective_date(path.name),
        "meta": EK_META.get(ek, {}) if ek else {},
        "rows": count_rows(path) if file_type(path) == "spreadsheet" else None,
        "ftype": file_type(path),
    }


def render_ek_entry(info: dict) -> str:
    meta = info["meta"]
    lines = [f"### {info['ek'] or info['name']}"]
    if meta.get("title"):
        lines.append(f"**{meta['title']}**")
    if info["effective"]:
        lines.append(f"- Yürürlük (dosya adından): `{info['effective']}`")
    lines.append(f"- Dosya: `{info['name']}`")
    if info["rows"] is not None:
        lines.append(f"- Yaklaşık satır sayısı: **{info['rows']:,}**")
    if meta.get("sut"):
        lines.append(f"- SUT bağlantısı: {meta['sut']}")
    if meta.get("bilun"):
        lines.append(f"- BILUN kullanımı: {meta['bilun']}")
    if meta.get("typical_cols") and meta["typical_cols"] != "—":
        lines.append(f"- Tipik sütunlar: `{meta['typical_cols']}`")
    elif info["ftype"] == "word":
        lines.append("- Tür: Word formu / prose (makine okumalı tarife tablosu değil)")
    lines.append("")
    return "\n".join(lines)


def render_folder_readme(folder: Path, rel: str) -> str:
    children_dirs = sorted(
        p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    files = sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.name != "README.md"
    )

    lines: list[str] = [
        f"# {folder.name}",
        "",
        f"Konum: `raw data/{rel}`",
        f"Son güncelleme: {TODAY}",
        "",
    ]

    if folder == RAW:
        lines += [
            "SGK **Sağlık Uygulama Tebliği (SUT)** kaynak belgeleri. Resmi gazete tebliğ paketleri, ilaç listeleri ve saha röportajları.",
            "",
            "## Dizin yapısı",
            "",
            "```",
            "raw data/",
        ]
        for d in children_dirs:
            subcount = sum(
                1 for f in d.rglob("*") if f.is_file() and not f.name.startswith(".")
            )
            lines.append(f"├── {d.name}/          ({subcount} dosya)")
        for f in files:
            if f.suffix.lower() == ".pdf":
                lines.append(f"├── {f.name}")
        lines += [
            "└── README.md            (bu dosya)",
            "```",
            "",
            "## Hangi tebliği kullanmalıyım?",
            "",
            "| Klasör | Tebliğ tarihi | Not |",
            "|--------|---------------|-----|",
            "| `2026.01.17-...` | 17 Ocak 2026 | **Güncel** — BILUN gazette ETL hedef kaynağı |",
            "| `2025.01.25-...` | 25 Ocak 2025 | Önceki sürüm; fiyat diff / tarihsel analiz |",
            "",
            "## Kök dosyalar",
            "",
        ]
        for f in files:
            if "MEDULA" in f.name:
                lines.append(
                    f"- `{f.name}` — MEDULA kullanım kılavuzu (fatura sistemi referansı)"
                )
            elif f.suffix == ".pdf":
                lines.append(
                    f"- `{f.name}` — PDF kaynak (içerik dosya adından belirsiz)"
                )
        lines += [
            "",
            "## EK grupları — hızlı rehber",
            "",
            "| Grup | Ne içerir? |",
            "|------|------------|",
            "| EK-1 | Katılım payı muafiyetleri, formlar |",
            "| EK-2 | İşlem puanları (2B), DRG paketleri (2C), diş (2Ç) |",
            "| EK-3 | Malzeme tavan fiyatları ve ödeme kuralları |",
            "| EK-4 | İlaç kataloğu (4A) ve reçete kuralları |",
            "",
            "İşlenmiş parquet: `data/gazette/curated/` — ayrıntı: `docs/core-system/gazette.md`.",
            "",
            "## Alt klasörler",
            "",
        ]
        for d in children_dirs:
            lines.append(f"- [{d.name}]({d.name}/README.md)")
        lines.append("")
        return "\n".join(lines)

    if "Değişiklik Tebliği" in folder.name and folder.parent == RAW:
        lines += [
            "SGK **işlenmiş güncel 2013 SUT** tebliğ paketi. Ana metin + dört EK klasörü.",
            "",
        ]
        docx = [f for f in files if f.suffix.lower() == ".docx" and "SUT" in f.name]
        if docx:
            lines.append(f"Ana tebliğ metni: `{docx[0].name}`")
            lines.append("")
        lines += ["## Alt klasörler", ""]
        for d in children_dirs:
            lines.append(f"- [{d.name}]({d.name}/README.md) — {GROUP_INTRO.get(d.name, '')}")
        lines.append("")
        return "\n".join(lines)

    if folder.name == "Referans Bazlı İlaç Listesi":
        lines += [
            "SGK **referans bazlı ilaç fiyat listesi** yayınları (EK-4A ile ilişkili fiyat güncellemeleri).",
            "",
            "## Dosyalar",
            "",
            "| Dosya | Yayın tarihi |",
            "|-------|--------------|",
        ]
        for f in files:
            dm = re.search(r"(\d{2}\.\d{2}\.\d{4})", f.name)
            lines.append(f"| `{f.name}` | {dm.group(1) if dm else '—'} |")
        lines += [
            "",
            "- Tipik sütunlar: barkod, ilaç adı, referans fiyat, indirim oranı",
            "- BILUN: `data/gazette/curated/ek4a_drugs.parquet`",
            "",
        ]
        return "\n".join(lines)

    if "Ek İzlemeye Tabi" in folder.name:
        lines += [
            "**Ek izlemeye tabi ilaçlar** — ruhsatlı ilaçların SGK izlem/recete kısıt listesi.",
            "",
            "## Dosyalar",
            "",
        ]
        for f in sorted(files, key=lambda x: x.name):
            dm = re.search(r"(\d{2}\.\d{2}\.\d{2,4})", f.name)
            suffix = f" — yayın: {dm.group(1)}" if dm else ""
            lines.append(f"- `{f.name}`{suffix}")
        lines.append("")
        return "\n".join(lines)

    if folder.name == "Interviews":
        lines += [
            "Saha araştırması — hastane faturalama ekipleriyle röportaj notları. SUT/EK kaynak verisi değil.",
            "",
        ]
        for f in files:
            lines.append(f"- `{f.name}`")
        lines.append("")
        return "\n".join(lines)

    if folder.name in GROUP_INTRO:
        lines.append(GROUP_INTRO[folder.name])
        lines.append("")
        if folder.name == "EK-3 LİSTELERİ":
            lines.append(EK3_CHEATSHEET.strip())
            lines.append("")
        spreadsheets, forms = [], []
        for f in files:
            info = describe_file(f)
            (spreadsheets if info["ftype"] == "spreadsheet" else forms).append(info)
        if spreadsheets:
            lines += ["## Tarife / katalog tabloları", ""]
            for info in spreadsheets:
                lines.append(render_ek_entry(info))
        if forms:
            lines += ["## Formlar ve açıklama belgeleri", ""]
            for info in forms:
                lines.append(render_ek_entry(info))
        lines += [
            "---",
            "BILUN pipeline: `scripts/sut/convert_xlsx_to_parquet.py` → `data/gazette/raw/` → `data/gazette/curated/`",
            "",
        ]
        return "\n".join(lines)

    return "\n".join(lines)


def main() -> None:
    written: list[str] = []
    folders = [RAW] + [
        p
        for p in RAW.rglob("*")
        if p.is_dir() and not any(part.startswith(".") for part in p.parts)
    ]
    for folder in sorted(folders):
        rel = str(folder.relative_to(RAW))
        content = render_folder_readme(folder, rel if rel != "." else "")
        if not content.strip():
            continue
        readme = folder / "README.md"
        readme.write_text(content, encoding="utf-8")
        written.append(str(readme.relative_to(RAW)))
    print(f"Wrote {len(written)} README files under raw data/")


if __name__ == "__main__":
    main()
