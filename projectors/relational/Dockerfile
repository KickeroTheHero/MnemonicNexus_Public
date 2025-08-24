FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install curl for health checks and create non-root user
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 10001 appuser && chown -R appuser:appuser /app

# Install dependencies (paths relative to repo root build context)
COPY projectors/relational/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy SDK package and relational projector code (as non-root)
COPY --chown=appuser:appuser projectors/sdk ./sdk
COPY --chown=appuser:appuser projectors/relational/ .
# Include shared common services for DB access/tenancy
COPY --chown=appuser:appuser services/common ./services/common

USER appuser

# Health check via FastAPI endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Run projector
CMD ["python", "main.py"]
