import { describe, it, expect, vi, afterEach } from "vitest";

import useStaggeredReveal from "./useStaggeredReveal";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function makeMatchMedia(matches: boolean) {
  return (query: string): MediaQueryList =>
    ({
      matches: query === REDUCED_MOTION_QUERY ? matches : false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}

/**
 * Build a `window` object exposing only what the hook touches (`matchMedia`)
 * so we can exercise the reduced-motion path under the node test environment,
 * which has no global `window` by default.
 */
function stubWindow(matches: boolean) {
  const win = { matchMedia: makeMatchMedia(matches) };
  vi.stubGlobal("window", win);
  return win;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useStaggeredReveal", () => {
  it("is a no-op when enabled:false (renders instantly)", () => {
    // No window in node env → reduced-motion guard is a safe no-op here, and
    // disabled opts short-circuit before any browser API is touched.
    const { getRevealProps } = useStaggeredReveal(3, { enabled: false });

    const props = getRevealProps(0);

    expect(props.staggerClass).toBe("");
    expect(props.staggerStyle).toEqual({});
    expect(props.staggerAttrs["data-stagger-index"]).toBe(0);
  });

  it("is a no-op when prefers-reduced-motion: reduce", () => {
    stubWindow(true); // reduced motion requested

    const { getRevealProps } = useStaggeredReveal(3, { enabled: true });
    const props = getRevealProps(1, "scale");

    expect(props.staggerClass).toBe("");
    expect(props.staggerStyle).toEqual({});
    // variant is still surfaced for callers that read it.
    expect(props.staggerAttrs["data-stagger-variant"]).toBe("scale");
    expect(props.staggerAttrs["data-stagger-index"]).toBe(1);
  });

  it("returns the stagger class + --stagger-delay when enabled and no reduced motion", () => {
    stubWindow(false); // reduced motion NOT requested

    const { getRevealProps } = useStaggeredReveal(
      3,
      { baseDelayMs: 40, stepMs: 140 },
    );

    const first = getRevealProps(0);
    const second = getRevealProps(1);

    expect(first.staggerClass).toBe("stagger-reveal");
    // Per-index delay = baseDelayMs + index * stepMs.
    expect(first.staggerStyle).toHaveProperty("--stagger-delay", "40ms");
    expect(second.staggerStyle).toHaveProperty("--stagger-delay", "180ms");

    // Group attrs are populated so the IntersectionObserver can target the set.
    expect(first.staggerAttrs["data-stagger-group"]).toBeTruthy();
    expect(second.staggerAttrs["data-stagger-group"]).toBe(
      first.staggerAttrs["data-stagger-group"],
    );
    expect(first.staggerAttrs["data-stagger-index"]).toBe(0);
    expect(second.staggerAttrs["data-stagger-index"]).toBe(1);
  });

  it("preserves the default delay math when options are omitted", () => {
    stubWindow(false);

    const { getRevealProps } = useStaggeredReveal(2);
    const props = getRevealProps(0);

    expect(props.staggerClass).toBe("stagger-reveal");
    // Defaults: baseDelayMs 40, stepMs 140 → index 0 is 40ms.
    expect(props.staggerStyle).toHaveProperty("--stagger-delay", "40ms");
  });
});
