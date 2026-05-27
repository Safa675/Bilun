# MEDULA Reimbursement Capabilities Reference

> Source: SGK MEDULA Hastane Web Servisleri Kullanım Kılavuzu v3.1.1 (16.02.2026), 383 pages.
> Scope: Reimbursement-relevant capabilities only. Authentication, WSDL URLs, and pure IT infrastructure omitted.
> 
> **Caveat:** The MEDULA manual is a web service DTO reference, not a SUT rulebook. SUT annex labels (EK-3B, EK-1A, EK-2G, etc.) do not appear in the manual text. MEDULA enforces SUT through EK-2/B and EK-2/C code lists, procedure presence rules, and ICU-group logic — not named annex enforcement. Where this document references SUT annexes, those are domain-level inferences added for readability, not direct manual citations.

---

## Architecture Overview

MEDULA is SGK's claims submission gateway. Hospitals interact with it through SOAP web services in a strict sequential workflow:

```
Patient Admission → Service Registration → Invoice Registration → Payment
    (Hasta Kabul)     (Hizmet Kayıt)        (Fatura Kayıt)
```

At each stage, MEDULA validates data, enforces SUT rules, and either accepts or rejects the transaction with error codes. When the invoice is submitted, MEDULA computes the final payable amount under SUT pricing and returns it.

Additionally, MEDULA provides auxiliary web services for lookups, report management, dental commitments, orthodontic tracking, and e-signed reports.

---

## 1. Patient Admission (Hasta Kabul)

Before any service can be recorded, a patient must be admitted, creating a `takipNo` (tracking number) that links all subsequent services.

### 1.1 Entitlement Check (Müstehaklık)

**What it does:** Verifies that the patient is entitled to healthcare benefits and that the facility has a valid contract with SGK.

**How it works:**
- At admission, MEDULA queries SGK's central registry using the patient's TC Kimlik number (or foreign ID).
- Returns the patient's benefit status, institution code (`devredilenKurum`), provision type (`provizyonTipi`), and `tedaviTipi` (treatment type).
- If entitled: a `hastaBasvuruNo` and `takipNo` are generated.
- If not entitled: admission is rejected.

**Reimbursement impact:** This is the gate. No takipNo = no services = no payment.

### 1.2 Facility Contract Validation

**What it does:** Checks that the health facility has a valid SGK contract and is authorized to provide the requested service type.

**Reimbursement impact:** Even if the patient is entitled, an un-contracted or suspended facility cannot submit claims.

### 1.3 Provision Type Assignment

**What it does:** Assigns a `provizyonTipi` that governs how the claim will be priced and audited. The manual explicitly mentions several types (N, I, A, T, V, M); the full list below combines explicit mentions with standard SUT provision type codes inferred from domain knowledge.

| Code | Type | Reimbursement Implication | Manual Confirmed? |
|------|------|--------------------------|--------------------|
| N | Normal | Standard SUT pricing | Yes |
| I | İş Kazası (Work Accident) | Different payer, no copay | Yes |
| A | Acil (Emergency) | No visit copay, special quota rules | Yes |
| T | Trafik Kazası (Traffic Accident) | Reduced payment %, special fund | Yes |
| V | Adli Vaka (Forensic) | Special audit, different payer | Yes |
| M | Meslek Hastalığı (Occupational Disease) | No copay, special fund | Yes |
| K | Kurum Sevki (Institution Referral) | 100% sampled for audit | Implied |
| C | Acil Hal (Emergency State) | Special rules | Implied |
| H | Bulaşıcı Hastalık (Infectious Disease) | Special pricing | Implied |
| R | Koruyucu Sağlık (Preventive Care) | Different coverage rules | Implied |
| L | Analık (Maternity) | Special pricing, no copay | Implied |
| G | Afet/Savaş/Grev/Lokavt | Emergency coverage | Implied |
| U | Bakıma Muhtaç (Dependent Care) | Special rules | Implied |
| D | Doğal Afet (Natural Disaster) | Emergency coverage | Implied |
| E | 3713/21 (Veterans/Terror victims) | 100% inspected, no copay | Implied |

### 1.4 Treatment Type (Tedavi Tipi)

**What it does:** Classifies the treatment as:

| Type | Meaning | Reimbursement |
|------|---------|--------------|
| Ayaktan | Outpatient | EK-2A visit pricing, copay applies |
| Yatan | Inpatient | EK-2B yatak pricing, DRG package rules |
| Günübirlik | Day surgery | Hybrid pricing |
| İş Göremezlik | Incapacity | No copay |

### 1.5 Sevk Chain (Referral Rules)

**What it does:** Enforces the Turkish healthcare referral chain:

- **Same-branch 10-day rule:** If facility A gives an outpatient takip to a patient, no other facility can give the same patient the same branch outpatient takip for 10 days — unless facility A issues a sevk (referral).
- **Sevk Bildirim:** Facility A declares the referral via `SevkBildir`. Facility B picks it up as a linked (`bağlı`) takip.
- **Köy Korucuları exemption:** Village guards under 60-C9 scope are exempt from the sevk chain.
- **Post-discharge rule:** Within 10 days of discharge from the same facility and same branch, no new outpatient takip can be opened. Examinations and routine tests in this window are included in the diagnosis-based payment.

**Reimbursement impact:** Violating the sevk chain means the claim is never created. This is a hard block, not a payment deduction.

### 1.6 Biometric Verification (EKDS)

**What it does:** Requires biometric identity verification (finger vein pattern or e-identity card) for:
- Outpatient (ayaktan) visits
- Acil (emergency) visits for green/yellow triage
- Certain specialized procedures

