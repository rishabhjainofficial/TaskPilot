import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.document_plan_schemas import PlanGenerateRequest, DocumentPlanResponse
from app.ai.document_plan_service import DocumentPlanService
from app.ai.schemas import (
    ChatRequest,
    ChatResponse,
    ProposalResponse,
    MessageResponse,
    ConversationResponse,
    OnboardingProjectRequest,
)
from app.ai.service import AIService
from app.core.permissions import require_permission
from app.dependencies import get_current_user, get_current_org_id, get_tenant_db
from app.db.models.ai_conversation import AIConversation, AIMessage
from app.db.models.ai_proposal import AIProposal
from app.db.models.project import Project
from app.db.models.user import User
from app.projects.schemas import ProjectCreateRequest
from app.projects.service import ProjectService

router = APIRouter(tags=["AI Agent"])


@router.post("/projects/{project_id}/ai/chat", response_model=ChatResponse)
async def project_ai_chat(
    project_id: uuid.UUID,
    body: ChatRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = AIService(db, org_id)
    return await service.chat(
        user=user,
        message=body.message,
        project_id=project_id,
        conversation_id=body.conversation_id,
    )


@router.get("/projects/{project_id}/ai/conversations", response_model=List[ConversationResponse])
async def list_project_conversations(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(AIConversation)
        .where(AIConversation.project_id == project_id, AIConversation.org_id == org_id)
        .order_by(AIConversation.created_at.desc())
    )
    result = await db.execute(stmt)
    convos = list(result.scalars().all())
    return [
        ConversationResponse(
            id=c.id,
            project_id=c.project_id,
            created_at=c.created_at,
        )
        for c in convos
    ]


@router.get("/ai/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_conversation_messages(
    conversation_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id, AIMessage.org_id == org_id)
        .order_by(AIMessage.created_at.asc())
    )
    result = await db.execute(stmt)
    msgs = list(result.scalars().all())
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in msgs
    ]


@router.get("/ai/proposals/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    stmt = select(AIProposal).where(AIProposal.id == proposal_id, AIProposal.org_id == org_id)
    p = (await db.execute(stmt)).scalar_one_or_none()
    if not p:
        from app.core.errors import NotFoundError
        raise NotFoundError("AIProposal", proposal_id)

    return ProposalResponse(
        id=p.id,
        conversation_id=p.conversation_id,
        project_id=p.project_id,
        explanation=p.explanation,
        actions=p.actions,
        status=p.status,
        created_at=p.created_at,
        expires_at=p.expires_at,
        result=p.result,
    )


@router.post("/ai/proposals/{proposal_id}/confirm", response_model=ProposalResponse)
async def confirm_proposal(
    proposal_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = AIService(db, org_id)
    p = await service.confirm_proposal(user, proposal_id)
    return ProposalResponse(
        id=p.id,
        conversation_id=p.conversation_id,
        project_id=p.project_id,
        explanation=p.explanation,
        actions=p.actions,
        status=p.status,
        created_at=p.created_at,
        expires_at=p.expires_at,
        result=p.result,
    )


@router.post("/ai/proposals/{proposal_id}/reject", response_model=ProposalResponse)
async def reject_proposal(
    proposal_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = AIService(db, org_id)
    p = await service.reject_proposal(user, proposal_id)
    return ProposalResponse(
        id=p.id,
        conversation_id=p.conversation_id,
        project_id=p.project_id,
        explanation=p.explanation,
        actions=p.actions,
        status=p.status,
        created_at=p.created_at,
        expires_at=p.expires_at,
        result=p.result,
    )


@router.post("/ai/onboarding-project", status_code=status.HTTP_201_CREATED)
async def create_onboarding_starter_project(
    body: OnboardingProjectRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("project.create")),
):
    """Generates a starter project with AI-suggested operational tasks from team description."""
    proj_service = ProjectService(db, org_id)
    proj_name = body.project_name or "Standard Operations"
    proj_key = (body.project_key or "OPS").upper()

    project = await proj_service.create_project(
        user.id,
        ProjectCreateRequest(
            name=proj_name,
            key=proj_key,
            description=f"Generated starter workspace for {body.team_description}",
        ),
    )

    ai_service = AIService(db, org_id)
    chat_prompt = f"We are {body.team_description}. Please propose 3 essential starter tasks with clear subtasks to run our operations."
    chat_res = await ai_service.chat(user=user, message=chat_prompt, project_id=project.id)

    return {
        "status": "ok",
        "project": {
            "id": project.id,
            "name": project.name,
            "key": project.key,
        },
        "proposal": chat_res.proposal,
    }


@router.post("/projects/{project_id}/documents/plan", response_model=DocumentPlanResponse)
async def generate_document_plan(
    project_id: uuid.UUID,
    body: PlanGenerateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = DocumentPlanService(db, org_id)
    return await service.generate_plan_from_document(user.id, project_id, body)


@router.get("/projects/{project_id}/documents")
async def list_project_documents(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = DocumentPlanService(db, org_id)
    docs = await service.list_documents(project_id)
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "status": d.status,
            "summary": d.summary,
            "proposal_id": d.proposal_id,
            "file_size": d.file_size,
            "created_at": d.created_at,
        }
        for d in docs
    ]


@router.get("/projects/{project_id}/documents/{document_id}")
async def get_project_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = DocumentPlanService(db, org_id)
    d = await service.get_document(document_id)
    return {
        "id": d.id,
        "filename": d.filename,
        "status": d.status,
        "summary": d.summary,
        "proposal_id": d.proposal_id,
        "extracted_text": d.extracted_text,
        "file_size": d.file_size,
        "created_at": d.created_at,
    }

