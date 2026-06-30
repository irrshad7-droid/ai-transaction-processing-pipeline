import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Index,
    text,
    func,
    Integer
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.db.database import Base

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    filename = Column(String, nullable=False)
    
    row_count_raw = Column(Integer, nullable=True)
    row_count_clean = Column(Integer, nullable=True)
    
    summary = Column(JSONB, nullable=True)
    error_message = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    transactions = relationship("Transaction", back_populates="job", cascade="all, delete-orphan")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    
    txn_id = Column(String, nullable=True)
    date = Column(String, nullable=True)
    merchant = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=True)
    status = Column(String, nullable=True)
    category = Column(String, nullable=True)
    account_id = Column(String, nullable=False)
    notes = Column(String, nullable=True)
    
    is_anomaly = Column(Boolean, default=False, server_default=text("false"), nullable=False)
    anomaly_reason = Column(String, nullable=True)
    
    llm_category = Column(String, nullable=True)
    llm_raw_response = Column(String, nullable=True)
    llm_failed = Column(Boolean, default=False, server_default=text("false"), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    job = relationship("Job", back_populates="transactions")

    # Indexes
    __table_args__ = (
        # Index to quickly find rows that haven't been categorized yet for a specific job
        Index("idx_job_uncategorized", "job_id", postgresql_where=(category.is_(None))),
        # Index on account_id to speed up the 3x median anomaly detection window function
        Index("idx_job_account", "job_id", "account_id"),
    )
