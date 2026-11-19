import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.schemas import SubscriptionUsageResponse, CheckoutRequest, CheckoutResponse, PlanSwitchRequest
from app.billing.service import BillingService
from app.config import get_settings
from app.core.errors import AppError
from app.core.permissions import require_permission
from app.dependencies import get_current_user, get_current_org_id, get_tenant_db, get_db
from app.db.models.user import User

settings = get_settings()

router = APIRouter(prefix="/billing", tags=["Billing & Subscriptions"])


@router.get("/subscription", response_model=SubscriptionUsageResponse)
async def get_subscription(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = BillingService(db, org_id)
    return await service.get_usage()


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("org.billing")),
):
    service = BillingService(db, org_id)
    return await service.create_checkout_session(
        user=user,
        plan=body.plan,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )


@router.post("/switch-plan", response_model=SubscriptionUsageResponse)
async def switch_plan(
    body: PlanSwitchRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("org.billing")),
):
    service = BillingService(db, org_id)
    await service.switch_plan(user, body.plan)
    return await service.get_usage()


@router.post("/webhook")
async def billing_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    signature_header = request.headers.get("Stripe-Signature")

    if settings.STRIPE_WEBHOOK_SECRET:
        if not signature_header:
            raise AppError(status_code=400, detail="Missing Stripe-Signature header")
        import hmac
        import hashlib
        try:
            parts = dict(p.strip().split("=", 1) for p in signature_header.split(",") if "=" in p)
            timestamp = parts.get("t", "")
            v1_sig = parts.get("v1", "")
            signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
            expected_sig = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(v1_sig, expected_sig):
                raise AppError(status_code=400, detail="Invalid Stripe webhook signature")
        except Exception as e:
            if isinstance(e, AppError):
                raise e
            raise AppError(status_code=400, detail="Malformed Stripe-Signature header")

    import json
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise AppError(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("type", "")
    data = payload.get("data", {}).get("object", {})

    service = BillingService(db, uuid.uuid4())
    await service.handle_webhook(event_type, data)
    return {"status": "ok"}

