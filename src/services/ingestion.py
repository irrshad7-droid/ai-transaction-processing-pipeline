import csv
import codecs
import uuid
import structlog
from fastapi import UploadFile, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_db
from src.db.models import Job, JobStatus
from starlette.concurrency import run_in_threadpool

logger = structlog.get_logger(__name__)

class IngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_upload(self, file: UploadFile) -> Job:
        """
        Validates the CSV and stages the data in Postgres using bulk COPY.
        Uses chunking to avoid loading the entire file into RAM (OOM protection).
        """
        logger.info("processing_upload", filename=file.filename)
        
        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")
            
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a .csv")

        # 1. Create Job in Database
        job = Job(filename=file.filename, status=JobStatus.PENDING)
        self.db.add(job)
        await self.db.flush() # Flush to generate the UUID
        
        # 2. Extract underlying asyncpg connection for fast COPY
        raw_conn = await self.db.connection()
        dbapi_conn = await raw_conn.get_raw_connection()
        asyncpg_conn = dbapi_conn.driver_connection
        
        # 3. Parse CSV and bulk insert in chunks
        # UploadFile.file is a SpooledTemporaryFile, which avoids RAM bloat for large files
        try:
            file.file.seek(0)
            reader = csv.DictReader(codecs.iterdecode(file.file, 'utf-8'))
            
            if not reader.fieldnames:
                raise ValueError("CSV is empty or missing headers")

            required_columns = {"account_id", "amount", "date", "description"}
            if not required_columns.issubset(set(reader.fieldnames)):
                missing = required_columns - set(reader.fieldnames)
                raise ValueError(f"CSV missing required columns: {missing}")

            # Define a generator expression so we don't load all rows into memory
            def record_generator():
                for row in reader:
                    try:
                        amt = float(row["amount"])
                    except (ValueError, TypeError):
                        amt = 0.0 # Standardize bad data, worker can flag this later
                    yield (
                        job.id,
                        row["account_id"],
                        amt,
                        row.get("date", ""),
                        row["description"]
                    )
            
            # asyncpg copy_records_to_table accepts a synchronous iterator.
            # It reads chunks and streams them to the DB socket asynchronously.
            await asyncpg_conn.copy_records_to_table(
                "transactions",
                columns=["job_id", "account_id", "amount", "date", "description"],
                records=record_generator()
            )
            
            await self.db.commit()
            logger.info("upload_successful", job_id=str(job.id))
            return job
        except ValueError as ve:
            await self.db.rollback()
            logger.error("csv_validation_failed", error=str(ve))
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
        except Exception as e:
            await self.db.rollback()
            logger.error("bulk_insert_failed", error=str(e), exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process CSV data")

def get_ingestion_service(db: AsyncSession = Depends(get_db)) -> IngestionService:
    """Dependency injection factory for IngestionService"""
    return IngestionService(db)
