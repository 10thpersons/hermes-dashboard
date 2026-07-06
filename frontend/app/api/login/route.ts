import { cookies } from "next/headers";
import { createHmac } from "crypto";
import { NextRequest, NextResponse } from "next/server";

const SECRET = process.env.DASHBOARD_API_KEY || "hermes-dashboard-2026";

function makeToken(): string {
  const payload = `${Date.now()}`;
  const sig = createHmac("sha256", SECRET).update(payload).digest("hex");
  return `${payload}.${sig}`;
}

export async function POST(req: NextRequest) {
  const { password } = await req.json();
  if (password !== SECRET) {
    return NextResponse.json({ error: "Invalid password" }, { status: 401 });
  }
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
