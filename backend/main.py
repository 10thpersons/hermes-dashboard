"""Hermes Dashboard Backend - Main entry point."""
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from contextlib import asynccontextmanager
import json

from config import API_KEY, ALLOWED_ORIGINS
from routers import sessions, cron, knowledge, config_router, system, obsidian

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Hermes Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"], dependencies=[Depends(verify_api_key)])
app.include_router(cron.router, prefix="/api/v1/cron", tags=["Cron"], dependencies=[Depends(verify_api_key)])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Knowledge"], dependencies=[Depends(verify_api_key)])
app.include_router(config_router.router, prefix="/api/v1/config", tags=["Config"], dependencies=[Depends(verify_api_key)])
app.include_router(system.router, prefix="/api/v1/system", tags=["System"], dependencies=[Depends(verify_api_key)])
app.include_router(obsidian.router, prefix="/api/v1/obsidian", tags=["Obsidian"], dependencies=[Depends(verify_api_key)])


@app.get("/health")
async def health():
    return {"status": "ok"}


# WebSocket for live session streaming
connected_clients: set[WebSocket] = set()


@app.websocket("/ws/sessions/{session_id}")
async def ws_session(websocket: WebSocket, session_id: str):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now — real implementation will stream from sessions DB
            await websocket.send_text(json.dumps({"type": "ack", "session_id": session_id}))
    except WebSocketDisconnect:
        connected_clients.discard(websocket)


@app.websocket("/ws/agent-status")
async def ws_agent_status(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "status", "agents": []}))
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
