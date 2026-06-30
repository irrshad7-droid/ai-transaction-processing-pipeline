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
   ↓
FastAPI
   ↓
Create Job
   ↓
Redis Queue
   ↓
Celery Worker
   ↓
Data Cleaning
   ↓
Anomaly Detection
   ↓
LLM Categorization
   ↓
Summary Generation
   ↓
PostgreSQL

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

## API

POST /jobs/upload

GET /jobs/{job_id}

GET /jobs/{job_id}/transactions

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
