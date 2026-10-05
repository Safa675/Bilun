# SUT clause corpus diff (Track E clause_key)

**Old:** `sut_clauses_old.parquet`  |  **New:** `sut_clauses.parquet`

## Summary

- STABLE (old corpus rows; refs survive): **8,375**
- AMENDED (old + new corpus rows → triage): **42** (**13 old** + **29 new**)
- NEW (added): **0**
- REMOVED (refs may dangle): **0**

_Counts describe corpus rows, not a count of distinct legal amendments. Multiple rows can share a coordinate; source review must establish the legal changes._

_STABLE clauses keep the same `clause_key` (coord#hash) across re-extraction — references to them remain valid. Everything else below needs human triage._

---

## AMENDED — old corpus rows (re-triage references)

**13** corpus row(s):

| clause_key | clause_coordinate | section_id | is_in_force | text_snippet |
| --- | --- | --- | --- | --- |
| 2.4.2.A#f4117565 | 2.4.2.A | 2.4.2.A | true | (Değişik: RG- 25/08/2022- 31934/ 15 md. Yürürlük: 03/09/2022) |
| 2.4.2.A#f4117565 | 2.4.2.A | 2.4.2.A | true | (Değişik: RG- 25/08/2022- 31934/ 15 md. Yürürlük: 03/09/2022) |
| 2.4.2.A#f4117565 | 2.4.2.A | 2.4.2.A | true | (Değişik: RG- 25/08/2022- 31934/ 15 md. Yürürlük: 03/09/2022) |
| 2.4.2.A.(2)#943077b8 | 2.4.2.A.(2) | 2.4.2.A | true | (Mülga: RG- 18/02/2017- 29983/ 5 md. Yürürlük: 01/03/2017) |
| 2.4.2.A.(3)#70a4b515 | 2.4.2.A.(3) | 2.4.2.A | true | (3) Organ nakli tedavileri, bünyesinde “organ nakli merkezi” bulunan sağlık hizmeti sunucularında gerçekleştirilecektir. |
| 2.4.2.A.(4)#dd4afd03 | 2.4.2.A.(4) | 2.4.2.A | true | (4) Yurt içinde organın bulunması halinde hastanın organın bulunduğu yere veya organın organ nakli yapılacak merkezin b… |
| 2.4.2.A.(5)#5733887d | 2.4.2.A.(5) | 2.4.2.A | true | (5) Ulusal Organ ve Doku Nakli Koordinasyon Merkezince bildirilen her bir kadavra donör için donörü temin eden sağlık h… |
| 4.2.14.C#07760ab4 | 4.2.14.C | 4.2.14.C | true | (Ek: RG- 25/08/2016- 29812/ 15 md. Yürürlük: 30/08/2016) |
| 4.2.14.C#110ce46e | 4.2.14.C | 4.2.14.C | true | gg) pertuzumab; daha önce metastatik hastalığı için sistemik kemoterapi veya trastuzumab tedavisi almamış, ECOG perform… |
| 4.2.14.C#5c1812da | 4.2.14.C | 4.2.14.C | true | (Ek: RG- 07/10/2016- 29850/ 23-ç md. Yürürlük: 15/10/2016) |
| 4.2.14.C#f8a8c237 | 4.2.14.C | 4.2.14.C | true | ff) Trastuzumab emtansin; metastatik meme kanserinde daha önce trastuzumab ve bir taksan tedavisi almış ve hastalığı so… |
| 4.2.61#5c2e97a1 | 4.2.61 | 4.2.61 | true | 4.2.61- Thiotepa kullanım ilkeleri |
| 4.2.61.(1)#fbf73d45 | 4.2.61.(1) | 4.2.61 | true | (1) Sağlık Bakanlığından hasta bazında alınacak endikasyon dışı onaya dayanılarak, üçüncü basamak (Değişik:RG-25/08/202… |

---

## AMENDED — new corpus rows (review replacement text)

**29** corpus row(s):

| clause_key | clause_coordinate | section_id | is_in_force | text_snippet |
| --- | --- | --- | --- | --- |
| 2.4.2#3dea13f4 | 2.4.2 | 2.4.2 | true | (Değişik: RG-02/10/2026- 33388/ 1 md. Yürürlük: 02/11/2026) |
| 2.4.2.A#e3b0c442 | 2.4.2.A | 2.4.2.A | false |  |
| 2.4.2.A#e3b0c442 | 2.4.2.A | 2.4.2.A | false |  |
| 2.4.2.A#e3b0c442 | 2.4.2.A | 2.4.2.A | false |  |
| 2.4.2.A#e3b0c442 | 2.4.2.A | 2.4.2.A | false |  |
| 2.4.2.A.(1)#e3b0c442 | 2.4.2.A.(1) | 2.4.2.A | false |  |
| 2.4.2.A.(2)#2ad7b196 | 2.4.2.A.(2) | 2.4.2.A | true | (2) Organ nakli tedavileri, bünyesinde “organ nakli merkezi” bulunan sağlık hizmeti sunucularında gerçekleştirilecektir. |
| 2.4.2.A.(2)#e3b0c442 | 2.4.2.A.(2) | 2.4.2.A | false |  |
| 2.4.2.A.(3)#27eda9b9 | 2.4.2.A.(3) | 2.4.2.A | true | (3) Yurt içinde organın bulunması halinde hastanın organın bulunduğu yere veya organın organ nakli yapılacak merkezin b… |
| 2.4.2.A.(4)#d88f07a7 | 2.4.2.A.(4) | 2.4.2.A | true | (4) Ulusal Organ ve Doku Nakli Koordinasyon Merkezince bildirilen her bir kadavra donör için donörü temin eden sağlık h… |
| 2.4.2.A.(4)#e3b0c442 | 2.4.2.A.(4) | 2.4.2.A | false |  |
| 2.4.2.A.(5)#25245921 | 2.4.2.A.(5) | 2.4.2.A | true | (5) Ölüm Bildirim Sistemindeki (ÖBS) Beyin Ölümü Modülüne ve Ulusal Organ ve Doku Nakli Koordinasyon Merkezine bildirim… |
| 4.2.14.C#0785013b | 4.2.14.C | 4.2.14.C | true | (Değişik: RG-02/10/2026- 33388/ 2-a md. Yürürlük: 10/10/2026) |
| 4.2.14.C#18d26799 | 4.2.14.C | 4.2.14.C | true | (Değişik: RG-02/10/2026- 33388/ 2-b md. Yürürlük: 10/10/2026) |
| 4.2.14.C#433e1e95 | 4.2.14.C | 4.2.14.C | true | 2- Expanded Disability Status Scale (EDSS) 6,5 ve altında olan, |
| 4.2.14.C#b79f07dd | 4.2.14.C | 4.2.14.C | true | (Ek: RG-02/10/2026- 33388/ 2-c md. Yürürlük: 10/10/2026) |
| 4.2.14.C#cc3a10d6 | 4.2.14.C | 4.2.14.C | true | aaaa) Satralizumab yalnızca; yüksek hastalık aktivitesi gösteren, relapslarla seyreden vücut ağırlığı 40 kg veya üzerin… |
| 4.2.14.C#d0fcbde8 | 4.2.14.C | 4.2.14.C | true | 3- En az iki ya da daha fazla immünosupresan tedaviyi (azatiyoprin, mikofenolat mofetil, siklofosfamid veya rituksimab … |
| 4.2.14.C#ecdc6ddc | 4.2.14.C | 4.2.14.C | true | ff) Trastuzumab emtansin; |
| 4.2.14.C#f1502340 | 4.2.14.C | 4.2.14.C | true | gg) Pertuzumab, trastuzumab ve pertuzumab kombinasyonu; |
| 4.2.14.C.a#53e8d7e6 | 4.2.14.C.a | 4.2.14.C | true | a) Aşağıda yer alan kriterleri birlikte sağlayan hastalarda tedaviye monoterapi olarak veya immünosupresif tedavi ile k… |
| 4.2.14.C.a#5debc401 | 4.2.14.C.a | 4.2.14.C | true | a)HER-2/neu testi immünohistokimyasal olarak 3+ (+++) veya FISH/SISH/CISH pozitif olan, neoadjuvan olarak yeterli süre … |
| 4.2.14.C.a#e70fa683 | 4.2.14.C.a | 4.2.14.C | true | a)Pertuzumab, trastuzumab ve kemoterapi ile kombine olarak HER-2/neu testi immünohistokimyasal olarak 3+ (+++) veya FIS… |
| 4.2.14.C.b#bf1895c2 | 4.2.14.C.b | 4.2.14.C | true | b)Metastatik meme kanserinde daha önce trastuzumab ve bir basamak taksan tedavisi almış ve hastalığı sonrasında progres… |
| 4.2.14.C.b#fe54158d | 4.2.14.C.b | 4.2.14.C | true | b)Daha önce metastatik hastalığı için sistemik kemoterapi veya trastuzumab tedavisi almamış, ECOG performans skoru 0-1 … |
| 4.2.14.C.c#4ec7412c | 4.2.14.C.c | 4.2.14.C | true | c)Tıbbi onkoloji uzman hekiminin yer aldığı ve bu hususların belirtildiği sağlık kurulu raporuna dayanılarak tıbbi onko… |
| 4.2.14.C.c#4ec7412c | 4.2.14.C.c | 4.2.14.C | true | c)Tıbbi onkoloji uzman hekiminin yer aldığı ve bu hususların belirtildiği sağlık kurulu raporuna dayanılarak tıbbi onko… |
| 4.2.61#e3b0c442 | 4.2.61 | 4.2.61 | false |  |
| 4.2.61.(1)#e3b0c442 | 4.2.61.(1) | 4.2.61 | false |  |

---

## REMOVED — clause no longer present (re-point references)

_(none)_

---

## NEW — clause added

_(none)_

---
