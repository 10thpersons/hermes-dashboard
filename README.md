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

# Build and run
docker compose up --build -d

# Access
open http://localhost:8080
```

## Services

| Service  | Port | Description                 |
| -------- | ---- | --------------------------- |
| Nginx    | 8080 | Reverse proxy (entry point) |
| Frontend | 3001 | Next.js UI                  |
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
| DASHBOARD_API_KEY | hermes-dashboard-2026 | API authentication key |
