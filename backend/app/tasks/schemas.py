import uuid
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class SubtaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    priority: Optional[str] = Field("medium", pattern="^(critical|high|medium|low)$")
    estimated_hours: Optional[int] = None


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = ""
    priority: Optional[str] = Field("medium", pattern="^(critical|high|medium|low)$")
    status: Optional[str] = Field("todo", pattern="^(draft|backlog|todo|in_progress|in_review|done|blocked)$")
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None
    estimated_hours: Optional[int] = None
    subtasks: List[SubtaskCreateRequest] = []


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, pattern="^(critical|high|medium|low)$")
    status: Optional[str] = Field(None, pattern="^(draft|backlog|todo|in_progress|in_review|done|blocked)$")
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None
    estimated_hours: Optional[int] = None


class TaskStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(draft|backlog|todo|in_progress|in_review|done|blocked)$")


class TaskAssignRequest(BaseModel):
    assignee_id: Optional[uuid.UUID] = None


class SubtaskResponse(BaseModel):
    id: uuid.UUID
    task_number: int
    title: str
    status: str
    priority: str
    created_at: datetime


class TaskResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID
    parent_task_id: Optional[uuid.UUID]
    task_number: int
    task_code: str  # e.g. "TP-42"
    title: str
    description: str
    priority: str
    status: str
    created_by: uuid.UUID
    assignee_id: Optional[uuid.UUID]
    due_date: Optional[date]
    estimated_hours: Optional[int]
    position: int
    ai_generated: bool
    created_at: datetime
    subtasks: List[SubtaskResponse] = []


class TaskDependencyCreateRequest(BaseModel):
    blocking_task_id: uuid.UUID


class TaskDependencyItem(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    task_code: str
    title: str
    status: str


class TaskDependenciesResponse(BaseModel):
    blocked_by: List[TaskDependencyItem] = []
    blocking: List[TaskDependencyItem] = []


class LabelCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field("#6b7280", pattern="^#[0-9a-fA-F]{6}$")


class LabelResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    color: str

