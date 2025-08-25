-- MnemonicNexus Schema Migration: EMO Base Tables
-- EMO (Episodic Memory Object) foundation for Alpha Base
-- File: 010_emo_tables.sql
-- Dependencies: 001_event_core.sql, PostgreSQL 16+, pgvector extension

-- =============================================================================
-- EMO SCHEMA CREATION
-- =============================================================================

-- Create schema for EMO lens data
CREATE SCHEMA IF NOT EXISTS lens_emo;

-- =============================================================================
-- EMO CURRENT STATE TABLE
-- =============================================================================

-- Primary EMO current state table - one row per EMO with latest version
CREATE TABLE lens_emo.emo_current (
    emo_id UUID NOT NULL,
    emo_type TEXT NOT NULL CHECK (emo_type IN ('note', 'fact', 'doc', 'artifact', 'profile')),
    emo_version INTEGER NOT NULL CHECK (emo_version >= 1),
    tenant_id UUID NOT NULL,
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'text/markdown',
    content TEXT,
    tags TEXT[] DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    deletion_reason TEXT,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('user', 'agent', 'ingest')),
    source_uri TEXT,
    content_hash TEXT, -- SHA-256 of content for integrity
    PRIMARY KEY (emo_id),
    UNIQUE (emo_id, world_id, branch),
    CHECK ((deleted = FALSE AND deleted_at IS NULL) OR (deleted = TRUE AND deleted_at IS NOT NULL))
);

-- Indexes for EMO current state
CREATE INDEX idx_emo_current_tenant_branch ON lens_emo.emo_current (tenant_id, world_id, branch);
CREATE INDEX idx_emo_current_type ON lens_emo.emo_current (world_id, branch, emo_type) WHERE NOT deleted;
CREATE INDEX idx_emo_current_tags ON lens_emo.emo_current USING GIN (tags) WHERE NOT deleted;
CREATE INDEX idx_emo_current_updated ON lens_emo.emo_current (world_id, branch, updated_at DESC);

-- =============================================================================
-- EMO VERSION HISTORY TABLE
-- =============================================================================

-- EMO version history for audit and lineage tracking  
CREATE TABLE lens_emo.emo_history (
    change_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    emo_id UUID NOT NULL,
    emo_version INTEGER NOT NULL CHECK (emo_version >= 1),
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    operation_type TEXT NOT NULL CHECK (operation_type IN ('created', 'updated', 'linked', 'deleted')),
    diff JSONB,
    content_hash TEXT NOT NULL, -- SHA-256 of content
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    idempotency_key TEXT,
    UNIQUE (emo_id, emo_version, world_id, branch),
    FOREIGN KEY (emo_id) REFERENCES lens_emo.emo_current(emo_id) ON DELETE CASCADE
);

-- Indexes for EMO history
CREATE INDEX idx_emo_history_id ON lens_emo.emo_history (emo_id, world_id, branch);
CREATE INDEX idx_emo_history_updated ON lens_emo.emo_history (world_id, branch, updated_at DESC);
CREATE UNIQUE INDEX idx_emo_history_idempotency ON lens_emo.emo_history (idempotency_key) WHERE idempotency_key IS NOT NULL;

-- =============================================================================
-- EMO LINKS TABLE
-- =============================================================================

-- EMO relationships and external links
CREATE TABLE lens_emo.emo_links (
    link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    emo_id UUID NOT NULL,
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    rel TEXT NOT NULL CHECK (rel IN ('derived', 'supersedes', 'merges')),
    target_emo_id UUID,
    target_uri TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((target_emo_id IS NOT NULL) != (target_uri IS NOT NULL)), -- XOR constraint
    FOREIGN KEY (emo_id) REFERENCES lens_emo.emo_current(emo_id) ON DELETE CASCADE,
    FOREIGN KEY (target_emo_id) REFERENCES lens_emo.emo_current(emo_id) ON DELETE CASCADE,
    UNIQUE (emo_id, world_id, branch, rel, COALESCE(target_emo_id::text, target_uri))
);

