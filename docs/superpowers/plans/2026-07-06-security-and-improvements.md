# Hermes Dashboard — Security & Improvements Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all critical security vulnerabilities and quality issues found in the code review, then apply minor polish.

**Architecture:** FastAPI backend (Python) proxied by Nginx, Next.js 14 frontend. Auth moves from NEXT_PUBLIC browser-exposed key to a login page + httpOnly cookie + server-side Next.js proxy route that holds the API key.

**Tech Stack:** FastAPI, Python 3.11, Next.js 14 App Router, React Query, Tailwind CSS, Docker Compose, Nginx

## Global Constraints

- Do NOT break existing API contract — same routes, same response shapes
- No new runtime dependencies on the backend (stdlib + existing packages only)
- Frontend: only add `iron-session` or use Node's built-in `crypto` — no heavy auth libs
- All env vars documented in `.env.example`
- Docker Compose must still work after changes

---

## Task 1: Path Traversal Fix

**Files:**
- Modify: `backend/services/hermes_data.py`

**Interfaces:**
- `get_obsidian_file(file_path: str) -> str | None` — unchanged signature, now safe
- `get_skill_detail(skill_path: str) -> str | None` — unchanged signature, now safe

- [ ] **Step 1: Add path safety helper to hermes_data.py**

Open `backend/services/hermes_data.py`. Add this helper function right after the imports:

```python
def _safe_path(base: Path, user_path: str) -> Path | None:
    """Return resolved path only if it stays inside base. Prevents traversal."""
    try:
        resolved = (base / user_path).resolve()
        base_resolved = base.resolve()
        resolved.relative_to(base_resolved)
        return resolved
    except (ValueError, OSError):
        return None
```

- [ ] **Step 2: Protect get_skill_detail**

Find `get_skill_detail` and replace its body:

```python
def get_skill_detail(skill_path: str):
    full_path = _safe_path(SKILLS_DIR, skill_path)
    if not full_path or not full_path.exists():
        return None
    return full_path.read_text(encoding="utf-8", errors="replace")
```

- [ ] **Step 3: Protect get_obsidian_file**

Find `get_obsidian_file` and replace its body:

```python
def get_obsidian_file(file_path: str):
    full_path = _safe_path(OBSIDIAN_VAULT, file_path)
    if not full_path or not full_path.exists() or not full_path.is_file():
        return None
    return full_path.read_text(encoding="utf-8", errors="replace")
```

- [ ] **Step 4: Commit**

```bash
cd /Users/nurulniza/hermes-gh
git add backend/services/hermes_data.py
git commit -m "fix: prevent path traversal in obsidian and skills file reads"
```

---

## Task 2: WebSocket Memory Leak + Authentication

**Files:**
- Modify: `backend/main.py`

**Interfaces:**
- `ws_session(websocket, session_id, api_key)` — now requires `api_key` query param
- `ws_agent_status(websocket, api_key)` — now requires `api_key` query param

- [ ] **Step 1: Fix WebSocket auth and cleanup in main.py**

Open `backend/main.py`. Replace the entire WebSocket section (from `connected_clients` to end of file) with:

```python
connected_clients: set[WebSocket] = set()


@app.websocket("/ws/sessions/{session_id}")
async def ws_session(websocket: WebSocket, session_id: str, api_key: str = ""):
    if api_key != API_KEY:
        await websocket.close(code=4001)
        return
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "ack", "session_id": session_id}))
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
    finally:
        connected_clients.discard(websocket)


@app.websocket("/ws/agent-status")
async def ws_agent_status(websocket: WebSocket, api_key: str = ""):
    if api_key != API_KEY:
        await websocket.close(code=4001)
        return
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "status", "agents": []}))
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
    finally:
        connected_clients.discard(websocket)
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nurulniza/hermes-gh
git add backend/main.py
git commit -m "fix: add WebSocket auth and fix memory leak in connected_clients"
```

---

## Task 3: Add Knowledge Directory Size Limit

**Files:**
- Modify: `backend/services/hermes_data.py`

- [ ] **Step 1: Update _read_markdown_dir to cap results**

