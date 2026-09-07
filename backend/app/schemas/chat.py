# Pydantic schemas for chat requests, responses, and messages.

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class ChatSource(BaseModel):
    meeting_id: UUID
    meeting_title: str
    excerpt: str = ""

class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    sources: Optional[List[ChatSource]] = None
    created_at: datetime

class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    user_id: UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: Optional[UUID] = None

    meeting_ids: Optional[List[UUID]] = Field(default=None, max_length=50)

class ChatResponse(BaseModel):
    session_id: UUID
    answer: str
    sources: Optional[List[ChatSource]] = None
