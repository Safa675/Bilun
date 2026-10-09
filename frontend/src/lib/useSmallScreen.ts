"use client";

import { useSyncExternalStore } from "react";

const QUERY = "(max-width: 640px)";
const snapshot = () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(QUERY).matches;
const serverSnapshot = () => false;
const subscribe = (changed: () => void) => {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", changed);
  return () => media.removeEventListener("change", changed);
};

export function useSmallScreen() {
  return useSyncExternalStore(subscribe, snapshot, serverSnapshot);
}
