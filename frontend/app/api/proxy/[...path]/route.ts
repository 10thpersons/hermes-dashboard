import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://backend:8000';
const API_KEY = process.env.DASHBOARD_API_KEY || 'hermes-dashboard-2026';
const SECRET = API_KEY;

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

async function verifyToken(token: string): Promise<boolean> {
  const [payload, sig] = token.split('.');
  if (!payload || !sig) return false;
  const expected = await hmacSha256Hex(SECRET, payload);
  if (sig !== expected) return false;
  const issuedAt = parseInt(payload, 10);
  const maxAge = 60 * 60 * 24 * 30 * 1000;
  if (Date.now() - issuedAt > maxAge) return false;
  return true;
}

async function handler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const cookieStore = await cookies();
  const session = cookieStore.get('session')?.value;
  if (!session || !(await verifyToken(session))) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { path } = await params;
  const targetPath = '/api/v1/' + path.join('/');
  const url = new URL(targetPath, BACKEND);
  req.nextUrl.searchParams.forEach((v, k) => url.searchParams.set(k, v));

  const body = ['GET', 'HEAD'].includes(req.method)
    ? undefined
    : await req.text();

  const upstream = await fetch(url.toString(), {
    method: req.method,
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json',
    },
    body,
  });

  const data = await upstream.text();
  return new NextResponse(data, {
    status: upstream.status,
    headers: {
      'Content-Type':
        upstream.headers.get('Content-Type') || 'application/json',
    },
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