Find `_read_markdown_dir` and replace it with:

```python
def _read_markdown_dir(directory: Path, max_files: int = 200) -> list[dict]:
    """Read .md files from a directory tree, capped at max_files."""
    items = []
    if not directory.exists():
        return items
    for md_file in sorted(directory.rglob("*.md"))[:max_files]:
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            items.append({
                "name": md_file.stem,
                "path": str(md_file),
                "relative": str(md_file.relative_to(directory)),
                "content": content[:10000],
                "size": len(content),
            })
        except Exception:
            continue
    return items
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nurulniza/hermes-gh
git add backend/services/hermes_data.py
git commit -m "fix: cap knowledge directory reads at 200 files to prevent memory issues"
```

---

## Task 4: Fix ALLOWED_ORIGINS in Docker Compose

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Add ALLOWED_ORIGINS to backend service env**

Open `docker-compose.yml`. In the `backend` service `environment` section, add:

```yaml
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-http://localhost:3000,http://localhost:8080}
```

- [ ] **Step 2: Document in .env.example**

Open `.env.example`. Add this line:

```
ALLOWED_ORIGINS=http://yourdomain.com
```

- [ ] **Step 3: Commit**

```bash
cd /Users/nurulniza/hermes-gh
git add docker-compose.yml .env.example
git commit -m "fix: pass ALLOWED_ORIGINS to backend container via docker-compose"
```

---

## Task 5: Login Page + Remove Exposed API Key

**Files:**
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/api/login/route.ts`
- Create: `frontend/app/api/proxy/[...path]/route.ts`
- Create: `frontend/middleware.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `docker-compose.yml`
- Modify: `.env.example`

**Interfaces:**
- `POST /api/login` body: `{ password: string }` → sets httpOnly `session` cookie, returns `{ ok: true }`
- `GET|POST|PUT|DELETE /api/proxy/[...path]` → proxies to backend with API key header (requires valid session cookie)
- `apiFetch(path, options)` — same signature, now calls `/api/proxy/...` instead of backend directly

- [ ] **Step 1: Create Next.js login API route**

Create `frontend/app/api/login/route.ts`:

```typescript
import { cookies } from "next/headers";
import { createHmac } from "crypto";
import { NextRequest, NextResponse } from "next/server";

const SECRET = process.env.DASHBOARD_API_KEY || "hermes-dashboard-2026";

function makeToken(): string {
  const payload = `${Date.now()}`;
  const sig = createHmac("sha256", SECRET).update(payload).digest("hex");
  return `${payload}.${sig}`;
}

export function verifyToken(token: string): boolean {
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return false;
  const expected = createHmac("sha256", SECRET).update(payload).digest("hex");
  return sig === expected;
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
```

- [ ] **Step 2: Create proxy API route**

Create `frontend/app/api/proxy/[...path]/route.ts`:

```typescript
import { cookies } from "next/headers";
import { createHmac } from "crypto";
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL || "http://backend:8000";
const API_KEY = process.env.DASHBOARD_API_KEY || "hermes-dashboard-2026";
const SECRET = API_KEY;

function verifyToken(token: string): boolean {
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return false;
  const expected = createHmac("sha256", SECRET).update(payload).digest("hex");
  return sig === expected;
}

async function handler(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const cookieStore = await cookies();
  const session = cookieStore.get("session")?.value;
  if (!session || !verifyToken(session)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { path } = await params;
  const targetPath = "/api/v1/" + path.join("/");
  const url = new URL(targetPath, BACKEND);
  req.nextUrl.searchParams.forEach((v, k) => url.searchParams.set(k, v));

  const body = ["GET", "HEAD"].includes(req.method) ? undefined : await req.text();

  const upstream = await fetch(url.toString(), {
    method: req.method,
    headers: {
      "X-API-Key": API_KEY,
      "Content-Type": "application/json",
    },
    body,
  });

  const data = await upstream.text();
  return new NextResponse(data, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("Content-Type") || "application/json" },
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
```

- [ ] **Step 3: Create middleware.ts**

