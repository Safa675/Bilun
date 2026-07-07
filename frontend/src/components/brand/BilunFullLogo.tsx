"use client";

import Image from "next/image";
import { type CSSProperties } from "react";
import fullLogo from "./assets/full.png";

export interface BilunFullLogoProps {
  /** Logo height in pixels. Defaults to 32. */
  size?: number;
  /** Accessible label. Defaults to "Bilun". */
  title?: string;
  className?: string;
  style?: CSSProperties;
}

/**
 * BILUN full logo (crest + wordmark) — the official artwork from
 * `Bilun Extras/Artwork/Logo/Full.png` (optimized to a palette PNG with alpha).
 * Renders at the given height, preserving aspect ratio. Used where the complete
 * lockup is wanted (login, design-system showcase).
 */
export default function BilunFullLogo({
  size = 32,
  title = "Bilun",
  className,
  style,
}: BilunFullLogoProps) {
  const ratio = fullLogo.width / fullLogo.height;
  return (
    <Image
      src={fullLogo}
      alt={title}
      width={Math.round(size * ratio)}
      height={size}
      className={className}
      style={style}
      priority
    />
  );
}
