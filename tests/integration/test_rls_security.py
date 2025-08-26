"""
Integration tests for Row Level Security (RLS) and tenancy isolation
Tests require database to be running - marked with @pytest.mark.integration
"""

import asyncio
import os
import pytest
import uuid
from typing import Dict, Any

# Import asyncpg for direct database testing
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    pytest.skip("asyncpg not available for RLS tests", allow_module_level=True)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/nexus")

@pytest.mark.integration
class TestRLSPolicies:
    """Test Row Level Security policy enforcement"""
    
    @pytest.fixture
    async def db_connection(self):
        """Create database connection for testing"""
        if not ASYNCPG_AVAILABLE:
            pytest.skip("asyncpg not available")
        
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            yield conn
            await conn.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")
    
    async def test_world_id_isolation_event_log(self, db_connection):
        """Test that events from different worlds are isolated"""
        conn = db_connection
        
        # Create test data for two different worlds
        world_id_1 = str(uuid.uuid4())
        world_id_2 = str(uuid.uuid4())
        
        try:
            # Insert test events for both worlds (as admin to bypass RLS initially)
            await conn.execute("SET row_security = off")
            
            event_id_1 = str(uuid.uuid4())
            event_id_2 = str(uuid.uuid4())
            
            await conn.execute("""
                INSERT INTO event_core.event_log (world_id, branch, event_id, kind, envelope, occurred_at)
                VALUES ($1, 'main', $2, 'test.rls.world1', '{"test": "data1"}', NOW()),
                       ($3, 'main', $4, 'test.rls.world2', '{"test": "data2"}', NOW())
            """, uuid.UUID(world_id_1), uuid.UUID(event_id_1), 
                 uuid.UUID(world_id_2), uuid.UUID(event_id_2))
            
            # Re-enable RLS
            await conn.execute("SET row_security = on")
            
            # Test isolation: Set world_id_1 context
            await conn.execute("SELECT set_current_world_id($1)", uuid.UUID(world_id_1))
            
            # Should only see events from world_id_1
            result_1 = await conn.fetch("""
                SELECT event_id, world_id::text FROM event_core.event_log 
                WHERE kind LIKE 'test.rls.%'
            """)
            
            assert len(result_1) == 1
            assert result_1[0]['world_id'] == world_id_1
            assert result_1[0]['event_id'] == uuid.UUID(event_id_1)
            
            # Test isolation: Set world_id_2 context  
            await conn.execute("SELECT set_current_world_id($1)", uuid.UUID(world_id_2))
            
            # Should only see events from world_id_2
            result_2 = await conn.fetch("""
                SELECT event_id, world_id::text FROM event_core.event_log 
                WHERE kind LIKE 'test.rls.%'
            """)
            
            assert len(result_2) == 1
            assert result_2[0]['world_id'] == world_id_2
            assert result_2[0]['event_id'] == uuid.UUID(event_id_2)
            
            # Test negative case: No world_id context should see nothing
            await conn.execute("SELECT set_current_world_id(NULL)")
            
            result_none = await conn.fetch("""
                SELECT event_id FROM event_core.event_log 
                WHERE kind LIKE 'test.rls.%'
            """)
            
            # Should see no events without proper world context
            assert len(result_none) == 0
            
        finally:
            # Cleanup
            await conn.execute("SET row_security = off")
            await conn.execute("""
                DELETE FROM event_core.event_log 
                WHERE kind LIKE 'test.rls.%'
            """)
    
    async def test_cross_world_access_denied(self, db_connection):
        """Test that attempts to access cross-world data are denied"""
        conn = db_connection
        
        world_id_1 = str(uuid.uuid4())
        world_id_2 = str(uuid.uuid4())
        
        try:
            # Insert test data as admin
            await conn.execute("SET row_security = off")
            
            event_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO event_core.event_log (world_id, branch, event_id, kind, envelope, occurred_at)
                VALUES ($1, 'main', $2, 'test.cross.access', '{"test": "secret"}', NOW())
            """, uuid.UUID(world_id_1), uuid.UUID(event_id))
            
            # Re-enable RLS
            await conn.execute("SET row_security = on")
            
            # Set context to different world
            await conn.execute("SELECT set_current_world_id($1)", uuid.UUID(world_id_2))
            
            # Try to access event from world_id_1 while in world_id_2 context
            result = await conn.fetch("""
                SELECT event_id FROM event_core.event_log 
                WHERE event_id = $1
            """, uuid.UUID(event_id))
            
            # Should not see the event from the other world
            assert len(result) == 0
            
            # Try to update event from different world
            update_result = await conn.execute("""
                UPDATE event_core.event_log 
                SET envelope = '{"test": "hacked"}' 
                WHERE event_id = $1
            """, uuid.UUID(event_id))
            
            # Should update 0 rows (no access)
            assert update_result == "UPDATE 0"
            
        finally:
            # Cleanup
            await conn.execute("SET row_security = off")
            await conn.execute("""
                DELETE FROM event_core.event_log 
                WHERE kind = 'test.cross.access'
            """)
    
    async def test_admin_bypass_role(self, db_connection):
        """Test that admin role can bypass RLS for operational tasks"""
        conn = db_connection
        
        world_id = str(uuid.uuid4())
        
        try:
            # Insert test data
            await conn.execute("SET row_security = off")
            
            event_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO event_core.event_log (world_id, branch, event_id, kind, envelope, occurred_at)
                VALUES ($1, 'main', $2, 'test.admin.bypass', '{"test": "admin"}', NOW())
            """, uuid.UUID(world_id), uuid.UUID(event_id))
            
            # Test as regular user with RLS
            await conn.execute("SET row_security = on")
            await conn.execute("SELECT set_current_world_id(NULL)")  # No world context
            
            # Should not see admin event
            result_user = await conn.fetch("""
                SELECT event_id FROM event_core.event_log 
                WHERE kind = 'test.admin.bypass'
            """)
            assert len(result_user) == 0
            
            # Test as admin (bypass RLS)
            await conn.execute("SET row_security = off")
            
            # Should see all events regardless of world context
            result_admin = await conn.fetch("""
                SELECT event_id FROM event_core.event_log 
                WHERE kind = 'test.admin.bypass'
            """)
            assert len(result_admin) == 1
            assert result_admin[0]['event_id'] == uuid.UUID(event_id)
            
        finally:
            # Cleanup
            await conn.execute("SET row_security = off")
            await conn.execute("""
                DELETE FROM event_core.event_log 
                WHERE kind = 'test.admin.bypass'
            """)
    
    async def test_world_id_validation(self, db_connection):
        """Test world_id validation function"""
        conn = db_connection
        
        # Test valid UUID
        valid_uuid = str(uuid.uuid4())
        await conn.execute("SELECT set_current_world_id($1)", uuid.UUID(valid_uuid))
        
        result = await conn.fetchval("SELECT validate_world_id_setting()")
        assert result is True
        
        # Test invalid UUID format should raise exception
        with pytest.raises(Exception) as exc_info:
            await conn.execute("SET app.current_world_id = 'not-a-uuid'")
            await conn.fetchval("SELECT validate_world_id_setting()")
        
        # The exception should mention UUID validation
        assert "UUID" in str(exc_info.value)


