import { buildApiUrl, extractSseFrames, parseSsePayload } from "../apiClient";
import { getCookie } from "../cookies";
import type { ChatMessage } from "../domains/common";
import type { SutChatPageContext } from "../sutChatPageContext";
import { LOCALE_COOKIE_KEY, type Locale } from "../i18n/types";
import { getModuleLocale } from "../i18n/localeModule";
import { translate } from "../i18n/translate";
import { translateApiText } from "../apiMessages";
import enMessages from "@/messages/en/index";
import trMessages from "@/messages/tr/index";

function activeMessages() {
  return getModuleLocale() === "tr" ? trMessages : enMessages;
}

function t(
  key: string,
  params?: Record<string, string | number | undefined | null>,
): string {
  return translate(activeMessages(), key, params);
}

function parseUiLocale(value: string | null): Locale {
  return value === "tr" ? "tr" : "en";
}

export type SutChatIntent = "auto_brief" | "user_question";

// Keep these in sync with BilunChatRequest in src/bilun/api/routes/chat.py.
const MAX_CHAT_MESSAGES = 20;
const MAX_CHAT_MESSAGE_CHARACTERS = 8_000;
const MAX_CHAT_TOTAL_CHARACTERS = 32_000;

export function validateSutChatQuestion(question: string): void {
  // Python/Pydantic count Unicode code points, not JavaScript UTF-16 units.
  if (Array.from(question).length > MAX_CHAT_MESSAGE_CHARACTERS) {
    throw new Error(t("chat.errors.questionTooLong", {
      max: MAX_CHAT_MESSAGE_CHARACTERS,
    }));
  }
}

function boundedChatMessages(messages: ChatMessage[]): ChatMessage[] {
  const latest = messages.at(-1);
  if (!latest) {
    return [];
  }
  // Never silently change the current question to make it fit.
  validateSutChatQuestion(latest.content);
  const bounded = [{ ...latest }];
  let remaining = MAX_CHAT_TOTAL_CHARACTERS - Array.from(latest.content).length;

  for (let index = messages.length - 2;
    index >= 0 && bounded.length < MAX_CHAT_MESSAGES && remaining > 0;
    index -= 1) {
    const message = messages[index];
    const limit = Math.min(MAX_CHAT_MESSAGE_CHARACTERS, remaining);
    const characters: string[] = [];
    // Read only the bounded prefix, even for an oversized restored message.
    for (const character of message.content) {
      if (characters.length === limit) {
        characters[limit - 1] = "…";
        break;
      }
      characters.push(character);
    }
    bounded.push({ ...message, content: characters.join("") });
    remaining -= characters.length;
  }

  // This is an outgoing copy only; the full thread stays in the UI/store.
  return bounded.reverse();
}

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
  const requestMessages = boundedChatMessages(messages);
  const url = buildApiUrl("/api/chat");
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
      return new Error(t("chat.api.requestTimedOut"));
    }
    return err;
  };

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: requestMessages,
        patient_id: patientId ?? null,
        active_tab: activeTab,
        intent,
        page_context: pageContext,
        ui_locale: uiLocale,
      }),
      signal: requestController.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw toAbortError(err);
    }
    throw new Error(t("chat.api.couldNotReachApi", { url }));
  }

  if (!response.ok) {
    clearTimeout(timeoutId);
    const body = await response.text().catch(() => "");
    throw new Error(
      body.trim()
        ? t("chat.api.failedWithBody", {
            status: response.status,
            statusText: response.statusText,
            body: body.trim(),
          })
        : t("chat.api.failedWithoutBody", {
            status: response.status,
            statusText: response.statusText,
          }),
    );
  }

  const reader = response.body?.getReader();
  if (!reader) {
    clearTimeout(timeoutId);
    throw new Error(t("chat.api.noResponseBody"));
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
          throw new Error(translateApiText(payload));
        }
        // LLM error yields arrive as plain data tokens (not event:error).
        const localized =
          typeof payload === "string" && /^(⚠️\s*)?(API error|The LLM|LLM )/i.test(payload)
            ? translateApiText(payload)
            : payload;
        onToken(localized, frame.event || undefined);
        tokenCount += 1;
        lastActivityTime = Date.now();
      }

      if (done) {
        break;
      }

      if (Date.now() - lastActivityTime > idleTimeoutMs) {
        throw new Error(t("chat.api.noResponseReceived"));
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
    throw new Error(t("chat.api.emptyResponse"));
  }
}