-- Indexes for EMO links
CREATE INDEX idx_emo_links_source ON lens_emo.emo_links (emo_id, world_id, branch);
CREATE INDEX idx_emo_links_target_emo ON lens_emo.emo_links (target_emo_id, world_id, branch) WHERE target_emo_id IS NOT NULL;
CREATE INDEX idx_emo_links_lineage ON lens_emo.emo_links (world_id, branch, rel) WHERE target_emo_id IS NOT NULL;

-- =============================================================================
-- EMO EMBEDDINGS TABLE
-- =============================================================================

-- EMO vector embeddings for semantic search
CREATE TABLE lens_emo.emo_embeddings (
    embedding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    emo_id UUID NOT NULL,
    emo_version INTEGER NOT NULL CHECK (emo_version >= 1),
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    model_id TEXT NOT NULL,
    embed_dim INTEGER NOT NULL CHECK (embed_dim > 0),
    embedding_vector vector, -- pgvector type
    model_version TEXT,
    template_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (emo_id) REFERENCES lens_emo.emo_current(emo_id) ON DELETE CASCADE,
    UNIQUE (emo_id, emo_version, world_id, branch, model_id)
);

-- Indexes for EMO embeddings - optimized for vector similarity search
CREATE INDEX idx_emo_embeddings_current ON lens_emo.emo_embeddings (emo_id, world_id, branch, model_id);
CREATE INDEX idx_emo_embeddings_vector_hnsw ON lens_emo.emo_embeddings 
USING hnsw (embedding_vector vector_cosine_ops) WHERE embedding_vector IS NOT NULL;

-- =============================================================================
-- EMO UTILITY FUNCTIONS
-- =============================================================================

