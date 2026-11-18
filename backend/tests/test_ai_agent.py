import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_proposal import AIProposal
from app.db.models.ai_usage import AIUsage
from app.db.models.project import Project
from app.db.models.subscription import Subscription
from app.db.models.task import Task


@pytest.mark.asyncio
async def test_ai_chat_propose_confirm_flow(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    # 1. Create a Project
    project = Project(
        org_id=org_a.id,
        name="Hotel Operations",
        key="HOTEL",
        created_by=owner_a.id,
    )
    db_session.add(project)
    await db_session.commit()

    # 2. Chat with AI requesting a new task
    res_chat = await client.post(
        f"/api/v1/projects/{project.id}/ai/chat",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"message": "Please create task for kitchen morning prep"},
    )
    assert res_chat.status_code == 200
    chat_data = res_chat.json()
    assert "proposal" in chat_data
    proposal = chat_data["proposal"]
    assert proposal is not None
    assert proposal["status"] == "pending"
    proposal_id = proposal["id"]

    # 3. Verify task is NOT created in DB yet (Propose then Confirm principle)
    stmt_tasks = select(Task).where(Task.project_id == project.id)
    tasks_before = list((await db_session.execute(stmt_tasks)).scalars().all())
    assert len(tasks_before) == 0

    # 4. Confirm Proposal
    res_confirm = await client.post(
        f"/api/v1/ai/proposals/{proposal_id}/confirm",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_confirm.status_code == 200
    assert res_confirm.json()["status"] == "accepted"

    # 5. Verify task is now officially created in the DB with task number
    tasks_after = list((await db_session.execute(stmt_tasks)).scalars().all())
    assert len(tasks_after) == 1
    assert tasks_after[0].task_number == 1


@pytest.mark.asyncio
async def test_ai_proposal_permission_enforcement(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]
    member_a = setup_orgs["member_a"]

    project = Project(
        org_id=org_a.id,
        name="Operations",
        key="OPS",
        created_by=owner_a.id,
    )
    db_session.add(project)
    await db_session.commit()

    # Chat as Member requesting a task
    res_chat = await client.post(
        f"/api/v1/projects/{project.id}/ai/chat",
        headers={"Authorization": f"Bearer {tokens['member_a']}"},
        json={"message": "Create task for night audit"},
    )
    assert res_chat.status_code == 200
    proposal = res_chat.json()["proposal"]
    proposal_id = proposal["id"]

    # Member attempts to confirm proposal (Member lacks 'task.create' permission)
    res_confirm = await client.post(
        f"/api/v1/ai/proposals/{proposal_id}/confirm",
        headers={"Authorization": f"Bearer {tokens['member_a']}"},
    )
    # Must fail with 403 Forbidden
    assert res_confirm.status_code == 403
    assert res_confirm.json()["error"]["code"] == "PERMISSION_DENIED"

    # Verify task was NOT created in DB
    stmt_tasks = select(Task).where(Task.project_id == project.id)
    tasks = list((await db_session.execute(stmt_tasks)).scalars().all())
    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_ai_proposal_rejection(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    project = Project(
        org_id=org_a.id,
        name="Boutique Hotel",
        key="BTH",
        created_by=owner_a.id,
    )
    db_session.add(project)
    await db_session.commit()

    res_chat = await client.post(
        f"/api/v1/projects/{project.id}/ai/chat",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"message": "Create task for housekeeping inventory"},
    )
    proposal_id = res_chat.json()["proposal"]["id"]

    # Reject proposal
    res_reject = await client.post(
        f"/api/v1/ai/proposals/{proposal_id}/reject",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "rejected"

    # Confirming a rejected proposal must fail
    res_confirm_again = await client.post(
        f"/api/v1/ai/proposals/{proposal_id}/confirm",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_confirm_again.status_code == 400


@pytest.mark.asyncio
async def test_ai_usage_and_credits_limit(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    project = Project(
        org_id=org_a.id,
        name="Tech Project",
        key="TECH",
        created_by=owner_a.id,
    )
    # Set limit to 1 credit
    sub = Subscription(
        org_id=org_a.id,
        plan="free",
        status="active",
        ai_credits_monthly=1,
    )
    db_session.add_all([project, sub])
    await db_session.commit()

    # Request 1 (uses the 1 credit)
    res_1 = await client.post(
        f"/api/v1/projects/{project.id}/ai/chat",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"message": "Hello AI"},
    )
    assert res_1.status_code == 200

    # Verify ai_usage logged
    stmt_usage = select(AIUsage).where(AIUsage.org_id == org_a.id)
    usage = list((await db_session.execute(stmt_usage)).scalars().all())
    assert len(usage) == 1

    # Request 2 (credits exhausted)
    res_2 = await client.post(
        f"/api/v1/projects/{project.id}/ai/chat",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"message": "Second message"},
    )
    assert res_2.status_code == 402
    assert res_2.json()["error"]["code"] == "AI_CREDITS_EXHAUSTED"


@pytest.mark.asyncio
async def test_onboarding_starter_project(client: AsyncClient, setup_orgs):
    tokens = setup_orgs["tokens"]

    res = await client.post(
        "/api/v1/ai/onboarding-project",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={
            "team_description": "25-room boutique hotel with café and pool",
            "project_name": "Hotel Master Ops",
            "project_key": "HMO",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["project"]["key"] == "HMO"
    assert "proposal" in data
