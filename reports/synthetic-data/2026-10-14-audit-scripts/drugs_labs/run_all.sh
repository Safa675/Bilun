#!/usr/bin/env bash
# Re-runs every check of the drugs/labs audit layer. Read-only on the repo; writes only to ./out/.
set -euo pipefail
cd "$(dirname "$0")"
PY=/home/safa/Documents/Bilun/.venv/bin/python
mkdir -p out
for s in a_drug_vs_recete b_drug_vs_ek4a c_drug_diversity d_drug_indication e_drug_money \
         f_lab_values g_lab_vs_dx h_lab_billed_vs_results s_tier_a_view; do
  echo ">>> $s"
  "$PY" "$s.py" > "out/$s.txt" 2>&1
done
echo "done: outputs in $(pwd)/out"
