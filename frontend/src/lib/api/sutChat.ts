import { buildApiUrl, extractSseFrames, parseSsePayload } from "../apiClient";
import { getCookie } from "../cookies";
import type { ChatMessage } from "../domains/common";
import type { SutChatPageContext } from "../sutChatPageContext";
import { LOCALE_COOKIE_KEY, type Locale } from "../i18n/types";
import { parseRole, ROLE_COOKIE_KEY, type UserRole } from "../userRole";

function parseUiLocale(value: string | null): Locale {
  return value === "tr" ? "tr" : "en";
}

export type SutChatIntent = "auto_brief" | "user_question";

export interface SendSutChatMessageOptions {
  patientId?: string | null;
  activeTab: string;
  intent?: SutChatIntent;
  pageContext?: SutChatPageContext | null;
  onToken: (token: string, event?: string) => void;
  signal?: AbortSignal;
}

export async function sendSutChatMessage(
  messages: ChatMessage[],
  {
    patientId,
    activeTab,
    intent = "user_question",
    pageContext = null,
    onToken,
    signal,
  }: SendSutChatMessageOptions,
): Promise<void> {
  const url = buildApiUrl("/api/chat");
  const userRole: UserRole = parseRole(getCookie(ROLE_COOKIE_KEY));
  const uiLocale: Locale = parseUiLocale(getCookie(LOCALE_COOKIE_KEY));
  const requestController = new AbortController();
  let abortSource: "caller" | "timeout" | null = null;

  const abortRequest = (source: "caller" | "timeout") => {
    if (abortSource !== null) {
      return;
    }
    abortSource = source;
    requestController.abort();
  };

  const onCallerAbort = () => abortRequest("caller");
  if (signal?.aborted) {
    abortRequest("caller");
  } else {
    signal?.addEventListener("abort", onCallerAbort);
  }
  const timeoutId = setTimeout(() => abortRequest("timeout"), 120_000);

  const toAbortError = (err: DOMException) => {
    if (abortSource === "timeout") {
      return new Error("SUT chat request timed out. Please try again.");
    }
    return err;
  };

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages,
        patient_id: patientId ?? null,
        active_tab: activeTab,
        intent,
        page_context: pageContext,
        user_role: userRole,
        ui_locale: uiLocale,
      }),
      signal: requestController.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw toAbortError(err);
    }
    throw new Error(`Could not reach API at ${url}`);
  }

  if (!response.ok) {
    clearTimeout(timeoutId);
    const body = await response.text().catch(() => "");
    throw new Error(
      body.trim()
        ? `SUT chat failed: ${response.status} ${response.statusText} - ${body.trim()}`
        : `SUT chat failed: ${response.status} ${response.statusText}`,
    );
  }

  const reader = response.body?.getReader();
  if (!reader) {
    clearTimeout(timeoutId);
    throw new Error("SUT chat returned no response body.");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let tokenCount = 0;
  let lastActivityTime = Date.now();
  const idleTimeoutMs = 90_000;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (value) {
        lastActivityTime = Date.now();
      }
      if (done) {
        buffer += decoder.decode();
      } else {
        buffer += decoder.decode(value, { stream: true });
      }

      const batch = extractSseFrames(buffer, done);
      buffer = batch.remainder;

      for (const frame of batch.frames) {
        if (frame.data === "[DONE]") {
          return;
        }
        const payload = parseSsePayload(frame.data);
        if (!payload || payload === "[DONE]") {
          continue;
        }
        if (frame.event === "error") {
          throw new Error(payload);
        }
        onToken(payload, frame.event || undefined);
        tokenCount += 1;
        lastActivityTime = Date.now();
      }

      if (done) {
        break;
      }

      if (Date.now() - lastActivityTime > idleTimeoutMs) {
        throw new Error("No response received from SUT chat. Please try again.");
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw toAbortError(err);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    signal?.removeEventListener("abort", onCallerAbort);
  }

  if (tokenCount === 0) {
    throw new Error("SUT chat returned an empty response.");
  }
}
