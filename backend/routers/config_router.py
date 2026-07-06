"""Config router."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from services.hermes_data import get_config, update_config

router = APIRouter()


class ConfigUpdate(BaseModel):
    updates: dict[str, Any]


@router.get("")
async def config():
    return get_config()


@router.put("")
async def update(body: ConfigUpdate):
    return update_config(body.updates)
