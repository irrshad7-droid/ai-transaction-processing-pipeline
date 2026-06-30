from celery import Celery
from src.core.config import settings

# Initialize Celery using Redis as both broker and result backend.
# Why: Decouples background processing from the web event loop.
celery_app = Celery(
    "transaction_pipeline",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.workers.tasks"]  # Task registry
)

# Configuration overrides for production readiness
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Acks late ensures tasks are not lost if the worker crashes mid-execution.
    task_acks_late=True,
    worker_prefetch_multiplier=1, # Ensures fair distribution among workers
    broker_connection_retry_on_startup=True, # Required for Celery 5.3+
)
