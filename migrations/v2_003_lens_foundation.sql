-- MnemonicNexus V2 Schema Migration: Lens Foundation
-- Phase A2: Multi-lens projection schemas with comprehensive tenancy
-- File: v2_003_lens_foundation.sql
-- Dependencies: v2_001_event_core.sql

-- =============================================================================
-- RELATIONAL LENS (lens_rel)
-- =============================================================================

-- Create relational lens schema
CREATE SCHEMA IF NOT EXISTS lens_rel;

-- Notes with comprehensive tenancy
CREATE TABLE lens_rel.note (
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    note_id UUID NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (world_id, branch, note_id)
);

-- Note tags with composite keys
CREATE TABLE lens_rel.note_tag (
    world_id UUID NOT NULL,
    branch TEXT NOT NULL, 
    note_id UUID NOT NULL,
    tag TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (world_id, branch, note_id, tag),
    FOREIGN KEY (world_id, branch, note_id) 
        REFERENCES lens_rel.note(world_id, branch, note_id) ON DELETE CASCADE
);

-- Inter-note links
CREATE TABLE lens_rel.link (
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    src_id UUID NOT NULL,
    dst_id UUID NOT NULL, 
    link_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (world_id, branch, src_id, dst_id, link_type),
    FOREIGN KEY (world_id, branch, src_id) 
        REFERENCES lens_rel.note(world_id, branch, note_id) ON DELETE CASCADE,
    FOREIGN KEY (world_id, branch, dst_id) 
        REFERENCES lens_rel.note(world_id, branch, note_id) ON DELETE CASCADE
);

-- Performance indexes for relational lens
CREATE INDEX idx_note_world_branch ON lens_rel.note (world_id, branch);
CREATE INDEX idx_note_updated_at ON lens_rel.note (world_id, branch, updated_at DESC);
CREATE INDEX idx_note_title_search ON lens_rel.note USING gin (to_tsvector('english', title));
CREATE INDEX idx_note_body_search ON lens_rel.note USING gin (to_tsvector('english', body));

CREATE INDEX idx_note_tag_tag ON lens_rel.note_tag (world_id, branch, tag);
CREATE INDEX idx_link_src ON lens_rel.link (world_id, branch, src_id);
CREATE INDEX idx_link_dst ON lens_rel.link (world_id, branch, dst_id);

-- =============================================================================
-- SEMANTIC LENS (lens_sem)
-- =============================================================================

-- Create semantic lens schema
CREATE SCHEMA IF NOT EXISTS lens_sem;

-- Embedding table with pgvector integration
CREATE TABLE lens_sem.embedding (
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    entity_id UUID NOT NULL,
    entity_type TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedding VECTOR(768), -- Default to 768 dimensions (OpenAI ada-002)
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (world_id, branch, entity_id, model_name),
    CONSTRAINT check_embedding_dimensions CHECK (dimensions = 768)
);

-- Separate indexes for vector operations (as recommended in architecture.md)
CREATE INDEX IF NOT EXISTS idx_embedding_ivfflat 
ON lens_sem.embedding USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- HNSW index (commented out - can be enabled based on query patterns)
-- CREATE INDEX IF NOT EXISTS idx_embedding_hnsw 
-- ON lens_sem.embedding USING hnsw (embedding vector_cosine_ops)
-- WITH (m = 16, ef_construction = 64);

-- Performance indexes for semantic lens
CREATE INDEX idx_embedding_world_branch ON lens_sem.embedding (world_id, branch);
CREATE INDEX idx_embedding_entity_type ON lens_sem.embedding (world_id, branch, entity_type);
CREATE INDEX idx_embedding_model ON lens_sem.embedding (model_name, model_version);

-- Entity lookup for embedding queries
CREATE INDEX idx_embedding_entity_lookup ON lens_sem.embedding (entity_id, entity_type);

-- =============================================================================
-- GRAPH LENS (lens_graph)
-- =============================================================================

-- Create graph lens schema
CREATE SCHEMA IF NOT EXISTS lens_graph;

-- Projector state tracking for graph operations
CREATE TABLE lens_graph.projector_state (
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    last_processed_seq BIGINT NOT NULL,
    node_count BIGINT NOT NULL DEFAULT 0,
    edge_count BIGINT NOT NULL DEFAULT 0,
    graph_adapter TEXT NOT NULL DEFAULT 'age',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (world_id, branch)
);

