"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Minimize2,
  PanelRight,
  PanelTopClose,
  PanelTopOpen,
  RotateCcw,
  Send,
  Sparkles,
} from "lucide-react";
import { sendSutChatMessage, validateSutChatQuestion } from "@/lib/api/sutChat";
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
import { useUserRole } from "@/components/shell/RoleProvider";
import { Button, buttonActiveClass, EmptyState } from "@/components/primitives";

interface SutInlineAIPanelProps {
  patientId?: string | null;
  activeTab: string;
  pageContext?: SutChatPageContext | null;
  autoPrompt?: string;
  dock?: SutChatDockPosition;
  onDockChange?: (dock: SutChatDockPosition) => void;
  /** False while a split view is open: the right column is off there, collapse and open still work. */
  allowRightDock?: boolean;
  chatState?: SutInlineChatState;
  onChatStateChange?: (state: SutInlineChatState) => void;
}

export const SUT_INLINE_CHAT_PANEL_WIDTH = 380;

const CHAT_INPUT_MIN_HEIGHT_PX = 36;
const CHAT_INPUT_MAX_HEIGHT_PX = 144;

const CHAT_INPUT_CLASS =
  "flex-1 resize-none overflow-y-auto rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-2 text-[13px] leading-[1.5] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none transition-[border-color] duration-150 focus:border-[var(--gold)] focus:outline-none focus:shadow-[0_0_0_2px_color-mix(in_srgb,var(--gold)_15%,transparent)]";

const CHAT_CURSOR_CLASS =
  "inline-block h-3.5 w-1.5 ml-0.5 align-text-bottom bg-[var(--gold)] [animation:sutChatCursorBlink_1s_step-end_infinite]";

