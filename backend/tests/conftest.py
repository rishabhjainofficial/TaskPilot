import asyncio
import os
import uuid
import pytest
import pytest_asyncio

# Enforce test environment
os.environ["ENVIRONMENT"] = "test"

from httpx import AsyncClient, ASGITransport
from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, INET
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

# Adapt Postgres dialect types when using SQLite in tests
from sqlalchemy.ext.compiler import compiles


@compiles(PG_UUID, "sqlite")
def compile_pg_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(INET, "sqlite")
def compile_inet_sqlite(type_, compiler, **kw):
    return "VARCHAR(45)"


from app.auth.jwt import create_access_token
from app.auth.passwords import hash_password
from app.db.base import Base
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.permission import Permission, RolePermission
from app.db.models.project import Project
from app.db.models.task import Task
from app.db.models.user import User
from app.dependencies import get_db, get_tenant_db
from app.main import app

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def seed_permissions(db_session: AsyncSession):
    from seeds.seed_roles_permissions import PERMISSIONS, ROLE_BUNDLES

    perm_map = {}
    for code, desc in PERMISSIONS:
        perm = Permission(code=code, description=desc)
        db_session.add(perm)
        await db_session.flush()
        perm_map[code] = perm.id

    for (role, scope), perms in ROLE_BUNDLES.items():
        for code in perms:
            rp = RolePermission(role=role, scope=scope, permission_id=perm_map[code])
            db_session.add(rp)

    await db_session.commit()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    async def override_get_tenant_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_tenant_db] = override_get_tenant_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def setup_orgs(db_session: AsyncSession, seed_permissions):
    # Org A
    org_a = Organization(name="Acme Corp", slug="acme-corp")
    db_session.add(org_a)
    await db_session.flush()

    # Org B
    org_b = Organization(name="Beta LLC", slug="beta-llc")
    db_session.add(org_b)
    await db_session.flush()

    # Org C (for 3+ tenant peer testing)
    org_c = Organization(name="Gamma Inc", slug="gamma-inc")
    db_session.add(org_c)
    await db_session.flush()

    # Users in Org A
    owner_a = User(email="owner@acme.com", full_name="Owner A", password_hash=hash_password("password123"), email_verified=True)
    admin_a = User(email="admin@acme.com", full_name="Admin A", password_hash=hash_password("password123"), email_verified=True)
    manager_a = User(email="manager@acme.com", full_name="Manager A", password_hash=hash_password("password123"), email_verified=True)
    member_a = User(email="member@acme.com", full_name="Member A", password_hash=hash_password("password123"), email_verified=True)

    # User in Org B
    member_b = User(email="member@beta.com", full_name="Member B", password_hash=hash_password("password123"), email_verified=True)

    # User in multiple orgs (Org A manager and Org C owner)
    multi_user = User(email="multi@domain.com", full_name="Multi User", password_hash=hash_password("password123"), email_verified=True)

    db_session.add_all([owner_a, admin_a, manager_a, member_a, member_b, multi_user])
    await db_session.flush()

    # Memberships
    db_session.add(Membership(org_id=org_a.id, user_id=owner_a.id, org_role="owner", status="active"))
    db_session.add(Membership(org_id=org_a.id, user_id=admin_a.id, org_role="admin", status="active"))
    db_session.add(Membership(org_id=org_a.id, user_id=manager_a.id, org_role="manager", status="active"))
    db_session.add(Membership(org_id=org_a.id, user_id=member_a.id, org_role="member", status="active"))

    db_session.add(Membership(org_id=org_b.id, user_id=member_b.id, org_role="owner", status="active"))

    # Multi-org memberships
    db_session.add(Membership(org_id=org_a.id, user_id=multi_user.id, org_role="manager", status="active"))
    db_session.add(Membership(org_id=org_c.id, user_id=multi_user.id, org_role="owner", status="active"))
    await db_session.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "org_c": org_c,
        "owner_a": owner_a,
        "admin_a": admin_a,
        "manager_a": manager_a,
        "member_a": member_a,
        "member_b": member_b,
        "multi_user": multi_user,
        "tokens": {
            "owner_a": create_access_token(owner_a.id, org_id=org_a.id, org_role="owner"),
            "admin_a": create_access_token(admin_a.id, org_id=org_a.id, org_role="admin"),
            "manager_a": create_access_token(manager_a.id, org_id=org_a.id, org_role="manager"),
            "member_a": create_access_token(member_a.id, org_id=org_a.id, org_role="member"),
            "member_b": create_access_token(member_b.id, org_id=org_b.id, org_role="owner"),
            "multi_user_a": create_access_token(multi_user.id, org_id=org_a.id, org_role="manager"),
            "multi_user_c": create_access_token(multi_user.id, org_id=org_c.id, org_role="owner"),
        }
    }
