import random
import string
from typing import Dict, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user

router = APIRouter(prefix="/rooms", tags=["Group Study Rooms"])

active_connections: Dict[str, List[WebSocket]] = {}


def generate_room_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


class CreateRoomRequest(BaseModel):
    name: str


class JoinRoomRequest(BaseModel):
    room_code: str


class RoomMessage(BaseModel):
    content: str


class SharedNotesUpdate(BaseModel):
    notes: str


@router.post("/create")
async def create_room(body: CreateRoomRequest, user: dict = Depends(get_current_user)):
    room_id = str(uuid4())
    code = generate_room_code()
    sb = get_supabase()
    sb.table("study_rooms").insert({
        "id": room_id,
        "room_code": code,
        "name": body.name,
        "created_by": user["id"],
    }).execute()
    sb.table("room_members").insert({
        "room_id": room_id,
        "user_id": user["id"],
    }).execute()
    return {"room_id": room_id, "room_code": code, "name": body.name}


@router.post("/join")
async def join_room(body: JoinRoomRequest, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    room = sb.table("study_rooms").select("*").eq("room_code", body.room_code.upper()).execute()
    if not room.data:
        raise HTTPException(status_code=404, detail="Room not found")

    room_id = room.data[0]["id"]
    existing = sb.table("room_members").select("id").eq("room_id", room_id).eq("user_id", user["id"]).execute()
    if not existing.data:
        sb.table("room_members").insert({"room_id": room_id, "user_id": user["id"]}).execute()

    return {"room": room.data[0]}


@router.post("/{room_id}/leave")
async def leave_room(room_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    sb.table("room_members").delete().eq("room_id", room_id).eq("user_id", user["id"]).execute()
    return {"message": "Left room"}


@router.get("/{room_id}/messages")
async def get_messages(room_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    member = sb.table("room_members").select("id").eq("room_id", room_id).eq("user_id", user["id"]).execute()
    if not member.data:
        raise HTTPException(status_code=403, detail="Not a member")

    result = sb.table("room_messages").select("*").eq("room_id", room_id).order("created_at").execute()
    return {"messages": result.data or []}


@router.post("/{room_id}/messages")
async def post_message(room_id: str, body: RoomMessage, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    member = sb.table("room_members").select("id").eq("room_id", room_id).eq("user_id", user["id"]).execute()
    if not member.data:
        raise HTTPException(status_code=403, detail="Not a member")

    msg_id = str(uuid4())
    row = {
        "id": msg_id,
        "room_id": room_id,
        "user_id": user["id"],
        "content": body.content,
    }
    sb.table("room_messages").insert(row).execute()

    for ws in active_connections.get(room_id, []):
        try:
            await ws.send_json({"type": "message", "data": row})
        except Exception:
            pass

    return row


@router.patch("/{room_id}/notes")
async def update_notes(room_id: str, body: SharedNotesUpdate, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    member = sb.table("room_members").select("id").eq("room_id", room_id).eq("user_id", user["id"]).execute()
    if not member.data:
        raise HTTPException(status_code=403, detail="Not a member")

    sb.table("study_rooms").update({"shared_notes": body.notes}).eq("id", room_id).execute()

    for ws in active_connections.get(room_id, []):
        try:
            await ws.send_json({"type": "notes", "notes": body.notes})
        except Exception:
            pass

    return {"notes": body.notes}


@router.get("/my-rooms")
async def my_rooms(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    members = sb.table("room_members").select("room_id, study_rooms(*)").eq("user_id", user["id"]).execute()
    return {"rooms": members.data or []}


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    if room_id not in active_connections:
        active_connections[room_id] = []
    active_connections[room_id].append(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            for ws in active_connections.get(room_id, []):
                if ws != websocket:
                    try:
                        await ws.send_json(data)
                    except Exception:
                        pass
    except WebSocketDisconnect:
        active_connections[room_id].remove(websocket)
