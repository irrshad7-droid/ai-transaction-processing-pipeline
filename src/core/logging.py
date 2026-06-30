import logging
import structlog
import sys

def setup_logging(log_level: str = "INFO") -> None:
    """
    Configures structured JSON logging for production.
    Why: Standard text logging is hard to parse in centralized logging systems (ELK/Datadog).
    Structlog enforces a strict JSON schema for every log line, making tracing trivial.
    """
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Force Uvicorn and FastAPI loggers to propagate up to our root JSON logger
    # Why: Without this, Uvicorn outputs plain text access logs, breaking ELK/Datadog parsing.
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"]:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers.clear()
        logging_logger.propagate = True
