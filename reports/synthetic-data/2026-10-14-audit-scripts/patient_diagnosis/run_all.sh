#!/usr/bin/env bash
# Re-runs every check of the patient/diagnosis realism audit. Read-only on the repo; outputs go to ./out/
set -euo pipefail
cd "$(dirname "$0")"
PY=/home/safa/Documents/Bilun/.venv/bin/python
rm -f out/*.txt out/*.csv
for s in a_demographics b_icd c_sex_age_lines d_diag_sets e_longitudinal f_vitals g_freetext h_copay x_crosslayer; do
  "$PY" -W ignore "$s.py" > /dev/null
  echo "ok $s -> out/$s.txt"
done