**Exceptions:**
- Yatan (inpatient) stays
- Sevk discharge
- Vefat (death) cases
- Red triage (kırmızı alan) with continuing hospitalization or same-day transfer
- Patients with `kapsamKodu=99` (health-based exemption)
- Under-18 patients (warning only, not rejection)

**Reimbursement impact:** If biometric verification is missing when required, `FaturaKayıt` is blocked. No invoice = no payment.

### 1.7 Patient Admission Methods

| Method | Purpose |
|--------|---------|
| `HastaKabul` | Primary admission — creates takip |
| `HastaKabulKimlikDogrulama` | Admission with identity verification (deprecated) |
| `HastaKabulOku` | Read admission details |
| `HastaKabulIptal` | Cancel admission (blocks if already invoiced) |
| `HastaCikisKayit` | Register patient discharge |
| `HastaCikisIptal` | Cancel discharge registration |
| `HastaYatisOku` | Read inpatient stay details |
| `BasvuruTakipOku` | Read application tracking info |
| `SevkBildir` | Declare patient referral to another facility |
| `UpdateTedaviTipi` | Change treatment type (only before any service sent) |
| `UpdateProvizyonTipi` | Change provision type (only before any service sent) |
| `getYesilKartliSevkliHasta` | Query green-card referred patients |
| `UpdateTedaviTuru` | Change treatment category |
| `UpdateTakipTipi` | Change tracking type |
| `getMustehaklikKapsamKodu` | Get entitlement scope code |
| `KemikIligiKabul/Iptal/Oku` | Bone marrow transplant-specific admission |
| `EKDS Kisi Dogrulama Sorgu` | E-identity person verification query |
| `EKDS Belge Gereken Takip Sorgu` | Query takips requiring physical verification documents |

### 1.8 Patient Information Returned at Admission

MEDULA returns a patient information block (`HastaBilgileriDVO`) containing:

| Field | Meaning | Reimbursement Relevance |
|-------|---------|------------------------|
| `katilimPayindanMuaf` | E=exempt from copay, H=not exempt | Determines if copay is deducted |
| `ilaveUcrettenMuaf` | E=exempt from surcharge, H=not exempt | Determines surcharge application |
| `devredilenKurum` | Legacy institution code (SSK, Bağkur, etc.) | Pricing rules differ by institution |
| `provizyonTipi` | Provision type | Determines audit rate, copay rules |
| `tedaviTipi` | Treatment type | Determines pricing model |
| `sigortaliTuru` | Insurance type (1=Employee, 2=Retired, 3=Other) | Copay rates differ |

---

## 2. Service Registration (Hizmet Kayıt)

This is the core of MEDULA — where every billable item is submitted and validated. This section spans from page 183 through page 268, making it the largest single section of the manual.

### 2.1 Service Types

MEDULA accepts 11 distinct service types, each with its own DTO (Data Transfer Object) and validation rules:

| Service Type | DTO Name | What It Covers |
|---|---|---|
| Muayene (Exam) | `MuayeneBilgisiDVO` | Outpatient/inpatient examinations |
| Ameliyat/Girişim (Surgery/Procedure) | `AmeliyatveGirisimBilgisiDVO` | Surgical and interventional procedures |
| Diğer İşlem (Other Procedure) | `DigerIslemBilgisiDVO` | Dialysis, FTR, HBO, ESWT, tüp bebek, etc. |
| Diş (Dental) | `DisBilgisiDVO` | Dental procedures with tooth mapping |
| Tahlil (Lab Test) | `TahlilBilgisiDVO` | Laboratory tests with result reporting |
| Tetkik/Radyoloji (Imaging) | `TetkikveRadyolojiBilgisiDVO` | Radiology and diagnostic imaging |
| İlaç (Drug) | `IlacBilgisiDVO` | Drugs including magistral and radiopharmaceutical |
| Malzeme (Material) | `MalzemeBilgisiDVO` | Medical materials, implants, consumables |
| Konsültasyon (Consultation) | `KonsultasyonBilgisiDVO` | Inter-specialty consultations |
| Yatış (Inpatient Stay) | `HastaYatisBilgisiDVO` | Bed/day charges for inpatient stays |
| Kan (Blood Products) | `KanBilgisiDVO` | Blood components and products |

### 2.2 Core Validation Rules (Applied to All Services)

Every service record must pass these checks:

| Rule | What It Validates | Outcome if Violated |
|------|-------------------|---------------------|
| SUT code existence | Procedure/drug/material code exists in SUT gazette | Reject |
| Facility code validity | `saglikTesisKodu` references a valid contracted facility | Reject |
| Takip validity | `takipNo` belongs to the facility and is active | Reject |
| Date validity | Service date falls within the takip's valid date range | Reject |
| Provider ref number uniqueness | `hizmetSunucuRefNo` is unique (used for idempotency) | Reject (duplicate) |
| Doctor registration | `drTescilNo` references a valid registered doctor | Reject |
| Branch code | `bransKodu` references a valid medical specialty | Reject |
| Diagnosis presence | At least one ICD-10 code exists for the takip | Reject |
| 105-day retroactive limit | Reports can be recorded max 105 days retroactively. Certain takip retro rules also reference 105 days (post-20.04.2015). Not a blanket rule for all services. | Reject (where applicable) |
| Concurrent call limit | Max 20 service items per `hizmetKayit` call | Reject |

### 2.3 Procedure Validation (Ameliyat, Diğer İşlem, Muayene)

