from datetime import date
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user, rate_limit_user
from app.services.llm_service import llm

router = APIRouter(prefix="/planner", tags=["Study Planner"])

PLANNER_SYSTEM = """You are a study planner. Return JSON:
{"daily_plans": [], "weekly_plans": [], "monthly_plans": [],
 "pomodoro_schedule": {"work_minutes": 25, "break_minutes": 5},
 "revision_schedule": [], "milestones": [], "tips": []}"""


class StudyPlanRequest(BaseModel):
    subjects: List[str]
    topics: Optional[List[str]] = None
    exam_date: Optional[date] = None
    study_hours: int = 2


class ProgressUpdate(BaseModel):
    completed_tasks: List[str]
    streak_increment: bool = False


@router.get("/plans")
async def list_plans(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("study_plans").select("*").eq("user_id", user["id"]).order("updated_at", desc=True).execute()
    return {"plans": result.data or []}


@router.post("/generate")
async def generate_plan(body: StudyPlanRequest, user: dict = Depends(rate_limit_user)):
    prompt = f"""Create a comprehensive study plan:
Subjects: {body.subjects}
Topics: {body.topics or 'all'}
Exam date: {body.exam_date or 'flexible'}
Daily study hours: {body.study_hours}"""

    plan_data = llm.generate_json(prompt, system=PLANNER_SYSTEM)
    plan_id = str(uuid4())

    sb = get_supabase()
    sb.table("study_plans").insert({
        "id": plan_id,
        "user_id": user["id"],
        "subjects": body.subjects,
        "topics": body.topics or [],
        "exam_date": str(body.exam_date) if body.exam_date else None,
        "study_hours": body.study_hours,
        "plan_data": plan_data,
        "progress": {"completed": [], "streak": 0},
    }).execute()
    return {"plan_id": plan_id, "plan": plan_data}


@router.patch("/plans/{plan_id}/progress")
async def update_progress(plan_id: str, body: ProgressUpdate, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    plan = sb.table("study_plans").select("*").eq("id", plan_id).eq("user_id", user["id"]).execute()
    if not plan.data:
        raise HTTPException(status_code=404, detail="Plan not found")

    progress = plan.data[0].get("progress", {})
    completed = set(progress.get("completed", []))
    completed.update(body.completed_tasks)
    streak = progress.get("streak", 0)
    if body.streak_increment:
        streak += 1

    progress.update({"completed": list(completed), "streak": streak})
    sb.table("study_plans").update({"progress": progress, "streak": streak}).eq("id", plan_id).execute()
    return {"progress": progress}


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("study_plans").select("*").eq("id", plan_id).eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Plan not found")
    return result.data[0]
