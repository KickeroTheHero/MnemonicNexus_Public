FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Create non-root user
RUN useradd -r -u 10001 appuser && chown -R appuser:appuser /app

# Install system dependencies with security updates
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY projectors/graph/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy SDK package and graph projector code
COPY --chown=appuser:appuser projectors/sdk ./sdk
COPY --chown=appuser:appuser projectors/graph/ .
# Also include shared services/common for adapters/tenancy
COPY --chown=appuser:appuser services/common ./services/common

USER appuser

# Health check via FastAPI endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Run projector
CMD ["python", "main.py"]
