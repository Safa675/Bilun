/**
 * BILUN wordmark — crescent mark + "BILUN" set in Fraunces, navy.
 *
 * Companion to `BilunMark`. The `Bilun` wordmark on the deck cover is set
 * in Georgia; the web equivalent uses our display serif (`--font-display`,
 * Fraunces) at regular weight, navy on white.
 */

import { type CSSProperties, type HTMLAttributes } from "react";
import BilunMark from "./BilunMark";

export interface BilunWordmarkProps extends HTMLAttributes<HTMLAnchorElement> {
  /** Wordmark text. Defaults to "BILUN". */
  label?: string;
  /** When false, render the wordmark without the crescent mark. */
  withMark?: boolean;
  /** Optional `href`. When set, renders an `<a>`; otherwise renders a `<span>`. */
  href?: string;
  /** Mark size in pixels. */
  size?: number;
}

const baseStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "0.55em",
  color: "var(--text-primary)",
  fontFamily: "var(--font-display)",
  fontWeight: 500,
  letterSpacing: "0.01em",
  textDecoration: "none",
  lineHeight: 1,
};

export default function BilunWordmark({
  label = "BILUN",
  withMark = true,
  href,
  size = 24,
  className,
  style,
  ...rest
}: BilunWordmarkProps) {
  const mergedStyle: CSSProperties = {
    ...baseStyle,
    fontSize: `${size}px`,
    ...style,
  };

  const content = (
    <>
      {withMark ? <BilunMark size={size} title="BILUN" /> : null}
      <span style={{ fontSize: `${size * 0.92}px` }}>{label}</span>
    </>
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
