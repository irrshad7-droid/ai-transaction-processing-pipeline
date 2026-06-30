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
            # Assignment requires: Normalise dates, Uppercase status, Fill missing categories, Remove duplicates
            
            # Remove exact duplicate rows first
            dedup_query = text("""
                DELETE FROM transactions 
                WHERE job_id = :job_id AND ctid NOT IN (
                    SELECT min(ctid) 
                    FROM transactions 
                    WHERE job_id = :job_id 
                    GROUP BY txn_id, date, merchant, amount, currency, status, category, account_id, notes
                )
            """)
            await self.db.execute(dedup_query, {"job_id": job_id})
            
            # Update clean count
            count_query = text("SELECT count(*) FROM transactions WHERE job_id = :job_id")
            clean_count_res = await self.db.execute(count_query, {"job_id": job_id})
            job.row_count_clean = clean_count_res.scalar()
            
            # Apply cleaning transformations
            clean_query = text("""
                UPDATE transactions
                SET merchant = trim(merchant),
                    status = upper(trim(status)),
                    category = COALESCE(nullif(trim(category), ''), 'Uncategorised'),
                    date = CASE 
                        WHEN date LIKE '%/%/%' THEN to_char(to_date(date, 'YYYY/MM/DD'), 'YYYY-MM-DD')
                        WHEN date LIKE '%-%-%' THEN to_char(to_date(date, 'DD-MM-YYYY'), 'YYYY-MM-DD')
                        ELSE trim(date) 
                    END
                WHERE job_id = :job_id
            """)
            await self.db.execute(clean_query, {"job_id": job_id})
            logger.info("transactions_cleaned", job_id=job_id_str)
            
            # 3. Anomaly Detection
            # Rule 1: 3x Account Median
            # Rule 2: USD currency for domestic merchants (Swiggy, Ola, IRCTC)
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
                SET is_anomaly = CASE 
                        WHEN t.amount > (3 * am.median_amount) AND am.median_amount > 0 THEN true
                        WHEN upper(trim(t.currency)) = 'USD' AND t.merchant ILIKE ANY(ARRAY['%Swiggy%', '%Ola%', '%IRCTC%']) THEN true
                        ELSE false 
                    END,
                    anomaly_reason = CASE
                        WHEN t.amount > (3 * am.median_amount) AND am.median_amount > 0 THEN 'Amount > 3x Median'
                        WHEN upper(trim(t.currency)) = 'USD' AND t.merchant ILIKE ANY(ARRAY['%Swiggy%', '%Ola%', '%IRCTC%']) THEN 'USD for Domestic Merchant'
                        ELSE NULL
                    END
                FROM account_medians am
                WHERE t.job_id = :job_id 
                  AND t.account_id = am.account_id;
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
                SELECT id, merchant, notes 
                FROM transactions 
                WHERE job_id = :job_id AND category = 'Uncategorised'
            """)
            result = await self.db.execute(uncategorized_query, {"job_id": job_id})
            rows = result.fetchall()
            
            transactions_to_categorize = [{"id": r.id, "merchant": r.merchant, "notes": r.notes} for r in rows]
            
            # Process in batches of 50
            BATCH_SIZE = 50
            for i in range(0, len(transactions_to_categorize), BATCH_SIZE):
                batch = transactions_to_categorize[i:i + BATCH_SIZE]
                llm_response = await llm_service.categorize_transactions(batch)
                categories = llm_response.get("categories", {})
                llm_failed = llm_response.get("llm_failed", False)
                
                # Update database with categorized values or llm_failed status
                for txn in batch:
                    txn_id = txn["id"]
                    category = categories.get(str(txn_id))
                    
                    if llm_failed or not category:
                        # If LLM failed, we mark the row as llm_failed = True but leave category as Uncategorised
                        update_fail_query = text("UPDATE transactions SET llm_failed = true WHERE id = :id")
                        await self.db.execute(update_fail_query, {"id": txn_id})
                    else:
                        update_cat_query = text("UPDATE transactions SET llm_category = :category, category = :category WHERE id = :id")
                        await self.db.execute(update_cat_query, {"category": category, "id": txn_id})
                
                logger.info("llm_batch_processed", job_id=job_id_str, batch_start=i, llm_failed=llm_failed)
                
            # 5. LLM Summarization
            # Gather aggregate statistics: total spend by currency, top 3 merchants, anomaly count
            stats_query = text("""
                SELECT 
                    currency,
                    SUM(amount) as total_amount
                FROM transactions
                WHERE job_id = :job_id
                GROUP BY currency
            """)
            currency_stats_res = await self.db.execute(stats_query, {"job_id": job_id})
            currency_stats = {row.currency: row.total_amount for row in currency_stats_res.fetchall()}
            
            merchant_query = text("""
                SELECT merchant, SUM(amount) as total
                FROM transactions
                WHERE job_id = :job_id
                GROUP BY merchant
                ORDER BY total DESC
                LIMIT 3
            """)
            merchant_res = await self.db.execute(merchant_query, {"job_id": job_id})
            top_merchants = [row.merchant for row in merchant_res.fetchall()]
            
            anomaly_count_query = text("SELECT COUNT(*) FROM transactions WHERE job_id = :job_id AND is_anomaly = true")
            anomaly_res = await self.db.execute(anomaly_count_query, {"job_id": job_id})
            anomaly_count = anomaly_res.scalar()
            
            stats_dict = {
                "total_spend_by_currency": currency_stats,
                "top_3_merchants": top_merchants,
                "anomaly_count": anomaly_count
            }
            
            summary = await llm_service.generate_summary(stats_dict)
            job.summary = summary
            logger.info("llm_summary_generated", job_id=job_id_str)
            
            # Clean up LLM client
            await llm_service.close()
            
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
