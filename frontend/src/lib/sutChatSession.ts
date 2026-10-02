import type { ChatMessage } from "@/lib/domains/common";

/** Base persistent chat thread key for the SUT workspace. */
export const SUT_WORKSPACE_CHAT_SESSION_KEY = "bilun:workspace";

export function sutWorkspaceChatSessionKey(tab?: string | null): string {
  const normalized = tab?.trim() || "home";
  return `${SUT_WORKSPACE_CHAT_SESSION_KEY}:${normalized}`;
}

export function sutPatientChatSessionKey(patientId: string, claimId?: string | null): string {
  const patientKey = `bilun:patient:${encodeURIComponent(patientId.trim())}`;
  return claimId ? `${patientKey}:bill:${encodeURIComponent(claimId)}` : patientKey;
}

export function buildSutChatContextKey(
  patientId: string | null | undefined,
  activeTab: string,
  locale = "en",
): string {
  const normalizedTab = activeTab.trim() || "SUT Workspace";
  return `${patientId?.trim() || "cohort"}::${normalizedTab}::${locale}`;
}

export function formatSutChatContextPrompt(
  activeTab: string,
  patientId: string | null | undefined,
  prompt: string,
): string {
  const scope = patientId?.trim()
    ? `Patient ${patientId.trim()} · ${activeTab}`
    : activeTab;
  return `[${scope}]\n\n${prompt}`;
}

/** Auto-briefing prompts sent to the API but hidden from the chat UI. */
export function isContextBriefingUserMessage(message: ChatMessage): boolean {
  return message.role === "user" && /^\[[^\]]+\]\n\n/.test(message.content);
}

export function visibleChatMessages(messages: ChatMessage[]): ChatMessage[] {
  return messages.filter((message) => !isContextBriefingUserMessage(message));
}
