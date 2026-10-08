// Error texts that are safe to print, log and store in run-meta.json.
//
// Playwright's request errors end in a "Call log:" that echoes the request
// headers, and with --identity dev one of them is `cookie: bilun:session=<token>`
// (valid for 8 hours). The same text carries ANSI colour codes. Everything the
// tool prints or writes about an error goes through safeMessage().

const SECRETS = new Set();

/** Remember a value (session token, signing secret) that must never be printed or stored. */
export function registerSecret(value) {
  if (value) SECRETS.add(value);
}

export function safeMessage(error) {
  let text = String(error?.message ?? error);
  text = text.replace(/\u001b\[[0-9;]*m/g, "");
  text = text.split(/\n\s*Call log:/)[0];
  for (const secret of SECRETS) text = text.split(secret).join("[redacted]");
  text = text.replace(/(bilun:session=)[^\s;"']+/g, "$1[redacted]");
  return text.trim();
}

export function clearSecrets() {
  SECRETS.clear();
}
