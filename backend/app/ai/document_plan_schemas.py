import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PlanGenerateRequest(BaseModel):
    document_text: Optional[str] = Field(None, description="Pasted document text / specs")
    filename: Optional[str] = Field("Project-Specification.md", max_length=255)
    auto_apply: bool = Field(False, description="Whether to automatically create tasks or generate proposal for review")


class GeneratedTaskItem(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: str = "medium"
    subtasks: List[str] = []
    recommended_role: Optional[str] = None
    assigned_user_id: Optional[uuid.UUID] = None
    assigned_user_name: Optional[str] = None


class DocumentPlanResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    status: str
    summary: Optional[str] = None
    proposal_id: Optional[uuid.UUID] = None
    tasks_count: int = 0
    tasks: List[GeneratedTaskItem] = []
    created_at: datetime
