/**
 * Session token verification for the frontend middleware.
 *
 * Mirrors the Python implementation in src/bilun/api/auth.py exactly so that
 * the Next.js middleware and the backend verify the SAME token format. The
 * token is `base64url(payload).base64url(hmac_sha256(payload))` where the
 * payload is `<username>.<expires_at_unix>`. Only the signature is verified
 * here — the cookie is httpOnly so client JS never reads it directly; the
 * middleware reads it from the request cookies.
 *
 * The HMAC key (BILUN_SESSION_SECRET) must match the backend's. It is read
 * server-side only (never NEXT_PUBLIC_) and is safe to use in the middleware
 * edge runtime.
 */

const SESSION_COOKIE = "bilun:session";

/**
 * Coerce a Uint8Array to a BufferSource acceptable to Web Crypto's
 * `crypto.subtle`. TS 5.7+ widens Uint8Array's buffer to ArrayBufferLike
 * (incl. SharedArrayBuffer), but subtle.importKey/sign require a concrete
 * ArrayBuffer-backed view. At runtime these are always ArrayBuffer-backed;
 * the cast is purely to satisfy the type checker.
 */
function asBufferSource(bytes: Uint8Array): BufferSource {
  return bytes as unknown as BufferSource;
}

function base64UrlDecode(input: string): Uint8Array {
  // base64url → base64, pad to length 4, decode via atob.
  const padded = input.replace(/-/g, "+").replace(/_/g, "/");
  const b64 = padded + "=".repeat((4 - (padded.length % 4)) % 4);
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

async function constantTimeEqual(a: Uint8Array, b: Uint8Array): Promise<boolean> {
  const key = await crypto.subtle.importKey(
    "raw",
    asBufferSource(new Uint8Array(32)),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  // HMAC both and compare digests — a constant-time-ish comparison without
  // needing Node's timingSafeEqual in the edge runtime.
  const [da, db] = await Promise.all([
    crypto.subtle.sign("HMAC", key, asBufferSource(a)),
    crypto.subtle.sign("HMAC", key, asBufferSource(b)),
  ]);
  const va = new Uint8Array(da);
  const vb = new Uint8Array(db);
  let diff = 0;
  for (let i = 0; i < va.length; i++) {
    diff |= va[i] ^ vb[i];
  }
  return diff === 0;
}

/**
 * Verify a session token against the configured secret.
 * Returns true if the signature is valid and the token has not expired.
 */
export async function verifySessionToken(
  token: string,
  secret: string,
): Promise<boolean> {
  if (!token || token.split(".").length !== 2) {
    return false;
  }
  const [payloadB64, sigB64] = token.split(".");
  let payloadBytes: Uint8Array;
  let providedSig: Uint8Array;
  try {
    payloadBytes = base64UrlDecode(payloadB64);
    providedSig = base64UrlDecode(sigB64);
  } catch {
    return false;
  }
  // Check expiry before crypto: parse "<username>.<expires_at>".
  const payload = new TextDecoder().decode(payloadBytes);
  const dotIdx = payload.lastIndexOf(".");
  if (dotIdx < 0) {
    return false;
  }
  const expStr = payload.slice(dotIdx + 1);
  const expiresAt = Number(expStr);
  if (!Number.isFinite(expiresAt) || expiresAt <= Math.floor(Date.now() / 1000)) {
    return false;
  }
  const key = await crypto.subtle.importKey(
    "raw",
    asBufferSource(new TextEncoder().encode(secret)),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const expectedSig = new Uint8Array(
    await crypto.subtle.sign("HMAC", key, asBufferSource(payloadBytes)),
  );
  if (expectedSig.length !== providedSig.length) {
    return false;
  }
  return constantTimeEqual(expectedSig, providedSig);
}

export { SESSION_COOKIE };
