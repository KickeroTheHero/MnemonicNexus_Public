# MoE Controller Production Dockerfile - PR-4
# Single-stage build to avoid package path issues

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies directly
COPY mnx/inference/moe_controller/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY mnx/ mnx/
COPY schemas/ schemas/
COPY services/common/ services/common/

# Set Python path to include project root
ENV PYTHONPATH=/app

# Create non-root user for security
RUN groupadd -r controller && useradd -r -g controller controller
RUN chown -R controller:controller /app
USER controller

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default configuration
ENV CONTROLLER_HOST=0.0.0.0
ENV CONTROLLER_PORT=8000
ENV LOG_LEVEL=INFO
ENV DATABASE_URL=postgresql://postgres:postgres@postgres:5432/nexus

EXPOSE 8000

# Start the controller service
CMD ["uvicorn", "mnx.inference.moe_controller.main:app", "--host", "0.0.0.0", "--port", "8000"]
