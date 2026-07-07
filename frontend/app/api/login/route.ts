import { cookies } from "next/headers";
import { createHmac } from "crypto";
import { NextRequest, NextResponse } from "next/server";

const SECRET = process.env.DASHBOARD_API_KEY || "hermes-dashboard-2026";

// Simple in-memory rate limiter (resets on server restart)
const loginAttempts = new Map<string, { count: number; lastAttempt: number }>();
const MAX_ATTEMPTS = 5;
const WINDOW_MS = 60 * 1000; // 1 minute
const LOCKOUT_MS = 30 * 1000; // 30 second lockout

function makeToken(): string {
  const payload = `${Date.now()}`;
  const sig = createHmac("sha256", SECRET).update(payload).digest("hex");
  return `${payload}.${sig}`;
}

function checkRateLimit(ip: string): { allowed: boolean; retryAfter?: number } {
  const now = Date.now();
  const record = loginAttempts.get(ip);

  if (record) {
    // Check if in lockout period
    if (record.count >= MAX_ATTEMPTS) {
      const elapsed = now - record.lastAttempt;
      if (elapsed < LOCKOUT_MS) {
        return { allowed: false, retryAfter: Math.ceil((LOCKOUT_MS - elapsed) / 1000) };
      }
      // Reset after lockout
      loginAttempts.delete(ip);
    }
    // Reset window if expired
    if (now - record.lastAttempt > WINDOW_MS) {
      loginAttempts.delete(ip);
    }
  }
  return { allowed: true };
}

function recordFailedAttempt(ip: string) {
  const now = Date.now();
  const record = loginAttempts.get(ip);
  if (record && now - record.lastAttempt < WINDOW_MS) {
    record.count++;
    record.lastAttempt = now;
  } else {
    loginAttempts.set(ip, { count: 1, lastAttempt: now });
  }
}

export async function POST(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";

  const rateCheck = checkRateLimit(ip);
  if (!rateCheck.allowed) {
    return NextResponse.json(
      { error: `Too many attempts. Try again in ${rateCheck.retryAfter}s.` },
      { status: 429, headers: { "Retry-After": String(rateCheck.retryAfter) } }
    );
  }

  const { password } = await req.json();
  if (password !== SECRET) {
    recordFailedAttempt(ip);
    return NextResponse.json({ error: "Invalid password" }, { status: 401 });
  }

  // Clear rate limit on success
  loginAttempts.delete(ip);

  const token = makeToken();
  const cookieStore = await cookies();
  cookieStore.set("session", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 30,
    path: "/",
  });
  return NextResponse.json({ ok: true });
}
