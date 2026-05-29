from typing import Any, List, Optional

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    content: str


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default="New Chat")


class ConversationUpdate(BaseModel):
    title: str


class ChatMessage(BaseModel):
    role: str
    content: str


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int = 1
    page_size: int = 20
