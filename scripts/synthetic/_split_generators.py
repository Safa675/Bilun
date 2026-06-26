#!/usr/bin/env python3
"""One-shot splitter: generators_monolith.py.bak -> gen/*.py + generators shim."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "generators_monolith.py.bak"
GEN = ROOT / "gen"
lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)


def slice_lines(start: int, end: int) -> str:
    """1-based inclusive line slice."""
    return "".join(lines[start - 1 : end])


MODULES: dict[str, tuple[str, list[tuple[int, int]]]] = {
    "specs.py": (
        '"""Demo spec dicts for synthetic claim generation."""\n\nfrom typing import Any\n\n',
        [(43, 321)],
    ),
    "drug_fields.py": (
        '"""Drug claim-line optional field defaults."""\n\nfrom typing import Any\n\n',
        [(324, 341)],
    ),
    "patients.py": (
        '"""Patient and episode generation."""\n\nfrom __future__ import annotations\n\n'
        "from typing import Any\n\n"
        "import numpy as np\n\n"
        "from constants import ICD10_CHAPTER_TO_DRG_GROUP, SCENARIO_TEMPLATES, TURKISH_FEMALE_NAMES, TURKISH_MALE_NAMES, TURKISH_SURNAMES\n"
        "from catalog import _ek1a\n"
        "from demo_config import vignette_for_patient_id\n"
        "from fault_injection import apply_vignette_episode_defaults\n"
        "from gen.specs import _MEDULA_DEMO_SPECS\n\n",
        [(344, 384), (388, 420), (424, 683), (687, 692)],
    ),
    "procedures.py": (
        '"""Procedure selection for synthetic claims."""\n\nfrom __future__ import annotations\n\n'
        "from typing import Any\n\n"
        "import numpy as np\n"
        "import pandas as pd\n\n"
        "from catalog import _money\n"
        "from constants import ICD10_CHAPTER_TO_DRG_GROUP\n"
        "from demo_config import vignette_for_patient_id\n"
        "from fault_injection import build_optional_override_specs\n"
        "from gen.patients import _drg_group\n"
        "from payment_method_sampling import episode_care_setting, filter_ek2b_pool_for_packaged_claim\n\n",
        [(696, 1225)],
    ),
    "materials_flags.py": (
        '"""Material and specialty prose flag columns and coverage helpers."""\n\nfrom __future__ import annotations\n\n'
        "from typing import Any\n\n",
        [(1229, 1562)],
    ),
    "reconcile.py": (
        '"""Claim header totals, specialty keyword demos, EK-2C-1 reconciliation."""\n\n'
        "from __future__ import annotations\n\n"
        "from collections import defaultdict\n"
        "from typing import Any\n\n"
        "import pandas as pd\n\n"
        "from catalog import _money\n"
        "from gen.materials_flags import (\n"
        "    _default_prose_material_flags,\n"
        "    _default_specialty_prose_flags,\n"
        ")\n\n",
        [(1430, 1516), (1603, 1684)],
    ),
    "claim_lines.py": (
        '"""Per-claim line builders and ClaimEpisodeContext."""\n\nfrom __future__ import annotations\n\n'
        "from collections import defaultdict\n"
        "from dataclasses import dataclass, field\n"
        "from typing import Any\n\n"
        "import numpy as np\n"
        "import pandas as pd\n\n"
        "from catalog import _drug_unit_price, _money\n"
        "from gen.drug_fields import _empty_drug_indication_fields\n"
        "from gen.materials_flags import _default_prose_material_flags, _default_specialty_prose_flags, _sample_prose_material_flags\n"
        "from gen.reconcile import _reconcile_ek2c1_procedure_lines\n\n",
        [(1565, 1601), (1686, 2125)],
    ),
    "medula_anchor.py": (
        '"""MEDULA rejection anchor line injection."""\n\n'
        "from __future__ import annotations\n\n"
        "import datetime as dt\n"
        "from typing import Any\n\n"
        "import pandas as pd\n\n"
        "from catalog import _money\n"
        "from gen.claim_lines import ClaimEpisodeContext\n"
        "from gen.drug_fields import _empty_drug_indication_fields\n"
        "from gen.materials_flags import _default_prose_material_flags, _default_specialty_prose_flags\n"
        "from gen.procedures import _lookup_ek2b_price\n\n",
        [(2128, 2374)],
    ),
    "orchestrate.py": (
        '"""Claims and lines orchestrator."""\n\n'
        "from __future__ import annotations\n\n"
        "import datetime as dt\n"
        "from typing import Any\n\n"
        "import numpy as np\n"
        "import pandas as pd\n\n"
        "from catalog import _drug_unit_price, _ek2b, _ek2c1, _ek2c_latest, _ek2g, _ek3_material, _ek4a, _money\n"
        "from constants import CURATED_DIR\n"
        "from gen.claim_lines import (\n"
        "    ClaimEpisodeContext,\n"
        "    _append_drug_lines_for_claim,\n"
        "    _append_material_lines_for_claim,\n"
        "    _append_material_prose_demo_line,\n"
        "    _append_procedure_lines_for_claim,\n"
        ")\n"
        "from gen.drug_fields import _empty_drug_indication_fields\n"
        "from gen.medula_anchor import _inject_medula_anchor_line\n"
        "from gen.procedures import (\n"
        "    _lookup_ek2b_price,\n"
        "    _pick_blood_uplift_demo_procedures,\n"
        "    _pick_care_setting_review_demo_procedures,\n"
        "    _pick_drg_uplift_demo_procedures,\n"
        "    _pick_gazette_repricing_demo_procedures,\n"
        "    _pick_material_uplift_demo_procedures,\n"
        "    _pick_optional_override_demo_procedures,\n"
        "    _pick_package_adequacy_demo_procedures,\n"
        "    _pick_payment_method_compliance_demo_procedures,\n"
        "    _pick_procedure_addon_demo_procedures,\n"
        "    _pick_procedure_capture_demo_procedures,\n"
        "    _pick_procedures,\n"
        "    _pick_session_uplift_demo_procedures,\n"
        ")\n"
        "from gen.reconcile import _build_normalized_ek2c1_copay_rates\n"
        "from gen.specs import (\n"
        "    PAYMENT_METHOD_COMPLIANCE_DEMO_TAG,\n"
        "    _CLAIM_READINESS_DEMO_SPECS,\n"
        "    _DRUG_INDICATION_DEMO_SPECS,\n"
        "    _MATERIAL_PROSE_DEMO_SPECS,\n"
        "    _MEDULA_DEMO_SPECS,\n"
        ")\n\n",
        [(2378, 2865)],
    ),
    "ancillary.py": (
        '"""Prescription and lab result generation."""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n"
        "import numpy as np\n\n",
        [(2869, 2939)],
    ),
    "workbook.py": (
        '"""Top-level workbook table assembly."""\n\nfrom __future__ import annotations\n\n'
        "import datetime as dt\n"
        "from collections import defaultdict\n\n"
        "import numpy as np\n"
        "import pandas as pd\n\n"
        "from constants import SYNTHETIC_NOTICE\n"
        "from gen.ancillary import _generate_lab_results, _generate_prescriptions\n"
        "from gen.drug_fields import _ensure_drug_indication_columns\n"
        "from gen.materials_flags import _ensure_prose_flag_coverage, _ensure_specialty_flag_coverage\n"
        "from gen.orchestrate import _generate_claims_and_lines\n"
        "from gen.patients import _assign_scenarios, _generate_patients\n"
        "from gen.reconcile import (\n"
        "    _ensure_ek2c1_violation_demos,\n"
        "    _inject_specialty_keyword_demo_rows,\n"
        "    _reconcile_claim_header_totals,\n"
        "    _reconcile_ek2c1_procedure_lines,\n"
        "    _build_normalized_ek2c1_copay_rates,\n"
        ")\n"
        "from catalog import _ek2c1\n\n",
        [(2943, 3046)],
    ),
}


def main() -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    for filename, (header, ranges) in MODULES.items():
        body = "".join(slice_lines(s, e) for s, e in ranges)
        (GEN / filename).write_text(header + body, encoding="utf-8")

    init = '''\
"""Synthetic data generation package (split from generators.py)."""

from gen.claim_lines import ClaimEpisodeContext
from gen.materials_flags import MATERIAL_PROSE_FLAG_COLUMNS, SPECIALTY_PROSE_FLAG_COLUMNS
from gen.specs import (
    PAYMENT_METHOD_COMPLIANCE_DEMO_TAG,
    _CLAIM_READINESS_DEMO_SPECS,
    _DRUG_INDICATION_DEMO_SPECS,
    _MEDULA_DEMO_SPECS,
)
from gen.workbook import build_workbook_tables

__all__ = [
    "ClaimEpisodeContext",
    "MATERIAL_PROSE_FLAG_COLUMNS",
    "SPECIALTY_PROSE_FLAG_COLUMNS",
    "PAYMENT_METHOD_COMPLIANCE_DEMO_TAG",
    "_CLAIM_READINESS_DEMO_SPECS",
    "_DRUG_INDICATION_DEMO_SPECS",
    "_MEDULA_DEMO_SPECS",
    "build_workbook_tables",
]
'''
    (GEN / "__init__.py").write_text(init, encoding="utf-8")

    shim = '''\
"""Backward-compatible shim — import from gen/ implementation."""

from gen import (  # noqa: F401
    MATERIAL_PROSE_FLAG_COLUMNS,
    SPECIALTY_PROSE_FLAG_COLUMNS,
    PAYMENT_METHOD_COMPLIANCE_DEMO_TAG,
    ClaimEpisodeContext,
    _CLAIM_READINESS_DEMO_SPECS,
    _DRUG_INDICATION_DEMO_SPECS,
    _MEDULA_DEMO_SPECS,
    build_workbook_tables,
)

__all__ = [
    "MATERIAL_PROSE_FLAG_COLUMNS",
    "SPECIALTY_PROSE_FLAG_COLUMNS",
    "PAYMENT_METHOD_COMPLIANCE_DEMO_TAG",
    "ClaimEpisodeContext",
    "_CLAIM_READINESS_DEMO_SPECS",
    "_DRUG_INDICATION_DEMO_SPECS",
    "_MEDULA_DEMO_SPECS",
    "build_workbook_tables",
]
'''
    (ROOT / "generators.py").write_text(shim, encoding="utf-8")
    print(f"Wrote {len(MODULES)} modules under {GEN}")


if __name__ == "__main__":
    main()
