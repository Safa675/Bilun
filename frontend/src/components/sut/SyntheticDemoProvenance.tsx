"use client";

import type { SUTDataSourceCarrier, SUTDataSourceMetadata } from "@/lib/domains/sut";

export const SYNTHETIC_DEMO_COPY =
  "Synthetic demo claims — SUT rule calculations are exact for this generated claim-line fixture.";

type ProvenanceInput =
  | SUTDataSourceMetadata
  | SUTDataSourceCarrier
  | null
  | undefined;

export function getSutDataSource(input: ProvenanceInput): SUTDataSourceMetadata | null {
  if (!input) return null;
  if ("mode" in input) return input;
  return input.data_source ?? input.dataSource ?? null;
}

export function isSyntheticDemoDataSource(
  input: ProvenanceInput,
): input is SUTDataSourceMetadata | SUTDataSourceCarrier {
  const dataSource = getSutDataSource(input);
  return dataSource?.mode === "synthetic_demo" || dataSource?.is_synthetic === true;
}

function firstSyntheticDataSource(inputs: ProvenanceInput[]): SUTDataSourceMetadata | null {
  for (const input of inputs) {
    const dataSource = getSutDataSource(input);
    if (isSyntheticDemoDataSource(dataSource)) return dataSource;
  }
  return null;
}

export function SyntheticDemoProvenance({
  dataSource,
  dataSources,
  compact = false,
  className = "",
}: {
  dataSource?: ProvenanceInput;
  dataSources?: ProvenanceInput[];
  compact?: boolean;
  className?: string;
}) {
  const syntheticDataSource = firstSyntheticDataSource([
    dataSource,
    ...(dataSources ?? []),
  ]);
  if (!syntheticDataSource) return null;

  const notice = syntheticDataSource.notice?.trim() || SYNTHETIC_DEMO_COPY;
  const classes = [
    "sut-synthetic-provenance",
    compact ? "sut-synthetic-provenance-compact" : "",
    className,
  ].filter(Boolean).join(" ");

  return (
    <div className={classes} role="note" aria-label="Synthetic SUT demo provenance">
      <span className="sut-synthetic-provenance-label">Synthetic demo claims</span>
      <span className="sut-synthetic-provenance-copy">
        {notice.includes("Synthetic demo claims") ? notice : SYNTHETIC_DEMO_COPY}
      </span>
    </div>
  );
}
