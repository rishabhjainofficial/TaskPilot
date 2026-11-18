import uuid
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[uuid.UUID] = None


class ProposalAction(BaseModel):
    tool: str
    args: Dict[str, Any]
    description: Optional[str] = None


class ProposalResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    project_id: uuid.UUID
    explanation: Optional[str]
    actions: List[Dict[str, Any]]
    status: str
    created_at: datetime
    expires_at: datetime
    result: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: str
    proposal: Optional[ProposalResponse] = None
    read_results: Optional[List[Dict[str, Any]]] = None


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: Optional[str]
    created_at: datetime


class ConversationResponse(BaseModel):
    id: uuid.UUID
    project_id: Optional[uuid.UUID]
    created_at: datetime
    last_message: Optional[str] = None


class OnboardingProjectRequest(BaseModel):
    team_description: str = Field(..., min_length=5, description="e.g. 15-room boutique hotel and breakfast restaurant")
    project_name: Optional[str] = None
    project_key: Optional[str] = None
