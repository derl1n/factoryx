CREATE TABLE IF NOT EXISTS checks (
    id SERIAL PRIMARY KEY,
    query_hash VARCHAR(64),
    url_hash VARCHAR(64),
    score INTEGER,
    verdict VARCHAR(20),
    explanation TEXT,
    sources TEXT,
    lang VARCHAR(10) DEFAULT 'uk',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_hash ON checks(query_hash);
CREATE INDEX IF NOT EXISTS idx_url_hash ON checks(url_hash);
CREATE INDEX IF NOT EXISTS idx_created_at ON checks(created_at);
CREATE INDEX IF NOT EXISTS idx_lang ON checks(lang);
CREATE INDEX IF NOT EXISTS idx_query_lang ON checks(query_hash, lang);

ALTER TABLE checks ADD COLUMN IF NOT EXISTS lang VARCHAR(10) DEFAULT 'uk';
ALTER TABLE checks ADD INDEX IF NOT EXISTS idx_lang (lang);
ALTER TABLE checks ADD INDEX IF NOT EXISTS idx_query_lang (query_hash, lang);
