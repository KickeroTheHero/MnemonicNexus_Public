# MoE Controller Production Dockerfile - PR-4
# 
# Multi-stage build for optimized production image with tool bus integration

FROM python:3.11-slim as builder

WORKDIR /build

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY mnx/inference/moe_controller/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Add local bin to PATH for installed packages
ENV PATH=/root/.local/bin:$PATH

# Copy application source
COPY mnx/ mnx/
COPY schemas/ schemas/

# Copy service-specific files
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
CMD ["python", "-m", "mnx.inference.moe_controller.main"]
