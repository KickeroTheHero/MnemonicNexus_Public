#!/bin/bash
# Health check script for MNX services
# Usage: bash scripts/health_check.sh

set -e

echo "🔍 MNX Health Check - $(date)"
echo "=================================="

# Function to check service health
check_health() {
    local service=$1
    local port=$2
    local name=$3
    
    echo -n "Checking $name (port $port)... "
    
    if curl -fsS "http://localhost:$port/health" > /dev/null 2>&1; then
        echo "✅ OK"
        return 0
    else
        echo "❌ FAILED"
        return 1
    fi
}

# Check all services
FAILED=0

check_health "gateway" "8081" "Gateway" || FAILED=1
check_health "publisher" "8082" "Publisher" || FAILED=1
check_health "projector-rel" "8083" "Relational Projector" || FAILED=1
check_health "projector-graph" "8084" "Graph Projector" || FAILED=1
check_health "projector-sem" "8085" "Semantic Projector" || FAILED=1

echo "=================================="

if [ $FAILED -eq 0 ]; then
    echo "✅ All services healthy"
    exit 0
else
    echo "❌ Some services failed health checks"
    exit 1
fi
