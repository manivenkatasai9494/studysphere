from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user, rate_limit_user
from app.services.llm_service import llm

router = APIRouter(prefix="/voice", tags=["Voice Assistant"])


class VoiceMessage(BaseModel):
    session_id: str
    text: str


class VoiceSessionCreate(BaseModel):
    title: str = "Voice Session"


@router.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("voice_sessions").select("*").eq("user_id", user["id"]).order("updated_at", desc=True).execute()
    return {"sessions": result.data or []}


@router.post("/sessions")
async def create_session(body: VoiceSessionCreate, user: dict = Depends(get_current_user)):
    session_id = str(uuid4())
    sb = get_supabase()
    sb.table("voice_sessions").insert({
        "id": session_id,
        "user_id": user["id"],
        "title": body.title,
        "messages": [],
    }).execute()
    return {"session_id": session_id}


@router.post("/chat")
async def voice_chat(body: VoiceMessage, user: dict = Depends(rate_limit_user)):
    sb = get_supabase()
    session = sb.table("voice_sessions").select("*").eq("id", body.session_id).eq("user_id", user["id"]).execute()
    if not session.data:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = session.data[0].get("messages", [])
    messages.append({"role": "user", "content": body.text})

    history = [{"role": m["role"], "content": m["content"]} for m in messages[-20:]]
    reply = llm.chat(history, system="You are a helpful voice learning assistant. Keep responses concise for speech.", temperature=0.7)
    messages.append({"role": "assistant", "content": reply})

    sb.table("voice_sessions").update({"messages": messages, "updated_at": "now()"}).eq("id", body.session_id).execute()
    return {"text": reply, "messages": messages}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("voice_sessions").select("*").eq("id", session_id).eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return result.data[0]
