const ACCENT_HEX = "#10B981";
const ACCENT_DARK_HEX = "#059669";

const hexToRgb = (hex: string): [number, number, number] => {
  const m = hex.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
  if (!m) throw new Error(`Invalid hex: ${hex}`);
  return [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)];
};

const [R, G, B] = hexToRgb(ACCENT_HEX);

export const theme = {
  accent: ACCENT_HEX,
  accentDark: ACCENT_DARK_HEX,
  accentAlpha: (a: number) => `rgba(${R}, ${G}, ${B}, ${a})`,
} as const;
