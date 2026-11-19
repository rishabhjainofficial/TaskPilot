import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.document_plan_schemas import PlanGenerateRequest, DocumentPlanResponse, GeneratedTaskItem
from app.ai.service import AIService
from app.core.audit import log_audit_event
from app.core.errors import AppError, NotFoundError
from app.db.models.ai_proposal import AIProposal
from app.db.models.project import Project
from app.db.models.project_document import ProjectDocument
from app.db.models.project_assignment import ProjectAssignment
from app.db.models.team_member import TeamMember
from app.db.models.user import User
from app.tasks.schemas import TaskCreateRequest, SubtaskCreateRequest
from app.tasks.service import TaskService


class DocumentPlanService:
    def __init__(self, db: AsyncSession, org_id: uuid.UUID):
        self.db = db
        self.org_id = org_id

    async def list_documents(self, project_id: uuid.UUID) -> List[ProjectDocument]:
        stmt = (
            select(ProjectDocument)
            .where(
                ProjectDocument.org_id == self.org_id,
                ProjectDocument.project_id == project_id,
            )
            .order_by(ProjectDocument.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_document(self, document_id: uuid.UUID) -> ProjectDocument:
        stmt = select(ProjectDocument).where(
            ProjectDocument.id == document_id,
            ProjectDocument.org_id == self.org_id,
        )
        doc = (await self.db.execute(stmt)).scalar_one_or_none()
        if not doc:
            raise NotFoundError("ProjectDocument", document_id)
        return doc

    async def generate_plan_from_document(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        req: PlanGenerateRequest,
    ) -> DocumentPlanResponse:
        # 1. Enforce AI credit quota via AIService
        ai_service = AIService(self.db, self.org_id)
        await ai_service._check_credits(user_id)

        # 2. Verify project
        stmt_proj = select(Project).where(Project.id == project_id, Project.org_id == self.org_id)
        project = (await self.db.execute(stmt_proj)).scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", project_id)

        doc_text = req.document_text.strip() if req.document_text else ""
        if not doc_text:
            raise AppError(status_code=400, detail="Document text or specification cannot be empty")

        # 3. Retrieve available candidates from teams assigned to this project
        candidates = await self._get_project_candidates(project_id)

        # 4. Extract tasks and breakdown from document text
        extracted_tasks = self._parse_tasks_from_text(doc_text, candidates)
        if not extracted_tasks:
            # Fallback default task if no structured tasks parsed
            extracted_tasks = [
                GeneratedTaskItem(
                    title="Implement Core Specifications",
                    description=doc_text[:300],
                    priority="high",
                    subtasks=["Review specification document", "Draft architectural blueprint", "Execute implementation"],
                    recommended_role="Lead Architect",
                )
            ]

        # 5. Persist ProjectDocument record
        storage_key = f"orgs/{self.org_id}/projects/{project_id}/documents/{uuid.uuid4()}_{req.filename}"
        doc_record = ProjectDocument(
            org_id=self.org_id,
            project_id=project_id,
            filename=req.filename or "Specification.md",
            storage_key=storage_key,
            content_type="text/markdown",
            file_size=len(doc_text.encode("utf-8")),
            status="completed",
            extracted_text=doc_text[:5000],  # store first 5k for reference
            summary=f"Extracted {len(extracted_tasks)} tasks from {req.filename}",
            created_by=user_id,
        )
        self.db.add(doc_record)
        await self.db.flush()

        # 6. Build Proposal Actions
        proposal_actions = []
        for t in extracted_tasks:
            # create_task action
            task_action = {
                "tool": "create_task",
                "args": {
                    "title": t.title,
                    "description": t.description,
                    "priority": t.priority,
                    "subtasks": [{"title": st} for st in t.subtasks],
                },
            }
            proposal_actions.append(task_action)

            # assign_task action if candidate matched
            if t.assigned_user_id:
                assign_action = {
                    "tool": "assign_task",
                    "args": {
                        "task_title_or_code": t.title,
                        "assignee_email_or_name": str(t.assigned_user_id),
                    },
                }
                proposal_actions.append(assign_action)

        # 7. Create AIProposal
        proposal = AIProposal(
            org_id=self.org_id,
            conversation_id=uuid.uuid4(),
            user_id=user_id,
            project_id=project_id,
            actions=proposal_actions,
            explanation=f"Generated implementation plan with {len(extracted_tasks)} tasks from document: {req.filename}",
            status="accepted" if req.auto_apply else "pending",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self.db.add(proposal)
        await self.db.flush()

        doc_record.proposal_id = proposal.id

        # 8. Auto-apply if requested
        if req.auto_apply:
            task_service = TaskService(self.db, self.org_id)
            for t in extracted_tasks:
                subtasks_data = [SubtaskCreateRequest(title=st) for st in t.subtasks]
                created_task = await task_service.create_task(
                    user_id=user_id,
                    project_id=project_id,
                    req=TaskCreateRequest(
                        title=t.title,
                        description=t.description,
                        priority=t.priority,
                        subtasks=subtasks_data,
                    ),
                )
                if t.assigned_user_id:
                    created_task.assignee_id = t.assigned_user_id

        await self.db.commit()

        await log_audit_event(
            self.db,
            user_id=user_id,
            org_id=self.org_id,
            action="ai.document_plan_generated",
            resource_type="project_document",
            resource_id=doc_record.id,
            after_state={"filename": doc_record.filename, "tasks_count": len(extracted_tasks)},
        )

        return DocumentPlanResponse(
            document_id=doc_record.id,
            filename=doc_record.filename,
            status=doc_record.status,
            summary=doc_record.summary,
            proposal_id=proposal.id,
            tasks_count=len(extracted_tasks),
            tasks=extracted_tasks,
            created_at=doc_record.created_at,
        )

    async def _get_project_candidates(self, project_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Finds candidate assignees from teams assigned to this project."""
        stmt = (
            select(TeamMember, User)
            .join(ProjectAssignment, ProjectAssignment.team_id == TeamMember.team_id)
            .join(User, TeamMember.user_id == User.id)
            .where(
                ProjectAssignment.project_id == project_id,
                ProjectAssignment.org_id == self.org_id,
            )
        )
        res = await self.db.execute(stmt)
        candidates = []
        for tm, u in res.all():
            candidates.append({
                "user_id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "job_title": tm.job_title or "",
                "team_role": tm.team_role,
            })
        return candidates

    def _parse_tasks_from_text(self, text: str, candidates: List[Dict[str, Any]]) -> List[GeneratedTaskItem]:
        """
        Parses document text into structured tasks.
        Recognizes headings (## Epic / Feature), bullet points (- [ ] or -), numbered lists,
        and role keywords.
        """
        lines = text.split("\n")
        tasks: List[GeneratedTaskItem] = []
        current_task: Optional[GeneratedTaskItem] = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Heading 1/2/3 or strong item indicating new task
            is_header = line.startswith("#") or re.match(r"^(\d+\.|\- \[ \]|Feature:|Task:|Epic:)", line)
            if is_header:
                clean_title = re.sub(r"^(#+|\d+\.|\- \[ \]|Feature:|Task:|Epic:)\s*", "", line).strip()
                if clean_title:
                    if current_task:
                        tasks.append(current_task)

                    priority = "medium"
                    lower_line = line.lower()
                    if "critical" in lower_line or "urgent" in lower_line or "security" in lower_line:
                        priority = "critical"
                    elif "high" in lower_line or "important" in lower_line or "core" in lower_line:
                        priority = "high"
                    elif "low" in lower_line or "optional" in lower_line:
                        priority = "low"

                    matched_user, matched_role = self._match_candidate_for_task(clean_title, candidates)

                    current_task = GeneratedTaskItem(
                        title=clean_title,
                        description="",
                        priority=priority,
                        subtasks=[],
                        recommended_role=matched_role,
                        assigned_user_id=matched_user["user_id"] if matched_user else None,
                        assigned_user_name=matched_user["full_name"] if matched_user else None,
                    )
            elif current_task:
                # Subtask or description
                if line.startswith("-") or line.startswith("*"):
                    subtask_title = line.lstrip("-* ").strip()
                    if subtask_title:
                        current_task.subtasks.append(subtask_title)
                else:
                    if len(current_task.description) < 500:
                        current_task.description += (" " + line if current_task.description else line)

        if current_task:
            tasks.append(current_task)

        # If no headings found, break by paragraph
        if not tasks:
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p in paragraphs[:8]:
                first_line = p.split("\n")[0][:100]
                matched_user, matched_role = self._match_candidate_for_task(first_line, candidates)
                tasks.append(
                    GeneratedTaskItem(
                        title=first_line,
                        description=p,
                        priority="medium",
                        subtasks=[],
                        recommended_role=matched_role,
                        assigned_user_id=matched_user["user_id"] if matched_user else None,
                        assigned_user_name=matched_user["full_name"] if matched_user else None,
                    )
                )

        return tasks

    def _match_candidate_for_task(self, task_title: str, candidates: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Matches a task title or keywords to the most relevant team member based on job_title."""
        lower = task_title.lower()
        role_map = [
            (["backend", "api", "database", "sql", "server", "postgres", "auth", "worker"], "Backend Developer"),
            (["frontend", "ui", "react", "css", "component", "page", "modal", "view"], "Frontend Engineer"),
            (["design", "ux", "wireframe", "mockup", "figma", "styling"], "UI/UX Designer"),
            (["test", "qa", "e2e", "coverage", "verify", "validation"], "QA / Test Engineer"),
            (["devops", "docker", "deploy", "ci", "cd", "cloud", "s3", "minio", "infra"], "DevOps Engineer"),
            (["lead", "architect", "spec", "planning", "security"], "Lead Architect"),
        ]

        detected_role = None
        for keywords, role_name in role_map:
            if any(k in lower for k in keywords):
                detected_role = role_name
                break

        if not detected_role:
            detected_role = "Software Engineer"

        # Match candidate whose job_title contains words from detected role
        for c in candidates:
            c_job = c["job_title"].lower()
            if any(w in c_job for w in detected_role.lower().split()):
                return c, c["job_title"]

        # Default fallback to first candidate if available
        if candidates:
            return candidates[0], candidates[0]["job_title"]

        return None, detected_role
