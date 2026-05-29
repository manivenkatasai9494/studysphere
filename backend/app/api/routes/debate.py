from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user, rate_limit_user
from app.services.llm_service import llm

router = APIRouter(prefix="/debate", tags=["AI Debate"])

DEBATE_SYSTEM = """You are a debate opponent. Always argue the OPPOSITE side of the student's position.
Be logical, use evidence, and provide strong rebuttals. Return JSON for final evaluation:
{"logic": 0-100, "evidence": 0-100, "clarity": 0-100, "persuasion": 0-100, "winner": "user|ai|tie", "analysis": "..."}
For debate rounds, respond in markdown with your argument."""


class DebateStart(BaseModel):
    topic: str
    user_position: str = "for"


class DebateRound(BaseModel):
    debate_id: str
    argument: str


@router.get("/history")
async def debate_history(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("debates").select("*").eq("user_id", user["id"]).order("updated_at", desc=True).execute()
    return {"debates": result.data or []}


@router.post("/start")
async def start_debate(body: DebateStart, user: dict = Depends(rate_limit_user)):
    debate_id = str(uuid4())
    prompt = f"""Debate topic: "{body.topic}"
Student position: {body.user_position} the proposition.
You must argue the OPPOSITE side. Open with your first argument (2-3 paragraphs)."""

    opening = llm.chat([{"role": "user", "content": prompt}], system=DEBATE_SYSTEM)
    rounds = [{"round": 1, "user": body.user_position, "ai": opening}]

    sb = get_supabase()
    sb.table("debates").insert({
        "id": debate_id,
        "user_id": user["id"],
        "topic": body.topic,
        "rounds": rounds,
    }).execute()
    return {"debate_id": debate_id, "topic": body.topic, "ai_opening": opening}


@router.post("/round")
async def debate_round(body: DebateRound, user: dict = Depends(rate_limit_user)):
    sb = get_supabase()
    debate = sb.table("debates").select("*").eq("id", body.debate_id).eq("user_id", user["id"]).execute()
    if not debate.data:
        raise HTTPException(status_code=404, detail="Debate not found")

    d = debate.data[0]
    rounds = d.get("rounds", [])
    round_num = len(rounds) + 1

    prompt = f"""Topic: {d['topic']}
Previous rounds: {rounds[-3:]}
Student's latest argument: {body.argument}
Provide your rebuttal and counterargument."""

    ai_response = llm.chat([{"role": "user", "content": prompt}], system=DEBATE_SYSTEM)
    rounds.append({"round": round_num, "user": body.argument, "ai": ai_response})

    sb.table("debates").update({"rounds": rounds, "updated_at": "now()"}).eq("id", body.debate_id).execute()
    return {"round": round_num, "ai_response": ai_response, "rounds": rounds}


@router.post("/{debate_id}/evaluate")
async def evaluate_debate(debate_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    debate = sb.table("debates").select("*").eq("id", debate_id).eq("user_id", user["id"]).execute()
    if not debate.data:
        raise HTTPException(status_code=404, detail="Debate not found")

    d = debate.data[0]
    evaluation = llm.generate_json(
        f"Evaluate this debate on '{d['topic']}': {d['rounds']}",
        system=DEBATE_SYSTEM,
    )
    sb.table("debates").update({"evaluation": evaluation}).eq("id", debate_id).execute()
    return {"evaluation": evaluation}
