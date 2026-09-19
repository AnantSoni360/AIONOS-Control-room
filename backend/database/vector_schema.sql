-- ============================================================
-- AIONOS Agentic AI Factory -- SOP Vector Store Schema
-- Run in Supabase SQL Editor AFTER enabling the pgvector extension:
--   Dashboard -> Database -> Extensions -> search "vector" -> Enable
-- ============================================================

-- Enable pgvector (idempotent)
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------
-- SOP Policy Chunks table
-- Stores chunked, embedded SOP documents for RAG retrieval
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS sop_chunks (
    id          SERIAL PRIMARY KEY,
    department  VARCHAR(50)  NOT NULL,   -- Finance | HR | Sales | Operations
    source_file VARCHAR(200) NOT NULL,   -- e.g. finance_sop.txt
    chunk_index INTEGER      NOT NULL,   -- position within the source doc
    chunk_text  TEXT         NOT NULL,   -- the raw text chunk
    embedding   vector(768)   NOT NULL,   -- Google text-embedding-004 (768-dim)
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- IVFFlat index for fast approximate nearest-neighbor search
-- NOTE: HNSW has a hard 2000-dim limit; IVFFlat supports any dimension.
-- lists=100 is a good default for datasets < 1M vectors.
CREATE INDEX IF NOT EXISTS sop_chunks_embedding_idx
    ON sop_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Composite index for department-filtered retrieval
CREATE INDEX IF NOT EXISTS sop_chunks_department_idx
    ON sop_chunks (department);

-- Disable RLS for service_role access
ALTER TABLE sop_chunks DISABLE ROW LEVEL SECURITY;

-- ---------------------------------------------
-- Similarity search function (called from Python)
-- ---------------------------------------------
CREATE OR REPLACE FUNCTION match_sop_chunks(
    query_embedding  vector(768),
    filter_dept      VARCHAR(50),
    match_count      INTEGER DEFAULT 3
)
RETURNS TABLE (
    id          INTEGER,
    department  VARCHAR(50),
    source_file VARCHAR(200),
    chunk_text  TEXT,
    similarity  FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        sc.id,
        sc.department,
        sc.source_file,
        sc.chunk_text,
        1 - (sc.embedding <=> query_embedding) AS similarity
    FROM sop_chunks sc
    WHERE (filter_dept IS NULL OR sc.department = filter_dept)
    ORDER BY sc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

SELECT 'Vector schema created successfully!' AS result;
