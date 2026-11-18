import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_and_verify_email(client: AsyncClient, seed_permissions):
    # 1. Signup
    signup_data = {
        "email": "sarah@startup.io",
        "password": "SecurePassword123!",
        "full_name": "Sarah Connor",
        "organization_name": "Cyberdyne Systems",
        "industry": "technology",
    }
    res = await client.post("/api/v1/auth/signup", json=signup_data)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "sarah@startup.io"
    assert "organization_id" in data
    raw_token = data.get("email_verification_token")
    assert raw_token is not None

    # 2. Verify Email
    res_verify = await client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert res_verify.status_code == 200
    assert res_verify.json()["status"] == "ok"

    # 3. Login
    login_data = {
        "email": "sarah@startup.io",
        "password": "SecurePassword123!",
    }
    res_login = await client.post("/api/v1/auth/login", json=login_data)
    assert res_login.status_code == 200
    tokens = res_login.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["role"] == "owner"

    # 4. Refresh token
    res_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert res_refresh.status_code == 200
    assert "access_token" in res_refresh.json()


@pytest.mark.asyncio
async def test_invite_and_accept_flow(client: AsyncClient, setup_orgs):
    tokens = setup_orgs["tokens"]

    # 1. Admin sends invite
    res_invite = await client.post(
        "/api/v1/org/members/invite",
        headers={"Authorization": f"Bearer {tokens['admin_a']}"},
        json={"email": "johndoe@test.com", "role": "manager"},
    )
    assert res_invite.status_code == 201
    raw_token = res_invite.json()["token"]
    assert raw_token is not None

    # 2. John accepts invite and creates password
    res_accept = await client.post(
        "/api/v1/auth/accept-invite",
        json={
            "token": raw_token,
            "full_name": "John Doe",
            "password": "PasswordForJohn123!",
        },
    )
    assert res_accept.status_code == 200
    assert res_accept.json()["role"] == "manager"

    # 3. John logs in
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "johndoe@test.com", "password": "PasswordForJohn123!"},
    )
    assert res_login.status_code == 200
    assert res_login.json()["role"] == "manager"
