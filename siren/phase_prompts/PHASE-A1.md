# PHASE A1: Fresh V2 Infrastructure Setup

**Objective**: Establish isolated V2 stack with PostgreSQL + AGE + pgvector extensions

**Prerequisites**: Phase A0 complete (V1 archived, V2 documentation foundation established)

---

## 🎯 **Goals**

### **Primary**
- Create clean V2 infrastructure isolated from archived V1
- Enable AGE + pgvector development with proper extensions
- Establish V2 development workflow foundation

### **Non-Goals**
- Any V1 compatibility or migration (Phase C scope)
- Full projector implementation (Phase A4 scope)
- Production deployment configuration

---

## 📋 **Deliverables**

### **1. V2 Docker Compose Stack** (`infra-v2/`)
```yaml
# infra-v2/docker-compose.yml
services:
  postgres-v2:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: nexus_v2
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5433:5432"  # Avoid V1 conflict
    volumes:
      - postgres_v2_data:/var/lib/postgresql/data
      - ./init-extensions.sql:/docker-entrypoint-initdb.d/01-extensions.sql
      
  gateway-v2:
    build: ../services/gateway-v2
    ports:
      - "8081:8000"  # Avoid V1 conflict
    depends_on:
      - postgres-v2
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres-v2:5432/nexus_v2
      GRAPH_ADAPTER: age
```

### **2. Database Extensions Setup**
```sql
-- infra-v2/init-extensions.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "age";
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
```

### **3. Makefile V2 Targets**
```makefile
# V2 development targets
v2-up:
	cd infra-v2 && docker compose up -d
	
v2-down:
	cd infra-v2 && docker compose down
	
v2-logs:
	cd infra-v2 && docker compose logs -f
	
v2-migrate:
	cd infra-v2 && docker compose exec postgres-v2 psql -U postgres -d nexus_v2 -f /migrations/v2_schema.sql
	
v2-health:
	@curl -f http://localhost:8081/health || echo "Gateway V2 not ready"
	@cd infra-v2 && docker compose exec postgres-v2 psql -U postgres -d nexus_v2 -c "SELECT version();" | grep -q "PostgreSQL 16" && echo "✅ PostgreSQL 16 ready"
	@cd infra-v2 && docker compose exec postgres-v2 psql -U postgres -d nexus_v2 -c "SELECT * FROM pg_extension WHERE extname IN ('vector', 'age');" | grep -q "vector\|age" && echo "✅ Extensions loaded"
```

---

## ✅ **Acceptance Criteria**

### **Infrastructure**
- [ ] `make v2-up` starts isolated V2 stack without V1 conflicts
- [ ] PostgreSQL 16+ accessible on port 5433
- [ ] Gateway V2 accessible on port 8081
- [ ] `make v2-health` passes all checks

### **Extensions**
- [ ] `vector` extension loaded and functional
- [ ] AGE extension installation **deferred to Phase A2** (requires custom Docker image)
- [ ] Basic vector operations work: `SELECT '[1,2,3]'::vector(3);`
- [ ] Gateway health check acknowledges AGE as "not_available" with proper deferral note

### **Development Workflow**
- [ ] `make v2-logs` shows clean startup without errors
- [ ] `make v2-down` cleanly shuts down services
- [ ] No interference with archived V1 services

---

## 🚧 **Implementation Steps**

### **Step 1: Infrastructure Setup**
1. Create `infra-v2/` directory structure
2. Write `docker-compose.yml` with isolated ports/volumes
3. Create extension initialization script
4. Add V2 Makefile targets

### **Step 2: Service Stubs**
1. Create minimal `services/gateway-v2/` with health endpoint
2. Basic Dockerfile for gateway service
3. Environment configuration for V2 stack

### **Step 3: Validation**
1. Test extension loading with manual queries
2. Verify port isolation from V1
3. Document any extension-specific configuration needs

---

## 🔧 **Technical Decisions**

### **Port Mappings**
- **PostgreSQL**: 5433 (avoid V1 5432)
- **Gateway**: 8081 (avoid V1 8080)
- **Future services**: 8082+

### **Volume Strategy**
- Separate `postgres_v2_data` volume
- No shared volumes with V1
- Clear naming for operational clarity

### **Extension Loading**
- Load extensions at container startup via initdb
- Set AGE search_path for development convenience
- Version pinning for reproducibility

---

## 🚨 **Risks & Mitigations**

### **Extension Compatibility**
- **Risk**: AGE version compatibility with PostgreSQL 16
- **Mitigation**: Pin specific versions, test basic operations

### **Resource Conflicts**
- **Risk**: V1/V2 services competing for resources
- **Mitigation**: Isolated ports, separate Docker networks

### **Development Complexity**
- **Risk**: Managing two stacks during transition
- **Mitigation**: Clear naming, separate Makefile targets

---

## 📊 **Success Metrics**

- **Setup Time**: < 5 minutes for `make v2-up` on clean system
- **Resource Usage**: < 2GB RAM for basic V2 stack
- **Extension Test**: All extension smoke tests pass
- **Documentation**: Clear setup instructions for new developers

---

## 🔄 **Next Phase**

**Phase A2**: V2 Schema & Event Envelope
- Implement V2 database schema with tenancy
- Canonical event envelope with `world_id`
- Event uniqueness constraints
