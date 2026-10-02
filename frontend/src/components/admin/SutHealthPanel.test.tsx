import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";

vi.mock("@/lib/theme", () => ({
  theme: {
    accent: "#059669",
  },
}));

import SutHealthPanel from "./SutHealthPanel";

describe("SutHealthPanel", () => {
  it("renders the health status fields when data is present", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutHealthPanel healthStatus={{ status: "ready", patients: 18, build_id: "sut-build-1", message: "Healthy" }} />,
    );

    expect(html).toContain("Admin");
    expect(html).toContain("ready");
    expect(html).toContain("18");
    expect(html).toContain("sut-build-1");
    expect(html).toContain("Healthy");
  });

  it("shows an unavailable fallback while health data is absent", () => {
    const html = renderToStaticMarkupWithLocale(<SutHealthPanel healthStatus={null} />);

    expect(html).toContain("unavailable");
    expect(html).toContain("Patients:");
    expect(html).toContain("—");
    expect(html).toContain("Build:");
  });
});

it("renders degraded readiness and unknown count/build without raw translation keys", () => {
  const html = renderToStaticMarkupWithLocale(<SutHealthPanel healthStatus={{ status: "degraded", patients: null, build_id: null }} />);
  expect(html).toContain("degraded");
  expect(html).not.toContain("admin.statuses.");
  expect(html.match(/—/g)).toHaveLength(2);
});
