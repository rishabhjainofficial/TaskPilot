import uuid
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Password at least 8 chars")
    full_name: str = Field(min_length=1, max_length=255)
    organization_name: str = Field(min_length=2, max_length=255)
    industry: Optional[str] = None


class SignupResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    organization_id: uuid.UUID
    organization_name: str
    message: str = "Account created. Please verify your email."
    email_verification_token: Optional[str] = None  # Returned in dev mode for easy testing


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    organization_id: Optional[uuid.UUID] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    role: Optional[str] = None


class VerifyEmailRequest(BaseModel):
    token: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern="^(admin|manager|member)$")


class AcceptInviteRequest(BaseModel):
    token: str
    full_name: str = Field(min_length=1)
    password: str = Field(min_length=8)


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    avatar_url: Optional[str]
    is_platform_admin: bool
    email_verified: bool
    current_org_id: Optional[uuid.UUID] = None
    current_role: Optional[str] = None
    organizations: List[dict] = []
    permissions: List[str] = []
