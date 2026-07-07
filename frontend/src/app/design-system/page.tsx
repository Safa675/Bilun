"use client";

/**
 * Design system verification sandbox.
 * Visit directly at `/design-system`.
 */

import BilunFullLogo from "@/components/brand/BilunFullLogo";
import BilunMark from "@/components/brand/BilunMark";
import {
  Chip,
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHeader,
  DataTableHeaderCell,
  DataTableRow,
  Eyebrow,
  Section,
  Stat,
  Surface,
  TabsContent,
  TabsList,
  TabsRoot,
  TabsTrigger,
  Toolbar,
} from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

const PALETTE_TOKENS = [
  { key: "primaryNavy", token: "--text-primary", value: "#1A2638" },
  { key: "secondaryNavy", token: "--text-secondary", value: "#3A4456" },
  { key: "mutedSlate", token: "--text-muted", value: "#8590A4" },
  { key: "disabled", token: "--text-disabled", value: "#98A0AC" },
  { key: "surfaceBase", token: "--surface-base", value: "#FFFFFF" },
  { key: "surfaceSoft", token: "--surface-soft", value: "#E5E2DA" },
  { key: "surfaceTint", token: "--surface-tint", value: "#EFEAD8" },
  { key: "gold", token: "--gold", value: "#9C7A3E" },
  { key: "goldHover", token: "--gold-hover", value: "#8B6A33" },
  { key: "goldLight", token: "--gold-light", value: "#C9B27E" },
  { key: "success", token: "--success", value: "#2F6E4E" },
  { key: "warning", token: "--warning", value: "#B45309" },
  { key: "danger", token: "--danger", value: "#B91C1C" },
] as const;

const SURFACE_VARIANTS = ["base", "soft", "tint", "inset", "raised"] as const;

