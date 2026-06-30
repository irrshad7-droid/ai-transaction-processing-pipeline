# AI Transaction Processing Pipeline

## Overview
A production-ready backend pipeline for processing large CSV transaction datasets asynchronously.

## Features
- FastAPI REST API
- PostgreSQL
- Redis + Celery
- Async processing
- Bulk CSV ingestion
- SQL-based anomaly detection
- LLM-powered categorization
- LLM summarization
- Dockerized deployment
- Alembic migrations

## Architecture

Client
   │
FastAPI
   │
PostgreSQL <── Celery Worker ── Redis
   │
LLM Service

## Tech Stack

- Python 3.11
- FastAPI
- SQLAlchemy Async
- PostgreSQL
- Redis
- Celery
- Docker
- Alembic
- OpenAI-compatible SDK

## Running

docker compose up --build

## API Endpoints

1. **`POST /api/v1/jobs/upload`**: Upload CSV file for asynchronous processing
2. **`GET /api/v1/jobs`**: List paginated jobs (supports `?status=...`)
3. **`GET /api/v1/jobs/{job_id}/status`**: Get job processing status
4. **`GET /api/v1/jobs/{job_id}/results`**: Get final job summary and paginated list of parsed transactions

### Example Usage

```bash
# Upload data
curl -X POST http://localhost:8000/api/v1/jobs/upload \
  -F "file=@sample_data/transactions.csv"

# Check Job Status
curl http://localhost:8000/api/v1/jobs/<JOB_ID>/status

# View Categorized Results (with pagination & anomaly filter)
curl "http://localhost:8000/api/v1/jobs/<JOB_ID>/results?is_anomaly=true&page=1&size=50"
```

## Design Decisions

- PostgreSQL COPY for ingestion
- SQL anomaly detection
- Async workers
- Graceful LLM fallback
- Background processing

## Future Improvements

- Authentication
- S3 storage
- Distributed rate limiting
- Prometheus metrics
