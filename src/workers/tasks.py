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

@celery_app.task(bind=True, max_retries=3)
def process_job_task(self, job_id: str):
    """
    Main orchestrator task for processing an uploaded CSV file.
    Why: Handles the asynchronous pipeline (clean -> analyze -> llm -> summarize).
    Currently just a placeholder that logs the job_id.
    """
    logger.info("processing_job_started", job_id=job_id)
    # TODO: Implement Milestone 4 logic here
    logger.info("processing_job_completed", job_id=job_id)
    return {"job_id": job_id, "status": "COMPLETED"}
