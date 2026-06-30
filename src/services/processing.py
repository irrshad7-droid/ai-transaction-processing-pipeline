import uuid
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.db.models import Job, JobStatus

logger = structlog.get_logger(__name__)

class ProcessingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_job(self, job_id_str: str):
        """
        Executes the data cleaning and anomaly detection pipeline for a job.
        Why: Executing this entirely inside the PostgreSQL engine via CTEs 
        prevents loading millions of rows into Python RAM, solving the classic OOM scaling issue.
        """
        job_id = uuid.UUID(job_id_str)
        
        # 1. Update status to PROCESSING
        job = await self.db.get(Job, job_id)
        if not job:
            logger.error("job_not_found", job_id=job_id_str)
            raise ValueError(f"Job {job_id_str} not found")
            
        job.status = JobStatus.PROCESSING
        await self.db.commit()
        logger.info("job_status_updated", job_id=job_id_str, status="PROCESSING")
        
        try:
            # 2. Transaction Cleaning
            # Trims whitespace from descriptions and dates in a single bulk operation
            clean_query = text("""
                UPDATE transactions
                SET description = trim(description),
                    date = trim(date)
                WHERE job_id = :job_id
            """)
            await self.db.execute(clean_query, {"job_id": job_id})
            logger.info("transactions_cleaned", job_id=job_id_str)
            
            # 3. Anomaly Detection (3x Account Median)
            # Uses a CTE to compute the median per account instantly using percentile_cont,
            # then joins back to flag anomalies. This is executed purely in C on the DB server.
            anomaly_query = text("""
                WITH account_medians AS (
                    SELECT 
                        account_id,
                        percentile_disc(0.5) WITHIN GROUP (ORDER BY amount) as median_amount
                    FROM transactions
                    WHERE job_id = :job_id
                    GROUP BY account_id
                )
                UPDATE transactions t
                SET is_anomaly = (t.amount > (3 * am.median_amount))
                FROM account_medians am
                WHERE t.job_id = :job_id 
                  AND t.account_id = am.account_id
                  AND am.median_amount > 0;
            """)
            await self.db.execute(anomaly_query, {"job_id": job_id})
            logger.info("anomaly_detection_completed", job_id=job_id_str)
            
            # 4. Mark job as COMPLETED (For Milestone 4 scope)
            job.status = JobStatus.COMPLETED
            await self.db.commit()
            logger.info("job_status_updated", job_id=job_id_str, status="COMPLETED")
            
        except Exception as e:
            await self.db.rollback()
            # Mark as FAILED on error
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            await self.db.commit()
            logger.error("job_processing_failed", job_id=job_id_str, error=str(e), exc_info=True)
            raise e
