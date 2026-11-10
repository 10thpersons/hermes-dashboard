import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';

import { dashboardKey } from '@/lib/dashboard-key';
import { createLoginLimiter, loginIdentity } from '@/lib/login-limiter.mjs';

const limiter = createLoginLimiter();

async function hmacSha256Hex(secret: string, payload: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(payload));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

async function makeToken(secret: string): Promise<string> {
  const payload = `${Date.now()}`;
  const sig = await hmacSha256Hex(secret, payload);
  return `${payload}.${sig}`;
}

export async function POST(req: NextRequest) {
  const secret = dashboardKey();
  if (!secret) {
    return NextResponse.json({ error: 'Authentication is not configured' }, { status: 503 });
  }
  const ip = loginIdentity(req.headers);
  const rateCheck = limiter.check(ip);
  if (!rateCheck.allowed) {
    return NextResponse.json(
      { error: `Too many attempts. Try again in ${rateCheck.retryAfter}s.` },
      { status: 429, headers: { 'Retry-After': String(rateCheck.retryAfter) } },
    );
  }

  let password: unknown;
  try {
    password = (await req.json())?.password;
  } catch {
    limiter.fail(ip);
    return NextResponse.json({ error: 'Invalid request' }, { status: 400 });
  }
  if (password !== secret) {
    limiter.fail(ip);
    return NextResponse.json({ error: 'Invalid password' }, { status: 401 });
  }

  // Clear rate limit on success
  limiter.clear(ip);

  const token = await makeToken(secret);
  const cookieStore = await cookies();
  cookieStore.set('session', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 30,
    path: '/',
  });
  return NextResponse.json({ ok: true });
}
