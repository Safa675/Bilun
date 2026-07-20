"""SUT pipeline end-to-end smoke runner (Data Engineer agent).

Chains the 5 canonical SUT-ingest scripts in sequence against a TEMP output directory
(never the real ``data/gazette/``) and fails fast on the first stage that exits nonzero.
The point is to surface latent pipeline bugs (missing deps, schema drift, broken
partition logic) the way a real consolidated-SUT replace would — without mutating any
committed artifact.

Stages (each a subprocess):
  1. convert_xlsx_to_parquet   raw xlsx → raw parquet + version_manifest
  2. build_curated_catalogs    raw parquet → curated catalogs
  3. extract_sut_prose         consolidated docx → sut_clauses.parquet
  4. build_sut_coverage        clauses → coverage matrix
  5. validate_parquet          post-hoc validation

Why a temp dir: per the 2026-06-30 lesson, an investigation step must NEVER overwrite the
real committed parquet it is observing. This runner writes only under a temp subdir that is
INSIDE the repo (``data/gazette/.pipeline_smoke_tmp/``) — it must be inside the repo because
``convert_xlsx_to_parquet`` computes output paths relative to PROJECT_ROOT (paths outside
the repo raise "is not in the subpath"). The temp dir is gitignored and cleaned up on
success unless ``--keep-temp`` is passed. A panic guard removes it on any exit so it never
pollutes the working tree.

Exit codes:
  0 — all 5 stages passed
  1 — at least one stage failed (stderr tail printed, temp dir preserved for debugging)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

# Temp dir MUST live inside the repo: convert_xlsx_to_parquet computes output paths
# relative to PROJECT_ROOT, so paths outside the repo raise "is not in the subpath".
# This subdir is gitignored (added to .gitignore by the agent setup) and removed on exit.
TEMP_BASE = PROJECT_ROOT / "data" / "gazette" / ".pipeline_smoke_tmp"

# The consolidated docx used by extract_sut_prose. Prefer the latest on-disk package.
DEFAULT_DOCX_CANDIDATES = [
    PROJECT_ROOT / "raw data" / "2026.07.01-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"
    / "2026.07.01-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"
    / "01.07.2026 - Değişiklik Tebliği İşlenmiş Güncel 2013 SUT.docx",
    PROJECT_ROOT / "raw data" / "2026.05.23-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"
    / "23.05.2026 - Değişiklik Tebliği İşlenmiş Güncel 2013 SUT.docx",
]


def find_docx() -> Path | None:
    for cand in DEFAULT_DOCX_CANDIDATES:
        if cand.exists():
            return cand
    # last resort: glob
    hits = sorted((PROJECT_ROOT / "raw data").rglob("*İşlenmiş*.docx"))
    return hits[0] if hits else None


def run_stage(name: str, cmd: list[str]) -> tuple[int, float, str, str]:
    """Run one pipeline stage as a subprocess. Returns (exit_code, elapsed_s, stdout, stderr)."""
    start = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    elapsed = time.monotonic() - start
    return proc.returncode, elapsed, proc.stdout, proc.stderr


def discover_annexes(raw_root: Path) -> list[str]:
    """Glob the temp raw dir for annex=* partitions produced by stage 1.
    Returns sorted list like ['EK-1A', 'EK-1C', 'EK-2A']."""
    annexes = set()
    for p in raw_root.rglob("*.parquet"):
        for part in p.parts:
            if part.startswith("annex="):
                annexes.add(part.removeprefix("annex="))
    return sorted(annexes)


def build_stages(temp_dir: Path, docx: Path | None, limit: int | None) -> list[tuple[str, list[str]]]:
    """Construct the stage command list. Stage 2's --annex list is a placeholder here
    and gets filled in dynamically AFTER stage 1 runs (see main loop) — because we
    only want to curate the annexes stage 1 actually produced, not all 40 (which would
    spuriously fail on missing annexes when --limit is set)."""
    raw_out = temp_dir / "raw"
    curated_root = temp_dir / "raw"  # build_curated reads the parquet-root (where raw lives)
    clauses_out = temp_dir / "sut_clauses.parquet"
    coverage_out = temp_dir / "coverage"

    convert_cmd = [
        sys.executable, "-m", "scripts.sut.convert_xlsx_to_parquet",
        "--output-dir", str(raw_out),
        "--overwrite-manifest",
    ]
    if limit is not None:
        convert_cmd += ["--limit", str(limit)]

    # NOTE: stage 2 uses ANNEX_PLACEHOLDER; the main loop rewrites this after stage 1.
    stages: list[tuple[str, list[str]]] = [
        ("1_convert_xlsx_to_parquet", convert_cmd),
        ("2_build_curated_catalogs", [
            sys.executable, "-m", "scripts.sut.build_curated_catalogs",
            "--parquet-root", str(curated_root),
            "--overwrite",
            "--annex", "ANNEX_PLACEHOLDER",
        ]),
    ]

    if docx is not None:
        stages.append(("3_extract_sut_prose", [
            sys.executable, "-m", "scripts.sut.extract_sut_prose",
            "--docx", str(docx),
            "--output", str(clauses_out),
        ]))
        stages.append(("4_build_sut_coverage", [
            sys.executable, "-m", "scripts.sut.build_sut_coverage",
            "--clauses", str(clauses_out),
            "--output-dir", str(coverage_out),
        ]))
    else:
        # No docx found — skip stages 3-4 but record why.
        stages.append(("3_extract_sut_prose_SKIPPED", [
            "echo", "SKIPPED: no consolidated docx found under raw data/",
        ]))
        stages.append(("4_build_sut_coverage_SKIPPED", [
            "echo", "SKIPPED: depends on stage 3",
        ]))

    stages.append(("5_validate_parquet", [
        sys.executable, "-m", "scripts.sut.validate_parquet",
        "--output-dir", str(raw_out),
    ]))
    return stages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keep-temp", action="store_true", help="Keep temp dir on success for debugging")
    parser.add_argument("--limit", type=int, default=5, help="Max XLSX files for stage 1 (default 5, keeps it fast)")
    parser.add_argument("--no-timeout", action="store_true", help="Disable per-stage 600s timeout (not recommended)")
    args = parser.parse_args()

    docx = find_docx()
    if docx is None:
        print("[pipeline_smoke] WARNING: no consolidated docx found; stages 3-4 will be skipped", file=sys.stderr)
    else:
        print(f"[pipeline_smoke] docx: {docx.relative_to(PROJECT_ROOT)}")

    # Temp dir INSIDE the repo (see TEMP_BASE comment). mkdtemp under TEMP_BASE so
    # multiple runs don't clobber each other.
    TEMP_BASE.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="run_", dir=TEMP_BASE))
    print(f"[pipeline_smoke] temp_dir: {temp_dir.relative_to(PROJECT_ROOT)}")

    def _cleanup() -> None:
        if temp_dir.exists() and not args.keep_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # onsigint / normal-exit cleanup. On a non-keep-temp success we clean explicitly below;
    # the atexit guard handles abnormal termination (KeyboardInterrupt, exception, SystemExit).
    import atexit
    atexit.register(_cleanup)

    stages = build_stages(temp_dir, docx, args.limit)
    results: list[tuple[str, int, float]] = []
    overall_start = time.monotonic()
    failed = False
    stage1_done = False

    for name, cmd in stages:
        is_skipped = "_SKIPPED" in name

        # After stage 1 succeeds, fill in stage 2's --annex list dynamically so we only
        # curate what stage 1 actually produced (avoids spurious missing-annex failures
        # when --limit is set).
        if name == "2_build_curated_catalogs" and stage1_done:
            annexes = discover_annexes(temp_dir / "raw")
            if annexes:
                # replace the ANNEX_PLACEHOLDER token with the discovered list
                cmd = [c for c in cmd if c != "ANNEX_PLACEHOLDER"] + annexes
                print(f"[pipeline_smoke] stage 2 scoped to annexes: {annexes}")
            else:
                print("[pipeline_smoke] WARN: stage 1 produced no annexes; stage 2 will likely fail")

        print(f"\n[pipeline_smoke] >>> {name}")
        if is_skipped:
            # echo-style placeholder; just run it (it prints the skip reason)
            r = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True)
            print(r.stdout.strip())
            results.append((name, 0, 0.0))
            continue

        # Rebuild with timeout override if requested
        timeout = None if args.no_timeout else 600
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout,
            )
            elapsed = time.monotonic() - start
            results.append((name, proc.returncode, elapsed))
            status = "PASS" if proc.returncode == 0 else f"FAIL (exit {proc.returncode})"
            print(f"[pipeline_smoke] {status} — {elapsed:.1f}s")
            if name == "1_convert_xlsx_to_parquet" and proc.returncode == 0:
                stage1_done = True
            # tail stdout (last 8 lines) so we see what it did
            stdout_tail = "\n".join((proc.stdout or "").splitlines()[-8:])
            if stdout_tail.strip():
                for line in stdout_tail.splitlines():
                    print(f"  | {line}")
            if proc.returncode != 0:
                failed = True
                stderr_tail = "\n".join((proc.stderr or "").splitlines()[-20:])
                print("[pipeline_smoke] stderr tail:")
                for line in stderr_tail.splitlines():
                    print(f"  ! {line}")
                break  # fail fast
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            results.append((name, 124, elapsed))
            print(f"[pipeline_smoke] FAIL (timeout after {timeout}s)")
            failed = True
            break

    total_elapsed = time.monotonic() - overall_start
    print(f"\n[pipeline_smoke] {'FAIL' if failed else 'PASS'} — total {total_elapsed:.1f}s")
    print("[pipeline_smoke] stage summary:")
    for name, code, elapsed in results:
        marker = "✗" if code != 0 else "✓"
        print(f"  {marker} {name:35s} exit={code:<3} {elapsed:6.1f}s")

    if failed:
        print(f"\n[pipeline_smoke] temp dir preserved for debugging: {temp_dir.relative_to(PROJECT_ROOT)}")
        return 1
    if not args.keep_temp:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("[pipeline_smoke] cleaned temp dir (use --keep-temp to preserve)")
    else:
        print(f"[pipeline_smoke] kept temp dir: {temp_dir.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
