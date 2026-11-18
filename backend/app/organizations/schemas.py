import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    industry: Optional[str] = None
    settings: dict = {}
    created_at: datetime


class UpdateOrgRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    industry: Optional[str] = None
    settings: Optional[dict] = None


class OrgMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    status: str
    joined_at: datetime


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|manager|member)$")
