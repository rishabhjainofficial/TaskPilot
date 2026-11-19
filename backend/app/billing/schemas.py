import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SubscriptionUsageResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    plan: str
    status: str
    seats_limit: int
    seats_used: int
    projects_limit: int
    projects_used: int
    ai_credits_monthly: int
    ai_credits_used: int
    storage_bytes_limit: int
    storage_bytes_used: int
    current_period_end: Optional[datetime] = None


class CheckoutRequest(BaseModel):
    plan: str = Field(..., pattern="^(pro|enterprise)$")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class PlanSwitchRequest(BaseModel):
    plan: str = Field(..., pattern="^(free|pro|enterprise)$")
