"""
Configuration for Semantic Projector
"""

import os
from typing import Optional

from pydantic import BaseModel, Field


class SemanticProjectorConfig(BaseModel):
    """Configuration for semantic projector"""

    # Base projector configuration
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "PROJECTOR_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nexus_v2"
        )
    )
    projector_name: str = "projector_sem"
    projector_port: int = 8000
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Embedding model configuration
    embedding_model_type: str = Field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL_TYPE", "sentence-transformer")
    )  # "openai", "sentence-transformer", or "lmstudio"

    # OpenAI configuration
    openai_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    openai_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "text-embedding-ada-002")
    )

    # Sentence Transformer configuration
    sentence_transformer_model: str = Field(
        default_factory=lambda: os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
    )

    # LMStudio configuration
    lmstudio_endpoint: str = Field(
        default_factory=lambda: os.getenv(
            "LMSTUDIO_ENDPOINT", "http://localhost:1234/v1/embeddings"
        )
    )
    lmstudio_model_name: str = Field(
        default_factory=lambda: os.getenv("LMSTUDIO_MODEL", "qwen3-embedding-0.6b")
    )
    lmstudio_timeout: float = Field(
        default_factory=lambda: float(os.getenv("LMSTUDIO_TIMEOUT", "30.0"))
    )

    # Processing configuration
    max_text_length: int = Field(
        default_factory=lambda: int(os.getenv("MAX_TEXT_LENGTH", "8192"))
    )  # Maximum text length for embedding
    batch_embedding_size: int = Field(
        default_factory=lambda: int(os.getenv("BATCH_EMBEDDING_SIZE", "10"))
    )  # Batch size for embedding generation

    # Vector storage
    vector_dimensions: int = Field(
        default_factory=lambda: int(os.getenv("VECTOR_DIMENSIONS", "384"))
    )  # Default for all-MiniLM-L6-v2 (384), OpenAI ada-002 (1536), Qwen3-0.6B (varies)

    # Performance settings
    embedding_timeout: float = Field(
        default_factory=lambda: float(os.getenv("EMBEDDING_TIMEOUT", "30.0"))
    )  # Timeout for embedding generation

    model_config = {"env_prefix": "SEMANTIC_"}
