# Subtab Icons & Active Subtab Display in Top Workspace Tab Strip

Add distinct Lucide icons to all subtabs across **Reference Tools**, **Compliance**, and **Rule Database**, synchronize subtab state via URL query parameters, and update the **WorkspaceTabStrip** (top bar) to show the active subtab's icon and localized title instead of only the parent tab.

## User Review Required

> [!IMPORTANT]
> When a user navigates to a specific subtab (e.g. `Referans Araçları > Branşa Göre` or `Kural Veritabanı > Hükümler`), the top tab bar tab will display the subtab's specific icon and name (e.g. `Branşa Göre` with a medical briefcase icon). If no subtab query is present, it will display the parent tab's name and icon (e.g. `Referans Araçları`).

## Proposed Changes

### 1. Reference Tools (`frontend/src/components/tabs/sut/ToolsSection.tsx`)

#### [MODIFY] `ToolsSection.tsx`
- Assign Lucide icons for all 8 subtabs:
  - `validator`: `FileCheck2` ("Talep Doğrulayıcı")
  - `search`: `PackageSearch` ("Malzeme Arama")
  - `bundled`: `Boxes` ("Paket Kalemler")
  - `price_history`: `TrendingUp` ("Fiyat Geçmişi")
  - `visits`: `CalendarCheck` ("Ziyaret Fiyatlandırması")
  - `drugs`: `Pill` ("İlaç Kataloğu")
  - `specialty`: `BriefcaseMedical` ("Branşa Göre")
  - `lab_prices`: `FlaskConical` ("Laboratuvar Fiyatları")
- Replace raw `<Button>` list with `<TabsRoot>`, `<TabsList>`, `<TabsTrigger>` (or `<Button>` with leading icon and accessible layout) for visual consistency.
- Synchronize active subtab with `useSearchParams()` (`toolSub` param) and update URL on change via `router.replace(..., { scroll: false })`.

---

### 2. Compliance Section (`frontend/src/components/tabs/sut/optimizer/SUTOptimizerTab.tsx`)

#### [MODIFY] `SUTOptimizerTab.tsx`
- Synchronize active subtab with URL query parameter `compTab` (`searchParams.get("compTab") || "exemptions"`).
- Update URL on subtab change (`handleCategoryChange`) using `router.replace(..., { scroll: false })` so `WorkspaceRouteSync` captures the active subtab.
- Ensure subtab icons (`ShieldCheck` for exemptions, `ShieldAlert` for surcharge) are rendered cleanly.

---

### 3. Rule Database Section (`frontend/src/components/tabs/sut/sections/RuleDatabaseSection.tsx`)

#### [MODIFY] `RuleDatabaseSection.tsx`
- Add distinct Lucide icons to all 5 `TabsTrigger` subtabs:
  - `rules`: `BookOpen` ("Kurallar")
  - `sections`: `FolderTree` ("Bölümler")
  - `clauses`: `ScrollText` ("Hükümler")
  - `prose`: `Cpu` ("Düz metin motorları")
  - `deferrals`: `Clock` ("Ertelenenler")
- Continue using `rdTab` URL param sync.

---

### 4. Workspace Tab Strip & Tab Helpers

#### [MODIFY] `frontend/src/lib/workspaceTabs.ts`
- Add subtab extraction helpers to parse `toolSub`, `compTab`, and `rdTab` from a tab's `query` string.
- Export subtab metadata resolver functions (`resolveSubtabInfo(tab, t)`) providing `{ label: string, icon: LucideIcon }`.

#### [MODIFY] `frontend/src/components/shell/WorkspaceTabStrip.tsx`
- Update `tabLabel(tab, t)` to return the active subtab's localized label if present (falling back to the parent section label).
- Update `TabIcon({ tab })` to render the active subtab's icon if present (falling back to `TAB_ICONS[tab.refId]`).
- Update the overflow dropdown items to also display the resolved subtab label and icon.

---

## Verification Plan

### Automated Tests
- Run `npx vitest run src/lib/workspaceTabs.test.ts`
- Run `npx vitest run src/components/tabs/sut/sections/RuleDatabaseSection.test.tsx`
- Run `npx vitest run src/components/tabs/sut/optimizer/SUTOptimizerTab.test.tsx`
- Run full vitest suite: `npx vitest run`

### Manual Verification
- Navigate to `http://localhost:3000/?tab=reference-tools&toolSub=specialty` -> Verify top tab displays `Branşa Göre` with `BriefcaseMedical` icon.
- Click `Malzeme Arama` -> Verify top tab updates immediately to `Malzeme Arama` with `PackageSearch` icon.
- Navigate to `http://localhost:3000/?tab=compliance&compTab=surcharge` -> Verify top tab displays `Fark ücreti uyumu` with `ShieldAlert` icon.
- Navigate to `http://localhost:3000/?tab=rule-database&rdTab=clauses` -> Verify top tab displays `Hükümler` with `ScrollText` icon.
