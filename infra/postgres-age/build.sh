#!/bin/bash
set -e

# Build configuration
IMAGE_NAME="nexus/postgres-age"
TAG="pg16"
AGE_VERSION="1.5.0"

echo "🔨 Building PostgreSQL + pgvector + AGE Docker image..."
echo "📋 Configuration:"
echo "   Image: ${IMAGE_NAME}:${TAG}"
echo "   AGE Version: ${AGE_VERSION}"
echo "   Base: pgvector/pgvector:pg16"

# Build the image
docker build \
    --build-arg AGE_VERSION=${AGE_VERSION} \
    --tag ${IMAGE_NAME}:${TAG} \
    --tag ${IMAGE_NAME}:latest \
    .

echo "✅ Build completed successfully"

# Test the image
echo "🧪 Testing the built image..."
docker run --rm ${IMAGE_NAME}:${TAG} postgres --version
docker run --rm ${IMAGE_NAME}:${TAG} psql --version

echo "🎯 Image ready: ${IMAGE_NAME}:${TAG}"
echo "💡 Next steps:"
echo "   1. Update docker-compose.yml to use this image"
echo "   2. Run migrations to test AGE integration"
echo "   3. Validate graph operations work correctly"
