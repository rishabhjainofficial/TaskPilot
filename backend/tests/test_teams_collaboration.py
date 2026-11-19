import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.db.models.project_assignment import ProjectAssignment
from app.db.models.task import Task
from app.db.models.team import Team
from app.db.models.team_member import TeamMember
from app.db.models.ai_proposal import AIProposal


@pytest.mark.asyncio
async def test_team_creation_and_atomic_lead(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]
    admin_a = setup_orgs["admin_a"]

    # 1. Create team
    res = await client.post(
        "/api/v1/teams",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"name": "Core Platform Team", "description": "Backend & Infrastructure"},
    )
    assert res.status_code == 201
    team_data = res.json()
    team_id = team_data["id"]
    assert team_data["name"] == "Core Platform Team"

    # 2. Add owner as lead
    res_m1 = await client.post(
        f"/api/v1/teams/{team_id}/members",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"user_id": str(owner_a.id), "team_role": "lead", "job_title": "Lead Architect"},
    )
    assert res_m1.status_code == 201

    # 3. Add admin as lead -> must atomically demote owner to member
    res_m2 = await client.post(
        f"/api/v1/teams/{team_id}/members",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"user_id": str(admin_a.id), "team_role": "lead", "job_title": "Engineering Manager"},
    )
    assert res_m2.status_code == 201

    # Verify team detail: only admin_a is lead
    res_detail = await client.get(
        f"/api/v1/teams/{team_id}",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_detail.status_code == 200
    members = res_detail.json()["members"]
    assert len(members) == 2
    leads = [m for m in members if m["team_role"] == "lead"]
    assert len(leads) == 1
    assert leads[0]["user_id"] == str(admin_a.id)


@pytest.mark.asyncio
async def test_team_lead_project_permissions(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    member_a = setup_orgs["member_a"]
    owner_a = setup_orgs["owner_a"]

    # Create Team Alpha and designate member_a as Lead
    team = Team(org_id=org_a.id, name="Frontend Specialists")
    db_session.add(team)
    await db_session.flush()

    tm = TeamMember(org_id=org_a.id, team_id=team.id, user_id=member_a.id, team_role="lead", job_title="Frontend Lead")
    db_session.add(tm)

    # Project 1: Assigned to Team Alpha
    proj_assigned = Project(org_id=org_a.id, name="Assigned Project", key="APROJ", created_by=owner_a.id)
    # Project 2: Unassigned
    proj_unassigned = Project(org_id=org_a.id, name="Unassigned Project", key="UPROJ", created_by=owner_a.id)
    db_session.add_all([proj_assigned, proj_unassigned])
    await db_session.flush()

    pa = ProjectAssignment(org_id=org_a.id, project_id=proj_assigned.id, team_id=team.id, assigned_by=owner_a.id)
    db_session.add(pa)
    await db_session.commit()

    # member_a is lead of team assigned to proj_assigned -> Can create task in proj_assigned
    res_create = await client.post(
        f"/api/v1/projects/{proj_assigned.id}/tasks",
        headers={"Authorization": f"Bearer {tokens['member_a']}"},
        json={"title": "Team Lead Created Task", "priority": "high"},
    )
    assert res_create.status_code == 201

    # member_a is NOT lead or manager of proj_unassigned -> Cannot create task in proj_unassigned
    res_forbidden = await client.post(
        f"/api/v1/projects/{proj_unassigned.id}/tasks",
        headers={"Authorization": f"Bearer {tokens['member_a']}"},
        json={"title": "Unauthorized Task", "priority": "high"},
    )
    assert res_forbidden.status_code == 403


@pytest.mark.asyncio
async def test_member_strict_silo_task_visibility(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]
    member_a = setup_orgs["member_a"]

    proj = Project(org_id=org_a.id, name="Strict Silo Project", key="SILO", created_by=owner_a.id)
    db_session.add(proj)
    await db_session.flush()

    # Task 1 assigned to member_a
    t1 = Task(org_id=org_a.id, project_id=proj.id, task_number=1, title="Task Assigned to Member A", assignee_id=member_a.id, created_by=owner_a.id)
    # Task 2 assigned to owner_a
    t2 = Task(org_id=org_a.id, project_id=proj.id, task_number=2, title="Confidential Owner Task", assignee_id=owner_a.id, created_by=owner_a.id)
    db_session.add_all([t1, t2])
    await db_session.commit()

    # Owner views all tasks
    res_owner = await client.get(
        f"/api/v1/projects/{proj.id}/tasks",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_owner.status_code == 200
    assert len(res_owner.json()) == 2

    # Member A views tasks -> strict silo: only sees Task 1
    res_member = await client.get(
        f"/api/v1/projects/{proj.id}/tasks",
        headers={"Authorization": f"Bearer {tokens['member_a']}"},
    )
    assert res_member.status_code == 200
    member_tasks = res_member.json()
    assert len(member_tasks) == 1
    assert member_tasks[0]["title"] == "Task Assigned to Member A"


@pytest.mark.asyncio
async def test_threaded_comments_flow(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    proj = Project(org_id=org_a.id, name="Discussion Project", key="DISC", created_by=owner_a.id)
    db_session.add(proj)
    await db_session.flush()

    task = Task(org_id=org_a.id, project_id=proj.id, task_number=1, title="Discuss Feature", created_by=owner_a.id)
    db_session.add(task)
    await db_session.commit()

    # 1. Post parent comment
    res_c1 = await client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"content": "Root discussion comment"},
    )
    assert res_c1.status_code == 201
    parent_id = res_c1.json()["id"]

    # 2. Post reply comment
    res_c2 = await client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers={"Authorization": f"Bearer {tokens['admin_a']}"},
        json={"content": "Nested reply to root", "parent_comment_id": parent_id},
    )
    assert res_c2.status_code == 201

    # 3. List comments: verify tree
    res_list = await client.get(
        f"/api/v1/tasks/{task.id}/comments",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_list.status_code == 200
    comments = res_list.json()
    assert len(comments) == 1  # 1 top-level comment
    assert len(comments[0]["replies"]) == 1
    assert comments[0]["replies"][0]["content"] == "Nested reply to root"


@pytest.mark.asyncio
async def test_time_logs_and_summary(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    proj = Project(org_id=org_a.id, name="Time Track Project", key="TIME", created_by=owner_a.id)
    db_session.add(proj)
    await db_session.flush()

    task = Task(org_id=org_a.id, project_id=proj.id, task_number=1, title="Trackable Task", created_by=owner_a.id)
    db_session.add(task)
    await db_session.commit()

    # Log 45 minutes
    res_t1 = await client.post(
        f"/api/v1/tasks/{task.id}/time-logs",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"duration_minutes": 45, "description": "Phase 1 work"},
    )
    assert res_t1.status_code == 201

    # Log 75 minutes
    res_t2 = await client.post(
        f"/api/v1/tasks/{task.id}/time-logs",
        headers={"Authorization": f"Bearer {tokens['admin_a']}"},
        json={"duration_minutes": 75, "description": "Review & tests"},
    )
    assert res_t2.status_code == 201

    # Fetch rollup: total = 120 minutes
    res_list = await client.get(
        f"/api/v1/tasks/{task.id}/time-logs",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total_duration_minutes"] == 120
    assert len(data["logs"]) == 2


@pytest.mark.asyncio
async def test_attachment_upload_and_confirm(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    proj = Project(org_id=org_a.id, name="Attachment Project", key="ATT", created_by=owner_a.id)
    db_session.add(proj)
    await db_session.flush()

    task = Task(org_id=org_a.id, project_id=proj.id, task_number=1, title="Attachment Task", created_by=owner_a.id)
    db_session.add(task)
    await db_session.commit()

    # 1. Request presigned upload URL
    res_ticket = await client.post(
        f"/api/v1/tasks/{task.id}/attachments/upload-url",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"filename": "architecture_diagram.png", "content_type": "image/png", "size_bytes": 102400},
    )
    assert res_ticket.status_code == 200
    ticket = res_ticket.json()
    storage_key = ticket["storage_key"]
    assert f"orgs/{org_a.id}/projects/{proj.id}/tasks/{task.id}/" in storage_key

    # 2. Confirm upload
    res_confirm = await client.post(
        f"/api/v1/tasks/{task.id}/attachments/confirm",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={
            "storage_key": storage_key,
            "filename": "architecture_diagram.png",
            "content_type": "image/png",
            "size_bytes": 102400,
        },
    )
    assert res_confirm.status_code == 201
    att_id = res_confirm.json()["id"]

    # 3. List attachments & get download url
    res_list = await client.get(
        f"/api/v1/tasks/{task.id}/attachments",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1

    res_dl = await client.get(
        f"/api/v1/tasks/{task.id}/attachments/{att_id}/download",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_dl.status_code == 200
    assert "download_url" in res_dl.json()


@pytest.mark.asyncio
async def test_ai_role_aware_assignment_flow(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    """Verifies that the AI proposal engine resolves assign_task by job_title within project teams."""
    from datetime import datetime, timezone, timedelta

    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]
    member_a = setup_orgs["member_a"]

    # Create Project & Task
    proj = Project(org_id=org_a.id, name="AI Role Assignment Project", key="AIRA", created_by=owner_a.id)
    db_session.add(proj)
    await db_session.flush()

    task = Task(org_id=org_a.id, project_id=proj.id, task_number=1, title="Implement API Auth", created_by=owner_a.id)
    db_session.add(task)

    # Create Team, add member_a as "Senior Backend Developer", assign Team to Project
    team = Team(org_id=org_a.id, name="Backend Squad")
    db_session.add(team)
    await db_session.flush()

    tm = TeamMember(org_id=org_a.id, team_id=team.id, user_id=member_a.id, team_role="member", job_title="Senior Backend Developer")
    pa = ProjectAssignment(org_id=org_a.id, project_id=proj.id, team_id=team.id, assigned_by=owner_a.id)
    db_session.add_all([tm, pa])
    await db_session.commit()

    # Create AI proposal proposing assign_task to "backend developer"
    proposal = AIProposal(
        org_id=org_a.id,
        conversation_id=uuid.uuid4(),
        user_id=owner_a.id,
        project_id=proj.id,
        actions=[
            {
                "tool": "assign_task",
                "args": {
                    "task_title_or_code": "AIRA-1",
                    "assignee_email_or_name": "backend developer",
                },
            }
        ],
        explanation="Matched Senior Backend Developer in Backend Squad",
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(proposal)
    await db_session.commit()

    # Confirm proposal as Owner
    res_confirm = await client.post(
        f"/api/v1/ai/proposals/{proposal.id}/confirm",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_confirm.status_code == 200
    assert res_confirm.json()["status"] == "accepted"

    # Refresh task and verify it is assigned to member_a
    await db_session.refresh(task)
    assert task.assignee_id == member_a.id


@pytest.mark.asyncio
async def test_project_team_assignment_endpoints(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    # 1. Create project
    proj = Project(org_id=org_a.id, name="Assignment Test Project", key="ATP", created_by=owner_a.id)
    db_session.add(proj)
    await db_session.flush()

    # 2. Create team
    team = Team(org_id=org_a.id, name="DevOps Guild")
    db_session.add(team)
    await db_session.commit()

    # 3. Assign team to project via POST /api/v1/projects/{project_id}/assign
    res_assign = await client.post(
        f"/api/v1/projects/{proj.id}/assign",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"team_id": str(team.id)},
    )
    assert res_assign.status_code == 200
    assignment_id = res_assign.json()["assignment_id"]

    # 4. List assignments via GET /api/v1/projects/{project_id}/assignments
    res_list = await client.get(
        f"/api/v1/projects/{proj.id}/assignments",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_list.status_code == 200
    assignments = res_list.json()
    assert any(a["team_id"] == str(team.id) and a["team_name"] == "DevOps Guild" for a in assignments)

    # 5. Remove assignment via DELETE /api/v1/projects/{project_id}/assignments/{assignment_id}
    res_del = await client.delete(
        f"/api/v1/projects/{proj.id}/assignments/{assignment_id}",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_del.status_code == 204

    # Verify list is empty
    res_list_after = await client.get(
        f"/api/v1/projects/{proj.id}/assignments",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_list_after.status_code == 200
    assert not any(a["id"] == assignment_id for a in res_list_after.json())

