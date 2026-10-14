"""Compute the Bilun demo billing reports in-process for the 50 synthetic patients.

Read-only against the repo. Guards:
  * audit hook: refuses any open/list/glob under "raw data/" or ilay_validation/,
    and any write/mkdir/rename/remove outside the scratch output folder;
  * pathlib patch: constants.py's import-time "raw data/" dental-xls probe sees
    the folder as absent (curated EK-2C dental parquet exists, so no result change).
Usage: python -B run_reports.py <out_dir>
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

REPO = pathlib.Path("/home/safa/Documents/Bilun")
OUT = pathlib.Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
FORBIDDEN = (str(REPO / "raw data"), str(REPO / "data/synthetic/sut/claims/ilay_validation"))
CLAIMS = REPO / "data/synthetic/sut/claims"
CLEAN = REPO / "data/synthetic/sut/clean"
VIOLATIONS: list[str] = []


def _p(value) -> str | None:
    if isinstance(value, int):
        return None
    try:
        return os.path.abspath(os.fsdecode(value))
    except Exception:
        return None


def _forbidden(path: str | None) -> bool:
    return bool(path) and any(path == f or path.startswith(f + "/") for f in FORBIDDEN)


def _writable_ok(path: str | None) -> bool:
    return path is None or path.startswith(str(OUT)) or path.startswith("/dev/") or path.startswith("/proc/")


def _hook(event: str, args: tuple) -> None:
    if event == "open":
        path = _p(args[0])
        mode = args[1] or ""
        flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
        if _forbidden(path):
            VIOLATIONS.append(f"open-forbidden {path}")
            raise PermissionError(f"audit guard: {path}")
        wants_write = any(c in str(mode) for c in "wax+") or bool(
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC)
        )
        if wants_write and not _writable_ok(path):
            VIOLATIONS.append(f"write-blocked {path} mode={mode} flags={flags}")
            raise PermissionError(f"audit guard (write): {path}")
    elif event in ("os.listdir", "os.scandir", "glob.glob", "pathlib.Path.glob", "pathlib.Path.rglob"):
        path = _p(args[0]) if args else None
        if _forbidden(path):
            VIOLATIONS.append(f"{event}-forbidden {path}")
            raise PermissionError(f"audit guard: {path}")
    elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.truncate",
                   "os.chmod", "os.utime", "os.link", "os.symlink", "shutil.rmtree",
                   "shutil.copyfile", "shutil.move"):
        paths = [_p(a) for a in args if isinstance(a, (str, bytes, os.PathLike))]
        for path in paths:
            if _forbidden(path) or not _writable_ok(path):
                VIOLATIONS.append(f"{event}-blocked {path}")
                raise PermissionError(f"audit guard ({event}): {path}")


sys.addaudithook(_hook)

_orig_exists = pathlib.Path.exists
_RAW = REPO / "raw data"


def _exists(self, *a, **k):  # hide "raw data/" from the import-time probe
    if self == _RAW or _RAW in self.parents:
        return False
    return _orig_exists(self, *a, **k)


pathlib.Path.exists = _exists  # type: ignore[method-assign]

os.environ["BILUN_DATA_MODE"] = "synthetic_demo"
os.environ["BILUN_CLAIMS_DIR"] = str(CLAIMS)
os.environ["BILUN_CLEAN_DIR"] = str(CLEAN)
sys.path.insert(0, str(REPO))

from src.bilun.cache.build_streaming import json_ready  # noqa: E402
from src.bilun.cache.context import load_sut_build_context  # noqa: E402
from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index  # noqa: E402
from src.bilun.domain.billing.drug_indication_findings import normalize_drug_indication_payload  # noqa: E402
from src.bilun.domain.billing.wavea_full_evidence import build_full_wavea_evidence_index  # noqa: E402


def _api_payload(report) -> dict:
    """json_ready report minus wavea detail, plus the API's dict-branch normalisation."""
    payload = json_ready({k: v for k, v in json_ready(report).items() if k != "wavea_evidence_detail"})
    di = payload.get("drug_indication")
    if isinstance(di, dict):
        norm = normalize_drug_indication_payload(di)
        payload["drug_indication"] = norm
        payload["drug_indication_violation_count"] = norm.get("violation_count", 0)
    block = payload.get("medula_rejection_playbook")
    if isinstance(block, dict) and isinstance(block.get("entries"), list):
        payload["medula_playbook_entry_count"] = len(block["entries"])
    return payload


t0 = time.perf_counter()
ctx = load_sut_build_context(
    billing_workers=4,
    sut_data_mode="synthetic_demo",
    sut_claims_dir=CLAIMS,
    sut_clean_dir=CLEAN,
)
elapsed = time.perf_counter() - t0

patient_reports = {pid: _api_payload(r) for pid, r in ctx["billing_reports"].items()}
bill_reports = {key: _api_payload(r) for key, r in ctx.get("bill_billing_reports", {}).items()}
wavea_details = {pid: json_ready(r.wavea_evidence_detail) for pid, r in ctx["billing_reports"].items()}

outputs = {
    "patient_billing_reports.json": patient_reports,
    "bill_billing_reports.json": bill_reports,
    "cohort_recovery_summary.json": json_ready(ctx.get("revenue_recovery", {})),
    "cohort_compliance_index.json": build_cohort_compliance_index(patient_reports),
    "wavea_evidence_index.json": build_full_wavea_evidence_index(wavea_details),
    "patient_alerts_cache.json": json_ready(ctx.get("patient_alerts_cache", {})),
    "optimization_summary.json": json_ready(ctx.get("optimization_summary", {})),
    "data_source.json": json_ready(ctx.get("sut_data_source", {})),
}
for name, obj in outputs.items():
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print(f"patients={len(patient_reports)} bills={len(bill_reports)} elapsed={elapsed:.1f}s")
print(f"guard_violations={VIOLATIONS}")
