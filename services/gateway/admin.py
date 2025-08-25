"""
Admin endpoints for MnemonicNexus V2 Gateway
Provides operational management capabilities for projectors and system health
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

# Add parent directories to path for common imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.tenancy import TenancyManager, TenancyValidator

logger = logging.getLogger(__name__)

# Create admin router
admin_router = APIRouter(prefix="/v1/admin", tags=["admin"])


class RebuildRequest(BaseModel):
    """Request model for projector rebuild operations"""

    world_id: UUID
    branch: str = Field(default="main", description="Branch to rebuild")
    from_global_seq: int = Field(default=0, description="Starting sequence number")
    clear_existing: bool = Field(
        default=False, description="Clear existing projector state"
    )


class RebuildResponse(BaseModel):
    """Response model for projector rebuild operations"""

    rebuild_job_id: str
    estimated_events: int
    status: str
    projector: str
    world_id: str
    branch: str


class HealthCheckResponse(BaseModel):
    """Response model for system health checks"""

    status: str
    version: str
    components: Dict[str, Any]
    projectors: List[Dict[str, Any]]


class TenancyTestResponse(BaseModel):
    """Response model for tenancy isolation tests"""

    isolation_status: str
    rls_enabled: bool
    policies_active: bool
    test_results: Dict[str, Any]


# Dependency for database pool injection
async def get_db_pool() -> asyncpg.Pool:
    """Dependency to inject database pool (to be implemented by main app)"""
    # This will be injected by the main application
    raise HTTPException(status_code=500, detail="Database pool not configured")


@admin_router.get("/health", response_model=HealthCheckResponse)
async def get_system_health(db_pool: asyncpg.Pool = Depends(get_db_pool)):
    """
    Comprehensive system health check including projector status.
    Returns detailed health information for monitoring and alerting.
    """
    try:
        health_data = {
            "status": "healthy",
            "version": "2.0.1-dev",
            "components": {},
            "projectors": [],
        }

        # Database health check
        async with db_pool.acquire() as conn:
            db_version = await conn.fetchval("SELECT version()")
            health_data["components"]["database"] = {
                "status": "up",
                "version": db_version.split()[1] if db_version else "unknown",
                "latency_ms": 0,  # TODO: Implement actual latency measurement
            }

            # Check extensions
            extensions = await conn.fetch(
                """
                SELECT extname FROM pg_extension 
                WHERE extname IN ('vector', 'age')
            """
            )

            health_data["components"]["extensions"] = {
                "vector": any(ext["extname"] == "vector" for ext in extensions),
                "age": any(ext["extname"] == "age" for ext in extensions),
            }

            # Check projector health via watermarks
            projectors = await conn.fetch(
                """
                SELECT 
                    projector_name,
                    COUNT(*) as world_count,
                    MAX(last_processed_seq) as max_seq,
                    MAX(updated_at) as last_update
                FROM event_core.projector_watermarks
                GROUP BY projector_name
                ORDER BY projector_name
            """
            )

            for proj in projectors:
                health_data["projectors"].append(
                    {
                        "name": proj["projector_name"],
                        "status": "healthy",  # TODO: Implement actual health checks
                        "world_count": proj["world_count"],
                        "max_sequence": proj["max_seq"],
                        "last_update": (
                            proj["last_update"].isoformat()
                            if proj["last_update"]
                            else None
                        ),
                    }
                )

        return HealthCheckResponse(**health_data)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")


@admin_router.post("/projectors/{lens}/rebuild", response_model=RebuildResponse)
async def rebuild_projector(
    lens: str,
    request: RebuildRequest,
    background_tasks: BackgroundTasks,
    db_pool: asyncpg.Pool = Depends(get_db_pool),
):
    """
    Initiate projector rebuild for specified lens and tenant.
    Rebuilds projector state from event log starting from specified sequence.
    """
    valid_lenses = ["rel", "sem", "graph"]
    if lens not in valid_lenses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lens '{lens}'. Must be one of: {valid_lenses}",
        )

    try:
        # Generate rebuild job ID
        import uuid

        job_id = str(uuid.uuid4())

        # Estimate event count
        async with db_pool.acquire() as conn:
            await TenancyManager.set_world_context(conn, request.world_id)

            event_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM event_core.event_log
                WHERE world_id = $1 AND branch = $2 AND global_seq >= $3
            """,
                request.world_id,
                request.branch,
                request.from_global_seq,
            )

        # Schedule background rebuild task
        background_tasks.add_task(
            _execute_projector_rebuild, job_id, lens, request, db_pool
        )

        return RebuildResponse(
            rebuild_job_id=job_id,
            estimated_events=event_count or 0,
            status="accepted",
            projector=f"projector_{lens}",
            world_id=str(request.world_id),
            branch=request.branch,
        )

    except Exception as e:
        logger.error(f"Rebuild initiation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Rebuild failed: {e}")


