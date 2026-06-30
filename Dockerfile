# Use slim image for smaller size
FROM python:3.11-slim

# Prevent python from writing pyc files to disc and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
# gcc and libpq-dev are required for building psycopg2 (used by Celery/Alembic if needed)
RUN apt-get update \
    && apt-get install -y gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create a non-root user and switch to it for security
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# Expose port (can be overridden)
EXPOSE 8000

# Default command (overridden in docker-compose for worker vs web)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
