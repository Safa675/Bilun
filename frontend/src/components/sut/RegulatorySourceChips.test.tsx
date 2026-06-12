import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  DrgEk2cGroupCell,
  PatientExemptionRuleSourceAttribution,
  ProcedureCopayRateSourceCell,
  ProcedureSurchargeSourceCell,
  RegulatorySourceChips,
  RuleSourceAttribution,
} from "./RegulatorySourceChips";
import {
  COPAY_RATE_REGULATORY_SOURCE,
  SURCHARGE_REGULATORY_SOURCE,
} from "@/lib/sutRegulatorySources";

describe("RegulatorySourceChips", () => {
  it("renders EK-2G and §1.9.3 for surcharge attribution", () => {
    const html = renderToStaticMarkup(
      <RegulatorySourceChips source={SURCHARGE_REGULATORY_SOURCE} />,
    );

    expect(html).toContain("EK-2G");
    expect(html).toContain("§1.9.3");
  });

  it("renders EK-2C-1 and §2.2 for add-on rate attribution", () => {
    const html = renderToStaticMarkup(
      <RegulatorySourceChips source={COPAY_RATE_REGULATORY_SOURCE} />,
    );

    expect(html).toContain("EK-2C-1");
    expect(html).toContain("§2.2");
    expect(html).not.toContain("§1.9.3");
  });

  it("renders procedure rule chips only when flags are applicable", () => {
    const surchargeHtml = renderToStaticMarkup(
      <ProcedureSurchargeSourceCell applicable={false} emDash="—" />,
    );
    const copayHtml = renderToStaticMarkup(
      <ProcedureCopayRateSourceCell applicable={true} />,
    );

    expect(surchargeHtml).toContain("—");
    expect(copayHtml).toContain("EK-2C-1");
  });

  it("renders rule_source annex chips with full text tooltip", () => {
    const html = renderToStaticMarkup(
      <RuleSourceAttribution ruleSource="SUT §1.8.5(7) + EK-1/A chronic disease copay exemptions" />,
    );

    expect(html).toContain("EK-1A");
    expect(html).toContain("SUT §1.8.5(7) + EK-1/A chronic disease copay exemptions");
  });

  it("aggregates patient exemption rule sources", () => {
    const html = renderToStaticMarkup(
      <PatientExemptionRuleSourceAttribution
        copay={{
          exempt: true,
          n_qualifying: 1,
          qualifying_diagnoses: [],
          exemption_sources: [
            { category: "ek1a_chronic", rule_source: "SUT §1.8.5(7) + EK-1/A" },
            { category: "acil_servis", rule_source: "SUT §1.8.5(5) emergency visit copay waiver" },
          ],
          action: null,
        }}
      />,
    );

    expect(html).toContain("EK-1A");
    expect(html).toContain("SUT §1.8.5(7) + EK-1/A");
  });

  it("renders EK-2C label beside DRG package group", () => {
    const html = renderToStaticMarkup(<DrgEk2cGroupCell group="A3" />);

    expect(html).toContain("EK-2C");
    expect(html).toContain("A3");
  });
});
