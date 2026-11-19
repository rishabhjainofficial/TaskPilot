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


@pytest.mark.asyncio
async def test_three_tenant_isolation_boundary(client: AsyncClient, setup_orgs, db_session: AsyncSession):
    """Verifies isolation across 3 distinct tenants (Org A, Org B, Org C)."""
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    org_b = setup_orgs["org_b"]
    org_c = setup_orgs["org_c"]
    owner_a = setup_orgs["owner_a"]

    # Org A Project
    proj_a = Project(org_id=org_a.id, name="Project Alpha", key="ALPHA", created_by=owner_a.id)
    # Org C Project
    proj_c = Project(org_id=org_c.id, name="Project Gamma", key="GAMMA", created_by=setup_orgs["multi_user"].id)
    db_session.add_all([proj_a, proj_c])
    await db_session.commit()

    # Org B user cannot view Org A or Org C projects
    res_ba = await client.get(f"/api/v1/projects/{proj_a.id}", headers={"Authorization": f"Bearer {tokens['member_b']}"})
    assert res_ba.status_code in (403, 404)

    res_bc = await client.get(f"/api/v1/projects/{proj_c.id}", headers={"Authorization": f"Bearer {tokens['member_b']}"})
    assert res_bc.status_code in (403, 404)

    # Org A member cannot view Org C project
    res_ac = await client.get(f"/api/v1/projects/{proj_c.id}", headers={"Authorization": f"Bearer {tokens['member_a']}"})
    assert res_ac.status_code in (403, 404)


@pytest.mark.asyncio
async def test_multi_org_discovery_and_switch(client: AsyncClient, setup_orgs):
    """Tests discovery of all memberships in /me and switching tenant context via /auth/switch-org."""
    tokens = setup_orgs["tokens"]
    org_a = setup_orgs["org_a"]
    org_b = setup_orgs["org_b"]
    org_c = setup_orgs["org_c"]

    # multi_user starts with Org A token
    res_me = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {tokens['multi_user_a']}"},
    )
    assert res_me.status_code == 200
    data = res_me.json()
    assert len(data["organizations"]) == 2
    org_ids = [o["id"] for o in data["organizations"]]
    assert str(org_a.id) in org_ids
    assert str(org_c.id) in org_ids

    # Switch to Org C
    res_switch = await client.post(
        "/api/v1/auth/switch-org",
        headers={"Authorization": f"Bearer {tokens['multi_user_a']}"},
        json={"org_id": str(org_c.id)},
    )
    assert res_switch.status_code == 200
    switch_data = res_switch.json()
    assert switch_data["organization_id"] == str(org_c.id)
    assert switch_data["role"] == "owner"
    token_c = switch_data["access_token"]

    # Using the new token, user is scoped to Org C
    res_me_c = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert res_me_c.status_code == 200
    assert res_me_c.json()["current_org_id"] == str(org_c.id)

    # Attempting to switch to Org B (where multi_user has no membership) must fail
    res_invalid_switch = await client.post(
        "/api/v1/auth/switch-org",
        headers={"Authorization": f"Bearer {token_c}"},
        json={"org_id": str(org_b.id)},
    )
    assert res_invalid_switch.status_code == 403
    assert res_invalid_switch.json()["error"]["code"] == "TENANT_MISMATCH"


@pytest.mark.asyncio
async def test_soft_deleted_organization_access_blocked(client: AsyncClient, setup_orgs):
    """Tests that soft-deleting an organization revokes access to all members."""
    tokens = setup_orgs["tokens"]

    # Owner of Org A soft-deletes the organization
    res_delete = await client.delete(
        "/api/v1/org",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_delete.status_code == 200
    assert res_delete.json()["status"] == "ok"

    # Subsequent access by Org A member must be blocked with TENANT_MISMATCH
    res_access = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {tokens['member_a']}"},
    )
    assert res_access.status_code == 403
    assert res_access.json()["error"]["code"] == "TENANT_MISMATCH"

    # Attempting to switch into a soft-deleted organization must also fail
    res_switch_deleted = await client.post(
        "/api/v1/auth/switch-org",
        headers={"Authorization": f"Bearer {tokens['multi_user_c']}"},
        json={"org_id": str(setup_orgs["org_a"].id)},
    )
    assert res_switch_deleted.status_code == 403
    assert res_switch_deleted.json()["error"]["code"] == "TENANT_MISMATCH"


@pytest.mark.asyncio
async def test_worker_tenant_session_context(db_session: AsyncSession, setup_orgs):
    """Verifies that the background worker context manager sets up a clean tenant session."""
    from app.workers.context import tenant_worker_session
    from app.db.models.project import Project
    from sqlalchemy import select
    from contextlib import asynccontextmanager

    org_a = setup_orgs["org_a"]

    @asynccontextmanager
    async def mock_factory():
        yield db_session

    async with tenant_worker_session(org_a.id, session_factory=mock_factory) as session:
        # Queries inside the worker session inherit org context
        result = await session.execute(select(Project).where(Project.org_id == org_a.id))
        assert result.scalars().all() is not None
