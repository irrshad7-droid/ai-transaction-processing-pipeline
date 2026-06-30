# Use slim image for smaller size
FROM python:3.11-slim

# Prevent python from writing pyc files to disc and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for security before copying code
RUN adduser --disabled-password --gecos '' appuser

# Copy source code with correct ownership
COPY --chown=appuser:appuser . .

USER appuser

# Expose port (can be overridden)
EXPOSE 8000

# Default command (overridden in docker-compose for worker vs web)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
