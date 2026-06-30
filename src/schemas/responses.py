import uuid
from pydantic import BaseModel, ConfigDict

class JobCreatedResponse(BaseModel):
    """
    Response schema for POST /jobs/upload.
    Why: Strict schema serialization for OpenAPI documentation and client guarantees.
    """
    job_id: uuid.UUID
    status: str

    model_config = ConfigDict(from_attributes=True)

class JobSummaryResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    filename: str
    row_count_raw: int | None = None
    created_at: str

class JobListResponse(BaseModel):
    items: list[JobSummaryResponse]

class JobStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    summary: dict | None = None

class TransactionResponse(BaseModel):
    id: uuid.UUID
    txn_id: str | None = None
    date: str | None = None
    merchant: str | None = None
    amount: float
    currency: str | None = None
    status: str | None = None
    category: str | None = None
    account_id: str
    notes: str | None = None
    is_anomaly: bool
    anomaly_reason: str | None = None
    llm_category: str | None = None
    llm_raw_response: str | None = None
    llm_failed: bool

class PaginatedTransactionResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    size: int

class JobResultResponse(BaseModel):
    job: JobStatusResponse
    summary: dict | None = None
    transactions: PaginatedTransactionResponse
