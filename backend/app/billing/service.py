import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.quotas import get_or_create_subscription
from app.billing.schemas import SubscriptionUsageResponse, CheckoutResponse
from app.config import get_settings
from app.core.audit import log_audit_event
from app.core.errors import AppError, NotFoundError
from app.db.models.subscription import Subscription
from app.db.models.project import Project
from app.db.models.membership import Membership
from app.db.models.ai_usage import AIUsage
from app.db.models.attachment import Attachment
from app.db.models.user import User

settings = get_settings()

PLAN_TIERS = {
    "free": {
        "seats_limit": 10,
        "projects_limit": 5,
        "ai_credits_monthly": 50,
        "storage_bytes_limit": 104857600,  # 100 MB
    },
    "pro": {
        "seats_limit": 25,
        "projects_limit": 20,
        "ai_credits_monthly": 500,
        "storage_bytes_limit": 10737418240,  # 10 GB
    },
    "enterprise": {
        "seats_limit": 200,
        "projects_limit": 100,
        "ai_credits_monthly": 5000,
        "storage_bytes_limit": 107374182400,  # 100 GB
    },
}


class BillingService:
    def __init__(self, db: AsyncSession, org_id: uuid.UUID):
        self.db = db
        self.org_id = org_id

    async def get_usage(self) -> SubscriptionUsageResponse:
        sub = await get_or_create_subscription(self.db, self.org_id)

        # 1. Projects used
        stmt_proj = select(func.count(Project.id)).where(Project.org_id == self.org_id)
        projects_used = (await self.db.execute(stmt_proj)).scalar_one() or 0

        # 2. Seats used
        stmt_seats = select(func.count(Membership.id)).where(
            Membership.org_id == self.org_id,
            Membership.status == "active",
        )
        seats_used = (await self.db.execute(stmt_seats)).scalar_one() or 0

        # 3. Monthly AI credits used
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stmt_ai = select(func.count(AIUsage.id)).where(
            AIUsage.org_id == self.org_id,
            AIUsage.created_at >= month_start,
        )
        ai_credits_used = (await self.db.execute(stmt_ai)).scalar_one() or 0

        # 4. Storage bytes used
        stmt_storage = select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
            Attachment.org_id == self.org_id,
        )
        storage_bytes_used = (await self.db.execute(stmt_storage)).scalar_one() or 0

        return SubscriptionUsageResponse(
            id=sub.id,
            org_id=sub.org_id,
            plan=sub.plan,
            status=sub.status,
            seats_limit=sub.seats_limit,
            seats_used=seats_used,
            projects_limit=sub.projects_limit,
            projects_used=projects_used,
            ai_credits_monthly=sub.ai_credits_monthly,
            ai_credits_used=ai_credits_used,
            storage_bytes_limit=sub.storage_bytes_limit,
            storage_bytes_used=storage_bytes_used,
            current_period_end=sub.current_period_end,
        )

    async def switch_plan(self, user: User, target_plan: str) -> Subscription:
        if target_plan not in PLAN_TIERS:
            raise AppError(status_code=400, detail=f"Invalid plan tier: {target_plan}")

        sub = await get_or_create_subscription(self.db, self.org_id)
        before_plan = sub.plan

        tier = PLAN_TIERS[target_plan]
        sub.plan = target_plan
        sub.status = "active"
        sub.seats_limit = tier["seats_limit"]
        sub.projects_limit = tier["projects_limit"]
        sub.ai_credits_monthly = tier["ai_credits_monthly"]
        sub.storage_bytes_limit = tier["storage_bytes_limit"]
        sub.current_period_start = datetime.now(timezone.utc)
        sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)

        await log_audit_event(
            self.db,
            user_id=user.id,
            org_id=self.org_id,
            action="subscription.plan_changed",
            resource_type="subscription",
            resource_id=sub.id,
            before_state={"plan": before_plan},
            after_state={"plan": target_plan},
        )
        await self.db.commit()
        return sub

    async def create_checkout_session(
        self,
        user: User,
        plan: str,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> CheckoutResponse:
        sub = await get_or_create_subscription(self.db, self.org_id)

        # In local/test or without real stripe keys, provide instant upgrade URL
        session_id = f"cs_test_{uuid.uuid4().hex[:16]}"
        checkout_url = success_url or f"/settings/billing?checkout_success={session_id}&plan={plan}"

        return CheckoutResponse(
            checkout_url=checkout_url,
            session_id=session_id,
        )

    async def handle_webhook(self, event_type: str, data: Dict[str, Any]) -> None:
        """Processes Stripe subscription webhooks idempotently."""
        org_id_str = data.get("client_reference_id") or data.get("metadata", {}).get("org_id")
        if not org_id_str:
            return

        try:
            org_id = uuid.UUID(org_id_str)
        except ValueError:
            return

        stmt = select(Subscription).where(Subscription.org_id == org_id)
        sub = (await self.db.execute(stmt)).scalar_one_or_none()
        if not sub:
            return

        if event_type == "customer.subscription.updated":
            status_val = data.get("status", "active")
            sub.status = status_val
        elif event_type == "customer.subscription.deleted":
            # Revert to free tier
            tier = PLAN_TIERS["free"]
            sub.plan = "free"
            sub.status = "canceled"
            sub.seats_limit = tier["seats_limit"]
            sub.projects_limit = tier["projects_limit"]
            sub.ai_credits_monthly = tier["ai_credits_monthly"]
            sub.storage_bytes_limit = tier["storage_bytes_limit"]

        await self.db.commit()
