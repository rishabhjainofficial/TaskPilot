import uuid
from typing import AsyncGenerator, Optional
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token
from app.core.errors import UnauthorizedError, TenantMismatchError
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.user import User
from app.db.session import AsyncSessionLocal, set_tenant_context

security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if not credentials or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token")
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        return payload
    except jwt.PyJWTError:
        raise UnauthorizedError("Invalid or expired token")


async def get_current_user(
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError("Token contains no subject")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedError("Malformed user ID in token")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("User does not exist")
    return user


async def get_current_org_id(
    payload: dict = Depends(get_current_token_payload),
    user: User = Depends(get_current_user),
    x_org_id: Optional[str] = Header(None, alias="X-Org-ID"),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """
    Retrieves the current tenant org_id.
    Prioritizes explicit X-Org-ID if provided, otherwise token org_id.
    Validates that the user is an active member of this organization,
    and that the organization has not been soft-deleted.
    """
    await set_tenant_context(db, user_id=user.id)
    raw_org_id = x_org_id or payload.get("org_id")
    if not raw_org_id:
        stmt = (
            select(Membership.org_id)
            .join(Organization, Membership.org_id == Organization.id)
            .where(
                Membership.user_id == user.id,
                Membership.status == "active",
                Organization.deleted_at.is_(None),
            )
            .limit(1)
        )
        res = await db.execute(stmt)
        active_org = res.scalar_one_or_none()
        if not active_org:
            raise TenantMismatchError()
        return active_org

    try:
        target_org_id = uuid.UUID(raw_org_id)
    except ValueError:
        raise TenantMismatchError()

    if user.is_platform_admin:
        # Check that the target org exists and is not soft deleted
        stmt_org = select(Organization.id).where(
            Organization.id == target_org_id,
            Organization.deleted_at.is_(None),
        )
        res_org = await db.execute(stmt_org)
        if not res_org.scalar_one_or_none():
            raise TenantMismatchError()
        return target_org_id

    # Verify that the user has an active membership in the target organization and org is not deleted
    stmt = (
        select(Membership)
        .join(Organization, Membership.org_id == Organization.id)
        .where(
            Membership.user_id == user.id,
            Membership.org_id == target_org_id,
            Membership.status == "active",
            Organization.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise TenantMismatchError()

    return target_org_id


async def get_tenant_db(
    org_id: uuid.UUID = Depends(get_current_org_id),
    user: User = Depends(get_current_user),
) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(session, org_id=org_id, user_id=user.id)
            yield session