| Rule | Detail |
|------|--------|
| SUT code must be valid | Code must exist in EK-2B or relevant SUT annex |
| Adet (quantity) limit | After 13.06.2016: max 1 per service line for procedures. Multiple occurrences → separate service records |
| Euroscore requirement | For KVC surgeries in EK-9 list: Euroscore (0/1/2/3) mandatory |
| Sağ/Sol default | If null, defaults to "3" (no left-right distinction) |
| Report dependency | Dialysis, FTR, HBO, ESWT, tüp bebek — require valid report (`raporTakipNo`) |
| Ordering doctor | `istemYapanDrTescilNo` and `istemYapanDrBrans` required for tests ordered by another doctor |
| EK-8/EK-9 count limits | Some procedures have daily/patient/treatment maximum counts listed in EK-8 (Ameliyat) and EK-9 (Özel İşlemler) |
| Eye surgery quota | Per doctor daily max: 8; per SHS daily max: 16; cannot exceed 13% of outpatient visits per billing period |
| EK-2/B list 617340-617342 | Each deducts 7 from SHS monthly exam quota |
| EK-2/B list 602200, 616510-616810 | Each deducts 14 from SHS monthly exam quota |
| Outpatient exam quota | Max 48 patients/day/doctor, max 8 hours/day across all facilities |
| Göz quota | 4.5 exams/hour baseline, max 1050/month full-time |
| Acil quota | Max 90 exams/day/doctor (can reach 120 with 112 ambulance documentation) |
| Yeşil alan muayenesi (520021) | Blocked for İstisnai Hal provizyon type |
| Same-day EK-8 exam + package | EK-8 exam blocked when package procedure exists same day |
| İstisnai Hal restrictions | GSS debtors (60+ days) could access care at public/university hospitals only, 23.06.2018-31.12.2018 |

### 2.4 Drug Validation (İlaç)

| Rule | Detail |
|------|--------|
| Barcode validation | Drug barcode must be registered in İTS (İlaç Takip Sistemi) |
| GSS drug definition | Drug must be defined in SGK's GSS drug database |
| Adet limit | Max = box unit quantity per line; if daily usage exceeds box unit → send as multiple lines |
| Tablet/capsule serial limit | Max 4 karekod serial numbers per line for tablet/capsule forms |
| Karekod serial mandatory | Certain drugs in EK-4/A require karekod serial numbers (since 15.04.2022) |
| Duplicate karekod prevention | Same karekod cannot appear more times than box unit quantity |
| Drug type classification | 1=Barcoded (karekodlu), 2=Magistral (compounded), 3=Radiopharmaceutical |
| Maximum dose control | Applied to all drugs since 01.05.2021 for all treatment types. MEDULA returns max usage period, max dose 1, max dose 2 |
| Special status 'i' restriction | "İlaç kullanımı tıbbi gerekliliktir" blocked for green/red prescription oral drugs |
| Special status 'l' (EK-4/E 6.1) | Valid only for specific drugs under EK-4/E item 6.1 with ICU-related conditions |
| Avibactam sodium limit | Max 14 days total, not reimbursed beyond |
| Contrast agent linking | For contrast agents under SUT 4.2.32: must send associated procedure SUT code and provider ref number |
| EK-4/H drug restriction | Tıp Merkezi and Dal Merkezi cannot bill EK-4/H drugs since 01.05.2016 (only C-type medical centers with pharmacy license) |
| I.V. Fluorescein karekod | For FFA procedure, karekod mandatory for I.V. Fluorescein drugs |
| Drug report matching | If drug is "raporla ödenir" (paid via report), `raporTakipNo` must be sent and active ingredient must match report's ingredients |
| Magistral drug fields | Requires preparation type (1-8), packaging type, size, quantity, raw material codes, amounts, and units |

### 2.5 Material Validation (Malzeme)

| Rule | Detail |
|------|--------|
| UBB barcode mandatory | Since 01.02.2008, all materials must have Ürün Barkod Bilişim (UBB) barcode |
| Material type classification | 1=SUT-coded, 2=ES Protocol (health ministry protocol), 3=Codeless (kodsuz) |
| Code requirement | SUT-coded (type 1) and ES Protocol (type 2): `malzemeKodu` required |
| Codeless requirements | Type 3: `kodsuzMalzemeAdi` (name) and `kodsuzMalzemeFiyati` (price) required |
| Allograft barcode restriction | Barcode 8888888888888 blocked for purchase date >= 01.02.2014 |
| ÜTS finalization | Material usage must be confirmed via ÜTS (Ürün Takip Sistemi) with `kullanimBildirimID` before invoicing |
| ÜTS locked material | If usage notification is SGK-locked in ÜTS, the hizmet cannot be cancelled |
| Tekil takip (unique tracking) | For materials purchased after 02.07.2018 with unique tracking: serial/lot data required |
| Donor ID | Mandatory for allograft submissions |
| Tender fields (public hospitals) | `ihaleKesinlesmeTarihi` and `ikNoAlimNo` mandatory for codeless materials since 01.10.2014 |
| BayiNo (distributor) | 13-char dealer identifier mandatory since 02.07.2018 |
| FirmaTanimlayiciNo (firm ID) | Mandatory since 01.09.2012 |
| Max 4 firm IDs per line | Max 4 İTS firm identifiers per hizmet line |
| KDVsiz fiyat (VAT-exclusive price) | Required |
| Katkı payı flag | E/H — copay applicability |
| Purchase date | Material purchase date required |
| Special status 'p' | Required for materials with detailed epicrisis report requirement |
| Price calculation rules | Depends on facility type: Private=KDV only; University=15% operating+1% treasury; Public=15%+1%+1% SHÇEK. SUT-coded with 0 TL price + uncoded: same splits. SUT-coded with price: Public/Univ=12% operating. Foundation hospitals: no additions |
| Material blocked without procedure | If no işlem exists in the takip, medical material invoicing is blocked |
| ICU material restrictions | D/E group ICU → 0 TL + material billing blocked. A/B/C group ICU absent → material billing blocked |
| SUT-coded only rule | After October 2014, only SUT-coded materials accepted; kodsuz malzeme gönderimi terminated |

