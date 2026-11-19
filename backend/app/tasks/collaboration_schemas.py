import uuid
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------- Comments ----------------
class TaskCommentCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    parent_comment_id: Optional[uuid.UUID] = None


class TaskCommentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_full_name: str
    content: str
    parent_comment_id: Optional[uuid.UUID] = None
    created_at: datetime
    replies: List["TaskCommentResponse"] = []


# ---------------- Time Logs ----------------
class TimeLogCreateRequest(BaseModel):
    duration_minutes: int = Field(gt=0, description="Duration in minutes, must be positive")
    description: Optional[str] = None
    log_date: Optional[date] = None


class TimeLogResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_full_name: str
    duration_minutes: int
    description: Optional[str] = None
    log_date: date
    created_at: datetime


class TimeLogListResponse(BaseModel):
    task_id: uuid.UUID
    total_duration_minutes: int
    logs: List[TimeLogResponse]


# ---------------- Attachments ----------------
class AttachmentUploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0, le=26214400, description="Max 25MB")


class AttachmentUploadUrlResponse(BaseModel):
    storage_key: str
    upload_url: str
    filename: str
    content_type: str


class AttachmentConfirmRequest(BaseModel):
    storage_key: str
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0)
    comment_id: Optional[uuid.UUID] = None


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_full_name: str
    filename: str
    storage_key: str
    content_type: str
    size_bytes: int
    created_at: datetime
