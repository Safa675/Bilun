#!/usr/bin/env bash
# Re-runs every check of the money / expected-outputs / MEDULA audit layer.
# Read-only against /home/safa/Documents/Bilun; outputs land in ./out/.
set -euo pipefail
cd "$(dirname "$0")"
PY=/home/safa/Documents/Bilun/.venv/bin/python
for s in a_prices b_arith cd_gap_package m_materials e_surcharge_copay f_expected_outputs g_medula h_magnitudes i_tier_a_and_packages j_header_dx k_extra; do
  echo "=== $s"
  "$PY" "$s.py" > "out/$s.txt" 2>&1
done
echo "all scripts completed"
