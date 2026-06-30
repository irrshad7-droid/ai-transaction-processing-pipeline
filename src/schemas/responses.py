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
