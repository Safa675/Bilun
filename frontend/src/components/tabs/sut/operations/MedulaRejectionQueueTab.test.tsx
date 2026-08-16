import { describe, expect, it, vi } from "vitest";
import React from "react";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import MedulaRejectionQueueTab from "./MedulaRejectionQueueTab";

vi.mock("@/lib/api/sut", () => ({
  getMedulaRejectionQueue: vi.fn().mockResolvedValue({
    ingest_available: true,
    rows: [
      {
        rejection_event_id: "evt-1",
        patient_id: "SENTETIK-HASTA-0012",
        claim_id: "F-SENTETIK-HASTA-0012-001",
        episode_id: "ep-1",
        medula_stage: "fatura_kayit",
        sonuc_kodu: "1688",
        hata_mesaji: "demo",
        playbook_matched: true,
        playbook_key: "1688_demo",
        rebill_permitted: true,
        corrective_steps_tr: ["Adim 1"],
      },
    ],
    total: 1,
    page: 1,
    page_size: 50,
    facets: { sonuc_kodu: ["1688"], medula_stage: ["fatura_kayit"] },
    stats: { n_events: 10, n_matched: 8, n_rebill_permitted: 7 },
  }),
}));

describe("MedulaRejectionQueueTab", () => {
  it("renders live KPIs and omits leftover triage subtitle", () => {
    const html = renderToStaticMarkupWithLocale(<MedulaRejectionQueueTab />);
    expect(html).not.toContain("reaktif acil");
    expect(html).not.toContain("Reactive triage");
    expect(html).toContain("Result code");
    expect(html).toContain("Only matched templates");
  });
});
