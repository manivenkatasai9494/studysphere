from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.redis_client import cache_delete, cache_get, cache_set
from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user, rate_limit_user
from app.schemas.common import ConversationCreate, ConversationUpdate, MessageCreate
from app.services.llm_service import llm

router = APIRouter(prefix="/tutor", tags=["AI Tutor"])


@router.get("/conversations")
async def list_conversations(
    user: dict = Depends(get_current_user),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    sb = get_supabase()
    q = sb.table("conversations").select("*", count="exact").eq("user_id", user["id"]).eq("feature_type", "tutor")
    if search:
        q = q.ilike("title", f"%{search}%")
    q = q.order("updated_at", desc=True).range((page - 1) * page_size, page * page_size - 1)
    result = q.execute()
    return {"items": result.data or [], "total": result.count or 0}


@router.post("/conversations")
async def create_conversation(body: ConversationCreate, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    row = {
        "id": str(uuid4()),
        "user_id": user["id"],
        "title": body.title or "New Chat",
        "feature_type": "tutor",
    }
    result = sb.table("conversations").insert(row).execute()
    return result.data[0] if result.data else row


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    result = sb.table("conversations").update({"title": body.title}).eq("id", conversation_id).eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result.data[0]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    sb.table("messages").delete().eq("conversation_id", conversation_id).eq("user_id", user["id"]).execute()
    sb.table("conversations").delete().eq("id", conversation_id).eq("user_id", user["id"]).execute()
    cache_delete(f"tutor:msgs:{conversation_id}")
    return {"message": "Deleted"}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, user: dict = Depends(get_current_user)):
    cache_key = f"tutor:msgs:{conversation_id}"
    cached = cache_get(cache_key)
    if cached:
        return {"messages": cached}

    sb = get_supabase()
    conv = sb.table("conversations").select("id").eq("id", conversation_id).eq("user_id", user["id"]).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = sb.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
    messages = result.data or []
    cache_set(cache_key, messages, ttl=300)
    return {"messages": messages}


@router.post("/conversations/{conversation_id}/chat")
async def chat(
    conversation_id: str,
    body: MessageCreate,
    user: dict = Depends(rate_limit_user),
):
    sb = get_supabase()
    conv = sb.table("conversations").select("*").eq("id", conversation_id).eq("user_id", user["id"]).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    sb.table("messages").insert({
        "conversation_id": conversation_id,
        "user_id": user["id"],
        "role": "user",
        "content": body.content,
    }).execute()

    history_result = sb.table("messages").select("role, content").eq("conversation_id", conversation_id).order("created_at").execute()
    history = [{"role": m["role"], "content": m["content"]} for m in (history_result.data or []) if m["role"] in ("user", "assistant")]

    reply = llm.chat(history[-20:])

    sb.table("messages").insert({
        "conversation_id": conversation_id,
        "user_id": user["id"],
        "role": "assistant",
        "content": reply,
    }).execute()

    title = conv.data[0].get("title", "New Chat")
    if title == "New Chat" and len(history) <= 2:
        new_title = body.content[:50] + ("..." if len(body.content) > 50 else "")
        sb.table("conversations").update({"title": new_title}).eq("id", conversation_id).execute()

    from datetime import datetime, timezone
    sb.table("conversations").update({"updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", conversation_id).execute()
    cache_delete(f"tutor:msgs:{conversation_id}")

    return {"role": "assistant", "content": reply}
