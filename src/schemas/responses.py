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

class JobStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    filename: str
    error_message: str | None = None
    summary: dict | None = None
    created_at: str
    updated_at: str

class TransactionResponse(BaseModel):
    id: uuid.UUID
    account_id: str
    amount: float
    date: str | None = None
    description: str
    category: str | None = None
    is_anomaly: bool

class PaginatedTransactionResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    size: int
