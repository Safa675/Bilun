import { describe, expect, it } from "vitest";
import { config } from "./middleware";

// Next compiles "/(<regex>)": the group is matched against the path after the leading slash.
const group = /^\/\((.*)\)$/.exec(config.matcher[0])![1];
const guarded = (path: string) => new RegExp(`^${group}$`).test(path.slice(1));

describe("middleware matcher", () => {
  it("lets public static assets, including the self-hosted fonts, bypass page authorization", () => {
    for (const path of [
      "/fonts/inter/normal-latin.woff2",
      "/fonts/fraunces/italic-latin-ext.woff2",
      "/brand/full.png",
      "/favicon.ico",
      "/_next/static/chunks/main.js",
      "/_next/image",
    ]) {
      expect(guarded(path), path).toBe(false);
    }
  });

  it("still guards every other path, including look-alikes", () => {
    for (const path of ["/", "/patient/SENTETIK-HASTA-0003", "/login", "/fontsx/inter.woff2", "/secret.woff2", "/api/patients"]) {
      expect(guarded(path), path).toBe(true);
    }
  });
});
