"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Minimize2,
  PanelLeft,
  PanelRight,
  RotateCcw,
  Send,
  Sparkles,
} from "lucide-react";
import { sendSutChatMessage } from "@/lib/api/sutChat";
import {
  buildSutChatContextKey,
  formatSutChatContextPrompt,
  visibleChatMessages,
} from "@/lib/sutChatSession";
import { cn } from "@/lib/cn";
import type { ChatMessage } from "@/lib/domains/common";
import type { SutChatPageContext } from "@/lib/sutChatPageContext";
import type { SutChatDockPosition, SutInlineChatState } from "@/stores/storeInterfaces";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import { useT } from "@/lib/i18n/useTranslations";

interface SutInlineAIPanelProps {
  patientId?: string | null;
  activeTab: string;
  pageContext?: SutChatPageContext | null;
  autoPrompt?: string;
  dock?: SutChatDockPosition;
  onDockChange?: (dock: SutChatDockPosition) => void;
  chatState?: SutInlineChatState;
  onChatStateChange?: (state: SutInlineChatState) => void;
}

export const SUT_INLINE_CHAT_PANEL_WIDTH = 380;

const CHAT_INPUT_CLASS =
  "flex-1 rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-2 text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none transition-[border-color] duration-150 focus:border-[var(--gold)] focus:outline-none focus:shadow-[0_0_0_2px_color-mix(in_srgb,var(--gold)_15%,transparent)]";

const CHAT_CURSOR_CLASS =
  "inline-block h-3.5 w-1.5 ml-0.5 align-text-bottom bg-[var(--gold)] [animation:sutChatCursorBlink_1s_step-end_infinite]";

const CHAT_ICON_BTN_CLASS =
  "inline-flex items-center justify-center rounded-[var(--r-md)] border-none bg-transparent p-[0.3rem] text-[var(--text-muted)] transition-[background,color] duration-150 hover:bg-[var(--gold-subtle)] hover:text-[var(--gold)]";

function resolvePromptKey(activeTab: string): string {
  const map: Record<string, string> = {
    "SUT Workspace": "sutWorkspace",
    Patients: "patients",
    Compliance: "compliance",
    Revenue: "revenue",
    "Reference Tools": "referenceTools",
    "Rule Database": "ruleDatabase",
    "SUT Patient Workspace": "sutPatientWorkspace",
    "SUT Billing Review": "sutBillingReview",
  };
  return map[activeTab] ?? "sutWorkspace";
}

function isAbortError(err: unknown): boolean {
  return (
    (err instanceof DOMException && err.name === "AbortError")
    || (err instanceof Error && /abort|cancel/i.test(err.message))
  );
}