### 2.6 Lab Validation (Tahlil)

| Rule | Detail |
|------|--------|
| Test results mandatory | `TahlilSonucDVO` required for: all inpatient treatments, and outpatient with EK-10C or molecular genetic procedures |
| Results format | +, -, or numeric value |
| Result unit required | `birim` field required |
| Genetic info | `GenBilgisiDVO` with gene code required for molecular genetic procedures |
| Minimum gene count | Per SUT code minimum gene code count enforced |
| Ordering doctor | `istemYapanDrTescilNo` and branch required |
| Blood gas tests | Only submittable via `KanBilgisiDVO`, not as regular tahlil (since 2021) |

### 2.7 Dental Validation (Diş)

| Rule | Detail |
|------|--------|
| Tooth quadrant mapping | 8 quadrants × 8 positions (adult) or 5 positions (child). Fill 'E' for treated teeth |
| Anomaly tooth fields | 4 anomaly flag fields per quadrant |
| SUT code | Must be in dental SUT list (BUT/SUIT codes) |
| Prosthesis taahhüt | Dental prosthesis codes (404010-404420) still have taahhüt DTOs in the API, but the **mandatory requirement was removed** after 01.03.2016 |
| 10-day repeat rule | 401010 (diş muayenesi) cannot appear more than once per 10 days, same patient, same facility |
| Detertraj + subgingival küretaj | Same-day billing blocked |

### 2.8 Inpatient Stay Validation (Yatış)

| Rule | Detail |
|------|--------|
| Bed code mandatory | Since 01.03.2016, yatış procedures require `yatakKodu` from the facility bed registry |
| Gündüz yatak exemption | Day beds do not require bed code |
| Full stay coverage | All days in admission range must have yatış procedures; otherwise invoicing blocked |
| ICU bed levels | 1st/2nd/3rd step ICU beds affect reimbursement rates |
| Bed type classification | E=Adult, Y=Newborn, P=Palliative |
| Bed registration status | 0=Level uncertain, 1=Registered, 2=Temporary → affects pricing |
| Post-discharge package window | Package procedures allowed back into closed yatış only within 15 days, and only if no ayaktan takip taken |
| Extended stay (Uzayan Yatış) | Requires taburcu kodu "13 - Uzayan Yatış" for faturalanmış uzayan yatış takips |
| ICU middle days | Drug and material payments blocked between ICU first and last day (except SUT 2.4.4.H exceptions) |
| Bed occupancy quota | Private hospitals: at dönem sonlandırma, bed count × 1.1 quota check (excluding ACİL) |

### 2.9 Diagnosis Validation (Tanı)

| Rule | Detail |
|------|--------|
| ICD-10 code | Must be valid 10-character ICD-10 code |
| Diagnosis type | 1=Ön Tanı (preliminary), 2=Kesin (definitive), 3=Ayırıcı (differential) |
| Primary flag | `birincilTani` (E/H) required |
| Minimum count | At least 1 diagnosis per takip |
| Duplicate prevention | Same ICD-10 code + same diagnosis type cannot repeat within same takip |
| A0 prefix | Queries with "A0" return A0-prefixed diagnosis codes |
| Multiple pregnancy | "AYNI BAŞVURU ALTINDA" rule for çoğul gebelik diagnosis check |

### 2.10 Özel Durum (Special Status Flags)

Special status flags modify how services are priced or validated:

| Flag | Meaning | Reimbursement Effect |
|------|---------|---------------------|
| 6 | Muayene katılım payı muafiyeti var | Exempt from visit copay |
| 8 | Muayene katılım payı muafiyeti yok | Not exempt from visit copay (6 and 8 mutually exclusive) |
| D,E,J,K,L,M,N,O | Various exemption + institution combinations | Copay rules vary |
| a | AMATEM/ÇEMATEM center | +30% payment for psychiatric procedures |
| d | Çoğul gebelik var | Multiple pregnancy pricing |
| f | Hizmet alımı (outsourced) | Outsourced procedure pricing |
| i | İlaç kullanımı tıbbi gerekliliktir | Drug necessity flag (blocked for green/red prescription oral drugs) |
| l | EK-4/E item 6.1 specific | ICU-related drug condition |
| m | Mesai saatleri dışı poliklinik | 2× EK-2/A rates for SB 2nd/3rd level hospitals |
| n | %40+ engelli/diş tedavisi | 2× EK-2/Ç rates for dental under general anesthesia |
| o | FTR transferred from another doctor | Incomplete FTR session flag |
| p | Malzeme detaylı epikriz raporu | Material detailed epicrisis report required |
| r | Yenidoğan yoğun bakım süre uzatılması | Extended newborn ICU stay |
| x | 112 Acil Komuta Merkezi | Allows exceeding 120 daily exam limit with documentation |
| \| | 60 dakika altı FTR seansı | FTR session under 60 minutes |

---

## 3. Invoice Registration (Fatura Kayıt)

After all services are registered, the invoice is submitted for final payment calculation.

### 3.1 Invoice Submission

**What it does:** Submits the final invoice for a takip (or group of takips). MEDULA:
1. Validates all services in the takip
2. Computes payment under SUT pricing rules
3. Applies all deductions (copays, surcharges, discounts)
4. Returns the final payable amount
5. Assigns a `faturaTeslimNo` for tracking

