import { afterEach, describe, expect, it } from "vitest";
import { clearSecrets, registerSecret, safeMessage } from "./safe-message.mjs";

afterEach(clearSecrets);

describe("safeMessage", () => {
  const playwrightError = [
    "\u001b[2mapiRequestContext.get: \u001b[22mconnect ECONNREFUSED 127.0.0.1:13100",
    "Call log:",
    "\u001b[2m  - → GET http://127.0.0.1:13100/api/auth/me\u001b[22m",
    "\u001b[2m  -   cookie: bilun:locale=en; bilun:session=TOKEN.SIGNATURE\u001b[22m",
  ].join("\n");

  it("drops the call log that echoes request headers, and the colour codes", () => {
    const text = safeMessage(new Error(playwrightError));
    expect(text).toBe("apiRequestContext.get: connect ECONNREFUSED 127.0.0.1:13100");
    expect(text).not.toMatch(/bilun:session|TOKEN|Call log|\u001b/);
  });

  it("redacts a registered secret and any session cookie left in the text", () => {
    registerSecret("s3cr3t-value");
    expect(safeMessage("failed with s3cr3t-value in it")).toBe("failed with [redacted] in it");
    expect(safeMessage("header bilun:session=abc.def; other=1")).toBe("header bilun:session=[redacted]; other=1");
  });

  it("accepts strings and keeps ordinary messages", () => {
    expect(safeMessage("GET /api/auth/me -> 500")).toBe("GET /api/auth/me -> 500");
    expect(safeMessage(undefined)).toBe("undefined");
  });
});
