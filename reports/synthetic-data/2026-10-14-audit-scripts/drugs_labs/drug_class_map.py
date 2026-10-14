"""JUDGMENT TABLE: drug_code -> active ingredient, narrow therapeutic class, lenient ICD-10 indication set,
sex restriction, pediatric flag, prescriber home specialty.

Basis column: 'EK-4A sib <grp>' = active ingredient inferred from a well-known brand in the same EK-4A
equivalence group (catalog evidence); 'brand' = auditor's pharmacological knowledge (judgment).
ICD sets are deliberately LENIENT (any plausible on-label or common use); a line fails only if NO
diagnosis in the set appears on the claim (or, in the lenient variant, anywhere in the patient's history).
Drugs without a narrow indication (IV fluids, analgesics, most antibiotics, PPIs, steroids, generic topicals,
nutrition, unknown brands) are NOT in this table and are excluded from the indication test.
"""
ONC = "C00-D09;D37-D48;Z51.0;Z51.1"
APS = "F00-F99;G30-G31"
AED = "G40-G41;R56;F31;S06;C71;I60-I62;G93"
GABA = "G40;G50-G64;E10-E14;M79;B02.2;F41;M54;M51;M47;G89;R52"
HTN = "I10-I15;I20-I25;I50;I60-I69;I70;N18;E10-E14;I48;I42"
LIPID = "E78;I20-I25;I63-I69;I70;E10-E14;Z95;I73;N18;G45"
DM = "E10-E14;R73;O24"
FUNG = "B35-B49;D70;C81-C96;Z94"
EYE = "H00-H59;S05;T15;T26"
OAB = "N31-N32;N39.3;N39.4;R32;R35;R39"

