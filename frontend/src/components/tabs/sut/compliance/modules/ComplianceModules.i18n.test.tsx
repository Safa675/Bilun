import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { CopayExemptionCompliance } from "./CopayExemptionCompliance";
import { CopayRateCompliance } from "./CopayRateCompliance";
import { SurchargeCompliance } from "./SurchargeCompliance";
import type { PatientAlertsResponse } from "@/lib/domains/sut";

const state = vi.hoisted(() => ({ data: null as PatientAlertsResponse | null }));

vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  return {
    ...actual,
    useState: ((initial: unknown) => actual.useState(
      initial === null ? state.data : initial === true ? false : initial,
    )) as typeof actual.useState,
  };
});

vi.mock("@/components/shell/PatientTabLink", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));
vi.mock("@/lib/api/sut", () => ({ getPatientAlerts: vi.fn() }));

const sourceText = "Kaynak tanı ve kural metni";
const knownTurkishLabels = [
  "Muafiyet uygunluğu", "Hasta ID", "Muafiyet durumu", "Eşleşen tanılar",
  "Önerilen aksiyon", "İncele", "Fatura öncesi", "Standart katılım",
  "İlave ücret", "Uygulanabilir işlemler", "En çok eşleşen", "Uyumluluk durumu",
  "Kullanılamıyor", "Kural ihlali yok", "Uyumlu", "Faturaya git", "Ortalama oran",
  "İşaretli", "Temiz", "Oran sapması", "Seçili filtre", "rapor yok", "Kronik hastalık raporunu", "Muaf (",
];
const modules = [CopayExemptionCompliance, SurchargeCompliance, CopayRateCompliance];

beforeEach(() => {
  state.data = {
    patients: [0, 1].map((i) => ({
      patient_id: `SYNTHETIC-${i}`,
      n_diagnoses: 2,
      icd10_chapters: ["E"],
      copay_exemption: {
        exempt: i === 0,
        qualifying_diagnoses: i === 0 ? [{ icd10: "E11", disease: sourceText }] : [],
      },
      surcharge_exposure: {
        exposure_rate: i === 0 ? 0 : null,
        n_applicable: i === 0 ? 0 : null,
        top_rules: i === 0 ? [{ code: "TEST", name: sourceText }] : [],
      },
      copay_rate_exposure: {
        mean_rate: i === 0 ? 0 : null,
        n_applicable: i === 0 ? 0 : null,
        n_violations: i,
        top_procedures: [],
      },
    })),
  } as unknown as PatientAlertsResponse;
});

describe("Compliance module language", () => {
  it.each(modules)("renders %s in EN without Turkish interface labels", (Module) => {
    const html = renderToStaticMarkupWithLocale(
      <Module cohortPatientIds={new Set()} cohortFilterActive={false} />, "en",
    );
    const uiText = html.replaceAll(sourceText, "").replace(/<[^>]+>/g, "");
    for (const label of knownTurkishLabels) expect(uiText).not.toContain(label);
    expect(uiText).toContain("Patient ID");
    expect(uiText).toContain("Open bill");
    expect(html).not.toMatch(/optimizer\.(modules|filters|tables)/);
    if (Module !== CopayRateCompliance) {
      expect(html).toContain('lang="tr"');
      expect(uiText).toContain("Source text (Turkish)");
      expect(html).toContain(sourceText);
    }
  });

  it.each(modules)("renders %s labels in TR", (Module) => {
    const html = renderToStaticMarkupWithLocale(
      <Module cohortPatientIds={new Set()} cohortFilterActive={false} />, "tr",
    );
    expect(html).toContain("Hasta Kimliği");
    expect(html).toContain("Faturaya git");
    expect(html).not.toContain("Open bill");
  });

  it.each([SurchargeCompliance, CopayRateCompliance])("keeps missing rates unavailable and real zero rates visible in %s", (Module) => {
    const before = JSON.stringify(state.data);
    const html = renderToStaticMarkupWithLocale(
      <Module cohortPatientIds={new Set()} cohortFilterActive={false} />, "en",
    );
    expect(html).toContain("Unavailable");
    expect(html).toMatch(/0(?:\.0)?%/);
    expect(html).toContain("0 procedures");
    expect(JSON.stringify(state.data)).toBe(before);
  });

  it.each(modules)("localizes the empty state in %s", (Module) => {
    state.data = { patients: [] } as unknown as PatientAlertsResponse;
    const html = renderToStaticMarkupWithLocale(
      <Module cohortPatientIds={new Set()} cohortFilterActive={false} />, "en",
    );
    expect(html).toContain("No patients match this filter.");
    expect(html).not.toContain("Seçili filtre");
  });
});

