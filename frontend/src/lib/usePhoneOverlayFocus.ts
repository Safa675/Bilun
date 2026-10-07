"use client";

import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

const FOCUSABLE = "a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex='-1'])";

export function usePhoneOverlayFocus(
  open: boolean,
  root: RefObject<HTMLElement | null>,
  onClose: () => void,
  returnFocus?: () => HTMLElement | null,
) {
  const callbacks = useRef({ onClose, returnFocus });
  useLayoutEffect(() => { callbacks.current = { onClose, returnFocus }; }, [onClose, returnFocus]);
  useEffect(() => {
    const panel = root.current;
    if (!open || !panel) return;
    const opener = document.activeElement instanceof HTMLElement && document.activeElement !== document.body && document.activeElement !== document.documentElement
      ? document.activeElement : null;
    let active = true;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const controls = () => [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)]
      .filter(element => element.getClientRects().length && !element.closest("[hidden],[inert]"));
    panel.focus({ preventScroll: true });
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        callbacks.current.onClose();
      } else if (event.key === "Tab") {
        const items = controls();
        const first = items[0] ?? panel;
        const last = items.at(-1) ?? panel;
        if (!panel.contains(document.activeElement) || document.activeElement === panel || (event.shiftKey ? document.activeElement === first : document.activeElement === last)) {
          event.preventDefault();
          (event.shiftKey ? last : first).focus();
        }
      }
    };
    const focusin = (event: FocusEvent) => {
      if (!panel.contains(event.target as Node)) panel.focus({ preventScroll: true });
    };
    const focusout = () => {
      queueMicrotask(() => {
        if (active && panel.isConnected && !panel.contains(document.activeElement)) panel.focus({ preventScroll: true });
      });
    };
    document.addEventListener("keydown", keydown);
    document.addEventListener("focusin", focusin);
    panel.addEventListener("focusout", focusout);
    return () => {
      active = false;
      document.removeEventListener("keydown", keydown);
      document.removeEventListener("focusin", focusin);
      panel.removeEventListener("focusout", focusout);
      document.body.style.overflow = previousOverflow;
      const target = opener?.isConnected ? opener : callbacks.current.returnFocus?.();
      target?.focus({ preventScroll: true });
    };
  }, [open, root]);
}
