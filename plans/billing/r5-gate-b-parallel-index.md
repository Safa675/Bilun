# R5 — Gate B genişletme: paralel epic orchestration

**Parent:** `plans/billing/sut-referans-normatif-plan.md` (Phase R5)  
**Status:** In progress (2026-06-27) — Epic **B** complete; A/C/D ongoing; §4.2 wave-2 merged locally  
**Prerequisite:** R1–R4 merged or on branch — honest referans / motora bağlı / encode KPI

---

## “Epic plan” ne demek?

**Epic plan** = büyük, bağımsız bir iş paketinin **tek dosyada yazılı yol haritası**.

| Kavram | Anlamı |
|--------|--------|
| **Task / PR planı** | 1–3 gün, tek PR, dar kapsam (`tasks/todo.md`) |
| **Epic plan** | Haftalar–aylar, birden fazla PR, bir **motor / SUT bölümü** (bu dosya ailesi) |
| **Phase (R1–R5)** | Program seviyesi — R5 = “encode borcunu kapat” programı |

Epic plan şunları içerir: mevcut baseline sayıları, fazlar, definition of done, test stratejisi, **hangi dosyaların kime ait olduğu**, mevcut planla ilişki (extend / replace).

Epic plan **kod yazmaz**; agent veya ekip onu uygular.

---

## Dört paralel epic — özet

| Epic | Plan dosyası | Motor(lar) | Encode bugün | Motor-bound gap | Mevcut plan (extend) |
|------|--------------|------------|-------------:|----------------:|----------------------|
| **A** §4.2 ilaç | `r5-epic-4.2-drug-indication.md` | `drug_indication_prose` | 518 clause | ~1.851 | `drug-indication-4.2.14.C-expansion-plan.md` ✅ çoğu bitti |
| **B** §3.1–3.2 malzeme ✅ | `r5-epic-3.1-material-bundling.md` | `material_bundling_prose` | **129 / 129** ✅ | **0** ✅ | `material-bundling-prose-p2-plan.md` ✅ **Epic B closed** |
| **C** §2.2 ödeme | `r5-epic-2.2-payment-method.md` | `payment_method_*` | **0** (manifest yok) | ~88 | `payment-method-compliance-data-fix-plan.md` (runtime; prose trace eksik) |
| **D** §1.8 katılım payı | `r5-epic-1.8-copay-exemption.md` | `copay_exemption_*`, `copay_rate_general` | **0** (manifest yok) | ~60 | `copay-exemption-coverage.md`, `copay-ek1a-ek4d-scope-fix-plan.md` |

**Not:** §3.3 branş malzemesi (`specialty_materials_prose`, 29/32 encoded) bu dörtlünün dışında — malzeme epic’inin **Phase B** olarak aynı agent’a verilebilir veya 5. agent.

Global encode baseline: **952** clause; **299 JSON rules**; graph **952 nodes**.

### §4.2 subsection batches (wave 2 merged 2026-06-27)

| Subsection | Encoded | Gap | Pilot rules | Notes |
|------------|--------:|----:|------------:|-------|
| **4.2.1** | **55** | 227 | **65** (A1–A4) | 36 Tier A pending |
| **4.2.10** | 13 | 118 | 8 | lysosomal storage; mostly Tier C |
| **4.2.6** | 3 | 81 | 3 | GH deficiency |
| **4.2.9** | 7 | 64 | (A6) | ESA + coagulation batch |
| **4.2.27** | 11 | 58 | (A6) | shared 4209_4227 manifest |

Next largest unencoded queues: **4.2.13** (101 → hepatitis Tier C tail), **4.2.24** (61), **4.2.15** (60).

### §4.2.13/4.2.16 A2b+TierB merged (2026-06-27)

| Batch | Rules | Clause IDs | Focus |
|-------|------:|-----------|-------|
| A2a | 12 | 15 | §4.2.13 hepatitis tail |
| A2b | 10 | 13 | §4.2.16 formula (celiac, CMPA, metabolic) |
| Tier B §4.2.13 | 4 | 5 | HBV oral switch/renewal |
| Tier B §4.2.16 | 2 | 7 | Protein metabolism formula |

4213+4216 manifest: **55 encoded, 0 Tier A/B pending** (317 Tier C deferred).
Global encode: **957**; JSON rules: **327**.

---