describe("Copay exemption states in the cohort table", () => {
  const unmetEk1a = { category: "ek1a_chronic", counts_toward_exempt: false, missing_requirements: ["chronic_health_report"] };
  const row = (patientId: string, copay: Record<string, unknown>) => ({
    patient_id: patientId,
    n_diagnoses: 2,
    icd10_chapters: ["I", "J"],
    copay_exemption: { n_qualifying: 0, qualifying_diagnoses: [], action: null, ...copay },
    surcharge_exposure: { exposure_rate: 0, n_applicable: 0, top_rules: [] },
    copay_rate_exposure: { mean_rate: 0, n_applicable: 0, n_violations: 0, top_procedures: [] },
  });
  const cells = (html: string, patientId: string) =>
    html.match(new RegExp(`<tr>(?:(?!</tr>).)*${patientId}(?:(?!</tr>).)*</tr>`, "s"))?.[0].replace(/<[^>]+>/g, "|") ?? "";

  beforeEach(() => {
    state.data = {
      patients: [
        row("P-EK1A", { exempt: true, n_qualifying: 1, qualifying_diagnoses: [{ icd10: "J44.0", disease: sourceText }], exemption_sources: [{ category: "ek1a_chronic", counts_toward_exempt: true }], primary_exemption_category: "ek1a_chronic" }),
        row("P-PARTIAL", { exempt: false, partial_exempt: true, has_chronic_health_report: null, n_qualifying: 1, qualifying_diagnoses: [{ icd10: "J44.0", disease: sourceText }], exemption_sources: [unmetEk1a], primary_exemption_category: "ek1a_chronic" }),
        // the patient-alerts rows carry no primary_exemption_category: the ground is the source that counts
        row("P-ACIL", { exempt: true, exemption_sources: [{ category: "acil_servis", counts_toward_exempt: true }] }),
        row("P-NONE", { exempt: false, exemption_sources: [] }),
      ],
    } as unknown as PatientAlertsResponse;
  });

  it("tells a partial EK-1A match from a standard copay and names the ground of an exemption", () => {
    const html = renderToStaticMarkupWithLocale(
      <CopayExemptionCompliance cohortPatientIds={new Set()} cohortFilterActive={false} />, "en",
    );
    expect(cells(html, "P-EK1A")).toContain("|Exempt (EK-1A)|");
    expect(cells(html, "P-EK1A")).toContain("Apply the exemption flag before billing");
    expect(cells(html, "P-PARTIAL")).toContain("|EK-1A match, report missing|");
    expect(cells(html, "P-PARTIAL")).toContain("Check for a chronic health report; if present, set the exemption flag before billing");
    expect(cells(html, "P-PARTIAL")).not.toContain("Standard copay");
    expect(cells(html, "P-ACIL")).toContain("|Exempt (Emergency)|");
    expect(cells(html, "P-ACIL")).not.toContain("EK-1A");
    expect(cells(html, "P-NONE")).toContain("|Standard copay|");
    expect(cells(html, "P-NONE")).toContain("Standard copay collection");
  });

  it("says the same in Turkish", () => {
    const html = renderToStaticMarkupWithLocale(
      <CopayExemptionCompliance cohortPatientIds={new Set()} cohortFilterActive={false} />, "tr",
    );
    expect(cells(html, "P-PARTIAL")).toContain("|EK-1A eşleşti, rapor yok|");
    expect(cells(html, "P-PARTIAL")).toContain("Kronik hastalık raporunu kontrol edin; varsa faturadan önce muafiyet bayrağını uygulayın");
    expect(cells(html, "P-NONE")).toContain("|Standart katılım payı|");
    expect(cells(html, "P-ACIL")).toMatch(/\|Muaf \([^)]+\)\|/);
    expect(cells(html, "P-ACIL")).not.toContain("EK-1A");
  });
});
