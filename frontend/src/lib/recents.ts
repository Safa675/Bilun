"use client";

import { useSyncExternalStore } from "react";

export type RecentKind = "patient" | "billing";

export interface RecentEntry {
  patientId: string;
  openedAt: number;
}

const STORAGE_KEYS: Record<RecentKind, string> = {
  patient: "bilun.recents.patient",
  billing: "bilun.recents.billing",
};

const MAX_ENTRIES = 8;

/**
 * SSR-safe localStorage read. Returns `[]` outside the browser
 * or when the stored value is missing / malformed.
 */
export function getRecents(kind: RecentKind, limit: number = MAX_ENTRIES): RecentEntry[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS[kind]);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    const cleaned: RecentEntry[] = [];
    for (const item of parsed) {
      if (
        item &&
        typeof item === "object" &&
        typeof (item as RecentEntry).patientId === "string" &&
        (item as RecentEntry).patientId.length > 0 &&
        typeof (item as RecentEntry).openedAt === "number" &&
        Number.isFinite((item as RecentEntry).openedAt)
      ) {
        cleaned.push({
          patientId: (item as RecentEntry).patientId,
          openedAt: (item as RecentEntry).openedAt,
        });
      }
    }
    cleaned.sort((a, b) => b.openedAt - a.openedAt);
    return cleaned.slice(0, limit);
  } catch {
    return [];
  }
}

/**
 * Record a recent patient or billing-report visit. Dedupes by patientId,
 * trims to MAX_ENTRIES, sorts newest-first. No-op outside the browser.
 */
export function recordRecent(kind: RecentKind, patientId: string): void {
  if (typeof window === "undefined") {
    return;
  }
  const trimmed = patientId?.trim?.();
  if (!trimmed) {
    return;
  }
  const next: RecentEntry[] = [
    { patientId: trimmed, openedAt: Date.now() },
    ...getRecents(kind, MAX_ENTRIES).filter((entry) => entry.patientId !== trimmed),
  ].slice(0, MAX_ENTRIES);
  try {
    window.localStorage.setItem(STORAGE_KEYS[kind], JSON.stringify(next));
    window.dispatchEvent(new CustomEvent("bilun:recents-changed", { detail: { kind } }));
  } catch {
    // Swallow quota / serialization errors silently — recents are non-critical.
  }
}

// Snapshot cache so `getSnapshot` returns referentially stable values between
// reads — required by `useSyncExternalStore` to avoid infinite re-renders.
const SNAPSHOT_CACHE: Record<RecentKind, { raw: string | null; value: RecentEntry[] }> = {
  patient: { raw: null, value: [] },
  billing: { raw: null, value: [] },
};

const EMPTY: RecentEntry[] = [];

function readSnapshot(kind: RecentKind): RecentEntry[] {
  if (typeof window === "undefined") {
    return EMPTY;
  }
  const raw = window.localStorage.getItem(STORAGE_KEYS[kind]);
  const cache = SNAPSHOT_CACHE[kind];
  if (cache.raw === raw) {
    return cache.value;
  }
  const next = getRecents(kind, MAX_ENTRIES);
  SNAPSHOT_CACHE[kind] = { raw, value: next };
  return next;
}

function subscribeToRecents(kind: RecentKind, onChange: () => void): () => void {
  if (typeof window === "undefined") {
    return () => undefined;
  }
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEYS[kind]) onChange();
  };
  const onCustom = (event: Event) => {
    const detail = (event as CustomEvent<{ kind?: RecentKind }>).detail;
    if (!detail || detail.kind === kind) onChange();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener("bilun:recents-changed", onCustom);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("bilun:recents-changed", onCustom);
  };
}

/**
 * Subscribe to the recents list for a given kind.
 * Uses `useSyncExternalStore`, so the value updates synchronously when
 * `recordRecent` runs (same tab) or `storage` fires (other tab).
 * Server snapshot is always `[]` — SSR-safe.
 */
export function useRecents(kind: RecentKind, limit: number = MAX_ENTRIES): RecentEntry[] {
  const entries = useSyncExternalStore(
    (notify) => subscribeToRecents(kind, notify),
    () => readSnapshot(kind),
    () => EMPTY,
  );
  return limit < entries.length ? entries.slice(0, limit) : entries;
}

export const RECENTS_STORAGE_KEYS = STORAGE_KEYS;
export const RECENTS_MAX_ENTRIES = MAX_ENTRIES;
