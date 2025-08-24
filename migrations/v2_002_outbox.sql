-- MnemonicNexus V2 Schema Migration: Transactional Outbox
-- Phase A2: Reliable CDC without external message broker
-- File: v2_002_outbox.sql
-- Dependencies: v2_001_event_core.sql

-- =============================================================================
-- TRANSACTIONAL OUTBOX PATTERN
-- =============================================================================

-- CDC outbox for reliable event publishing
CREATE TABLE event_core.outbox (
    global_seq BIGINT PRIMARY KEY REFERENCES event_core.event_log(global_seq),
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    event_id UUID NOT NULL,
    envelope JSONB NOT NULL,
    payload_hash TEXT NOT NULL, -- Integrity check vs event_log
    published_at TIMESTAMPTZ,
    processing_attempts INTEGER DEFAULT 0,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ
);

-- Publisher performance indexes
CREATE INDEX idx_outbox_unpublished ON event_core.outbox (world_id, branch) 
WHERE published_at IS NULL;

CREATE INDEX idx_outbox_retry ON event_core.outbox (next_retry_at) 
WHERE published_at IS NULL AND next_retry_at IS NOT NULL;

-- Global processing order index
CREATE INDEX idx_outbox_processing_order ON event_core.outbox (global_seq)
WHERE published_at IS NULL;

-- =============================================================================
-- DEAD LETTER QUEUE
-- =============================================================================

-- Dead Letter Queue for poison/failed events
CREATE TABLE event_core.dead_letter_queue (
    original_global_seq BIGINT PRIMARY KEY,
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    event_id UUID NOT NULL,
    envelope JSONB NOT NULL,
    error_reason TEXT NOT NULL,
    failed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retry_attempts INT NOT NULL DEFAULT 0,
    last_retry_at TIMESTAMPTZ,
    poisoned_by TEXT -- Publisher instance that marked as poison
);

-- DLQ analysis indexes
CREATE INDEX idx_dlq_world_branch ON event_core.dead_letter_queue (world_id, branch);
CREATE INDEX idx_dlq_failed_at ON event_core.dead_letter_queue (failed_at);
CREATE INDEX idx_dlq_error_pattern ON event_core.dead_letter_queue 
USING gin (to_tsvector('english', error_reason));

-- =============================================================================
-- OUTBOX MANAGEMENT FUNCTIONS
-- =============================================================================

