"""Obsidian vault router."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from services.hermes_data import get_obsidian_tree, get_obsidian_file

router = APIRouter()


@router.get("/tree")
async def tree(path: Optional[str] = Query("", description="Relative path within vault")):
    return get_obsidian_tree(path)


@router.get("/file")
async def file(path: str = Query(..., description="Relative path to file")):
    content = get_obsidian_file(path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": content}
