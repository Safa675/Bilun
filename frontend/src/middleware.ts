/**
 * Session gate middleware.
 *
 * Every request without a valid `bilun:session` cookie is redirected to
 * /login. This is the UI-side layer of defense; the backend enforces the same
 * token on /api/* independently (see src/bilun/api/__init__.py).
 *
 * Auth fails closed when ``BILUN_SESSION_SECRET`` is unset unless
 * ``BILUN_AUTH_OPTIONAL=1`` (local dev / pytest only). Production MUST set
 * the secret and leave ``BILUN_AUTH_OPTIONAL`` unset.
 */

import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, verifySessionToken } from "@/lib/sessionToken";

const LOGIN_PATH = "/login";
// Login/logout API must be reachable without a session — otherwise the login
// form's POST /api/auth/login is redirected to /login and credentials look "wrong".
// /api/health and /api/feedback are exact paths, not prefixes.
const PUBLIC_PATHS = [LOGIN_PATH, "/api/health", "/api/feedback"];
/** Auth endpoints must stay reachable before a session exists. */
const PUBLIC_PREFIXES = ["/api/auth/"];

// Match all routes except Next.js internals and static assets.
export const config = {
  matcher: [
    /*
     * Match everything except:
     * - _next/static, _next/image, favicon (static assets)
     * - /_next/data (build output)
     */
    "/((?!_next/static|_next/image|_next/data|favicon.ico).*)",
  ],
};

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return true;
  }
  return PUBLIC_PREFIXES.some(
    (prefix) => pathname === prefix.slice(0, -1) || pathname.startsWith(prefix),
  );
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Fail closed unless explicitly opted out for local dev.
  const authOptional = ["1", "true", "yes"].includes(
    process.env.BILUN_AUTH_OPTIONAL?.trim().toLowerCase() ?? "",
  );
  const secret = process.env.BILUN_SESSION_SECRET?.trim();
  if (!secret) {
    if (authOptional) {
      return NextResponse.next();
    }
    if (!isPublicPath(pathname)) {
      const loginUrl = request.nextUrl.clone();
      loginUrl.pathname = LOGIN_PATH;
      loginUrl.search = "";
      return NextResponse.redirect(loginUrl);
    }
    return NextResponse.next();
  }

  // Public paths (login page + auth/health APIs) pass through.
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  const token = request.cookies.get(SESSION_COOKIE)?.value ?? "";
  const valid = token ? await verifySessionToken(token, secret) : false;

  if (!valid) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = LOGIN_PATH;
    loginUrl.search = "";
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}
