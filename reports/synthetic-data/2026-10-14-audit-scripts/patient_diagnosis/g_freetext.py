"""(g) Free text (YAKINMA, OYKU, Muayene Notu, Tedavi Notu): templating, clinical content, agreement with episode."""
from common import claims, episodes, write, tr_fold
import polars as pl

ep = episodes().sort("HASTA_ID", "edate")
lines = []
P = lines.append
TXT = ["YAKINMA", "OYKU", "Muayene Notu", "Tedavi Notu"]
pat = r"^(.+) sentetik (yakınma|öykü|muayene|tedavi) - epizot (\d+)$"
for c in TXT:
    m = ep.filter(pl.col(c).str.contains(pat))
    P(f"{c}: rows={ep.height} distinct={ep[c].n_unique()} match template '<SERVISADI> sentetik <kind> - epizot <n>': {m.height}; mean length {round(ep[c].str.len_chars().mean(),1)} chars")
ep = ep.with_columns(
    pl.col("YAKINMA").str.extract(pat, 1).alias("txt_dept"),
    pl.col("YAKINMA").str.extract(pat, 3).cast(pl.Int32).alias("txt_n"),
    pl.col("SQ_EPISODE").str.slice(-3).cast(pl.Int32).alias("seq"),
    pl.col("edate").rank("ordinal").over("HASTA_ID").cast(pl.Int32).alias("chron"),
)
P(f"department named in text == SERVISADI: {ep.filter(pl.col('txt_dept') == pl.col('SERVISADI')).height}/94; 'epizot n' == episode id suffix: {ep.filter(pl.col('txt_n') == pl.col('seq')).height}/94; 'epizot n' == chronological visit number: {ep.filter(pl.col('txt_n') == pl.col('chron')).height}/94")
P(f"text-vs-ward mismatches: {ep.filter(pl.col('txt_dept') != pl.col('SERVISADI')).select('SQ_EPISODE', 'tier', 'txt_dept', 'SERVISADI').rows()}")
# any clinical vocabulary at all?
CLIN = [r"\bagri", r"\bates", r"\boksuruk", r"\bnefes", r"\bsikayet", r"\btansiyon", r"\bbulanti", r"\bkusma", r"\bhalsiz", r"\bgogus", r"\bdispne", r"\bmuayenede\b", r"\bbatin", r"\bekstremite", r"\bnormal\b", r"\breçete|\brecete", r"\bilac", r"\bameliyat", r"\bgun\b", r"\byil\b", r"\bkg\b", r"\bmg\b", r"\bicd", r"[A-Z]\d\d\.\d"]
allt = ep.select(pl.concat_str([pl.col(c) for c in TXT], separator=" || ").alias("t")).with_columns(tr_fold(pl.col("t")).alias("f"))
hit = allt.filter(pl.any_horizontal([pl.col("f").str.contains(p) for p in CLIN]))
P(f"episodes whose 4 notes contain ANY clinical word from {len(CLIN)} patterns (agri, ates, oksuruk, nefes, sikayet, tansiyon, ...): {hit.height}/94  (note: 'gogus' only via department name 'Gogus Hastaliklari')")
hit2 = allt.with_columns(pl.col("f").str.replace_all(r"gogus hastaliklari", "")).filter(pl.any_horizontal([pl.col("f").str.contains(p) for p in CLIN]))
P(f"...after removing the department name: {hit2.height}/94")
# representative mismatches
pp = claims("performed_procedure_lines")
pr = claims("procedure_claim_lines")
def show(eid, why):
    r = ep.filter(pl.col("SQ_EPISODE") == eid).row(0, named=True)
    P(f"- {eid} (tier {r['tier']}, {r['CINSIYET']} {r['TANI_YASI']}y, {r['edate']}, {r['claim_type']}, primary {r['primary_icd10']}, codes {r['TUM_EPS_TANILAR']}): {why}")
    for c in TXT:
        P(f"    {c}: \"{r[c]}\"")
show("B-SENTETIK-HASTA-0038-001", "AML (C92.0) admission; notes name only the (wrong) ward 'Gogus Hastaliklari', nothing about leukaemia")
show("B-SENTETIK-HASTA-0001-005", "this is the patient's chronologically FIRST visit (2023-06-22) but the text says 'epizot 5'")
r9 = pp.filter(pl.col("patient_id") == "SENTETIK-HASTA-0009").select("procedure_name").to_series().to_list()
show("B-SENTETIK-HASTA-0009-001", f"Tier A capture demo: EMR performed {r9} on a lumbar-disc (M51.1) orthopaedics day case; notes say nothing")
r16 = pr.filter(pl.col("claim_id") == "F-SENTETIK-HASTA-0016-030").select("procedure_name").to_series().to_list()
show("B-SENTETIK-HASTA-0016-001", f"66-year-old man, chest-diseases day case billed for {r16}")
write("g_freetext.txt", "\n".join(lines))
