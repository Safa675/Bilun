/**
 * BILUN wordmark — official horizontal logo (crest + "Bilun" type).
 *
 * Source: `Bilun Extras/Artwork/Logo/Full.png` → `public/brand/full.png`.
 * Use `withMark={false}` for text-only fallback (e.g. constrained layouts).
 */

import { type CSSProperties, type HTMLAttributes } from "react";

export interface BilunWordmarkProps extends HTMLAttributes<HTMLAnchorElement> {
  /** Accessible label / alt text. Defaults to "Bilun". */
  label?: string;
  /** When false, render the wordmark text without the logo image. */
  withMark?: boolean;
  /** Optional `href`. When set, renders an `<a>`; otherwise renders a `<span>`. */
  href?: string;
  /** Logo height in pixels. */
  size?: number;
}

const LOGO_SRC = "/brand/full.png";
/** Intrinsic aspect ratio of `Full.png` (2836×1504). */
const LOGO_ASPECT = 2836 / 1504;

const textStyle = (size: number): CSSProperties => ({
  color: "var(--text-primary)",
  fontFamily: "var(--font-display)",
  fontWeight: 500,
  fontSize: `${size * 0.92}px`,
  letterSpacing: "0.01em",
  lineHeight: 1,
});

export default function BilunWordmark({
  label = "Bilun",
  withMark = true,
  href,
  size = 24,
  className,
  style,
  ...rest
}: BilunWordmarkProps) {
  const mergedStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    textDecoration: "none",
    lineHeight: 0,
    ...style,
  };

  const content = withMark ? (
    // eslint-disable-next-line @next/next/no-img-element -- static brand asset; no next/image in app yet
    <img
      src={LOGO_SRC}
      alt={label}
      width={Math.round(size * LOGO_ASPECT)}
      height={size}
      style={{ display: "block", height: size, width: "auto" }}
    />
  ) : (
    <span style={textStyle(size)}>{label}</span>
  );

  if (href) {
    return (
      <a href={href} className={className} style={mergedStyle} {...rest}>
        {content}
      </a>
    );
  }

  return (
    <span
      className={className}
      style={mergedStyle}
      {...(rest as HTMLAttributes<HTMLSpanElement>)}
    >
      {content}
    </span>
  );
}
