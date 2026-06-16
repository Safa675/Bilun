import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import RoleSwitcher from "./RoleSwitcher";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";

vi.mock("@/components/shell/RoleProvider", () => ({
  useUserRole: () => "dev",
  useSetUserRole: () => vi.fn(),
}));

describe("RoleSwitcher", () => {
  beforeEach(() => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => "dev",
        setItem: vi.fn(),
      },
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders a select with the two roles and selects the current role", () => {
    const html = renderToStaticMarkupWithLocale(<RoleSwitcher />, "en");
    expect(html).toContain('<select');
    expect(html).toContain('value="dev"');
    expect(html).toContain('value="billing_officer"');
    expect(html).toContain("Developer");
    expect(html).toContain("Billing Officer");
  });
});
