from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import DATABASE_URL
import asyncio
import logging

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()

logger = logging.getLogger("backend.database")


async def init_db():
    # create tables (blocking run_sync) with basic retry while Postgres starts
    attempt = 0
    while True:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception as e:
            attempt += 1
            wait_seconds = min(5, 0.5 * attempt)
            logger.warning(
                f"Database not ready (attempt {attempt}): {e}. Retrying in {wait_seconds}s..."
            )
            await asyncio.sleep(wait_seconds)
