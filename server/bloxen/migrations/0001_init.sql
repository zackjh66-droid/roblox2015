-- BLOXEN application database schema (SQLite). Migration 0001.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,          -- scrypt/pbkdf2 modern hashing
    password_algo TEXT NOT NULL DEFAULT 'scrypt',
    email TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    banned INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,      -- sha256 of opaque cookie token
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    user_agent TEXT,
    ip TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    blurb TEXT NOT NULL DEFAULT '',
    age_band TEXT,
    gender TEXT,
    location TEXT,
    avatar_json TEXT NOT NULL DEFAULT '{}',   -- body colours, scales, equipped ids
    join_date TEXT
);

CREATE TABLE IF NOT EXISTS friendships (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    friend_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, friend_id),
    CHECK (user_id <> friend_id)
);

CREATE TABLE IF NOT EXISTS friend_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending / accepted / declined
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (from_user, to_user)
);

CREATE TABLE IF NOT EXISTS items (              -- catalog items (historically evidenced)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    historical_asset_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    creator TEXT NOT NULL DEFAULT 'ROBLOX',
    item_type TEXT NOT NULL,                    -- Hat, Face, Shirt, Pants, TShirt, Head, Gear, Package...
    price_robux INTEGER,
    price_tix INTEGER,
    is_limited INTEGER NOT NULL DEFAULT 0,
    created_date TEXT,                          -- historical date where evidenced
    thumbnail_path TEXT,
    archive_source TEXT,
    provenance_grade TEXT NOT NULL DEFAULT '3',
    provenance_note TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
    method TEXT NOT NULL DEFAULT 'purchase',    -- purchase / grant / promo
    UNIQUE (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,                  -- game / item
    target_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    creator TEXT NOT NULL,
    historical_place_id INTEGER,
    historical_creator_id INTEGER,
    description TEXT NOT NULL DEFAULT '',
    genre TEXT NOT NULL DEFAULT 'All',
    created_date TEXT,
    place_path TEXT,                            -- local imported place file
    place_sha256 TEXT,
    thumbnail_path TEXT,
    provenance_grade TEXT NOT NULL DEFAULT '4',
    provenance_note TEXT,
    compatibility_status TEXT NOT NULL DEFAULT 'imported'
        -- researched / imported / parsed / metadata-ok / SIMULATOR-TESTED / REAL-CLIENT-TESTED
);

CREATE TABLE IF NOT EXISTS game_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    version_label TEXT,
    version_date TEXT,
    sha256 TEXT,
    source_url TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS assets (             -- recovered historical asset index
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    historical_asset_id INTEGER NOT NULL UNIQUE,
    asset_type TEXT NOT NULL,                   -- Texture, Decal, Mesh, Sound, Shirt, Pants, TShirt, Face, Hat, Model, Animation...
    name TEXT,
    source_url TEXT,
    local_path TEXT,
    sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'MISSING',     -- MISSING / RECOVERED / REJECTED
    provenance_grade TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS asset_dependencies (
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    PRIMARY KEY (game_id, asset_id)
);

CREATE TABLE IF NOT EXISTS launch_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket TEXT NOT NULL UNIQUE,                -- single-use opaque ticket (stored hashed)
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    server_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    used_at TEXT,
    status TEXT NOT NULL DEFAULT 'issued'       -- issued / used / expired / revoked
);

CREATE TABLE IF NOT EXISTS recently_played (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    played_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, game_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    read_at TEXT
);

CREATE TABLE IF NOT EXISTS place_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    format TEXT NOT NULL,                       -- rbxl-binary / rbxl-xml / rbxm / rbxmx
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    class_counts TEXT,                          -- JSON histogram
    external_asset_ids TEXT,                    -- JSON list
    service_report TEXT,                        -- JSON compatibility report
    script_inventory TEXT,                      -- JSON inert script list
    accepted INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS compat_requests (    -- log of 2015-client compatibility HTTP calls
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL DEFAULT (datetime('now')),
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    query TEXT,
    body_preview TEXT,
    response_status INTEGER,
    client_tag TEXT
);

CREATE TABLE IF NOT EXISTS play_sessions (      -- game-server sessions (simulator or real client)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,                         -- SIMULATOR / REAL-CLIENT
    game_id INTEGER REFERENCES games(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    notes TEXT
);
