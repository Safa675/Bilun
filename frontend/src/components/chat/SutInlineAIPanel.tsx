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
  const panelClassName = [
    "frost-panel",
    "sut-chat-panel",
    "sut-premium-enter",
    dock === "center" ? "sut-chat-panel-inline" : "sut-chat-panel-docked",
    dock !== "center" ? `sut-chat-panel-${dock}` : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={panelClassName}>
      <div className="sut-chat-header">
        <div className="sut-chat-title-wrap">
          <Sparkles className="sut-chat-title-icon" />
          <div>
            <div className="sut-chat-title">BILUN Analysis</div>
            <p className="sut-chat-subtitle">{patientId ? `${activeTab} - ${patientId}` : activeTab}</p>
          </div>
        </div>
        <div className="sut-chat-actions">
          <button
            type="button"
            onClick={() => {
              autoFiredRef.current = "";
              setAutoError(null);
              fireAutoAnalysis();
            }}
            aria-label="Regenerate analysis"
            title="Regenerate analysis"
            className="sut-chat-icon-btn"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
          {onDockChange && (
            <div className="sut-chat-actions">
              <button
                type="button"
                onClick={() => onDockChange("left")}
                aria-label="Dock left"
                title="Dock left"
                className={`sut-chat-icon-btn ${dock === "left" ? "sut-chat-icon-btn-active" : ""}`}
              >
                <PanelLeft className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onDockChange("center")}
                aria-label="Center inline"
                title="Center (inline)"
                className={`sut-chat-icon-btn ${dock === "center" ? "sut-chat-icon-btn-active" : ""}`}
              >
                <Minimize2 className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onDockChange("right")}
                aria-label="Dock right"
                title="Dock right"
                className={`sut-chat-icon-btn ${dock === "right" ? "sut-chat-icon-btn-active" : ""}`}
              >
                <PanelRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="sut-chat-copy">
        {isAutoLoading && !autoText && (
          <span className="sut-chat-loading">BILUN is analyzing...</span>
        )}
        {autoText}
        {isAutoLoading && autoText && (
          <span className="sut-chat-cursor" />
        )}
        {autoError && !autoText && (
          <div className="sut-chat-error">
            <AlertCircle className="sut-chat-error-icon" />
            <span>
              {autoError}{" "}
              <button
                type="button"
                onClick={() => {
                  autoFiredRef.current = "";
                  setAutoError(null);
                  fireAutoAnalysis();
                }}
                className="sut-chat-error-link"
              >
                Retry
              </button>
            </span>
          </div>
        )}
      </div>

      {messages.length > 2 && (
        <div className="sut-chat-history">
          {messages.slice(2).map((message, index) => (
            <div
              key={`${message.role}-${index}-${message.content.slice(0, 24)}`}
              className={`sut-chat-message ${message.role === "user" ? "sut-chat-message-user" : "sut-chat-message-assistant"}`}
            >
              {message.role === "user" ? `You: ${message.content}` : message.content}
            </div>
          ))}
        </div>
      )}

      {followUpText && (
        <div className="sut-chat-message sut-chat-message-assistant sut-chat-streaming">
          {followUpText}
          <span className="sut-chat-cursor" />
        </div>
      )}

      {followUpError && (
        <div className="sut-chat-error-text">
          {followUpError}
        </div>
      )}

      <div className="sut-chat-input-row">
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={patientId ? "Ask BILUN about this patient or billing review..." : "Ask BILUN about this workspace..."}
          disabled={isAutoLoading || isResponding}
          className="sut-input sut-chat-input"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!input.trim() || isAutoLoading || isResponding}
          aria-label="Send message"
          className="sut-chat-send-btn"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