Create `frontend/middleware.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { createHmac } from "crypto";

const PUBLIC_PATHS = ["/login", "/api/login"];

function verifyToken(token: string, secret: string): boolean {
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return false;
  const expected = createHmac("sha256", secret).update(payload).digest("hex");
  return sig === expected;
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
```

- [ ] **Step 4: Create login page**

Create `frontend/app/login/page.tsx`:

```typescript
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (res.ok) {
        router.push("/");
        router.refresh();
      } else {
        setError("Wrong password. Try again.");
      }
    } catch {
      setError("Connection failed. Is the server running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)]">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="font-mono text-2xl font-bold tracking-widest text-[var(--accent)]">HERMES</span>
          <p className="text-sm text-[var(--text-secondary)] mt-2">Enter your dashboard password</p>
        </div>
        <form onSubmit={handleSubmit} className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6 space-y-4">
          <div>
            <label className="block text-xs text-[var(--text-secondary)] mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
              required
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
            />
          </div>
          {error && <p className="text-xs text-[var(--error)]">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Update frontend/lib/api.ts to use proxy**

Replace the entire content of `frontend/lib/api.ts` with:

```typescript
const API_BASE = "/api/proxy";

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

export async function apiFetch<T = any>(path: string, options: FetchOptions = {}): Promise<T> {
  const { params, ...init } = options;
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }

  const res = await fetch(url.toString(), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export const fetchers = {
  sessions: (limit = 50, offset = 0, q?: string) =>
    apiFetch("/sessions", { params: { limit: String(limit), offset: String(offset), ...(q ? { q } : {}) } }),

  sessionDetail: (id: string) =>
    apiFetch(`/sessions/${id}`),

  cronJobs: () =>
    apiFetch("/cron"),

  toggleCron: (id: string, enabled: boolean) =>
    apiFetch(`/cron/${id}/toggle`, { method: "POST", body: JSON.stringify({ enabled }) }),

  memory: () =>
    apiFetch("/knowledge/memory"),

  skills: () =>
    apiFetch("/knowledge/skills"),

  souls: () =>
    apiFetch("/knowledge/souls"),

  config: () =>
    apiFetch("/config"),

  updateConfig: (updates: Record<string, any>) =>
    apiFetch("/config", { method: "PUT", body: JSON.stringify({ updates }) }),

  systemHealth: () =>
    apiFetch("/system/health"),

  obsidianTree: (path = "") =>
    apiFetch("/obsidian/tree", { params: { path } }),

  obsidianFile: (path: string) =>
    apiFetch("/obsidian/file", { params: { path } }),
};
```

- [ ] **Step 6: Update docker-compose.yml — add BACKEND_URL, remove NEXT_PUBLIC_API_KEY**

In `docker-compose.yml` frontend service environment, replace:
```yaml
      - NEXT_PUBLIC_API_URL=/api/v1
      - NEXT_PUBLIC_API_KEY=${DASHBOARD_API_KEY:-hermes-dashboard-2026}
```
with:
```yaml
      - BACKEND_URL=http://backend:8000
      - DASHBOARD_API_KEY=${DASHBOARD_API_KEY:-hermes-dashboard-2026}
```

- [ ] **Step 7: Update .env.example**

Replace content of `.env.example` with:
```
DASHBOARD_API_KEY=change-me-to-something-secret
ALLOWED_ORIGINS=http://yourdomain.com
```

- [ ] **Step 8: Commit**

```bash
cd /Users/nurulniza/hermes-gh
git add frontend/app/login/page.tsx frontend/app/api/login/route.ts frontend/app/api/proxy frontend/middleware.ts frontend/lib/api.ts docker-compose.yml .env.example
git commit -m "feat: add login page and server-side proxy — API key no longer exposed to browser"
```

---

## Task 6: Remove Unused zustand Dependency

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json` (regenerated automatically)

- [ ] **Step 1: Remove zustand from package.json**

Open `frontend/package.json`. Remove the `"zustand": "^4.5.0"` line from `dependencies`.

- [ ] **Step 2: Commit**

```bash
cd /Users/nurulniza/hermes-gh/frontend
npm install
cd ..
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: remove unused zustand dependency"
```

---

## Task 7: Mobile Sidebar

**Files:**
- Modify: `frontend/components/sidebar.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Update sidebar.tsx with mobile toggle**

Replace entire content of `frontend/components/sidebar.tsx` with:

```typescript
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  BookOpen,
  Clock,
  Settings,
  Activity,
  Menu,
  X,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/sessions", label: "Sessions", icon: MessageSquare },
  { href: "/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/automation", label: "Automation", icon: Clock },
  { href: "/config", label: "Config", icon: Settings },
  { href: "/system", label: "System", icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const navLinks = (
    <nav className="flex-1 p-3 space-y-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || (href !== "/" && pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            onClick={() => setOpen(false)}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              active
                ? "bg-[var(--accent)]/10 text-[var(--accent)]"
                : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <Icon size={18} />
            {label}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-[var(--border)] bg-[var(--bg-secondary)]">
        <span className="font-mono text-lg font-bold tracking-widest text-[var(--accent)]">HERMES</span>
        <button onClick={() => setOpen((o) => !o)} className="text-[var(--text-secondary)]">
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="w-56 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col">
            <div className="p-5 border-b border-[var(--border)] flex items-center justify-between">
              <span className="font-mono text-lg font-bold tracking-widest text-[var(--accent)]">HERMES</span>
              <button onClick={() => setOpen(false)}><X size={18} /></button>
            </div>
            {navLinks}
            <div className="p-4 text-xs text-[var(--text-secondary)] border-t border-[var(--border)]">v1.0.0</div>
          </div>
          <div className="flex-1" onClick={() => setOpen(false)} />
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-56 shrink-0 border-r border-[var(--border)] bg-[var(--bg-secondary)] flex-col">
        <div className="p-5 border-b border-[var(--border)]">
          <span className="font-mono text-lg font-bold tracking-widest text-[var(--accent)]">HERMES</span>
        </div>
        {navLinks}
        <div className="p-4 text-xs text-[var(--text-secondary)] border-t border-[var(--border)]">v1.0.0</div>
      </aside>
    </>
  );
}
```

- [ ] **Step 2: Update layout.tsx for mobile**

Open `frontend/app/layout.tsx`. Replace `<div className="flex h-screen overflow-hidden">` with `<div className="flex flex-col md:flex-row h-screen overflow-hidden">`.

- [ ] **Step 3: Commit**

```bash
cd /Users/nurulniza/hermes-gh
git add frontend/components/sidebar.tsx frontend/app/layout.tsx
git commit -m "feat: add mobile-responsive sidebar with slide-out drawer"
```

---

## Task 8: Error Display for Failed API Calls

**Files:**
- Create: `frontend/components/error-banner.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/sessions/page.tsx`

- [ ] **Step 1: Create reusable error banner component**

Create `frontend/components/error-banner.tsx`:

```typescript
export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-[var(--error)]/30 bg-[var(--error)]/10 px-4 py-3 text-sm text-[var(--error)]">
      {message}
    </div>
  );
}
```

- [ ] **Step 2: Add error display to sessions page**

In `frontend/app/sessions/page.tsx`, add the import and use it. After the `useQuery` line, destructure `error` and `isError`:

```typescript
const { data, isLoading, isError } = useQuery({
  queryKey: ["sessions", search, page],
  queryFn: () => fetchers.sessions(limit, page * limit, search || undefined),
});
```

Add `import { ErrorBanner } from "@/components/error-banner";` at the top.

After `<h1 className="text-2xl font-bold">Sessions</h1>` add:

```typescript
{isError && <ErrorBanner message="Could not load sessions. Is the backend running?" />}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/nurulniza/hermes-gh
git add frontend/components/error-banner.tsx frontend/app/sessions/page.tsx frontend/app/page.tsx
git commit -m "feat: show error banner when API calls fail"
```

---

## Final: Push to GitHub

- [ ] **Push all commits**

```bash
cd /Users/nurulniza/hermes-gh
git push origin main
```
