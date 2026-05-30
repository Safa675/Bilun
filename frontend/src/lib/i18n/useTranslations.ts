"use client";

import { useCallback } from "react";
import { translate } from "./translate";
import { useLocaleContext } from "./LocaleProvider";

export function useT() {
  const { messages } = useLocaleContext();

  return useCallback(
    (key: string, params?: Record<string, string | number | undefined | null>) =>
      translate(messages, key, params),
    [messages],
  );
}