## 4 paralel agent — evet, ama kurallarla

Dört agent **aynı anda** çalışabilir; her biri **farklı epic plan** + **farklı dosya sahipliği** alır.

```mermaid
flowchart TB
  subgraph shared["Shared (sırayla merge)"]
    COV["build_sut_coverage.py"]
    GRAPH["build_rule_interaction_graph.py"]
    REG["rule_registry.py — read-only unless epic owner"]
  end
  A["Agent A — §4.2 drug"]
  B["Agent B — §3.1 material"]
  C["Agent C — §2.2 payment"]
  D["Agent D — §1.8 copay"]
  A --> COV
  B --> COV
  C --> COV
  D --> COV
  COV --> GRAPH
```

### Agent başına sahiplik (conflict önleme)

| Agent | Sahip olduğu path’ler | Dokunmaması gereken |
|-------|----------------------|---------------------|
| **A §4.2** | `drug_indication_prose.json`, `L4.2_*manifest*`, `drug_indication_*batch*`, `drug_indication_gate_b.py`, `claim_drug_indication.py` | B/C/D JSON + manifest |
| **B §3.1** | `material_bundling_prose.json`, `L1.4_*`, `material_bundling_*batch*` | A/C/D |
| **C §2.2** | `payment_method_2_2.json`, yeni `L2.2_*manifest*`, `payment_method.py` prose extend | A/B/D |
| **D §1.8** | `copay_general_1_8.json`, yeni `L1.8_*manifest*`, `copay_exemption_rules/*` | A/B/C |

### Paylaşılan merge protokolü

1. Her agent kendi epic’inde bitince: **sadece kendi manifest + JSON + batch rules + golden tests**.
2. **Coverage regen:** merge sırasında veya orchestrator agent tek sefer `python scripts/sut/build_sut_coverage.py` + `build_rule_interaction_graph.py`.
3. `scripts/sut/prose/classify.py` — epic owner PR açmadan önce grep; başka epic prefix değiştirmiyorsa dokunma.
4. Tek PR’da iki epic birleştirme — conflict riski; tercih **4 branch → sıralı merge** veya **4 PR + final regen PR**.

## Branch policy (2026-06-27)

**Single branch only:** `feat/sut-referans-normatif-r5` (local + `origin`).

- Agents must **not** create `feat/r5-epic-*` or other feature branches.
- All parallel agents work on the same branch; coordinate via **file ownership** (below).
- After all agents finish: one orchestrator run `build_sut_coverage.py` + `build_rule_interaction_graph.py` if multiple agents touched manifests.

~~### Önerilen branch isimleri~~ (deprecated)

```
feat/sut-referans-normatif-r5   ← only branch
```

---

## Öncelik sırası (iş değeri × hazırlık)

1. **C §2.2** — JSON var, manifest yok; 88 gap; ödeme yöntemi faturalama çekirdeği.
2. **D §1.8** — JSON var (4 rule), status rules kısmen var; 60 gap; copay planları net.
3. **A §4.2** — en büyük gap ama **131+ rule zaten encode**; kalan §4.2 beyond 4.2.14.C + Tier C.
4. **B §3.1** — en küçük gap (35); long-tail corpus batch2.

Paralel çalışma sırası önceliği değiştirmez — hepsi aynı anda başlayabilir.

---

## R5 program definition of done

- [ ] Her epic kendi planındaki “definition of done” maddelerini karşılar.
- [x] `sut_clause_coverage.parquet`: `has_rule_encoding` global **639 → 912** (wave 1+2 §4.2 batches merged locally).
- [x] `rule_interaction_graph.json` regen; **912 nodes** (parquet-aligned).
- [ ] Rule Database: “Motora bağlı” rozet sayısı düşer; false gap yok (R1–R4 korunur).
- [ ] Fact-check audit satırları L2.2 / L1.8 / L4.2 için **PARTIAL → daha yüksek coverage fraction** (COMPLIANT’a erken atlama yok).

---

## Epic plan dosyaları

- [§4.2 ilaç](./r5-epic-4.2-drug-indication.md)
- [§3.1–3.2 malzeme](./r5-epic-3.1-material-bundling.md)
- [§2.2 ödeme yöntemi](./r5-epic-2.2-payment-method.md)
- [§1.8 katılım payı](./r5-epic-1.8-copay-exemption.md)
