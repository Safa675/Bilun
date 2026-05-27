## Task: UI Fixes + Patient Invoice Table on Home

### Goal
Fix remaining UI issues (dock shift, logo size, remove status), then add a patient invoice table to the SUT Analytics home view.

### Subtasks

#### Quick Fixes (no ambiguity)
- [ ] **Fix docked chatbot content shift** — change `max-w-7xl` to a responsive calc when docked; or remove `mx-auto` and use `width: 100%` so padding actually creates space
- [ ] **Bigger BILUN logo** — increase from `h-6` (~24px) to `h-8` (~32px) in `AppTopBar.tsx`
- [ ] **Remove "Status unknown" indicator** — remove the health status polling UI from `AppTopBar.tsx` (keep SyntheticDemoChip)

#### Patient Invoice Table (needs clarification)
- [ ] **Explore available patient APIs** — what fields does `getSutPatients()` or `/api/patients` return?
- [ ] **Design table columns** — patient ID, invoice count, total billed, total payable, priority tier, last updated?
- [ ] **Decide placement** — replace the current patient-search empty state in `SUTAnalyticsShell`, or add as a new section?
- [ ] **Implement table component** — reusable data table with sorting, pagination if needed
- [ ] **Wire to API** — fetch patient list on mount, show loading skeleton
- [ ] **Build and lint verify**

### Out of Scope
- Backend API changes (use existing endpoints)
- Changes to patient detail page

### Clarification Needed
What columns should the patient invoice table show? For example:
- Patient ID
- Number of invoices/claims
- Total billed amount
- Total payable amount
- Priority tier (high/medium/low)
- Last visit date
- Copay exemption status

Please confirm or suggest different columns.
