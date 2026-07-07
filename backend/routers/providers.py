"""VansRoute provider health router.

Reads provider connection status and available models from VansRoute
(a Docker container named 'vansrouter' on port 3003).

Primary path: VansRoute HTTP API (http://localhost:3003).
Fallback:  SQLite via `docker exec vansrouter node -e ...` for provider
           connection details, since the /dashboard/api/providers endpoint
           requires an authenticated session cookie that we don't hold.
"""
import json
import os
import subprocess
import urllib.request
import urllib.error
from typing import Any

from fastapi import APIRouter

router = APIRouter()

VANSROUTE_URL = os.getenv("VANSROUTE_URL", "http://localhost:3003")
VANSROUTE_API_KEY = os.getenv("VANSROUTE_API_KEY", "")
VANSROUTE_CONTAINER = os.getenv("VANSROUTE_CONTAINER", "vansrouter")
VANSROUTE_DB_PATH = os.getenv("VANSROUTE_DB_PATH", "/app/data/db/data.sqlite")

# How long to wait for VansRoute HTTP responses before falling back.
_HTTP_TIMEOUT = 8.0


def _models_from_http() -> list[dict[str, Any]] | None:
    """Fetch /v1/models from VansRoute. Returns None on failure.

    Uses stdlib urllib so no extra dependency is required.
    """
    if not VANSROUTE_API_KEY:
        return None
    url = f"{VANSROUTE_URL}/v1/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {VANSROUTE_API_KEY}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        data = payload.get("data", [])
        return [
            {"id": m.get("id", ""), "object": m.get("object", "model"),
             "owned_by": m.get("owned_by", "")}
            for m in data
        ]
    except Exception:
        return None


def _providers_from_sqlite() -> list[dict[str, Any]]:
    """Query VansRoute SQLite directly via docker exec (fallback / source of truth
    for per-connection status, since the dashboard API needs a session cookie)."""
    # Use better-sqlite3 inside the container to read the DB read-only and
    # return JSON on stdout. We pass a small node script via -e.
    script = (
        "const Database=require('better-sqlite3');"
        f"const db=new Database('{VANSROUTE_DB_PATH}',{{readonly:true}});"
        "const rows=db.prepare('SELECT id,provider,data FROM providerConnections').all();"
        "process.stdout.write(JSON.stringify(rows));"
    )
    try:
        result = subprocess.run(
            ["docker", "exec", VANSROUTE_CONTAINER, "node", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return [{"error": f"docker exec failed: {result.stderr.strip()[:200]}"}]
        rows = json.loads(result.stdout)
    except Exception as e:
        return [{"error": f"sqlite query failed: {e}"}]

    providers: list[dict[str, Any]] = []
    for row in rows:
        try:
            data = json.loads(row.get("data", "{}")) if isinstance(row.get("data"), str) else (row.get("data") or {})
        except json.JSONDecodeError:
            data = {}
        # Mask the API key — never expose it to the dashboard frontend.
        has_key = bool(data.get("apiKey"))
        providers.append({
            "id": row.get("id", ""),
            "provider": row.get("provider", ""),
            "testStatus": data.get("testStatus", "unknown"),
            "backoffLevel": data.get("backoffLevel", 0),
            "lastError": data.get("lastError"),
            "errorCode": data.get("errorCode"),
            "baseUrl": data.get("baseUrl", ""),
            "hasApiKey": has_key,
        })
    return providers


def _classify_status(test_status: str, backoff_level: int | None, last_error: str | None) -> str:
    """Map raw VansRoute testStatus + backoff into a simple badge category.

    Returns one of: 'active', 'backoff', 'error', 'unknown'.
    Frontend renders: active=green, backoff=yellow, error=red, unknown=gray.
    """
    ts = (test_status or "unknown").lower()
    if ts == "active" and (backoff_level or 0) == 0 and not last_error:
        return "active"
    if ts in ("error", "failed", "unavailable"):
        return "error"
    if (backoff_level or 0) > 0:
        return "backoff"
    if last_error:
        return "error"
    if ts == "active":
        return "active"
    return "unknown"


@router.get("")
async def list_providers():
    """List all VansRoute provider connections with health status.

    Reads per-connection status from the VansRoute SQLite DB (via docker exec)
    and enriches each provider with a model count pulled from /v1/models.
    """
    providers = _providers_from_sqlite()

    # If we got a single error dict back, surface it directly.
    if len(providers) == 1 and "error" in providers[0]:
        return {"providers": [], "error": providers[0]["error"], "count": 0}

    # Enrich with model count per provider prefix (owned_by or provider name).
    models = _models_from_http()
    model_owners: dict[str, int] = {}
    if models:
        for m in models:
            owner = (m.get("owned_by") or "").lower()
            if owner:
                model_owners[owner] = model_owners.get(owner, 0) + 1

    for p in providers:
        p["status"] = _classify_status(
            p.get("testStatus", "unknown"),
            p.get("backoffLevel"),
            p.get("lastError"),
        )
        # Best-effort model count: match on provider name or owned_by prefix.
        key = (p.get("provider") or "").lower()
        # openai-compatible-* connections don't map to a single owner; leave 0.
        p["modelCount"] = model_owners.get(key, 0)

    return {
        "providers": providers,
        "count": len(providers),
        "modelsAvailable": len(models) if models is not None else None,
    }


@router.get("/models")
async def list_models():
    """List all models available through VansRoute (from /v1/models)."""
    models = _models_from_http()
    if models is None:
        # Fallback: try to read model list from SQLite settings/kv if present.
        return {"models": [], "error": "VansRoute /v1/models unreachable (set VANSROUTE_API_KEY)", "count": 0}
    return {"models": models, "count": len(models)}