### 3.2 Payment Calculation Rules

**SUT-based pricing:**
- Each service is priced according to the SUT gazette (EK-2B for procedures, EK-2A for visits, EK-2C for packages, EK-4A for drugs, EK-3 catalogs for materials)
- MEDULA has the canonical price list and applies it authoritatively
- Hospitals do not set prices — they submit services, MEDULA computes payment

**Deductions applied at payment:**

| Deduction | What It Is | Rate |
|-----------|-----------|------|
| Muayene katılım payı | Visit copay | Varies by patient category |
| Malzeme katılım payı | Material copay | Varies by material and patient |
| Tüp bebek katılım payı | IVF copay | Varies |
| İlaç katılım payı | Drug copay | 10-20% depending on patient category |
| İlave ücret | Surcharge | Hospital-specific, capped by SUT |

**Copay exemptions:**
- Acil (emergency) provision type → no visit copay
- İş Göremezlik treatment type → no copay
- İş Kazası, Meslek Hastalığı, Analık → no copay
- 3713/21 (veterans/terror victims) → no copay
- Kurum sevkli → varies
- Patients with `katilimPayindanMuaf=E` → no copay
- Özel durum flag 6 → no visit copay

### 3.3 Special Pricing Rules

| Rule | Detail |
|------|--------|
| Traffic accident percentage | `trafikKazasiOdemeYuzdesi` reduces payment by a percentage |
| MR same-day same-hospital | Multiple MRIs → highest priced = full, others = 50% |
| CT same-day same-hospital | Multiple CTs → highest priced = full, others = 50% |
| Non-contracted SHS payment | `muvafakatVar` — E=payment to SHS, H=patient self-pay |
| Green-card referral pricing | Special pricing for yeşil kartlı sevkli patients |
| Foundation hospital pricing | No operating/cost additions |

### 3.4 Audit and Sampling

| Rule | Detail |
|------|--------|
| Kurum sevkli | 100% sampled (all claims audited) |
| 3713/21 (E type) | 100% inspected |
| Yeşil kartlı | 5% sampled |
| Sevkli yeşil kartlı | 5% sampled |
| E-signature requirement | Sampling operations require e-signature since 01.12.2020 |

### 3.5 Invoice Blocking Rules

| Condition | Effect |
|-----------|--------|
| Biometric verification missing (when required) | Invoice blocked |
| Inpatient stay not closed | Invoice blocked for linked services |
| ICU bed occupancy > 1.1× bed count (private hospitals) | Dönem sonlandırma blocked |
| Eye surgery ratio > 13% of outpatient visits | Dönem sonlandırma blocked |
| 105-day retroactive limit exceeded | Invoice blocked |
| ÜTS finalization missing | Invoice blocked |
| No procedure in takip but material present | Invoice blocked |
| Malüliyet report not registered (for kurum sevkli/kontrol, since 15.10.2020) | Invoice blocked |

### 3.6 Invoice Methods

| Method | Purpose |
|--------|---------|
| `FaturaKayit` | Submit invoice for payment calculation |
| `FaturaIptal` | Cancel submitted invoice |
| `FaturaOku` | Read invoice details (by `faturaTeslimNo` or `faturaRefNo`+date) |
| `FaturaTutarOku` | Read invoice amount only |
| `utsKullanimKesinlestirme` | Finalize material usage in ÜTS |
| `utsKullanimKesinlestirmeSorgu` | Query ÜTS finalization status |
| `utsKullanimKesinlestirmeIptal` | Cancel ÜTS finalization |
| `itsIlacIslem` | ITS drug processing (only `islemTipi=K` supported) |
| `majistralIlacTutariHesapla` | Calculate magistral drug price |

---

## 4. Report Management (Rapor Bilgisi Kayıt)

MEDULA manages medical reports that authorize specific treatments, drugs, or procedures.

### 4.1 Report Types

| Code | Type | Purpose |
|------|------|---------|
| 1 | Tedavi (Treatment) | Authorizes dialysis, HBO, ESWT, IVF, FTR, ESWL, home hemodialysis |
| 2 | İş Kazası (Work Accident) | Documents work accident for special reimbursement |
| 3 | Meslek Hastalığı (Occupational Disease) | Occupational disease for special reimbursement |
| 4 | Hastalık (Illness) | General illness for incapacity benefits |
| 5 | Doğum Öncesi Çalışabilir | Prenatal work capacity |
| 6 | Analık (Maternity) | Maternity leave and benefits |
| 7 | Doğum (Birth) | Birth documentation |
| 8 | Protez (Prosthesis) | Authorizes prosthetic devices |
| 9 | Maluliyet (Disability) | Permanent disability assessment |
| 10 | İlaç Kullanım (Drug Use) | Authorizes specific drugs (with active ingredient list) |
| 11 | İlaç Muafiyet (Drug Exemption) | Drug copay exemption |

### 4.2 Report Management Methods

| Method | Purpose |
|--------|---------|
| `RaporBilgisiKaydet` | Register a new report |
| `TakipNoileRaporBilgisiKaydet` | Register report linked to takip |
| `RaporBilgisiBul` | Find report by various criteria |
| `RaporBilgisiBulRaporTakipNodan` | Find report by rapor takip no |
| `RaporBilgisiBulTCKimlikNodan` | Find reports by patient TC |
| `RaporBilgisiSil` | Delete report |
| `IlacRaporDuzelt` | Correct drug report |

### 4.3 Key Report Validation Rules