export default function DesignSandbox() {
  const t = useT();

  return (
    <main className="min-h-screen bg-[var(--surface-base)] px-6 py-10">
      <div className="mx-auto max-w-6xl space-y-10">
        <header className="flex items-end justify-between gap-6">
          <div className="space-y-3">
            <Eyebrow tone="gold">{t("designSystem.eyebrow")}</Eyebrow>
            <h1 className="font-[var(--font-display)] text-4xl font-medium tracking-tight text-[var(--text-primary)]">
              {t("designSystem.title")} <em className="text-[var(--gold)]">{t("designSystem.titleAccent")}</em>
            </h1>
            <p className="max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)]">
              {t("designSystem.intro")}
            </p>
          </div>
          <BilunFullLogo size={28} />
        </header>

        <Section
          title={t("designSystem.palette.title")}
          titleAccent={t("designSystem.palette.titleAccent")}
          description={t("designSystem.palette.description")}
        >
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {PALETTE_TOKENS.map((entry) => (
              <div
                key={entry.token}
                className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)]"
              >
                <div
                  className="h-14 w-full rounded-t-[var(--r-md)] border-b border-[var(--border-subtle)]"
                  style={{ background: entry.value }}
                />
                <div className="px-3 py-2">
                  <p className="text-xs font-semibold text-[var(--text-primary)]">
                    {t(`designSystem.paletteLabels.${entry.key}`)}
                  </p>
                  <p className="font-[var(--font-mono)] text-[0.7rem] text-[var(--text-muted)]">
                    {entry.token} · {entry.value}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section
          title={t("designSystem.typography.title")}
          titleAccent={t("designSystem.typography.titleAccent")}
          description={t("designSystem.typography.description")}
        >
          <div className="space-y-3">
            <p className="font-[var(--font-display)] text-5xl tracking-tight text-[var(--text-primary)]">
              {t("designSystem.typography.heroRecovered")}{" "}
              <em className="text-[var(--gold)]">{t("designSystem.typography.heroAmount")}</em>{" "}
              {t("designSystem.typography.heroCurrency")}
            </p>
            <p className="font-[var(--font-display)] text-3xl text-[var(--text-primary)]">
              {t("designSystem.typography.heroHospitals")}
            </p>
            <p className="font-[var(--font-display)] text-2xl italic text-[var(--gold)]">
              {t("designSystem.typography.heroReimbursement")}
            </p>
            <p className="text-base text-[var(--text-primary)]">{t("designSystem.typography.bodySample")}</p>
            <p className="text-sm text-[var(--text-secondary)]">{t("designSystem.typography.secondarySample")}</p>
            <p className="text-xs text-[var(--text-muted)]">{t("designSystem.typography.mutedSample")}</p>
            <p className="tabular-nums lining-nums font-medium text-[var(--text-primary)]">
              {t("designSystem.typography.numericSample")}
            </p>
          </div>
        </Section>

        <Section title={t("designSystem.surface.title")} titleAccent={t("designSystem.surface.titleAccent")}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {SURFACE_VARIANTS.map((variant) => (
              <Surface key={variant} variant={variant}>
                <Eyebrow>{variant}</Eyebrow>
                <p className="mt-2 text-sm text-[var(--text-secondary)]">
                  {t("designSystem.surface.variantDescription", { variant })}
                </p>
              </Surface>
            ))}
          </div>
        </Section>

        <Section title={t("designSystem.stat.title")} titleAccent={t("designSystem.stat.titleAccent")} variant="soft">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label={t("designSystem.stat.maxReimbursement")}
              value={t("designSystem.stat.maxReimbursementValue")}
              display="gold"
              hint={t("designSystem.stat.maxReimbursementHint")}
            />
            <Stat
              label={t("designSystem.stat.recommendedActions")}
              value={t("designSystem.stat.recommendedActionsValue")}
              delta={t("designSystem.stat.recommendedActionsDelta")}
            />
            <Stat label={t("designSystem.stat.priorityTier")} value={t("designSystem.stat.priorityTierValue")} />
            <Stat
              label={t("designSystem.stat.cohortPatients")}
              value={t("designSystem.stat.cohortPatientsValue")}
              delta={t("designSystem.stat.cohortPatientsDelta")}
            />
          </div>
        </Section>

        <Section title={t("designSystem.chip.title")} titleAccent={t("designSystem.chip.titleAccent")}>
          <div className="flex flex-wrap gap-2">
            <Chip variant="neutral">{t("designSystem.chip.neutral")}</Chip>
            <Chip variant="success">{t("designSystem.chip.exact")}</Chip>
            <Chip variant="warning">{t("designSystem.chip.partial")}</Chip>
            <Chip variant="danger">{t("designSystem.chip.unavailable")}</Chip>
            <Chip variant="gold">{t("designSystem.chip.gold")}</Chip>
            <Chip variant="outline">{t("designSystem.chip.outline")}</Chip>
          </div>
        </Section>

        <Section title={t("designSystem.tabs.title")} titleAccent={t("designSystem.tabs.titleAccent")}>
          <TabsRoot defaultValue="patient">
            <TabsList>
              <TabsTrigger value="patient">{t("designSystem.tabs.patient")}</TabsTrigger>
              <TabsTrigger value="tools">{t("designSystem.tabs.tools")}</TabsTrigger>
              <TabsTrigger value="opt">{t("designSystem.tabs.optimizer")}</TabsTrigger>
            </TabsList>
            <TabsContent value="patient" className="pt-4 text-sm text-[var(--text-secondary)]">
              {t("designSystem.tabs.contentFor", { tab: "patient" })}
            </TabsContent>
            <TabsContent value="tools" className="pt-4 text-sm text-[var(--text-secondary)]">
              {t("designSystem.tabs.contentFor", { tab: "tools" })}
            </TabsContent>
            <TabsContent value="opt" className="pt-4 text-sm text-[var(--text-secondary)]">
              {t("designSystem.tabs.contentFor", { tab: "opt" })}
            </TabsContent>
          </TabsRoot>
        </Section>

        <Section title={t("designSystem.toolbar.title")} titleAccent={t("designSystem.toolbar.titleAccent")}>
          <Toolbar
            leading={
              <input
                className="rounded-[var(--r-sm)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-1.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--gold)] focus:outline-none"
                placeholder={t("designSystem.toolbar.searchPlaceholder")}
              />
            }
            trailing={
              <>
                <Chip variant="outline">{t("designSystem.toolbar.matchCount")}</Chip>
                <button className="rounded-[var(--r-sm)] bg-[var(--gold)] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[var(--gold-hover)]">
                  {t("designSystem.toolbar.apply")}
                </button>
              </>
            }
          >
            <select className="rounded-[var(--r-sm)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-2 py-1.5 text-sm text-[var(--text-primary)]">
              <option>{t("designSystem.toolbar.allCategories")}</option>
              <option>{t("designSystem.toolbar.materials")}</option>
              <option>{t("designSystem.toolbar.labs")}</option>
            </select>
          </Toolbar>
        </Section>

        <Section title={t("designSystem.dataTable.title")} titleAccent={t("designSystem.dataTable.titleAccent")}>
          <DataTable minWidth={640}>
            <DataTableHeader>
              <DataTableRow>
                <DataTableHeaderCell>{t("designSystem.dataTable.patient")}</DataTableHeaderCell>
                <DataTableHeaderCell>{t("designSystem.dataTable.claim")}</DataTableHeaderCell>
                <DataTableHeaderCell>{t("designSystem.dataTable.status")}</DataTableHeaderCell>
                <DataTableHeaderCell numeric>{t("designSystem.dataTable.billed")}</DataTableHeaderCell>
                <DataTableHeaderCell numeric>{t("designSystem.dataTable.recovered")}</DataTableHeaderCell>
              </DataTableRow>
            </DataTableHeader>
            <DataTableBody>
              <DataTableRow>
                <DataTableCell>SENTETIK-0001</DataTableCell>
                <DataTableCell>F-001-021</DataTableCell>
                <DataTableCell>
                  <Chip variant="success">{t("designSystem.chip.exact")}</Chip>
                </DataTableCell>
                <DataTableCell numeric>12 480,00</DataTableCell>
                <DataTableCell numeric>1 240,00</DataTableCell>
              </DataTableRow>
              <DataTableRow>
                <DataTableCell>SENTETIK-0007</DataTableCell>
                <DataTableCell>F-007-008</DataTableCell>
                <DataTableCell>
                  <Chip variant="warning">{t("designSystem.chip.partial")}</Chip>
                </DataTableCell>
                <DataTableCell numeric>4 992,50</DataTableCell>
                <DataTableCell numeric>820,00</DataTableCell>
              </DataTableRow>
              <DataTableRow>
                <DataTableCell>SENTETIK-0019</DataTableCell>
                <DataTableCell>F-019-002</DataTableCell>
                <DataTableCell>
                  <Chip variant="danger">{t("designSystem.chip.unavailable")}</Chip>
                </DataTableCell>
                <DataTableCell numeric>—</DataTableCell>
                <DataTableCell numeric>—</DataTableCell>
              </DataTableRow>
            </DataTableBody>
          </DataTable>
        </Section>

        <Section title={t("designSystem.brand.title")} titleAccent={t("designSystem.brand.titleAccent")}>
          <div className="flex flex-wrap items-center gap-8 text-[var(--text-primary)]">
            <BilunMark size={48} title={t("designSystem.brand.markTitle")} />
            <BilunFullLogo size={40} />
            <BilunFullLogo size={28} />
          </div>
        </Section>

        <Section
          title={t("designSystem.focus.title")}
          titleAccent={t("designSystem.focus.titleAccent")}
          description={t("designSystem.focus.description")}
        >
          <div className="flex flex-wrap items-center gap-3">
            <input
              className="rounded-[var(--r-sm)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--gold)] focus:outline-none focus:ring-2 focus:ring-[var(--gold)]/30"
              placeholder={t("designSystem.focus.placeholder")}
            />
            <button
              className="rounded-[var(--r-sm)] bg-[var(--gold)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--gold-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--gold)]/40 focus:ring-offset-2 focus:ring-offset-[var(--surface-base)]"
            >
              {t("designSystem.focus.primary")}
            </button>
            <button
              className="rounded-[var(--r-sm)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:border-[var(--gold)] focus:outline-none focus:ring-2 focus:ring-[var(--gold)]/40"
            >
              {t("designSystem.focus.secondary")}
            </button>
          </div>
        </Section>
      </div>
    </main>
  );
}
