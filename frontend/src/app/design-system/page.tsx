/**
 * Design system verification sandbox.
 *
 * Renders every Phase 1 primitive in every variant against the locked
 * BILUN palette. Used only for visual smoke-testing the design system
 * before existing pages are reskinned (Phase 2+).
 *
 * NOT linked from product navigation. Visit directly at `/design-system`.
 */

import BilunMark from "@/components/brand/BilunMark";
import BilunWordmark from "@/components/brand/BilunWordmark";
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

const PALETTE = [
  { label: "Primary navy", token: "--text-primary", value: "#1A2638" },
  { label: "Secondary navy", token: "--text-secondary", value: "#3A4456" },
  { label: "Muted slate", token: "--text-muted", value: "#8590A4" },
  { label: "Disabled", token: "--text-disabled", value: "#98A0AC" },
  { label: "Surface base", token: "--surface-base", value: "#FFFFFF" },
  { label: "Surface soft", token: "--surface-soft", value: "#E5E2DA" },
  { label: "Surface tint", token: "--surface-tint", value: "#EFEAD8" },
  { label: "Gold", token: "--gold", value: "#9C7A3E" },
  { label: "Gold hover", token: "--gold-hover", value: "#8B6A33" },
  { label: "Gold light", token: "--gold-light", value: "#C9B27E" },
  { label: "Success", token: "--success", value: "#2F6E4E" },
  { label: "Warning", token: "--warning", value: "#B45309" },
  { label: "Danger", token: "--danger", value: "#B91C1C" },
];

