import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { getHealthStatus, type HealthStatus } from "@/lib/api/health";
import { useHealthPolling } from "./useHealthPolling";
vi.mock("@/lib/api/health", () => ({ getHealthStatus: vi.fn() }));
const ready: HealthStatus = { status: "ready", patients: null, build_id: "B" };
const calls: { signal: AbortSignal; resolve: (status: HealthStatus) => void; reject: (error: Error) => void }[] = [];
const setStatus = vi.fn();
let renderer: ReactTestRenderer;
function Harness({ enabled }: { enabled: boolean }) { useHealthPolling(enabled, setStatus); return null; }
beforeEach(async () => {
  vi.useFakeTimers(); vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("window", { setInterval, clearInterval }); calls.length = 0; setStatus.mockClear();
  vi.mocked(getHealthStatus).mockImplementation(options => new Promise((resolve, reject) => calls.push({ signal: options!.signal!, resolve, reject })));
  await act(async () => { renderer = create(<Harness enabled />); });
});
afterEach(async () => { await act(async () => { renderer.unmount(); }); vi.useRealTimers(); vi.unstubAllGlobals(); });
it.each(["network", "malformed", "unauthorized"])("shows unavailable after a ready poll then %s failure", async reason => {
  await act(async () => { calls[0].resolve(ready); }); expect(setStatus).toHaveBeenLastCalledWith(ready);
  await act(async () => { vi.advanceTimersByTime(30_000); calls[1].reject(new Error(reason)); });
  expect(setStatus).toHaveBeenLastCalledWith(null);
});
it("supersedes slow polls and ignores stale success/failure", async () => {
  await act(async () => { vi.advanceTimersByTime(30_000); }); expect(calls[0].signal.aborted).toBe(true);
  await act(async () => { calls[1].resolve(ready); calls[0].reject(new Error("late error")); });
  expect(setStatus).toHaveBeenCalledTimes(1); expect(setStatus).toHaveBeenLastCalledWith(ready);
});
it("aborts on toggle/unmount without clearing the last result, and isolates refocus", async () => {
  await act(async () => { calls[0].resolve(ready); });
  await act(async () => { vi.advanceTimersByTime(30_000); });
  await act(async () => { renderer.update(<Harness enabled={false} />); });
  expect(calls[1].signal.aborted).toBe(true);
  await act(async () => { calls[1].resolve({ ...ready, build_id: "old" }); vi.advanceTimersByTime(90_000); });
  expect(calls).toHaveLength(2); expect(setStatus).toHaveBeenLastCalledWith(ready);
  await act(async () => { renderer.update(<Harness enabled />); }); expect(calls).toHaveLength(3);
  await act(async () => { renderer.unmount(); });
  await act(async () => { calls[2].resolve(ready); });
  expect(calls[2].signal.aborted).toBe(true); expect(setStatus).toHaveBeenCalledTimes(1);
});
