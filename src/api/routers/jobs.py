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

from fastapi import Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_db
from sqlalchemy import select, func
from src.db.models import Job
from src.schemas.responses import JobSummaryResponse
from pydantic import BaseModel

class PaginatedJobListResponse(BaseModel):
    items: list[JobSummaryResponse]
    total: int
    page: int
    size: int

@router.get("", response_model=PaginatedJobListResponse)
async def list_jobs(
    status: Optional[str] = None,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=1000, description="Items per page"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all jobs with pagination. Supports filtering via ?status= query parameter.
    """
    base_query = select(Job)
    if status:
        base_query = base_query.where(Job.status == status)
        
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
        
    paginated_query = base_query.order_by(Job.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(paginated_query)
    jobs = result.scalars().all()
    
    return PaginatedJobListResponse(
        items=[
            JobSummaryResponse(
                job_id=j.id,
                status=j.status.value,
                filename=j.filename,
                row_count_raw=j.row_count_raw,
                created_at=j.created_at.isoformat()
            ) for j in jobs
        ],
        total=total,
        page=page,
        size=size
    )
