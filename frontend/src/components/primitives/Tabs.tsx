/**
 * Tabs — single tab primitive wrapping `@radix-ui/react-tabs`.
 *
 * Replaces the legacy app-tab, home-nav-tab, and section tab visuals
 * (three different tab looks doing the same job).
 *
 * Two densities:
 * - `comfortable` (default) — page-level navigation
 * - `compact`              — inline subsections
 *
 * The active indicator is a 2px gold underline; inactive triggers
 * stay muted navy.
 */

"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/cn";

type Density = "comfortable" | "compact";

const DENSITY_LIST: Record<Density, string> = {
  comfortable: "gap-6",
  compact: "gap-4",
};

const DENSITY_TRIGGER: Record<Density, string> = {
  comfortable:
    "pb-2 text-sm font-medium",
  compact:
    "pb-1.5 text-xs font-medium",
};

export interface TabsRootProps extends ComponentProps<typeof RadixTabs.Root> {
  density?: Density;
}

export function TabsRoot({
  density = "comfortable",
  className,
  children,
  ...rest
}: TabsRootProps) {
  return (
    <RadixTabs.Root
      data-density={density}
      className={cn("flex flex-col gap-6", className)}
      {...rest}
    >
      {children}
    </RadixTabs.Root>
  );
}

export interface TabsListProps extends ComponentProps<typeof RadixTabs.List> {
  density?: Density;
}

export function TabsList({
  density = "comfortable",
  className,
  children,
  ...rest
}: TabsListProps) {
  return (
    <RadixTabs.List
      className={cn(
        "inline-flex border-b border-[var(--border-subtle)]",
        DENSITY_LIST[density],
        className,
      )}
      {...rest}
    >
      {children}
    </RadixTabs.List>
  );
}

export interface TabsTriggerProps extends ComponentProps<typeof RadixTabs.Trigger> {
  density?: Density;
  leading?: ReactNode;
}

export function TabsTrigger({
  density = "comfortable",
  leading,
  className,
  children,
  ...rest
}: TabsTriggerProps) {
  return (
    <RadixTabs.Trigger
      className={cn(
        "relative -mb-px inline-flex items-center gap-2 border-b-2 border-transparent text-[var(--text-muted)] outline-none transition-colors duration-[var(--dur)] ease-[var(--ease)]",
        "hover:text-[var(--text-primary)]",
        "data-[state=active]:border-[var(--gold)] data-[state=active]:text-[var(--text-primary)]",
        "focus-visible:ring-2 focus-visible:ring-[var(--gold)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface-base)] focus-visible:rounded-sm",
        DENSITY_TRIGGER[density],
        className,
      )}
      {...rest}
    >
      {leading ? <span className="inline-flex h-4 w-4 items-center justify-center">{leading}</span> : null}
      <span>{children}</span>
    </RadixTabs.Trigger>
  );
}

export const TabsContent = RadixTabs.Content;

const Tabs = {
  Root: TabsRoot,
  List: TabsList,
  Trigger: TabsTrigger,
  Content: TabsContent,
};

export default Tabs;
