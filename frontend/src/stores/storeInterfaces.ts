import type { ChatMessage } from "@/lib/domains/common";
import type { HealthStatus } from "@/lib/api/health";

/**
 * Chat is a collapsed thin bar (the default), an inline card (center) or a right column;
 * left is reserved for the app sidebar.
 */
export type SutChatDockPosition = "collapsed" | "center" | "right";

export interface SutInlineChatState {
  messages: ChatMessage[];
  autoText: string;
  autoFiredKey: string;
  /** Context keys that already received an auto-briefing in this session. */
  briefedContextKeys: string[];
  /** Unanswered request retained for explicit retry after interruption/remount. */
  pendingQuestion?: string | null;
}

export const EMPTY_SUT_INLINE_CHAT_STATE: SutInlineChatState = {
  messages: [],
  autoText: "",
  autoFiredKey: "",
  briefedContextKeys: [],
};

export interface NavigationState {
  showHowItWorks: boolean;
  showAdmin: boolean;
  showReportProblem: boolean;
  aiDockPosition: SutChatDockPosition;
}

export interface NavigationActions {
  setShowHowItWorks: (show: boolean) => void;
  setShowAdmin: (show: boolean) => void;
  setShowReportProblem: (show: boolean) => void;
  setAiDockPosition: (position: SutChatDockPosition) => void;
}

export type NavigationStore = NavigationState & NavigationActions;

export interface UIStateState {
  healthStatus: HealthStatus | null;
  sutChatSessions: Record<string, SutInlineChatState>;
}

export interface UIStateActions {
  setHealthStatus: (status: HealthStatus | null) => void;
  setSutChatSession: (sessionKey: string, state: SutInlineChatState) => void;
  clearSutChatSession: (sessionKey: string) => void;
}

export type UIStateStore = UIStateState & UIStateActions;
