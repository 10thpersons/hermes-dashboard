# Hermes Agent Operations Dashboard

Single-pane-of-glass web dashboard for monitoring and managing a Hermes Agent instance.

## Stack

- **Frontend:** Next.js 14 + Tailwind CSS + TanStack Query
- **Backend:** FastAPI (Python 3.12)
- **Reverse Proxy:** Nginx
- **Deployment:** Docker Compose

## Quick Start

```bash
# Copy environment file
cp .env.example .env

# Before starting, set DASHBOARD_API_KEY in .env to a newly generated random secret.
# Use at least 32 printable ASCII characters without whitespace (e.g. 32 random
# bytes encoded as 64 hex characters). Use the same key for frontend and backend.

# Build and run
docker compose up --build -d

# Access
open http://localhost:8080
```

## Services

| Service  | Port | Description                 |
| -------- | ---- | --------------------------- |
| Nginx    | 8080 | Reverse proxy (entry point) |
| Frontend | internal 3000 | Next.js UI (nginx only) |
| Backend  | 8000 | FastAPI API                 |

## API Endpoints

All endpoints require `X-API-Key` header.

- `GET /api/v1/sessions` — List sessions (supports `?q=` FTS5 search)
- `GET /api/v1/sessions/{id}` — Session messages
- `GET /api/v1/cron` — Cron jobs
- `POST /api/v1/cron/{id}/toggle` — Enable/disable cron job
- `GET /api/v1/knowledge/memory` — Memory files
- `GET /api/v1/knowledge/skills` — Skill files
- `GET /api/v1/knowledge/souls` — SOUL files
- `GET /api/v1/config` — Read config.yaml
- `PUT /api/v1/config` — Update config.yaml
- `GET /api/v1/system/health` — System health
- `GET /api/v1/obsidian/tree` — Obsidian vault tree
- `GET /api/v1/obsidian/file` — Read Obsidian file

## Environment Variables

| Variable          | Default               | Description            |
| ----------------- | --------------------- | ---------------------- |
| DASHBOARD_API_KEY | Required; no default | Shared admin login/API key: random, at least 32 printable ASCII characters, no whitespace, at least 8 distinct characters |

Invalid or missing key configuration stops backend startup; frontend authentication
and proxy operations return a generic 503 without issuing a session or forwarding.
Key rotation invalidates existing sessions. Length/variety checks cannot establish
entropy: generate random material rather than choosing a memorable password.

Login throttling uses `X-Dashboard-Client-IP`, overwritten by nginx from the actual
peer address. Keep the frontend reachable only by that trusted ingress (including
for non-Compose deployments); never expose its port directly to untrusted clients.
The checked-in Compose file no longer publishes frontend port 3001. Use port 8080.
A preceding proxy shares its peer bucket unless nginx is separately configured with
explicitly trusted real-IP hops; never trust arbitrary forwarded headers. Missing
identity shares one conservative limiter bucket. Limits are process-local and reset
on restart; this is not distributed rate limiting.

Affiliate publish now requires `{ "draft_id": "<listed id>", "override": false }`;
reject takes an array of listed string IDs, not positional indices. Reload old
browser tabs after upgrading. Existing drafts receive deterministic monotonic IDs
in stored order, persisted before listing; duplicate existing IDs fail closed.
Deploy the bundled bot source changes together with the dashboard, including to any
external checkout selected by `AFFILIATE_BOT_DIR`. The identity counter must be
preserved with the ledger. This change does not repair publication readiness or
provide cross-process transactional publication/quota guarantees.
