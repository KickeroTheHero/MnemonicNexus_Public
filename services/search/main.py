"""
MnemonicNexus V2 Hybrid Search Service

Implements /v1/search/hybrid endpoint with multiple search modes:
- relational_only: SQL-based search on EMO content/metadata
- vector_only: Pure semantic similarity search
- hybrid: Combined relational + vector search with fusion
- hybrid+graph_expansion: Hybrid search + graph traversal expansion

Supports rank versioning, stable ordering, and performance SLOs per checklist.
"""

import asyncio
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="MnemonicNexus V2 Search",
    description="Hybrid search API with multiple search strategies",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
db_pool: Optional[asyncpg.Pool] = None
http_client: Optional[httpx.AsyncClient] = None

# Search mode constants
SEARCH_MODES = {
    "relational_only": "Pure SQL-based search",
    "vector_only": "Pure semantic similarity search",
    "hybrid": "Combined relational + vector with fusion",
    "hybrid+graph_expansion": "Hybrid + graph traversal expansion",
}

RANK_VERSION = "v2.0-alpha"  # Stable rank versioning for reproducible results


class SearchRequest(BaseModel):
    query: str
    world_id: str
    branch: str = "main"
    mode: str = "hybrid"
    k: int = 50
    threshold: float = 0.7
    weights: Optional[Dict[str, float]] = {"relational": 0.3, "semantic": 0.7}


class SearchResult(BaseModel):
    emo_id: str
    emo_type: str
    content: str
    score: float
    rank: int
    source: str  # "relational", "semantic", or "fusion"


class HybridSearchResponse(BaseModel):
    query: str
    world_id: str
    branch: str
    mode: str
    k: int
    rank_version: str
    fusion_method: str
    weights: Dict[str, float]
    tie_break_policy: str
    results: List[SearchResult]
    count: int
    latency_ms: float
    debug_info: Optional[Dict[str, Any]] = None


