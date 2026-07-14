import { NextRequest, NextResponse } from 'next/server';

const PUBLIC_PATHS = ['/login', '/api/login'];

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

async function verifyToken(token: string, secret: string): Promise<boolean> {
  const [payload, sig] = token.split('.');
  if (!payload || !sig) return false;
  const expected = await hmacSha256Hex(secret, payload);
  if (sig !== expected) return false;
  const issuedAt = parseInt(payload, 10);
  const maxAge = 60 * 60 * 24 * 30 * 1000;
  if (Date.now() - issuedAt > maxAge) return false;
  return true;
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p)))
    return NextResponse.next();

  const session = req.cookies.get('session')?.value;
  const secret = process.env.DASHBOARD_API_KEY || 'hermes-dashboard-2026';

  if (!session || !(await verifyToken(session, secret))) {
    const loginUrl = new URL('/login', req.url);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|health.json).*)'],
};
