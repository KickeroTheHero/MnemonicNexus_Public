-- MnemonicNexus Schema Migration: Event Core
-- Phase A2: Core event storage with comprehensive tenancy and idempotency
-- File: 001_event_core.sql
-- Dependencies: PostgreSQL 16+, uuid-ossp, pgcrypto extensions

-- =============================================================================
-- CORE EVENT SCHEMA
-- =============================================================================

-- Create event_core schema for system of record
CREATE SCHEMA IF NOT EXISTS event_core;

-- Core event log with enhanced tenancy and integrity
CREATE TABLE event_core.event_log (
    global_seq BIGSERIAL PRIMARY KEY,
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    event_id UUID NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    envelope JSONB NOT NULL,
    occurred_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    idempotency_key TEXT,
    payload_hash TEXT NOT NULL, -- SHA-256 of canonical envelope
    checksum TEXT
);

-- Partial unique index for idempotency (better performance than EXCLUDE)
CREATE UNIQUE INDEX IF NOT EXISTS uq_event_idem
ON event_core.event_log (world_id, branch, idempotency_key)
WHERE idempotency_key IS NOT NULL;

-- Fast idempotency lookup
CREATE INDEX idx_event_log_idempotency 
ON event_core.event_log (world_id, branch, idempotency_key) 
WHERE idempotency_key IS NOT NULL;

-- Performance index for filtered event reads
CREATE INDEX IF NOT EXISTS idx_event_log_filtered_reads
ON event_core.event_log (world_id, branch, kind, global_seq);

-- Tenant-scoped queries (primary access pattern)
CREATE INDEX IF NOT EXISTS idx_event_log_tenant_scoped
ON event_core.event_log (world_id, branch, global_seq);

-- Event ID lookup (for correlation and debugging)
CREATE INDEX IF NOT EXISTS idx_event_log_event_id
ON event_core.event_log (event_id);

-- =============================================================================
-- BRANCH REGISTRY
-- =============================================================================

-- Branch registry with tenancy for DVCS-lite operations
CREATE TABLE event_core.branches (
    world_id UUID NOT NULL,
    branch_name TEXT NOT NULL,
    parent_branch TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by_agent TEXT NOT NULL,
    metadata JSONB,
    PRIMARY KEY (world_id, branch_name)
);

-- Index for branch lineage queries
CREATE INDEX IF NOT EXISTS idx_branches_parent
ON event_core.branches (world_id, parent_branch);

-- =============================================================================
-- UTILITY FUNCTIONS
-- =============================================================================

-- Function to compute payload hash for integrity verification
CREATE OR REPLACE FUNCTION event_core.compute_payload_hash(envelope JSONB)
RETURNS TEXT AS $$
BEGIN
    -- Compute SHA-256 of canonical JSON representation
    -- Hash only the payload object to align with client-side hashing
    RETURN encode(digest((envelope->'payload')::text, 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to validate event envelope structure
CREATE OR REPLACE FUNCTION event_core.validate_envelope(envelope JSONB)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check required envelope fields
    IF NOT (envelope ? 'world_id' AND envelope ? 'branch' AND envelope ? 'kind' AND envelope ? 'payload' AND envelope ? 'by') THEN
        RETURN FALSE;
    END IF;
    
    -- Check by.agent field exists
    IF NOT (envelope->'by' ? 'agent') THEN
        RETURN FALSE;
    END IF;
    
    -- Validate UUID format for world_id
    BEGIN
        PERFORM (envelope->>'world_id')::UUID;
    EXCEPTION WHEN OTHERS THEN
        RETURN FALSE;
    END;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON SCHEMA event_core IS 'Event Core: System of Record with comprehensive tenancy';
COMMENT ON TABLE event_core.event_log IS 'Append-only event log with world_id tenancy and branch isolation';
COMMENT ON TABLE event_core.branches IS 'Branch registry for DVCS-lite operations with metadata';

COMMENT ON COLUMN event_core.event_log.global_seq IS 'Monotonic sequence for total event ordering';
COMMENT ON COLUMN event_core.event_log.world_id IS 'Tenancy UUID - required in all operations';
COMMENT ON COLUMN event_core.event_log.branch IS 'Branch name for DVCS-lite isolation';
COMMENT ON COLUMN event_core.event_log.event_id IS 'Unique event identifier for correlation';
COMMENT ON COLUMN event_core.event_log.envelope IS 'Complete event envelope with audit fields';
COMMENT ON COLUMN event_core.event_log.payload_hash IS 'SHA-256 integrity hash of canonical envelope';
COMMENT ON COLUMN event_core.event_log.idempotency_key IS 'Optional client idempotency key (from header)';

-- =============================================================================
-- VALIDATION
-- =============================================================================

-- Verify schema creation
DO $$
BEGIN
    -- Check that event_core schema exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'event_core') THEN
        RAISE EXCEPTION 'event_core schema creation failed';
    END IF;
    
    -- Check that event_log table exists with required columns
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'event_core' AND table_name = 'event_log'
    ) THEN
        RAISE EXCEPTION 'event_log table creation failed';
    END IF;
    
    -- Check that unique constraint exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE schemaname = 'event_core' 
        AND tablename = 'event_log' 
        AND indexname = 'uq_event_idem'
    ) THEN
        RAISE EXCEPTION 'idempotency unique index creation failed';
    END IF;
    
    RAISE NOTICE 'Event Core schema migration completed successfully';
    RAISE NOTICE 'Tables created: event_log, branches';
    RAISE NOTICE 'Indexes created: idempotency, performance, tenant-scoped';
    RAISE NOTICE 'Functions created: compute_payload_hash, validate_envelope';
END
$$;
