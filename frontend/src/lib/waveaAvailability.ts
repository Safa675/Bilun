import type { WaveAEvidenceBlock } from "@/lib/domains/waveaEvidence";

/** The reason the backend gives while the extended evidence layer (Wave A) is not active in this build. */
export const WAVEA_CAPABILITY_UNAVAILABLE = "wavea_capability_unavailable";

/**
 * True when every given block says, by the backend's own reason code, that the
 * extended evidence layer is not active in this build. An absent block, a
 * block unavailable for another reason or a malformed one says nothing about
 * the build, so it never counts as "layer off".
 */
export function waveALayerOff(blocks: ReadonlyArray<WaveAEvidenceBlock | null | undefined>): boolean {
  return blocks.length > 0 && blocks.every(
    (block) => block?.available === false && block.unavailable_reason === WAVEA_CAPABILITY_UNAVAILABLE,
  );
}
