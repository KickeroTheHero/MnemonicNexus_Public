FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY projectors/sdk/requirements.txt ./sdk_requirements.txt
RUN pip install --no-cache-dir -r sdk_requirements.txt

# Additional dependencies already covered in SDK requirements

# Copy the projector SDK
COPY projectors/sdk/ ./sdk/

# Copy translator code
COPY projectors/translator_memory_to_emo/ ./translator/

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the translator
CMD ["python", "translator/translator_memory_to_emo.py"]
