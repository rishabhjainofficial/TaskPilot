import uuid
from typing import List, Optional
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.websockets import ws_manager
from app.db.models.notification import Notification
from app.db.models.audit_log import AuditLog
from app.db.models.user import User
from app.notifications.schemas import NotificationResponse, NotificationListResponse, ActivityItemResponse


class NotificationService:
    def __init__(self, db: AsyncSession, org_id: uuid.UUID):
        self.db = db
        self.org_id = org_id

    async def create_notification(
        self,
        user_id: uuid.UUID,
        title: str,
        message: str,
        type: str = "system",
        link: Optional[str] = None,
    ) -> Notification:
        notif = Notification(
            org_id=self.org_id,
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            link=link,
            is_read=False,
        )
        self.db.add(notif)
        await self.db.commit()

        # Real-time WebSocket delivery
        await ws_manager.send_to_user(
            org_id=self.org_id,
            user_id=user_id,
            event="notification_received",
            payload={
                "id": str(notif.id),
                "title": notif.title,
                "message": notif.message,
                "type": notif.type,
                "link": notif.link,
                "created_at": notif.created_at.isoformat(),
            },
        )
        return notif

    async def list_notifications(self, user_id: uuid.UUID, limit: int = 50) -> NotificationListResponse:
        stmt = (
            select(Notification)
            .where(
                Notification.org_id == self.org_id,
                Notification.user_id == user_id,
            )
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        notifs = list((await self.db.execute(stmt)).scalars().all())

        stmt_count = select(func.count(Notification.id)).where(
            Notification.org_id == self.org_id,
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
        unread = (await self.db.execute(stmt_count)).scalar_one() or 0

        return NotificationListResponse(
            unread_count=unread,
            notifications=[
                NotificationResponse(
                    id=n.id,
                    org_id=n.org_id,
                    user_id=n.user_id,
                    type=n.type,
                    title=n.title,
                    message=n.message,
                    link=n.link,
                    is_read=n.is_read,
                    created_at=n.created_at,
                )
                for n in notifs
            ],
        )

    async def mark_as_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.org_id == self.org_id,
        )
        notif = (await self.db.execute(stmt)).scalar_one_or_none()
        if not notif:
            raise NotFoundError("Notification", notification_id)
        notif.is_read = True
        await self.db.commit()

    async def mark_all_as_read(self, user_id: uuid.UUID) -> None:
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.org_id == self.org_id,
                Notification.is_read == False,
            )
            .values(is_read=True)
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def list_activity(self, limit: int = 25) -> List[ActivityItemResponse]:
        """Returns recent audit logs for the tenant activity stream."""
        stmt = (
            select(AuditLog, User)
            .join(User, AuditLog.user_id == User.id)
            .where(AuditLog.org_id == self.org_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            ActivityItemResponse(
                id=log.id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                user_id=user.id,
                user_full_name=user.full_name,
                user_email=user.email,
                created_at=log.created_at,
            )
            for log, user in rows
        ]
