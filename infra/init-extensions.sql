-- PostgreSQL Extensions for MnemonicNexus V2
-- Loaded automatically during container initialization

-- Standard PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- pgvector for semantic embeddings (already available in pgvector/pgvector image)
CREATE EXTENSION IF NOT EXISTS "vector";

-- Apache AGE for graph operations
-- Note: AGE extension requires custom compilation, deferred to Phase A2
-- For Phase A1, we focus on infrastructure validation with pgvector
-- TODO Phase A2: Add AGE extension via custom Docker image or installation

-- Verify critical extensions loaded
DO $$
BEGIN
    -- Check vector extension
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'Vector extension failed to load';
    END IF;
    
    RAISE NOTICE 'Phase A1 extensions loaded successfully: uuid-ossp, pgcrypto, vector';
    RAISE NOTICE 'AGE extension installation deferred to Phase A2 with custom image';
END
$$;
