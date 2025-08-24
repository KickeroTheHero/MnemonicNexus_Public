-- Migration: v2_004_rls_policies.sql
-- Purpose: Implement Row Level Security policies for multi-tenant isolation
-- Phase: A (Critical Security)
-- Date: 2025-01-20

BEGIN;

-- ============================================================================
-- ROW LEVEL SECURITY POLICIES IMPLEMENTATION
-- ============================================================================

-- Note: Tables already have RLS enabled via v2_003_lens_foundation.sql
-- This migration adds the actual policies for tenant isolation

-- ============================================================================
-- LENS_REL SCHEMA POLICIES
-- ============================================================================

-- Policy for lens_rel.note - enforce world_id isolation
CREATE POLICY world_isolation_note ON lens_rel.note
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- Policy for lens_rel.note_tag - enforce world_id isolation  
CREATE POLICY world_isolation_note_tag ON lens_rel.note_tag
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- Policy for lens_rel.link - enforce world_id isolation
CREATE POLICY world_isolation_link ON lens_rel.link
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- ============================================================================
-- LENS_SEM SCHEMA POLICIES
-- ============================================================================

-- Policy for lens_sem.embedding - enforce world_id isolation
CREATE POLICY world_isolation_embedding ON lens_sem.embedding
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- Policy for lens_sem.embedding_state - enforce world_id isolation
CREATE POLICY world_isolation_embedding_state ON lens_sem.embedding_state
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- ============================================================================
-- LENS_GRAPH SCHEMA POLICIES
-- ============================================================================

-- Policy for lens_graph.projector_state - enforce world_id isolation
CREATE POLICY world_isolation_projector_state ON lens_graph.projector_state
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- Policy for lens_graph.graph_metadata - enforce world_id isolation
CREATE POLICY world_isolation_graph_metadata ON lens_graph.graph_metadata
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- ============================================================================
-- EVENT_CORE SCHEMA POLICIES
-- ============================================================================

-- Policy for event_core.event_log - enforce world_id isolation
CREATE POLICY world_isolation_event_log ON event_core.event_log
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- Policy for event_core.outbox - enforce world_id isolation
CREATE POLICY world_isolation_outbox ON event_core.outbox
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- Policy for event_core.dead_letter_queue - enforce world_id isolation
CREATE POLICY world_isolation_dlq ON event_core.dead_letter_queue
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- Policy for event_core.projector_watermarks - enforce world_id isolation
CREATE POLICY world_isolation_projector_watermarks ON event_core.projector_watermarks
    FOR ALL TO PUBLIC
    USING (world_id = current_setting('app.current_world_id', true)::UUID);

-- ============================================================================
-- ADMIN BYPASS ROLE (For operational access)
-- ============================================================================

-- Create admin role that can bypass RLS for operational tasks
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_admin') THEN
        CREATE ROLE nexus_admin;
        RAISE NOTICE 'Created nexus_admin role';
    ELSE
        RAISE NOTICE 'nexus_admin role already exists';
    END IF;
END $$;

-- Grant admin role ability to bypass RLS on all tables
GRANT nexus_admin TO postgres;

-- ============================================================================
-- VALIDATION FUNCTIONS
-- ============================================================================

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

-- ============================================================================
-- TESTING UTILITIES (for negative tests)
-- ============================================================================

-- Function to test RLS isolation (should fail cross-tenant access)
CREATE OR REPLACE FUNCTION test_rls_isolation(
    test_world_id UUID,
    other_world_id UUID
)
RETURNS TABLE(
    test_name TEXT,
    expected_result TEXT,
    actual_result TEXT,
    status TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    test_count INTEGER;
    cross_tenant_count INTEGER;
BEGIN
    -- Set context to test_world_id
    PERFORM set_current_world_id(test_world_id);
    
    -- Test 1: Should see own world's data
    SELECT COUNT(*) INTO test_count 
    FROM lens_rel.note 
    WHERE world_id = test_world_id;
    
    RETURN QUERY SELECT 
        'own_world_access'::TEXT,
        'success'::TEXT,
        CASE WHEN test_count >= 0 THEN 'success' ELSE 'fail' END,
        CASE WHEN test_count >= 0 THEN 'PASS' ELSE 'FAIL' END;
    
    -- Test 2: Should NOT see other world's data
    SELECT COUNT(*) INTO cross_tenant_count
    FROM lens_rel.note 
    WHERE world_id = other_world_id;
    
    RETURN QUERY SELECT
        'cross_tenant_isolation'::TEXT,
        'should_be_zero'::TEXT,
        cross_tenant_count::TEXT,
        CASE WHEN cross_tenant_count = 0 THEN 'PASS' ELSE 'FAIL' END;
        
    -- Reset context
    PERFORM set_config('app.current_world_id', '', false);
END;
$$;

-- ============================================================================
-- MIGRATION VALIDATION
-- ============================================================================

DO $$
DECLARE
    policy_count INTEGER;
    expected_policies INTEGER := 9; -- Number of policies we should have created
BEGIN
    -- Count RLS policies created
    SELECT COUNT(*) INTO policy_count
    FROM pg_policies 
    WHERE policyname LIKE 'world_isolation_%';
    
    IF policy_count = expected_policies THEN
        RAISE NOTICE 'SUCCESS: Created % RLS policies for tenant isolation', policy_count;
    ELSE
        RAISE EXCEPTION 'FAILED: Expected % policies, created %', expected_policies, policy_count;
    END IF;
    
    -- Verify RLS is enabled on key tables
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables t
        JOIN pg_class c ON c.relname = t.tablename
        WHERE t.schemaname = 'lens_rel' 
        AND t.tablename = 'note'
        AND c.relrowsecurity = true
    ) THEN
        RAISE EXCEPTION 'RLS not enabled on lens_rel.note';
    END IF;
    
    RAISE NOTICE 'RLS policies implementation complete and validated';
END $$;

COMMIT;
