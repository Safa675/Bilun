import { Children, isValidElement, type ReactElement, type ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import type { BillingActionReport } from "@/lib/domains/sut";
import fixture from "@/test/fixtures/checklist-constraint-inputs.json";
import AuditViewSection from "./AuditViewSection";

const hooks = vi.hoisted(() => ({ states: [] as unknown[], index: 0, didLoad: false }));
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useState: (initial: unknown) => {
    const index = hooks.index++;
    if (!(index in hooks.states)) hooks.states[index] = initial;
    return [hooks.states[index], (value: unknown) => {
      hooks.states[index] = typeof value === "function" ? value(hooks.states[index]) : value;
    }];
  },
  useEffect: (load: () => void) => {
    if (!hooks.didLoad) { hooks.didLoad = true; load(); }
  },
  useCallback: (callback: unknown) => callback,
}));
vi.mock("@/lib/i18n/useTranslations", () => ({ useT: () => (key: string) => key }));

type Element = ReactElement<{ children?: ReactNode; type?: string; checked?: boolean; onChange?: () => void }>;
function elements(node: ReactNode): Element[] {
  return Children.toArray(node).flatMap((child) =>
    isValidElement<Element["props"]>(child) ? [child, ...elements(child.props.children)] : [],
  );
}
const report = {
  patient_id: "P1", recommended_actions: [],
  claim_submission_checklist: { items: fixture.checklistItems, exactness_status: "exact", item_count: 3 },
} as unknown as BillingActionReport;
function renderCheckboxes() {
  hooks.index = 0;
  return elements(AuditViewSection({ billingReport: report, patientId: "P1" }))
    .filter((element) => element.type === "input" && element.props.type === "checkbox");
}
beforeEach(() => {
  hooks.states = [];
  hooks.didLoad = false;
  const storage = new Map([["bilun:checklist:ready:P1", '["0612_board_report_missing:"]']]);
  vi.stubGlobal("window", { localStorage: {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
  } });
});
it("keeps legacy blank-suffix readiness isolated and toggles one of three real backend rows", () => {
  renderCheckboxes(); // Load persisted state, then render it.
  expect(renderCheckboxes().map((row) => row.props.checked)).toEqual([false, false, false]);
  renderCheckboxes()[0].props.onChange?.();
  expect(renderCheckboxes().map((row) => row.props.checked)).toEqual([true, false, false]);
  renderCheckboxes()[2].props.onChange?.();
  expect(renderCheckboxes().map((row) => row.props.checked)).toEqual([true, false, true]);
  renderCheckboxes()[0].props.onChange?.();
  expect(renderCheckboxes().map((row) => row.props.checked)).toEqual([false, false, true]);
});
