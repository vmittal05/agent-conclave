-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table for tracking individual model execution steps
CREATE TABLE IF NOT EXISTS model_runs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    model_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing detailed citations gathered by research agents
CREATE TABLE IF NOT EXISTS citations (
    id SERIAL PRIMARY KEY,
    model_run_id INTEGER REFERENCES model_runs(id) ON DELETE CASCADE,
    source_url TEXT,
    source_type VARCHAR(50),
    title TEXT,
    snippet TEXT,
    raw_citation TEXT,
    normalized_key TEXT,
    embedding VECTOR(1536), -- Assuming standard embedding size (e.g., OpenAI/Vertex)
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_citations_model_run_id ON citations(model_run_id);
CREATE INDEX IF NOT EXISTS idx_citations_normalized_key ON citations(normalized_key);
CREATE INDEX IF NOT EXISTS idx_model_runs_session_id ON model_runs(session_id);
