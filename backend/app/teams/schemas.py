import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None


class TeamUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class TeamMemberAddRequest(BaseModel):
    user_id: uuid.UUID
    team_role: str = Field(default="member", pattern="^(lead|member)$")
    job_title: Optional[str] = Field(None, max_length=100)


class TeamMemberUpdateRequest(BaseModel):
    team_role: Optional[str] = Field(None, pattern="^(lead|member)$")
    job_title: Optional[str] = Field(None, max_length=100)


class TeamMemberResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_full_name: str
    team_role: str
    job_title: Optional[str] = None
    joined_at: datetime


class TeamResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    members_count: int = 0
    lead: Optional[TeamMemberResponse] = None


class TeamDetailResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    members: List[TeamMemberResponse] = []
