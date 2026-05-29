from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user, rate_limit_user
from app.services.llm_service import llm

router = APIRouter(prefix="/career", tags=["Career Guidance"])

CAREER_SYSTEM = """You are an expert career counselor. Return comprehensive JSON:
{"career_suggestions": [], "industry_trends": "...", "skill_gap_analysis": {},
 "salary_insights": {}, "learning_paths": [], "job_market_analysis": "...",
 "resume_suggestions": [], "portfolio_suggestions": [], "project_recommendations": [],
 "interview_guidance": "...", "certification_recommendations": []}"""


class CareerRequest(BaseModel):
    skills: List[str]
    interests: List[str]
    education: str
    experience: str
    goals: str


@router.get("/reports")
async def list_reports(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("career_reports").select("id, inputs, created_at").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    return {"reports": result.data or []}


@router.post("/generate")
async def generate_report(body: CareerRequest, user: dict = Depends(rate_limit_user)):
    prompt = f"""Generate career guidance for:
Skills: {', '.join(body.skills)}
Interests: {', '.join(body.interests)}
Education: {body.education}
Experience: {body.experience}
Goals: {body.goals}"""

    report = llm.generate_json(prompt, system=CAREER_SYSTEM)
    report_id = str(uuid4())

    sb = get_supabase()
    sb.table("career_reports").insert({
        "id": report_id,
        "user_id": user["id"],
        "inputs": body.model_dump(),
        "report": report,
    }).execute()
    return {"report_id": report_id, "report": report}


@router.get("/reports/{report_id}")
async def get_report(report_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("career_reports").select("*").eq("id", report_id).eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Report not found")
    return result.data[0]
