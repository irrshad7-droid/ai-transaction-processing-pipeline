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
