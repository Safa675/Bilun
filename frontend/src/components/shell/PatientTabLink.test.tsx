import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { WorkspaceProvider } from "@/stores/workspaceContext";
import PatientTabLink from "./PatientTabLink";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

describe("PatientTabLink", () => {
  it("renders a real patient href so Ctrl-click has a target", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientTabLink patientId="P-001" href="/patient/P-001?claim=C1">
          P-001
        </PatientTabLink>
      </WorkspaceProvider>,
    );
    expect(html).toContain("href=\"/patient/P-001?claim=C1\"");
    expect(html).toContain("data-patient-tab-link=\"P-001\"");
    expect(html).toContain("P-001");
  });
});
