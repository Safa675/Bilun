import type { MessageTree } from "./types";

function getNestedMessage(messages: MessageTree, key: string): string | undefined {
  const parts = key.split(".");
  let current: unknown = messages;

  for (const part of parts) {
    if (!current || typeof current !== "object" || !(part in (current as MessageTree))) {
      return undefined;
    }
    current = (current as MessageTree)[part];
  }

  return typeof current === "string" ? current : undefined;
}

export function interpolate(
  template: string,
  params?: Record<string, string | number | undefined | null>,
): string {
  if (!params) {
    return template;
  }

  return template.replace(/\{\{(\w+)\}\}|\{(\w+)\}/g, (_match, doubleKey, singleKey) => {
    const key = doubleKey ?? singleKey;
    const value = params[key];
    return value == null ? "" : String(value);
  });
}

export function translate(
  messages: MessageTree,
  key: string,
  params?: Record<string, string | number | undefined | null>,
): string {
  const message = getNestedMessage(messages, key);
  if (message == null) {
    return key;
  }
  return interpolate(message, params);
}
