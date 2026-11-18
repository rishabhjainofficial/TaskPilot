import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.context import build_system_prompt
from app.ai.llm import call_llm, LLMResult
from app.ai.schemas import ProposalResponse, ChatResponse
from app.ai.tools import TOOL_DEFINITIONS, WRITE_TOOLS
from app.core.audit import log_audit_event
from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.core.permissions import has_permission, get_user_org_membership
from app.db.models.ai_conversation import AIConversation, AIMessage
from app.db.models.ai_proposal import AIProposal
from app.db.models.ai_usage import AIUsage
from app.db.models.project import Project
from app.db.models.subscription import Subscription
from app.db.models.task import Task
from app.db.models.user import User
from app.tasks.schemas import TaskCreateRequest, SubtaskCreateRequest, TaskStatusUpdateRequest
from app.tasks.service import TaskService


class AIService:
    def __init__(self, db: AsyncSession, org_id: uuid.UUID):
        self.db = db
        self.org_id = org_id

    async def _check_credits(self, user_id: uuid.UUID) -> None:
        """Enforces monthly credit limits from subscriptions."""
        stmt = select(Subscription).where(Subscription.org_id == self.org_id)
        sub = (await self.db.execute(stmt)).scalar_one_or_none()
        if not sub:
            return  # Default allowed if subscription record is missing

        # Calculate monthly usage
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stmt_usage = select(func.count(AIUsage.id)).where(
            AIUsage.org_id == self.org_id,
            AIUsage.created_at >= month_start,
        )
        usage_count = (await self.db.execute(stmt_usage)).scalar_one() or 0

        if usage_count >= sub.ai_credits_monthly:
            raise AppError(
                status_code=402,
                detail=f"Monthly AI credits exhausted ({usage_count}/{sub.ai_credits_monthly}). Please upgrade your plan.",
                code="AI_CREDITS_EXHAUSTED",
            )

    async def _log_usage(self, user_id: uuid.UUID, feature: str, result: LLMResult) -> None:
        usage = AIUsage(
            org_id=self.org_id,
            user_id=user_id,
            feature=feature,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=(result.input_tokens * 0.00000015 + result.output_tokens * 0.0000006),
        )
        self.db.add(usage)
        await self.db.flush()

    async def chat(
        self,
        user: User,
        message: str,
        project_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[uuid.UUID] = None,
        mock_result: Optional[LLMResult] = None,
    ) -> ChatResponse:
        await self._check_credits(user.id)

        # 1. Fetch or create conversation
        if conversation_id:
            convo = (await self.db.execute(
                select(AIConversation).where(AIConversation.id == conversation_id, AIConversation.org_id == self.org_id)
            )).scalar_one_or_none()
            if not convo:
                raise NotFoundError("AIConversation", conversation_id)
        else:
            convo = AIConversation(
                org_id=self.org_id,
                project_id=project_id,
                user_id=user.id,
            )
            self.db.add(convo)
            await self.db.flush()

        # Record user message
        user_msg = AIMessage(
            conversation_id=convo.id,
            org_id=self.org_id,
            role="user",
            content=message,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # 2. Fetch context
        project = None
        tasks = []
        if project_id:
            project = (await self.db.execute(
                select(Project).where(Project.id == project_id, Project.org_id == self.org_id)
            )).scalar_one_or_none()
            if project:
                stmt_tasks = (
                    select(Task)
                    .where(Task.project_id == project_id, Task.org_id == self.org_id, Task.parent_task_id == None)
                    .options(selectinload(Task.subtasks))
                    .order_by(Task.task_number.asc())
                )
                tasks = list((await self.db.execute(stmt_tasks)).scalars().all())

        membership = await get_user_org_membership(self.db, user.id, self.org_id)
        user_role = membership.org_role if membership else "member"

        system_prompt = build_system_prompt(
            user=user,
            project=project,
            tasks=tasks,
            user_role=user_role,
        )

        # 3. Load conversation history (sliding window up to 10 recent messages)
        history_stmt = (
            select(AIMessage)
            .where(AIMessage.conversation_id == convo.id)
            .order_by(AIMessage.created_at.desc())
            .limit(10)
        )
        recent_messages = list((await self.db.execute(history_stmt)).scalars().all())
        recent_messages.reverse()

        llm_messages = [{"role": "system", "content": system_prompt}]
        for m in recent_messages:
            llm_messages.append({"role": m.role, "content": m.content or ""})

        # 4. Call LLM
        llm_res = call_llm(llm_messages, tools=TOOL_DEFINITIONS, mock_response=mock_result)
        await self._log_usage(user.id, "chat", llm_res)

        # 5. Handle Tool Calls
        proposal_response = None
        read_results = []
        assistant_reply = llm_res.content

        if llm_res.tool_calls:
            write_actions = []
            for tc in llm_res.tool_calls:
                func_name = tc["function"]["name"]
                args_str = tc["function"]["arguments"]
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except Exception:
                    args = {}

                if func_name in WRITE_TOOLS:
                    write_actions.append({"tool": func_name, "args": args})
                elif func_name == "list_tasks":
                    # Execute read-only directly
                    task_items = [
                        {"code": f"{project.key if project else 'T'}-{t.task_number}", "title": t.title, "status": t.status}
                        for t in tasks
                    ]
                    read_results.append({"tool": "list_tasks", "result": task_items})
                    if not assistant_reply:
                        assistant_reply = f"There are {len(task_items)} tasks currently in this project."

            # If write actions were suggested, create persistent AIProposal in 'pending' status
            if write_actions and project_id:
                proposal = AIProposal(
                    org_id=self.org_id,
                    conversation_id=convo.id,
                    user_id=user.id,
                    project_id=project_id,
                    actions=write_actions,
                    explanation=assistant_reply or "Proposed actions based on your request:",
                    status="pending",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                )
                self.db.add(proposal)
                await self.db.flush()

                proposal_response = ProposalResponse(
                    id=proposal.id,
                    conversation_id=proposal.conversation_id,
                    project_id=proposal.project_id,
                    explanation=proposal.explanation,
                    actions=proposal.actions,
                    status=proposal.status,
                    created_at=proposal.created_at,
                    expires_at=proposal.expires_at,
                )

        # Record assistant reply message
        asst_msg = AIMessage(
            conversation_id=convo.id,
            org_id=self.org_id,
            role="assistant",
            content=assistant_reply,
        )
        self.db.add(asst_msg)
        await self.db.commit()

        return ChatResponse(
            conversation_id=convo.id,
            message=assistant_reply,
            proposal=proposal_response,
            read_results=read_results if read_results else None,
        )

    async def confirm_proposal(self, user: User, proposal_id: uuid.UUID) -> AIProposal:
        """
        Executes a proposal after human confirmation.
        Enforces user RBAC on every action via normal service layer.
        """
        stmt = select(AIProposal).where(AIProposal.id == proposal_id, AIProposal.org_id == self.org_id)
        proposal = (await self.db.execute(stmt)).scalar_one_or_none()
        if not proposal:
            raise NotFoundError("AIProposal", proposal_id)

        if proposal.status != "pending":
            raise AppError(status_code=400, detail=f"Proposal is already {proposal.status}", code="PROPOSAL_RESOLVED")

        exp = proposal.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            proposal.status = "expired"
            await self.db.commit()
            raise AppError(status_code=400, detail="Proposal has expired", code="PROPOSAL_EXPIRED")

        task_service = TaskService(self.db, self.org_id)
        execution_results = []

        # Execute each action through the exact same permission-checked service layer
        for act in proposal.actions:
            tool = act.get("tool")
            args = act.get("args", {})

            if tool == "create_task":
                if not await has_permission(user, self.org_id, "task.create", self.db, project_id=proposal.project_id):
                    raise PermissionDeniedError("task.create")
                t_req = TaskCreateRequest(
                    title=args.get("title", "New Task"),
                    description=args.get("description", ""),
                    priority=args.get("priority", "medium"),
                )
                created = await task_service.create_task(user.id, proposal.project_id, t_req)
                execution_results.append({"tool": tool, "status": "created", "task_id": str(created.id), "code": f"{created.task_number}"})

            elif tool == "create_subtask":
                if not await has_permission(user, self.org_id, "task.create_subtask", self.db, project_id=proposal.project_id):
                    raise PermissionDeniedError("task.create_subtask")
                parent_ref = args.get("parent_task_title_or_code", "")
                # Find parent task
                stmt_p = select(Task).where(Task.project_id == proposal.project_id, Task.org_id == self.org_id)
                all_tasks = list((await self.db.execute(stmt_p)).scalars().all())
                target_parent = None
                for t in all_tasks:
                    if parent_ref.lower() in t.title.lower() or str(t.task_number) in parent_ref:
                        target_parent = t
                        break
                if target_parent:
                    st_req = SubtaskCreateRequest(title=args.get("title", "Subtask"), priority=args.get("priority", "medium"))
                    st = await task_service.create_subtask(user.id, target_parent.id, st_req)
                    execution_results.append({"tool": tool, "status": "created", "parent_id": str(target_parent.id)})

            elif tool == "update_task_status":
                if not await has_permission(user, self.org_id, "task.update_any", self.db, project_id=proposal.project_id):
                    if not await has_permission(user, self.org_id, "task.update_own", self.db, project_id=proposal.project_id):
                        raise PermissionDeniedError("task.update_status")
                ref = args.get("task_title_or_code", "")
                new_status = args.get("status", "done")
                stmt_t = select(Task).where(Task.project_id == proposal.project_id, Task.org_id == self.org_id)
                all_tasks = list((await self.db.execute(stmt_t)).scalars().all())
                for t in all_tasks:
                    if ref.lower() in t.title.lower() or str(t.task_number) in ref:
                        await task_service.update_task_status(user.id, t.id, new_status)
                        execution_results.append({"tool": tool, "task_id": str(t.id), "new_status": new_status})
                        break

            elif tool == "suggest_tasks":
                if not await has_permission(user, self.org_id, "task.create", self.db, project_id=proposal.project_id):
                    raise PermissionDeniedError("task.create")
                raw_tasks = args.get("tasks", [])
                for item in raw_tasks:
                    st_list = [SubtaskCreateRequest(title=st.get("title", "")) for st in item.get("subtasks", []) if st.get("title")]
                    t_req = TaskCreateRequest(
                        title=item.get("title", "Task"),
                        description=item.get("description", ""),
                        priority=item.get("priority", "medium"),
                        subtasks=st_list,
                    )
                    created = await task_service.create_task(user.id, proposal.project_id, t_req)
                    execution_results.append({"tool": "suggest_tasks", "created_task": created.title})

        proposal.status = "accepted"
        proposal.resolved_at = datetime.now(timezone.utc)
        proposal.result = {"results": execution_results}

        await log_audit_event(
            self.db,
            user_id=user.id,
            org_id=self.org_id,
            action="ai_proposal.confirmed",
            resource_type="ai_proposal",
            resource_id=proposal.id,
            ai=True,
            after_state={"results": execution_results},
        )
        await self.db.commit()
        return proposal

    async def reject_proposal(self, user: User, proposal_id: uuid.UUID) -> AIProposal:
        stmt = select(AIProposal).where(AIProposal.id == proposal_id, AIProposal.org_id == self.org_id)
        proposal = (await self.db.execute(stmt)).scalar_one_or_none()
        if not proposal:
            raise NotFoundError("AIProposal", proposal_id)

        proposal.status = "rejected"
        proposal.resolved_at = datetime.now(timezone.utc)
        await log_audit_event(
            self.db,
            user_id=user.id,
            org_id=self.org_id,
            action="ai_proposal.rejected",
            resource_type="ai_proposal",
            resource_id=proposal.id,
            ai=True,
        )
        await self.db.commit()
        return proposal
