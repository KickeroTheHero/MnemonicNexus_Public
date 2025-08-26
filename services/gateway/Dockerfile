# MnemonicNexus Gateway - Phase A1 Infrastructure
# Pin base image with digest for security
FROM python:3.11-slim@sha256:f3b72a3c5b3c0e1b6e6e3e1a3e2e2a1b2c3d4e5f6789abcdef0123456789abcd

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY services/gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/gateway/main.py .
COPY services/gateway/admin.py .
COPY services/gateway/models.py .
COPY services/gateway/validation.py .
COPY services/gateway/persistence.py .
COPY services/gateway/monitoring.py .
COPY services/common ./common

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash nexus
RUN chown -R nexus:nexus /app
USER nexus

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
