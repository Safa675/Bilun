import { describe, expect, it } from "vitest";
import type { WaveAEvidenceBlock } from "@/lib/domains/waveaEvidence";
import { waveALayerOff } from "./waveaAvailability";

const off: WaveAEvidenceBlock = {
  available: false,
  unavailable_reason: "wavea_capability_unavailable",
  total_rows: null,
  rows: [],
  has_more: false,
};

describe("waveALayerOff", () => {
  it("is true only when every block carries the capability reason", () => {
    expect(waveALayerOff([off, { ...off }])).toBe(true);
  });

  it("is false for an absent block, another reason or an available block", () => {
    expect(waveALayerOff([])).toBe(false);
    expect(waveALayerOff([off, undefined])).toBe(false);
    expect(waveALayerOff([off, null])).toBe(false);
    expect(waveALayerOff([off, { ...off, unavailable_reason: "claim_context_unavailable" }])).toBe(false);
    expect(waveALayerOff([off, { ...off, available: true, unavailable_reason: null, total_rows: 0 }])).toBe(false);
  });
});