| Rule | Detail |
|------|--------|
| Report exclusivity | Only one of ilaç/tedavi/maluliyet/işgöremezlik report types per record |
| Single physician vs. board | `duzenlemeTuru`: 1=Heyet (board), 2=Tek Hekim (single physician) |
| İşgöremezlik sub-types | Each subtype (iş kazası, meslek hastalığı, hastalık, analık, emzirme) has mandatory sub-objects |
| Hospitalization dependencies | İş kazası/meslek hastalığı report fields depend on `yatisDevam` status |
| Maternity-specific fields | `bebekDogumTarihi`, `dogumOncBasTarihi`, live birth count, delivery method, `analikRaporTipi`, `gebelikTipi` |
| Drug report active ingredients | `raporEtkinMaddeler` must list active ingredient codes |
| Drug report takip formu | Diabetes-like diagnosis codes → takip formu number within last 90 days (may be lifted in some versions) |
| Start/end dates | Required for all types except Protez (8) and Doğum Öncesi Çalışabilir (5) |
| Doktorlar array | Always required; at least one doctor must be listed |
| Diagnosis vs drug diagnosis | `tanilar`/`teshisler` for non-drug reports; `ilacTeshisler` for drug reports |
| Adli vaka/trafik kazası flag | `aVakaTKaza`: 1=Adli Vaka, 2=Trafik Kazası, 3=Yok — required for Hastalık, Meslek Hastalığı, İş Kazası |
| Hak sahibi ID | At least one of: TC Kimlik No, Karne No, or Sosyal Güvenlik No |
| Devredilen kurum | 1-32+ codes covering all Turkish social security institutions |
| Yakinlik kodu | Required for Bağkur patients |
| Sigortali türü | 1=Çalışan, 2=Emekli, 3=Diğer |
| Provizyon type | N through E codes must match valid provision types |
| Provizyon date | Must be the examination opening date, not the report date |

### 4.4 Treatment Report Subtypes

| Subtype | Code | Required Fields |
|---------|------|----------------|
| Diyaliz (Dialysis) | 1 | `refakatVarMi`, `seansGun`, `seansSayi`, `butKodu` |
| Hiperbarik Oksijen (HBO) | 2 | Session and code info |
| ESWT | 3 | `eswtVucutBolgesiKodu` (12-23 for left/right body regions), `seansGun`, `seansSayi`, `butKodu` |
| Tüp Bebek (IVF) | 4 | `tupBebekRaporTuru` (1=disease, 2=other), `butKodu` |
| FTR (Physical Therapy) | 5 | `ftrVucutBolgesiKodu` (1-23, 11=Tüm Vücut), `seansGun`, `seansSayi`, `butKodu`, `tedaviTuru`, `robotikRehabilitasyon` |
| ESWL | 6 | `butKodu`, `tasSayisi`, `seansSayisi`, `bobrekBilgisi` (1=Sağ, 2=Sol), `tasBilgileri[]` (size + localization) |
| FTR-Trafik Kazası | 7 | Same as FTR |
| Ev Hemodiyalizi | 8 | `butKodu`, `seansSayi`, `tedaviSuresi` |

### 4.5 Report Limits and Quotas

| Rule | Detail |
|------|--------|
| ESWT/FTR report duration | 1 year |
| ESWT/FTR same body region | Max 1 report per year per body region |
| ESWT/FTR total body regions | Max 2 reports total per year across different regions |
| ESWT/FTR active reports count | Each active report = 1 işlem for quota checks |
| ESWL report check | Added in v3.1.0 — ESWL procedures require valid report |
| Retroactive limit | Reports can only be recorded max 105 days retrospectively |

### 4.6 E-Signed Report Management

| Method | Purpose |
|--------|---------|
| `raporKaydet` | Submit e-signed report |
| `raporOnay` | Doctor signs the report |
| `kurulBaskanıRaporOnay` | Board president approves |
| `bashekimRaporOnay` | Başhekim approves |
| `raporSorgu` | Query e-signed report |
| `tcIleraporSorgu` | Query reports by TC |
| `kurulBaskaniOnayBekleyenRaporSorgu` | Query reports awaiting board president |
| `bashekimOnayBekleyenRaporSorgu` | Query reports awaiting başhekim |
| `onayBekleyenRaporSorgu` | Query pending approval reports |
| `raporSil` | Delete e-signed report |
| `onay` | Generic approval |
| `onayBekleyen` | Generic pending approval query |

**E-signed report validation:**
- Report content sent as signed XML byte array
- Workflow enforced: Doctor → Board President → Başhekim
- Board president `drTescilNo` required
- Board members must be defined in `Uyeler[]` array
- Specialty opinions in `bransGorusler[]`
- Tıbbi Gereklilik report: at least 3 doctors must issue
- Maluliyet: `maluliyetRaporTuru`, `sevkNedeni`, `basvuruSekli`
- Engellilik: all 8 disability type flags (E/H) required, `engelOrani` 0-100, `bagimlilikDegerlendirilmesi`

---

## 5. Auxiliary Web Services (Yardımcı Metotlar)

These are lookup and query services that support the main workflow.

### 5.1 Healthcare Provider Services

| Method | Returns |
|--------|---------|
| `SaglikTesisiAra` | Facility search: code, name, class, type, province, district |
| `DoktorAra` | Doctor search: name, surname, branch, diploma no, registration no |
| `tesisYatakSorgu` | Facility bed list: code, type (Adult/Newborn/Palliative), registration status, ICU level, validity dates |

### 5.2 Query Services

