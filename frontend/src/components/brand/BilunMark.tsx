/**
 * BILUN crescent mark.
 *
 * Traced from the investor deck cover (`BILUN_EN.pptx` slide 1 cover image).
 * Implemented as an SVG mask: a larger filled disc with a smaller offset
 * disc subtracted, producing the thick waxing-crescent shape used on the
 * cover slide.
 *
 * Uses `currentColor` so it inherits text color — navy on white surfaces,
 * cream on navy surfaces (when those exist later).
 */

import type { SVGProps } from "react";
import { useId } from "react";

export interface BilunMarkProps extends Omit<SVGProps<SVGSVGElement>, "ref"> {
  /** Pixel size for both width and height. Defaults to `1em`. */
  size?: number | string;
  /** Optional accessible title. When omitted, the SVG is treated as decorative. */
  title?: string;
}

export default function BilunMark({
  size,
  title,
  className,
  ...rest
}: BilunMarkProps) {
  const maskId = useId();
  const dimension = size ?? "1em";
  const ariaProps = title
    ? { role: "img" as const, "aria-label": title }
    : { "aria-hidden": true as const };

  return (
    <svg
      width={dimension}
      height={dimension}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...ariaProps}
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      <defs>
        <mask id={maskId} maskUnits="userSpaceOnUse">
          <rect width="64" height="64" fill="white" />
          <circle cx="44" cy="22" r="22" fill="black" />
        </mask>
      </defs>
      <circle cx="32" cy="32" r="28" fill="currentColor" mask={`url(#${maskId})`} />
    </svg>
  );
}
