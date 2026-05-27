## Task: Fix awful table styling

### Goal
Restore professional table appearance across the frontend after frost-table CSS removal.

### Root cause
Phase 6 migrated wrappers to `<DataTable>` but deleted `.frost-table` CSS. Call sites still use raw `<thead>/<tr>/<th>/<td>` without sub-components — cells lost padding, headers, borders, sticky behavior, and `.num-col` alignment.

### Subtasks
- [x] Add `.bilun-data-table` descendant styles in globals.css
- [x] Apply class in DataTable.tsx; restore `.num-col` on sub-components
- [x] Wrap remaining raw `<table>` usages (PatientSection, TemporalPriceSection, SUTOptimizerTab)
- [x] Verify: lint, tsc, vitest 62/62, build

### Out of Scope
- Rewriting every table to DataTableHeaderCell sub-components (CSS handles raw markup)

### Review (2026-05-27)
Fixed by restoring table cell styling via `.bilun-data-table` on the inner `<table>`. All DataTable wrappers now inherit cream sticky headers, row padding/borders, hover tint, and numeric column alignment without touching 12+ call sites individually.
