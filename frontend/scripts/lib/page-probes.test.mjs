import fs from "node:fs";
import { describe, expect, it } from "vitest";
import { runProbeSelfTest } from "./probe-selftest.mjs";

// The visibility probes decide what the default view shows, and the default-view
// honesty check of --compare stands on them. They can only be tested in a real
// browser, so this runs the built-in page in system Chrome. Where Chrome is not
// installed the test is SKIPPED (vitest prints it as skipped); the same checks
// run with `node scripts/capture-screens.mjs --self-test`.
const CHROME_CANDIDATES = [process.env.BILUN_CHROME_PATH, "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/opt/google/chrome/chrome"];
const chromePath = CHROME_CANDIDATES.find((candidate) => candidate && fs.existsSync(candidate));

describe.skipIf(!chromePath)("visibility probes in a real browser", () => {
  it("keep visible text, drop text that CSS collapsed (also with padding, border, scale or clip-path) and restore the page", async () => {
    const { problems } = await runProbeSelfTest({ executablePath: chromePath });
    expect(problems).toEqual([]);
  }, 60_000);
});
