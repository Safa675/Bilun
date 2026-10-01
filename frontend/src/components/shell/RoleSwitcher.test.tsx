import { describe, expect, it } from "vitest";
import RoleSwitcher from "./RoleSwitcher";
import { RoleProvider } from "./RoleProvider";
import { CLOSED_IDENTITY } from "@/lib/auth";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";

describe("developer entry", () => {
  it.each([false, true])("offers login without a role selector (compact=%s)", (compact) => {
    const html = renderToStaticMarkupWithLocale(<RoleProvider initialIdentity={{ ...CLOSED_IDENTITY, public_billing_enabled: true, capabilities: ["billing"] }}><RoleSwitcher compact={compact} /></RoleProvider>);
    expect(html).toContain('href="/login"');
    expect(html).toContain("Developer sign in");
    expect(html).not.toContain("<select");
    expect(html).not.toContain('value="dev"');
  });

  it("shows developer identity only after the server grants capability", () => {
    const html = renderToStaticMarkupWithLocale(<RoleProvider initialIdentity={{ ...CLOSED_IDENTITY, authenticated: true, username: "tester", role: "dev", capabilities: ["billing", "developer"] }}><RoleSwitcher /></RoleProvider>);
    expect(html).toContain("Developer");
    expect(html).not.toContain('href="/login"');
    expect(html).not.toContain("<select");
  });
});
