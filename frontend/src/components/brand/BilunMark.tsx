"use client";

import Image from "next/image";
import { type CSSProperties } from "react";
import namelessMark from "./assets/nameless.png";

export interface BilunMarkProps {
  /** Mark height in pixels. Defaults to 24. */
  size?: number;
  /** Accessible label. When omitted, the mark is decorative. */
  title?: string;
  className?: string;
  style?: CSSProperties;
}

/**
 * BILUN mark — the official crest from `Bilun Extras/Artwork/Logo/Nameless.png`
 * (optimized to a palette PNG with alpha). Used standalone and as the glyph
 * inside `BilunWordmark`. Renders at the given height, preserving aspect ratio.
 */
export default function BilunMark({
  size = 24,
  title,
  className,
  style,
}: BilunMarkProps) {
  const ratio = namelessMark.width / namelessMark.height;
  return (
    <Image
      src={namelessMark}
      alt={title ?? ""}
      width={Math.round(size * ratio)}
      height={size}
      {...(title ? { role: "img" as const } : { "aria-hidden": true })}
      className={className}
      style={style}
      priority
    />
  );
}
