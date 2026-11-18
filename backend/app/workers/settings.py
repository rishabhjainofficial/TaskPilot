import asyncio
from arq.connections import RedisSettings
from app.config import get_settings

settings = get_settings()


async def startup(ctx):
    print("🚀 ARQ Worker starting up...")


async def shutdown(ctx):
    print("🛑 ARQ Worker shutting down...")


class WorkerSettings:
    functions = []
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
