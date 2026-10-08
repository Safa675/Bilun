import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SutPatientPageContent } from "./page";
import SutInlineAIPanel from "@/components/chat/SutInlineAIPanel";
import PatientSearch from "@/components/ui/PatientSearch";
import BillPicker from "@/components/patient/BillPicker";
import SutPatientWorkspace from "@/components/patient/SutPatientWorkspace";
import PatientWorkspaceViews from "@/components/patient/views/PatientWorkspaceViews";
import { BillingSummary } from "@/components/patient/SutBillingReportSections";
import { BillingReportGroup } from "@/components/patient/BillingReportGroup";
import { createWorkspaceStore } from "@/stores/workspaceStore";
import * as api from "@/lib/api/sut";
import type { SutChatDockPosition } from "@/stores/storeInterfaces";

const navigation = vi.hoisted(() => ({ query: "claim=A-1&section=lab&finding=primary", replace: vi.fn(), push: vi.fn() }));
const dockState = vi.hoisted(() => ({ value: "center" as SutChatDockPosition }));
const translate = (key: string) => key === "patient.workspace.backToPatients" ? "Back to patients" : key;
vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
  useSearchParams: () => new URLSearchParams(navigation.query), useParams: () => ({ id: "A" }),
}));
vi.mock("next/link", () => ({
  default: ({ children, ...props }: React.ComponentProps<"a">) => <a {...props}>{children}</a>,
}));
vi.mock("@/lib/i18n/useTranslations", () => ({ useT: () => translate }));
vi.mock("@/lib/recents", () => ({ recordRecent: vi.fn() }));
vi.mock("@/components/chat/SutInlineAIPanel", () => ({ default: () => null }));
vi.mock("@/components/modals/SutHowItWorksModal", () => ({ default: () => null }));
vi.mock("@/components/feedback/ReportProblemModal", () => ({ default: () => null }));
vi.mock("@/components/ui/PatientSearch", () => ({ default: () => null }));
vi.mock("@/components/sut/SutClauseDrawer", () => ({ SutClauseDrawer: () => null }));
vi.mock("@/components/patient/SutPatientWorkspace", () => ({ default: () => null, PatientClinicalSnapshot: () => null }));
vi.mock("@/components/patient/SutBillingReportSections", () => ({ BillingSummary: () => null, SutOptimizationSection: () => null }));
vi.mock("@/components/patient/views/PatientWorkspaceViews", () => ({ default: ({ billContent, detailsContent }: { billContent: React.ReactNode; detailsContent: React.ReactNode }) => <>{billContent}{detailsContent}</> }));
vi.mock("@/components/patient/OriginalBillView", () => ({ default: () => null }));
vi.mock("@/stores/index", () => ({
  useAiDockPosition: () => dockState.value, useSetAiDockPosition: () => vi.fn(),
  useSetShowHowItWorks: () => vi.fn(), useSetShowReportProblem: () => vi.fn(), useSetSutChatSession: () => vi.fn(),
  useShowHowItWorks: () => false, useShowReportProblem: () => false,
  useSutChatSession: () => ({ messages: [], autoText: "" }), useWorkspacePaneBTabId: () => "patient:B",
}));
vi.mock("@/lib/api/sut", () => ({
  getSutPatientOutcome: vi.fn(async (patient_id: string) => ({ patient_id })),
  getPatientOptimization: vi.fn(async (patient_id: string) => ({ patient_id })),
  getPatientBillingReport: vi.fn(async (patient_id: string) => ({ patient_id, recommended_actions: [] })),
  getPatientClaims: vi.fn(async (patient_id: string) => ({ claims: [1, 2].map(n => ({ claim_id: `${patient_id}-${n}`, claim_start_date: "2026-09-01" })) })),
  getPatientClaimDetail: vi.fn(async (patient_id: string, claim_id: string) => ({ patient_id, claim_id })),
  getBillBillingReport: vi.fn(async (patient_id: string, claim_id: string) => ({ patient_id, claim_id, scope: "bill", recommended_actions: [] })),
  getBillOptimization: vi.fn(async (patient_id: string, claim_id: string) => ({ patient_id, claim_id, scope: "bill" })),
  searchSutPatients: vi.fn(),
}));
const renderers: ReactTestRenderer[] = [];
async function mount(patientId: string, embedded: boolean, embeddedQuery?: string, createNodeMock?: (element: React.ReactElement) => unknown) {
  let renderer: ReactTestRenderer;
  await act(async () => { renderer = create(<SutPatientPageContent patientId={patientId} embedded={embedded} embeddedQuery={embeddedQuery} />, { createNodeMock: createNodeMock ?? (() => null) }); });
  renderers.push(renderer!);
  await act(async () => { vi.advanceTimersByTime(0); });
  const picker = () => renderer!.root.findByType(BillPicker);
  return {
    renderer: renderer!, picker,
    select: (id: string | null) => act(async () => { picker().props.onSelectClaim(id); }),
    update: async (id = patientId) => {
      await act(async () => { renderer!.update(<SutPatientPageContent patientId={id} embedded={embedded} embeddedQuery={embeddedQuery} />); });
      await act(async () => { vi.advanceTimersByTime(0); });
    },
  };
}
beforeEach(() => {
  vi.useFakeTimers(); vi.clearAllMocks(); vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("window", { setTimeout, clearTimeout });
  vi.stubGlobal("requestAnimationFrame", () => 1); vi.stubGlobal("cancelAnimationFrame", vi.fn());
  navigation.query = "claim=A-1&section=lab&finding=primary";
  dockState.value = "center";
});
afterEach(async () => {
  for (const renderer of renderers.splice(0)) await act(async () => { renderer.unmount(); });
  vi.useRealTimers(); vi.unstubAllGlobals();
});
it("keeps a Back to patients link inside the loading skeleton", async () => {
  let renderer: ReactTestRenderer;
  await act(async () => { renderer = create(<SutPatientPageContent patientId="A" />); });
  renderers.push(renderer!);
  const link = renderer!.root.findByType("main").findByType("a");
  expect(link.props.href).toBe("/?tab=patients");
  expect(link.children).toContain("Back to patients");
});
it("restores the embedded pane's own saved bill, section and finding query", async () => {
  const pane = await mount("B", true, "claim=B-2&section=claim-reviews&finding=B-review");
  expect(pane.picker().props.selectedClaimId).toBe("B-2");
  expect(pane.renderer.root.findByType(PatientWorkspaceViews).props).toMatchObject({
    sectionQuery: "claim-reviews", selectedFindingId: "B-review",
  });
  expect(api.getBillBillingReport).toHaveBeenCalledWith("B", "B-2", expect.anything());
  expect(navigation.replace).not.toHaveBeenCalled();
});
it.each([null, "B-2"])("retains one distinct financial detail owner without a second overview wrapper for claim %s", async (claimId) => {
  const pane = await mount("B", true, claimId ? `claim=${claimId}` : "");
  const workspace = pane.renderer.root.findByType(SutPatientWorkspace);
  const summary = pane.renderer.root.findByType(BillingSummary);
  expect(summary.props.billingReport).toBe(workspace.props.billingReport);
  expect(summary.props.omitPriority).toBe(true);
  expect(summary.props.billingReport).toMatchObject({ patient_id: "B", ...(claimId ? { claim_id: claimId, scope: "bill" } : {}) });
  expect(pane.renderer.root.findAllByType(BillingSummary)).toHaveLength(1);
  expect(pane.renderer.root.findAllByType(BillingReportGroup)).toHaveLength(0);
});
it.each([
  [false, null], [true, null], [false, "B-2"], [true, "B-2"],
] as const)("omits duplicate context only for a matching report in embedded=%s claim=%s", async (embedded, claimId) => {
  vi.mocked(api.getPatientBillingReport).mockResolvedValueOnce({
    patient_id: "B", recommended_actions: [],
  } as unknown as Awaited<ReturnType<typeof api.getPatientBillingReport>>);
  navigation.query = claimId ? `claim=${claimId}` : "";
  const pane = await mount("B", embedded, embedded ? navigation.query : undefined);
  const summary = pane.renderer.root.findByType(BillingSummary);
  const workspace = pane.renderer.root.findByType(SutPatientWorkspace);
  expect(summary.props.omitHeaderContext).toBe(true);
  expect(summary.props.billingReport).toBe(workspace.props.billingReport);
  expect(workspace.props.patientId).toBe("B");
  expect(workspace.props.selectedClaimId).toBe(claimId);
});
it.each([
  [false, "wrong-patient"], [true, "wrong-patient"], [false, "unexpected-scope"], [true, "unexpected-scope"],
  [false, "bill-scope"], [true, "bill-scope"], [false, "unselected-claim"], [true, "unselected-claim"],
] as const)("retains full context for %s pane with %s patient report", async (embedded, mismatch) => {
  vi.mocked(api.getPatientBillingReport).mockResolvedValueOnce({
    patient_id: mismatch === "wrong-patient" ? "OTHER" : "B",
    scope: mismatch === "unexpected-scope" ? "patient" : mismatch === "bill-scope" ? "bill" : undefined,
    claim_id: mismatch === "unselected-claim" ? "UNSELECTED" : undefined, recommended_actions: [],
  } as unknown as Awaited<ReturnType<typeof api.getPatientBillingReport>>);
  navigation.query = "";
  const pane = await mount("B", embedded, embedded ? "" : undefined);
  expect(pane.renderer.root.findByType(BillingSummary).props.omitHeaderContext).toBe(false);
});
it.each([
  [false, "wrong-patient"], [true, "wrong-patient"], [false, "wrong-claim"], [true, "wrong-claim"],
  [false, "wrong-scope"], [true, "wrong-scope"],
] as const)("keeps rejecting a mismatched selected-bill report in %s pane with %s", async (embedded, mismatch) => {
  vi.mocked(api.getBillBillingReport).mockResolvedValueOnce({
    patient_id: mismatch === "wrong-patient" ? "OTHER" : "B",
    claim_id: mismatch === "wrong-claim" ? "B-1" : "B-2", scope: mismatch === "wrong-scope" ? "patient" : "bill",
    recommended_actions: [],
  } as unknown as Awaited<ReturnType<typeof api.getBillBillingReport>>);
  navigation.query = "claim=B-2";
  const pane = await mount("B", embedded, embedded ? navigation.query : undefined);
  expect(pane.renderer.root.findAllByType(BillingSummary)).toHaveLength(0);
  expect(pane.renderer.root.findByType(SutPatientWorkspace).props.billingReport).toBeNull();
});
it.each([false, true])("opens an optional-method detail target itself and its parent in embedded=%s", async (embedded) => {
  const outer = { tagName: "DETAILS", open: false, parentElement: null };
  const target = { id: "billing-optional-override", tagName: "DETAILS", open: false, parentElement: outer, scrollIntoView: vi.fn() };
  const root = {
    querySelectorAll: (selector: string) => selector === "[id]" ? [target] : [],
    contains: (element: unknown) => element === target || element === outer,
  };
  const frames: Array<FrameRequestCallback> = [];
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => { frames.push(callback); return frames.length; });
  navigation.query = "section=billing-optional-override";
  const pane = await mount("A", embedded, embedded ? navigation.query : undefined, () => root);
  await act(async () => { for (const frame of frames.splice(0)) frame(0); });
  expect(target.open).toBe(true);
  expect(outer.open).toBe(true);
  expect(target.scrollIntoView).toHaveBeenCalled();
  expect(pane.renderer.root.findByType(PatientWorkspaceViews).props.sectionQuery).toBe("billing-optional-override");
});
it("keeps a Back to patients link inside the unavailable billing report card", async () => {
  vi.mocked(api.getSutPatientOutcome).mockRejectedValueOnce(new Error("Patient not found"));
  vi.mocked(api.getPatientOptimization).mockRejectedValueOnce(new Error("Patient not found"));
  vi.mocked(api.getPatientBillingReport).mockRejectedValueOnce(new Error("Patient not found"));
  const view = await mount("SENTETIK-HASTA-9999", false);
  expect(view.renderer.root.findByType("h1").children).toContain("patient.page.billingUnavailable");
  const link = view.renderer.root.findByType("main").findByType("a");
  expect(link.props.href).toBe("/?tab=patients");
  expect(link.children).toContain("Back to patients");
});
it("keeps B's bill selection local while A's URL and real split workspace remain intact", async () => {
  const store = createWorkspaceStore({
    tabs: [{ id: "patient:A", kind: "patient", refId: "A", query: navigation.query, lastActivatedAt: 2 },
      { id: "patient:B", kind: "patient", refId: "B", lastActivatedAt: 1 }],
    activeTabId: "patient:A", paneBTabId: "patient:B",
  });
  navigation.replace.mockImplementation((href: string) => {
    const url = new URL(href, "https://test");
    store.getState().syncFromRoute({ kind: "patient", refId: url.pathname.split("/").at(-1)!, query: url.search.slice(1) });
  });
  const primary = await mount("A", false); const pane = await mount("B", true);
  expect(primary.picker().props.selectedClaimId).toBe("A-1");
  expect(pane.picker().props.selectedClaimId).toBeNull();
  expect(pane.renderer.root.findByType(PatientWorkspaceViews).props.sectionQuery).toBeNull();
  await pane.select("B-2"); await pane.select("B-2");
  expect(navigation.replace).not.toHaveBeenCalled();
  expect(primary.picker().props.selectedClaimId).toBe("A-1");
  expect(store.getState()).toMatchObject({ activeTabId: "patient:A", paneBTabId: "patient:B" });
  expect(api.getBillBillingReport).toHaveBeenCalledWith("B", "B-2", expect.anything());
  expect(api.getPatientClaimDetail).toHaveBeenCalledWith("B", "B-2", expect.anything());
  expect(pane.renderer.root.findByType(SutPatientWorkspace).props.selectedClaimId).toBe("B-2");
  await pane.select(null); expect(pane.picker().props.selectedClaimId).toBeNull();
  expect(navigation.replace).not.toHaveBeenCalled();
});
it("masks the old embedded patient's bill before any new-patient fetch or render", async () => {
  const pane = await mount("B", true);
  let finish: (value: Awaited<ReturnType<typeof api.getBillBillingReport>>) => void;
  vi.mocked(api.getBillBillingReport).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  await pane.select("B-1");
  const signals = vi.mocked(api.getBillBillingReport).mock.calls.map(call => call[2]?.signal);
  await pane.update("C");
  expect(pane.picker().props.selectedClaimId).toBeNull();
  expect(api.getBillBillingReport).not.toHaveBeenCalledWith("C", "B-1", expect.anything());
  expect(api.getPatientClaimDetail).not.toHaveBeenCalledWith("C", "B-1", expect.anything());
  expect(signals.every(signal => signal?.aborted)).toBe(true);
  await act(async () => { finish!({ patient_id: "B", claim_id: "B-1", scope: "bill" } as Awaited<ReturnType<typeof api.getBillBillingReport>>); });
  expect(pane.renderer.root.findByType(SutPatientWorkspace).props.selectedClaimId).toBeNull();
  await pane.select("C-2");
  expect(api.getBillBillingReport).toHaveBeenLastCalledWith("C", "C-2", expect.anything());
  navigation.query = "claim=A-2&section=materials"; await pane.update("C");
  expect(pane.picker().props.selectedClaimId).toBe("C-2");
});
it("preserves primary selection URLs, reload and Back/Forward query changes", async () => {
  const primary = await mount("A", false);
  expect(primary.picker().props.selectedClaimId).toBe("A-1");
  await primary.select("A-2");
  expect(navigation.replace).toHaveBeenLastCalledWith("/patient/A?claim=A-2&section=lab", { scroll: false });
  navigation.query = "claim=A-2"; await primary.update();
  expect(primary.picker().props.selectedClaimId).toBe("A-2");
  navigation.query = "claim=A-1"; await primary.update();
  expect(primary.picker().props.selectedClaimId).toBe("A-1");
  navigation.query = "claim=A-2"; await primary.update();
  expect(primary.picker().props.selectedClaimId).toBe("A-2");
  navigation.query = ""; await primary.update();
  expect(primary.picker().props.selectedClaimId).toBeNull();
  await primary.select(null); expect(navigation.replace).toHaveBeenLastCalledWith("/patient/A", { scroll: false });
});
it("has no standalone patient search card, and the chat keeps collapse and open while a split view is active", async () => {
  const primary = await mount("A", false);
  expect(primary.renderer.root.findAllByType(PatientSearch)).toHaveLength(0);
  expect(primary.renderer.root.findAllByProps({ id: "sut-patient-workspace-search" })).toHaveLength(0);
  const chat = primary.renderer.root.findByType(SutInlineAIPanel);
  // the mocked store reports a split view (pane B open) and the "center" dock
  expect(chat.props).toMatchObject({ dock: "center", allowRightDock: false });
  expect(typeof chat.props.onDockChange).toBe("function");
  const pane = await mount("B", true);
  expect(pane.renderer.root.findAllByType(SutInlineAIPanel)).toHaveLength(0);
});
// The page frame follows the chat dock: only the right dock (a fixed column) and the embedded split pane use the full
// width; the collapsed bar (the default) and the centre card keep the centred max-w-7xl frame.
it.each([
  ["collapsed", false, "mx-auto max-w-7xl space-y-6"],
  ["center", false, "mx-auto max-w-7xl space-y-6"],
  ["right", false, "w-full space-y-6"],
  ["collapsed", true, "w-full space-y-6"],
  ["right", true, "w-full space-y-6"],
] as const)("frames the page for the %s chat dock (embedded %s) as '%s'", async (dock, embedded, expectedClass) => {
  dockState.value = dock;
  const view = await mount("A", embedded);
  const frames = view.renderer.root.findAll(node => node.type === "section" && String(node.props.className).includes("space-y-6"));
  expect(frames).toHaveLength(1);
  expect(frames[0].props.className).toBe(expectedClass);
});