@pytest.mark.integration  
class TestTenancyIntegration:
    """Test tenancy integration with actual service calls"""
    
    @pytest.fixture
    async def db_connection(self):
        """Create database connection for testing"""
        if not ASYNCPG_AVAILABLE:
            pytest.skip("asyncpg not available")
        
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            yield conn
            await conn.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")
    
    async def test_projector_watermarks_isolation(self, db_connection):
        """Test that projector watermarks respect world isolation"""
        conn = db_connection
        
        world_id_1 = str(uuid.uuid4())
        world_id_2 = str(uuid.uuid4())
        
        try:
            # Insert watermarks for different worlds
            await conn.execute("SET row_security = off")
            
            await conn.execute("""
                INSERT INTO event_core.projector_watermarks 
                (world_id, branch, projector_name, global_seq, processed_at)
                VALUES 
                ($1, 'main', 'test_projector', 100, NOW()),
                ($2, 'main', 'test_projector', 200, NOW())
            """, uuid.UUID(world_id_1), uuid.UUID(world_id_2))
            
            # Test isolation
            await conn.execute("SET row_security = on")
            
            # World 1 context should only see world 1 watermarks
            await conn.execute("SELECT set_current_world_id($1)", uuid.UUID(world_id_1))
            
            result_1 = await conn.fetch("""
                SELECT world_id::text, global_seq FROM event_core.projector_watermarks 
                WHERE projector_name = 'test_projector'
            """)
            
            assert len(result_1) == 1
            assert result_1[0]['world_id'] == world_id_1
            assert result_1[0]['global_seq'] == 100
            
            # World 2 context should only see world 2 watermarks
            await conn.execute("SELECT set_current_world_id($1)", uuid.UUID(world_id_2))
            
            result_2 = await conn.fetch("""
                SELECT world_id::text, global_seq FROM event_core.projector_watermarks 
                WHERE projector_name = 'test_projector'
            """)
            
            assert len(result_2) == 1
            assert result_2[0]['world_id'] == world_id_2
            assert result_2[0]['global_seq'] == 200
            
        finally:
            # Cleanup
            await conn.execute("SET row_security = off")
            await conn.execute("""
                DELETE FROM event_core.projector_watermarks 
                WHERE projector_name = 'test_projector'
            """)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
