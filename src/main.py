from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.core.config import settings
from src.core.logging import setup_logging
from src.api.routers import health
import structlog

# Initialize structured logging before anything else
setup_logging(settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events for startup and shutdown logic.
    Why: Safer and more explicit than the old @app.on_event decorators, prevents resource leaks.
    """
    logger.info("startup_event", environment=settings.ENVIRONMENT)
    yield
    logger.info("shutdown_event")

# Initialize FastAPI application
app = FastAPI(
    title="AI Transaction Processing Pipeline",
    description="Asynchronous data ingestion and LLM enrichment API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None, # Disable redoc if unused to save resources
)

# Register routers
app.include_router(health.router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
