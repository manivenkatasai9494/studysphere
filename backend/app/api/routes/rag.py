import os
import shutil
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.config import get_settings
from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user, rate_limit_user
from app.schemas.common import MessageCreate
from app.services.document_parser import chunk_text, parse_file
from app.services.embedding_service import embeddings
from app.services.llm_service import llm
from app.services.pinecone_service import pinecone_svc, user_namespace

router = APIRouter(prefix="/rag", tags=["RAG Notes"])

ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md", ".pptx", ".csv"}


@router.get("/documents")
async def list_documents(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("documents").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    return {"documents": result.data or []}


@router.get("/chats")
async def list_document_chats(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("document_chats").select("*, documents(filename)").eq("user_id", user["id"]).order("updated_at", desc=True).execute()
    return {"chats": result.data or []}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: dict = Depends(rate_limit_user),
):
    settings = get_settings()
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {ALLOWED_EXT}")

    upload_dir = Path(settings.upload_dir) / user["id"]
    upload_dir.mkdir(parents=True, exist_ok=True)

    doc_id = str(uuid4())
    safe_name = f"{doc_id}{ext}"
    file_path = upload_dir / safe_name

    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"File too large. Max {settings.max_upload_mb}MB")

    with open(file_path, "wb") as f:
        f.write(content)

    text = parse_file(str(file_path), ext.lstrip("."))
    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="Could not extract text from document")

    sb = get_supabase()
    namespace = user_namespace(user["id"])
    doc_row = {
        "id": doc_id,
        "user_id": user["id"],
        "filename": file.filename,
        "file_type": ext.lstrip("."),
        "file_size": len(content),
        "storage_path": str(file_path),
        "chunk_count": len(chunks),
        "pinecone_namespace": namespace,
    }
    sb.table("documents").insert(doc_row).execute()

    vectors = []
    chunk_rows = []
    embeds = embeddings.embed_batch(chunks)

    for i, (chunk, emb) in enumerate(zip(chunks, embeds)):
        pinecone_id = f"{doc_id}_{i}"
        vectors.append({
            "id": pinecone_id,
            "values": emb,
            "metadata": {
                "content": chunk[:1000],
                "document_id": doc_id,
                "filename": file.filename,
                "chunk_index": i,
            },
        })
        chunk_rows.append({
            "document_id": doc_id,
            "user_id": user["id"],
            "chunk_index": i,
            "content": chunk,
            "pinecone_id": pinecone_id,
        })

    pinecone_svc.upsert_chunks(user["id"], vectors)
    sb.table("document_chunks").insert(chunk_rows).execute()

    chat_id = str(uuid4())
    sb.table("document_chats").insert({
        "id": chat_id,
        "user_id": user["id"],
        "document_id": doc_id,
        "title": file.filename,
    }).execute()

    return {"document": doc_row, "chat_id": chat_id, "chunks": len(chunks)}


@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    chat = sb.table("document_chats").select("*").eq("id", chat_id).eq("user_id", user["id"]).execute()
    if not chat.data:
        raise HTTPException(status_code=404, detail="Chat not found")
    result = sb.table("document_chat_messages").select("*").eq("chat_id", chat_id).order("created_at").execute()
    return {"messages": result.data or [], "chat": chat.data[0]}


@router.post("/chats/{chat_id}/chat")
async def document_chat(
    chat_id: str,
    body: MessageCreate,
    document_ids: Optional[List[str]] = Query(None),
    user: dict = Depends(rate_limit_user),
):
    sb = get_supabase()
    chat = sb.table("document_chats").select("*").eq("id", chat_id).eq("user_id", user["id"]).execute()
    if not chat.data:
        raise HTTPException(status_code=404, detail="Chat not found")

    doc_id = chat.data[0].get("document_id")
    search_ids = document_ids or ([doc_id] if doc_id else None)

    matches = []
    if search_ids:
        for did in search_ids:
            matches.extend(pinecone_svc.search(user["id"], body.content, top_k=5, document_id=did))
    else:
        matches = pinecone_svc.search(user["id"], body.content, top_k=8)

    matches.sort(key=lambda x: x.get("score", 0), reverse=True)
    matches = matches[:8]

    if not matches:
        reply = "I could not find this information in your uploaded documents."
        sources = []
    else:
        context = "\n\n---\n\n".join(f"[{m.get('filename', 'doc')}] {m['content']}" for m in matches)
        hist = sb.table("document_chat_messages").select("role, content").eq("chat_id", chat_id).order("created_at").execute()
        history = [{"role": m["role"], "content": m["content"]} for m in (hist.data or [])[-10:]]
        reply = llm.chat_with_context(body.content, context, history)
        sources = [{"content": m["content"][:200], "score": m.get("score"), "filename": m.get("filename")} for m in matches]

    sb.table("document_chat_messages").insert({
        "chat_id": chat_id,
        "user_id": user["id"],
        "role": "user",
        "content": body.content,
    }).execute()
    sb.table("document_chat_messages").insert({
        "chat_id": chat_id,
        "user_id": user["id"],
        "role": "assistant",
        "content": reply,
        "sources": sources,
    }).execute()
    sb.table("document_chats").update({"updated_at": "now()"}).eq("id", chat_id).execute()

    return {"role": "assistant", "content": reply, "sources": sources}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    doc = sb.table("documents").select("*").eq("id", document_id).eq("user_id", user["id"]).execute()
    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    path = doc.data[0].get("storage_path")
    if path and os.path.exists(path):
        os.remove(path)

    pinecone_svc.delete_document_vectors(user["id"], document_id)
    sb.table("document_chunks").delete().eq("document_id", document_id).execute()
    sb.table("documents").delete().eq("id", document_id).execute()
    return {"message": "Document deleted"}
