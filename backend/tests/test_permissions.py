import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_owner_permissions(client: AsyncClient, setup_orgs):
    tokens = setup_orgs["tokens"]

    # Owner can create project
    res = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"name": "Owner Project", "key": "OP", "description": "Created by owner"},
    )
    assert res.status_code == 201
    assert res.json()["name"] == "Owner Project"

    # Owner can view members
    res_members = await client.get(
        "/api/v1/org/members",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_members.status_code == 200
    assert len(res_members.json()) >= 4


@pytest.mark.asyncio
async def test_admin_permissions(client: AsyncClient, setup_orgs):
    tokens = setup_orgs["tokens"]

    # Admin can create project
    res = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {tokens['admin_a']}"},
        json={"name": "Admin Project", "key": "AP"},
    )
    assert res.status_code == 201

    # Admin can invite members
    res_inv = await client.post(
        "/api/v1/org/members/invite",
        headers={"Authorization": f"Bearer {tokens['admin_a']}"},
        json={"email": "newdev@acme.com", "role": "member"},
    )
    assert res_inv.status_code == 201


@pytest.mark.asyncio
async def test_manager_permissions(client: AsyncClient, setup_orgs):
    tokens = setup_orgs["tokens"]

    # Manager can create project
    res = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {tokens['manager_a']}"},
        json={"name": "Manager Project", "key": "MP"},
    )
    assert res.status_code == 201
    proj_id = res.json()["id"]

    # Manager CANNOT delete project (missing project.delete permission)
    res_del = await client.delete(
        f"/api/v1/projects/{proj_id}",
        headers={"Authorization": f"Bearer {tokens['manager_a']}"},
    )
    assert res_del.status_code == 403
    assert res_del.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_member_restricted_permissions(client: AsyncClient, setup_orgs):
    tokens = setup_orgs["tokens"]

    # Member cannot create projects (missing project.create)
    res = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {tokens['member_a']}"},
        json={"name": "Unauthorized Project", "key": "UP"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "PERMISSION_DENIED"

    # Member cannot invite others (missing org.members.invite)
    res_inv = await client.post(
        "/api/v1/org/members/invite",
        headers={"Authorization": f"Bearer {tokens['member_a']}"},
        json={"email": "someone@acme.com", "role": "member"},
    )
    assert res_inv.status_code == 403
