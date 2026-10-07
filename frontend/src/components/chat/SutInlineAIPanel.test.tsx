import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import SutInlineAIPanel from "./SutInlineAIPanel";

// Mock the streaming API — we can't test SSE in SSR, but we verify the
// component mounts and calls it with the right args when wired.
vi.mock("@/lib/api/sutChat", () => ({
  sendSutChatMessage: vi.fn(() => Promise.resolve()),
}));

vi.mock("@/lib/sutChatSession", () => ({
  buildSutChatContextKey: vi.fn(() => "cohort::test::en"),
  formatSutChatContextPrompt: vi.fn((_tab: string, _pid: string | null, prompt: string) => prompt),
  visibleChatMessages: vi.fn((messages: unknown[]) => messages),
  isContextBriefingUserMessage: vi.fn(() => false),
}));

vi.mock("@/components/shell/RoleProvider", () => ({
  useUserRole: () => "billing_officer",
}));

describe("SutInlineAIPanel", () => {
  it("renders the chat title and cohort subtitle when no patientId", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutInlineAIPanel activeTab="SUT Workspace" />,
    );
    expect(html).toContain("Bilun Analysis");
    expect(html).toContain("Cohort overview");
  });

  it("renders patient subtitle when patientId is provided", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutInlineAIPanel activeTab="SUT Patient Workspace" patientId="P-001" />,
    );
    expect(html).toContain("Patient: P-001");
  });

  it("renders the empty state message", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutInlineAIPanel activeTab="SUT Workspace" />,
    );
    expect(html).toContain("Bilun will brief each view");
  });

  it("renders in Turkish when locale is tr", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutInlineAIPanel activeTab="SUT Workspace" />,
      "tr",
    );
    expect(html).toContain("Bilun Analizi");
    expect(html).toContain("Kohort özeti");
  });

  it("renders docked-right class when dock is right", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutInlineAIPanel activeTab="SUT Workspace" dock="right" />,
    );
    expect(html).toContain("right-0");
  });

  it("renders center (inline) layout when dock is center", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutInlineAIPanel activeTab="SUT Workspace" dock="center" />,
    );
    // Center layout uses rounded + max-h, not fixed positioning
    expect(html).toContain("rounded-[var(--r-lg)]");
    expect(html).not.toContain("fixed");
  });

  it("renders pre-existing messages from chatState", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutInlineAIPanel
        activeTab="SUT Workspace"
        chatState={{
          messages: [
            { role: "user", content: "What is the copay savings?" },
            { role: "assistant", content: "The copay savings is 5000 TRY." },
          ],
          autoText: "",
          autoFiredKey: "",
          briefedContextKeys: [],
        }}
      />,
    );
    expect(html).toContain("What is the copay savings?");
    expect(html).toContain("The copay savings is 5000 TRY.");
  });

  it("accepts chatState and renders shell without errors", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutInlineAIPanel
        activeTab="SUT Workspace"
        chatState={{
          messages: [],
          autoText: "",
          autoFiredKey: "",
          briefedContextKeys: [],
        }}
      />,
    );
    expect(html).toContain("Bilun Analysis");
  });

  it("renders the send button and textarea input", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutInlineAIPanel activeTab="SUT Workspace" />,
    );
    // The send button has the Send icon; the textarea has the chat input class
    expect(html).toContain("Send message");
    expect(html).toContain("Ask Bilun");
  });

  describe("collapsed dock", () => {
    const noop = () => undefined;

    it("renders a one-line bar: no thread, no input, no fixed column", () => {
      const html = renderToStaticMarkupWithLocale(
        <SutInlineAIPanel activeTab="SUT Workspace" dock="collapsed" onDockChange={noop} />,
      );
      expect(html).toContain("Ask Bilun…");
      expect(html).toContain('aria-label="Open chat"');
      expect(html).toContain('aria-label="Dock right"');
      expect(html).not.toContain("Bilun Analysis");
      expect(html).not.toContain("<textarea");
      expect(html).not.toContain("Send message");
      expect(html).not.toContain("fixed");
    });

    it("renders the bar in Turkish", () => {
      const html = renderToStaticMarkupWithLocale(
        <SutInlineAIPanel activeTab="SUT Workspace" dock="collapsed" onDockChange={noop} />,
        "tr",
      );
      expect(html).toContain("sorun…");
      expect(html).toContain('aria-label="Sohbeti aç"');
    });

    it("keeps open available in a split view and switches the right column off", () => {
      const html = renderToStaticMarkupWithLocale(
        <SutInlineAIPanel activeTab="SUT Workspace" dock="collapsed" onDockChange={noop} allowRightDock={false} />,
      );
      expect(html).toContain('aria-label="Open chat"');
      expect(html).not.toContain("Dock right");
    });

    it("offers collapse, center and right in the open panel, and only collapse and center in a split view", () => {
      const open = renderToStaticMarkupWithLocale(
        <SutInlineAIPanel activeTab="SUT Workspace" dock="center" onDockChange={noop} />,
      );
      expect(open).toContain('aria-label="Collapse chat"');
      expect(open).toContain('aria-label="Center (inline)"');
      expect(open).toContain('aria-label="Dock right"');
      const split = renderToStaticMarkupWithLocale(
        <SutInlineAIPanel activeTab="SUT Workspace" dock="center" onDockChange={noop} allowRightDock={false} />,
      );
      expect(split).toContain('aria-label="Collapse chat"');
      expect(split).not.toContain("Dock right");
    });

    it("renders no dock buttons when nobody can change the dock (the open panel keeps its old markup)", () => {
      const html = renderToStaticMarkupWithLocale(<SutInlineAIPanel activeTab="SUT Workspace" dock="center" />);
      expect(html).not.toContain("Collapse chat");
      expect(html).not.toContain("Dock right");
    });
  });
});
