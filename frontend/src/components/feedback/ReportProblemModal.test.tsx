import { describe, expect, it, vi } from "vitest";
import ReportProblemModal from "./ReportProblemModal";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";

vi.mock("next/navigation", () => ({
  usePathname: () => "/?tab=reference-tools",
  useSearchParams: () => ({
    get: (key: string) => (key === "tab" ? "reference-tools" : null),
  }),
}));

vi.mock("@/components/shell/RoleProvider", () => ({
  useUserRole: () => "billing_officer",
}));

describe("ReportProblemModal", () => {
  it("renders nothing when closed", () => {
    const html = renderToStaticMarkupWithLocale(
      <ReportProblemModal open={false} onClose={() => undefined} />,
      "tr",
    );
    expect(html).toBe("");
  });

  it("renders Turkish fields, safaoksuz@bilun.tech destination, and category options when open in TR", () => {
    const html = renderToStaticMarkupWithLocale(
      <ReportProblemModal open={true} onClose={() => undefined} />,
      "tr",
    );

    expect(html).toContain("safaoksuz@bilun.tech");
    expect(html).toContain("Geri Bildirim");
    expect(html).toContain('id="feedback-name"');
    expect(html).toContain('id="feedback-email"');
    expect(html).toContain('id="feedback-category"');
    expect(html).toContain('id="feedback-message"');
    expect(html).toContain("Geri Bildirimi Gönder");
  });

  it("renders English fields and actions when open in EN", () => {
    const html = renderToStaticMarkupWithLocale(
      <ReportProblemModal open={true} onClose={() => undefined} />,
      "en",
    );

    expect(html).toContain("safaoksuz@bilun.tech");
    expect(html).toContain("Feedback &amp; Problem Report");
    expect(html).toContain("Send Feedback");
    expect(html).toContain('name="website"');
  });
});
