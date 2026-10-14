"""Exploration dump of material_claim_lines (read-only)."""
import polars as pl

B = "/home/safa/Documents/Bilun/data/synthetic/sut/claims/"
m = pl.read_parquet(B + "material_claim_lines.parquet")

core = [
    "material_line_id", "claim_id", "procedure_line_id", "patient_id", "material_date",
    "material_code", "material_name", "material_type", "specialty_category", "quantity",
    "unit_price_try", "billed_amount_try", "expected_payable_try", "is_bundled",
    "requires_pre_auth", "titubb_registered", "uts_registered", "denial_reason_expected",
    "rule_trace_expected",
]
for row in m.select(core).iter_rows(named=True):  # dump only (81 rows) - not analysis
    print(" | ".join(f"{k}={row[k]}" for k in core))
