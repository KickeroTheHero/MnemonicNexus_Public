# MNX Security Guide

## Overview

MNX implements multi-layered security including API key authentication, role-based access control, row-level security (RLS), and rate limiting.

## Authentication & Authorization

### API Key Setup

Configure API keys via environment variables:

```bash
# Admin role - full access
MNX_ADMIN_API_KEY=admin-your-secure-random-key-here

# Write role - can POST events  
MNX_WRITE_API_KEY=write-your-secure-random-key-here

# Read role - can GET events and health endpoints
MNX_READ_API_KEY=read-your-secure-random-key-here
```

### Using API Keys

Include API key in requests via header:

```bash
# Option 1: X-API-Key header
curl -H "X-API-Key: your-api-key" http://localhost:8081/v1/events

# Option 2: Authorization Bearer token  
curl -H "Authorization: Bearer your-api-key" http://localhost:8081/v1/events
```

### Role Permissions

| Role   | Permissions |
|--------|-------------|
| `admin` | Full access to all endpoints |
| `write` | POST to `/v1/events/*` |
| `read`  | GET to events and health endpoints |

### Public Endpoints

These endpoints don't require authentication:
- `/health` - Service health checks
- `/metrics` - Prometheus metrics 
- `/` - Service information
- `/docs` - API documentation

## Multi-Tenant Isolation

### Row Level Security (RLS)

All database tables implement RLS policies that enforce `world_id` isolation:

```sql
-- Example: Events are isolated by world_id
CREATE POLICY world_isolation_event_log ON event_core.event_log
    FOR ALL TO PUBLIC  
    USING (world_id = current_setting('app.current_world_id', true)::UUID);
```

### World Context Setting

Services must set world context before database operations:

```sql
-- Set world context for tenant isolation
SELECT set_current_world_id('550e8400-e29b-41d4-a716-446655440001'::UUID);

-- Now all queries are automatically filtered to this world
SELECT * FROM event_core.event_log;  -- Only shows events for this world
```

### Admin Bypass

The `nexus_admin` role can bypass RLS for operational tasks:

```sql
-- Disable RLS for admin operations
SET row_security = off;

-- Re-enable for normal operations  
SET row_security = on;
```

## Rate Limiting

Gateway implements per-client rate limiting:

```bash
# Configuration
RATE_LIMIT_PER_MINUTE=1000

# Rate limit headers in responses
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1609459200
```

When rate limit is exceeded:
- Returns `429 Too Many Requests`
- Includes `Retry-After` header

## Security Headers

Gateway automatically adds security headers:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY  
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

## Input Validation

### Event Envelope Validation

All events are validated against JSON schemas:

```typescript
{
  "world_id": "UUID format required",
  "branch": "string, non-empty",
  "kind": "string, event type identifier",
  "payload": "object, event-specific data",
  "by": {
    "agent": "string, agent identifier"
  }
}
```

### Correlation ID Validation

Correlation IDs must be valid UUIDs:

```bash
curl -H "X-Correlation-Id: 123e4567-e89b-12d3-a456-426614174000" \
     -H "X-API-Key: your-key" \
     http://localhost:8081/v1/events
```

## Testing Security

### RLS Negative Tests

Run RLS isolation tests:

```bash
# Test tenant isolation
python -m pytest tests/integration/test_rls_security.py -v

# Specific RLS tests
python -m pytest tests/integration/test_rls_security.py::TestRLSPolicies::test_world_id_isolation_event_log -v
```

### Authentication Tests

Test API key authentication:

```bash
# Should fail without API key
curl http://localhost:8081/v1/events
# Response: 401 Unauthorized

# Should succeed with valid API key
curl -H "X-API-Key: write-your-key" \
     -X POST http://localhost:8081/v1/events \
     -d '{"world_id":"...", "branch":"main", ...}'
# Response: 201 Created
```

## Security Monitoring

### Failed Authentication Attempts

Monitor failed authentication in logs:

```bash
# View authentication failures
docker logs gateway-container | grep "Invalid API key"
```

### Rate Limit Violations

Monitor rate limiting via metrics:

```bash
# Check rate limit metrics
curl http://localhost:8081/metrics | grep rate_limit
```

## Production Security Checklist

- [ ] Generate strong, random API keys
- [ ] Set up proper key rotation process  
- [ ] Configure appropriate rate limits
- [ ] Enable HTTPS in production
- [ ] Set up monitoring for auth failures
- [ ] Regular security audits of RLS policies
- [ ] Database connection encryption
- [ ] Network security (firewalls, VPC)

## Security Incident Response

1. **Revoke compromised API keys** - Update environment variables
2. **Check audit logs** - Review authentication and access patterns  
3. **Verify RLS integrity** - Run negative tests to ensure isolation
4. **Monitor for unusual patterns** - Check metrics and logs
5. **Update security measures** - Strengthen based on incident learnings

---

For implementation details, see:
- `services/gateway/auth.py` - Authentication implementation
- `migrations/004_rls_policies.sql` - RLS policy definitions
- `tests/integration/test_rls_security.py` - Security test suite
