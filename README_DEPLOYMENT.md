# MNX EMO Deployment Guide

## 🚀 Proper Deployment

The EMO system has been restructured with proper file placement:

### **File Structure**
```
infra/
├── docker-compose.yml          # Base services
├── docker-compose-emo.yml      # EMO extensions (MOVED HERE)
├── init-extensions.sql         # PostgreSQL extensions
└── postgres-age/               # AGE setup

projectors/
├── translator_memory_to_emo/   # PROPERLY STRUCTURED
│   ├── Dockerfile              # Translator container
│   ├── translator_memory_to_emo.py  # Main translator code
│   └── __init__.py             # Python package
└── sdk/                        # Projector SDK
```

### **Deployment Commands**

#### Option 1: Combined Deployment (Recommended)
```bash
cd infra
docker-compose -f docker-compose.yml -f docker-compose-emo.yml up -d
```

#### Option 2: Base + EMO Separately  
```bash
cd infra
docker-compose up -d                    # Start base services
docker-compose -f docker-compose-emo.yml up -d  # Add EMO services
```

### **Service URLs**
- **Base Gateway**: http://localhost:8081
- **Search Service**: http://localhost:8087/v1/search/hybrid
- **Translator**: http://localhost:8088
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000

### **Database Migrations**
```bash
# Apply EMO migrations to the base nexus database
psql postgresql://postgres:postgres@localhost:5433/nexus -f ../migrations/010_emo_tables.sql
psql postgresql://postgres:postgres@localhost:5433/nexus -f ../migrations/011_emo_graph_schema.sql
```

### **CI Testing**
```bash
# Set environment for tests
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/nexus"
export GATEWAY_URL="http://localhost:8081"

# Run all CI tests
cd scripts
python run_all_ci_tests.py
```

## ✅ **Fixed Issues** 

**The docker-compose-emo.yml file was in the wrong place and had structural issues. Here's what was fixed:**

### **Before (❌ Incorrect)**
- File at root level: `docker-compose-emo.yml`
- Referenced non-existent services: `postgres-v2`, `gateway-v2`, `publisher-v2`
- Used wrong database: `nexus_v2` (should be `nexus`)
- Wrong network: `mnx-v2-emo` (should be `nexus-network`)
- Broken extends references: `docker-compose.yml` (should be in `infra/`)
- Incorrect build paths and port mappings

### **After (✅ Correct)**
1. **File placement**: Moved to `infra/docker-compose-emo.yml`
2. **Service references**: Fixed to use correct base service names (`postgres`, `gateway`, `publisher`)
3. **Database consistency**: All services now use `nexus` database
4. **Network alignment**: All services use `nexus-network`
5. **Build contexts**: Corrected relative paths from `infra/` directory
6. **Translator structure**: Proper directory structure with Dockerfile
7. **Port consistency**: Aligned with base service conventions
8. **Volume references**: Fixed to match base compose file

## 🎯 **Next Steps**

1. Test the deployment with the corrected compose files
2. Run CI validation to ensure everything works
3. Monitor services via Prometheus/Grafana
