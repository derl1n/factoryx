CREATE TABLE IF NOT EXISTS checks (
    id SERIAL PRIMARY KEY,
    query_hash VARCHAR(64),
    url_hash VARCHAR(64),
    score INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_created_at ON checks(created_at);
CREATE INDEX IF NOT EXISTS idx_query_hash ON checks(query_hash);
CREATE INDEX IF NOT EXISTS idx_url_hash ON checks(url_hash);
