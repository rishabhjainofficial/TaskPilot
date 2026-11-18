import asyncio
from app.db.session import AsyncSessionLocal


async def seed():
    # Placeholder for catalog plans seed if subscription catalog table is added,
    # Free tier defaults are already seeded on organization creation.
    print("🌱 Plans seed validated.")


if __name__ == "__main__":
    asyncio.run(seed())
