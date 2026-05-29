from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user, rate_limit_user
from app.services.llm_service import llm

router = APIRouter(prefix="/feynman", tags=["Feynman Technique"])

FEYNMAN_SYSTEM = """You evaluate student explanations using the Feynman Technique.
Return JSON only:
{"understanding_score": 0-100, "accuracy": "...", "simplicity": "...", "clarity": "...", "completeness": "...",
 "missing_concepts": [], "understanding_level": "beginner|intermediate|advanced|expert",
 "better_explanation": "...", "learning_recommendations": []}"""


class FeynmanStart(BaseModel):
    topic: str


class FeynmanSubmit(BaseModel):
    session_id: str
    explanation: str


@router.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("feynman_sessions").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    return {"sessions": result.data or []}


@router.post("/start")
async def start_session(body: FeynmanStart, user: dict = Depends(get_current_user)):
    session_id = str(uuid4())
    prompt = f'The student is learning about: "{body.topic}". Ask them to explain this topic in their own words as if teaching a beginner. One welcoming prompt only.'
    intro = llm.chat([{"role": "user", "content": prompt}], system="You are a Feynman technique coach.", temperature=0.7)

    sb = get_supabase()
    sb.table("feynman_sessions").insert({
        "id": session_id,
        "user_id": user["id"],
        "topic": body.topic,
        "evaluation": {"intro": intro},
    }).execute()
    return {"session_id": session_id, "topic": body.topic, "prompt": intro}


@router.post("/evaluate")
async def evaluate_explanation(body: FeynmanSubmit, user: dict = Depends(rate_limit_user)):
    sb = get_supabase()
    session = sb.table("feynman_sessions").select("*").eq("id", body.session_id).eq("user_id", user["id"]).execute()
    if not session.data:
        raise HTTPException(status_code=404, detail="Session not found")

    topic = session.data[0]["topic"]
    eval_prompt = f"""Topic: {topic}
Student explanation: {body.explanation}
Evaluate using Feynman Technique criteria."""

    evaluation = llm.generate_json(eval_prompt, system=FEYNMAN_SYSTEM)
    score = evaluation.get("understanding_score", 0)

    sb.table("feynman_sessions").update({
        "student_explanation": body.explanation,
        "evaluation": evaluation,
        "understanding_score": score,
    }).eq("id", body.session_id).execute()

    return {"evaluation": evaluation, "understanding_score": score}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("feynman_sessions").select("*").eq("id", session_id).eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return result.data[0]
