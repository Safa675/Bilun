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
  "İşaretli", "Temiz", "Oran sapması", "Seçili filtre",
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
