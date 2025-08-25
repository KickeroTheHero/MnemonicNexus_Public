-- Initialize Apache AGE extension for MnemonicNexus V2
-- This script runs automatically during container initialization

-- Load AGE extension
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE functions into current session
LOAD 'age';

-- Set search path to include ag_catalog
SET search_path = ag_catalog, "$user", public;

-- Verify AGE extension is loaded
DO $$
BEGIN
    RAISE NOTICE 'AGE extension installed successfully';
    RAISE NOTICE 'ag_catalog schema available with %s functions', 
        (SELECT count(*) FROM information_schema.routines WHERE routine_schema = 'ag_catalog');
END
$$;
