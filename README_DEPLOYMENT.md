# MNX Deployment Guide

## 🚀 Quick Start

### Start Services

```bash
# Start all services
make up

# Or manually with docker-compose
cd infra
docker-compose up -d
```

### Service URLs

- **Gateway**: http://localhost:8081
- **Publisher**: http://localhost:8082
- **Relational Projector**: http://localhost:8083
- **Graph Projector**: http://localhost:8084
- **Semantic Projector**: http://localhost:8085
- **Search Service**: http://localhost:8087
- **Translator**: http://localhost:8088
- **Prometheus**: http://localhost:9090
- **Database**: localhost:5433

### Database Setup

PostgreSQL with AGE extension is automatically configured via:
- `infra/init-extensions.sql` - Extension setup
- `infra/postgres-age/` - AGE-specific configuration

### Health Checks

```bash
# Check all services
make health

# Or manually check individual services
curl http://localhost:8081/health  # Gateway
curl http://localhost:8082/health  # Publisher  
curl http://localhost:8087/health  # Search
```

## 📊 Monitoring & Metrics

### Prometheus Metrics

```bash
# View all metrics
curl http://localhost:8081/metrics  # Gateway metrics
curl http://localhost:8082/metrics  # Publisher metrics

# Check projector lag
curl http://localhost:9090 | grep projector_lag_ms
```

### Health Monitoring

All services expose `/health` endpoints returning:
```json
{
  "status": "ok|degraded|down",
  "time": "2024-01-15T10:30:00Z",
  "version": "0.1.0"
}
```

## 🗄️ Database Operations

### Apply Migrations

```bash
# Apply all migrations
cd migrations
for file in *.sql; do
  psql postgresql://postgres:postgres@localhost:5433/nexus -f "$file"
done
```

### Backup Commands

```bash
# Backup event log
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --table=events --data-only > events_backup.sql

# Backup lens tables  
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --schema=relational_lens > relational_backup.sql
```

## 🧪 Testing Deployment

### Run Full Test Suite

```bash
# Set environment for tests
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/nexus"
export GATEWAY_URL="http://localhost:8081"

# Run all tests
make test

# Run integration tests specifically
make test-integration
```

### Baseline Verification

```bash
# Generate and verify baseline
make baseline

# Check baseline artifacts
ls artifacts/baseline.sha
```

### Sample Data & Idempotency Testing

```bash
# 1. Test successful event creation (should return 201 Created)
curl -X POST http://localhost:8081/v1/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: write-your-secure-key" \
  -H "X-Correlation-Id: $(uuidgen)" \
  -H "Idempotency-Key: unique-test-$(date +%s)" \
  -d @tests/golden/envelopes/sample.json

# Expected response: 201 Created with event_id, global_seq, received_at

# 2. Test idempotency: Resubmit with same idempotency key (should return 409 Conflict)
IDEM_KEY="test-duplicate-$(date +%s)"

curl -X POST http://localhost:8081/v1/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: write-your-secure-key" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -d @tests/golden/envelopes/sample.json

curl -X POST http://localhost:8081/v1/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: write-your-secure-key" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -d @tests/golden/envelopes/sample.json

# First call: 201 Created, Second call: 409 Conflict

# 3. Test without API key (should return 401 Unauthorized)
curl -X POST http://localhost:8081/v1/events \
  -H "Content-Type: application/json" \
  -d @tests/golden/envelopes/sample.json

# Expected response: 401 Unauthorized
```

## 🔧 Configuration

### Environment Variables

Key configuration via environment variables:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/nexus

# Services
GATEWAY_PORT=8081
PUBLISHER_PORT=8082
SEARCH_PORT=8087

# Observability
PROMETHEUS_PORT=9090
LOG_LEVEL=INFO
```

### Docker Compose Override

Create `infra/docker-compose.override.yml` for local customization:

```yaml
version: '3.8'
services:
  gateway:
    environment:
      - LOG_LEVEL=DEBUG
  publisher:
    environment:
      - LOG_LEVEL=DEBUG
```

## 🚨 Troubleshooting

### Common Issues

1. **Port conflicts**: Check if ports 8081, 8082, 8087, 5433, 9090 are available
2. **Database connection**: Ensure PostgreSQL container is healthy
3. **Health checks failing**: Check service logs with `docker-compose logs [service]`

### Reset Environment

```bash
# Clean shutdown and reset
make down
make clean
docker system prune -f
make up
```

### Logs and Debugging

```bash
# View all service logs
docker-compose -f infra/docker-compose.yml logs -f

# View specific service logs  
docker-compose -f infra/docker-compose.yml logs gateway
docker-compose -f infra/docker-compose.yml logs publisher
```

---

For architecture details and development workflow, see [README.md](README.md).