function resolvePromptKey(activeTab: string): string {
  const map: Record<string, string> = {
    "SUT Workspace": "sutWorkspace",
    "SUT Çalışma Alanı": "sutWorkspace",
    Patients: "patients",
    Hastalar: "patients",
    Compliance: "compliance",
    Uyumluluk: "compliance",
    "Revenue Dashboard": "revenue",
    "Gelir Dashboard": "revenue",
    Operations: "operations",
    Operasyonlar: "operations",
    "Red Kuyruğu": "operations",
    "Reference Tools": "referenceTools",
    "Referans Araçları": "referenceTools",
    "Rule Database": "ruleDatabase",
    "Kural Veritabanı": "ruleDatabase",
    "SUT Kural Veritabanı": "ruleDatabase",
    "SUT Patient Workspace": "sutPatientWorkspace",
    "SUT Hasta Çalışma Alanı": "sutPatientWorkspace",
    "SUT Billing Review": "sutBillingReview",
    "SUT Fatura İncelemesi": "sutBillingReview",
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
  allowRightDock = true,
  chatState: externalState,
  onChatStateChange,
}: SutInlineAIPanelProps) {
  const t = useT();
  const locale = useLocale();
  const userRole = useUserRole();
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
  const pendingQuestionRef = useRef(externalState?.pendingQuestion ?? null);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(externalState?.pendingQuestion ?? null);
  const pageContextRef = useRef(pageContext);
  const fireAutoAnalysisRef = useRef<(options?: { force?: boolean }) => void>(() => undefined);
  const prevLocaleRef = useRef(locale);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  // Collapsed mode never starts a brief; opening the panel does (effects below).
  const autoBriefEnabled = dock !== "collapsed";
  const autoBriefEnabledRef = useRef(autoBriefEnabled);
  const wasAutoBriefEnabledRef = useRef(autoBriefEnabled);
  const focusToggleRef = useRef(false);

  const syncInputHeight = useCallback(() => {
    const el = inputRef.current;
    if (!el) {
      return;
    }
    el.style.height = "0px";
    const nextHeight = Math.min(
      Math.max(el.scrollHeight, CHAT_INPUT_MIN_HEIGHT_PX),
      CHAT_INPUT_MAX_HEIGHT_PX,
    );
    el.style.height = `${nextHeight}px`;
  }, []);

  useEffect(() => {
    syncInputHeight();
  }, [input, syncInputHeight]);

  const handleInputFocus = useCallback((event: React.FocusEvent<HTMLTextAreaElement>) => {
    const el = event.currentTarget;
    const end = el.value.length;
    requestAnimationFrame(() => {
      el.setSelectionRange(end, end);
    });
  }, []);

  useEffect(() => {
    pageContextRef.current = pageContext;
  }, [pageContext]);

  useEffect(() => {
    autoBriefEnabledRef.current = autoBriefEnabled;
  }, [autoBriefEnabled]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      autoAbortRef.current?.abort();
      followUpAbortRef.current?.abort();
      autoAbortRef.current = null;
      followUpAbortRef.current = null;
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
    pendingQuestion?: string | null;
  }) => {
    if (next.pendingQuestion !== undefined) {
      pendingQuestionRef.current = next.pendingQuestion;
      setPendingQuestion(next.pendingQuestion);
    }
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
      pendingQuestion: pendingQuestionRef.current,
    });
  }, [onChatStateChange]);

  const setMessages = useCallback((nextMessages: ChatMessage[], pending?: string | null) => {
    persistChatState({
      messages: nextMessages,
      autoText: autoTextRef.current,
      pendingQuestion: pending,
    });
  }, [persistChatState]);

  const setAutoTextStreaming = useCallback((nextText: string) => {
    _setAutoText(nextText);
    autoTextRef.current = nextText;
  }, []);

  const fireAutoAnalysis = useCallback((options?: { force?: boolean }) => {
    const force = options?.force ?? false;
    const contextKey = buildSutChatContextKey(patientId, activeTab, locale);
    const briefedKeys = briefedContextKeysRef.current;

    // Refs close the same-render double-click window; force only bypasses
    // the completed-brief cache, never an active generation or pending answer.
    if (!mountedRef.current || autoAbortRef.current || followUpAbortRef.current || pendingQuestionRef.current) {
      return;
    }

    if (!force && briefedKeys.includes(contextKey)) {
      return;
    }

    const controller = new AbortController();
    autoAbortRef.current = controller;
    const isCurrent = () => mountedRef.current && !controller.signal.aborted
      && autoAbortRef.current === controller;

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
        if (!isCurrent()) {
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
        if (!isCurrent()) {
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
        if (!isCurrent()) {
          return;
        }
        if (isAbortError(err)) {
          setAutoTextStreaming("");
          return;
        }
        setAutoTextStreaming("");
        setAutoReasoningText("");
        setAutoError(
          err instanceof Error ? err.message : t("chat.errors.failedAutoAnalysis"),
        );
      })
      .finally(() => {
        if (!isCurrent()) {
          return;
        }
        if (autoAbortRef.current === controller) {
          autoAbortRef.current = null;
        }
        setIsAutoLoading(false);
      });
  }, [activeTab, autoPrompt, locale, patientId, persistChatState, setAutoTextStreaming, t]);

  useEffect(() => {
    fireAutoAnalysisRef.current = fireAutoAnalysis;
  }, [fireAutoAnalysis]);

  useEffect(() => {
    if (prevLocaleRef.current !== locale) {
      prevLocaleRef.current = locale;
      // Clear any pending debounce from the [patientId, activeTab] effect so
      // the forced re-brief below is not followed by a stale second fire.
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
      followUpAbortRef.current?.abort();
      autoAbortRef.current?.abort();
      followUpAbortRef.current = null;
      autoAbortRef.current = null;
      setIsResponding(false);
      setIsAutoLoading(false);
      persistChatState({
        messages: [],
        autoText: "",
        autoFiredKey: "",
        briefedContextKeys: [],
        pendingQuestion: null,
      });
      setFollowUpText("");
      setFollowUpReasoningText("");
      setFollowUpError(null);
      if (autoBriefEnabledRef.current) fireAutoAnalysisRef.current({ force: true });
    }
  }, [locale, persistChatState]);

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      if (autoBriefEnabledRef.current) fireAutoAnalysisRef.current();
    }, 400);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      autoAbortRef.current?.abort();
      followUpAbortRef.current?.abort();
      autoAbortRef.current = null;
      followUpAbortRef.current = null;
    };
  }, [patientId, activeTab]);

  // Opening the panel starts the brief that collapsed mode skipped. A context that already has its brief
  // is not repeated (fireAutoAnalysis checks briefedContextKeys). Collapsing aborts nothing.
  useEffect(() => {
    const opened = autoBriefEnabled && !wasAutoBriefEnabledRef.current;
    wasAutoBriefEnabledRef.current = autoBriefEnabled;
    if (!opened) return;
    const timer = setTimeout(() => fireAutoAnalysisRef.current(), 0);
    return () => clearTimeout(timer);
  }, [autoBriefEnabled]);

  // After a user toggle the clicked button is replaced by its twin: keep keyboard focus inside the panel.
  useEffect(() => {
    if (!focusToggleRef.current) return;
    focusToggleRef.current = false;
    rootRef.current?.querySelector<HTMLElement>("[data-chat-dock-toggle]")?.focus();
  }, [dock]);

  const changeDock = useCallback((next: SutChatDockPosition) => {
    if ((next === "collapsed") !== (dock === "collapsed")) focusToggleRef.current = true;
    onDockChange?.(next);
  }, [dock, onDockChange]);

  const handleSend = useCallback((retryQuestion?: string) => {
    const question = (retryQuestion ?? input).trim();
    if (!mountedRef.current || !question || autoAbortRef.current || followUpAbortRef.current) {
      return;
    }

    try {
      validateSutChatQuestion(question);
    } catch (err) {
      setFollowUpError(
        err instanceof Error ? err.message : t("chat.errors.failedFollowUp"),
      );
      return;
    }

    const controller = new AbortController();
    followUpAbortRef.current = controller;
    const isCurrent = () => mountedRef.current && !controller.signal.aborted
      && followUpAbortRef.current === controller;

    const history = messagesRef.current;
    const last = history.at(-1);
    const retrying = retryQuestion && pendingQuestionRef.current === question
      && last?.role === "user" && last.content === question;
    const nextMessages: ChatMessage[] = retrying ? history : [
      ...history,
      { role: "user", content: question },
    ];
    setMessages(nextMessages, question);
    setInput("");
    requestAnimationFrame(syncInputHeight);
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
        if (!isCurrent()) {
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
        if (!isCurrent()) {
          return;
        }
        setMessages([
          ...nextMessages,
          { role: "assistant", content: accumulated },
        ], null);
        setFollowUpText("");
        setFollowUpReasoningText("");
      })
      .catch((err) => {
        if (!isCurrent() || isAbortError(err)) {
          return;
        }
        setFollowUpError(
          err instanceof Error ? err.message : t("chat.errors.failedFollowUp"),
        );
      })
      .finally(() => {
        if (!isCurrent()) {
          return;
        }
        followUpAbortRef.current = null;
        setIsResponding(false);
      });
  }, [activeTab, input, patientId, setMessages, syncInputHeight, t]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const collapsed = dock === "collapsed";
  const dockButtonClass =
    "h-7 w-7 border-transparent text-[var(--text-muted)] hover:bg-[var(--gold-subtle)] hover:text-[var(--gold)]";
  const dockControls = onDockChange ? (
    <div className="flex items-center gap-1">
      <Button
        variant="icon"
        data-chat-dock-toggle
        onClick={() => changeDock(collapsed ? "center" : "collapsed")}
        aria-label={collapsed ? t("chat.actions.expand") : t("chat.actions.collapse")}
        title={collapsed ? t("chat.actions.expand") : t("chat.actions.collapse")}
        className={dockButtonClass}
      >
        {collapsed ? <PanelTopOpen className="h-3.5 w-3.5" /> : <PanelTopClose className="h-3.5 w-3.5" />}
      </Button>
      {!collapsed && (
        <Button
          variant="icon"
          onClick={() => changeDock("center")}
          aria-label={t("chat.actions.centerInline")}
          title={t("chat.actions.centerInline")}
          className={cn(dockButtonClass, dock === "center" && buttonActiveClass)}
        >
          <Minimize2 className="h-3.5 w-3.5" />
        </Button>
      )}
      {allowRightDock && (
        <Button
          variant="icon"
          onClick={() => changeDock("right")}
          aria-label={t("chat.actions.dockRight")}
          title={t("chat.actions.dockRight")}
          className={cn(dockButtonClass, dock === "right" && buttonActiveClass)}
        >
          <PanelRight className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
  ) : null;

  if (collapsed) {
    const working = isAutoLoading || isResponding;
    return (
      <div
        ref={rootRef}
        className="mb-3 flex items-center gap-2 rounded-[var(--r-lg)] border border-[var(--border-subtle)] bg-[var(--surface-base)] py-1 pl-3 pr-2 text-[var(--text-primary)] shadow-[var(--shadow-1)]"
      >
        <Sparkles className="h-4 w-4 shrink-0 text-[var(--gold)]" aria-hidden="true" />
        <button
          type="button"
          disabled={!onDockChange}
          onClick={() => changeDock("center")}
          className="min-w-0 flex-1 truncate rounded-[var(--r-sm)] py-1 text-left text-[13px] text-[var(--text-muted)] hover:text-[var(--text-secondary)] disabled:cursor-default"
        >
          {working ? t("chat.collapsed.working") : t("chat.collapsed.prompt")}
        </button>
        {dockControls}
      </div>
    );
  }

  // The header row below wraps (flex-wrap): in the 380px right dock the four controls beside a long subtitle
  // ("Patient: <id>") do not fit one row, and the controls then take their own row instead of running past the viewport edge.
  const displayedMessages = visibleChatMessages(messages);

  return (
    <div
      ref={rootRef}
      className={cn(
        "border border-[var(--border-subtle)] bg-[var(--surface-base)] px-5 py-4 text-[var(--text-primary)] shadow-[var(--shadow-1)]",
        dock === "center"
          ? "my-4 max-h-80 w-full overflow-y-auto rounded-[var(--r-lg)]"
          : "fixed top-0 right-0 z-50 h-screen w-[380px] overflow-y-auto rounded-none max-md:w-[min(100vw,380px)]",
      )}
    >
      <div className="mb-2 flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <div className="flex min-w-0 items-start gap-3">
          <Sparkles className="mt-[0.15rem] h-4 w-4 shrink-0 text-[var(--gold)]" />
          <div>
            <div className="text-[0.95rem] font-bold leading-[1.35] text-[var(--text-primary)]">
              {t("chat.title")}
              {userRole === "dev" && (
                <span className="ml-2 align-middle text-[0.65rem] font-semibold uppercase tracking-wide text-[var(--gold)]">
                  {t("chat.devModeBadge")}
                </span>
              )}
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
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="icon"
            onClick={() => {
              setAutoError(null);
              fireAutoAnalysis({ force: true });
            }}
            disabled={isAutoLoading || isResponding || Boolean(pendingQuestion)}
            aria-label={t("chat.actions.regenerateAnalysis")}
            title={t("chat.actions.regenerateAnalysis")}
            className="h-7 w-7 border-transparent text-[var(--text-muted)] hover:bg-[var(--gold-subtle)] hover:text-[var(--gold)]"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </Button>
          {dockControls}
        </div>
      </div>

      <div className={cn("min-h-6 overflow-y-auto whitespace-pre-wrap text-[13px] leading-[1.65] text-[var(--text-primary)]", dock === "center" ? "max-h-52" : "max-h-none")}>
        {displayedMessages.length === 0 && !isAutoLoading && !autoError && (
          <EmptyState
            icon={<Sparkles className="h-5 w-5" />}
            title={t("chat.emptyState")}
            className="min-h-0 border-transparent bg-transparent px-0 py-6"
          />
        )}

        {displayedMessages.map((message, index) => {
          // Append-only chat: use role+content as a stable key instead of the
          // array index, which shifts when visibleChatMessages filters out
          // briefing messages and makes React misidentify rows. The index is
          // only a tie-breaker for the rare duplicate-question case.
          return (
            <div
              key={`${message.role}-${message.content.slice(0, 64)}-${index}`}
              className="mb-3"
            >
              <div className="mb-1 text-[0.72rem] font-semibold text-[var(--text-muted)]">
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
                  {t("chat.loading.thinking")}{" "}
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
          <EmptyState
            icon={<AlertCircle className="h-5 w-5 text-[var(--danger)]" />}
            title={autoError}
            className="min-h-0 border-[var(--danger)]/30 bg-transparent px-0 py-6"
            action={
              <Button
                variant="ghost"
                size="compact"
                disabled={isAutoLoading || isResponding || Boolean(pendingQuestion)}
                onClick={() => {
                  setAutoError(null);
                  fireAutoAnalysis({ force: true });
                }}
                className="text-[var(--gold)] hover:bg-[var(--gold-subtle)] hover:text-[var(--gold-hover)]"
              >
                {t("common.retry")}
              </Button>
            }
          />
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
                {t("chat.loading.thinking")}
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

      {pendingQuestion && !isResponding && !isAutoLoading && (
        <div role="status" className="mt-2 text-[13px] text-[var(--text-muted)]">
          {t("chat.errors.interruptedFollowUp")}
          <Button variant="ghost" size="compact" onClick={() => handleSend(pendingQuestion)}
            aria-label={t("chat.actions.retryQuestion")}>
            {t("common.retry")}
          </Button>
        </div>
      )}

      <div className="mt-2.5 flex items-end gap-2">
        <textarea
          ref={inputRef}
          rows={1}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onFocus={handleInputFocus}
          onKeyDown={handleKeyDown}
          placeholder={patientId ? t("chat.input.placeholderPatient") : t("chat.input.placeholderWorkspace")}
          disabled={isResponding || isAutoLoading}
          className={CHAT_INPUT_CLASS}
          style={{ minHeight: CHAT_INPUT_MIN_HEIGHT_PX, maxHeight: CHAT_INPUT_MAX_HEIGHT_PX }}
        />
        <Button
          variant="icon"
          onClick={() => handleSend()}
          disabled={!input.trim() || isResponding || isAutoLoading}
          aria-label={t("chat.actions.sendMessage")}
          className="border-none bg-[var(--gold)] text-[var(--text-inverse)] hover:bg-[var(--gold-hover)] hover:border-transparent hover:text-[var(--text-inverse)] disabled:cursor-default disabled:bg-[var(--surface-soft)] disabled:text-[var(--text-muted)] disabled:border-transparent disabled:opacity-100"
        >
          <Send className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
