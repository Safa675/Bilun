#!/usr/bin/env bash
# Re-runs the whole materials-layer audit in dependency order. Read-only on the repo;
# writes only *.parquet / *.txt next to this script.
set -euo pipefail
cd "$(dirname "$0")"
PY=/home/safa/Documents/Bilun/.venv/bin/python
$PY 10_build_ek3_index.py        > 10_index.txt
$PY 20_identity.py               > 20_identity.txt
$PY 31_ek2b_anchor_procs.py      > 31_ek2b_anchor.txt
$PY 32_material_procedure_link.py > 32_link.txt
$PY 35_care_setting.py           > 35_setting.txt
$PY 40_specialty_department.py   > 40_specialty.txt
$PY 45_patient_fit.py            > 45_patient_fit.txt
$PY 50_prices_quantities.py      > 50_prices.txt
$PY 60_flags.py                  > 60_flags.txt
$PY 70_admin_fields.py           > 70_admin.txt
echo "all scripts OK"
