import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import PatientSearch from "./PatientSearch";
import type { PatientSearchResponse } from "@/lib/domains/patient";

const translate = (key: string, params?: { patientId: string }) => params?.patientId ?? key;
vi.mock("@/lib/i18n/useTranslations", () => ({ useT: () => translate }));
vi.mock("@/components/shell/PatientTabLink", () => ({
  PatientTabContextMenu: () => null, useOpenPatientBackground: () => vi.fn(),
}));
const renderers: ReactTestRenderer[] = [];
let outside: (event: { target: unknown }) => void;
const calls: { q: string; signal: AbortSignal; resolve: (body: PatientSearchResponse) => void; reject: (error: Error) => void }[] = [];
const onSelect = vi.fn();
const search = vi.fn((q: string, _limit?: number, options?: RequestInit) =>
  new Promise<PatientSearchResponse>((resolve, reject) => calls.push({ q, signal: options!.signal!, resolve, reject })));
const result = { results: [{ patient_id: "PATIENT-B", age: null, sex: null }], total_matched: 1 } satisfies PatientSearchResponse;
async function mount(selectedPatientId: string | null = null) {
  let renderer: ReactTestRenderer;
  await act(async () => { renderer = create(<PatientSearch selectedPatientId={selectedPatientId} onSelect={onSelect} searchFn={search} />, {
    createNodeMock: element => element.type === "div" ? { contains: () => false } : null,
  }); });
  renderers.push(renderer!);
  const input = () => renderer!.root.findByType("input");
  return {
    renderer: renderer!, input,
    focus: () => act(async () => { input().props.onFocus(); }),
    type: (value: string) => act(async () => { input().props.onChange({ target: { value } }); }),
    key: (key: string) => act(async () => { input().props.onKeyDown({ key, preventDefault: vi.fn() }); }),
    blur: () => act(async () => { renderer!.root.findAllByType("div")[0].props.onBlur({ currentTarget: { contains: () => false }, relatedTarget: null }); }),
  };
}
const tick = () => act(async () => { vi.advanceTimersByTime(200); });
const finish = (index: number) => act(async () => { calls[index].resolve(result); });
beforeEach(() => {
  vi.useFakeTimers(); vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("document", { addEventListener: (_: string, cb: typeof outside) => { outside = cb; }, removeEventListener: vi.fn() });
  calls.length = 0; search.mockClear(); onSelect.mockClear();
});
afterEach(async () => {
  for (const renderer of renderers.splice(0)) await act(async () => { renderer.unmount(); });
  vi.useRealTimers(); vi.unstubAllGlobals();
});
it("keeps fast AB typing visible before debounce and response, replacing a selected label", async () => {
  const ui = await mount("PATIENT-A");
  expect(ui.input().props.value).toBe("PATIENT-A");
  await ui.focus(); expect(ui.input().props.value).toBe("");
  await ui.type("A"); expect(ui.input().props.value).toBe("A");
  await ui.type("AB"); expect(ui.input().props.value).toBe("AB");
  await tick(); expect(calls.map(c => c.q)).toEqual(["AB"]);
  await finish(0); expect(ui.input().props.value).toBe("AB");
});
it("Escape before the debounce cancels work and keeps the editing draft", async () => {
  const ui = await mount(); await ui.focus(); await ui.type("AB"); await ui.key("Escape"); await tick();
  expect(calls).toHaveLength(0); expect(ui.input().props.value).toBe("AB"); expect(ui.input().props["aria-expanded"]).toBe(false);
});
it.each(["escape", "outside", "blur"])("%s invalidates stale success and error, including fast refocus", async reason => {
  const ui = await mount(); await ui.focus(); await ui.type("A"); await tick();
  if (reason === "escape") await ui.key("Escape");
  else if (reason === "outside") await act(async () => { outside({ target: {} }); });
  else await ui.blur();
  expect(calls[0].signal.aborted).toBe(true);
  await finish(0); expect(ui.input().props["aria-expanded"]).toBe(false);
  await ui.focus(); await ui.type("B"); await tick();
  await ui.type("C"); expect(calls[1].signal.aborted).toBe(true);
  await act(async () => { calls[1].reject(new Error("old failure")); });
  await tick(); await finish(2);
  expect(ui.renderer.root.findAllByProps({ role: "option" })).toHaveLength(1);
  expect(ui.input().props.value).toBe("C");
});
it("does not apply out-of-order results during the next debounce", async () => {
  const ui = await mount(); await ui.focus(); await ui.type("A"); await tick();
  await ui.type("AB"); await finish(0);
  expect(ui.renderer.root.findAllByProps({ role: "option" })).toHaveLength(0);
  await tick(); await finish(1); expect(calls[1].q).toBe("AB");
});
it("supports loading, error retry, clearing and keyboard selection without reopening", async () => {
  const ui = await mount(); await ui.focus(); await tick();
  expect(ui.renderer.root.findByType("ul").children.length).toBeGreaterThan(0);
  await act(async () => { calls[0].reject(new Error("search failed")); });
  const retry = ui.renderer.root.findAllByType("button")[0];
  await act(async () => { retry.props.onClick(); }); await tick(); await finish(1);
  await ui.key("ArrowDown"); await ui.key("Enter");
  expect(onSelect).toHaveBeenCalledWith("PATIENT-B"); expect(ui.input().props["aria-expanded"]).toBe(false);
  await ui.focus(); await ui.type(""); await tick(); expect(calls[2].q).toBe("");
  await act(async () => { ui.renderer.unmount(); }); expect(calls[2].signal.aborted).toBe(true); await finish(2);
});

it.each(["success", "error"])("selection invalidates a pending %s even from a captured result handler", async outcome => {
  const ui = await mount(); await ui.focus(); await tick(); await finish(0);
  const select = ui.renderer.root.findByProps({ role: "option" }).props.onClick;
  await ui.type("new query"); await tick();
  await act(async () => { select({ button: 0 }); });
  expect(calls[1].signal.aborted).toBe(true);
  await act(async () => { if (outcome === "success") calls[1].resolve(result); else calls[1].reject(new Error("late failure")); });
  expect(ui.input().props["aria-expanded"]).toBe(false);
  expect(onSelect).toHaveBeenCalledWith("PATIENT-B");
});