-- Function to insert event into both event_log and outbox atomically
CREATE OR REPLACE FUNCTION event_core.insert_event_with_outbox(
    p_world_id UUID,
    p_branch TEXT,
    p_event_id UUID,
    p_kind TEXT,
    p_envelope JSONB,
    p_occurred_at TIMESTAMPTZ DEFAULT NULL,
    p_idempotency_key TEXT DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    v_global_seq BIGINT;
    v_payload_hash TEXT;
BEGIN
    -- Validate envelope structure
    IF NOT event_core.validate_envelope(p_envelope) THEN
        RAISE EXCEPTION 'Invalid event envelope structure';
    END IF;
    
    -- Compute payload hash
    v_payload_hash := event_core.compute_payload_hash(p_envelope);
    
    -- Insert into event_log
    INSERT INTO event_core.event_log (
        world_id, branch, event_id, kind, envelope, 
        occurred_at, idempotency_key, payload_hash
    ) VALUES (
        p_world_id, p_branch, p_event_id, p_kind, p_envelope,
        p_occurred_at, p_idempotency_key, v_payload_hash
    ) RETURNING global_seq INTO v_global_seq;
    
    -- Insert into outbox for CDC
    INSERT INTO event_core.outbox (
        global_seq, world_id, branch, event_id, envelope, payload_hash
    ) VALUES (
        v_global_seq, p_world_id, p_branch, p_event_id, p_envelope, v_payload_hash
    );
    
    RETURN v_global_seq;
END;
$$ LANGUAGE plpgsql;

-- Function to mark event as published
CREATE OR REPLACE FUNCTION event_core.mark_published(p_global_seq BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
    v_updated_count INTEGER;
BEGIN
    UPDATE event_core.outbox 
    SET published_at = now(),
        processing_attempts = processing_attempts + 1,
        last_error = NULL,
        next_retry_at = NULL
    WHERE global_seq = p_global_seq 
    AND published_at IS NULL;
    
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    RETURN v_updated_count > 0;
END;
$$ LANGUAGE plpgsql;

-- Function to mark event for retry
CREATE OR REPLACE FUNCTION event_core.mark_retry(
    p_global_seq BIGINT,
    p_error_message TEXT,
    p_retry_delay_seconds INTEGER DEFAULT 60
) RETURNS BOOLEAN AS $$
DECLARE
    v_updated_count INTEGER;
    v_next_retry TIMESTAMPTZ;
BEGIN
    -- Exponential backoff: base_delay * (2 ^ attempts)
    SELECT now() + (p_retry_delay_seconds * power(2, LEAST(processing_attempts, 10))) * INTERVAL '1 second'
    INTO v_next_retry
    FROM event_core.outbox 
    WHERE global_seq = p_global_seq;
    
    UPDATE event_core.outbox
    SET processing_attempts = processing_attempts + 1,
        last_error = p_error_message,
        next_retry_at = v_next_retry
    WHERE global_seq = p_global_seq
    AND published_at IS NULL;
    
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    RETURN v_updated_count > 0;
END;
$$ LANGUAGE plpgsql;

-- Function to move event to dead letter queue
CREATE OR REPLACE FUNCTION event_core.move_to_dlq(
    p_global_seq BIGINT,
    p_error_reason TEXT,
    p_poisoned_by TEXT DEFAULT 'unknown'
) RETURNS BOOLEAN AS $$
DECLARE
    v_event_record RECORD;
    v_moved_count INTEGER;
BEGIN
    -- Get event details from outbox
    SELECT global_seq, world_id, branch, event_id, envelope, processing_attempts
    INTO v_event_record
    FROM event_core.outbox
    WHERE global_seq = p_global_seq;
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Insert into DLQ
    INSERT INTO event_core.dead_letter_queue (
        original_global_seq, world_id, branch, event_id, envelope,
        error_reason, retry_attempts, poisoned_by
    ) VALUES (
        v_event_record.global_seq, v_event_record.world_id, v_event_record.branch,
        v_event_record.event_id, v_event_record.envelope,
        p_error_reason, v_event_record.processing_attempts, p_poisoned_by
    );
    
    -- Remove from outbox
    DELETE FROM event_core.outbox WHERE global_seq = p_global_seq;
    
    GET DIAGNOSTICS v_moved_count = ROW_COUNT;
    RETURN v_moved_count > 0;
END;
$$ LANGUAGE plpgsql;

-- Function to get next batch of unpublished events
CREATE OR REPLACE FUNCTION event_core.get_unpublished_batch(
    p_batch_size INTEGER DEFAULT 100,
    p_world_id UUID DEFAULT NULL,
    p_branch TEXT DEFAULT NULL
) RETURNS TABLE (
    global_seq BIGINT,
    world_id UUID,
    branch TEXT,
    event_id UUID,
    envelope JSONB,
    processing_attempts INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT o.global_seq, o.world_id, o.branch, o.event_id, o.envelope, o.processing_attempts
    FROM event_core.outbox o
    WHERE o.published_at IS NULL
    AND (o.next_retry_at IS NULL OR o.next_retry_at <= now())
    AND (p_world_id IS NULL OR o.world_id = p_world_id)
    AND (p_branch IS NULL OR o.branch = p_branch)
    ORDER BY o.global_seq
    LIMIT p_batch_size
    FOR UPDATE SKIP LOCKED;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- METRICS AND MONITORING
-- =============================================================================

-- View for outbox monitoring
CREATE VIEW event_core.outbox_metrics AS
SELECT 
    world_id,
    branch,
    COUNT(*) FILTER (WHERE published_at IS NULL) as pending_count,
    COUNT(*) FILTER (WHERE published_at IS NOT NULL) as published_count,
    AVG(processing_attempts) FILTER (WHERE published_at IS NULL) as avg_retry_attempts,
    MAX(processing_attempts) FILTER (WHERE published_at IS NULL) as max_retry_attempts,
    COUNT(*) FILTER (WHERE next_retry_at IS NOT NULL AND next_retry_at > now()) as scheduled_retries
FROM event_core.outbox
GROUP BY world_id, branch;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE event_core.outbox IS 'Transactional outbox for reliable CDC without external broker';
COMMENT ON TABLE event_core.dead_letter_queue IS 'Dead letter queue for poison or persistently failing events';

COMMENT ON COLUMN event_core.outbox.payload_hash IS 'Integrity verification against event_log.payload_hash';
COMMENT ON COLUMN event_core.outbox.processing_attempts IS 'Retry counter for failed publishing attempts';
COMMENT ON COLUMN event_core.outbox.next_retry_at IS 'Scheduled retry time with exponential backoff';

COMMENT ON FUNCTION event_core.insert_event_with_outbox IS 'Atomically insert event into log and outbox';
COMMENT ON FUNCTION event_core.get_unpublished_batch IS 'Get next batch of events for publisher (with row locking)';

-- =============================================================================
-- VALIDATION
-- =============================================================================

-- Verify outbox schema creation
DO $$
BEGIN
    -- Check that outbox table exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'event_core' AND table_name = 'outbox'
    ) THEN
        RAISE EXCEPTION 'outbox table creation failed';
    END IF;
    
    -- Check that DLQ table exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'event_core' AND table_name = 'dead_letter_queue'
    ) THEN
        RAISE EXCEPTION 'dead_letter_queue table creation failed';
    END IF;
    
    -- Check that key functions exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.routines 
        WHERE routine_schema = 'event_core' AND routine_name = 'insert_event_with_outbox'
    ) THEN
        RAISE EXCEPTION 'insert_event_with_outbox function creation failed';
    END IF;
    
    RAISE NOTICE 'V2 Transactional Outbox migration completed successfully';
    RAISE NOTICE 'Tables created: outbox, dead_letter_queue';
    RAISE NOTICE 'Functions created: insert_event_with_outbox, mark_published, mark_retry, move_to_dlq';
    RAISE NOTICE 'Monitoring: outbox_metrics view available';
END
$$;