-- Function to compute content hash for EMO content
CREATE OR REPLACE FUNCTION lens_emo.compute_content_hash(content TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN encode(digest(COALESCE(content, ''), 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to get current EMO version
CREATE OR REPLACE FUNCTION lens_emo.get_current_version(p_emo_id UUID, p_world_id UUID, p_branch TEXT)
RETURNS INTEGER AS $$
DECLARE
    current_version INTEGER;
BEGIN
    SELECT emo_version INTO current_version
    FROM lens_emo.emo_current
    WHERE emo_id = p_emo_id AND world_id = p_world_id AND branch = p_branch;
    
    RETURN COALESCE(current_version, 0);
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to check if EMO exists and is not deleted
CREATE OR REPLACE FUNCTION lens_emo.emo_exists(p_emo_id UUID, p_world_id UUID, p_branch TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM lens_emo.emo_current
        WHERE emo_id = p_emo_id 
        AND world_id = p_world_id 
        AND branch = p_branch 
        AND NOT deleted
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- =============================================================================
-- EMO MATERIALIZED VIEWS FOR PERFORMANCE
-- =============================================================================

-- Materialized view for active EMOs with full metadata
CREATE MATERIALIZED VIEW lens_emo.emo_active AS
SELECT 
    ec.emo_id,
    ec.emo_type,
    ec.emo_version,
    ec.tenant_id,
    ec.world_id,
    ec.branch,
    ec.mime_type,
    ec.content,
    ec.tags,
    ec.updated_at,
    ec.source_kind,
    ec.source_uri,
    ec.content_hash,
    -- Aggregate links
    COALESCE(
        json_agg(
            json_build_object(
                'rel', el.rel,
                'target_emo_id', el.target_emo_id,
                'target_uri', el.target_uri
            )
        ) FILTER (WHERE el.link_id IS NOT NULL), 
        '[]'::json
    ) AS links
FROM lens_emo.emo_current ec
LEFT JOIN lens_emo.emo_links el ON (
    ec.emo_id = el.emo_id 
    AND ec.world_id = el.world_id 
    AND ec.branch = el.branch
)
WHERE NOT ec.deleted
GROUP BY 
    ec.emo_id, ec.emo_type, ec.emo_version, ec.tenant_id,
    ec.world_id, ec.branch, ec.mime_type, ec.content,
    ec.tags, ec.updated_at, ec.source_kind, ec.source_uri, ec.content_hash;

-- Indexes on materialized view
CREATE INDEX idx_emo_active_tenant_branch ON lens_emo.emo_active (tenant_id, world_id, branch);
CREATE INDEX idx_emo_active_type ON lens_emo.emo_active (world_id, branch, emo_type);
CREATE INDEX idx_emo_active_updated ON lens_emo.emo_active (world_id, branch, updated_at DESC);

-- =============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =============================================================================

-- Enable RLS on all EMO tables
ALTER TABLE lens_emo.emo_current ENABLE ROW LEVEL SECURITY;
ALTER TABLE lens_emo.emo_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE lens_emo.emo_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE lens_emo.emo_embeddings ENABLE ROW LEVEL SECURITY;

-- Basic tenant isolation policy for emo_current
CREATE POLICY tenant_isolation_emo_current ON lens_emo.emo_current
FOR ALL TO PUBLIC
USING (tenant_id = COALESCE(current_setting('app.tenant_id', true)::uuid, tenant_id));

-- Basic tenant isolation policy for emo_history  
CREATE POLICY tenant_isolation_emo_history ON lens_emo.emo_history
FOR ALL TO PUBLIC
USING (world_id = COALESCE(current_setting('app.world_id', true)::uuid, world_id));

-- Basic tenant isolation policy for emo_links
CREATE POLICY tenant_isolation_emo_links ON lens_emo.emo_links
FOR ALL TO PUBLIC
USING (world_id = COALESCE(current_setting('app.world_id', true)::uuid, world_id));

-- Basic tenant isolation policy for emo_embeddings
CREATE POLICY tenant_isolation_emo_embeddings ON lens_emo.emo_embeddings
FOR ALL TO PUBLIC
USING (world_id = COALESCE(current_setting('app.world_id', true)::uuid, world_id));

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON SCHEMA lens_emo IS 'EMO (Episodic Memory Object) lens data with identity, versioning, and lineage';
COMMENT ON TABLE lens_emo.emo_current IS 'Current state of all EMOs - one row per EMO with latest version';
COMMENT ON TABLE lens_emo.emo_history IS 'Version history and audit trail for EMO changes';
COMMENT ON TABLE lens_emo.emo_links IS 'EMO relationships and external links for lineage tracking';
COMMENT ON TABLE lens_emo.emo_embeddings IS 'Vector embeddings for EMO semantic search operations';
COMMENT ON MATERIALIZED VIEW lens_emo.emo_active IS 'Optimized view of active EMOs with aggregated links';

COMMENT ON COLUMN lens_emo.emo_current.emo_id IS 'Unique EMO identifier (UUID)';
COMMENT ON COLUMN lens_emo.emo_current.emo_version IS 'Current version number, increments on updates';
COMMENT ON COLUMN lens_emo.emo_current.deleted IS 'Soft delete flag - when true, EMO is tombstoned';
COMMENT ON COLUMN lens_emo.emo_history.content_hash IS 'SHA-256 hash of content for integrity verification';
COMMENT ON COLUMN lens_emo.emo_embeddings.embedding_vector IS 'pgvector embedding for semantic similarity search';

-- =============================================================================
-- VALIDATION
-- =============================================================================

-- Verify schema creation
DO $$
BEGIN
    -- Check that lens_emo schema exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'lens_emo') THEN
        RAISE EXCEPTION 'lens_emo schema creation failed';
    END IF;
    
    -- Check that all required tables exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'lens_emo' AND table_name = 'emo_current') THEN
        RAISE EXCEPTION 'emo_current table creation failed';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'lens_emo' AND table_name = 'emo_history') THEN
        RAISE EXCEPTION 'emo_history table creation failed';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'lens_emo' AND table_name = 'emo_links') THEN
        RAISE EXCEPTION 'emo_links table creation failed';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'lens_emo' AND table_name = 'emo_embeddings') THEN
        RAISE EXCEPTION 'emo_embeddings table creation failed';
    END IF;
    
    -- Check that materialized view exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.views WHERE table_schema = 'lens_emo' AND table_name = 'emo_active') THEN
        RAISE EXCEPTION 'emo_active materialized view creation failed';
    END IF;
    
    RAISE NOTICE 'EMO Tables migration completed successfully';
    RAISE NOTICE 'Tables created: emo_current, emo_history, emo_links, emo_embeddings';
    RAISE NOTICE 'Materialized view created: emo_active';
    RAISE NOTICE 'Functions created: compute_content_hash, get_current_version, emo_exists';
    RAISE NOTICE 'RLS policies applied for tenant isolation';
END
$$;
