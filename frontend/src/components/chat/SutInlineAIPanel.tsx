"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
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

const DEFAULT_PROMPTS: Record<string, string> = {
  "SUT Workspace":
    "Summarize the current SUT workspace. Highlight the main rule-review workflows available here and what the user should inspect first.",
  Patients:
    "Summarize the patient cohort directory. Focus on recoverable totals, priority patients, and any exactness caveats before drilling into a patient.",
  Compliance:
    "Summarize compliance alerts for the filtered cohort. Highlight copay exemption gaps, surcharge flags, copay-rate issues, and where exactness blocks action.",
  Revenue:
    "Summarize revenue recovery for the filtered cohort. Highlight recoverable totals, top patients, and where exactness limitations block action.",
  "Reference Tools":
    "Explain which gazette reference tools are available and when a billing officer should use each lookup.",
  "SUT Patient Workspace":
    "Give a patient-level SUT briefing. Summarize the rule-calculation state, exactness-aware optimization findings, and what the billing review should confirm next.",
  "SUT Billing Review":
    "Summarize this SUT billing review. Explain which sections are exact, which remain unavailable, and what the user should verify before taking action.",
};

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
  const [_messages, _setMessages] = useState<ChatMessage[]>(externalState?.messages ?? []);
  const [_autoText, _setAutoText] = useState(externalState?.autoText ?? "");
  const [isAutoLoading, setIsAutoLoading] = useState(false);
  const [autoError, setAutoError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isResponding, setIsResponding] = useState(false);
  const [followUpText, setFollowUpText] = useState("");
  const [followUpError, setFollowUpError] = useState<string | null>(null);
  const [approvedIndices, setApprovedIndices] = useState<Set<number>>(new Set());
  const autoAbortRef = useRef<AbortController | null>(null);
  const followUpAbortRef = useRef<AbortController | null>(null);
  const autoFiredRef = useRef<string>(externalState?.autoFiredKey ?? "");
  const briefedContextKeysRef = useRef<string[]>(externalState?.briefedContextKeys ?? []);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const autoInFlightRef = useRef(false);
  const pageContextRef = useRef(pageContext);
  const fireAutoAnalysisRef = useRef<(options?: { force?: boolean }) => void>(() => undefined);

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
    const contextKey = buildSutChatContextKey(patientId, activeTab);
    const briefedKeys = briefedContextKeysRef.current;

    if (autoInFlightRef.current && !force) {
      return;
    }

    autoAbortRef.current?.abort();
    const controller = new AbortController();
    autoAbortRef.current = controller;
    autoInFlightRef.current = true;

    const prompt = autoPrompt ?? DEFAULT_PROMPTS[activeTab] ?? DEFAULT_PROMPTS["SUT Workspace"];
    const userMessage: ChatMessage = {
      role: "user",
      content: formatSutChatContextPrompt(activeTab, patientId, prompt),
    };
    const baseMessages = messagesRef.current;
    const requestMessages = [...baseMessages, userMessage];

    setAutoTextStreaming("");
    setAutoError(null);
    setIsAutoLoading(true);
    setFollowUpText("");

    let accumulated = "";

    sendSutChatMessage(requestMessages, {
      patientId,
      activeTab,
      intent: "auto_brief",
      pageContext: pageContextRef.current,
      signal: controller.signal,
      onToken: (token: string) => {
        if (!mountedRef.current) {
          return;
        }
        accumulated += token;
        setAutoTextStreaming(accumulated);
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
        setAutoError(
          err instanceof Error ? err.message : "Failed to get SUT analysis. Click regenerate to retry.",
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
  }, [activeTab, autoPrompt, clearInFlightAuto, patientId, persistChatState, setAutoTextStreaming]);

  fireAutoAnalysisRef.current = fireAutoAnalysis;

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
    setFollowUpError(null);
    setIsResponding(true);

    let accumulated = "";

    sendSutChatMessage(nextMessages, {
      patientId,
      activeTab,
      intent: "user_question",
      pageContext: pageContextRef.current,
      signal: controller.signal,
      onToken: (token: string) => {
        if (!mountedRef.current) {
          return;
        }
        accumulated += token;
        setFollowUpText(accumulated);
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
      })
      .catch((err) => {
        if (!mountedRef.current || isAbortError(err)) {
          return;
        }
        setFollowUpError(
          err instanceof Error ? err.message : "Failed to get a SUT response.",
        );
      })
      .finally(() => {
        if (!mountedRef.current) {
          return;
        }
        setIsResponding(false);
      });
  }, [activeTab, input, isResponding, messages, patientId, setMessages]);

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
              BILUN Analysis
            </div>
            <p className="mt-[0.2rem] flex items-center gap-1.5 text-[0.78rem] leading-[1.4] text-[var(--text-muted)]">
              {patientId ? (
                <>
                  <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-success)]" aria-hidden="true" />
                  <span className="truncate max-w-[240px]">Patient: {patientId}</span>
                </>
              ) : (
                <>
                  <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--gold)]" aria-hidden="true" />
                  <span>Cohort overview</span>
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
            aria-label="Regenerate analysis"
            title="Regenerate analysis"
            className={CHAT_ICON_BTN_CLASS}
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
          {onDockChange && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onDockChange("left")}
                aria-label="Dock left"
                title="Dock left"
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
                aria-label="Center inline"
                title="Center (inline)"
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
                aria-label="Dock right"
                title="Dock right"
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
          <span className="italic text-[var(--text-muted)]">BILUN will brief each view and keep the full thread here.</span>
        )}

        {displayedMessages.map((message, index) => {
          const isApproved = approvedIndices.has(index);
          const isAssistant = message.role === "assistant";
          return (
            <div
              key={`${message.role}-${index}-${message.content.slice(0, 24)}`}
              className="mb-3"
            >
              <div className="mb-1 text-[0.68rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                {message.role === "user" ? "You" : "BILUN"}
              </div>
              <div
                className={cn(
                  "whitespace-pre-wrap text-[13px] leading-[1.7]",
                  isAssistant && isApproved && "border-l-2 border-[var(--color-success)] pl-2",
                  message.role === "user"
                    ? "italic text-[var(--text-secondary)]"
                    : "text-[var(--text-primary)]",
                )}
              >
                {message.content}
              </div>
              {isAssistant && (
                <div className="mt-1">
                  <button
                    type="button"
                    onClick={() => {
                      setApprovedIndices((prev) => {
                        const next = new Set(prev);
                        if (next.has(index)) {
                          next.delete(index);
                        } else {
                          next.add(index);
                        }
                        return next;
                      });
                    }}
                    className={cn(
                      "inline-flex items-center gap-1 rounded-[var(--r-sm)] border px-2 py-0.5 text-[11px] transition-colors",
                      isApproved
                        ? "border-[var(--color-success)] bg-[var(--color-success)]/10 text-[var(--color-success)]"
                        : "border-[var(--border-subtle)] text-[var(--text-muted)] hover:border-[var(--gold)] hover:text-[var(--gold)]",
                    )}
                  >
                    <Check className="h-3 w-3" />
                    {isApproved ? "Approved" : "Approve"}
                  </button>
                </div>
              )}
            </div>
          );
        })}

        {isAutoLoading && (
          <div className="mb-2 whitespace-pre-wrap text-[13px] leading-[1.7] text-[var(--text-primary)]">
            {!autoText && (
              <span className="italic text-[var(--text-muted)]">BILUN is analyzing...</span>
            )}
            {autoText}
            {autoText && <span className={CHAT_CURSOR_CLASS} />}
          </div>
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
                Retry
              </button>
            </span>
          </div>
        )}
      </div>

      {!patientId && !isAutoLoading && displayedMessages.length > 0 && (
        <div className="mt-2.5 rounded-[var(--r-md)] border border-[var(--gold-subtle)] bg-[var(--gold-subtle)]/20 px-3 py-2 text-[12px] leading-[1.5] text-[var(--text-muted)]">
          <span className="font-medium text-[var(--gold)]">Tip:</span>{" "}
          Select a patient from the cohort table to get detailed billing analysis, including copay savings, lab optimization, drug substitution, and billing strategy comparisons.
        </div>
      )}

      {followUpText && (
        <div className="mt-2 whitespace-pre-wrap text-[13px] leading-[1.7] text-[var(--text-primary)]">
          {followUpText}
          <span className={CHAT_CURSOR_CLASS} />
        </div>
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
          placeholder={patientId ? "Ask BILUN about this patient or billing review..." : "Ask BILUN about this workspace..."}
          disabled={isAutoLoading || isResponding}
          className={CHAT_INPUT_CLASS}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!input.trim() || isAutoLoading || isResponding}
          aria-label="Send message"
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--r-md)] border-none bg-[var(--gold)] text-[var(--text-inverse)] transition-colors duration-150 hover:bg-[var(--gold-hover)] disabled:cursor-default disabled:bg-[var(--surface-soft)] disabled:text-[var(--text-muted)]"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
