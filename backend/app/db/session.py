import uuid
from typing import AsyncGenerator, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine_kwargs = {}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 3600

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def is_sqlite_session(session: AsyncSession) -> bool:
    if session.bind is not None and hasattr(session.bind, "dialect"):
        return session.bind.dialect.name == "sqlite"
    return is_sqlite


async def set_tenant_context(
    session: AsyncSession,
    org_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
) -> None:
    if not is_sqlite_session(session):
        if org_id is not None:
            await session.execute(
                text("SET LOCAL app.current_org = :org_id"),
                {"org_id": str(org_id)}
            )
        if user_id is not None:
            await session.execute(
                text("SET LOCAL app.current_user_id = :user_id"),
                {"user_id": str(user_id)}
            )


async def set_invitation_redeem_context(session: AsyncSession) -> None:
    if not is_sqlite_session(session):
        await session.execute(
            text("SET LOCAL app.invitation_lookup_mode = 'token_redeem'")
        )
