import polars as pl
R="/home/safa/Documents/Bilun/data/synthetic/sut/"
pr=pl.read_parquet(R+"claims/procedure_claim_lines.parquet")
dr=pl.read_parquet(R+"claims/drug_claim_lines.parquet")
ma=pl.read_parquet(R+"claims/material_claim_lines.parquet")
pp=pl.read_parquet(R+"claims/performed_procedure_lines.parquet")
with open("07_proc_names.txt","w") as f:
    for c,n,cat,k in pr.group_by("procedure_code","procedure_name","procedure_category").agg(pl.len()).sort("procedure_category","procedure_name").iter_rows():
        f.write(f"{cat}\t{c}\t{k}\t{n}\n")
with open("07_drug_names.txt","w") as f:
    for n,k in dr.group_by("drug_name").agg(pl.len()).sort("drug_name").iter_rows():
        f.write(f"{k}\t{n}\n")
with open("07_material_names.txt","w") as f:
    for n,k in ma.group_by("material_name").agg(pl.len()).sort("material_name").iter_rows():
        f.write(f"{k}\t{n}\n")
print(pr["procedure_name"].n_unique(), dr["drug_name"].n_unique(), ma["material_name"].n_unique())
print(pp)
print(pr.group_by("procedure_category").agg(pl.len()))
