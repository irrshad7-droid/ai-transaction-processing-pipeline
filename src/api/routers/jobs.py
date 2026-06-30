from fastapi import APIRouter, UploadFile, File, Depends, status
import structlog

from src.schemas.responses import JobCreatedResponse
from src.services.ingestion import IngestionService, get_ingestion_service
from src.workers.tasks import process_job_task

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.post("/upload", response_model=JobCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_csv(
    file: UploadFile = File(...),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    """
    Upload a CSV file for processing.
    Why: Uses HTTP 202 (Accepted) because the heavy lifting happens asynchronously.
    The router is extremely thin; all logic is delegated to the IngestionService.
    """
    logger.info("upload_csv_endpoint_hit", filename=file.filename)
    
    # Delegate parsing, validation, and DB staging to the service layer
    job = await ingestion_service.process_upload(file)
    
    # Fire and forget the Celery background task
    process_job_task.delay(str(job.id))
    logger.info("celery_task_queued", job_id=str(job.id))
    
    return JobCreatedResponse(
        job_id=job.id,
        status=job.status.value
    )
