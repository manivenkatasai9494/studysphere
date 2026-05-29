from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user, rate_limit_user
from app.services.llm_service import llm

router = APIRouter(prefix="/roadmap", tags=["Roadmap Generator"])

ROADMAP_SYSTEM = """You are a career roadmap expert. Return JSON:
{"career_goal": "...", "timeline_months": 12, "phases": [{"name": "...", "duration": "...", "skills": [], "projects": [], "courses": [], "certifications": [], "milestones": []}],
 "required_skills": [], "recommended_projects": [], "summary": "..."}"""


class RoadmapRequest(BaseModel):
    career_goal: str


class RoadmapUpdate(BaseModel):
    roadmap_data: dict


@router.get("/list")
async def list_roadmaps(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("roadmaps").select("*").eq("user_id", user["id"]).order("updated_at", desc=True).execute()
    return {"roadmaps": result.data or []}


@router.post("/generate")
async def generate_roadmap(body: RoadmapRequest, user: dict = Depends(rate_limit_user)):
    prompt = f"Create a detailed learning roadmap to become a: {body.career_goal}"
    roadmap_data = llm.generate_json(prompt, system=ROADMAP_SYSTEM)
    roadmap_id = str(uuid4())

    sb = get_supabase()
    sb.table("roadmaps").insert({
        "id": roadmap_id,
        "user_id": user["id"],
        "career_goal": body.career_goal,
        "roadmap_data": roadmap_data,
    }).execute()
    return {"roadmap_id": roadmap_id, "roadmap": roadmap_data}


@router.patch("/{roadmap_id}")
async def update_roadmap(roadmap_id: str, body: RoadmapUpdate, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("roadmaps").update({"roadmap_data": body.roadmap_data}).eq("id", roadmap_id).eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return result.data[0]


@router.get("/{roadmap_id}")
async def get_roadmap(roadmap_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("roadmaps").select("*").eq("id", roadmap_id).eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return result.data[0]
