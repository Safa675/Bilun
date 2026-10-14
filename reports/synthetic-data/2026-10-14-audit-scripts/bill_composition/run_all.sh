#!/usr/bin/env bash
# Reproduce every number in the bill-composition audit (read-only on the repo).
set -euo pipefail
cd "$(dirname "$0")"
PY=/home/safa/Documents/Bilun/.venv/bin/python
mkdir -p rerun
$PY 10_build_chapter_map.py        > rerun/out_10_chapter_map.txt 2>&1
$PY 20_enrich.py                   > rerun/out_20_enrich.txt 2>&1
$PY 30_checks_a_b.py               > rerun/out_30_checks_a_b.txt 2>&1
$PY 31_checks_c_d.py               > rerun/out_31_checks_c_d.txt 2>&1
$PY 32_checks_e_f_g_h.py           > rerun/out_32_checks_e_f_g_h.txt 2>&1
$PY 33_sensitivity.py              > rerun/out_33_sensitivity.txt 2>&1
$PY 34_tier_rollup.py              > rerun/out_34_tier_rollup.txt 2>&1
$PY 35_codes_before_existence.py   > rerun/out_35_codes_before_existence.txt 2>&1
echo "all scripts ran"
