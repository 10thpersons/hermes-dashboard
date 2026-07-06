"""Sessions router."""
from fastapi import APIRouter, Query
from typing import Optional
from services.hermes_data import get_sessions, get_session_messages

router = APIRouter()


@router.get("")
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, description="FTS5 search query"),
):
    return get_sessions(limit=limit, offset=offset, query=q)


@router.get("/{session_id}")
async def session_detail(session_id: str, limit: int = Query(200, ge=1, le=1000)):
    messages = get_session_messages(session_id, limit=limit)
    return {"session_id": session_id, "messages": messages, "count": len(messages)}
