import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    key: str = Field(..., min_length=2, max_length=10, description="Short project key, e.g. 'TP'")
    description: Optional[str] = ""


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|archived|completed)$")


class ProjectResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    key: str
    description: str
    status: str
    created_by: uuid.UUID
    created_at: datetime


class ProjectAssignRequest(BaseModel):
    user_id: Optional[uuid.UUID] = None
    team_id: Optional[uuid.UUID] = None
