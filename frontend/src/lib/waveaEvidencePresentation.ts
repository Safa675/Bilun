import type { WaveAEvidenceRow } from "@/lib/domains/waveaEvidence";

type PresentationRow = Pick<WaveAEvidenceRow, "rule_id" | "reason">;
type Translate = (key: string) => string;

/** Display copy only: a rule ID never establishes a legal outcome on its own. */
const ruleCopy: Record<string, { key: string; reason: string }> = {
  "1.9.1.(1).extra_fee_permissible_scope": {
    key: "extraFeeScope", reason: "authored_source_pending_independent_review",
  },
  "ORTAK-13.gecmis_muayene_sorgu": {
    key: "priorVisitLookup", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "ORTAK-14.onkolojik_ek2b": {
    key: "oncologyEk2b", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "ORTAK-19.eksik_faturalama_yuzde10": {
    key: "underbillingThreshold", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "ORTAK-22.seans_kesi_kurali": {
    key: "sessionDeduction", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "ORTAK-25.yatis_oncesi_hazirlik_paket": {
    key: "preadmissionPackage", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "ORTAK-28.ek2b_tetkik_gereksiz": {
    key: "ek2bTestNecessity", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "ORTAK-8.paket_islem_ilac_malzeme": {
    key: "packageProcedureDrugMaterial", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "ORTAK-2.ek2a2_olmayan_islem": {
    key: "outpatientEk2a2Scope", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "ORTAK-20.ayaktan_ek2a_yatis_ek2b": {
    key: "outpatientAdmissionAnnex", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "KARDİYOLOJİ-4.ayni_seans_periferik_anjiografi": {
    key: "sameSessionAngiography", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "KARDİYOLOJİ-9.kalp_kat_sirasi_cerrahi_sadece_cerrahi": {
    key: "catheterizationAndSurgery", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "ORTOPEDİ-2.acik_kirik_parmak_ana_islem": {
    key: "openFractureProcedure", reason: "guideline_not_automatic_sut_violation_authority",
  },
  "tablo15_15_material_preauth_missing": {
    key: "materialPreauthorization", reason: "approval_evidence_unavailable",
  },
  "tablo15_7_green_area_bundled_extra": {
    key: "greenAreaExtraProcedure", reason: "warning_requires_review",
  },
  "2.2.1.B-1.a": {
    key: "outpatientEk2cPackage", reason: "effective_source_and_full_exceptions_must_be_verified_for_service_date",
  },
  "2.2.1.B-2.a.itemized_ek2b_ek2c_basis": {
    key: "itemizedEk2bEk2cBasis", reason: "effective_source_and_full_exceptions_must_be_verified_for_service_date",
  },
  "2.2.1.B-1.c.training_hospital_outpatient": {
    key: "trainingHospitalOutpatient", reason: "effective_source_and_full_exceptions_must_be_verified_for_service_date",
  },
  "2.2.1.B-2.(4).training_hospital_inpatient": {
    key: "trainingHospitalInpatient", reason: "effective_source_and_full_exceptions_must_be_verified_for_service_date",
  },
  "2.2.2.(1).package": {
    key: "inpatientPackage", reason: "effective_source_and_full_exceptions_must_be_verified_for_service_date",
  },
  "2.2.2.A(1).itemized_basis": {
    key: "inpatientItemizedBasis", reason: "effective_source_and_full_exceptions_must_be_verified_for_service_date",
  },
  "2.2.2.A(2).itemized_materials_drugs": {
    key: "inpatientMaterialsDrugs", reason: "effective_source_and_full_exceptions_must_be_verified_for_service_date",
  },
  "2.2.2.A(6).training_hospital_itemized": {
    key: "trainingHospitalItemized", reason: "effective_source_and_full_exceptions_must_be_verified_for_service_date",
  },
  "2.2.2.B.(1).diagnosis_based_ek2c": {
    key: "diagnosisBasedEk2c", reason: "effective_source_and_full_exceptions_must_be_verified_for_service_date",
  },
  "2.4.4.H.(5).platelet_pheresis_separate_bill": {
    key: "plateletPheresis", reason: "effective_source_and_full_exceptions_must_be_verified_for_service_date",
  },
};

export function getWaveAEvidencePresentation(row: PresentationRow, t: Translate): {
  title: string;
  nextStep: string;
} {
  const copy = ruleCopy[row.rule_id];
  if (!copy) {
    return {
      title: t("billing.wavea.unknownRuleTitle"),
      nextStep: t("billing.wavea.unknownNextStep"),
    };
  }
  const base = `billing.wavea.presentation.${copy.key}`;
  return {
    title: t(`${base}.title`),
    nextStep: row.reason === copy.reason
      ? t(`${base}.nextStep`)
      : t("billing.wavea.unknownNextStep"),
  };
}
