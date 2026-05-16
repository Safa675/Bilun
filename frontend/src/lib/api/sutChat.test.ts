import { afterEach, describe, expect, it, vi } from "vitest";

import { sendSutChatMessage } from "./sutChat";

describe("sendSutChatMessage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
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
      }),
    );
  });
});
