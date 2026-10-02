import { act, useCallback, useState } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { sendSutChatMessage, type SendSutChatMessageOptions } from "@/lib/api/sutChat";
import type { ChatMessage } from "@/lib/domains/common";
import type { SutChatDockPosition, SutInlineChatState } from "@/stores/storeInterfaces";
import SutInlineAIPanel from "./SutInlineAIPanel";

const settings = vi.hoisted(() => ({ locale: "en", translate: (key: string) => key }));
vi.mock("@/lib/api/sutChat", async importOriginal => ({
  ...await importOriginal<typeof import("@/lib/api/sutChat")>(),
  sendSutChatMessage: vi.fn(),
}));
vi.mock("@/lib/i18n/LocaleProvider", () => ({ useLocale: () => settings.locale }));
vi.mock("@/lib/i18n/useTranslations", () => ({ useT: () => settings.translate }));
vi.mock("@/components/shell/RoleProvider", () => ({ useUserRole: () => "billing_officer" }));

interface PendingCall {
  messages: ChatMessage[];
  options: SendSutChatMessageOptions;
  finish: () => void;
  fail: (error: Error) => void;
}
const calls: PendingCall[] = [];
const renderers: ReactTestRenderer[] = [];
const initialState = (): SutInlineChatState => ({
  messages: [{ role: "assistant", content: "Initial briefing" }],
  autoText: "", autoFiredKey: "cohort::Patients::en", briefedContextKeys: ["cohort::Patients::en"],
});

