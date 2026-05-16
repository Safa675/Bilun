import type { CSSProperties } from "react";

type RevealVariant = "fade" | "scale";

type RevealOptions = {
  baseDelayMs?: number;
  stepMs?: number;
  threshold?: number;
  rootMargin?: string;
  enabled?: boolean;
  revision?: number;
};

type RevealProps = {
  staggerClass: string;
  staggerStyle: CSSProperties;
  staggerAttrs: {
    "data-stagger-group": string;
    "data-stagger-index": number;
    "data-stagger-variant": RevealVariant;
  };
};

/**
 * No-op stagger hook — elements render instantly.
 * Interface preserved so callers don't need changes.
 */
export default function useStaggeredReveal(
  _count: number,
  _options: RevealOptions = {},
) {
  void _count;
  void _options;

  const getRevealProps = (index: number, _variant: RevealVariant = "fade"): RevealProps => ({
    staggerClass: "",
    staggerStyle: {},
    staggerAttrs: {
      "data-stagger-group": "",
      "data-stagger-index": index,
      "data-stagger-variant": _variant,
    },
  });

  return { getRevealProps };
}
