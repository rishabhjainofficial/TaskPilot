import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_current_org_id, get_tenant_db
from app.db.models.user import User
from app.notifications.schemas import NotificationListResponse, ActivityItemResponse
from app.notifications.service import NotificationService

router = APIRouter(tags=["Notifications & Activity"])


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = NotificationService(db, org_id)
    return await service.list_notifications(user.id)


@router.patch("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = NotificationService(db, org_id)
    await service.mark_as_read(user.id, notification_id)


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_read(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = NotificationService(db, org_id)
    await service.mark_all_as_read(user.id)


@router.get("/activity", response_model=List[ActivityItemResponse])
async def list_tenant_activity(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = NotificationService(db, org_id)
    return await service.list_activity()
