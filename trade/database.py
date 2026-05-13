"""
Trade AI Assistant — SQLite database layer.

Provides an independent database (data/trade.db) for B2B business tables:
libraries, customers, customer_libraries, conversations.

Does NOT interfere with Hermes Agent's session database.
"""

import os
import sqlite3
from pathlib import Path

# Database path: <project_root>/data/trade.db
def _get_db_path() -> Path:
    """Resolve the trade.db path relative to this file's project root."""
    # trade/database.py → parent is project root
    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "trade.db"


def get_connection() -> sqlite3.Connection:
    """Return a connection to trade.db with WAL mode and foreign keys enabled."""
    db_path = _get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema ──────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- Companies (multi-tenancy root entity)
-- Spare columns: extra1/extra2/extra3 为 TEXT 类型，存储 JSON 字符串，
--                用于未来 schema 扩展，无需 ALTER TABLE
CREATE TABLE IF NOT EXISTS companies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    slug         TEXT    NOT NULL UNIQUE,
    logo_url     TEXT    DEFAULT '',
    website      TEXT    DEFAULT '',
    contact_name TEXT    DEFAULT '',
    contact_email TEXT   DEFAULT '',
    address      TEXT    DEFAULT '',
    is_active    INTEGER DEFAULT 1,   -- 1=active, 0=inactive
    created_at   TEXT    DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT    DEFAULT (datetime('now', 'localtime')),
    extra1       TEXT    DEFAULT '{}',  -- spare: {"industry":"", "country":"", ...}
    extra2       TEXT    DEFAULT '{}',  -- spare: {"employee_count":"", "annual_revenue":"", ...}
    extra3       TEXT    DEFAULT '{}'   -- spare: reserved for future use
);

-- Trade-level company config (links company to Trade system)
CREATE TABLE IF NOT EXISTS trade_companies (
    company_id        INTEGER PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    data_dir          TEXT    NOT NULL,   -- absolute path to ~/.trade/{slug}/
    agent_identity_md TEXT    DEFAULT '', -- inline agent identity, overrides data_dir file
    is_active         INTEGER DEFAULT 1,  -- 1=active session
    created_at        TEXT    DEFAULT (datetime('now', 'localtime')),
    extra1            TEXT    DEFAULT '{}',  -- spare: {"max_iterations":90, "temperature":0.7, ...}
    extra2            TEXT    DEFAULT '{}',  -- spare: {"model":"", "provider":"", ...}
    extra3            TEXT    DEFAULT '{}'   -- spare: reserved for future use
);

CREATE TABLE IF NOT EXISTS libraries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    name         TEXT    NOT NULL,
    root_path    TEXT    NOT NULL,
    description  TEXT    DEFAULT '',
    created_at   TEXT    DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT    DEFAULT (datetime('now', 'localtime')),
    extra1       TEXT    DEFAULT '{}',  -- spare: {"scan_depth":3, "file_count":0, "last_scan":""}
    extra2       TEXT    DEFAULT '{}',  -- spare: {"indexed":false, "index_version":1}
    extra3       TEXT    DEFAULT '{}'   -- spare: reserved for future use
);

CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    contact     TEXT    DEFAULT '',
    note        TEXT    DEFAULT '',
    created_at  TEXT    DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT    DEFAULT (datetime('now', 'localtime')),
    extra1      TEXT    DEFAULT '{}',  -- spare: {"country":"", "website":"", "linkedin_url":""}
    extra2      TEXT    DEFAULT '{}',  -- spare: {"customer_type":"", "tier":"", "source":""}
    extra3      TEXT    DEFAULT '{}'   -- spare: reserved for future use
);

CREATE TABLE IF NOT EXISTS customer_libraries (
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    library_id  INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
    extra1      TEXT    DEFAULT '{}',  -- spare: {"relevance_score":0.0, "notes":""}
    extra2      TEXT    DEFAULT '{}',  -- spare: reserved for future use
    extra3      TEXT    DEFAULT '{}',  -- spare: reserved for future use
    PRIMARY KEY (customer_id, library_id)
);

CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    library_id  INTEGER REFERENCES libraries(id) ON DELETE SET NULL,
    query       TEXT    NOT NULL,
    response    TEXT    DEFAULT '',
    files_read  TEXT    DEFAULT '[]',  -- JSON array: [{"file":"...","pages":[1,2]}]
    created_at  TEXT    DEFAULT (datetime('now', 'localtime')),
    extra1      TEXT    DEFAULT '{}',  -- spare: {"tokens_used":0, "model":"", "duration_ms":0}
    extra2      TEXT    DEFAULT '{}',  -- spare: {"rating":null, "feedback":""}
    extra3      TEXT    DEFAULT '{}'   -- spare: {"tools_used":[], "iterations":0}
);

