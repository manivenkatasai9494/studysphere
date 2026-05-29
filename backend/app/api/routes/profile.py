from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user

router = APIRouter(prefix="/profile", tags=["Profile"])


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


@router.get("/me")
async def get_profile(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("profiles").select("*").eq("id", user["id"]).execute()
    if not result.data:
        return {"id": user["id"], "email": user.get("email")}
    return result.data[0]


@router.patch("/me")
async def update_profile(body: ProfileUpdate, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    result = sb.table("profiles").update(updates).eq("id", user["id"]).execute()
    return result.data[0] if result.data else updates


@router.get("/dashboard-stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    uid = user["id"]

    def count(table: str) -> int:
        r = sb.table(table).select("id", count="exact").eq("user_id", uid).execute()
        return r.count or 0

    return {
        "conversations": count("conversations"),
        "documents": count("documents"),
        "quizzes": count("quizzes"),
        "feynman_sessions": count("feynman_sessions"),
        "debates": count("debates"),
        "career_reports": count("career_reports"),
        "study_plans": count("study_plans"),
        "roadmaps": count("roadmaps"),
        "voice_sessions": count("voice_sessions"),
    }
