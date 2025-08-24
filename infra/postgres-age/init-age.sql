-- Initialize Apache AGE extension for MnemonicNexus V2
-- This script runs automatically during container initialization

-- Load AGE extension
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE functions into current session
LOAD 'age';

-- Set search path to include ag_catalog
SET search_path = ag_catalog, "$user", public;

-- Create a test graph to verify AGE is working
SELECT ag_catalog.create_graph('test_age_installation');

-- Test basic AGE functionality
DO $$
BEGIN
    -- Test graph creation and basic node insertion
    PERFORM ag_catalog.cypher('test_age_installation', $$
        CREATE (n:TestNode {name: 'installation_test', installed_at: timestamp()})
        RETURN n
    $$) AS (result agtype);
    
    -- Clean up test graph
    PERFORM ag_catalog.drop_graph('test_age_installation', true);
    
    RAISE NOTICE 'AGE extension installed and validated successfully';
    RAISE NOTICE 'ag_catalog schema available with %s functions', 
        (SELECT count(*) FROM information_schema.routines WHERE routine_schema = 'ag_catalog');
        
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'AGE extension test failed: %', SQLERRM;
    RAISE NOTICE 'AGE may not be properly installed, but extension creation succeeded';
END
$$;
