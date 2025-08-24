# Build PostgreSQL + pgvector + AGE Docker image for Windows
param(
    [string]$ImageName = "nexus/postgres-age",
    [string]$Tag = "pg16",
    [string]$AgeVersion = "PG16/v1.5.0-rc0"
)

Write-Host "🔨 Building PostgreSQL + pgvector + AGE Docker image..." -ForegroundColor Green
Write-Host "📋 Configuration:"
Write-Host "   Image: $ImageName`:$Tag"
Write-Host "   AGE Version: $AgeVersion"
Write-Host "   Base: pgvector/pgvector:pg16"

try {
    # Build the image
    Write-Host "Building image..." -ForegroundColor Yellow
    docker build `
        --build-arg AGE_VERSION=$AgeVersion `
        --tag "$ImageName`:$Tag" `
        --tag "$ImageName`:latest" `
        .

    Write-Host "✅ Build completed successfully" -ForegroundColor Green

    # Test the image
    Write-Host "🧪 Testing the built image..." -ForegroundColor Yellow
    docker run --rm "$ImageName`:$Tag" postgres --version
    docker run --rm "$ImageName`:$Tag" psql --version

    Write-Host "🎯 Image ready: $ImageName`:$Tag" -ForegroundColor Green
    Write-Host "💡 Next steps:"
    Write-Host "   1. Update docker-compose.yml to use this image"
    Write-Host "   2. Run v2-migrate-up to test AGE integration"
    Write-Host "   3. Validate graph operations work correctly"
}
catch {
    Write-Host "❌ Build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
