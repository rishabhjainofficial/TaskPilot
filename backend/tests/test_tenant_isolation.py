import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.db.models.task import Task


@pytest.mark.asyncio
async def test_cross_tenant_read_forbidden(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    # Create project in Org A
    project_a = Project(
        org_id=org_a.id,
        name="Confidential Project A",
        key="CPA",
        created_by=owner_a.id,
    )
    db_session.add(project_a)
    await db_session.flush()

    task_a = Task(
        org_id=org_a.id,
        project_id=project_a.id,
        task_number=1,
        title="Secret Task A",
        created_by=owner_a.id,
    )
    db_session.add(task_a)
    await db_session.commit()

    # Org B user attempts to fetch tasks of project_a
    res = await client.get(
        f"/api/v1/projects/{project_a.id}/tasks",
        headers={"Authorization": f"Bearer {tokens['member_b']}"},
    )
    # Must be 403 or 404, never 200 with data
    assert res.status_code in (403, 404)

    # Org B user attempts to fetch task_a directly
    res_task = await client.get(
        f"/api/v1/tasks/{task_a.id}",
        headers={"Authorization": f"Bearer {tokens['member_b']}"},
    )
    assert res_task.status_code in (403, 404)


@pytest.mark.asyncio
async def test_cross_tenant_spoofing_prevented(client: AsyncClient, setup_orgs):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]

    # User B tries to forge X-Org-ID header to access Org A
    res = await client.get(
        "/api/v1/projects",
        headers={
            "Authorization": f"Bearer {tokens['member_b']}",
            "X-Org-ID": str(org_a.id),
        },
    )
    # Must fail with 403 Forbidden (TENANT_MISMATCH)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "TENANT_MISMATCH"


@pytest.mark.asyncio
async def test_cross_tenant_mutation_blocked(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    owner_a = setup_orgs["owner_a"]

    project_a = Project(
        org_id=org_a.id,
        name="Project A",
        key="PA",
        created_by=owner_a.id,
    )
    db_session.add(project_a)
    await db_session.commit()

    # User B tries to create a task in Project A
    res = await client.post(
        f"/api/v1/projects/{project_a.id}/tasks",
        headers={"Authorization": f"Bearer {tokens['member_b']}"},
        json={"title": "Malicious Injected Task"},
    )
    assert res.status_code in (403, 404)
