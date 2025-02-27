import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


async def get_db():
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://user:password@user_db/user_db"
    )

    engine = create_async_engine(DATABASE_URL, echo=True)
    SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore
    async with SessionLocal() as session:  # type: ignore
        yield session
