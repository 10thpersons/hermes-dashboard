"""Knowledge router - Memory, Skills, SOULs."""
from fastapi import APIRouter, HTTPException
from services.hermes_data import get_memory, get_skills, get_souls, get_skill_detail

router = APIRouter()


@router.get("/memory")
async def memory():
    return get_memory()


@router.get("/skills")
async def skills():
    return get_skills()


@router.get("/souls")
async def souls():
    return get_souls()


@router.get("/skills/{path:path}")
async def skill_detail(path: str):
    content = get_skill_detail(path)
    if content is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"path": path, "content": content}
