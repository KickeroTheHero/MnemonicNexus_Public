"""
Semantic Query Interface for MnemonicNexus V2
Provides similarity search and semantic retrieval capabilities with advanced performance optimizations
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import asyncpg


@dataclass
class SearchResult:
    """Structured search result with metadata"""

    entity_id: str
    entity_type: str
    similarity_score: float
    metadata: Dict[str, Any]
    model_name: str
    model_version: str
    dimensions: int
    created_at: str


@dataclass
class QueryPerformanceMetrics:
    """Performance metrics for similarity searches"""

    query_time_ms: float
    results_count: int
    total_embeddings: int
    index_used: bool
    cache_hit: bool = False


class SemanticQueryInterface:
    """Interface for semantic similarity queries using pgvector"""

    def __init__(
        self, db_pool: asyncpg.Pool, enable_caching: bool = True, cache_ttl: int = 300
    ):
        self.pool = db_pool
        self.logger = logging.getLogger(__name__)

        # Simple in-memory cache for frequent queries
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl  # 5 minutes default
        self._query_cache: Dict[str, Tuple[Any, float]] = (
            {}
        )  # query_hash -> (result, timestamp)

        # Performance metrics
        self.query_metrics: Dict[str, List[QueryPerformanceMetrics]] = defaultdict(list)

        self.logger.info(
            f"SemanticQueryInterface initialized with caching={'enabled' if enable_caching else 'disabled'}"
        )

    async def find_similar_notes(
        self,
        world_id: str,
        branch: str,
        query_text: str,
        similarity_threshold: float = 0.7,
        limit: int = 10,
        embedding_generator: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """Find notes semantically similar to query text"""

        if not embedding_generator:
            raise ValueError(
                "embedding_generator function is required for similarity search"
            )

        try:
            # Generate embedding for query
            query_embedding = await embedding_generator(query_text)

            # Convert to pgvector string format
            query_vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            async with self.pool.acquire() as conn:
                # Use cosine similarity search with pgvector
                results = await conn.fetch(
                    """
                    SELECT 
                        entity_id,
                        entity_type,
                        metadata,
                        model_name,
                        model_version,
                        dimensions,
                        created_at,
                        1 - (embedding <=> $3::vector) as similarity_score
                    FROM lens_sem.embedding
                    WHERE world_id = $1::uuid 
                      AND branch = $2::text
                      AND entity_type = 'note'
                      AND 1 - (embedding <=> $3::vector) >= $4::float
                    ORDER BY embedding <=> $3::vector ASC
                    LIMIT $5
                """,
                    world_id,
                    branch,
                    query_vector_str,
                    similarity_threshold,
                    limit,
                )

                # Convert results to dictionaries and parse metadata
                similar_notes = []
                for result in results:
                    note_data = dict(result)

                    # Parse JSON metadata
                    if isinstance(note_data["metadata"], str):
                        try:
                            note_data["metadata"] = json.loads(note_data["metadata"])
                        except json.JSONDecodeError:
                            self.logger.warning(
                                f"Failed to parse metadata for note {note_data['entity_id']}"
                            )
                            note_data["metadata"] = {}

                    # Convert datetime to string for JSON serialization
                    if note_data["created_at"]:
                        note_data["created_at"] = note_data["created_at"].isoformat()

                    similar_notes.append(note_data)

                self.logger.info(
                    f"Found {len(similar_notes)} similar notes for query in {world_id}/{branch}"
                )
                return similar_notes

        except Exception as e:
            self.logger.error(f"Error in similarity search: {e}")
            raise

    async def find_similar_embeddings(
        self,
        world_id: str,
        branch: str,
        embedding_vector: List[float],
        similarity_threshold: float = 0.7,
        limit: int = 10,
        entity_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Find embeddings similar to provided vector"""

        try:
            # Convert to pgvector string format
            vector_str = "[" + ",".join(str(x) for x in embedding_vector) + "]"

            async with self.pool.acquire() as conn:
                # Build query with optional entity_type filter
                query = """
                    SELECT 
                        entity_id,
                        entity_type,
                        metadata,
                        model_name,
                        model_version,
                        dimensions,
                        created_at,
                        1 - (embedding <=> $3::vector) as similarity_score
                    FROM lens_sem.embedding
                    WHERE world_id = $1::uuid 
                      AND branch = $2::text
                      AND 1 - (embedding <=> $3::vector) >= $4::float
                """

                params = [world_id, branch, vector_str, similarity_threshold]

                if entity_type:
                    query += " AND entity_type = $6::text"
                    params.append(entity_type)

                query += " ORDER BY embedding <=> $3::vector ASC LIMIT $5"
                params.insert(4, limit)  # Insert limit parameter

                results = await conn.fetch(query, *params)

                # Convert results and parse metadata
                similar_embeddings = []
                for result in results:
                    embedding_data = dict(result)

                    # Parse JSON metadata
                    if isinstance(embedding_data["metadata"], str):
                        try:
                            embedding_data["metadata"] = json.loads(
                                embedding_data["metadata"]
                            )
                        except json.JSONDecodeError:
                            embedding_data["metadata"] = {}

                    # Convert datetime to string
                    if embedding_data["created_at"]:
                        embedding_data["created_at"] = embedding_data[
                            "created_at"
                        ].isoformat()

                    similar_embeddings.append(embedding_data)

                self.logger.info(
                    f"Found {len(similar_embeddings)} similar embeddings in {world_id}/{branch}"
                )
                return similar_embeddings

        except Exception as e:
            self.logger.error(f"Error in embedding similarity search: {e}")
            raise

    async def get_embedding_stats(self, world_id: str, branch: str) -> Dict[str, Any]:
        """Get statistics about stored embeddings"""
        try:
            async with self.pool.acquire() as conn:
                stats = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) as total_embeddings,
                        COUNT(DISTINCT entity_id) as unique_entities,
                        COUNT(DISTINCT entity_type) as entity_types,
                        COUNT(DISTINCT model_name) as model_count,
                        MIN(created_at) as first_embedding,
                        MAX(created_at) as latest_embedding,
                        AVG(dimensions) as avg_dimensions
                    FROM lens_sem.embedding
                    WHERE world_id = $1::uuid AND branch = $2::text
                """,
                    world_id,
                    branch,
                )

                if not stats:
                    return {
                        "total_embeddings": 0,
                        "unique_entities": 0,
                        "entity_types": 0,
                        "model_count": 0,
                        "first_embedding": None,
                        "latest_embedding": None,
                        "avg_dimensions": 0,
                    }

                result = dict(stats)

                # Convert datetime fields to strings
                if result["first_embedding"]:
                    result["first_embedding"] = result["first_embedding"].isoformat()
                if result["latest_embedding"]:
                    result["latest_embedding"] = result["latest_embedding"].isoformat()

                # Round average dimensions
                if result["avg_dimensions"]:
                    result["avg_dimensions"] = round(float(result["avg_dimensions"]), 1)

                return result

        except Exception as e:
            self.logger.error(f"Error getting embedding stats: {e}")
            raise

    async def get_embedding_by_id(
        self,
        world_id: str,
        branch: str,
        entity_id: str,
        model_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get specific embedding by entity ID"""
        try:
            async with self.pool.acquire() as conn:
                if model_name:
                    result = await conn.fetchrow(
                        """
                        SELECT * FROM lens_sem.embedding
                        WHERE world_id = $1::uuid 
                          AND branch = $2::text 
                          AND entity_id = $3::text
                          AND model_name = $4::text
                    """,
                        world_id,
                        branch,
                        entity_id,
                        model_name,
                    )
                else:
                    result = await conn.fetchrow(
                        """
                        SELECT * FROM lens_sem.embedding
                        WHERE world_id = $1::uuid 
                          AND branch = $2::text 
                          AND entity_id = $3::text
                        ORDER BY created_at DESC
                        LIMIT 1
                    """,
                        world_id,
                        branch,
                        entity_id,
                    )

                if not result:
                    return None

                embedding_data = dict(result)

                # Parse JSON metadata
                if isinstance(embedding_data["metadata"], str):
                    try:
                        embedding_data["metadata"] = json.loads(
                            embedding_data["metadata"]
                        )
                    except json.JSONDecodeError:
                        embedding_data["metadata"] = {}

                # Convert datetime to string
                if embedding_data["created_at"]:
                    embedding_data["created_at"] = embedding_data[
                        "created_at"
                    ].isoformat()

                return embedding_data

        except Exception as e:
            self.logger.error(f"Error getting embedding by ID: {e}")
            raise

    def _get_cache_key(self, method: str, **kwargs) -> str:
        """Generate cache key for query caching"""
        # Create a consistent hash from method name and parameters
        import hashlib

        key_data = f"{method}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Get cached result if valid and not expired"""
        if not self.enable_caching or cache_key not in self._query_cache:
            return None

        result, timestamp = self._query_cache[cache_key]
        if time.time() - timestamp > self.cache_ttl:
            # Expired, remove from cache
            del self._query_cache[cache_key]
            return None

        return result

    def _cache_result(self, cache_key: str, result: Any):
        """Cache query result with timestamp"""
        if self.enable_caching:
            self._query_cache[cache_key] = (result, time.time())

            # Simple cache cleanup - remove oldest entries if cache grows too large
            if len(self._query_cache) > 1000:
                oldest_key = min(
                    self._query_cache.keys(), key=lambda k: self._query_cache[k][1]
                )
                del self._query_cache[oldest_key]

    async def optimized_batch_similarity_search(
        self,
        world_id: str,
        branch: str,
        query_embeddings: List[List[float]],
        similarity_threshold: float = 0.7,
        limit_per_query: int = 5,
        deduplicate_results: bool = True,
    ) -> Tuple[List[List[Dict[str, Any]]], QueryPerformanceMetrics]:
        """Optimized batch similarity search with single database query"""

        start_time = time.time()

        try:
            # Convert all embeddings to pgvector format
            vector_strings = [
                "[" + ",".join(str(x) for x in emb) + "]" for emb in query_embeddings
            ]

            async with self.pool.acquire() as conn:
                # Single query to search against all embeddings simultaneously
                # Uses UNION ALL for each embedding vector
                union_queries = []
                params = [world_id, branch, similarity_threshold]
                param_counter = 4

                for i, vector_str in enumerate(vector_strings):
                    union_queries.append(
                        f"""
                        (SELECT 
                            {i} as query_index,
                            entity_id,
                            entity_type,
                            metadata,
                            model_name,
                            model_version,
                            dimensions,
                            created_at,
                            1 - (embedding <=> ${param_counter}::vector) as similarity_score
                        FROM lens_sem.embedding
                        WHERE world_id = $1::uuid 
                          AND branch = $2::text
                          AND entity_type = 'note'
                          AND 1 - (embedding <=> ${param_counter}::vector) >= $3::float
                        ORDER BY embedding <=> ${param_counter}::vector ASC
                        LIMIT {limit_per_query})
                    """
                    )
                    params.append(vector_str)
                    param_counter += 1

                full_query = (
                    " UNION ALL ".join(union_queries)
                    + " ORDER BY query_index, similarity_score DESC"
                )

                all_results = await conn.fetch(full_query, *params)

                # Group results by query index
                grouped_results = defaultdict(list)
                total_count = 0
                seen_entities: Optional[set] = set() if deduplicate_results else None

                for result in all_results:
                    result_dict = dict(result)

                    # Deduplicate across queries if requested
                    if deduplicate_results and seen_entities is not None:
                        entity_key = (
                            result_dict["entity_id"],
                            result_dict["model_name"],
                        )
                        if entity_key in seen_entities:
                            continue
                        seen_entities.add(entity_key)

                    # Parse metadata
                    if isinstance(result_dict["metadata"], str):
                        try:
                            result_dict["metadata"] = json.loads(
                                result_dict["metadata"]
                            )
                        except json.JSONDecodeError:
                            result_dict["metadata"] = {}

                    # Convert datetime
                    if result_dict["created_at"]:
                        result_dict["created_at"] = result_dict[
                            "created_at"
                        ].isoformat()

                    # Remove query_index from final result
                    query_idx = result_dict.pop("query_index")
                    grouped_results[query_idx].append(result_dict)
                    total_count += 1

                # Convert to ordered list matching input order
                final_results = []
                for i in range(len(query_embeddings)):
                    final_results.append(grouped_results.get(i, []))

                # Performance metrics
                query_time = (time.time() - start_time) * 1000
                metrics = QueryPerformanceMetrics(
                    query_time_ms=query_time,
                    results_count=total_count,
                    total_embeddings=len(query_embeddings),
                    index_used=True,  # Assuming HNSW index is used
                    cache_hit=False,
                )

                self.query_metrics["batch_search"].append(metrics)

                self.logger.info(
                    f"Optimized batch search: {len(query_embeddings)} queries, "
                    f"{total_count} results in {query_time:.1f}ms"
                )

                return final_results, metrics

        except Exception as e:
            self.logger.error(f"Error in optimized batch similarity search: {e}")
            raise

    async def batch_similarity_search(
        self,
        world_id: str,
        branch: str,
        query_embeddings: List[List[float]],
        similarity_threshold: float = 0.7,
        limit_per_query: int = 5,
    ) -> List[List[Dict[str, Any]]]:
        """Perform batch similarity searches for multiple embeddings (legacy method)"""

        # Use optimized version and return just results
        results, _ = await self.optimized_batch_similarity_search(
            world_id, branch, query_embeddings, similarity_threshold, limit_per_query
        )
        return results

    async def get_query_analytics(self) -> Dict[str, Any]:
        """Get detailed analytics about query performance"""
        analytics: Dict[str, Any] = {
            "cache_stats": {
                "enabled": self.enable_caching,
                "cache_size": len(self._query_cache),
                "cache_ttl_seconds": self.cache_ttl,
            },
            "query_metrics": {},
        }

        for query_type, metrics_list in self.query_metrics.items():
            if not metrics_list:
                continue

            # Calculate statistics
            query_times = [m.query_time_ms for m in metrics_list]
            result_counts = [m.results_count for m in metrics_list]

            analytics["query_metrics"][query_type] = {
                "total_queries": len(metrics_list),
                "avg_query_time_ms": sum(query_times) / len(query_times),
                "min_query_time_ms": min(query_times),
                "max_query_time_ms": max(query_times),
                "avg_results_per_query": sum(result_counts) / len(result_counts),
                "total_results": sum(result_counts),
                "cache_hit_rate": sum(1 for m in metrics_list if m.cache_hit)
                / len(metrics_list),
            }

        return analytics

    async def semantic_clustering(
        self,
        world_id: str,
        branch: str,
        min_similarity: float = 0.8,
        min_cluster_size: int = 2,
    ) -> List[Dict[str, Any]]:
        """Find clusters of semantically similar embeddings"""

        try:
            async with self.pool.acquire() as conn:
                # Get all embeddings for clustering
                embeddings = await conn.fetch(
                    """
                    SELECT entity_id, embedding, metadata, model_name, created_at
                    FROM lens_sem.embedding
                    WHERE world_id = $1::uuid AND branch = $2::text
                    ORDER BY created_at DESC
                """,
                    world_id,
                    branch,
                )

                if len(embeddings) < min_cluster_size:
                    return []

                # Simple clustering: for each embedding, find similar ones
                clusters: list = []
                processed = set()

                for i, emb1 in enumerate(embeddings):
                    if emb1["entity_id"] in processed:
                        continue

                    cluster_members = [emb1]
                    processed.add(emb1["entity_id"])

                    # Find similar embeddings
                    similar = await conn.fetch(
                        """
                        SELECT entity_id, embedding, metadata, model_name, created_at,
                               1 - (embedding <=> $3::vector) as similarity
                        FROM lens_sem.embedding
                        WHERE world_id = $1::uuid 
                          AND branch = $2::text
                          AND entity_id != $4::text
                          AND 1 - (embedding <=> $3::vector) >= $5::float
                        ORDER BY similarity DESC
                    """,
                        world_id,
                        branch,
                        str(emb1["embedding"]),
                        emb1["entity_id"],
                        min_similarity,
                    )

                    for similar_emb in similar:
                        if similar_emb["entity_id"] not in processed:
                            cluster_members.append(similar_emb)
                            processed.add(similar_emb["entity_id"])

                    if len(cluster_members) >= min_cluster_size:
                        # Parse metadata for cluster members
                        for member in cluster_members:
                            if isinstance(member["metadata"], str):
                                try:
                                    member["metadata"] = json.loads(member["metadata"])
                                except json.JSONDecodeError:
                                    member["metadata"] = {}

                            if member["created_at"]:
                                member["created_at"] = member["created_at"].isoformat()

                        clusters.append(
                            {
                                "cluster_id": f"cluster_{len(clusters)}",
                                "size": len(cluster_members),
                                "avg_similarity": sum(
                                    m.get("similarity", 1.0) for m in cluster_members
                                )
                                / len(cluster_members),
                                "members": cluster_members,
                            }
                        )

                self.logger.info(
                    f"Found {len(clusters)} semantic clusters in {world_id}/{branch}"
                )
                return clusters

        except Exception as e:
            self.logger.error(f"Error in semantic clustering: {e}")
            raise

    async def clear_cache(self):
        """Clear query cache manually"""
        self._query_cache.clear()
        self.logger.info("Query cache cleared")

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for semantic query interface"""
        health = {
            "status": "healthy",
            "timestamp": time.time(),
            "cache_enabled": self.enable_caching,
            "cache_size": len(self._query_cache),
            "total_queries_processed": sum(
                len(metrics) for metrics in self.query_metrics.values()
            ),
        }

        try:
            # Test database connectivity
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT COUNT(*) FROM lens_sem.embedding")
                health["total_embeddings"] = result
                health["database_connection"] = "ok"

        except Exception as e:
            health["status"] = "unhealthy"
            health["database_connection"] = f"error: {str(e)}"

        return health
