import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.db.models.task import Task
from app.db.models.team import Team
from app.db.models.team_member import TeamMember
from app.db.models.project_assignment import ProjectAssignment
from app.notifications.service import NotificationService


@pytest.mark.asyncio
async def test_phase4_document_to_plan(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]
    member_a = setup_orgs["member_a"]

    # 1. Create project
    proj = Project(org_id=org_a.id, name="Mobile App Redesign", key="MAR", created_by=owner_a.id)
    db_session.add(proj)
    await db_session.flush()

    # 2. Create team & member with job_title and assign to project
    team = Team(org_id=org_a.id, name="Mobile Team")
    db_session.add(team)
    await db_session.flush()

    tm = TeamMember(org_id=org_a.id, team_id=team.id, user_id=member_a.id, team_role="member", job_title="Senior Frontend Engineer")
    pa = ProjectAssignment(org_id=org_a.id, project_id=proj.id, team_id=team.id, assigned_by=owner_a.id)
    db_session.add_all([tm, pa])
    await db_session.commit()

    # 3. Call document plan generation with specification markdown
    spec_text = """
    # Mobile App Overhaul Spec

    ## Feature: Authentication & Biometrics
    - [ ] Setup FaceID and TouchID biometric authentication
    - [ ] Implement refresh token rotation

    ## Feature: Frontend Dashboard UI
    - [ ] Design sleek dashboard cards
    - [ ] Implement pull to refresh gesture

    ## Feature: Push Notifications Engine
    - [ ] Configure APNS and FCM credentials
    """

    res = await client.post(
        f"/api/v1/projects/{proj.id}/documents/plan",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={
            "document_text": spec_text,
            "filename": "Mobile-Spec.md",
            "auto_apply": True,
        },
    )
    assert res.status_code == 200
    plan_data = res.json()
    assert plan_data["tasks_count"] >= 3
    assert plan_data["proposal_id"] is not None

    # Verify tasks were created in project
    res_tasks = await client.get(
        f"/api/v1/projects/{proj.id}/tasks",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_tasks.status_code == 200
    tasks = res_tasks.json()
    assert len(tasks) >= 3


@pytest.mark.asyncio
async def test_phase5_dependencies_and_cycle_guardrail(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    # Create project and 3 tasks: A, B, C
    proj = Project(org_id=org_a.id, name="DAG Project", key="DAG", created_by=owner_a.id)
    db_session.add(proj)
    await db_session.flush()

    task_a = Task(org_id=org_a.id, project_id=proj.id, task_number=1, title="Task Alpha", created_by=owner_a.id)
    task_b = Task(org_id=org_a.id, project_id=proj.id, task_number=2, title="Task Beta", created_by=owner_a.id)
    task_c = Task(org_id=org_a.id, project_id=proj.id, task_number=3, title="Task Gamma", created_by=owner_a.id)
    db_session.add_all([task_a, task_b, task_c])
    await db_session.commit()

    # 1. Add dependency: Alpha blocks Beta (Beta depends on Alpha)
    res_dep1 = await client.post(
        f"/api/v1/tasks/{task_b.id}/dependencies",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"blocking_task_id": str(task_a.id)},
    )
    assert res_dep1.status_code == 201

    # 2. Add dependency: Beta blocks Gamma (Gamma depends on Beta)
    res_dep2 = await client.post(
        f"/api/v1/tasks/{task_c.id}/dependencies",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"blocking_task_id": str(task_b.id)},
    )
    assert res_dep2.status_code == 201

    # 3. Attempt to add cycle: Gamma blocks Alpha (Alpha depends on Gamma) -> Must fail with CIRCULAR_DEPENDENCY
    res_cycle = await client.post(
        f"/api/v1/tasks/{task_a.id}/dependencies",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"blocking_task_id": str(task_c.id)},
    )
    assert res_cycle.status_code == 400
    assert res_cycle.json()["error"]["code"] == "CIRCULAR_DEPENDENCY"

    # 4. Dependency status guardrail: Attempt to mark Beta as 'done' while Alpha is 'todo'
    res_status = await client.patch(
        f"/api/v1/tasks/{task_b.id}/status",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"status": "done"},
    )
    assert res_status.status_code == 400
    assert res_status.json()["error"]["code"] == "TASK_BLOCKED"

    # 5. Mark Alpha as 'done' -> Now Beta can be marked 'done'
    res_alpha = await client.patch(
        f"/api/v1/tasks/{task_a.id}/status",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"status": "done"},
    )
    assert res_alpha.status_code == 200

    res_beta = await client.patch(
        f"/api/v1/tasks/{task_b.id}/status",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"status": "done"},
    )
    assert res_beta.status_code == 200


@pytest.mark.asyncio
async def test_phase5_labels_crud(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    proj = Project(org_id=org_a.id, name="Labels Project", key="LBL", created_by=owner_a.id)
    db_session.add(proj)
    await db_session.flush()

    task = Task(org_id=org_a.id, project_id=proj.id, task_number=1, title="Label Target", created_by=owner_a.id)
    db_session.add(task)
    await db_session.commit()

    # 1. Create label
    res_lbl = await client.post(
        "/api/v1/labels",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"name": "Frontend", "color": "#3b82f6"},
    )
    assert res_lbl.status_code == 201
    label_id = res_lbl.json()["id"]

    # 2. Attach label to task
    res_attach = await client.post(
        f"/api/v1/tasks/{task.id}/labels/{label_id}",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_attach.status_code == 200

    # 3. Detach label from task
    res_detach = await client.delete(
        f"/api/v1/tasks/{task.id}/labels/{label_id}",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_detach.status_code == 204


@pytest.mark.asyncio
async def test_phase6_billing_and_plan_switching(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]

    # 1. Query usage
    res_sub = await client.get(
        "/api/v1/billing/subscription",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_sub.status_code == 200
    sub_data = res_sub.json()
    assert sub_data["plan"] == "free"
    assert sub_data["seats_limit"] >= 5

    # 2. Switch plan to Pro
    res_switch = await client.post(
        "/api/v1/billing/switch-plan",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"plan": "pro"},
    )
    assert res_switch.status_code == 200
    pro_data = res_switch.json()
    assert pro_data["plan"] == "pro"
    assert pro_data["seats_limit"] == 25
    assert pro_data["ai_credits_monthly"] == 500

    # 3. Create checkout session
    res_co = await client.post(
        "/api/v1/billing/checkout",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"plan": "enterprise"},
    )
    assert res_co.status_code == 200
    assert "checkout_url" in res_co.json()


@pytest.mark.asyncio
async def test_phase7_notifications_and_activity(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    notif_service = NotificationService(db_session, org_a.id)

    # 1. Create notification
    notif = await notif_service.create_notification(
        user_id=owner_a.id,
        title="Welcome to TaskPilot",
        message="Your workspace is fully ready.",
        type="system",
        link="/dashboard",
    )
    assert notif.id is not None

    # 2. Query notifications via API
    res_list = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["unread_count"] >= 1
    assert any(n["id"] == str(notif.id) for n in data["notifications"])

    # 3. Mark as read
    res_read = await client.patch(
        f"/api/v1/notifications/{notif.id}/read",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_read.status_code == 204

    # 4. Activity stream
    res_act = await client.get(
        "/api/v1/activity",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_act.status_code == 200
    assert isinstance(res_act.json(), list)
