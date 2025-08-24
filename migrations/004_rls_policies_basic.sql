-- Migration: 004_rls_policies_basic.sql
-- Purpose: Implement Row Level Security policies for existing tables only
-- Phase: A (Critical Security)
-- Date: 2025-01-20
--
-- ⚠️  PLANNED OBSOLESCENCE WARNING ⚠️
-- This migration applies RLS policies only to existing tables.
-- Will be replaced by comprehensive 004_rls_policies.sql when
-- semantic and graph lens schemas are complete (Phase B1).
-- 
-- Replacement triggers:
-- - All lens schemas (rel, sem, graph) are implemented
-- - Comprehensive schema validation is available
-- - Production deployment preparation begins

BEGIN;

-- ============================================================================
-- ROW LEVEL SECURITY POLICIES FOR EXISTING TABLES
-- ============================================================================

-- Check which tables exist and have RLS enabled
DO $$
DECLARE
    table_exists BOOLEAN;
BEGIN
    -- Policy for lens_rel.note
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'lens_rel' AND table_name = 'note'
    ) INTO table_exists;
    
    IF table_exists THEN
        CREATE POLICY world_isolation_note ON lens_rel.note
            FOR ALL TO PUBLIC
            USING (world_id = current_setting('app.current_world_id', true)::UUID);
        RAISE NOTICE 'Created RLS policy for lens_rel.note';
    END IF;

    -- Policy for lens_rel.note_tag
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'lens_rel' AND table_name = 'note_tag'
    ) INTO table_exists;
    
    IF table_exists THEN
        CREATE POLICY world_isolation_note_tag ON lens_rel.note_tag
            FOR ALL TO PUBLIC
            USING (world_id = current_setting('app.current_world_id', true)::UUID);
        RAISE NOTICE 'Created RLS policy for lens_rel.note_tag';
    END IF;

    -- Policy for lens_rel.link
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'lens_rel' AND table_name = 'link'
    ) INTO table_exists;
    
    IF table_exists THEN
        CREATE POLICY world_isolation_link ON lens_rel.link
            FOR ALL TO PUBLIC
            USING (world_id = current_setting('app.current_world_id', true)::UUID);
        RAISE NOTICE 'Created RLS policy for lens_rel.link';
    END IF;

    -- Policy for event_core.event_log
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'event_core' AND table_name = 'event_log'
    ) INTO table_exists;
    
    IF table_exists THEN
        CREATE POLICY world_isolation_event_log ON event_core.event_log
            FOR ALL TO PUBLIC
            USING (world_id = current_setting('app.current_world_id', true)::UUID);
        RAISE NOTICE 'Created RLS policy for event_core.event_log';
    END IF;

    -- Policy for event_core.outbox
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'event_core' AND table_name = 'outbox'
    ) INTO table_exists;
    
    IF table_exists THEN
        CREATE POLICY world_isolation_outbox ON event_core.outbox
            FOR ALL TO PUBLIC
            USING (world_id = current_setting('app.current_world_id', true)::UUID);
        RAISE NOTICE 'Created RLS policy for event_core.outbox';
    END IF;

    -- Policy for event_core.projector_watermarks
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'event_core' AND table_name = 'projector_watermarks'
    ) INTO table_exists;
    
    IF table_exists THEN
        CREATE POLICY world_isolation_projector_watermarks ON event_core.projector_watermarks
            FOR ALL TO PUBLIC
            USING (world_id = current_setting('app.current_world_id', true)::UUID);
        RAISE NOTICE 'Created RLS policy for event_core.projector_watermarks';
    END IF;
END $$;

-- ============================================================================
-- TENANCY FUNCTIONS
-- ============================================================================

-- Function to set world_id context (for use by applications)
CREATE OR REPLACE FUNCTION set_current_world_id(world_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Validate input
    IF world_id IS NULL THEN
        RAISE EXCEPTION 'world_id cannot be NULL';
    END IF;
    
    -- Set the session variable
    PERFORM set_config('app.current_world_id', world_id::TEXT, false);
    
    RAISE DEBUG 'Set current_world_id to: %', world_id;
END;
$$;

-- Function to validate current world_id setting
CREATE OR REPLACE FUNCTION validate_world_id_setting()
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
BEGIN
    -- Check if app.current_world_id is set and valid UUID
    BEGIN
        PERFORM current_setting('app.current_world_id', true)::UUID;
        RETURN TRUE;
    EXCEPTION 
        WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'app.current_world_id must be a valid UUID';
        WHEN OTHERS THEN
            RAISE EXCEPTION 'app.current_world_id must be set for tenant isolation';
    END;
END;
$$;

-- ============================================================================
-- VALIDATION
-- ============================================================================

DO $$
DECLARE
    policy_count INTEGER;
BEGIN
    -- Count RLS policies created
    SELECT COUNT(*) INTO policy_count
    FROM pg_policies 
    WHERE policyname LIKE 'world_isolation_%';
    
    RAISE NOTICE 'SUCCESS: Created % RLS policies for tenant isolation', policy_count;
    RAISE NOTICE 'RLS policies implementation complete for existing tables';
END $$;

COMMIT;