@admin_router.get("/tenancy/test")
async def test_tenancy_isolation(
    world_id_1: UUID, world_id_2: UUID, db_pool: asyncpg.Pool = Depends(get_db_pool)
) -> TenancyTestResponse:
    """
    Test tenant isolation between two world IDs.
    Validates that RLS policies properly enforce boundaries.
    """
    try:
        async with db_pool.acquire() as conn:
            # Validate RLS setup
            rls_validation = await TenancyValidator.validate_rls_setup(conn)

            # Test isolation between tenants
            isolation_results = await TenancyValidator.test_isolation(
                conn, world_id_1, world_id_2
            )

        return TenancyTestResponse(
            isolation_status=(
                "pass"
                if isolation_results.get("cross_tenant_blocked", False)
                else "fail"
            ),
            rls_enabled=rls_validation.get("rls_enabled", False),
            policies_active=rls_validation.get("policies_exist", False),
            test_results={
                "rls_validation": rls_validation,
                "isolation_test": isolation_results,
            },
        )

    except Exception as e:
        logger.error(f"Tenancy test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Tenancy test failed: {e}")


@admin_router.post("/mv/refresh")
async def refresh_materialized_view(
    mv_name: str,
    world_id: Optional[UUID] = None,
    branch: Optional[str] = None,
    db_pool: asyncpg.Pool = Depends(get_db_pool),
):
    """
    Refresh materialized view.
    Supports targeted refresh by world_id/branch for efficiency.
    """
    # Validate MV name to prevent SQL injection
    valid_mvs = ["lens_rel.mv_note_enriched"]  # Add more as needed
    if mv_name not in valid_mvs:
        raise HTTPException(
            status_code=400, detail=f"Invalid MV name. Valid options: {valid_mvs}"
        )

    try:
        async with db_pool.acquire() as conn:
            if world_id:
                await TenancyManager.set_world_context(conn, world_id)

            # Refresh materialized view
            await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv_name}")

            # Get refresh metadata
            refresh_info = await conn.fetchrow(
                """
                SELECT 
                    schemaname, 
                    matviewname,
                    pg_size_pretty(pg_total_relation_size(oid)) as size
                FROM pg_matviews 
                WHERE schemaname || '.' || matviewname = $1
            """,
                mv_name,
            )

        return {
            "status": "success",
            "mv_name": mv_name,
            "refreshed_at": "now()",  # TODO: Get actual timestamp
            "size": refresh_info["size"] if refresh_info else None,
            "world_id": str(world_id) if world_id else None,
            "branch": branch,
        }

    except Exception as e:
        logger.error(f"MV refresh failed: {e}")
        raise HTTPException(status_code=500, detail=f"MV refresh failed: {e}")


@admin_router.get("/projectors")
async def list_projectors(db_pool: asyncpg.Pool = Depends(get_db_pool)):
    """
    List all active projectors with their current status.
    Provides operational visibility into projector fleet.
    """
    try:
        async with db_pool.acquire() as conn:
            projectors = await conn.fetch(
                """
                SELECT 
                    projector_name,
                    world_id,
                    branch,
                    last_processed_seq,
                    updated_at,
                    EXTRACT(EPOCH FROM (now() - updated_at)) as lag_seconds
                FROM event_core.projector_watermarks
                ORDER BY projector_name, world_id, branch
            """
            )

        projector_list = []
        for proj in projectors:
            projector_list.append(
                {
                    "name": proj["projector_name"],
                    "world_id": str(proj["world_id"]),
                    "branch": proj["branch"],
                    "last_sequence": proj["last_processed_seq"],
                    "last_update": (
                        proj["updated_at"].isoformat() if proj["updated_at"] else None
                    ),
                    "lag_seconds": (
                        float(proj["lag_seconds"]) if proj["lag_seconds"] else None
                    ),
                }
            )

        return {"projectors": projector_list, "total_count": len(projector_list)}

    except Exception as e:
        logger.error(f"Projector listing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Projector listing failed: {e}")


async def _execute_projector_rebuild(
    job_id: str, lens: str, request: RebuildRequest, db_pool: asyncpg.Pool
):
    """
    Background task to execute projector rebuild.
    This is a simplified implementation - full rebuild would require
    coordination with actual projector services.
    """
    logger.info(f"Starting rebuild job {job_id} for {lens} projector")

    try:
        async with db_pool.acquire() as conn:
            await TenancyManager.set_world_context(conn, request.world_id)

            if request.clear_existing:
                # Clear existing watermark
                await conn.execute(
                    """
                    DELETE FROM event_core.projector_watermarks
                    WHERE projector_name = $1 AND world_id = $2 AND branch = $3
                """,
                    f"projector_{lens}",
                    request.world_id,
                    request.branch,
                )

                logger.info(f"Cleared existing state for {lens} projector")

            # TODO: Implement actual rebuild logic
            # This would involve:
            # 1. Stopping the projector
            # 2. Clearing lens-specific data
            # 3. Replaying events from from_global_seq
            # 4. Restarting the projector

            logger.info(f"Rebuild job {job_id} completed (placeholder implementation)")

    except Exception as e:
        logger.error(f"Rebuild job {job_id} failed: {e}")
        # TODO: Update job status in database
