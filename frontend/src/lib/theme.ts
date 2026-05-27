/**
 * BILUN runtime theme values.
 *
 * Mirrors the locked palette in `frontend/src/app/globals.css` (also
 * documented in `plans/frontend-rebuild.md`). Sourced from the investor
 * deck `BILUN_EN.pptx`: navy + antique gold + cream + white.
 *
 * Use the CSS tokens (`var(--gold)`, `var(--text-primary)`, …) wherever
 * possible. This object exists for the few places where colors must be
 * passed to non-CSS consumers (Recharts, canvas, inline SVG).
 */

const NAVY_HEX = "#1A2638";
const GOLD_HEX = "#9C7A3E";
const GOLD_HOVER_HEX = "#8B6A33";

const hexToRgb = (hex: string): [number, number, number] => {
  const m = hex.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
  if (!m) throw new Error(`Invalid hex: ${hex}`);
  return [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)];
};

const [GR, GG, GB] = hexToRgb(GOLD_HEX);

export const theme = {
  textPrimary: NAVY_HEX,
  textSecondary: "#3A4456",
  textMuted: "#8590A4",
  textDisabled: "#98A0AC",
  surfaceBase: "#FFFFFF",
  surfaceSoft: "#E5E2DA",
  surfaceTint: "#EFEAD8",
  borderSubtle: "#E5E2DA",
  gold: GOLD_HEX,
  goldHover: GOLD_HOVER_HEX,
  goldPressed: "#735628",
  goldLight: "#C9B27E",
  success: "#2F6E4E",
  warning: "#B45309",
  danger: "#B91C1C",
  info: NAVY_HEX,
  /** Gold @ alpha — for legacy code that reaches for `accentAlpha`. */
  accentAlpha: (a: number) => `rgba(${GR}, ${GG}, ${GB}, ${a})`,
  /* ── Legacy aliases kept until Phase 5 finishes ───────────────── */
  /** @deprecated Use `theme.gold`. Kept for Phase 1/2 transition. */
  accent: GOLD_HEX,
  /** @deprecated Use `theme.goldHover`. Kept for Phase 1/2 transition. */
  accentDark: GOLD_HOVER_HEX,
} as const;
