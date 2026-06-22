export type Locale = "en" | "tr";

export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_STORAGE_KEY = "bilun:locale";
export const LOCALE_COOKIE_KEY = "bilun:locale";

export type MessageTree = Record<string, string | Record<string, unknown>>;
