"""
Tenancy management for MNX V2.

Provides world_id/branch isolation and RLS policy management.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import asyncpg
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TenancyManager:
    """Manages tenancy context for database operations."""

    @staticmethod
    async def set_world_context(conn: asyncpg.Connection, world_id: str) -> None:
        """Set the world context for RLS policies."""
        try:
            await conn.execute("SELECT set_config('app.world_id', $1, false)", world_id)
            logger.debug(f"Set world context to {world_id}")
        except Exception as e:
            logger.error(f"Failed to set world context: {e}")
            raise

    @staticmethod
    async def clear_world_context(conn: asyncpg.Connection) -> None:
        """Clear the world context."""
        try:
            await conn.execute("SELECT set_config('app.world_id', '', false)")
            logger.debug("Cleared world context")
        except Exception as e:
            logger.error(f"Failed to clear world context: {e}")
            raise


class TenancyValidator:
    """Validates tenancy isolation and RLS setup."""

    @staticmethod
    async def validate_rls_setup(conn: asyncpg.Connection) -> Dict[str, Any]:
        """Validate that RLS policies are properly configured."""
        try:
            # Check if RLS is enabled on key tables
            rls_tables = await conn.fetch(
                """
                SELECT schemaname, tablename, rowsecurity 
                FROM pg_tables 
                WHERE schemaname IN ('event_core', 'lens_rel', 'lens_sem', 'lens_graph')
                AND tablename IN ('event_log', 'note', 'note_embedding', 'note_graph')
            """
            )

            validation = {
                "rls_enabled": True,
                "tables_checked": len(rls_tables),
                "issues": [],
            }

            for table in rls_tables:
                if not table["rowsecurity"]:
                    validation["rls_enabled"] = False
                    validation["issues"].append(
                        f"RLS not enabled on {table['schemaname']}.{table['tablename']}"
                    )

            return validation

        except Exception as e:
            logger.error(f"RLS validation failed: {e}")
            return {
                "rls_enabled": False,
                "tables_checked": 0,
                "issues": [f"Validation error: {e}"],
            }

    @staticmethod
    async def test_isolation(
        conn: asyncpg.Connection, world_id_1: str, world_id_2: str
    ) -> Dict[str, Any]:
        """Test tenancy isolation between two world IDs."""
        try:
            # Create test data in world 1
            await TenancyManager.set_world_context(conn, world_id_1)
            test_id_1 = str(uuid4())

            await conn.execute(
                """
                INSERT INTO event_core.event_log (
                    event_id, world_id, branch, event_type, event_data, 
                    correlation_id, created_at
                ) VALUES ($1, $2, 'main', 'test.isolation', '{"test": true}', $3, NOW())
            """,
                test_id_1,
                world_id_1,
                str(uuid4()),
            )

            # Try to read from world 2 context
            await TenancyManager.set_world_context(conn, world_id_2)
            world_2_data = await conn.fetch(
                """
                SELECT event_id FROM event_core.event_log 
                WHERE event_id = $1
            """,
                test_id_1,
            )

            # Clean up test data
            await TenancyManager.set_world_context(conn, world_id_1)
            await conn.execute(
                """
                DELETE FROM event_core.event_log WHERE event_id = $1
            """,
                test_id_1,
            )

            isolation_working = len(world_2_data) == 0

            return {
                "isolation_working": isolation_working,
                "world_1_data_created": True,
                "world_2_cross_access": len(world_2_data) > 0,
                "test_data_cleaned": True,
            }

        except Exception as e:
            logger.error(f"Isolation test failed: {e}")
            return {
                "isolation_working": False,
                "world_1_data_created": False,
                "world_2_cross_access": False,
                "test_data_cleaned": False,
                "error": str(e),
            }


class TenancyContext:
    """Context manager for tenancy operations."""

    def __init__(self, conn: asyncpg.Connection, world_id: str):
        self.conn = conn
        self.world_id = world_id

    async def __aenter__(self):
        await TenancyManager.set_world_context(self.conn, self.world_id)
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await TenancyManager.clear_world_context(self.conn)
