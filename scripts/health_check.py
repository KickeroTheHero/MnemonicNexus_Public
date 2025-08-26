#!/usr/bin/env python3
"""
Health check script for MNX services
Cross-platform alternative to health_check.sh
Usage: python scripts/health_check.py
"""

import sys
import time
from datetime import datetime
from typing import List, Tuple

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️  requests package not available, using urllib")
    import urllib.request
    import urllib.error

def check_health_requests(service: str, port: int, name: str) -> bool:
    """Check service health using requests library"""
    try:
        url = f"http://localhost:{port}/health"
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def check_health_urllib(service: str, port: int, name: str) -> bool:
    """Check service health using urllib (fallback)"""
    try:
        url = f"http://localhost:{port}/health"
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False

def check_service(service: str, port: int, name: str) -> bool:
    """Check a single service and print result"""
    print(f"Checking {name} (port {port})... ", end="", flush=True)
    
    if REQUESTS_AVAILABLE:
        healthy = check_health_requests(service, port, name)
    else:
        healthy = check_health_urllib(service, port, name)
    
    if healthy:
        print("✅ OK")
        return True
    else:
        print("❌ FAILED")
        return False

def get_service_info_requests(port: int) -> dict:
    """Get service information using requests"""
    try:
        url = f"http://localhost:{port}/"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {}

def get_service_info_urllib(port: int) -> dict:
    """Get service information using urllib"""
    try:
        import json
        url = f"http://localhost:{port}/"
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=3) as response:
            if response.status == 200:
                data = response.read().decode('utf-8')
                return json.loads(data)
    except Exception:
        pass
    return {}

def show_service_info():
    """Show additional service information"""
    print("\n📊 Service Information:")
    print("=" * 50)
    
    services = [
        (8081, "Gateway"),
        (8082, "Publisher"),
        (8083, "Relational Projector"),
        (8084, "Graph Projector"),
        (8085, "Semantic Projector"),
        (8087, "Search Service"),
    ]
    
    for port, name in services:
        if REQUESTS_AVAILABLE:
            info = get_service_info_requests(port)
        else:
            info = get_service_info_urllib(port)
            
        if info:
            service_name = info.get('service', 'Unknown')
            version = info.get('version', 'Unknown')
            status = info.get('status', 'Unknown')
            print(f"  {name}: {service_name} v{version} ({status})")
        else:
            print(f"  {name}: Not responding")

def check_database():
    """Check database connectivity"""
    print("\n🗄️  Database Check:")
    print("=" * 50)
    
    try:
        import os
        database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/nexus')
        
        # Try to import psycopg2 or asyncpg
        try:
            import psycopg2
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result and result[0] == 1:
                print("  ✅ Database connection OK")
                return True
            else:
                print("  ❌ Database query failed")
                return False
                
        except ImportError:
            print("  ⚠️  psycopg2 not available, skipping database check")
            return True
            
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return False

def main():
    """Main health check function"""
    print(f"🔍 MNX Health Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Service definitions: (service_name, port, display_name)
    services = [
        ("gateway", 8081, "Gateway"),
        ("publisher", 8082, "Publisher"),
        ("projector-rel", 8083, "Relational Projector"),
        ("projector-graph", 8084, "Graph Projector"),
        ("projector-sem", 8085, "Semantic Projector"),
    ]
    
    # Additional services that might be running
    optional_services = [
        ("search", 8087, "Search Service"),
        ("prometheus", 9090, "Prometheus"),
    ]
    
    failed_count = 0
    total_count = 0
    
    # Check core services
    print("Core Services:")
    for service, port, name in services:
        total_count += 1
        if not check_service(service, port, name):
            failed_count += 1
    
    # Check optional services
    print("\nOptional Services:")
    for service, port, name in optional_services:
        if not check_service(service, port, name):
            print(f"  ⚠️  {name} not running (optional)")
    
    # Show service information
    show_service_info()
    
    # Check database
    database_ok = check_database()
    
    print("\n" + "=" * 50)
    
    if failed_count == 0:
        print("✅ All core services healthy")
        if database_ok:
            print("✅ Database connection OK")
        print(f"📊 Status: {total_count}/{total_count} services running")
        return 0
    else:
        print(f"❌ {failed_count}/{total_count} core services failed health checks")
        if not database_ok:
            print("❌ Database connection failed")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
