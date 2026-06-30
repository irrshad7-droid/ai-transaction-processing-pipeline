import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from src.db.database import get_db
from src.db.models import Job, Transaction
from src.schemas.responses import JobStatusResponse, PaginatedTransactionResponse, TransactionResponse

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["Results"])

@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Fetches the status and LLM summary of a background job.
    """
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        filename=job.filename,
        error_message=job.error_message,
        summary=job.summary,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat()
    )

@router.get("/{job_id}/transactions", response_model=PaginatedTransactionResponse)
async def get_job_transactions(
    job_id: uuid.UUID,
    is_anomaly: bool | None = Query(None, description="Filter by anomaly status"),
    category: str | None = Query(None, description="Filter by transaction category"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=1000, description="Items per page"),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns a paginated, filterable list of processed transactions.
    """
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Build query
    base_query = select(Transaction).where(Transaction.job_id == job_id)
    
    if is_anomaly is not None:
        base_query = base_query.where(Transaction.is_anomaly == is_anomaly)
    if category is not None:
        base_query = base_query.where(Transaction.category == category)
        
    # Count total items matching filters
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Apply pagination and sorting (consistent ordering is critical for pagination)
    paginated_query = base_query.order_by(Transaction.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(paginated_query)
    transactions = result.scalars().all()
    
    items = [
        TransactionResponse(
            id=t.id,
            account_id=t.account_id,
            amount=t.amount,
            date=t.date,
            description=t.description,
            category=t.category,
            is_anomaly=t.is_anomaly
        ) for t in transactions
    ]
    
    return PaginatedTransactionResponse(
        items=items,
        total=total,
        page=page,
        size=size
    )
