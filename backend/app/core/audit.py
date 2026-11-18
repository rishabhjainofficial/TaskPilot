import uuid
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog


async def log_audit_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    action: str,
    org_id: Optional[uuid.UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[uuid.UUID] = None,
    before_state: Optional[dict[str, Any]] = None,
    after_state: Optional[dict[str, Any]] = None,
    ai: bool = False,
    impersonated_by: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[uuid.UUID] = None,
) -> AuditLog:
    """Logs an audit event to the audit_logs table."""
    log_entry = AuditLog(
        org_id=org_id,
        user_id=user_id,
        impersonated_by=impersonated_by,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        ai=ai,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    db.add(log_entry)
    await db.flush()
    return log_entry