export default function DesignSandbox() {
  return (
    <main className="min-h-screen bg-[var(--surface-base)] px-6 py-10">
      <div className="mx-auto max-w-6xl space-y-10">
        <header className="flex items-end justify-between gap-6">
          <div className="space-y-3">
            <Eyebrow tone="gold">Design system · Phase 1</Eyebrow>
            <h1 className="font-[var(--font-display)] text-4xl font-medium tracking-tight text-[var(--text-primary)]">
              BILUN <em className="text-[var(--gold)]">primitives</em>
            </h1>
            <p className="max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)]">
              Locked palette and typography from{" "}
              <code className="rounded bg-[var(--surface-soft)] px-1.5 py-0.5 font-[var(--font-mono)] text-xs">
                BILUN_EN.pptx
              </code>{" "}
              — verify renderer fidelity before reskinning real pages.
            </p>
          </div>
          <BilunWordmark size={28} />
        </header>

        {/* Palette */}
        <Section
          title="Palette"
          titleAccent="tokens"
          description="Every color used in the system. Status (success/warning/danger) is intentionally separate from brand (gold)."
        >
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {PALETTE.map((entry) => (
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
                    {entry.label}
                  </p>
                  <p className="font-[var(--font-mono)] text-[0.7rem] text-[var(--text-muted)]">
                    {entry.token} · {entry.value}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Type */}
        <Section
          title="Typography"
          titleAccent="Fraunces × Inter"
          description="Display serif Fraunces with italic-gold emphasis. Body sans Inter with tabular numerics for tables."
        >
          <div className="space-y-3">
            <p className="font-[var(--font-display)] text-5xl tracking-tight text-[var(--text-primary)]">
              Recovered <em className="text-[var(--gold)]">2 412 850</em> TL
            </p>
            <p className="font-[var(--font-display)] text-3xl text-[var(--text-primary)]">
              For Turkish Hospitals
            </p>
            <p className="font-[var(--font-display)] text-2xl italic text-[var(--gold)]">
              Reimbursement
            </p>
            <p className="text-base text-[var(--text-primary)]">
              Inter body — the quick brown fox jumps over the lazy dog 0123456789
            </p>
            <p className="text-sm text-[var(--text-secondary)]">
              Inter secondary — supporting copy stays in `--text-secondary`.
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              Inter muted — captions and axis labels stay in `--text-muted`.
            </p>
            <p className="tabular-nums lining-nums font-medium text-[var(--text-primary)]">
              1,234,567.89 · 0.001 · 999,999 · 42.0%
            </p>
          </div>
        </Section>

        {/* Surface variants */}
        <Section title="Surface" titleAccent="variants">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {(["base", "soft", "tint", "inset", "raised"] as const).map((variant) => (
              <Surface key={variant} variant={variant}>
                <Eyebrow>{variant}</Eyebrow>
                <p className="mt-2 text-sm text-[var(--text-secondary)]">
                  Surface variant `{variant}`.
                </p>
              </Surface>
            ))}
          </div>
        </Section>

        {/* Stats */}
        <Section title="Stat" titleAccent="primitive" variant="soft">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="Rule-calculated opportunity"
              value="2 412 850 TL"
              display="gold"
              hint="Italic gold treatment — one per page"
            />
            <Stat label="Recommended actions" value="34" delta="+6" />
            <Stat label="Priority tier" value="High" />
            <Stat label="Cohort patients" value="1 248" delta="+12%" />
          </div>
        </Section>

        {/* Chip */}
        <Section title="Chip" titleAccent="variants">
          <div className="flex flex-wrap gap-2">
            <Chip variant="neutral">Neutral</Chip>
            <Chip variant="success">Exact</Chip>
            <Chip variant="warning">Partial</Chip>
            <Chip variant="danger">Unavailable</Chip>
            <Chip variant="gold">Gold</Chip>
            <Chip variant="outline">Outline</Chip>
          </div>
        </Section>

        {/* Tabs */}
        <Section title="Tabs" titleAccent="primitive">
          <TabsRoot defaultValue="patient">
            <TabsList>
              <TabsTrigger value="patient">Patient SUT</TabsTrigger>
              <TabsTrigger value="tools">Reference Tools</TabsTrigger>
              <TabsTrigger value="opt">Optimizer</TabsTrigger>
            </TabsList>
            <TabsContent value="patient" className="pt-4 text-sm text-[var(--text-secondary)]">
              Active tab content area for `patient`.
            </TabsContent>
            <TabsContent value="tools" className="pt-4 text-sm text-[var(--text-secondary)]">
              Active tab content area for `tools`.
            </TabsContent>
            <TabsContent value="opt" className="pt-4 text-sm text-[var(--text-secondary)]">
              Active tab content area for `opt`.
            </TabsContent>
          </TabsRoot>
        </Section>

        {/* Toolbar */}
        <Section title="Toolbar" titleAccent="primitive">
          <Toolbar
            leading={
              <input
                className="rounded-[var(--r-sm)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-1.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--gold)] focus:outline-none"
                placeholder="Search claims…"
              />
            }
            trailing={
              <>
                <Chip variant="outline">120 of 4,328</Chip>
                <button className="rounded-[var(--r-sm)] bg-[var(--gold)] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[var(--gold-hover)]">
                  Apply
                </button>
              </>
            }
          >
            <select className="rounded-[var(--r-sm)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-2 py-1.5 text-sm text-[var(--text-primary)]">
              <option>All categories</option>
              <option>Materials</option>
              <option>Labs</option>
            </select>
          </Toolbar>
        </Section>

        {/* DataTable */}
        <Section title="DataTable" titleAccent="primitive">
          <DataTable minWidth={640}>
            <DataTableHeader>
              <DataTableRow>
                <DataTableHeaderCell>Patient</DataTableHeaderCell>
                <DataTableHeaderCell>Claim</DataTableHeaderCell>
                <DataTableHeaderCell>Status</DataTableHeaderCell>
                <DataTableHeaderCell numeric>Billed</DataTableHeaderCell>
                <DataTableHeaderCell numeric>Recovered</DataTableHeaderCell>
              </DataTableRow>
            </DataTableHeader>
            <DataTableBody>
              <DataTableRow>
                <DataTableCell>SENTETIK-0001</DataTableCell>
                <DataTableCell>F-001-021</DataTableCell>
                <DataTableCell>
                  <Chip variant="success">Exact</Chip>
                </DataTableCell>
                <DataTableCell numeric>12 480,00</DataTableCell>
                <DataTableCell numeric>1 240,00</DataTableCell>
              </DataTableRow>
              <DataTableRow>
                <DataTableCell>SENTETIK-0007</DataTableCell>
                <DataTableCell>F-007-008</DataTableCell>
                <DataTableCell>
                  <Chip variant="warning">Partial</Chip>
                </DataTableCell>
                <DataTableCell numeric>4 992,50</DataTableCell>
                <DataTableCell numeric>820,00</DataTableCell>
              </DataTableRow>
              <DataTableRow>
                <DataTableCell>SENTETIK-0019</DataTableCell>
                <DataTableCell>F-019-002</DataTableCell>
                <DataTableCell>
                  <Chip variant="danger">Unavailable</Chip>
                </DataTableCell>
                <DataTableCell numeric>—</DataTableCell>
                <DataTableCell numeric>—</DataTableCell>
              </DataTableRow>
            </DataTableBody>
          </DataTable>
        </Section>

        {/* Brand */}
        <Section title="Brand" titleAccent="mark">
          <div className="flex flex-wrap items-center gap-8 text-[var(--text-primary)]">
            <BilunMark size={48} title="BILUN mark" />
            <BilunWordmark size={32} />
            <BilunWordmark size={20} />
            <div className="rounded-[var(--r-lg)] bg-[var(--text-primary)] p-4 text-white">
              <BilunWordmark size={28} style={{ color: "white" }} />
            </div>
          </div>
        </Section>

        {/* Focus demo */}
        <Section
          title="Focus state"
          titleAccent="audit"
          description="Tab through the inputs and buttons — gold ring should appear on every interactive element."
        >
          <div className="flex flex-wrap items-center gap-3">
            <input
              className="rounded-[var(--r-sm)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--gold)] focus:outline-none focus:ring-2 focus:ring-[var(--gold)]/30"
              placeholder="Focus me"
            />
            <button
              className="rounded-[var(--r-sm)] bg-[var(--gold)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--gold-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--gold)]/40 focus:ring-offset-2 focus:ring-offset-[var(--surface-base)]"
            >
              Primary action
            </button>
            <button
              className="rounded-[var(--r-sm)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:border-[var(--gold)] focus:outline-none focus:ring-2 focus:ring-[var(--gold)]/40"
            >
              Secondary
            </button>
          </div>
        </Section>
      </div>
    </main>
  );
}
