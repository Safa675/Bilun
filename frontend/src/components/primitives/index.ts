/**
 * Primitives barrel export.
 *
 * Phase 1 surface — see `plans/frontend-rebuild.md`.
 *
 * Usage:
 *   import { Surface, Stat, Section, Chip, Eyebrow, DataTable } from "@/components/primitives";
 */

export { default as Surface } from "./Surface";
export type { SurfaceProps, SurfaceVariant } from "./Surface";

export { default as Stat } from "./Stat";
export type { StatProps, StatDisplay } from "./Stat";

export { default as Eyebrow } from "./Eyebrow";
export type { EyebrowProps, EyebrowTone } from "./Eyebrow";

export { default as Section } from "./Section";
export type { SectionProps } from "./Section";

export { default as Chip } from "./Chip";
export type { ChipProps, ChipVariant } from "./Chip";

export {
  default as DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHeader,
  DataTableHeaderCell,
  DataTableRow,
} from "./DataTable";
export type { DataTableProps } from "./DataTable";

export {
  default as Tabs,
  TabsRoot,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "./Tabs";
export type { TabsRootProps, TabsListProps, TabsTriggerProps } from "./Tabs";

export { default as Toolbar } from "./Toolbar";
export type { ToolbarProps } from "./Toolbar";
