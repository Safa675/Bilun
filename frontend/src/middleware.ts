import { NextResponse, type NextRequest } from "next/server";
import { canUseBilling, canUseDeveloper, isBillingPage, requestsDeveloper } from "@/lib/auth";
import { getServerIdentity } from "@/lib/authServer";

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|brand/|fonts/).*)"],
};

export async function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  // The backend is the API authority; never convert an API denial into login HTML.
  // The local feedback handler checks the same identity independently.
  if (pathname === "/api" || pathname.startsWith("/api/") || pathname === "/health") {
    return NextResponse.next();
  }
  const noCache = (response: NextResponse) => {
    response.headers.set("Cache-Control", "private, no-store");
    return response;
  };
  if (pathname === "/login") return noCache(NextResponse.next());

  const identity = await getServerIdentity(request.headers.get("cookie") ?? "");
  const developerPage = requestsDeveloper(pathname, searchParams);
  if ((developerPage && canUseDeveloper(identity)) || (!developerPage && isBillingPage(pathname) && canUseBilling(identity))) {
    return noCache(NextResponse.next());
  }
  if (!isBillingPage(pathname) && !developerPage) {
    return noCache(new NextResponse("Not found", { status: 404 }));
  }
  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.search = developerPage ? "?access=developer" : "";
  return noCache(NextResponse.redirect(loginUrl));
}
