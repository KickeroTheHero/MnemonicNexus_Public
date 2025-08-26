# MNX Backup and Recovery Guide

## Overview

This guide covers backup strategies for MNX components including event logs, projector states, and configuration data.

## Database Backup

### Event Log Backup

The event log is the source of truth - backing it up ensures full system recovery:

```bash
# Create compressed backup of event log
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --table=event_core.event_log \
  --data-only \
  --compress=9 \
  > "mnx-eventlog-$(date +%Y%m%d-%H%M%S).sql.gz"

# Include outbox for consistency
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --table=event_core.outbox \
  --data-only \
  --compress=9 \
  > "mnx-outbox-$(date +%Y%m%d-%H%M%S).sql.gz"
```

### Full Database Backup

```bash
# Complete database backup with all schemas
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --format=custom \
  --compress=9 \
  --file="mnx-full-$(date +%Y%m%d-%H%M%S).dump"

# Or plain SQL format for portability
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --format=plain \
  --compress=9 \
  > "mnx-full-$(date +%Y%m%d-%H%M%S).sql.gz"
```

### Schema-Only Backup

```bash
# Backup database schema without data
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --schema-only \
  --file="mnx-schema-$(date +%Y%m%d-%H%M%S).sql"
```

## Projector State Snapshots

### Lens-Specific Backups

```bash
# Relational lens backup
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --schema=lens_rel \
  --data-only \
  --compress=9 \
  > "mnx-lens-rel-$(date +%Y%m%d-%H%M%S).sql.gz"

# Semantic lens backup (embeddings)
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --schema=lens_sem \
  --data-only \
  --compress=9 \
  > "mnx-lens-sem-$(date +%Y%m%d-%H%M%S).sql.gz"

# Graph lens backup  
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --schema=lens_graph \
  --data-only \
  --compress=9 \
  > "mnx-lens-graph-$(date +%Y%m%d-%H%M%S).sql.gz"

# EMO lens backup
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --schema=lens_emo \
  --data-only \
  --compress=9 \
  > "mnx-lens-emo-$(date +%Y%m%d-%H%M%S).sql.gz"
```

### Watermark State

```bash
# Backup projector watermarks for resumption
pg_dump postgresql://postgres:postgres@localhost:5433/nexus \
  --table=event_core.projector_watermarks \
  --data-only \
  > "mnx-watermarks-$(date +%Y%m%d-%H%M%S).sql"
```

## Configuration Backup

### Environment Configuration

```bash
# Backup environment files (excluding secrets)
cp env.example backup/env.example.$(date +%Y%m%d)
cp env.production backup/env.production.$(date +%Y%m%d)

# Backup docker compose configurations
cp infra/docker-compose*.yml backup/
```

### Application Schemas

```bash
# Backup JSON schemas and OpenAPI specs
tar -czf "mnx-schemas-$(date +%Y%m%d).tar.gz" schemas/
```

## Automated Backup Script

Create `scripts/backup.sh`:

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5433/nexus}"

echo "🔄 Starting MNX backup at $TIMESTAMP"

# Create backup directory
mkdir -p "$BACKUP_DIR/$TIMESTAMP"
cd "$BACKUP_DIR/$TIMESTAMP"

# Event log (critical)
echo "📊 Backing up event log..."
pg_dump "$DATABASE_URL" \
  --table=event_core.event_log \
  --table=event_core.outbox \
  --data-only \
  --compress=9 \
  > "eventlog.sql.gz"

# Full database backup
echo "🗄️ Creating full database backup..."
pg_dump "$DATABASE_URL" \
  --format=custom \
  --compress=9 \
  --file="database.dump"

# Projector states
echo "📋 Backing up projector states..."
for schema in lens_rel lens_sem lens_graph lens_emo; do
  pg_dump "$DATABASE_URL" \
    --schema="$schema" \
    --data-only \
    --compress=9 \
    > "${schema}.sql.gz" || echo "Warning: $schema backup failed"
done

# Watermarks
pg_dump "$DATABASE_URL" \
  --table=event_core.projector_watermarks \
  --data-only \
  > "watermarks.sql"

# Configuration
cp -r ../../schemas ./
cp -r ../../infra ./

echo "✅ Backup completed: $BACKUP_DIR/$TIMESTAMP"
echo "📁 Backup size: $(du -sh . | cut -f1)"
```

## Recovery Procedures

### Full System Recovery

```bash
# 1. Restore database schema
psql "$DATABASE_URL" -f mnx-schema-YYYYMMDD.sql

# 2. Restore event log (critical for replay)
gunzip -c mnx-eventlog-YYYYMMDD.sql.gz | psql "$DATABASE_URL"

# 3. Restart services to trigger projection rebuild
docker-compose restart

# 4. Verify replay determinism
make baseline
```

### Projector Recovery

```bash
# Option 1: Restore from backup
gunzip -c mnx-lens-rel-YYYYMMDD.sql.gz | psql "$DATABASE_URL"

# Option 2: Rebuild from event log (slower but guaranteed consistent)
# Via admin API:
curl -X POST http://localhost:8081/v1/admin/projectors/rel/rebuild \
  -H "Content-Type: application/json" \
  -d '{"world_id": "all", "from_global_seq": 0}'
```

### Point-in-Time Recovery

```bash
# Restore to specific global sequence number
pg_dump "$DATABASE_URL" \
  --table=event_core.event_log \
  --where="global_seq <= 12345" \
  --data-only \
  > "eventlog-pit-12345.sql"

# Restore and replay
psql "$DATABASE_URL" -c "TRUNCATE event_core.event_log CASCADE"
psql "$DATABASE_URL" -f "eventlog-pit-12345.sql"
```

## Backup Validation

### Verify Backup Integrity

```bash
# Test backup file integrity
gunzip -t backup.sql.gz && echo "✅ Backup file is valid"

# Validate backup contents
psql "$TEST_DATABASE_URL" -f backup.sql
```

### Restore Testing

```bash
# Create test database for restore validation
createdb mnx_restore_test
psql mnx_restore_test -f mnx-schema-latest.sql
gunzip -c mnx-eventlog-latest.sql.gz | psql mnx_restore_test

# Verify row counts match
echo "Event count: $(psql mnx_restore_test -t -c 'SELECT COUNT(*) FROM event_core.event_log')"
```

## Backup Schedule Recommendations

### Production

- **Event Log**: Continuous WAL archiving + daily full backup
- **Full Database**: Daily during maintenance window  
- **Configuration**: On every deployment
- **Retention**: 30 days for daily, 12 months for weekly

### Development

- **Event Log**: Daily backup
- **Full Database**: Weekly backup
- **Retention**: 7 days

## Security Considerations

- Encrypt backups at rest and in transit
- Use separate credentials for backup operations
- Store backups in different geographic locations
- Regularly test restore procedures
- Audit backup access logs

## Monitoring Backup Health

```bash
# Check backup file ages
find backups/ -name "*.sql.gz" -mtime +1 -ls

# Verify backup sizes are reasonable
ls -lah backups/latest/

# Test restore on schedule
# (Include in monitoring/alerting)
```

---

For operational procedures, see:
- [Deployment Guide](README_DEPLOYMENT.md) - Service management
- [Security Guide](SECURITY.md) - Access controls
- [Observability Guide](observability.md) - Monitoring setup
