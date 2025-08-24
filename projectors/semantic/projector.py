"""
Semantic Projector for MnemonicNexus V2
Processes events into semantic embeddings and search structures
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List

import asyncpg
from queries import SemanticQueryInterface
from sdk.projector import ProjectorSDK

# HTTP client for LMStudio
try:
    import httpx
except ImportError:
    httpx = None

# ML imports with graceful fallback
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    import openai
except ImportError:
    openai = None


class SemanticProjector(ProjectorSDK):
    """Semantic lens projector implementation for vector search and embeddings"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.embedding_model = None
        self.query_interface = None
        self.http_client = None
        self._initialize_embedding_model()

    async def start_polling(self):
        """Start polling with query interface initialization"""
        await super().start_polling()
        # Initialize query interface after database pool is ready
        if self.db_pool:
            self.query_interface = SemanticQueryInterface(self.db_pool)
            self.logger.info("✅ SemanticQueryInterface initialized with caching enabled")

    async def shutdown(self):
        """Clean shutdown including HTTP client"""
        if self.http_client:
            await self.http_client.aclose()
        await super().shutdown()

    @property
    def name(self) -> str:
        return "projector_sem"

    @property
    def lens(self) -> str:
        return "sem"

    def _initialize_embedding_model(self):
        """Initialize embedding model based on configuration"""
        model_type = self.config.get("embedding_model_type", "sentence-transformer")

        self.logger.info(f"Initializing embedding model: {model_type}")

        if model_type == "lmstudio":
            if httpx is None:
                self.logger.error("httpx library not installed. Install with: pip install httpx")
                return

            endpoint = self.config.get("lmstudio_endpoint", "http://localhost:1234/v1/embeddings")
            model_name = self.config.get("lmstudio_model_name", "qwen3-embedding-0.6b")
            timeout = self.config.get("lmstudio_timeout", 30.0)

            self.http_client = httpx.AsyncClient(timeout=timeout)
            self.embedding_model = "lmstudio"  # Marker for LMStudio usage
            self.logger.info(f"Initialized LMStudio client: {endpoint} with model {model_name}")

        elif model_type == "openai":
            if openai is None:
                raise ImportError("OpenAI library not installed. Install with: pip install openai")

            api_key = self.config.get("openai_api_key")
            if not api_key:
                self.logger.warning(
                    "OpenAI API key not provided, falling back to placeholder embeddings"
                )
                return

            openai.api_key = api_key
            self.embedding_model = "openai"  # Marker for OpenAI usage

        elif model_type == "sentence-transformer":
            if SentenceTransformer is None:
                self.logger.warning(
                    "sentence-transformers not installed, using placeholder embeddings"
                )
                return

            model_name = self.config.get("sentence_transformer_model", "all-MiniLM-L6-v2")
            try:
                self.embedding_model = SentenceTransformer(model_name)
                self.logger.info(f"Loaded sentence transformer model: {model_name}")
            except Exception as e:
                self.logger.error(f"Failed to load sentence transformer model {model_name}: {e}")
                self.logger.warning("Falling back to placeholder embeddings")
                return
        else:
            self.logger.warning(
                f"Unknown embedding model type: {model_type}, using placeholder embeddings"
            )

    async def apply(self, envelope: Dict[str, Any], global_seq: int) -> None:
        """Apply event to semantic lens with idempotency"""
        kind = envelope["kind"]
        payload = envelope["payload"]
        world_id = envelope["world_id"]
        branch = envelope["branch"]

        self.logger.info(f"Processing {kind} event for {world_id}/{branch} (seq: {global_seq})")

        async with self.db_pool.acquire() as conn:
            if kind == "note.created":
                await self._handle_note_created(conn, world_id, branch, payload)
            elif kind == "note.updated":
                await self._handle_note_updated(conn, world_id, branch, payload)
            elif kind == "note.deleted":
                await self._handle_note_deleted(conn, world_id, branch, payload)
            else:
                # Semantic projector focuses on note content for embeddings
                self.logger.debug(f"Skipping non-note event: {kind}")

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text"""
        if not text.strip():
            # Return zero vector for empty text
            dimensions = self.config.get("vector_dimensions", 384)
            return [0.0] * dimensions

        model_type = self.config.get("embedding_model_type", "sentence-transformer")

        if model_type == "lmstudio" and self.embedding_model == "lmstudio" and self.http_client:
            try:
                endpoint = self.config.get(
                    "lmstudio_endpoint", "http://localhost:1234/v1/embeddings"
                )
                model_name = self.config.get("lmstudio_model_name", "qwen3-embedding-0.6b")

                payload = {"model": model_name, "input": text}

                self.logger.debug(
                    f"Making LMStudio request to {endpoint} with model {model_name}, text length: {len(text)}"
                )
                response = await self.http_client.post(endpoint, json=payload)
                self.logger.debug(f"LMStudio response status: {response.status_code}")
                response.raise_for_status()

                result = response.json()
                embedding = result["data"][0]["embedding"]

                self.logger.info(
                    f"Generated {len(embedding)}-dim embedding via LMStudio for content: '{text[:50]}...'"
                )
                return embedding

            except Exception as e:
                self.logger.error(
                    f"LMStudio embedding generation failed: {e} (type: {type(e).__name__})"
                )
                self.logger.error(
                    f"Request details - endpoint: {endpoint}, model: {model_name}, text_len: {len(text) if 'text' in locals() else 'unknown'}"
                )
                # Fall back to zero vector
                dimensions = self.config.get("vector_dimensions", 384)
                return [0.0] * dimensions

        elif model_type == "openai" and self.embedding_model == "openai":
            try:
                response = await openai.Embedding.acreate(
                    model=self.config.get("openai_model", "text-embedding-ada-002"), input=text
                )
                return response["data"][0]["embedding"]
            except Exception as e:
                self.logger.error(f"OpenAI embedding generation failed: {e}")
                # Fall back to zero vector
                return [0.0] * 1536  # OpenAI ada-002 dimensions

        elif model_type == "sentence-transformer" and self.embedding_model is not None:
            try:
                # Run embedding generation in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                embedding = await loop.run_in_executor(
                    None, lambda: self.embedding_model.encode(text).tolist()
                )
                return embedding
            except Exception as e:
                self.logger.error(f"Sentence transformer embedding generation failed: {e}")
                # Fall back to zero vector
                dimensions = self.config.get("vector_dimensions", 384)
                return [0.0] * dimensions

        else:
            # Fall back to zero vector (placeholder mode)
            dimensions = self.config.get("vector_dimensions", 384)
            return [0.0] * dimensions

    async def _handle_note_created(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle note.created event by creating semantic entry with real embeddings"""
        content = self._extract_content(payload)

        # Generate real embedding for the content
        embedding_vector = await self._generate_embedding(content)

        # Convert to pgvector string format: '[0.1234,0.5678,...]'
        embedding_str = "[" + ",".join(str(x) for x in embedding_vector) + "]"

        # Get model info for tracking
        model_info = self._get_model_info()

        metadata = {
            "note_id": payload["id"],
            "title": payload.get("title", ""),
            "content": content,
            "content_length": len(content),
        }

        await conn.execute(
            """
            INSERT INTO lens_sem.embedding (
                world_id, branch, entity_id, entity_type, model_name, model_version,
                dimensions, embedding, metadata, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, COALESCE($10::timestamptz, now()))
            ON CONFLICT (world_id, branch, entity_id, model_name) DO NOTHING
        """,
            world_id,
            branch,
            payload["id"],  # entity_id
            "note",  # entity_type
            model_info["name"],  # model_name
            model_info["version"],  # model_version
            len(embedding_vector),  # dimensions
            embedding_str,  # embedding vector
            json.dumps(metadata),  # metadata as JSON string
            payload.get("created_at"),
        )

        self.logger.info(
            f"Created semantic embedding for note {payload['id']} in {world_id}/{branch} with {len(embedding_vector)} dimensions"
        )

    async def _handle_note_updated(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle note.updated event by regenerating semantic entry"""
        # Delete existing embeddings for this note
        model_info = self._get_model_info()
        await conn.execute(
            """
            DELETE FROM lens_sem.embedding 
            WHERE world_id = $1 AND branch = $2 AND entity_id = $3 AND model_name = $4
        """,
            world_id,
            branch,
            payload["id"],
            model_info["name"],
        )

        # Regenerate embeddings (same logic as create)
        await self._handle_note_created(conn, world_id, branch, payload)

        self.logger.info(
            f"Updated semantic embedding for note {payload['id']} in {world_id}/{branch}"
        )

    def _get_model_info(self) -> Dict[str, str]:
        """Get current model name and version for tracking"""
        model_type = self.config.get("embedding_model_type", "sentence-transformer")

        if model_type == "lmstudio" and self.embedding_model == "lmstudio":
            return {
                "name": self.config.get("lmstudio_model_name", "qwen3-embedding-0.6b"),
                "version": "lmstudio",
            }
        elif model_type == "openai" and self.embedding_model == "openai":
            return {
                "name": self.config.get("openai_model", "text-embedding-ada-002"),
                "version": "openai-api",
            }
        elif model_type == "sentence-transformer" and isinstance(
            self.embedding_model, SentenceTransformer
        ):
            model_name = self.config.get("sentence_transformer_model", "all-MiniLM-L6-v2")
            return {"name": model_name, "version": "sentence-transformers"}

        return {"name": "placeholder", "version": "0.1"}

    def _setup_routes(self):
        """Setup semantic-specific HTTP routes"""
        # Get base routes from parent
        super()._setup_routes()

        # Add semantic similarity search endpoints
        @self.app.get("/search")
        async def semantic_search(
            query: str, world_id: str, branch: str = "main", threshold: float = 0.7, limit: int = 10
        ):
            """Semantic similarity search endpoint"""
            if not self.query_interface:
                return {"error": "Query interface not initialized"}

            try:
                results = await self.query_interface.find_similar_notes(
                    world_id=world_id,
                    branch=branch,
                    query_text=query,
                    similarity_threshold=threshold,
                    limit=limit,
                    embedding_generator=self._generate_embedding,
                )

                return {
                    "query": query,
                    "world_id": world_id,
                    "branch": branch,
                    "threshold": threshold,
                    "results": results,
                    "count": len(results),
                }

            except Exception as e:
                self.logger.error(f"Search error: {e}")
                return {"error": str(e)}

        @self.app.get("/stats")
        async def embedding_stats(world_id: str, branch: str = "main"):
            """Get embedding statistics"""
            if not self.query_interface:
                return {"error": "Query interface not initialized"}

            try:
                stats = await self.query_interface.get_embedding_stats(world_id, branch)
                return stats
            except Exception as e:
                self.logger.error(f"Stats error: {e}")
                return {"error": str(e)}

        @self.app.get("/embedding/{entity_id}")
        async def get_embedding(entity_id: str, world_id: str, branch: str = "main"):
            """Get specific embedding by entity ID"""
            if not self.query_interface:
                return {"error": "Query interface not initialized"}

            try:
                embedding = await self.query_interface.get_embedding_by_id(
                    world_id=world_id, branch=branch, entity_id=entity_id
                )

                if not embedding:
                    return {"error": "Embedding not found"}

                return embedding

            except Exception as e:
                self.logger.error(f"Get embedding error: {e}")
                return {"error": str(e)}

        @self.app.post("/batch-search")
        async def optimized_batch_search(
            request_data: dict,
            world_id: str,
            branch: str = "main",
            threshold: float = 0.7,
            limit: int = 5,
            deduplicate: bool = True,
        ):
            """Optimized batch similarity search with performance metrics"""
            if not self.query_interface:
                return {"error": "Query interface not initialized"}

            try:
                # Extract query texts from request
                query_texts = request_data.get("queries", [])
                if not query_texts:
                    return {"error": "No queries provided"}

                # Generate embeddings for all queries
                query_embeddings = []
                for text in query_texts:
                    embedding = await self._generate_embedding(text)
                    query_embeddings.append(embedding)

                # Perform optimized batch search
                results, metrics = await self.query_interface.optimized_batch_similarity_search(
                    world_id=world_id,
                    branch=branch,
                    query_embeddings=query_embeddings,
                    similarity_threshold=threshold,
                    limit_per_query=limit,
                    deduplicate_results=deduplicate,
                )

                return {
                    "queries": query_texts,
                    "world_id": world_id,
                    "branch": branch,
                    "threshold": threshold,
                    "results": results,
                    "performance_metrics": {
                        "query_time_ms": metrics.query_time_ms,
                        "total_results": metrics.results_count,
                        "queries_count": len(query_texts),
                        "avg_time_per_query": metrics.query_time_ms / len(query_texts),
                        "index_used": metrics.index_used,
                    },
                }

            except Exception as e:
                self.logger.error(f"Batch search error: {e}")
                return {"error": str(e)}

        @self.app.get("/analytics")
        async def query_analytics():
            """Get detailed analytics about query performance"""
            if not self.query_interface:
                return {"error": "Query interface not initialized"}

            try:
                analytics = await self.query_interface.get_query_analytics()
                return analytics

            except Exception as e:
                self.logger.error(f"Analytics error: {e}")
                return {"error": str(e)}

        @self.app.get("/clusters")
        async def semantic_clusters(
            world_id: str,
            branch: str = "main",
            min_similarity: float = 0.8,
            min_cluster_size: int = 2,
        ):
            """Find semantic clusters of similar embeddings"""
            if not self.query_interface:
                return {"error": "Query interface not initialized"}

            try:
                clusters = await self.query_interface.semantic_clustering(
                    world_id=world_id,
                    branch=branch,
                    min_similarity=min_similarity,
                    min_cluster_size=min_cluster_size,
                )

                return {
                    "world_id": world_id,
                    "branch": branch,
                    "min_similarity": min_similarity,
                    "min_cluster_size": min_cluster_size,
                    "clusters": clusters,
                    "total_clusters": len(clusters),
                }

            except Exception as e:
                self.logger.error(f"Clustering error: {e}")
                return {"error": str(e)}

        @self.app.post("/cache/clear")
        async def clear_cache():
            """Clear query cache manually"""
            if not self.query_interface:
                return {"error": "Query interface not initialized"}

            try:
                await self.query_interface.clear_cache()
                return {"status": "cache_cleared", "timestamp": time.time()}

            except Exception as e:
                self.logger.error(f"Cache clear error: {e}")
                return {"error": str(e)}

    async def _handle_note_deleted(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle note.deleted event by removing semantic entry"""
        await conn.execute(
            """
            DELETE FROM lens_sem.embedding 
            WHERE world_id = $1 AND branch = $2 AND entity_id = $3 AND entity_type = 'note'
        """,
            world_id,
            branch,
            payload["id"],
        )

        self.logger.debug(
            f"Deleted semantic embedding for note {payload['id']} from {world_id}/{branch}"
        )

    def _extract_content(self, payload: Dict[str, Any]) -> str:
        """Extract searchable content from note payload"""
        title = payload.get("title", "")
        body = payload.get("body", "")

        # Combine title and body for semantic indexing
        content_parts = []
        if title:
            content_parts.append(title)
        if body:
            content_parts.append(body)

        return " ".join(content_parts).strip()

    async def _get_state_snapshot(
        self, conn: asyncpg.Connection, world_id: str, branch: str
    ) -> Dict[str, Any]:
        """Get deterministic semantic lens state snapshot"""

        # Get sorted embedding data for deterministic hash
        embeddings = await conn.fetch(
            """
            SELECT entity_id, entity_type, model_name, model_version, dimensions, created_at
            FROM lens_sem.embedding
            WHERE world_id = $1 AND branch = $2
            ORDER BY entity_id, model_name
        """,
            world_id,
            branch,
        )

        # Convert to serializable format
        def serialize_record(record):
            """Convert asyncpg record to JSON-serializable dict"""
            result = dict(record)
            for key, value in result.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
            return result

        return {
            "lens": "semantic",
            "world_id": world_id,
            "branch": branch,
            "embeddings": [serialize_record(emb) for emb in embeddings],
            "embedding_count": len(embeddings),
        }