# code: (inn, class, icd_spec, sex, peds, home_specialty, basis)
MAP = {
    # ---- onco-hematology
    "A03647": ("ifosfamide", "antineoplastic", ONC, "", "", "onkoloji", "brand"),
    "A12259": ("doxorubicin", "antineoplastic", ONC, "", "", "onkoloji", "EK-4A sib E379A DOXORUBICIN"),
    "A11363": ("paclitaxel", "antineoplastic", ONC, "", "", "onkoloji", "EK-4A sib E275C"),
    "A16820": ("carboplatin", "antineoplastic", ONC, "", "", "onkoloji", "EK-4A sib E253C CARBOPLATIN"),
    "A03698": ("hydroxyurea", "antineoplastic", ONC + ";D57;D75", "", "", "hematoloji", "brand"),
    "A16058": ("trametinib", "antineoplastic_targeted", "C43;C34", "", "", "onkoloji", "brand"),
    "A19382": ("dacomitinib", "antineoplastic_targeted", "C34", "", "", "onkoloji", "brand"),
    "A18882": ("erlotinib", "antineoplastic_targeted", "C34;C25", "", "", "onkoloji", "EK-4A sib E720C LUNGERLO/ETINIB"),
    "A19390": ("dasatinib", "antineoplastic_targeted", "C92.1;C91.0", "", "", "hematoloji", "EK-4A sib E901C SPRYCEL"),
    "A19759": ("selinexor", "antineoplastic_targeted", "C90.0;C83.3", "", "", "hematoloji", "brand"),
    "A20245": ("pomalidomide", "antineoplastic_targeted", "C90.0", "", "", "hematoloji", "EK-4A sib E789D IMNOVID"),
    "A17867": ("daratumumab", "antineoplastic_targeted", "C90.0;E85", "", "", "hematoloji", "brand"),
    "A18333": ("bevacizumab", "antineoplastic_targeted", "C18-C20;C34;C50;C53;C56;C64;C71", "", "", "onkoloji", "brand"),
    "A00892": ("exemestane", "antineoplastic_hormonal", "C50", "", "", "onkoloji", "brand"),
    "A00759": ("cyproterone acetate", "antiandrogen", "C61;L68.0;E28.2;L70;F65", "", "", "uroloji/onkoloji", "brand"),
    "A19063": ("eculizumab", "complement_inhibitor", "D59.5;D59.3;G70.0;G36.0", "", "", "hematoloji", "brand"),
    "A17692": ("plerixafor", "stem_cell_mobilizer", "C81-C96", "", "", "hematoloji", "EK-4A sib E846A MOZOBIL"),
    "A20070": ("plerixafor", "stem_cell_mobilizer", "C81-C96", "", "", "hematoloji", "EK-4A sib E846A MOZOBIL"),
    "A19583": ("pegfilgrastim", "g_csf", ONC + ";D70", "", "", "onkoloji", "EK-4A sib E946A NEULASTIM"),
    "A00869": ("darbepoetin alfa", "esa", "N18;N19;D63;D64;D46;" + ONC, "", "", "nefroloji/onkoloji", "brand"),
    "A04463": ("granisetron (oral)", "antiemetic_chemo", ONC + ";R11", "", "", "onkoloji", "EK-4A sib E202A"),
    "A04381": ("factor VIII/vWF (plasma)", "coagulation_factor", "D66;D68.0;D68.3;D68.4", "", "", "hematoloji", "name"),
    "A14364": ("factor VIII (moroctocog)", "coagulation_factor", "D66;D68.3", "", "", "hematoloji", "EK-4A sib E144D ADVATE"),
    "A17082": ("factor VIII (turoctocog)", "coagulation_factor", "D66;D68.3", "", "", "hematoloji", "EK-4A sib E144I ADVATE"),
    "A14683": ("factor IX (nonacog)", "coagulation_factor", "D67;D68.3", "", "", "hematoloji", "EK-4A sib E145D RIXUBIS"),
    "A17438": ("protein C concentrate", "coagulation_factor", "D68.5;D68.6;D65", "", "", "hematoloji", "brand"),
    "A17793": ("immunoglobulin SC + hyaluronidase", "immunoglobulin", "D80-D84;G61;G70;D69.3;C91.1;C90", "", "", "immunoloji", "brand"),
    # ---- infection-specific
    "A12794": ("darunavir", "hiv_arv", "B20-B24;Z21", "", "", "enfeksiyon", "brand"),
    "A06709": ("zidovudine IV", "hiv_arv", "B20-B24;Z21;O98.7;Z20.6", "", "", "enfeksiyon", "brand"),
    "A12599": ("tenofovir disoproxil", "hbv_hiv_antiviral", "B16;B18.0;B18.1;B19;B20-B24;Z21;Z22.5", "", "", "enfeksiyon/gastro", "EK-4A sib E594A"),
    "A18907": ("ganciclovir IV", "cmv_antiviral", "B25;B20-B24;Z94;T86", "", "", "enfeksiyon", "EK-4A sib E795A"),
    "A20066": ("valacyclovir 1 g", "herpes_antiviral", "B00-B02", "", "", "enfeksiyon/derm", "EK-4A sib E464B VALTREX"),
    "A18272": ("oseltamivir suspension", "influenza_antiviral", "J09-J11", "", "likely", "enfeksiyon/pediatri", "EK-4A sib E522C"),
    "A04289": ("ketoconazole oral", "systemic_antifungal", "B35-B49", "", "", "derm/enfeksiyon", "brand"),
    "A16340": ("voriconazole IV", "systemic_antifungal", FUNG, "", "", "enfeksiyon/hematoloji", "EK-4A sib E650C VFEND"),
    "A20113": ("voriconazole IV", "systemic_antifungal", FUNG, "", "", "enfeksiyon/hematoloji", "EK-4A sib E650C VFEND"),
    "A19047": ("anidulafungin", "systemic_antifungal", FUNG, "", "", "enfeksiyon/hematoloji", "EK-4A sib E751A ERAXIS"),
    "A17475": ("anidulafungin", "systemic_antifungal", FUNG, "", "", "enfeksiyon/hematoloji", "EK-4A sib E751A ERAXIS"),
    # ---- immunology / transplant
    "A05223": ("mycophenolate sodium", "transplant_immunosuppressant", "Z94;T86;M32;N04;N05", "", "", "nefroloji/transplant", "brand"),
    "A14551": ("abatacept SC", "biologic_dmard", "M05-M06;M08", "", "", "romatoloji", "brand"),
    "A19868": ("adalimumab", "biologic_dmard", "M05-M08;M45;L40;K50-K51;L73.2;H20", "", "", "romatoloji", "EK-4A sib E667A HUMIRA"),
    "A16848": ("methotrexate SC", "csdmard", "M05-M08;M45;L40;K50;M32-M35;C00-D09", "", "", "romatoloji", "EK-4A sib E168J"),
    "A20080": ("methotrexate SC", "csdmard", "M05-M08;M45;L40;K50;M32-M35;C00-D09", "", "", "romatoloji", "EK-4A sib E168K"),
    # ---- psychiatry / neurology
    "A10348": ("risperidone", "antipsychotic", APS, "", "", "psikiyatri", "EK-4A sib E361A RISPERDAL"),
    "A12685": ("aripiprazole", "antipsychotic", APS, "", "", "psikiyatri", "EK-4A sib E537D ABILIFY"),
    "A10711": ("paliperidone", "antipsychotic", APS, "", "", "psikiyatri", "brand"),
    "A13389": ("olanzapine", "antipsychotic", APS, "", "", "psikiyatri", "EK-4A sib E329F"),
    "A11588": ("quetiapine", "antipsychotic", APS, "", "", "psikiyatri", "EK-4A sib E344A"),
    "A06814": ("risperidone LAI", "antipsychotic", APS, "", "", "psikiyatri", "brand"),
    "A03086": ("flupentixol", "antipsychotic", APS, "", "", "psikiyatri", "brand"),
    "A17908": ("methylphenidate OROS", "adhd_stimulant", "F90;G47.4", "", "", "psikiyatri", "EK-4A sib E859B CONCERTA"),
    "A16712": ("memantine XR", "antidementia", "F00-F03;G30-G31", "", "", "noroloji/psikiyatri", "brand"),
    "A14078": ("pramipexole ER", "antiparkinson", "G20-G21;G25.8", "", "", "noroloji", "brand"),
    "A02196": ("valproate IV", "antiepileptic", AED, "", "", "noroloji", "EK-4A sib E876A"),
    "A11109": ("zonisamide", "antiepileptic", AED, "", "", "noroloji", "EK-4A sib E844A"),
    "A12960": ("levetiracetam oral sol.", "antiepileptic", AED, "", "", "noroloji", "EK-4A sib E372F KEPPRA"),
    "A08051": ("oxcarbazepine susp.", "antiepileptic", AED, "", "likely", "noroloji", "brand"),
    "A17893": ("phenytoin IV", "antiepileptic", AED, "", "", "noroloji", "EK-4A sib E193A EPANUTIN"),
    "A11934": ("gabapentin", "gabapentinoid", GABA, "", "", "noroloji/algoloji", "EK-4A sib E360E NEURONTIN"),
    "A18515": ("pregabalin", "gabapentinoid", GABA, "", "", "noroloji/algoloji", "brand"),
    "A12294": ("pregabalin", "gabapentinoid", GABA, "", "", "noroloji/algoloji", "EK-4A sib E575D LYRICA"),
    "A14425": ("duloxetine", "snri", "F32-F33;F41;E10-E14;G62-G63;M79;M54;M16-M17;M47", "", "", "psikiyatri", "EK-4A sib E601A"),
    "A08299": ("betahistine", "antivertigo", "H81;H83;R42", "", "", "kbb/noroloji", "EK-4A sib E256B BETASERC"),
    # ---- cardio-metabolic
    "A11676": ("vildagliptin", "antidiabetic", DM, "", "", "endokrin", "brand"),
    "A20202": ("linagliptin/metformin", "antidiabetic", DM, "", "", "endokrin", "EK-4A sib E944A"),
    "A20045": ("alpha-lipoic acid", "neuropathy_ala", "E10-E14;G62-G63", "", "", "noroloji/endokrin", "EK-4A sib E584A THIOCTACID"),
    "A03800": ("indapamide", "antihypertensive", HTN, "", "", "kardiyoloji/dahiliye", "EK-4A sib E027A"),
    "A03817": ("cilazapril", "antihypertensive", HTN, "", "", "kardiyoloji/dahiliye", "brand"),
    "A12173": ("candesartan", "antihypertensive", HTN, "", "", "kardiyoloji/dahiliye", "EK-4A sib E239D"),
    "A15117": ("amlodipine/valsartan/HCTZ", "antihypertensive", HTN, "", "", "kardiyoloji/dahiliye", "brand"),
    "A18151": ("candesartan/amlodipine/HCTZ", "antihypertensive", HTN, "", "", "kardiyoloji/dahiliye", "EK-4A sib E851D"),
    "A19022": ("candesartan/amlodipine", "antihypertensive", HTN, "", "", "kardiyoloji/dahiliye", "EK-4A sib E851E"),
    "A15316": ("benidipine", "antihypertensive", HTN, "", "", "kardiyoloji/dahiliye", "brand"),
    "A11475": ("ramipril", "antihypertensive", HTN, "", "", "kardiyoloji/dahiliye", "EK-4A sib E365A DELIX"),
    "A09435": ("atorvastatin", "lipid_lowering", LIPID, "", "", "kardiyoloji/dahiliye", "brand"),
    "A09794": ("atorvastatin", "lipid_lowering", LIPID, "", "", "kardiyoloji/dahiliye", "EK-4A sib E008C"),
    "A09799": ("atorvastatin", "lipid_lowering", LIPID, "", "", "kardiyoloji/dahiliye", "EK-4A sib E008A"),
    "A15428": ("ezetimibe", "lipid_lowering", LIPID, "", "", "kardiyoloji/dahiliye", "brand"),
    "A18721": ("apixaban 2.5", "doac", "I48;I26;I80-I82;Z96.6;I63-I64;Z86.7;I74;M16-M17", "", "", "kardiyoloji", "EK-4A sib E826A ELIQUIS"),
    "A19785": ("edoxaban 60", "doac", "I48;I26;I80-I82;I63-I64;Z86.7;I74", "", "", "kardiyoloji", "EK-4A sib E966B LIXIANA"),
    "A20272": ("macitentan/tadalafil", "pah", "I27", "", "", "kardiyoloji/gogus", "brand"),
    "A18801": ("levosimendan", "inotrope_icu", "I50;I21;R57.0;I42", "", "", "kardiyoloji/yogun bakim", "EK-4A sib E883A SIMDAX"),
    "A18922": ("esmolol IV", "iv_betablocker", "I47-I49;I10-I15;I20-I25;R00", "", "", "kardiyoloji/anestezi", "EK-4A sib E721A BREVIBLOC"),
    "A16367": ("paricalcitol IV", "ckd_mbd", "N18;N19;N25.8;E21;E83.5", "", "", "nefroloji", "EK-4A sib E651A"),
    "A18729": ("albumin 20%", "albumin", "K70-K77;R18;E88.0;N04;R57;T20-T32;E40-E46;R60;I85", "", "", "dahiliye/yogun bakim", "EK-4A sib E213E"),
    # ---- respiratory
    "A17922": ("pirfenidone", "antifibrotic", "J84", "", "", "gogus", "brand"),
    "A16790": ("salmeterol/fluticasone", "inhaled_resp", "J44-J45;J41-J43;J47;J98", "", "", "gogus", "EK-4A sib E597M"),
    "A06484": ("budesonide nebul.", "inhaled_resp", "J44-J45;J05;J20-J21;J96;J47;J98;J18", "", "", "gogus", "EK-4A sib E425F"),
    "A07300": ("montelukast", "leukotriene", "J45;J30-J31;J44;L50", "", "", "gogus/allerji", "EK-4A sib E327C"),
    "A12020": ("desloratadine/montelukast", "leukotriene", "J45;J30-J31;J44;L50", "", "", "gogus/allerji", "EK-4A sib E558A"),
    # ---- urology / gynecology / endocrine / misc
    "A12893": ("solifenacin", "oab", OAB, "", "", "uroloji", "EK-4A sib E564B"),
    "A20259": ("tolterodine", "oab", OAB, "", "", "uroloji", "EK-4A sib E367B DETRUSITOL"),
    "A17404": ("propiverine", "oab", OAB, "", "", "uroloji", "EK-4A sib E674C"),
    "A12118": ("alfuzosin", "bph", "N40;R33;N13;R39", "M", "", "uroloji", "EK-4A sib E561A XATRAL"),
    "A02506": ("cabergoline", "dopamine_agonist", "E22.1;D35.2;E23;O92;Z39.1;G20;N64.3", "", "", "endokrin", "brand"),
    "A08029": ("protirelin (TRH test)", "endocrine_diagnostic", "E00-E07;E22-E23", "", "", "endokrin", "brand"),
    "A13419": ("ibandronate 150 mg", "osteoporosis", "M80-M82;M85.8", "", "", "endokrin/FTR", "EK-4A sib E573A BONVIVA"),
    "A06353": ("metenolone", "anabolic_steroid", "D61;D63;D64;M80-M81;R64;E40-E46;C00-D09", "", "", "hematoloji", "brand"),
    "A18326": ("trientine", "wilson_chelator", "E83.0", "", "", "gastro/noroloji", "EK-4A sib E879A SIPRYNE"),
    "A09705": ("metronidazole/miconazole vaginal", "vaginal_antiinfective", "N76-N77;B37.3;A59;N89", "F", "", "kadin dogum", "EK-4A sib E041G"),
    "A17716": ("fenticonazole vaginal", "vaginal_antiinfective", "N76-N77;B37.3;A59;N89", "F", "", "kadin dogum", "EK-4A sib E816B GYNO-LOMEXIN"),
    "A20131": ("dydrogesterone", "progestogen", "N80-N98;O00-O99;Z30-Z39", "F", "", "kadin dogum", "EK-4A sib E984A DUPHASTON"),
    # ---- eye / skin / dental
    "A00491": ("proparacaine eye drops", "ophthalmic", EYE, "", "", "goz", "brand"),
    "A05221": ("phenylephrine eye drops", "ophthalmic", EYE, "", "", "goz", "EK-4A sib E905A"),
    "A06155": ("pilocarpine eye drops", "ophthalmic", EYE, "", "", "goz", "brand"),
    "A13212": ("loteprednol/tobramycin eye", "ophthalmic", EYE, "", "", "goz", "EK-4A sib E233D"),
    "A02020": ("eye ointment", "ophthalmic", EYE, "", "", "goz", "name"),
    "A17367": ("eye drops", "ophthalmic", EYE, "", "", "goz", "name"),
    "A09972": ("calcipotriol/betamethasone", "psoriasis_topical", "L40", "", "", "dermatoloji", "EK-4A sib E796A"),
    "A17657": ("tazarotene cream", "psoriasis_acne_topical", "L40;L70", "", "", "dermatoloji", "EK-4A sib E843A"),
    "A19276": ("tazarotene gel", "psoriasis_acne_topical", "L40;L70", "", "", "dermatoloji", "EK-4A sib E843B"),
    "A20054": ("clobetasol scalp lotion", "potent_topical_steroid", "L20-L30;L40;L43;L90;L21;L63", "", "", "dermatoloji", "EK-4A sib E108B DERMOVATE"),
    "A09973": ("clobetasol ointment", "potent_topical_steroid", "L20-L30;L40;L43;L90;L21;L63", "", "", "dermatoloji", "brand"),
    "A08146": ("articaine/epinephrine dental", "dental_anesthetic", "K00-K14;S02.5;S03.2", "", "", "dis", "brand"),
}

