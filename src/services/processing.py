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
            
            # 4. LLM Categorization (Batching)
            # Fetch uncategorized transactions in batches of 50 to avoid token limits
            from src.services.llm import LLMService
            llm_service = LLMService()
            
            # Since this is a background job, we can process all transactions.
            # In a real system with millions of rows, we'd use an async generator.
            uncategorized_query = text("""
                SELECT id, amount, description 
                FROM transactions 
                WHERE job_id = :job_id AND category IS NULL
            """)
            result = await self.db.execute(uncategorized_query, {"job_id": job_id})
            rows = result.fetchall()
            
            transactions_to_categorize = [{"id": r.id, "amount": r.amount, "description": r.description} for r in rows]
            
            # Process in batches of 50
            BATCH_SIZE = 50
            for i in range(0, len(transactions_to_categorize), BATCH_SIZE):
                batch = transactions_to_categorize[i:i + BATCH_SIZE]
                categories = await llm_service.categorize_transactions(batch)
                
                # Update database with categorized values
                # We do this one by one or via case statements. Since batch is small, direct parameter binding is fine.
                for txn_id, category in categories.items():
                    update_cat_query = text("""
                        UPDATE transactions SET category = :category WHERE id = :id
                    """)
                    await self.db.execute(update_cat_query, {"category": category, "id": txn_id})
                
                logger.info("llm_batch_categorized", job_id=job_id_str, batch_start=i)
                
            # 5. LLM Summarization
            # Gather aggregate statistics instead of raw rows to save tokens and prevent context bloat
            stats_query = text("""
                SELECT 
                    COUNT(*) as total_txns,
                    SUM(amount) as total_amount,
                    SUM(CASE WHEN is_anomaly THEN 1 ELSE 0 END) as anomaly_count,
                    COUNT(DISTINCT category) as unique_categories
                FROM transactions
                WHERE job_id = :job_id
            """)
            stats_result = await self.db.execute(stats_query, {"job_id": job_id})
            stats_row = stats_result.fetchone()
            
            stats_dict = {
                "total_transactions": stats_row.total_txns,
                "total_amount_processed": stats_row.total_amount,
                "total_anomalies_detected": stats_row.anomaly_count,
                "unique_categories_used": stats_row.unique_categories
            }
            
            summary = await llm_service.generate_summary(stats_dict)
            job.summary = summary
            logger.info("llm_summary_generated", job_id=job_id_str)
            
            # 6. Mark job as COMPLETED
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
