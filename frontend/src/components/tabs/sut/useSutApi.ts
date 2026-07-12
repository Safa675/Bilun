"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { isAbortError } from "../../../lib/api/request";
import { getModuleLocale } from "../../../lib/i18n/localeModule";
import { translate } from "../../../lib/i18n/translate";
import enMessages from "@/messages/en/index";
import trMessages from "@/messages/tr/index";

type Fetcher<T> = (opts: { signal: AbortSignal }) => Promise<T>;

interface UseSutApiOptions {
  enabled: boolean;
  onceOnEnable?: boolean;
  abortMessage?: string;
  errorFallback?: string;
}

interface UseSutApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/** Resolve a localized message from the active module-locale catalog. */
function lt(key: string): string {
  const messages = getModuleLocale() === "tr" ? trMessages : enMessages;
  return translate(messages, key);
}

/** Default abort message, resolved against the active locale at call time. */
function defaultAbortMessage(): string {
  return lt("common.requestAborted");
}

/** Default error fallback, resolved against the active locale at call time. */
function defaultErrorMessage(): string {
  return lt("common.loadFailed");
}

export function useSutApi<T>(
  fetcher: Fetcher<T>,
  options: UseSutApiOptions,
): UseSutApiResult<T> {
  const {
    enabled,
    onceOnEnable = true,
    abortMessage,
    errorFallback,
  } = options;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchedRef = useRef(false);
  const [reloadTick, setReloadTick] = useState(0);

  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  useEffect(() => {
    if (!enabled) return;
    if (onceOnEnable && fetchedRef.current) return;

    const controller = new AbortController();
    let active = true;

    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetcherRef.current({ signal: controller.signal });
        if (!active || controller.signal.aborted) return;
        setData(res);
        fetchedRef.current = true;
      } catch (err) {
        if (!active) return;
        if (controller.signal.aborted || isAbortError(err)) {
          setError(abortMessage ?? defaultAbortMessage());
          return;
        }
        setError(err instanceof Error ? err.message : (errorFallback ?? defaultErrorMessage()));
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [enabled, onceOnEnable, reloadTick, abortMessage, errorFallback]);

  const refetch = useCallback(() => {
    fetchedRef.current = false;
    setReloadTick((n) => n + 1);
  }, []);

  return { data, loading, error, refetch };
}
