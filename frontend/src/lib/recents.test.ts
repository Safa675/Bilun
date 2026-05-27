import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  RECENTS_MAX_ENTRIES,
  RECENTS_STORAGE_KEYS,
  getRecents,
  recordRecent,
} from "./recents";

const KEY_PATIENT = RECENTS_STORAGE_KEYS.patient;
const KEY_BILLING = RECENTS_STORAGE_KEYS.billing;

function setupBrowserGlobals(): Storage {
  const store = new Map<string, string>();
  const fake: Storage = {
    get length() { return store.size; },
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => { store.set(k, v); },
    removeItem: (k: string) => { store.delete(k); },
    clear: () => { store.clear(); },
  };

  const listeners = new Map<string, Set<EventListener>>();
  const fakeWindow = {
    localStorage: fake,
    addEventListener: (type: string, listener: EventListener) => {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(listener);
    },
    removeEventListener: (type: string, listener: EventListener) => {
      listeners.get(type)?.delete(listener);
    },
    dispatchEvent: (event: Event) => {
      listeners.get(event.type)?.forEach((l) => l(event));
      return true;
    },
  };

  Object.defineProperty(globalThis, "window", { configurable: true, value: fakeWindow });
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: fake });
  return fake;
}

describe("recents", () => {
  let now = 1_000_000_000_000;

  beforeEach(() => {
    setupBrowserGlobals();
    now = 1_000_000_000_000;
    vi.spyOn(Date, "now").mockImplementation(() => now);

    if (typeof CustomEvent === "undefined") {
      (globalThis as unknown as { CustomEvent: typeof CustomEvent }).CustomEvent =
        class CustomEventPolyfill<T> extends Event {
          detail: T | undefined;
          constructor(type: string, init?: CustomEventInit<T>) {
            super(type, init);
            this.detail = init?.detail;
          }
        } as unknown as typeof CustomEvent;
    }
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete (globalThis as { window?: unknown }).window;
    delete (globalThis as { localStorage?: unknown }).localStorage;
  });

  it("returns an empty array when storage is empty", () => {
    expect(getRecents("patient")).toEqual([]);
    expect(getRecents("billing")).toEqual([]);
  });

  it("records a patient visit and reads it back", () => {
    recordRecent("patient", "P-0001");
    const out = getRecents("patient");
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ patientId: "P-0001", openedAt: now });
  });

  it("orders newest-first and dedupes by patientId", () => {
    now = 1_700_000_000_000;
    recordRecent("patient", "P-0001");
    now = 1_700_000_000_100;
    recordRecent("patient", "P-0002");
    now = 1_700_000_000_200;
    recordRecent("patient", "P-0001"); // re-visit P-0001
    const out = getRecents("patient");
    expect(out.map((entry) => entry.patientId)).toEqual(["P-0001", "P-0002"]);
    expect(out[0].openedAt).toBe(1_700_000_000_200);
  });

  it(`caps stored entries at ${RECENTS_MAX_ENTRIES}`, () => {
    for (let i = 0; i < RECENTS_MAX_ENTRIES + 5; i += 1) {
      now = 1_700_000_000_000 + i * 1_000;
      recordRecent("patient", `P-${i.toString().padStart(4, "0")}`);
    }
    const out = getRecents("patient", 100);
    expect(out).toHaveLength(RECENTS_MAX_ENTRIES);
    expect(out[0].patientId).toBe(`P-${(RECENTS_MAX_ENTRIES + 4).toString().padStart(4, "0")}`);
  });

  it("keeps patient and billing lists independent", () => {
    recordRecent("patient", "P-0001");
    recordRecent("billing", "P-9999");
    expect(getRecents("patient").map((e) => e.patientId)).toEqual(["P-0001"]);
    expect(getRecents("billing").map((e) => e.patientId)).toEqual(["P-9999"]);
  });

  it("ignores blank or whitespace patientIds", () => {
    recordRecent("patient", "");
    recordRecent("patient", "   ");
    expect(getRecents("patient")).toEqual([]);
  });

  it("returns [] when stored JSON is malformed or wrong shape", () => {
    window.localStorage.setItem(KEY_PATIENT, "{not json");
    expect(getRecents("patient")).toEqual([]);
    window.localStorage.setItem(KEY_PATIENT, JSON.stringify("scalar"));
    expect(getRecents("patient")).toEqual([]);
    window.localStorage.setItem(KEY_PATIENT, JSON.stringify([{ patientId: 1 }]));
    expect(getRecents("patient")).toEqual([]);
  });

  it("respects the optional limit parameter on getRecents", () => {
    for (let i = 0; i < 4; i += 1) {
      now = 1_700_000_000_000 + i * 1_000;
      recordRecent("billing", `P-${i}`);
    }
    expect(getRecents("billing", 2)).toHaveLength(2);
  });

  it("returns [] on the server (no window)", () => {
    delete (globalThis as { window?: unknown }).window;
    expect(getRecents("patient")).toEqual([]);
    recordRecent("patient", "P-SSR"); // no-op
    expect(getRecents("patient")).toEqual([]);
  });

  it("writes through to the documented storage keys", () => {
    recordRecent("patient", "P-A");
    recordRecent("billing", "P-B");
    expect(window.localStorage.getItem(KEY_PATIENT)).toContain("P-A");
    expect(window.localStorage.getItem(KEY_BILLING)).toContain("P-B");
  });
});
