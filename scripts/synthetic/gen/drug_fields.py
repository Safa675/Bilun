"""Drug claim-line optional field defaults."""

from typing import Any

def _empty_drug_indication_fields() -> dict[str, Any]:
    return {
        "uzmanlik_kurulu_raporu_var": None,
        "rapor_suresi_ay": None,
        "yatarak_tedavi_ilac": None,
        "recete_eden_uzmanlik": None,
        "yillik_uygulama_sayisi": None,
        "yukleme_fazinda": None,
        "biyobelirteciler": None,
        "onceki_tedaviler": None,
    }


def _ensure_drug_indication_columns(drug_claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in drug_claims:
        for key, default in _empty_drug_indication_fields().items():
            row.setdefault(key, default)
    return drug_claims
