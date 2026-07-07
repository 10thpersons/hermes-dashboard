"""Usage router - Token consumption analytics."""
from fastapi import APIRouter, Query
from services.hermes_data import get_usage_summary, get_usage_daily, get_usage_by_model

router = APIRouter()


@router.get("/summary")
async def summary():
    """Total tokens, total sessions, avg tokens/session, and by-model breakdown."""
    return get_usage_summary()


@router.get("/daily")
async def daily(days: int = Query(30, ge=1, le=365)):
    """Daily token usage for the last N days (default 30)."""
    return get_usage_daily(days=days)


@router.get("/by-model")
async def by_model():
    """Token usage grouped by model."""
    return get_usage_by_model()
