FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY projectors/semantic/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY projectors/ ./projectors/
COPY services/common/ ./services/common/

# Health check via FastAPI endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set working directory to semantic projector
WORKDIR /app/projectors/semantic

# Run semantic projector
CMD ["python", "main.py"]