export default function SutInlineAIPanel({
  patientId,
  activeTab,
  pageContext = null,
  autoPrompt,
  dock = "center",
  onDockChange,
  chatState: externalState,
  onChatStateChange,
}: SutInlineAIPanelProps) {
  const t = useT();
  const locale = useLocale();
  const [_messages, _setMessages] = useState<ChatMessage[]>(externalState?.messages ?? []);
  const [_autoText, _setAutoText] = useState(externalState?.autoText ?? "");
  const [autoReasoningText, setAutoReasoningText] = useState("");
  const [isAutoLoading, setIsAutoLoading] = useState(false);
  const [autoError, setAutoError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isResponding, setIsResponding] = useState(false);
  const [followUpText, setFollowUpText] = useState("");
  const [followUpReasoningText, setFollowUpReasoningText] = useState("");
  const [followUpError, setFollowUpError] = useState<string | null>(null);
  const autoAbortRef = useRef<AbortController | null>(null);
  const followUpAbortRef = useRef<AbortController | null>(null);
  const autoFiredRef = useRef<string>(externalState?.autoFiredKey ?? "");
  const briefedContextKeysRef = useRef<string[]>(externalState?.briefedContextKeys ?? []);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const autoInFlightRef = useRef(false);
  const pageContextRef = useRef(pageContext);
  const fireAutoAnalysisRef = useRef<(options?: { force?: boolean }) => void>(() => undefined);
  const prevLocaleRef = useRef(locale);

  useEffect(() => {
    pageContextRef.current = pageContext;
  }, [pageContext]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    briefedContextKeysRef.current = externalState?.briefedContextKeys ?? briefedContextKeysRef.current;
    autoFiredRef.current = externalState?.autoFiredKey ?? autoFiredRef.current;
  }, [externalState?.briefedContextKeys, externalState?.autoFiredKey]);

  const messages = externalState?.messages ?? _messages;
  const autoText = isAutoLoading ? _autoText : (externalState?.autoText ?? _autoText);
  const autoTextRef = useRef(autoText);
  const messagesRef = useRef(messages);

  useEffect(() => {
    autoTextRef.current = autoText;
  }, [autoText]);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const persistChatState = useCallback((next: {
    messages: ChatMessage[];
    autoText: string;
    autoFiredKey?: string;
    briefedContextKeys?: string[];
  }) => {
    if (next.autoFiredKey !== undefined) {
      autoFiredRef.current = next.autoFiredKey;
    }
    if (next.briefedContextKeys !== undefined) {
      briefedContextKeysRef.current = next.briefedContextKeys;
    }
    _setMessages(next.messages);
    messagesRef.current = next.messages;
    _setAutoText(next.autoText);
    autoTextRef.current = next.autoText;
    onChatStateChange?.({
      messages: next.messages,
      autoText: next.autoText,
      autoFiredKey: autoFiredRef.current,
      briefedContextKeys: briefedContextKeysRef.current,
    });
  }, [onChatStateChange]);

  const setMessages = useCallback((nextMessages: ChatMessage[]) => {
    persistChatState({
      messages: nextMessages,
      autoText: autoTextRef.current,
    });
  }, [persistChatState]);

  const setAutoTextStreaming = useCallback((nextText: string) => {
    _setAutoText(nextText);
    autoTextRef.current = nextText;
  }, []);

  const clearInFlightAuto = useCallback(() => {
    setAutoTextStreaming("");
    autoInFlightRef.current = false;
    setAutoError(null);
  }, [setAutoTextStreaming]);

  const fireAutoAnalysis = useCallback((options?: { force?: boolean }) => {
    const force = options?.force ?? false;
    const contextKey = buildSutChatContextKey(patientId, activeTab, locale);
    const briefedKeys = briefedContextKeysRef.current;

    if (autoInFlightRef.current && !force) {
      return;
    }

    if (!force && briefedKeys.includes(contextKey)) {
      return;
    }

    autoAbortRef.current?.abort();
    const controller = new AbortController();
    autoAbortRef.current = controller;
    autoInFlightRef.current = true;

    const promptKey = resolvePromptKey(activeTab);
    const prompt = autoPrompt ?? t(`chat.defaultPrompts.${promptKey}`);
    const userMessage: ChatMessage = {
      role: "user",
      content: formatSutChatContextPrompt(activeTab, patientId, prompt),
    };
    const baseMessages = messagesRef.current;
    const requestMessages = [...baseMessages, userMessage];

    setAutoTextStreaming("");
    setAutoReasoningText("");
    setAutoError(null);
    setIsAutoLoading(true);
    setFollowUpText("");

    let accumulated = "";
    let accumulatedReasoning = "";

    sendSutChatMessage(requestMessages, {
      patientId,
      activeTab,
      intent: "auto_brief",
      pageContext: pageContextRef.current,
      signal: controller.signal,
      onToken: (token: string, event?: string) => {
        if (!mountedRef.current) {
          return;
        }
        if (event === "reasoning") {
          accumulatedReasoning += token;
          setAutoReasoningText(accumulatedReasoning);
        } else {
          accumulated += token;
          setAutoTextStreaming(accumulated);
        }
      },
    })
      .then(() => {
        if (!mountedRef.current) {
          return;
        }
        const nextBriefedKeys = [...new Set([...briefedKeys, contextKey])];
        persistChatState({
          messages: [
            ...baseMessages,
            { role: "assistant", content: accumulated },
          ],
          autoText: "",
          autoFiredKey: contextKey,
          briefedContextKeys: nextBriefedKeys,
        });
        setAutoTextStreaming("");
        setAutoReasoningText("");
      })
      .catch((err) => {
        if (!mountedRef.current) {
          return;
        }
        if (isAbortError(err)) {
          clearInFlightAuto();
          return;
        }
        setAutoTextStreaming("");
        setAutoReasoningText("");
        setAutoError(
          err instanceof Error ? err.message : t("chat.errors.failedAutoAnalysis"),
        );
      })
      .finally(() => {
        if (!mountedRef.current) {
          return;
        }
        if (autoAbortRef.current === controller) {
          autoAbortRef.current = null;
        }
        autoInFlightRef.current = false;
        setIsAutoLoading(false);
      });
  }, [activeTab, autoPrompt, clearInFlightAuto, locale, patientId, persistChatState, setAutoTextStreaming, t]);

  fireAutoAnalysisRef.current = fireAutoAnalysis;

  useEffect(() => {
    if (prevLocaleRef.current !== locale) {
      prevLocaleRef.current = locale;
      followUpAbortRef.current?.abort();
      autoAbortRef.current?.abort();
      persistChatState({
        messages: [],
        autoText: "",
        autoFiredKey: "",
        briefedContextKeys: [],
      });
      setFollowUpText("");
      setFollowUpReasoningText("");
      setFollowUpError(null);
      fireAutoAnalysisRef.current({ force: true });
    }
  }, [locale, persistChatState]);

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      fireAutoAnalysisRef.current();
    }, 400);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      autoAbortRef.current?.abort();
      autoAbortRef.current = null;
    };
  }, [patientId, activeTab]);

  const handleSend = useCallback(() => {
    const question = input.trim();
    if (!question || isResponding) {
      return;
    }

    followUpAbortRef.current?.abort();
    const controller = new AbortController();
    followUpAbortRef.current = controller;

    const nextMessages: ChatMessage[] = [
      ...messages,
      { role: "user", content: question },
    ];
    setMessages(nextMessages);
    setInput("");
    setFollowUpText("");
    setFollowUpReasoningText("");
    setFollowUpError(null);
    setIsResponding(true);

    let accumulated = "";
    let accumulatedReasoning = "";

    sendSutChatMessage(nextMessages, {
      patientId,
      activeTab,
      intent: "user_question",
      pageContext: pageContextRef.current,
      signal: controller.signal,
      onToken: (token: string, event?: string) => {
        if (!mountedRef.current) {
          return;
        }
        if (event === "reasoning") {
          accumulatedReasoning += token;
          setFollowUpReasoningText(accumulatedReasoning);
        } else {
          accumulated += token;
          setFollowUpText(accumulated);
        }
      },
    })
      .then(() => {
        if (!mountedRef.current) {
          return;
        }
        setMessages([
          ...nextMessages,
          { role: "assistant", content: accumulated },
        ]);
        setFollowUpText("");
        setFollowUpReasoningText("");
      })
      .catch((err) => {
        if (!mountedRef.current || isAbortError(err)) {
          return;
        }
        setFollowUpError(
          err instanceof Error ? err.message : t("chat.errors.failedFollowUp"),
        );
      })
      .finally(() => {
        if (!mountedRef.current) {
          return;
        }
        setIsResponding(false);
      });
  }, [activeTab, input, isResponding, messages, patientId, setMessages, t]);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const displayedMessages = visibleChatMessages(messages);

  return (
    <div
      className={cn(
        "border border-[var(--border-subtle)] bg-[var(--surface-base)] px-5 py-4 text-[var(--text-primary)] shadow-[var(--shadow-1)]",
        dock === "center"
          ? "my-4 max-h-80 w-full overflow-y-auto rounded-[var(--r-lg)]"
          : cn(
              "fixed top-0 z-50 h-screen w-[380px] overflow-y-auto rounded-none max-md:w-[min(100vw,380px)]",
              dock === "left" && "left-0",
              dock === "right" && "right-0",
            ),
      )}
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-[0.15rem] h-4 w-4 shrink-0 text-[var(--gold)]" />
          <div>
            <div className="text-[0.95rem] font-bold leading-[1.35] text-[var(--text-primary)]">
              {t("chat.title")}
            </div>
            <p className="mt-[0.2rem] flex items-center gap-1.5 text-[0.78rem] leading-[1.4] text-[var(--text-muted)]">
              {patientId ? (
                <>
                  <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-success)]" aria-hidden="true" />
                  <span className="truncate max-w-[240px]">{t("chat.subtitle.patient", { patientId })}</span>
                </>
              ) : (
                <>
                  <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--gold)]" aria-hidden="true" />
                  <span>{t("chat.subtitle.cohortOverview")}</span>
                </>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => {
              setAutoError(null);
              fireAutoAnalysis({ force: true });
            }}
            aria-label={t("chat.actions.regenerateAnalysis")}
            title={t("chat.actions.regenerateAnalysis")}
            className={CHAT_ICON_BTN_CLASS}
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
          {onDockChange && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onDockChange("left")}
                aria-label={t("chat.actions.dockLeft")}
                title={t("chat.actions.dockLeft")}
                className={cn(
                  CHAT_ICON_BTN_CLASS,
                  dock === "left" && "bg-[var(--gold-subtle)] text-[var(--gold)]",
                )}
              >
                <PanelLeft className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onDockChange("center")}
                aria-label={t("chat.actions.centerInline")}
                title={t("chat.actions.centerInline")}
                className={cn(
                  CHAT_ICON_BTN_CLASS,
                  dock === "center" && "bg-[var(--gold-subtle)] text-[var(--gold)]",
                )}
              >
                <Minimize2 className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onDockChange("right")}
                aria-label={t("chat.actions.dockRight")}
                title={t("chat.actions.dockRight")}
                className={cn(
                  CHAT_ICON_BTN_CLASS,
                  dock === "right" && "bg-[var(--gold-subtle)] text-[var(--gold)]",
                )}
              >
                <PanelRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      <div className={cn("min-h-6 overflow-y-auto whitespace-pre-wrap text-[13px] leading-[1.65] text-[var(--text-primary)]", dock === "center" ? "max-h-52" : "max-h-none")}>
        {displayedMessages.length === 0 && !isAutoLoading && !autoError && (
          <span className="italic text-[var(--text-muted)]">{t("chat.emptyState")}</span>
        )}

        {displayedMessages.map((message, index) => {
          return (
            <div
              key={`${message.role}-${index}-${message.content.slice(0, 24)}`}
              className="mb-3"
            >
              <div className="mb-1 text-[0.68rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                {message.role === "user" ? t("chat.roles.you") : t("chat.roles.bilun")}
              </div>
              <div
                className={cn(
                  "whitespace-pre-wrap text-[13px] leading-[1.7]",
                  message.role === "user"
                    ? "italic text-[var(--text-secondary)]"
                    : "text-[var(--text-primary)]",
                )}
              >
                {message.content}
              </div>
            </div>
          );
        })}

        {isAutoLoading && (
          <>
            {autoReasoningText && (
              <details className="mb-2 rounded-[var(--r-sm)] border border-[var(--border-subtle)] p-2 text-[12px] leading-[1.6]">
                <summary className="cursor-pointer text-[var(--text-muted)] select-none">
                  Thinking{" "}
                  <span className="inline-block h-3 w-3 ml-1 align-text-bottom bg-[var(--text-muted)]/30 [animation:sutChatCursorBlink_1s_step-end_infinite]" />
                </summary>
                <div className="mt-1 whitespace-pre-wrap text-[var(--text-muted)]">
                  {autoReasoningText}
                </div>
              </details>
            )}
            <div className="mb-2 whitespace-pre-wrap text-[13px] leading-[1.7] text-[var(--text-primary)]">
              {!autoText && !autoReasoningText && (
                <span className="italic text-[var(--text-muted)]">{t("chat.loading.analyzing")}</span>
              )}
              {autoText}
              {isAutoLoading && autoText && <span className={CHAT_CURSOR_CLASS} />}
            </div>
          </>
        )}

        {autoError && !isAutoLoading && (
          <div className="flex items-start gap-2 text-[var(--danger)]">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              {autoError}{" "}
              <button
                type="button"
                onClick={() => {
                  setAutoError(null);
                  fireAutoAnalysis({ force: true });
                }}
                className="cursor-pointer border-none bg-transparent p-0 font-[inherit] text-[var(--gold)] underline"
              >
                {t("common.retry")}
              </button>
            </span>
          </div>
        )}
      </div>

      {!patientId && !isAutoLoading && displayedMessages.length > 0 && (
        <div className="mt-2.5 rounded-[var(--r-md)] border border-[var(--gold-subtle)] bg-[var(--gold-subtle)]/20 px-3 py-2 text-[12px] leading-[1.5] text-[var(--text-muted)]">
          <span className="font-medium text-[var(--gold)]">{t("chat.tip.label")}</span>{" "}
          {t("chat.tip.selectPatient")}
        </div>
      )}

      {isResponding && (
        <>
          {followUpReasoningText && (
            <details className="mt-2 rounded-[var(--r-sm)] border border-[var(--border-subtle)] p-2 text-[12px] leading-[1.6]">
              <summary className="cursor-pointer text-[var(--text-muted)] select-none">
                Thinking
                {!followUpText && (
                  <span className="inline-block h-3 w-3 ml-1 align-text-bottom bg-[var(--text-muted)]/30 [animation:sutChatCursorBlink_1s_step-end_infinite]" />
                )}
              </summary>
              <div className="mt-1 whitespace-pre-wrap text-[var(--text-muted)]">
                {followUpReasoningText}
              </div>
            </details>
          )}
          {followUpText && (
            <div className="mt-2 whitespace-pre-wrap text-[13px] leading-[1.7] text-[var(--text-primary)]">
              {followUpText}
              <span className={CHAT_CURSOR_CLASS} />
            </div>
          )}
        </>
      )}

      {followUpError && (
        <div className="mt-2 text-[13px] text-[var(--danger)]">
          {followUpError}
        </div>
      )}

      <div className="mt-2.5 flex items-center gap-2">
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={patientId ? t("chat.input.placeholderPatient") : t("chat.input.placeholderWorkspace")}
          disabled={isResponding}
          className={CHAT_INPUT_CLASS}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!input.trim() || isResponding}
          aria-label={t("chat.actions.sendMessage")}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--r-md)] border-none bg-[var(--gold)] text-[var(--text-inverse)] transition-colors duration-150 hover:bg-[var(--gold-hover)] disabled:cursor-default disabled:bg-[var(--surface-soft)] disabled:text-[var(--text-muted)]"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
