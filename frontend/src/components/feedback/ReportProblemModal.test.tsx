import { afterEach, describe, expect, it, vi } from "vitest";
import ReportProblemModal from "./ReportProblemModal";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";

const feedbackState = vi.hoisted(() => ({ localOnly: false }));
vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  return {
    ...actual,
    useState: ((initial: unknown) => actual.useState(
      initial === "idle" && feedbackState.localOnly ? "local_only" : initial,
    )) as typeof actual.useState,
  };
});
afterEach(() => { feedbackState.localOnly = false; });

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
  it.each(["en", "tr"] as const)("honestly localizes undelivered email and the fallback in %s", (locale) => {
    feedbackState.localOnly = true;
    const html = renderToStaticMarkupWithLocale(
      <ReportProblemModal open={true} onClose={() => undefined} />, locale,
    );
    expect(html).not.toContain("RESEND_API_KEY");
    expect(html).not.toContain("Konsola Kaydedildi");
    expect(html).toContain(locale === "en" ? "Email not sent" : "E-posta gönderilmedi");
    const mailto = decodeURIComponent(html.match(/href="(mailto:[^"]+)"/)?.[1] ?? "");
    expect(mailto).toContain(locale === "en" ? "[Bilun Feedback]" : "[Bilun Geri Bildirim]");
    expect(mailto).toContain(locale === "en" ? "Message:" : "Mesaj:");
  });
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
