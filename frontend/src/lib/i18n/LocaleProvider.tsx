"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import enMessages from "@/messages/en/index";
import trMessages from "@/messages/tr/index";
import { setModuleLocale } from "./localeModule";
import type { Locale, MessageTree } from "./types";
import { DEFAULT_LOCALE, LOCALE_STORAGE_KEY } from "./types";

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  messages: MessageTree;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

const MESSAGE_CATALOG: Record<Locale, MessageTree> = {
  en: enMessages,
  tr: trMessages,
};

function readStoredLocale(): Locale {
  if (typeof window === "undefined") {
    return DEFAULT_LOCALE;
  }
  const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return stored === "tr" ? "tr" : DEFAULT_LOCALE;
}

export function LocaleProvider({
  children,
  initialLocale,
}: {
  children: ReactNode;
  initialLocale?: Locale;
}) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    const next = initialLocale ?? DEFAULT_LOCALE;
    setModuleLocale(next);
    return next;
  });

  useEffect(() => {
    if (initialLocale !== undefined) {
      setModuleLocale(initialLocale);
      document.documentElement.lang = initialLocale;
      return;
    }
    const stored = readStoredLocale();
    setLocaleState(stored);
    setModuleLocale(stored);
    document.documentElement.lang = stored;
  }, [initialLocale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    setModuleLocale(next);
    window.localStorage.setItem(LOCALE_STORAGE_KEY, next);
    document.documentElement.lang = next;
  }, []);

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      messages: MESSAGE_CATALOG[locale],
    }),
    [locale, setLocale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocaleContext(): LocaleContextValue {
  const context = useContext(LocaleContext);
  if (!context) {
    throw new Error("useLocaleContext must be used within LocaleProvider");
  }
  return context;
}

export function useLocale(): Locale {
  return useLocaleContext().locale;
}
