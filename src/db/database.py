from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from src.core.config import settings

# We use asyncpg for high-throughput non-blocking DB access in FastAPI.
engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    future=True,
    # Connection pool settings for production
    pool_size=20,
    max_overflow=10,
)

# Session factory bound to the async engine
AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db() -> AsyncSession: # type: ignore
    """
    FastAPI dependency that provides an asynchronous database session.
    Why: Handles explicit setup and teardown of the connection per request.
    Yields connection to route, ensuring it's always closed in `finally`.
    """
    async with AsyncSessionLocal() as session:
        yield session
