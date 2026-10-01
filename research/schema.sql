-- BLOXEN research/provenance database schema
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT,
    archive_timestamp TEXT,          -- when the artifact itself was archived/captured, if known
    retrieved_at TEXT NOT NULL,      -- when BLOXEN retrieved it
    target_date TEXT,                -- historical date the evidence speaks to (YYYY-MM-DD)
    content_type TEXT,               -- client-binary, api-dump, css, html, place-file, doc, metadata...
    historical_entity TEXT,          -- e.g. "WindowsPlayer 0.205.0.61876", "Catalog item 1029025"
    local_path TEXT,
    sha256 TEXT,
    provenance_grade TEXT NOT NULL,  -- 1-original 2-archived-exact 3-archived-near 4-reconstruction 5-inference
    verification_state TEXT,         -- unverified / cross-checked / hash-verified / rejected
    notes TEXT
);
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,             -- CLIENT / WEBSITE / GAMES / CATALOG / ASSETS / PROTOCOL / PROVENANCE
    claim TEXT NOT NULL,
    evidence_source_id INTEGER REFERENCES sources(id),
    grade TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'proposed'
);
CREATE TABLE IF NOT EXISTS verification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    method TEXT NOT NULL,
    result TEXT NOT NULL,
    detail TEXT,
    at TEXT NOT NULL DEFAULT (datetime('now'))
);
