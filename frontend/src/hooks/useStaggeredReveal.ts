import { useCallback, useEffect, useId, useMemo } from "react";
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

type ResolvedOptions = {
  baseDelayMs: number;
  stepMs: number;
  threshold: number;
  rootMargin: string;
  enabled: boolean;
};

const DEFAULTS: ResolvedOptions = {
  baseDelayMs: 40,
  stepMs: 140,
  threshold: 0.15,
  rootMargin: "0px",
  enabled: true,
};

function resolveOptions(options: RevealOptions): ResolvedOptions {
  return {
    baseDelayMs: options.baseDelayMs ?? DEFAULTS.baseDelayMs,
    stepMs: options.stepMs ?? DEFAULTS.stepMs,
    threshold: options.threshold ?? DEFAULTS.threshold,
    rootMargin: options.rootMargin ?? DEFAULTS.rootMargin,
    enabled: options.enabled ?? DEFAULTS.enabled,
  };
}

/**
 * Reports whether the user has requested reduced motion. Guarded for SSR
 * (no `window`) and for environments without `matchMedia`.
 */
function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Staggered enter-animation hook for list/card reveals.
 *
 * Each element receives a `.stagger-reveal` class plus a per-index
 * `--stagger-delay` custom property (`baseDelayMs + index * stepMs`), so the
 * group fades/rises in with a subtle cascade when it scrolls into view.
 *
 * An `IntersectionObserver` re-applies the per-index delay once the group
 * actually enters the viewport, so the stagger is timed to visibility rather
 * than to page load. It re-observes whenever `revision` changes (use this to
 * re-trigger the reveal after the list content swaps).
 *
 * Respects `prefers-reduced-motion: reduce` and an `enabled: false` opt-out:
 * in either case the hook becomes a no-op and elements render instantly. The
 * interface is identical to the previous no-op stub so existing callers need
 * no changes.
 */
export default function useStaggeredReveal(count: number, options: RevealOptions = {}) {
  const resolved = resolveOptions(options);
  const { baseDelayMs, stepMs, threshold, rootMargin, enabled } = resolved;
  const revision = options.revision;
  const groupId = useId();

  // `useEffect` does not run during SSR / static-markup rendering, so the
  // active/no-op decision is derived synchronously here and the per-index
  // delay is encoded directly in `staggerStyle`. The observer below only
  // matters in a real browser.
  const active = enabled && !prefersReducedMotion();

  useEffect(() => {
    if (!enabled) return;
    if (typeof window === "undefined" || typeof IntersectionObserver === "undefined") {
      return;
    }
    if (prefersReducedMotion()) return;

    const selector = `[data-stagger-group="${groupId}"]`;
    const nodes = Array.from(document.querySelectorAll<HTMLElement>(selector));
    if (nodes.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const el = entry.target as HTMLElement;
            const idxAttr = el.getAttribute("data-stagger-index");
            const index = idxAttr == null ? 0 : Number(idxAttr);
            if (!Number.isNaN(index)) {
              el.style.setProperty("--stagger-delay", `${baseDelayMs + index * stepMs}ms`);
            }
            observer.unobserve(el);
          }
        }
      },
      { threshold, rootMargin },
    );

    for (const node of nodes) observer.observe(node);

    return () => observer.disconnect();
  }, [enabled, threshold, rootMargin, groupId, baseDelayMs, stepMs, count, revision]);

  const getRevealProps = useCallback(
    (index: number, variant: RevealVariant = "fade"): RevealProps => {
      if (!active) {
        return {
          staggerClass: "",
          staggerStyle: {},
          staggerAttrs: {
            "data-stagger-group": "",
            "data-stagger-index": index,
            "data-stagger-variant": variant,
          },
        };
      }

      const delay = baseDelayMs + index * stepMs;

      return {
        staggerClass: "stagger-reveal",
        staggerStyle: { "--stagger-delay": `${delay}ms` } as CSSProperties,
        staggerAttrs: {
          "data-stagger-group": groupId,
          "data-stagger-index": index,
          "data-stagger-variant": variant,
        },
      };
    },
    [active, groupId, baseDelayMs, stepMs],
  );

  return useMemo(() => ({ getRevealProps }), [getRevealProps]);
}
