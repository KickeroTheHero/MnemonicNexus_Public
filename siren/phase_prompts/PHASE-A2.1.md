# PHASE A2.1: AGE Extension Docker Build

**Objective**: Build custom PostgreSQL Docker image with Apache AGE extension for graph capabilities

**Prerequisites**: Phase A2 complete ✅ (V2 schema operational, AGE functionality deferred)

---

## 🎯 **Goals**

### **Primary**
- Create custom PostgreSQL 16 + pgvector + AGE Docker image
- Integrate with existing V2 Docker stack  
- Validate AGE compilation and basic functionality
- Establish foundation for Phase A2.2 testing

### **Non-Goals**
- Full AGE integration testing (Phase A2.2 scope)
- Graph projector implementation (Phase A5.1 scope)
- Production optimization (Phase B scope)

---

## 📋 **Deliverables**

### **1. Custom Docker Image** (`infra-v2/postgres-age/`)

#### **Dockerfile**
```dockerfile
FROM pgvector/pgvector:pg16

# Set build arguments
ARG AGE_VERSION=PG16/v1.5.0-rc0
ARG PG_VERSION=16

# Install AGE build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    flex \
    bison \
    libpq-dev \
    postgresql-server-dev-${PG_VERSION} \
    && rm -rf /var/lib/apt/lists/*

# Clone and build Apache AGE
RUN git clone https://github.com/apache/age.git /tmp/age \
    && cd /tmp/age \
    && git checkout ${AGE_VERSION} \
    && make PG_CONFIG=/usr/bin/pg_config install \
    && rm -rf /tmp/age

# Clean up build dependencies
RUN apt-get remove -y \
    build-essential \
    cmake \
    git \
    flex \
    bison \
    && apt-get autoremove -y \
    && apt-get clean

# Copy initialization script
COPY init-age.sql /docker-entrypoint-initdb.d/02-age.sql

# Metadata
LABEL maintainer="MnemonicNexus V2"
LABEL description="PostgreSQL 16 with pgvector and Apache AGE extensions"
LABEL age.version="${AGE_VERSION}"
LABEL postgresql.version="${PG_VERSION}"
```

#### **AGE Initialization Script** (`init-age.sql`)
```sql
-- Initialize Apache AGE extension for MnemonicNexus V2
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Test AGE installation
SELECT ag_catalog.create_graph('test_age_installation');
SELECT ag_catalog.cypher('test_age_installation', $$
    CREATE (n:TestNode {name: 'installation_test'}) RETURN n
$$) AS (result agtype);
SELECT ag_catalog.drop_graph('test_age_installation', true);

RAISE NOTICE 'AGE extension installed and validated successfully';
```

### **2. Build Scripts**

#### **PowerShell Build Script** (`build.ps1`)
```powershell
param(
    [string]$ImageName = "nexus/postgres-age",
    [string]$Tag = "pg16"
)

Write-Host "🔨 Building PostgreSQL + pgvector + AGE Docker image..."
docker build --tag "$ImageName:$Tag" .

Write-Host "🧪 Testing the built image..."
docker run --rm "$ImageName:$Tag" postgres --version
```

### **3. Docker Compose Integration**

Update `infra-v2/docker-compose.yml`:
```yaml
services:
  postgres-v2:
    build:
      context: ./postgres-age
    container_name: nexus-postgres-v2
    environment:
      POSTGRES_DB: nexus_v2
      POSTGRES_USER: postgres  
      POSTGRES_PASSWORD: postgres
    ports:
      - "5433:5432"
    volumes:
      - postgres_v2_data:/var/lib/postgresql/data
      - ./init-extensions.sql:/docker-entrypoint-initdb.d/01-extensions.sql
      - ../migrations:/migrations
```

---

## ✅ **Acceptance Criteria**

### **Build Success**
- [ ] Docker image builds without errors
- [ ] AGE extension compiles successfully from source
- [ ] Image size reasonable (< 2GB)
- [ ] All dependencies properly installed

### **Functionality Validation**
- [ ] PostgreSQL 16 starts correctly
- [ ] pgvector extension loads successfully  
- [ ] AGE extension loads and basic graph operations work
- [ ] V2 migrations run without issues

### **Integration**
- [ ] V2 Docker stack starts with custom image
- [ ] No conflicts with existing infrastructure
- [ ] Health checks pass for all services
- [ ] Database connectivity confirmed

---

## 🚧 **Implementation Steps**

### **Step 1: Create Build Infrastructure**
1. Create `infra-v2/postgres-age/` directory
2. Write Dockerfile with AGE compilation
3. Create AGE initialization script
4. Add build scripts for cross-platform support

### **Step 2: Build and Test Image**
1. Build custom Docker image locally
2. Test PostgreSQL and extension functionality
3. Validate AGE basic operations
4. Confirm image stability

### **Step 3: Integration**
1. Update docker-compose.yml to use custom image
2. Test V2 stack startup with new image
3. Run V2 migrations against AGE-enabled database
4. Validate health checks and connectivity

### **Step 4: Validation**
1. Confirm all V2 functionality still works
2. Test basic AGE graph operations
3. Document any limitations or known issues
4. Prepare for Phase A2.2 testing

---

## 🔧 **Technical Decisions**

### **AGE Version**
- **Version**: PG16/v1.5.0-rc0 (latest stable for PostgreSQL 16)
- **Source**: Compile from GitHub source for latest features
- **Fallback**: Pre-built packages if compilation issues

### **Base Image**
- **Base**: pgvector/pgvector:pg16 (adds pgvector to PostgreSQL 16)
- **Benefits**: Combines vector search with graph capabilities
- **Size**: Optimized multi-stage build to minimize final image

### **Build Strategy**
- **Approach**: Multi-stage Docker build for clean final image
- **Dependencies**: Install only runtime dependencies in final stage
- **Caching**: Leverage Docker layer caching for faster rebuilds

---

## 🚨 **Risks & Mitigations**

### **Compilation Failures**
- **Risk**: AGE compilation fails on different architectures
- **Mitigation**: Test on multiple platforms, provide pre-built fallback
- **Escalation**: Use official AGE Docker image if available

### **Version Compatibility**
- **Risk**: AGE version incompatible with PostgreSQL 16 or pgvector
- **Mitigation**: Use tested version combinations, pin dependencies
- **Fallback**: Downgrade to known working versions

### **Performance Impact**
- **Risk**: Custom image slower than official PostgreSQL
- **Mitigation**: Benchmark against baseline, optimize build
- **Monitoring**: Track startup time and query performance

---

## 📊 **Success Metrics**

- **Build Time**: < 10 minutes on modern hardware
- **Image Size**: < 2GB final image size
- **Startup Time**: < 30 seconds for database ready
- **Functionality**: 100% of V2 migrations successful
- **Stability**: No crashes during basic operation testing

---

## 🔄 **Next Phase**

**Phase A2.2: AGE Integration Testing & Validation**
- Comprehensive AGE functionality testing
- Performance benchmarks vs relational queries
- Operational procedures and monitoring
- Production readiness validation

**Dependencies**: A2.1 success enables A2.2 comprehensive testing and A5.1 graph projector implementation