| Method | Returns |
|--------|---------|
| `TakipAra` | Patient takip query (max 1-month date range). Filter by sevk status |
| `takipBilgileriListesi` | Takip details grouped by evrak with total amounts |
| `kisiGecmisIslemSorgu` | Historical procedures for a person+procedure code — which facility, what dates |
| `KisiGenSorgula` | Person-gene procedure history for genetic procedure checks |
| `kurumSevkTalepNoSorgu` | Institutional referral details: sevk number, facility, whether provizyon taken, whether report recorded, cost liability (`ucret`: Kurum vs Sigortalı) |
| `eNabizBildirimSorgu` | e-Nabız notification status for services under a takip |

### 5.3 Drug Services

| Method | Returns |
|--------|---------|
| `IlacAra` | Drug search with full reimbursement profile: outpatient payment code (1=Paid, 2=Paid with report, 3=Not paid), inpatient payment code, max usage period/dose, equivalent group price/barcode, discount tier bands (public discount upper/lower ratios), active/passive status |

**Drug payment codes returned by `IlacAra`:**
- `ayaktanOdenme`: 1=Ödenir (paid), 2=Raporla Ödenir (paid with report), 3=Ödenmez (not paid)
- `yatanOdenme`: Same coding for inpatient
- In hospital context: anything ≠ 3 is paid
- `hasAktifPasif` / `eczAktifPasif`: Active/passive in hospital/pharmacy channel

**Drug max usage parameters returned:**
- `yatanMaksimumKullanimPeriyot` + `Birim` (inpatient max period + unit)
- `yatanMaksimumKullanimDoz1` + `Doz2` (inpatient max dose values)
- `ayaktanMaksimumKullanimPeriyot` + `Birim` (outpatient max period + unit)
- `ayaktanMaksimumKullanimDoz1` + `Doz2` (outpatient max dose values)

### 5.4 Payment and Audit Services

| Method | Returns |
|--------|---------|
| `kesintiYapilmisIslemler` | Per-service-line deductions: `kesintiTutari`, reviewer `aciklama`, procedure codes, amounts. Also: aggregate `muayeneKatilimTutari`, `malzemeKatilimTutari`, `tupBebekKatilimTutari` |
| `katilimPayiUcreti` | Per-takip copay breakdown: `muayeneKatilimTutari`, `malzemeKatilimTutari`, `tupBebekKatilimTutari` |
| `getOrneklenmisTakipler` | Sampled takips for a given evrak document (filtered by group type: A=Ameliyat, Y=Yatış, G=Girişimsel, D=Diğer) |

### 5.5 Catalog and Reference Services

| Method | Returns |
|--------|---------|
| `guncelSutKodlari` | Current SUT procedure codes: `sutKodu`, `adi`, `fiyat`, `turu` (1=Muayene through 10=Kan), `gecerlilikTarihi`. If date given: only codes changed after that date |
| `taniAra` | ICD-10 diagnosis codes by partial code search |
| `barkodSutEslesmeSorgu` | SUT code(s) matching a barcode/firm ID, or vice versa, with validity dates |
| `evrakTakipGrupKodlariSorgu` | Group codes and names for evrak grouping |

### 5.6 Other Services

| Method | Purpose |
|--------|---------|
| `getYesilKartliSevkliHasta` | Query green-card referred patients |
| `yurtDisiYardimHakkiGetir` | Health aid rights for foreign-insured individuals: `formulAdi`, `odemeTuru`, `tedaviKapsami` |
| `kisiVefatKayit` | Register patient death (TC, date/time, death certificate) |

---

## 6. Specialized Form and Commitment Management

### 6.1 Diabetes Follow-Up Form (Takip Formu)

**Purpose:** Required for certain diabetes drug prescriptions.

**What it captures:**
- Patient demographics and residence type
- Clinical values: APG, TPG, HbA1c, kreatinin, total kolesterol, LDL, HDL, trigliserid, mikroalbumin, TSH
- Medical history: antiGAD, EKG, eye exam, peripheral neuropathy, coronary artery disease, cerebrovascular disease, foot exam
- Acute complications in last 3 months (DKA, HHD, hypoglycemia)
- Insulin pump usage (with install/replacement dates)
- Medical nutrition therapy and exercise compliance
- Doctor's DM training status
- Comorbidity codes (14 options including hypertension through no comorbidity)
- Habits (smoking, alcohol, caffeine, other)
- BMI, waist circumference, blood pressure

**Reimbursement relevance:** Certain diabetes ICD-10 codes (47, 50-54, 145, 244, 246, 247) require a takip formu within the last 90 days to authorize drug reports. Without it, the drug report is rejected.

### 6.2 Dental Commitment (Diş Taahhüt)

**Purpose:** Previously required for dental prosthesis reimbursement. **The mandatory requirement was removed for procedures dated after 01.03.2016** (manual line 2794). The taahhüt API methods still exist (`disTaahhutKayit`, `okuDisTaahhut`, `silDisTaahhut`, `okuKisiDisTaahhut`) and the DTOs are still documented, but the system no longer rejects diş protez hizmet kaydı without a taahhüt record.

**What the taahhüt API still supports:**
- SUT codes 404010-404420 (prosthesis codes)
- Mouth schema: 32-position adult dentition (11-48) or 20-position primary dentition (51-94)
- District validation (`adressIlce`) against province (`adressIlPlaka`)
- System-generated PDF output (`taahhutCikti`)

### 6.3 Orthodontic Form (Ortodonti Formu)

**Purpose:** Tracks sequential orthodontic procedures.

**What it tracks:**
- Up to 3 sequential procedures per patient
- Each step: facility code, procedure date, provizyon number
- `formNo` is mutually consistent with `sutKodu` and `tcKimlikNo`
- Read-only tracking — the form itself doesn't authorize payment, it documents progression

