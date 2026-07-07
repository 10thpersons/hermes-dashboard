import { NextRequest, NextResponse } from "next/server";
import { createHmac } from "crypto";

const PUBLIC_PATHS = ["/login", "/api/login"];

function verifyToken(token: string, secret: string): boolean {
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return false;
  const expected = createHmac("sha256", secret).update(payload).digest("hex");
  if (sig !== expected) return false;
  // Check token age (max 30 days)
  const issuedAt = parseInt(payload, 10);
  const maxAge = 60 * 60 * 24 * 30 * 1000; // 30 days in ms
  if (Date.now() - issuedAt > maxAge) return false;
  return true;
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) return NextResponse.next();

  const session = req.cookies.get("session")?.value;
  const secret = process.env.DASHBOARD_API_KEY || "hermes-dashboard-2026";

  if (!session || !verifyToken(session, secret)) {
    const loginUrl = new URL("/login", req.url);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|health.json).*)"],
};