-- Graph metadata for AGE graph management
CREATE TABLE lens_graph.graph_metadata (
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    graph_name TEXT NOT NULL, -- AGE graph name (e.g., g_550e8400_main)
    world_prefix TEXT NOT NULL, -- 8-char world_id prefix
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_rebuild_at TIMESTAMPTZ,
    node_types JSONB, -- Available node types in this graph
    edge_types JSONB, -- Available edge types in this graph
    PRIMARY KEY (world_id, branch),
    UNIQUE (graph_name)
);

-- Graph operation log for debugging and audit
CREATE TABLE lens_graph.operation_log (
    operation_id BIGSERIAL PRIMARY KEY,
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    operation_type TEXT NOT NULL, -- create_node, create_edge, delete_node, etc.
    cypher_query TEXT,
    parameters JSONB,
    execution_time_ms INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Performance indexes for graph lens
CREATE INDEX idx_projector_state_world_branch ON lens_graph.projector_state (world_id, branch);
CREATE INDEX idx_graph_metadata_world_prefix ON lens_graph.graph_metadata (world_prefix);
CREATE INDEX idx_operation_log_world_branch ON lens_graph.operation_log (world_id, branch, created_at DESC);
CREATE INDEX idx_operation_log_errors ON lens_graph.operation_log (success, created_at DESC) WHERE success = FALSE;

-- =============================================================================
-- MATERIALIZED VIEWS (MV DISCIPLINE)
-- =============================================================================

-- Enriched note view (projectors write base tables, MVs refreshed on schedule)
CREATE MATERIALIZED VIEW lens_rel.mv_note_enriched AS
SELECT 
    n.world_id,
    n.branch,
    n.note_id,
    n.title,
    n.body,
    n.created_at,
    n.updated_at,
    array_agg(DISTINCT nt.tag) FILTER (WHERE nt.tag IS NOT NULL) as tags,
    count(DISTINCT l.dst_id) as outgoing_links,
    count(DISTINCT l2.src_id) as incoming_links
FROM lens_rel.note n
LEFT JOIN lens_rel.note_tag nt ON (n.world_id, n.branch, n.note_id) = (nt.world_id, nt.branch, nt.note_id)
LEFT JOIN lens_rel.link l ON (n.world_id, n.branch, n.note_id) = (l.world_id, l.branch, l.src_id)
LEFT JOIN lens_rel.link l2 ON (n.world_id, n.branch, n.note_id) = (l2.world_id, l2.branch, l2.dst_id)
GROUP BY n.world_id, n.branch, n.note_id, n.title, n.body, n.created_at, n.updated_at;

-- Unique index on MV for fast lookups
CREATE UNIQUE INDEX idx_mv_note_enriched_pk 
ON lens_rel.mv_note_enriched (world_id, branch, note_id);

-- =============================================================================
-- LENS UTILITY FUNCTIONS
-- =============================================================================

-- Function to compute similarity between embeddings
CREATE OR REPLACE FUNCTION lens_sem.cosine_similarity(
    embedding1 VECTOR(768),
    embedding2 VECTOR(768)
) RETURNS FLOAT AS $$
BEGIN
    RETURN 1 - (embedding1 <=> embedding2); -- pgvector cosine distance -> similarity
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to find similar embeddings
CREATE OR REPLACE FUNCTION lens_sem.find_similar_embeddings(
    p_world_id UUID,
    p_branch TEXT,
    p_query_embedding VECTOR(768),
    p_entity_type TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 10,
    p_similarity_threshold FLOAT DEFAULT 0.7
) RETURNS TABLE (
    entity_id UUID,
    entity_type TEXT,
    similarity FLOAT,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.entity_id,
        e.entity_type,
        lens_sem.cosine_similarity(e.embedding, p_query_embedding) as similarity,
        e.metadata
    FROM lens_sem.embedding e
    WHERE e.world_id = p_world_id
    AND e.branch = p_branch
    AND (p_entity_type IS NULL OR e.entity_type = p_entity_type)
    AND lens_sem.cosine_similarity(e.embedding, p_query_embedding) >= p_similarity_threshold
    ORDER BY e.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to validate AGE graph name format
CREATE OR REPLACE FUNCTION lens_graph.validate_graph_name(graph_name TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    -- Must match: g_{8_alphanumeric}_{sanitized_branch}
    IF NOT graph_name ~ '^g_[a-z0-9]{8}_[a-z0-9_]{1,20}$' THEN
        RETURN FALSE;
    END IF;
    
    IF length(graph_name) > 63 THEN -- PostgreSQL identifier limit
        RETURN FALSE;
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to generate AGE graph name from world_id and branch
CREATE OR REPLACE FUNCTION lens_graph.generate_graph_name(
    p_world_id UUID,
    p_branch TEXT
) RETURNS TEXT AS $$
DECLARE
    world_prefix TEXT;
    sanitized_branch TEXT;
    graph_name TEXT;
BEGIN
    -- Extract first 8 chars of world_id (remove hyphens)
    world_prefix := substr(lower(replace(p_world_id::text, '-', '')), 1, 8);
    
    -- Sanitize branch name (alphanumeric + underscore only)
    sanitized_branch := lower(regexp_replace(p_branch, '[^a-z0-9_]', '_', 'g'));
    
    -- Truncate if too long
    IF length(sanitized_branch) > 20 THEN
        sanitized_branch := substr(sanitized_branch, 1, 20);
    END IF;
    
    -- Construct graph name
    graph_name := 'g_' || world_prefix || '_' || sanitized_branch;
    
    -- Validate result
    IF NOT lens_graph.validate_graph_name(graph_name) THEN
        RAISE EXCEPTION 'Generated invalid graph name: %', graph_name;
    END IF;
    
    RETURN graph_name;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================================================
-- ROW LEVEL SECURITY (RLS) PREPARATION
-- =============================================================================

-- Note: RLS policies will be defined in a later migration when multi-tenancy is fully active
-- For now, we set up the framework

-- Enable RLS on all lens tables (policies to be added later)
ALTER TABLE lens_rel.note ENABLE ROW LEVEL SECURITY;
ALTER TABLE lens_rel.note_tag ENABLE ROW LEVEL SECURITY;
ALTER TABLE lens_rel.link ENABLE ROW LEVEL SECURITY;
ALTER TABLE lens_sem.embedding ENABLE ROW LEVEL SECURITY;
ALTER TABLE lens_graph.projector_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE lens_graph.graph_metadata ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON SCHEMA lens_rel IS 'Relational lens: structured note data with tags and links';
COMMENT ON SCHEMA lens_sem IS 'Semantic lens: vector embeddings for similarity search';
COMMENT ON SCHEMA lens_graph IS 'Graph lens: AGE graph projection state and metadata';

COMMENT ON TABLE lens_rel.note IS 'Core note entities with world_id/branch tenancy';
COMMENT ON TABLE lens_rel.note_tag IS 'Note tagging with composite foreign keys';
COMMENT ON TABLE lens_rel.link IS 'Inter-note relationships with typed links';

COMMENT ON TABLE lens_sem.embedding IS 'Vector embeddings with pgvector for similarity search';
COMMENT ON COLUMN lens_sem.embedding.embedding IS 'Vector column (768 dimensions, cosine distance)';

COMMENT ON TABLE lens_graph.projector_state IS 'Graph projector state tracking per world/branch';
COMMENT ON TABLE lens_graph.graph_metadata IS 'AGE graph metadata and naming registry';

COMMENT ON MATERIALIZED VIEW lens_rel.mv_note_enriched IS 'Enriched note view (MV discipline - refresh on schedule)';

-- =============================================================================
-- VALIDATION
-- =============================================================================

-- Verify lens foundation schema creation
DO $$
BEGIN
    -- Check that all schemas exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'lens_rel') THEN
        RAISE EXCEPTION 'lens_rel schema creation failed';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'lens_sem') THEN
        RAISE EXCEPTION 'lens_sem schema creation failed';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'lens_graph') THEN
        RAISE EXCEPTION 'lens_graph schema creation failed';
    END IF;
    
    -- Check key tables exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'lens_rel' AND table_name = 'note'
    ) THEN
        RAISE EXCEPTION 'lens_rel.note table creation failed';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'lens_sem' AND table_name = 'embedding'
    ) THEN
        RAISE EXCEPTION 'lens_sem.embedding table creation failed';
    END IF;
    
    -- Check that vector extension is working
    BEGIN
        PERFORM '[1,2,3]'::vector(3);
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'pgvector extension not working properly';
    END;
    
    -- Check key functions exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.routines 
        WHERE routine_schema = 'lens_sem' AND routine_name = 'find_similar_embeddings'
    ) THEN
        RAISE EXCEPTION 'find_similar_embeddings function creation failed';
    END IF;
    
    RAISE NOTICE 'V2 Lens Foundation migration completed successfully';
    RAISE NOTICE 'Schemas created: lens_rel, lens_sem, lens_graph';
    RAISE NOTICE 'Tables created: note, note_tag, link, embedding, projector_state, graph_metadata';
    RAISE NOTICE 'Materialized views: mv_note_enriched (MV discipline)';
    RAISE NOTICE 'pgvector integration: vector operations functional';
    RAISE NOTICE 'RLS enabled: policies to be added in future migrations';
END
$$;