### 6.4 Bone Marrow Transplant Tracking

**Purpose:** Specialized admission for bone marrow transplant procedures.

**Methods:** `KemikIligiKabul`, `KemikIligiIptal`, `KemikIligiOku`, `KemikIligiIslemDuzeltme`, `KemikIligiTCIleSorgu`

**Reimbursement rules:**
- Bone marrow transplant procedures (P704970-P704980) require `KemikIligiKabul` registered before invoicing
- Acceptance must be registered at least 15 days before the procedure
- No acceptance = cannot invoice

---

## 7. Cross-Cutting Constraints

### 7.1 Temporal Constraints

| Rule | Limit | Notes |
|------|-------|-------|
| Retroactive takip creation | 105 days | Post-20.04.2015 rule for certain takip types |
| Retroactive report recording | 105 days | Explicitly stated for reports |
| Retroactive service recording | Varies | Not a blanket 105-day rule; depends on takip context |
| Invoice retroactivity | 105 days | Post-20.04.2015 |
| Sevk chain (same branch, different facility) | 10-day block without referral |
| Post-discharge (same facility, same branch) | 10-day block |
| Dental exam repeat (401010) | 10-day block, same facility, same patient |

### 7.2 Quantity and Quota Constraints

| Rule | Limit |
|------|-------|
| Doctor daily max (general) | 48 patients/day, 8 hours/day |
| Doctor daily max (göz) | 4.5 exams/hour, max 1050/month |
| Doctor daily max (certain codes) | 8 procedures/day (codes 602200, 616510-616810) |
| SHS daily max (göz) | 16 procedures/day |
| Acil daily max | 90/doctor (120 with 112 documentation) |
| Eye surgery ratio | Max 13% of outpatient visits |
| ICU bed occupancy (private) | 1.1 × bed count |
| Service items per hizmet kayıt call | Max 20 |
| Drug adet per line | Max = box unit quantity |
| Procedure adet per line | Max 1 |
| İTS firm IDs per line | Max 4 |

### 7.3 Payment Adjustment Rules

| Rule | Detail |
|------|--------|
| MR same-day same-facility | Highest price: 100%, others: 50% |
| CT same-day same-facility | Highest price: 100%, others: 50% |
| AMATEM/ÇEMATEM psychiatric procedures | +30% payment |
| Mesai dışı poliklinik (SB 2nd/3rd level) | 2× EK-2/A rates |
| %40+ engelli diş tedavisi | 2× EK-2/Ç rates |
| Traffic accident | Reduced by `trafikKazasiOdemeYuzdesi` |
| D/E group ICU | 0 TL, no material billing |
| Material pricing by SUT code price | Public/Univ=12% ops; Private=KDV only |
| Material pricing for 0 TL + kodsu | Public=15%+1%+1%; Univ=15%+1%; Private=KDV only |

### 7.4 Pre-Conditions for Payment

| Condition | Requirement |
|-----------|-------------|
| Biometric verification (outpatient) | Required for invoicing |
| UTS finalization (materials) | Required for invoicing |
| Inpatient discharge | Required for invoicing |
| Sevk declaration (cross-facility) | Required for 10-day rule exception |
| Drug report | Required for "raporla ödenir" drugs |
| Takip formu (diabetes) | Required for certain drug reports |
| Taahhüt (dental prosthesis) | Previously required for prosthesis invoicing; removed after 01.03.2016 |
| Kemik iliği kabul (bone marrow) | Required for transplant invoicing |
| ESWT/FTR report | Required for procedure submission |
| ESWL report | Required since v3.1.0 |
| Maluliyet report | Required for kurum sevkli/kontrol invoicing |
| E-signature (sampling) | Required since 01.12.2020 |
| KTS HBYS registration | Required since 02.11.2018 |

---

## 8. Response and Error Handling

### 8.1 Hizmet Kayıt Response

MEDULA returns a `HizmetKayitCevapDVO` with:
- `sonucKodu`: `0000` = success, anything else = error
- `hataliKayitlar`: Array of `HataliIslemBilgisiDVO` with `hataKodu` + `hataMesaji`
- `islemSiraNo`: MEDULA-assigned sequential number for correlation

**Special response code:** `9000` = warning/informational (not an error). Used for under-18 provizyon warnings — the provision succeeds, just with a notification about GSS registration.

### 8.2 Fatura Kayıt Response

MEDULA returns:
- `faturaTeslimNo`: Receipt number for tracking
- `faturaTutari`: Final computed payable amount
- All deductions applied

### 8.3 Cancellation Rules

- Takip can be cancelled only if no fatura has been created
- Hizmet kaydı can be cancelled individually
- Fatura can be cancelled (returns to pre-invoice state)
- ÜTS-finalized materials cannot be cancelled if SGK-locked

---

## Summary: What MEDULA Does

MEDULA is a **real-time claims adjudication engine.** Its capabilities span:

1. **Gatekeeping:** Entitlement checks, contract validation, biometric verification
2. **Validation:** SUT code validity, field completeness, date ranges, quota enforcement
3. **Authorization:** Report management, commitment tracking, form requirements
4. **Pricing:** SUT-based payment calculation with all deductions and adjustments
5. **Audit:** Sampling, deduction tracking, inspection queries
6. **Reference:** Drug catalogs, SUT codes, facility/doctor registries, ICD-10 diagnostics

What MEDULA does NOT do:
- Recommend alternative billing strategies
- Find cheaper drug equivalents
- Detect unbundling opportunities
- Aggregate cohort-level savings
- Track historical price changes
- Proactively discover patient exemptions
- Compare package vs. itemized totals

These are the gaps BILUN fills.
