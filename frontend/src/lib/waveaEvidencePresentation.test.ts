import { describe, expect, it } from "vitest";
import { translate } from "@/lib/i18n/translate";
import enMessages from "@/messages/en/index";
import trMessages from "@/messages/tr/index";
import { getWaveAEvidencePresentation } from "./waveaEvidencePresentation";

const enT = (key: string) => translate(enMessages, key);
const trT = (key: string) => translate(trMessages, key);

// Distinct review/advisory rule-and-reason pairs in the 50-patient, 94-bill
// Wave A candidate cache (b509); patient and bill scopes have the same set.
const observedPairs = [
  ["2.2.1.B-1.a", "effective_source_and_full_exceptions_must_be_verified_for_service_date"],
  ["2.2.1.B-1.c.training_hospital_outpatient", "effective_source_and_full_exceptions_must_be_verified_for_service_date"],
  ["2.2.1.B-2.(4).training_hospital_inpatient", "effective_source_and_full_exceptions_must_be_verified_for_service_date"],
  ["2.2.1.B-2.a.itemized_ek2b_ek2c_basis", "effective_source_and_full_exceptions_must_be_verified_for_service_date"],
  ["2.2.2.(1).package", "effective_source_and_full_exceptions_must_be_verified_for_service_date"],
  ["2.2.2.A(1).itemized_basis", "effective_source_and_full_exceptions_must_be_verified_for_service_date"],
  ["2.2.2.A(2).itemized_materials_drugs", "effective_source_and_full_exceptions_must_be_verified_for_service_date"],
  ["2.2.2.A(6).training_hospital_itemized", "effective_source_and_full_exceptions_must_be_verified_for_service_date"],
  ["2.2.2.B.(1).diagnosis_based_ek2c", "effective_source_and_full_exceptions_must_be_verified_for_service_date"],
  ["2.4.4.H.(5).platelet_pheresis_separate_bill", "effective_source_and_full_exceptions_must_be_verified_for_service_date"],
  ["1.9.1.(1).extra_fee_permissible_scope", "authored_source_pending_independent_review"],
  ["KARDİYOLOJİ-4.ayni_seans_periferik_anjiografi", "guideline_not_automatic_sut_violation_authority"],
  ["KARDİYOLOJİ-9.kalp_kat_sirasi_cerrahi_sadece_cerrahi", "guideline_not_automatic_sut_violation_authority"],
  ["ORTAK-13.gecmis_muayene_sorgu", "guideline_not_automatic_sut_violation_authority"],
  ["ORTAK-14.onkolojik_ek2b", "guideline_not_automatic_sut_violation_authority"],
  ["ORTAK-19.eksik_faturalama_yuzde10", "guideline_not_automatic_sut_violation_authority"],
  ["ORTAK-2.ek2a2_olmayan_islem", "guideline_not_automatic_sut_violation_authority"],
  ["ORTAK-20.ayaktan_ek2a_yatis_ek2b", "guideline_not_automatic_sut_violation_authority"],
  ["ORTAK-22.seans_kesi_kurali", "guideline_not_automatic_sut_violation_authority"],
  ["ORTAK-25.yatis_oncesi_hazirlik_paket", "guideline_not_automatic_sut_violation_authority"],
  ["ORTAK-28.ek2b_tetkik_gereksiz", "guideline_not_automatic_sut_violation_authority"],
  ["ORTAK-8.paket_islem_ilac_malzeme", "guideline_not_automatic_sut_violation_authority"],
  ["ORTOPEDİ-2.acik_kirik_parmak_ana_islem", "guideline_not_automatic_sut_violation_authority"],
  ["tablo15_15_material_preauth_missing", "approval_evidence_unavailable"],
  ["tablo15_7_green_area_bundled_extra", "warning_requires_review"],
] as const;

describe("getWaveAEvidencePresentation", () => {
  it("gives the billing officer a translated topic and cautious next step", () => {
    const row = {
      rule_id: "1.9.1.(1).extra_fee_permissible_scope",
      reason: "authored_source_pending_independent_review",
    };
    expect(getWaveAEvidencePresentation(row, trT)).toEqual({
      title: "Ek ücret kapsamı",
      nextStep: expect.stringContaining("ayrıca teyit edin"),
    });
    expect(getWaveAEvidencePresentation(row, enT)).toEqual({
      title: "Extra-charge scope",
      nextStep: expect.stringContaining("Verify the source text"),
    });
  });

  it("covers every review/advisory pair observed in the candidate cache in both locales", () => {
    expect(observedPairs).toHaveLength(25);
    for (const [rule_id, reason] of observedPairs) {
      for (const [t, unknownTitle] of [
        [trT, trT("billing.wavea.unknownRuleTitle")],
        [enT, enT("billing.wavea.unknownRuleTitle")],
      ] as const) {
        const { title, nextStep } = getWaveAEvidencePresentation({ rule_id, reason }, t);
        expect(title, rule_id).not.toBe(unknownTitle);
        expect(nextStep, rule_id).not.toBe(t("billing.wavea.unknownNextStep"));
        expect(title, rule_id).not.toContain("billing.wavea.presentation.");
        expect(nextStep, rule_id).not.toContain("billing.wavea.presentation.");
        expect(title, rule_id).not.toMatch(/[a-z]+_[a-z]+/);
      }
    }
  });

  it("uses a conservative next step for a new reason on a known rule", () => {
    const presented = getWaveAEvidencePresentation({
      rule_id: "ORTAK-13.gecmis_muayene_sorgu",
      reason: "new_reason_needing_review",
    }, trT);
    expect(presented.title).toBe("Geçmiş muayene sorgusu");
    expect(presented.nextStep).toBe(trT("billing.wavea.unknownNextStep"));
  });

  it("does not expose unknown rule or reason codes as primary copy", () => {
    const row = { rule_id: "new_unmapped_rule", reason: "unknown_reason" };
    expect(getWaveAEvidencePresentation(row, trT)).toEqual({
      title: trT("billing.wavea.unknownRuleTitle"),
      nextStep: trT("billing.wavea.unknownNextStep"),
    });
    expect(getWaveAEvidencePresentation(row, enT)).toEqual({
      title: enT("billing.wavea.unknownRuleTitle"),
      nextStep: enT("billing.wavea.unknownNextStep"),
    });
  });
});
