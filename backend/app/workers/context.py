import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal, set_tenant_context


@asynccontextmanager
async def tenant_worker_session(
    org_id: uuid.UUID,
    session_factory=None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for background workers (e.g. ARQ jobs).
    Sets the transaction-local PostgreSQL tenant context for safe RLS execution.
    """
    factory = session_factory or AsyncSessionLocal
    async with factory() as session:
        async with session.begin():
            await set_tenant_context(session, org_id=org_id)
            yield session
