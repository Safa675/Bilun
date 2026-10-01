import { afterEach, describe, expect, it, vi } from "vitest";
import { announceSessionChange, AUTH_CHANGE_KEY, clearProtectedBrowserState } from "./authBrowser";

afterEach(() => vi.unstubAllGlobals());

describe("browser identity transitions", () => {
  it("removes old role and workspace state without touching locale or unrelated preferences", () => {
    const localRemove = vi.fn();
    const sessionRemove = vi.fn();
    const setItem = vi.fn();
    vi.stubGlobal("window", { localStorage: { removeItem: localRemove, setItem }, sessionStorage: { removeItem: sessionRemove } });
    vi.stubGlobal("document", { cookie: "" });
    clearProtectedBrowserState();
    expect(localRemove.mock.calls).toEqual([["bilun_user_role"]]);
    expect(sessionRemove.mock.calls).toEqual([["bilun:workspace-tabs"]]);
    expect(document.cookie).toContain("bilun:role=; Max-Age=0");
    announceSessionChange();
    expect(setItem).toHaveBeenCalledWith(AUTH_CHANGE_KEY, expect.any(String));
  });

  it("does not let unavailable browser storage block a safe transition", () => {
    const fail = () => { throw new Error("disabled"); };
    vi.stubGlobal("window", { localStorage: { removeItem: fail, setItem: fail }, sessionStorage: { removeItem: fail } });
    vi.stubGlobal("document", { cookie: "" });
    expect(() => { clearProtectedBrowserState(); announceSessionChange(); }).not.toThrow();
  });
});
