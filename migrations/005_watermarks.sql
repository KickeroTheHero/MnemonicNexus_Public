-- MnemonicNexus Schema Migration: Projector Watermarks
-- Phase A2: Shared watermark tracking and deterministic replay
-- File: 005_watermarks.sql
-- Dependencies: 001_event_core.sql

-- =============================================================================
-- PROJECTOR WATERMARK MANAGEMENT
-- =============================================================================

-- Shared watermark tracking across all projectors
CREATE TABLE event_core.projector_watermarks (
    projector_name TEXT NOT NULL,
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    last_processed_seq BIGINT NOT NULL,
    determinism_hash TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum TEXT, -- Projector-specific checksum for state verification
    metadata JSONB, -- Projector-specific metadata (e.g., performance stats)
    PRIMARY KEY (projector_name, world_id, branch)
);

-- Performance indexes for watermark queries
CREATE INDEX idx_watermarks_projector ON event_core.projector_watermarks (projector_name);
CREATE INDEX idx_watermarks_world_branch ON event_core.projector_watermarks (world_id, branch);
CREATE INDEX idx_watermarks_last_processed ON event_core.projector_watermarks (last_processed_seq);
CREATE INDEX idx_watermarks_updated_at ON event_core.projector_watermarks (updated_at DESC);

-- =============================================================================
-- DETERMINISM TRACKING
-- =============================================================================

-- Determinism hash computation log for replay validation
CREATE TABLE event_core.determinism_log (
    computation_id BIGSERIAL PRIMARY KEY,
    projector_name TEXT NOT NULL,
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    start_seq BIGINT NOT NULL,
    end_seq BIGINT NOT NULL,
    event_count INTEGER NOT NULL,
    determinism_hash TEXT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    computation_time_ms INTEGER
);

-- Indexes for determinism validation
CREATE INDEX idx_determinism_log_projector_range 
ON event_core.determinism_log (projector_name, world_id, branch, start_seq, end_seq);
CREATE INDEX idx_determinism_log_hash ON event_core.determinism_log (determinism_hash);

-- =============================================================================
-- WATERMARK MANAGEMENT FUNCTIONS
-- =============================================================================

-- Function to get current watermark for projector
CREATE OR REPLACE FUNCTION event_core.get_watermark(
    p_projector_name TEXT,
    p_world_id UUID,
    p_branch TEXT
) RETURNS BIGINT AS $$
DECLARE
    watermark BIGINT;
BEGIN
    SELECT last_processed_seq INTO watermark
    FROM event_core.projector_watermarks
    WHERE projector_name = p_projector_name
    AND world_id = p_world_id
    AND branch = p_branch;
    
    -- Return 0 if no watermark exists (start from beginning)
    RETURN COALESCE(watermark, 0);
END;
$$ LANGUAGE plpgsql;

