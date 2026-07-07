import { describe, it, expect } from "vitest";

import {
  computeStaggerDelay,
  isStaggerActive,
  _resolveStaggerOptions,
  STAGGER_DEFAULTS,
} from "./useStaggeredReveal";

describe("useStaggeredReveal — pure logic", () => {
  describe("computeStaggerDelay", () => {
    it("computes baseDelayMs + index * stepMs", () => {
      expect(computeStaggerDelay(0, 40, 140)).toBe(40);
      expect(computeStaggerDelay(1, 40, 140)).toBe(180);
      expect(computeStaggerDelay(3, 40, 140)).toBe(460);
    });

    it("falls back to defaults when base/step omitted", () => {
      // Defaults: baseDelayMs 40, stepMs 140.
      expect(computeStaggerDelay(0)).toBe(STAGGER_DEFAULTS.baseDelayMs);
      expect(computeStaggerDelay(1)).toBe(
        STAGGER_DEFAULTS.baseDelayMs + STAGGER_DEFAULTS.stepMs,
      );
    });
  });

  describe("isStaggerActive", () => {
    it("is inactive when enabled:false", () => {
      expect(isStaggerActive({ enabled: false }, false)).toBe(false);
    });

    it("is inactive when reduced-motion is requested", () => {
      expect(isStaggerActive({ enabled: true }, true)).toBe(false);
    });

    it("is active when enabled and no reduced motion", () => {
      expect(isStaggerActive({ enabled: true }, false)).toBe(true);
      expect(isStaggerActive({}, false)).toBe(true); // enabled defaults to true
    });
  });

  describe("_resolveStaggerOptions", () => {
    it("applies defaults for omitted fields", () => {
      const resolved = _resolveStaggerOptions({});
      expect(resolved).toEqual(STAGGER_DEFAULTS);
    });

    it("honors explicit overrides", () => {
      const resolved = _resolveStaggerOptions({
        baseDelayMs: 100,
        stepMs: 50,
        threshold: 0.3,
        enabled: false,
      });
      expect(resolved.baseDelayMs).toBe(100);
      expect(resolved.stepMs).toBe(50);
      expect(resolved.threshold).toBe(0.3);
      expect(resolved.enabled).toBe(false);
    });
  });
});
