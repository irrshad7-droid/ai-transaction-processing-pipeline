from src.core.celery_app import celery_app
import structlog

logger = structlog.get_logger(__name__)

@celery_app.task(bind=True, max_retries=3)
def health_check_task(self):
    """
    Simple task to verify Celery is processing correctly.
    Why: We need an isolated way to test worker connectivity without triggering heavy DB/LLM workloads.
    """
    logger.info("health_check_task_executed")
    return {"status": "ok"}

import asyncio
from src.db.database import AsyncSessionLocal
from src.services.processing import ProcessingService

@celery_app.task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def process_job_task(self, job_id: str):
    """
    Main orchestrator task for processing an uploaded CSV file.
    Why: Handles the asynchronous pipeline (clean -> analyze -> llm -> summarize).
    Uses asyncio.run to execute the async ProcessingService within the synchronous Celery worker.
    """
    logger.info("processing_job_started", job_id=job_id)
    try:
        asyncio.run(_run_processing(job_id))
    except Exception as e:
        logger.error("processing_job_failed", job_id=job_id, error=str(e), exc_info=True)
        # Celery will retry automatically due to autoretry_for
        raise

async def _run_processing(job_id: str):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from src.core.config import settings
    
    # Create an isolated engine per task to ensure connection pool binds 
    # strictly to the new event loop created by asyncio.run()
    task_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        future=True,
        pool_size=5,
        max_overflow=10,
    )
    
    TaskSessionLocal = async_sessionmaker(
        bind=task_engine, 
        class_=AsyncSession, 
        expire_on_commit=False,
        autoflush=False
    )
    
    try:
        async with TaskSessionLocal() as db:
            service = ProcessingService(db)
            await service.process_job(job_id)
    finally:
        # Ensure the engine and its connection pool are closed before the event loop dies
        await task_engine.dispose()
