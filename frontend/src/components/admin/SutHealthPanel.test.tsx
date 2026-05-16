import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/theme", () => ({
  theme: {
    accent: "#059669",
  },
}));

import SutHealthPanel from "./SutHealthPanel";

describe("SutHealthPanel", () => {
  it("renders the health status fields when data is present", () => {
    const html = renderToStaticMarkup(
      <SutHealthPanel healthStatus={{ status: "ready", patients: 18, build_id: "sut-build-1", message: "Healthy" }} />,
    );

    expect(html).toContain("Admin");
    expect(html).toContain("ready");
    expect(html).toContain("18");
    expect(html).toContain("sut-build-1");
    expect(html).toContain("Healthy");
  });

  it("shows an unavailable fallback while health data is absent", () => {
    const html = renderToStaticMarkup(<SutHealthPanel healthStatus={null} />);

    expect(html).toContain("unavailable");
    expect(html).toContain("Patients: —");
    expect(html).toContain("Build:");
  });
});