async function mount(initial = initialState(), sessionKey = "patient:A") {
  let state = initial;
  let renderer: ReactTestRenderer;
  function Harness() {
    const [chatState, setChatState] = useState(initial);
    const [dock, setDock] = useState<SutChatDockPosition>("center");
    const publish = useCallback((next: SutInlineChatState) => {
      state = next;
      setChatState(next);
    }, []);
    return <SutInlineAIPanel activeTab="Patients" chatState={chatState}
      onChatStateChange={publish} dock={dock} onDockChange={setDock} />;
  }
  await act(async () => { renderer = create(<Harness key={sessionKey} />); });
  renderers.push(renderer!);
  const button = (label: string) => renderer!.root.findAllByType("button")
    .find(element => element.props["aria-label"] === label)!;
  return {
    state: () => state,
    button,
    renderer: renderer!,
    async type(value: string) {
      await act(async () => { renderer!.root.findByType("textarea").props.onChange({ target: { value } }); });
    },
    async click(label: string) {
      await act(async () => { button(label).props.onClick(); });
    },
    async refresh(key = sessionKey) {
      await act(async () => { renderer!.update(<Harness key={key} />); });
    },
    async unmount() { await act(async () => { renderer!.unmount(); }); },
  };
}
async function finish(index: number, text: string) {
  await act(async () => { calls[index].options.onToken(text); calls[index].finish(); });
}
const SEND = "chat.actions.sendMessage";
const REGENERATE = "chat.actions.regenerateAnalysis";
const RETRY = "chat.actions.retryQuestion";

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("requestAnimationFrame", (callback: () => void) => { callback(); return 1; });
  settings.locale = "en";
  calls.length = 0;
  vi.mocked(sendSutChatMessage).mockReset().mockImplementation((messages, options) =>
    new Promise<void>((resolve, reject) => calls.push({ messages, options, finish: resolve, fail: reject })));
});
afterEach(async () => {
  for (const renderer of renderers.splice(0)) await act(async () => { renderer.unmount(); });
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("mounted chat generation lifecycle", () => {
  it("serializes follow-up and regeneration without erasing completed answers", async () => {
    const panel = await mount();
    await panel.type("Which bill?");
    await panel.click(SEND);
    expect(panel.button(REGENERATE).props.disabled).toBe(true);
    await panel.click(REGENERATE); // Even a stale/direct handler must not start work.
    expect(calls).toHaveLength(1);
    await finish(0, "Bill A needs correction");
    await panel.click(REGENERATE);
    await finish(1, "Regenerated briefing");
    expect(panel.state().messages.map(m => m.content)).toEqual([
      "Initial briefing", "Which bill?", "Bill A needs correction", "Regenerated briefing",
    ]);
  });

  it("blocks same-render double sends, repeated regenerate, and Enter during analysis", async () => {
    const panel = await mount();
    await panel.type("Question");
    const send = panel.button(SEND).props.onClick;
    await act(async () => { send(); send(); });
    expect(calls).toHaveLength(1);
    await finish(0, "Answer");
    await panel.type("Next question");
    const regenerate = panel.button(REGENERATE).props.onClick;
    await act(async () => { regenerate(); regenerate(); });
    await act(async () => {
      panel.renderer.root.findByType("textarea").props.onKeyDown({ key: "Enter", shiftKey: false, preventDefault: vi.fn() });
    });
    expect(calls).toHaveLength(2);
    await finish(1, "New summary");
    expect(panel.button(REGENERATE).props.disabled).toBe(false);
  });

  it.each(["user_question", "auto_brief"])("keeps %s alive across repeated docking and returns", async intent => {
    const panel = await mount();
    if (intent === "user_question") {
      await panel.type("Question");
      await panel.click(SEND);
    } else await panel.click(REGENERATE);
    for (const label of ["chat.actions.dockRight", "chat.actions.centerInline", "chat.actions.dockRight"]) {
      await panel.click(label);
      expect(calls[0].options.signal?.aborted).toBe(false);
    }
    expect(calls).toHaveLength(1);
    await finish(0, "Completed while docked");
    expect(panel.state().messages.at(-1)?.content).toBe("Completed while docked");
  });

  it("aborts on unmount, ignores late responses, and retries once without duplicating the question", async () => {
    const panel = await mount();
    await panel.type("Interrupted question");
    await panel.click(SEND);
    await act(async () => { calls[0].options.onToken("Partial response"); });
    const staleSend = panel.button(SEND).props.onClick;
    const staleRegenerate = panel.button(REGENERATE).props.onClick;
    await panel.unmount();
    await act(async () => { staleSend(); staleRegenerate(); });
    expect(calls).toHaveLength(1);
    expect(calls[0].options.signal?.aborted).toBe(true);
    const saved = panel.state();
    await finish(0, "late stale response");
    expect(panel.state()).toBe(saved);
    expect(saved.pendingQuestion).toBe("Interrupted question");
    const restored = await mount(saved);
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(calls).toHaveLength(1); // Remount never auto-spends to retry an interrupted question.
    expect(restored.button(RETRY)).toBeDefined();
    const retry = restored.button(RETRY).props.onClick;
    await act(async () => { retry(); retry(); });
    expect(calls).toHaveLength(2);
    expect(calls[1].messages.filter(m => m.content === "Interrupted question")).toHaveLength(1);
    await finish(1, "Recovered answer");
    expect(restored.state().pendingQuestion).toBeNull();
    expect(restored.state().messages.at(-1)?.content).toBe("Recovered answer");
  });

  it.each(["user_question", "auto_brief"])("ignores late %s tokens/completion/finally after a locale change", async intent => {
    const panel = await mount();
    if (intent === "user_question") {
      await panel.type("Old question");
      await panel.click(SEND);
    } else await panel.click(REGENERATE);
    settings.locale = "tr";
    await panel.refresh();
    expect(calls).toHaveLength(2);
    expect(calls[0].options.signal?.aborted).toBe(true);
    await finish(0, "Stale English response");
    expect(panel.button(REGENERATE).props.disabled).toBe(true);
    expect(panel.state().messages).toEqual([]);
    await finish(1, "Yeni yanıt");
    expect(panel.state().messages.map(m => m.content)).toEqual(["Yeni yanıt"]);
    expect(panel.button(REGENERATE).props.disabled).toBe(false);
  });

  it("invalidates old session work and cancels pending auto-brief on unmount", async () => {
    const panel = await mount();
    await panel.type("Bill A question");
    await panel.click(SEND);
    await panel.refresh("patient:B");
    expect(calls[0].options.signal?.aborted).toBe(true);
    await finish(0, "Bill A answer must not reach B");
    expect(panel.renderer.root.findAllByType("div").some(el => el.props.children === "Bill A answer must not reach B")).toBe(false);
    await panel.unmount();
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(calls).toHaveLength(1);
  });

  it("retains failed questions for explicit retry and accepts a new question", async () => {
    const panel = await mount();
    await panel.type("First question");
    await panel.click(SEND);
    await act(async () => { calls[0].fail(new Error("Temporary failure")); });
    expect(panel.button(RETRY)).toBeDefined();
    await panel.type("A different question");
    await panel.click(SEND);
    await finish(1, "New answer");
    expect(panel.state().pendingQuestion).toBeNull();
    expect(panel.state().messages.at(-1)?.content).toBe("New answer");
  });
});
