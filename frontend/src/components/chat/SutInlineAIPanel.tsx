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
import { cn } from "@/lib/cn";
import type { ChatMessage } from "@/lib/domains/common";
import type { SutChatDockPosition, SutInlineChatState } from "@/stores/storeInterfaces";

interface SutInlineAIPanelProps {
  patientId?: string | null;
  activeTab: string;
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
  "SUT Analytics":
    "Summarize the cohort's SUT analytics view. Focus on exposure, patient workflow, and any exactness caveats that matter before drilling into a patient.",
  "SUT Optimizer":
    "Summarize the SUT optimizer findings. Highlight copay exemption opportunities, recovery potential, and where exactness limitations block action.",
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
  const autoAbortRef = useRef<AbortController | null>(null);
  const followUpAbortRef = useRef<AbortController | null>(null);
  const autoFiredRef = useRef<string>(externalState?.autoFiredKey ?? "");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const messages = externalState?.messages ?? _messages;
  const autoText = externalState?.autoText ?? _autoText;
  const autoTextRef = useRef(_autoText);
  const messagesRef = useRef(_messages);

  useEffect(() => {
    autoTextRef.current = _autoText;
  }, [_autoText]);

  useEffect(() => {
    messagesRef.current = _messages;
  }, [_messages]);

  const setMessages = useCallback((nextMessages: ChatMessage[]) => {
    _setMessages(nextMessages);
    messagesRef.current = nextMessages;
    onChatStateChange?.({
      messages: nextMessages,
      autoText: autoTextRef.current,
      autoFiredKey: autoFiredRef.current,
    });
  }, [onChatStateChange]);

  const setAutoText = useCallback((nextText: string) => {
    _setAutoText(nextText);
    autoTextRef.current = nextText;
    onChatStateChange?.({
      messages: messagesRef.current,
      autoText: nextText,
      autoFiredKey: autoFiredRef.current,
    });
  }, [onChatStateChange]);

  const resetAutoAnalysis = useCallback(() => {
    autoFiredRef.current = "";
    setAutoText("");
    setAutoError(null);
    setMessages([]);
  }, [setAutoText, setMessages]);

  const fireAutoAnalysis = useCallback(() => {
    const contextKey = `${patientId ?? "workspace"}_${activeTab}`;
    if (autoFiredRef.current === contextKey && autoText) {
      return;
    }

    autoAbortRef.current?.abort();
    const controller = new AbortController();
    autoAbortRef.current = controller;
    autoFiredRef.current = contextKey;

    const prompt = autoPrompt ?? DEFAULT_PROMPTS[activeTab] ?? DEFAULT_PROMPTS["SUT Workspace"];

    setAutoText("");
    setAutoError(null);
    setIsAutoLoading(true);
    setFollowUpText("");
    setMessages([]);

    const initialMessages: ChatMessage[] = [
      { role: "user", content: prompt },
    ];

    let accumulated = "";

    sendSutChatMessage(initialMessages, {
      patientId,
      activeTab,
      signal: controller.signal,
      onToken: (token: string) => {
        if (!mountedRef.current) {
          return;
        }
        accumulated += token;
        setAutoText(accumulated);
      },
    })
      .then(() => {
        if (!mountedRef.current) {
          return;
        }
        setMessages([
          ...initialMessages,
          { role: "assistant", content: accumulated },
        ]);
      })
      .catch((err) => {
        if (!mountedRef.current) {
          return;
        }
        if (isAbortError(err)) {
          resetAutoAnalysis();
          return;
        }
        autoFiredRef.current = "";
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
        setIsAutoLoading(false);
      });
  }, [activeTab, autoPrompt, autoText, patientId, resetAutoAnalysis, setAutoText, setMessages]);

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      fireAutoAnalysis();
    }, 400);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      if (autoAbortRef.current) {
        resetAutoAnalysis();
        autoAbortRef.current.abort();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
            <p className="mt-[0.2rem] text-[0.78rem] leading-[1.4] text-[var(--text-muted)]">
              {patientId ? `${activeTab} - ${patientId}` : activeTab}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => {
              autoFiredRef.current = "";
              setAutoError(null);
              fireAutoAnalysis();
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

      <div className={cn("min-h-6 overflow-y-auto whitespace-pre-wrap text-[13px] leading-[1.65] text-[var(--text-primary)]", dock === "center" ? "max-h-40" : "max-h-none")}>
        {isAutoLoading && !autoText && (
          <span className="italic text-[var(--text-muted)]">BILUN is analyzing...</span>
        )}
        {autoText}
        {isAutoLoading && autoText && (
          <span className={CHAT_CURSOR_CLASS} />
        )}
        {autoError && !autoText && (
          <div className="flex items-start gap-2 text-[var(--danger)]">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              {autoError}{" "}
              <button
                type="button"
                onClick={() => {
                  autoFiredRef.current = "";
                  setAutoError(null);
                  fireAutoAnalysis();
                }}
                className="cursor-pointer border-none bg-transparent p-0 font-[inherit] text-[var(--gold)] underline"
              >
                Retry
              </button>
            </span>
          </div>
        )}
      </div>

      {messages.length > 2 && (
        <div className="mt-2.5 border-t border-[var(--border-subtle)] pt-2">
          {messages.slice(2).map((message, index) => (
            <div
              key={`${message.role}-${index}-${message.content.slice(0, 24)}`}
              className={cn(
                "mb-2 whitespace-pre-wrap text-[13px] leading-[1.7]",
                message.role === "user"
                  ? "italic text-[var(--text-muted)]"
                  : "text-[var(--text-primary)]",
              )}
            >
              {message.role === "user" ? `You: ${message.content}` : message.content}
            </div>
          ))}
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
