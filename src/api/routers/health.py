from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.db.database import get_db
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

@router.get("/health", response_model=dict, tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Deep health check endpoint.
    Why: Verifies that both the application is running AND the DB connection is active.
    Required by Kubernetes/Docker for readiness probes.
    """
    try:
        # Ping the database
        await db.execute(text("SELECT 1"))
        logger.info("health_check_success")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {"status": "unhealthy", "database": "disconnected"}
