import type { ChatMessage } from "@/lib/domains/common";
import type { HealthStatus } from "@/lib/api/health";

export type SutChatDockPosition = "left" | "center" | "right";

export interface SutInlineChatState {
  messages: ChatMessage[];
  autoText: string;
  autoFiredKey: string;
}

export const EMPTY_SUT_INLINE_CHAT_STATE: SutInlineChatState = {
  messages: [],
  autoText: "",
  autoFiredKey: "",
};

export interface NavigationState {
  showHowItWorks: boolean;
  showAdmin: boolean;
  aiDockPosition: SutChatDockPosition;
  workspaceEntered: boolean;
}

export interface NavigationActions {
  setShowHowItWorks: (show: boolean) => void;
  setShowAdmin: (show: boolean) => void;
  setAiDockPosition: (position: SutChatDockPosition) => void;
  setWorkspaceEntered: (entered: boolean) => void;
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