-- Function to update watermark atomically
CREATE OR REPLACE FUNCTION event_core.update_watermark(
    p_projector_name TEXT,
    p_world_id UUID,
    p_branch TEXT,
    p_last_processed_seq BIGINT,
    p_determinism_hash TEXT DEFAULT NULL,
    p_checksum TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    updated_count INTEGER;
BEGIN
    -- Upsert watermark record
    INSERT INTO event_core.projector_watermarks (
        projector_name, world_id, branch, last_processed_seq,
        determinism_hash, checksum, metadata
    ) VALUES (
        p_projector_name, p_world_id, p_branch, p_last_processed_seq,
        p_determinism_hash, p_checksum, p_metadata
    )
    ON CONFLICT (projector_name, world_id, branch)
    DO UPDATE SET
        last_processed_seq = EXCLUDED.last_processed_seq,
        determinism_hash = COALESCE(EXCLUDED.determinism_hash, projector_watermarks.determinism_hash),
        checksum = COALESCE(EXCLUDED.checksum, projector_watermarks.checksum),
        metadata = COALESCE(EXCLUDED.metadata, projector_watermarks.metadata),
        updated_at = now()
    WHERE projector_watermarks.last_processed_seq < EXCLUDED.last_processed_seq; -- Only update if advancing
    
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count > 0;
END;
$$ LANGUAGE plpgsql;

-- Function to get events since last watermark
CREATE OR REPLACE FUNCTION event_core.get_events_since_watermark(
    p_projector_name TEXT,
    p_world_id UUID,
    p_branch TEXT,
    p_batch_size INTEGER DEFAULT 100
) RETURNS TABLE (
    global_seq BIGINT,
    world_id UUID,
    branch TEXT,
    event_id UUID,
    kind TEXT,
    envelope JSONB,
    occurred_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ,
    payload_hash TEXT
) AS $$
DECLARE
    current_watermark BIGINT;
BEGIN
    -- Get current watermark
    current_watermark := event_core.get_watermark(p_projector_name, p_world_id, p_branch);
    
    -- Return events after watermark
    RETURN QUERY
    SELECT 
        el.global_seq, el.world_id, el.branch, el.event_id, el.kind,
        el.envelope, el.occurred_at, el.received_at, el.payload_hash
    FROM event_core.event_log el
    WHERE el.world_id = p_world_id
    AND el.branch = p_branch
    AND el.global_seq > current_watermark
    ORDER BY el.global_seq
    LIMIT p_batch_size;
END;
$$ LANGUAGE plpgsql;

-- Function to compute determinism hash for event range
CREATE OR REPLACE FUNCTION event_core.compute_determinism_hash(
    p_projector_name TEXT,
    p_world_id UUID,
    p_branch TEXT,
    p_start_seq BIGINT,
    p_end_seq BIGINT
) RETURNS TEXT AS $$
DECLARE
    hash_input TEXT;
    determinism_hash TEXT;
    event_count INTEGER;
    start_time TIMESTAMP;
    execution_time_ms INTEGER;
BEGIN
    start_time := clock_timestamp();
    
    -- Build deterministic string from events in range
    SELECT 
        string_agg(
            el.global_seq || '|' || el.event_id || '|' || el.kind || '|' || el.payload_hash,
            E'\n' ORDER BY el.global_seq
        ),
        COUNT(*)
    INTO hash_input, event_count
    FROM event_core.event_log el
    WHERE el.world_id = p_world_id
    AND el.branch = p_branch
    AND el.global_seq >= p_start_seq
    AND el.global_seq <= p_end_seq;
    
    -- Compute SHA-256 hash
    determinism_hash := encode(digest(COALESCE(hash_input, ''), 'sha256'), 'hex');
    
    execution_time_ms := EXTRACT(MILLISECONDS FROM clock_timestamp() - start_time)::INTEGER;
    
    -- Log computation
    INSERT INTO event_core.determinism_log (
        projector_name, world_id, branch, start_seq, end_seq,
        event_count, determinism_hash, computation_time_ms
    ) VALUES (
        p_projector_name, p_world_id, p_branch, p_start_seq, p_end_seq,
        event_count, determinism_hash, execution_time_ms
    );
    
    RETURN determinism_hash;
END;
$$ LANGUAGE plpgsql;

-- Function to validate determinism by recomputing hash
CREATE OR REPLACE FUNCTION event_core.validate_determinism(
    p_projector_name TEXT,
    p_world_id UUID,
    p_branch TEXT,
    p_start_seq BIGINT,
    p_end_seq BIGINT,
    p_expected_hash TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    computed_hash TEXT;
BEGIN
    -- Recompute hash for the same range
    computed_hash := event_core.compute_determinism_hash(
        p_projector_name, p_world_id, p_branch, p_start_seq, p_end_seq
    );
    
    -- Compare with expected hash
    RETURN computed_hash = p_expected_hash;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- PROJECTOR STATE MANAGEMENT
-- =============================================================================

-- Function to reset projector state (for rebuilds)
CREATE OR REPLACE FUNCTION event_core.reset_projector(
    p_projector_name TEXT,
    p_world_id UUID,
    p_branch TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete watermark record
    DELETE FROM event_core.projector_watermarks
    WHERE projector_name = p_projector_name
    AND world_id = p_world_id
    AND branch = p_branch;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Also clean up determinism log for this projector
    DELETE FROM event_core.determinism_log
    WHERE projector_name = p_projector_name
    AND world_id = p_world_id
    AND branch = p_branch;
    
    RETURN deleted_count > 0;
END;
$$ LANGUAGE plpgsql;

-- Function to get projector status summary
CREATE OR REPLACE FUNCTION event_core.get_projector_status(
    p_world_id UUID,
    p_branch TEXT
) RETURNS TABLE (
    projector_name TEXT,
    last_processed_seq BIGINT,
    events_behind BIGINT,
    last_updated TIMESTAMPTZ,
    determinism_hash TEXT
) AS $$
DECLARE
    max_seq BIGINT;
BEGIN
    -- Get the latest event sequence for this world/branch
    SELECT COALESCE(MAX(global_seq), 0) INTO max_seq
    FROM event_core.event_log
    WHERE world_id = p_world_id AND branch = p_branch;
    
    -- Return projector status
    RETURN QUERY
    SELECT 
        pw.projector_name,
        pw.last_processed_seq,
        max_seq - pw.last_processed_seq as events_behind,
        pw.updated_at,
        pw.determinism_hash
    FROM event_core.projector_watermarks pw
    WHERE pw.world_id = p_world_id
    AND pw.branch = p_branch
    ORDER BY pw.projector_name;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- MONITORING VIEWS
-- =============================================================================

-- View for projector lag monitoring
CREATE VIEW event_core.projector_lag AS
SELECT 
    pw.projector_name,
    pw.world_id,
    pw.branch,
    pw.last_processed_seq,
    COALESCE(el_max.max_seq, 0) as latest_event_seq,
    COALESCE(el_max.max_seq, 0) - pw.last_processed_seq as events_behind,
    pw.updated_at,
    now() - pw.updated_at as time_since_update
FROM event_core.projector_watermarks pw
LEFT JOIN (
    SELECT 
        world_id,
        branch,
        MAX(global_seq) as max_seq
    FROM event_core.event_log
    GROUP BY world_id, branch
) el_max ON pw.world_id = el_max.world_id AND pw.branch = el_max.branch;

-- View for determinism tracking
CREATE VIEW event_core.determinism_summary AS
SELECT 
    projector_name,
    world_id,
    branch,
    COUNT(*) as computation_count,
    MIN(computed_at) as first_computation,
    MAX(computed_at) as last_computation,
    AVG(computation_time_ms) as avg_computation_time_ms,
    COUNT(DISTINCT determinism_hash) as unique_hashes
FROM event_core.determinism_log
GROUP BY projector_name, world_id, branch;

-- =============================================================================
-- WATERMARK UTILITIES
-- =============================================================================

-- Function to cleanup old determinism log entries
CREATE OR REPLACE FUNCTION event_core.cleanup_determinism_log(
    p_retention_days INTEGER DEFAULT 30
) RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM event_core.determinism_log
    WHERE computed_at < now() - (p_retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get watermark statistics
CREATE OR REPLACE FUNCTION event_core.get_watermark_stats()
RETURNS JSONB AS $$
DECLARE
    stats JSONB;
BEGIN
    SELECT jsonb_build_object(
        'total_projectors', COUNT(*),
        'active_worlds', COUNT(DISTINCT world_id),
        'active_branches', COUNT(DISTINCT (world_id, branch)),
        'avg_events_behind', AVG(COALESCE(latest_event_seq, 0) - last_processed_seq),
        'max_events_behind', MAX(COALESCE(latest_event_seq, 0) - last_processed_seq),
        'oldest_update', MIN(updated_at),
        'newest_update', MAX(updated_at)
    ) INTO stats
    FROM event_core.projector_lag;
    
    RETURN stats;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE event_core.projector_watermarks IS 'Shared watermark tracking for all projectors with determinism validation';
COMMENT ON TABLE event_core.determinism_log IS 'Log of determinism hash computations for replay validation';

COMMENT ON COLUMN event_core.projector_watermarks.determinism_hash IS 'Hash of processed event range for deterministic replay validation';
COMMENT ON COLUMN event_core.projector_watermarks.checksum IS 'Projector-specific state checksum for integrity verification';

COMMENT ON FUNCTION event_core.compute_determinism_hash IS 'Compute deterministic hash for event range to validate replay consistency';
COMMENT ON FUNCTION event_core.get_events_since_watermark IS 'Get batch of events since last processed watermark for projector';

COMMENT ON VIEW event_core.projector_lag IS 'Monitor projector lag and processing delays';
COMMENT ON VIEW event_core.determinism_summary IS 'Summary of determinism hash computations per projector';

-- =============================================================================
-- VALIDATION
-- =============================================================================

-- Verify watermark schema creation
DO $$
DECLARE
    test_projector TEXT := 'test_projector';
    test_world_id UUID := '550e8400-e29b-41d4-a716-446655440000';
    test_branch TEXT := 'main';
    watermark_value BIGINT;
    update_success BOOLEAN;
    hash_result TEXT;
BEGIN
    -- Check that watermarks table exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'event_core' AND table_name = 'projector_watermarks'
    ) THEN
        RAISE EXCEPTION 'projector_watermarks table creation failed';
    END IF;
    
    -- Check that determinism_log table exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'event_core' AND table_name = 'determinism_log'
    ) THEN
        RAISE EXCEPTION 'determinism_log table creation failed';
    END IF;
    
    -- Test watermark functions
    watermark_value := event_core.get_watermark(test_projector, test_world_id, test_branch);
    IF watermark_value != 0 THEN
        RAISE EXCEPTION 'Initial watermark should be 0, got %', watermark_value;
    END IF;
    
    -- Test watermark update
    update_success := event_core.update_watermark(
        test_projector, test_world_id, test_branch, 100, 'test-hash'
    );
    IF NOT update_success THEN
        RAISE EXCEPTION 'Watermark update failed';
    END IF;
    
    -- Test determinism hash computation
    hash_result := event_core.compute_determinism_hash(
        test_projector, test_world_id, test_branch, 1, 100
    );
    IF hash_result IS NULL OR length(hash_result) != 64 THEN
        RAISE EXCEPTION 'Determinism hash computation failed';
    END IF;
    
    -- Cleanup test data
    PERFORM event_core.reset_projector(test_projector, test_world_id, test_branch);
    
    -- Check that monitoring views work
    PERFORM * FROM event_core.projector_lag LIMIT 1;
    PERFORM * FROM event_core.determinism_summary LIMIT 1;
    
    RAISE NOTICE 'Projector Watermarks migration completed successfully';
    RAISE NOTICE 'Tables created: projector_watermarks, determinism_log';
    RAISE NOTICE 'Functions created: watermark management, determinism validation';
    RAISE NOTICE 'Monitoring views: projector_lag, determinism_summary';
    RAISE NOTICE 'Watermark functions tested and validated';
END
$$;
