import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import re
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.passwords import hash_password, verify_password, hash_token
from app.auth.schemas import SignupRequest, LoginRequest, AcceptInviteRequest
from app.core.audit import log_audit_event
from app.core.errors import AppError, UnauthorizedError
from app.core.permissions import load_role_permissions
from app.db.models.auth_token import AuthToken
from app.db.models.invitation import Invitation
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.subscription import Subscription
from app.db.models.user import User


def generate_slug(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name).strip().lower()
    base_slug = re.sub(r"[-\s]+", "-", cleaned)[:50]
    return f"{base_slug}-{secrets.token_hex(4)}"


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def signup(self, req: SignupRequest) -> Tuple[User, Organization, str]:
        # Check existing user
        stmt = select(User).where(User.email == req.email.lower())
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise AppError(status_code=400, detail="User with this email already exists", code="EMAIL_EXISTS")

        # 1. Create Organization
        org = Organization(
            name=req.organization_name.strip(),
            slug=generate_slug(req.organization_name),
            industry=req.industry,
        )
        self.db.add(org)
        await self.db.flush()

        # 2. Create User
        user = User(
            email=req.email.lower().strip(),
            password_hash=hash_password(req.password),
            full_name=req.full_name.strip(),
            email_verified=False,
        )
        self.db.add(user)
        await self.db.flush()

        # 3. Create Owner Membership
        membership = Membership(
            org_id=org.id,
            user_id=user.id,
            org_role="owner",
            status="active",
        )
        self.db.add(membership)

        # 4. Create default Free Subscription
        subscription = Subscription(
            org_id=org.id,
            plan="free",
            status="active",
            seats_limit=5,
            projects_limit=3,
            ai_credits_monthly=50,
        )
        self.db.add(subscription)

        # 5. Create Email Verification Token
        raw_token = secrets.token_urlsafe(32)
        auth_token = AuthToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            type="email_verification",
            expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        )
        self.db.add(auth_token)

        # Log audit
        await log_audit_event(
            self.db,
            user_id=user.id,
            org_id=org.id,
            action="organization.created",
            resource_type="organization",
            resource_id=org.id,
        )

        await self.db.commit()
        return user, org, raw_token

    async def verify_email(self, raw_token: str) -> User:
        hashed = hash_token(raw_token)
        now = datetime.now(timezone.utc)

        stmt = select(AuthToken).where(
            AuthToken.token_hash == hashed,
            AuthToken.type == "email_verification",
            AuthToken.used_at == None,
            AuthToken.expires_at > now,
        )
        token_record = (await self.db.execute(stmt)).scalar_one_or_none()
        if not token_record:
            raise AppError(status_code=400, detail="Invalid or expired verification token", code="INVALID_TOKEN")

        stmt_user = select(User).where(User.id == token_record.user_id)
        user = (await self.db.execute(stmt_user)).scalar_one()

        user.email_verified = True
        token_record.used_at = now
        await self.db.commit()
        return user

    async def login(self, req: LoginRequest) -> Tuple[str, str, User, Organization, str]:
        stmt = select(User).where(User.email == req.email.lower().strip())
        user = (await self.db.execute(stmt)).scalar_one_or_none()

        if not user or not verify_password(req.password, user.password_hash):
            raise UnauthorizedError("Incorrect email or password")

        # Find active membership
        query = (
            select(Membership, Organization)
            .join(Organization, Membership.org_id == Organization.id)
            .where(Membership.user_id == user.id, Membership.status == "active")
        )
        if req.organization_id:
            query = query.where(Membership.org_id == req.organization_id)

        res = (await self.db.execute(query)).first()
        if not res and not user.is_platform_admin:
            raise UnauthorizedError("User is not an active member of any organization")

        org = res[1] if res else None
        membership = res[0] if res else None
        org_id = org.id if org else None
        role = membership.org_role if membership else ("platform_admin" if user.is_platform_admin else "member")

        access_token = create_access_token(
            user_id=user.id,
            org_id=org_id,
            org_role=role,
            is_platform_admin=user.is_platform_admin,
        )
        refresh_token, _ = create_refresh_token(user_id=user.id, org_id=org_id)

        return access_token, refresh_token, user, org, role

    async def refresh_access_token(self, refresh_token: str) -> str:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise UnauthorizedError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise UnauthorizedError("Token is not a refresh token")

        user_id = uuid.UUID(payload["sub"])
        org_id = uuid.UUID(payload["org_id"]) if payload.get("org_id") else None

        user = (await self.db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise UnauthorizedError("User not found")

        role = "member"
        if org_id:
            membership = (await self.db.execute(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.org_id == org_id,
                    Membership.status == "active",
                )
            )).scalar_one_or_none()
            if membership:
                role = membership.org_role

        return create_access_token(
            user_id=user.id,
            org_id=org_id,
            org_role=role,
            is_platform_admin=user.is_platform_admin,
        )

    async def create_invitation(
        self,
        org_id: uuid.UUID,
        inviter_id: uuid.UUID,
        email: str,
        role: str,
    ) -> Tuple[Invitation, str]:
        # Check if already active member
        stmt = (
            select(Membership)
            .join(User, Membership.user_id == User.id)
            .where(
                Membership.org_id == org_id,
                User.email == email.lower(),
                Membership.status == "active",
            )
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise AppError(status_code=400, detail="User is already a member of this organization", code="ALREADY_MEMBER")

        raw_token = secrets.token_urlsafe(32)
        invitation = Invitation(
            org_id=org_id,
            email=email.lower().strip(),
            org_role=role,
            token=hash_token(raw_token),
            status="pending",
            invited_by=inviter_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        self.db.add(invitation)
        await self.db.commit()
        return invitation, raw_token

    async def accept_invitation(self, req: AcceptInviteRequest) -> Tuple[User, Membership]:
        now = datetime.now(timezone.utc)
        hashed = hash_token(req.token)

        stmt = select(Invitation).where(
            Invitation.token == hashed,
            Invitation.status == "pending",
            Invitation.expires_at > now,
        )
        invitation = (await self.db.execute(stmt)).scalar_one_or_none()
        if not invitation:
            raise AppError(status_code=400, detail="Invalid or expired invitation token", code="INVALID_INVITATION")

        # Find or create user
        stmt_user = select(User).where(User.email == invitation.email)
        user = (await self.db.execute(stmt_user)).scalar_one_or_none()

        if not user:
            user = User(
                email=invitation.email,
                password_hash=hash_password(req.password),
                full_name=req.full_name.strip(),
                email_verified=True,  # Invitation implies email ownership
            )
            self.db.add(user)
            await self.db.flush()

        # Create or reactivate membership
        stmt_mem = select(Membership).where(
            Membership.org_id == invitation.org_id,
            Membership.user_id == user.id,
        )
        membership = (await self.db.execute(stmt_mem)).scalar_one_or_none()
        if membership:
            membership.status = "active"
            membership.org_role = invitation.org_role
        else:
            membership = Membership(
                org_id=invitation.org_id,
                user_id=user.id,
                org_role=invitation.org_role,
                status="active",
            )
            self.db.add(membership)

        invitation.status = "accepted"
        await self.db.commit()
        return user, membership
