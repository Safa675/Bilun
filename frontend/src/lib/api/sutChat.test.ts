import { afterEach, describe, expect, it, vi } from "vitest";

import { sendSutChatMessage } from "./sutChat";
import type { ChatMessage } from "../domains/common";
import { setModuleLocale } from "../i18n/localeModule";

vi.mock("../cookies", () => ({
  getCookie: vi.fn((name: string) => {
    if (name === "bilun:role") return "dev";
    if (name === "bilun:locale") return "en";
    return null;
  }),
}));

describe("sendSutChatMessage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    setModuleLocale("en");
  });

  it("posts to the SUT-owned chat endpoint and streams tokens", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('data: "Hello"\n\ndata: " world"\n\ndata: "[DONE]"\n\n', {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const tokens: string[] = [];

    await sendSutChatMessage(
      [{ role: "user", content: "Summarize the patient workspace." }],
      {
        patientId: "P-001",
        activeTab: "SUT Patient Workspace",
        onToken: (token) => tokens.push(token),
      },
    );

    expect(tokens).toEqual(["Hello", " world"]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8000/api/chat");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBe(
      JSON.stringify({
        messages: [{ role: "user", content: "Summarize the patient workspace." }],
        patient_id: "P-001",
        active_tab: "SUT Patient Workspace",
        intent: "user_question",
        page_context: null,
        ui_locale: "en",
      }),
    );
  });

  it("sends intent and page_context when provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('data: "ok"\n\ndata: "[DONE]"\n\n', {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const pageContext = {
      page: "patient_workspace" as const,
      patient_id: "P-001",
      sections: { billing_report: { patient_id: "P-001" } },
    };

    await sendSutChatMessage([{ role: "user", content: "Explain each section." }], {
      patientId: "P-001",
      activeTab: "SUT Patient Workspace",
      intent: "user_question",
      pageContext,
      onToken: () => undefined,
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      messages: [{ role: "user", content: "Explain each section." }],
      patient_id: "P-001",
      active_tab: "SUT Patient Workspace",
      intent: "user_question",
      page_context: pageContext,
      ui_locale: "en",
    });
  });

  function mockChatResponse() {
    const fetchMock = vi.fn().mockImplementation(async () => new Response(
      'data: "ok"\n\ndata: "[DONE]"\n\n',
      { status: 200, headers: { "Content-Type": "text/event-stream" } },
    ));
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  function requestMessages(fetchMock: ReturnType<typeof vi.fn>, call = 0): ChatMessage[] {
    return JSON.parse(String(fetchMock.mock.calls[call]?.[1]?.body)).messages;
  }

  const options = { activeTab: "SUT Workspace", onToken: () => undefined };

  function expectWithinLimits(messages: ChatMessage[]) {
    expect(messages.length).toBeLessThanOrEqual(20);
    const lengths = messages.map((message) => Array.from(message.content).length);
    expect(lengths.every((length) => length <= 8_000)).toBe(true);
    expect(lengths.reduce((total, length) => total + length, 0)).toBeLessThanOrEqual(32_000);
  }

  it.each(["user_question", "auto_brief"] as const)(
    "sends only the newest 20 messages for %s without changing stored history",
    async (intent) => {
      const fetchMock = mockChatResponse();
      const history: ChatMessage[] = Array.from({ length: 61 }, (_, index) => ({
        role: index % 2 === 0 ? "user" : "assistant",
        content: `Message ${index}`,
      }));
      const original = structuredClone(history);

      await sendSutChatMessage(history, { ...options, intent });

      expect(requestMessages(fetchMock)).toEqual(original.slice(-20));
      expect(history).toEqual(original);
      expectWithinLimits(requestMessages(fetchMock));
    },
  );

  it.each(["user", "assistant"] as const)(
    "bounds an oversized historical %s message and retains the current question",
    async (role) => {
      const fetchMock = mockChatResponse();
      const history: ChatMessage[] = [
        { role, content: "x".repeat(12_000) },
        { role: "user", content: "What should I do next?" },
      ];

      await sendSutChatMessage(history, options);

      expect(requestMessages(fetchMock)).toEqual([
        { role, content: `${"x".repeat(7_999)}…` },
        history[1],
      ]);
      expect(history[0].content).toHaveLength(12_000);
      expectWithinLimits(requestMessages(fetchMock));
    },
  );

  it("spends the aggregate budget on the newest context, including a bounded oldest prefix", async () => {
    const fetchMock = mockChatResponse();
    const history: ChatMessage[] = Array.from({ length: 6 }, (_, index) => ({
      role: index % 2 === 0 ? "user" : "assistant",
      content: String(index).repeat(8_000),
    }));
    const question: ChatMessage = { role: "user", content: "q".repeat(123) };

    await sendSutChatMessage([...history, question], options);

    const sent = requestMessages(fetchMock);
    expect(sent).toEqual([
      { ...history[2], content: `${"2".repeat(7_876)}…` },
      ...history.slice(3),
      question,
    ]);
    expect(sent.reduce((total, message) => total + Array.from(message.content).length, 0)).toBe(32_000);
    expectWithinLimits(sent);
  });

  it("keeps messages exactly on all server boundaries unchanged", async () => {
    const fetchMock = mockChatResponse();
    const history: ChatMessage[] = Array.from({ length: 4 }, (_, index) => ({
      role: index % 2 === 0 ? "assistant" : "user",
      content: String(index).repeat(8_000),
    }));

    await sendSutChatMessage(history, options);

    expect(requestMessages(fetchMock)).toEqual(history);
    expectWithinLimits(requestMessages(fetchMock));
  });

  it("counts Unicode code points and never splits an astral character while truncating", async () => {
    const fetchMock = mockChatResponse();
    const history: ChatMessage[] = [
      { role: "assistant", content: "🩺".repeat(8_001) },
      { role: "user", content: "😀".repeat(8_000) },
    ];

    await sendSutChatMessage(history, options);

    expect(requestMessages(fetchMock)).toEqual([
      { role: "assistant", content: `${"🩺".repeat(7_999)}…` },
      history[1],
    ]);
    expectWithinLimits(requestMessages(fetchMock));
  });

  it.each(["\u0000", "😀"])("stays within the HTTP body limit with worst-case encoding (%s)", async (character) => {
    const fetchMock = mockChatResponse();
    const history: ChatMessage[] = Array.from({ length: 10 }, (_, index) => ({
      role: index % 2 === 0 ? "assistant" : "user",
      content: character.repeat(8_000),
    }));
    const pageContext = { page: "home" as const, sections: { detail: "p".repeat(24_000) } };
    expect(new TextEncoder().encode(JSON.stringify(pageContext)).length).toBeLessThan(24_576);

    await sendSutChatMessage(history, { ...options, pageContext });

    const body = String(fetchMock.mock.calls[0]?.[1]?.body);
    expect(new TextEncoder().encode(body).length).toBeLessThan(256 * 1024);
    expectWithinLimits(requestMessages(fetchMock));
  });

  it.each(["x", "😀"])("rejects oversized latest input (%s) before fetching and can recover", async (character) => {
    const fetchMock = mockChatResponse();
    const history: ChatMessage[] = [{ role: "assistant", content: "Briefing" }];
    const question: ChatMessage = { role: "user", content: character.repeat(8_001) };

    await expect(sendSutChatMessage([...history, question], options)).rejects.toThrow(
      "Shorten it to 8000 characters or fewer",
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(history).toEqual([{ role: "assistant", content: "Briefing" }]);

    await sendSutChatMessage([...history, { ...question, content: "A shorter question" }], options);

    expect(requestMessages(fetchMock).at(-1)?.content).toBe("A shorter question");
    expectWithinLimits(requestMessages(fetchMock));
  });

  it("localizes oversized input feedback in Turkish", async () => {
    const fetchMock = mockChatResponse();
    setModuleLocale("tr");

    await expect(sendSutChatMessage([{ role: "user", content: "x".repeat(8_001) }], options))
      .rejects.toThrow("Sorunuz çok uzun. 8000 karakter");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("continues beyond ten follow-ups while keeping the complete display history", async () => {
    const fetchMock = mockChatResponse();
    const history: ChatMessage[] = [{ role: "assistant", content: "Initial briefing" }];

    for (let turn = 0; turn < 15; turn += 1) {
      history.push({ role: "user", content: `Question ${turn}` });
      await sendSutChatMessage(history, options);
      expectWithinLimits(requestMessages(fetchMock, turn));
      expect(requestMessages(fetchMock, turn).at(-1)).toEqual(history.at(-1));
      history.push({ role: "assistant", content: "a".repeat(9_000) });
    }

    expect(history).toHaveLength(31);
    expect(history[0].content).toBe("Initial briefing");
    expect(history[2].content).toHaveLength(9_000);
  });

  it("does not let a failed send with restored oversized history poison later sends", async () => {
    const fetchMock = mockChatResponse();
    fetchMock.mockResolvedValueOnce(new Response("Temporary failure", { status: 503 }));
    const history: ChatMessage[] = [
      { role: "user", content: "x".repeat(40_000) },
      { role: "assistant", content: "a".repeat(12_000) },
      { role: "user", content: "First attempt" },
    ];
    const original = structuredClone(history);

    await expect(sendSutChatMessage(history, options)).rejects.toThrow("503");
    history.push({ role: "user", content: "Retry" });
    await sendSutChatMessage(history, options);

    expectWithinLimits(requestMessages(fetchMock, 0));
    expectWithinLimits(requestMessages(fetchMock, 1));
    expect(requestMessages(fetchMock, 1).at(-1)?.content).toBe("Retry");
    expect(history.slice(0, -1)).toEqual(original);
  });
});