CREATE INDEX IF NOT EXISTS idx_libraries_company   ON libraries(company_id);
CREATE INDEX IF NOT EXISTS idx_customers_company    ON customers(company_id);
CREATE INDEX IF NOT EXISTS idx_conversations_company ON conversations(company_id);
CREATE INDEX IF NOT EXISTS idx_conversations_library ON conversations(library_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created  ON conversations(created_at);
"""

# Migration from v0 (single-company) schema — handled in Python, not SQL

def _add_spare_columns(conn: sqlite3.Connection) -> None:
    """Add spare TEXT columns (extra1/extra2/extra3) to all tables if missing.

    Idempotent — safe to call on any schema version. Uses ALTER TABLE ADD COLUMN
    which is a no-op if the column already exists.
    """
    for table, extras in [
        ("companies",        ["extra1", "extra2", "extra3"]),
        ("trade_companies",  ["extra1", "extra2", "extra3"]),
        ("libraries",       ["extra1", "extra2", "extra3"]),
        ("customers",       ["extra1", "extra2", "extra3"]),
        ("customer_libraries", ["extra1", "extra2", "extra3"]),
        ("conversations",   ["extra1", "extra2", "extra3"]),
    ]:
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for col in extras:
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT '{{}}'")


def _migrate_from_v0(conn: sqlite3.Connection) -> bool:
    """Migrate v0 (single-company) schema to v1 (multi-company).

    Checks if the old tables lack company_id columns.
    If they do, adds company_id columns and creates a default company
    with slug='default', owned by the Trade system.
    Returns True if migration was performed, False if already on v1.
    """
    # Detect old schema by checking if libraries lacks company_id column
    cur = conn.execute("PRAGMA table_info(libraries)")
    cols = {row[1] for row in cur.fetchall()}
    if "company_id" in cols:
        return False  # Already v1

    print("  Detected v0 schema — migrating to multi-company v1 …")

    # Create companies + trade_companies tables first
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT    NOT NULL,
            slug         TEXT    NOT NULL UNIQUE,
            logo_url     TEXT    DEFAULT '',
            website      TEXT    DEFAULT '',
            contact_name TEXT    DEFAULT '',
            contact_email TEXT   DEFAULT '',
            address      TEXT    DEFAULT '',
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT    DEFAULT (datetime('now', 'localtime')),
            updated_at   TEXT    DEFAULT (datetime('now', 'localtime')),
            extra1       TEXT    DEFAULT '{}',
            extra2       TEXT    DEFAULT '{}',
            extra3       TEXT    DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS trade_companies (
            company_id        INTEGER PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
            data_dir          TEXT    NOT NULL,
            agent_identity_md TEXT    DEFAULT '',
            is_active         INTEGER DEFAULT 1,
            created_at        TEXT    DEFAULT (datetime('now', 'localtime')),
            extra1            TEXT    DEFAULT '{}',
            extra2            TEXT    DEFAULT '{}',
            extra3            TEXT    DEFAULT '{}'
        );

        INSERT OR IGNORE INTO companies (name, slug, is_active)
        VALUES ('我的公司', 'default', 1);

        INSERT OR IGNORE INTO trade_companies (company_id, data_dir, is_active)
        VALUES (1, '', 1);
    """)

    # Add company_id column to existing v0 tables
    conn.execute("ALTER TABLE libraries ADD COLUMN company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE")
    conn.execute("UPDATE libraries SET company_id = 1")

    conn.execute("ALTER TABLE customers ADD COLUMN company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE")
    conn.execute("UPDATE customers SET company_id = 1")

    conn.execute("ALTER TABLE conversations ADD COLUMN company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE")
    conn.execute("UPDATE conversations SET company_id = 1")

    # Add new indexes
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_libraries_company    ON libraries(company_id);
        CREATE INDEX IF NOT EXISTS idx_customers_company     ON customers(company_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_company ON conversations(company_id);
    """)

    # Add spare columns to ALL existing tables (v1 DB upgraded in-place, or fresh v1 install).
    # Uses ALTER TABLE ADD COLUMN which is idempotent — safe to call even if column exists.
    _add_spare_columns(conn)

    conn.commit()
    print("  Migration complete. Default company '我的公司' (slug=default) created.")
    return True


def init_db() -> Path:
    """Create tables if they don't exist. Handles v0→v1 migration.
    Also adds spare columns to any existing tables regardless of version.
    Returns the database path."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        migrated = _migrate_from_v0(conn)
        if not migrated:
            # Already on v1 (or fresh install) — still ensure spare columns exist
            _add_spare_columns(conn)
            conn.commit()
    finally:
        conn.close()
    return _get_db_path()


# ── Quick CLI test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    path = init_db()
    print(f"Database initialized: {path}")

    # Print table list
    conn = get_connection()
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        print(f"Tables ({len(tables)}):")
        for (name,) in tables:
            print(f"  • {name}")
    finally:
        conn.close()
