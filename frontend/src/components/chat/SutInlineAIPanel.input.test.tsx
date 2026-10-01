import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Children, isValidElement, type ReactElement, type ReactNode } from "react";
import type { ChatMessage } from "@/lib/domains/common";
import type { SutInlineChatState } from "@/stores/storeInterfaces";
import { sendSutChatMessage } from "@/lib/api/sutChat";
import SutInlineAIPanel from "./SutInlineAIPanel";

// Exercise the component's input handlers without a DOM dependency. Effects are
// disabled so automatic briefing is independent of these follow-up scenarios.
const hooks = vi.hoisted(() => ({
  states: [] as unknown[],
  refs: [] as { current: unknown }[],
  stateIndex: 0,
  refIndex: 0,
}));

vi.mock("react", async (importOriginal) => ({
  ...await importOriginal<typeof import("react")>(),
  useState: (initial: unknown) => {
    const index = hooks.stateIndex++;
    if (!(index in hooks.states)) hooks.states[index] = initial;
    return [hooks.states[index], (next: unknown) => { hooks.states[index] = next; }];
  },
  useRef: (initial: unknown) => {
    const index = hooks.refIndex++;
    hooks.refs[index] ??= { current: initial };
    return hooks.refs[index];
  },
  useCallback: (callback: unknown) => callback,
  useEffect: () => undefined,
}));

vi.mock("@/lib/api/sutChat", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/api/sutChat")>(),
  sendSutChatMessage: vi.fn(async () => undefined),
}));

vi.mock("@/lib/i18n/LocaleProvider", () => ({ useLocale: () => "en" }));
vi.mock("@/lib/i18n/useTranslations", () => ({ useT: () => (key: string) => key }));
vi.mock("@/components/shell/RoleProvider", () => ({ useUserRole: () => "billing_officer" }));

type Element = ReactElement<Record<string, unknown>>;

function elements(node: ReactNode): Element[] {
  return Children.toArray(node).flatMap((child) => {
    if (!isValidElement<Record<string, unknown>>(child)) return [];
    return [child, ...elements(child.props.children as ReactNode)];
  });
}

function mountPanel(messages: ChatMessage[] = []) {
  let state: SutInlineChatState = {
    messages,
    autoText: "",
    autoFiredKey: "already-briefed",
    briefedContextKeys: [],
  };
  const onChange = vi.fn((next: SutInlineChatState) => { state = next; });
  function render() {
    hooks.stateIndex = 0;
    hooks.refIndex = 0;
    return SutInlineAIPanel({
      activeTab: "SUT Workspace",
      chatState: state,
      onChatStateChange: onChange,
    });
  }
  function input() {
    return elements(render()).find((element) => element.type === "textarea")!;
  }
  return {
    onChange,
    state: () => state,
    input,
    type: (value: string) => {
      (input().props.onChange as (event: { target: { value: string } }) => void)({ target: { value } });
    },
    send: () => {
      const button = elements(render()).find((element) => element.props["aria-label"] === "chat.actions.sendMessage")!;
      (button.props.onClick as () => void)();
    },
    errors: () => elements(render()).filter((element) => (
      typeof element.props.children === "string" && element.props.children.includes("question is too long")
    )),
  };
}

describe("SutInlineAIPanel follow-up input", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    hooks.states = [];
    hooks.refs = [];
    vi.mocked(sendSutChatMessage).mockReset().mockResolvedValue(undefined);
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => { callback(0); return 1; });
  });

  it("rejects an oversized question before persistence and keeps it editable for recovery", async () => {
    const original: ChatMessage[] = [{ role: "assistant", content: "Existing briefing" }];
    const panel = mountPanel(original);
    panel.type("x".repeat(8_001));
    panel.send();

    expect(panel.onChange).not.toHaveBeenCalled();
    expect(sendSutChatMessage).not.toHaveBeenCalled();
    expect(panel.state().messages).toBe(original);
    expect(panel.input().props.value).toBe("x".repeat(8_001));
    expect(panel.errors()).toHaveLength(1);

    panel.type("A shorter question");
    panel.send();
    await new Promise((resolve) => setImmediate(resolve));

    expect(sendSutChatMessage).toHaveBeenCalledTimes(1);
    expect(panel.state().messages).toContainEqual({ role: "user", content: "A shorter question" });
    expect(panel.state().messages.some((message) => message.content.length > 8_000)).toBe(false);
    expect(panel.input().props.value).toBe("");
    expect(panel.errors()).toHaveLength(0);
  });

  it("accepts exactly 8,000 Unicode code points and retains full display history", async () => {
    const original: ChatMessage[] = Array.from({ length: 24 }, (_, index) => ({
      role: index % 2 === 0 ? "user" : "assistant",
      content: `Historical message ${index}`,
    }));
    vi.mocked(sendSutChatMessage).mockImplementation(async (_messages, options) => {
      options.onToken("a".repeat(9_000));
    });
    const panel = mountPanel(original);
    const question = "😀".repeat(8_000);
    panel.type(question);
    panel.send();
    await new Promise((resolve) => setImmediate(resolve));

    expect(panel.state().messages).toEqual([
      ...original,
      { role: "user", content: question },
      { role: "assistant", content: "a".repeat(9_000) },
    ]);
    expect(panel.state().messages).toHaveLength(26);
  });

  it("allows a new send after a failed request with restored oversized history", async () => {
    vi.mocked(sendSutChatMessage).mockRejectedValueOnce(new Error("Temporary failure"));
    const original: ChatMessage[] = [{ role: "user", content: "x".repeat(10_000) }];
    const panel = mountPanel(original);
    panel.type("First attempt");
    panel.send();
    await new Promise((resolve) => setImmediate(resolve));

    expect(panel.input().props.disabled).toBe(false);
    panel.type("Retry");
    panel.send();
    await new Promise((resolve) => setImmediate(resolve));

    expect(sendSutChatMessage).toHaveBeenCalledTimes(2);
    expect(panel.state().messages.slice(0, 3)).toEqual([
      ...original,
      { role: "user", content: "First attempt" },
      { role: "user", content: "Retry" },
    ]);
    expect(panel.input().props.disabled).toBe(false);
  });
});