@app.on_event("startup")
async def startup_event():
    """Initialize database connection and HTTP client"""
    global db_pool, http_client

    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@postgres-v2:5432/nexus_v2"
    )

    try:
        db_pool = await asyncpg.create_pool(
            database_url, min_size=2, max_size=20, command_timeout=30
        )
        http_client = httpx.AsyncClient(timeout=30.0)

        print("✅ Hybrid Search Service started successfully")
        print(f"✅ Database pool created: {database_url}")
    except Exception as e:
        print(f"❌ Search service startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources"""
    if db_pool:
        await db_pool.close()
    if http_client:
        await http_client.aclose()
    print("✅ Search service shut down cleanly")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

        return {
            "status": "healthy",
            "version": "2.0.0",
            "supported_modes": list(SEARCH_MODES.keys()),
            "rank_version": RANK_VERSION,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")


@app.post("/v1/search/hybrid", response_model=HybridSearchResponse)
async def hybrid_search(request: SearchRequest):
    """
    Hybrid search endpoint with multiple modes and stable ranking

    Implements all search modes from MNX checklist:
    - relational_only: SQL search on content/metadata
    - vector_only: Semantic similarity only
    - hybrid: Weighted fusion of relational + semantic
    - hybrid+graph_expansion: Hybrid + graph traversal
    """
    start_time = time.time()

    # Validate search mode
    if request.mode not in SEARCH_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search mode. Supported: {list(SEARCH_MODES.keys())}",
        )

    try:
        async with db_pool.acquire() as conn:
            if request.mode == "relational_only":
                results = await _relational_search(conn, request)
            elif request.mode == "vector_only":
                results = await _vector_search(conn, request)
            elif request.mode == "hybrid":
                results = await _hybrid_search(conn, request)
            elif request.mode == "hybrid+graph_expansion":
                results = await _hybrid_graph_search(conn, request)
            else:
                raise HTTPException(status_code=400, detail="Invalid search mode")

            latency_ms = (time.time() - start_time) * 1000

            return HybridSearchResponse(
                query=request.query,
                world_id=request.world_id,
                branch=request.branch,
                mode=request.mode,
                k=request.k,
                rank_version=RANK_VERSION,
                fusion_method=(
                    "weighted_sum" if request.mode == "hybrid" else "single_source"
                ),
                weights=request.weights or {},
                tie_break_policy="emo_id_asc",
                results=results,
                count=len(results),
                latency_ms=latency_ms,
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


async def _relational_search(
    conn: asyncpg.Connection, request: SearchRequest
) -> List[SearchResult]:
    """Pure relational search using SQL full-text search"""

    # Use PostgreSQL full-text search on EMO content
    query_results = await conn.fetch(
        """
        SELECT 
            emo_id::text,
            emo_type,
            content,
            ts_rank(to_tsvector('english', COALESCE(content, '')), plainto_tsquery('english', $1)) as score
        FROM lens_emo.emo_current
        WHERE world_id = $2::uuid 
        AND branch = $3
        AND NOT deleted
        AND to_tsvector('english', COALESCE(content, '')) @@ plainto_tsquery('english', $1)
        ORDER BY score DESC, emo_id ASC  -- Stable tie-breaking
        LIMIT $4
    """,
        request.query,
        request.world_id,
        request.branch,
        request.k,
    )

    results = []
    for i, row in enumerate(query_results):
        results.append(
            SearchResult(
                emo_id=row["emo_id"],
                emo_type=row["emo_type"],
                content=row["content"] or "",
                score=float(row["score"]),
                rank=i + 1,
                source="relational",
            )
        )

    return results


async def _vector_search(
    conn: asyncpg.Connection, request: SearchRequest
) -> List[SearchResult]:
    """Pure vector similarity search using EMO embeddings"""

    # Generate query embedding
    query_embedding = await _generate_query_embedding(request.query)
    if not query_embedding:
        return []

    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    # Vector similarity search
    query_results = await conn.fetch(
        """
        SELECT 
            ec.emo_id::text,
            ec.emo_type,
            ec.content,
            1 - (ee.embedding_vector <=> $1::vector) as similarity_score
        FROM lens_emo.emo_current ec
        JOIN lens_emo.emo_embeddings ee ON (
            ec.emo_id = ee.emo_id 
            AND ec.world_id = ee.world_id 
            AND ec.branch = ee.branch
        )
        WHERE ec.world_id = $2::uuid 
        AND ec.branch = $3
        AND NOT ec.deleted
        AND ee.embedding_vector IS NOT NULL
        AND (1 - (ee.embedding_vector <=> $1::vector)) >= $4
        ORDER BY similarity_score DESC, ec.emo_id ASC  -- Stable tie-breaking  
        LIMIT $5
    """,
        embedding_str,
        request.world_id,
        request.branch,
        request.threshold,
        request.k,
    )

    results = []
    for i, row in enumerate(query_results):
        results.append(
            SearchResult(
                emo_id=row["emo_id"],
                emo_type=row["emo_type"],
                content=row["content"] or "",
                score=float(row["similarity_score"]),
                rank=i + 1,
                source="semantic",
            )
        )

    return results


async def _hybrid_search(
    conn: asyncpg.Connection, request: SearchRequest
) -> List[SearchResult]:
    """Hybrid search with weighted fusion of relational + semantic results"""

    # Get separate result sets
    rel_request = SearchRequest(**request.dict())
    rel_request.mode = "relational_only"
    rel_request.k = min(request.k * 2, 100)  # Get more candidates for fusion

    vec_request = SearchRequest(**request.dict())
    vec_request.mode = "vector_only"
    vec_request.k = min(request.k * 2, 100)

    rel_results = await _relational_search(conn, rel_request)
    vec_results = await _vector_search(conn, vec_request)

    # Fusion using weighted combination
    weights = request.weights or {"relational": 0.3, "semantic": 0.7}
    rel_weight = weights.get("relational", 0.3)
    sem_weight = weights.get("semantic", 0.7)

    # Normalize scores to 0-1 range
    if rel_results:
        max_rel_score = max(r.score for r in rel_results)
        for r in rel_results:
            r.score = r.score / max_rel_score if max_rel_score > 0 else 0

    if vec_results:
        max_vec_score = max(r.score for r in vec_results)
        for r in vec_results:
            r.score = r.score / max_vec_score if max_vec_score > 0 else 0

    # Create combined result set
    combined_results = {}

    # Add relational results
    for result in rel_results:
        combined_results[result.emo_id] = SearchResult(
            emo_id=result.emo_id,
            emo_type=result.emo_type,
            content=result.content,
            score=result.score * rel_weight,
            rank=0,  # Will be set after sorting
            source="fusion",
        )

    # Add/combine semantic results
    for result in vec_results:
        if result.emo_id in combined_results:
            # Combine scores
            combined_results[result.emo_id].score += result.score * sem_weight
        else:
            # Add new result
            combined_results[result.emo_id] = SearchResult(
                emo_id=result.emo_id,
                emo_type=result.emo_type,
                content=result.content,
                score=result.score * sem_weight,
                rank=0,
                source="fusion",
            )

    # Sort by combined score with stable tie-breaking
    sorted_results = sorted(
        combined_results.values(),
        key=lambda x: (-x.score, x.emo_id),  # Descending score, ascending emo_id
    )

    # Set ranks and limit results
    final_results = []
    for i, result in enumerate(sorted_results[: request.k]):
        result.rank = i + 1
        final_results.append(result)

    return final_results


async def _hybrid_graph_search(
    conn: asyncpg.Connection, request: SearchRequest
) -> List[SearchResult]:
    """Hybrid search with graph expansion using EMO relationships"""

    # First get hybrid results as seed set
    hybrid_request = SearchRequest(**request.dict())
    hybrid_request.mode = "hybrid"
    hybrid_request.k = min(request.k // 2, 25)  # Get fewer seeds for expansion

    seed_results = await _hybrid_search(conn, hybrid_request)
    if not seed_results:
        return []

    # Extract seed EMO IDs
    seed_emo_ids = [r.emo_id for r in seed_results]

    # Find related EMOs through graph traversal
    try:
        related_emos = []
        for emo_id in seed_emo_ids:
            # Get EMO descendants (things derived from this EMO)
            descendants = await conn.fetch(
                """
                SELECT descendant_id::text, depth
                FROM lens_emo.get_emo_descendants($1::uuid, $2, $3::uuid, 2)
                LIMIT 5
            """,
                request.world_id,
                request.branch,
                emo_id,
            )

            for desc in descendants:
                if desc["descendant_id"] not in seed_emo_ids:
                    related_emos.append(
                        {
                            "emo_id": desc["descendant_id"],
                            "depth": desc["depth"],
                            "source_seed": emo_id,
                        }
                    )

    except Exception as e:
        # If graph traversal fails, fall back to hybrid results
        print(f"Graph expansion failed, falling back to hybrid: {e}")
        return seed_results

    # Get content for related EMOs
    if related_emos:
        related_ids = [r["emo_id"] for r in related_emos]
        related_content = await conn.fetch(
            """
            SELECT emo_id::text, emo_type, content
            FROM lens_emo.emo_current
            WHERE emo_id = ANY($1::uuid[]) 
            AND world_id = $2::uuid 
            AND branch = $3
            AND NOT deleted
        """,
            related_ids,
            request.world_id,
            request.branch,
        )

        # Add related results with decayed scores
        for content_row in related_content:
            emo_id = content_row["emo_id"]

            # Find the depth for score decay
            depth = next((r["depth"] for r in related_emos if r["emo_id"] == emo_id), 1)

            # Decay score based on graph distance
            base_score = 0.5  # Base score for graph-expanded results
            decayed_score = base_score * (0.7 ** (depth - 1))  # Decay by 30% per hop

            seed_results.append(
                SearchResult(
                    emo_id=emo_id,
                    emo_type=content_row["emo_type"],
                    content=content_row["content"] or "",
                    score=decayed_score,
                    rank=0,  # Will be set after sorting
                    source="graph_expansion",
                )
            )

    # Re-sort combined results
    sorted_results = sorted(seed_results, key=lambda x: (-x.score, x.emo_id))

    # Set final ranks and limit
    final_results = []
    for i, result in enumerate(sorted_results[: request.k]):
        result.rank = i + 1
        final_results.append(result)

    return final_results


async def _generate_query_embedding(query: str) -> Optional[List[float]]:
    """Generate embedding for search query using LMStudio"""
    if not query.strip():
        return None

    try:
        endpoint = os.getenv("LMSTUDIO_ENDPOINT", "http://localhost:1234/v1/embeddings")
        model_name = os.getenv("LMSTUDIO_MODEL", "text-embedding-nomic-embed-text-v1.5")

        payload = {"model": model_name, "input": query}

        response = await http_client.post(endpoint, json=payload)
        response.raise_for_status()

        result = response.json()
        return result["data"][0]["embedding"]

    except Exception as e:
        print(f"Failed to generate query embedding: {e}")
        return None


@app.get("/v1/search/modes")
async def get_search_modes():
    """Get available search modes and their descriptions"""
    return {
        "modes": SEARCH_MODES,
        "rank_version": RANK_VERSION,
        "default_weights": {"relational": 0.3, "semantic": 0.7},
    }


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "MnemonicNexus V2 Hybrid Search",
        "version": "2.0.0",
        "status": "ready",
        "endpoints": {
            "search": "/v1/search/hybrid",
            "modes": "/v1/search/modes",
            "health": "/health",
        },
        "supported_modes": list(SEARCH_MODES.keys()),
        "rank_version": RANK_VERSION,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8087, reload=True)