# pediatric-only products (explicit by name / product type) - judgment on 'pediatric-only'
PEDIATRIC_EXPLICIT = {
    "A14672": "BRUS 100 MG/5 ML PED SUSP (ibuprofen pediatric)",
    "A04399": "KONAKION MM PED 2 MG (vitamin K1 neonatal/infant)",
    "A13184": "PEDIASURE (pediatric formula, ages ~1-10)",
    "A13609": "PEDIASURE PLUS FIBER (pediatric formula)",
    "A19434": "PEDIASURE FIBER (pediatric formula)",
    "A14900": "KLAVUNAT ES 600/42.9 (amox/clav ES pediatric suspension)",
}
PEDIATRIC_LIKELY = {
    "A01079": "AZITRO 200 MG/5 ML SUSP",
    "A17966": "CEFDIFIX 250 MG/5 ML SUSP",
    "A17577": "BRUPREX 200 MG/5 ML SUSP",
    "A18272": "OSELMIR 12 MG/ML SUSP",
    "A08051": "TRILEPTAL 60 MG/ML SUSP",
}
# products that need a context on the same claim (judgment): contrast -> imaging procedure; anaesthetics -> OR/ICU
CONTRAST = {"A05864": "PAMIRAY-370 (iopamidol)", "A08533": "XENETIX 350 (iobitridol)",
            "A18936": "BUTORAST (gadobutrol, EK-4A sib GADOVIST)", "A19812": "CTRAY (gadoterate, EK-4A sib DOTAREM)"}
ANESTHESIA_ICU = {"A19480": "REMANEST 2 MG (remifentanil, EK-4A sib ULTIVA)",
                  "A15716": "HIPNODEX (dexmedetomidine, EK-4A sib PRECEDEX)",
                  "A18801": "LEOKS (levosimendan, EK-4A sib SIMDAX)",
                  "A18922": "esmolol IV infusion",
                  "A17243": "POLINUTHREE (3-chamber parenteral nutrition)",
                  "A18626": "PF HIPERALAMINE %10 aminoacid (parenteral nutrition)"}
