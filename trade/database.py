"""
Trade AI Assistant — SQLite 数据库层。

提供独立的数据库 (data/trade.db) 用于 B2B 业务表：
libraries、customers、customer_libraries、conversations。

不干预 Hermes Agent 的会话数据库。
"""

import os
import sqlite3
from pathlib import Path


# 数据库路径: ~/.trade/data/trade.db（macOS/Linux）或 %LOCALAPPDATA%\trade\data\trade.db（Windows）
def _get_db_path() -> Path:
    """解析用户 Trade 数据目录下的 trade.db 路径。

    优先级: TRADE_HOME 环境变量 → ~/.trade/（macOS/Linux）或 %LOCALAPPDATA%\\trade\\（Windows）。
    """
    trade_home = os.environ.get("TRADE_HOME", "").strip()
    # 如果 TRADE_HOME 环境变量未设置，则使用系统默认路径
    if not trade_home:
        # Windows: %LOCALAPPDATA%\trade, macOS/Linux: ~/.trade
        if os.name == "nt":
            trade_home = str(Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "trade")
        else:
            trade_home = str(Path.home() / ".trade")
    data_dir = Path(trade_home) / "data"
    # 确保 data 目录存在，不存在则创建
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "trade.db"


def get_connection() -> sqlite3.Connection:
    """返回 trade.db 的连接，启用 WAL 模式、外键约束和 Row 工厂。

    sqlite3.Row 使查询结果支持按列名访问（row["id"] 而非 row[0]），
    避免 schema 顺序变更导致的位置索引 bug。
    """
    db_path = _get_db_path()
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
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
    """向所有表中添加备用 TEXT 列（extra1/extra2/extra3）（如果缺少的话）。

    幂等操作 — 先查询已存在列再决定是否添加，避免 ALTER TABLE ADD COLUMN 重复报错。
    安全跳过尚未存在的表（如 v0→v1 迁移过程中）。
    """
    # 获取当前存在的所有表
    existing_tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    for table, extras in [
        ("companies",        ["extra1", "extra2", "extra3"]),
        ("trade_companies",  ["extra1", "extra2", "extra3"]),
        ("libraries",       ["extra1", "extra2", "extra3"]),
        ("customers",       ["extra1", "extra2", "extra3"]),
        ("customer_libraries", ["extra1", "extra2", "extra3"]),
        ("conversations",   ["extra1", "extra2", "extra3"]),
    ]:
        # 跳过还不存在的表（如 v0 schema 中没有 customer_libraries）
        if table not in existing_tables:
            continue
        existing_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for col in extras:
            # 仅当列不存在时才添加，避免 ALTER TABLE 重复报错
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT '{{}}'")


def _migrate_from_v0(conn: sqlite3.Connection) -> bool:
    """将 v0（单公司）schema 迁移到 v1（多公司）。

    检查旧表是否缺少 company_id 列。
    如果缺少，则添加 company_id 列并创建一个 slug='default' 的默认公司，
    由 Trade 系统拥有。
    如果已执行迁移则返回 True，如果已是 v1 则返回 False。
    """
    # 通过检查 libraries 表是否缺少 company_id 列来检测旧 schema
    cur = conn.execute("PRAGMA table_info(libraries)")
    cols = {row[1] for row in cur.fetchall()}
    # 如果已有 company_id 列，说明已是 v1 schema，无需迁移
    if "company_id" in cols:
        return False  # 已是 v1

    print("  检测到 v0 schema — 正在迁移到多公司 v1 …")

    # 先创建 companies + trade_companies 表
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

    # 向现有 v0 表添加 company_id 列
    conn.execute("ALTER TABLE libraries ADD COLUMN company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE")
    # 将所有现有记录关联到默认公司 (id=1)
    conn.execute("UPDATE libraries SET company_id = 1")

    conn.execute("ALTER TABLE customers ADD COLUMN company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE")
    # 将所有现有客户关联到默认公司 (id=1)
    conn.execute("UPDATE customers SET company_id = 1")

    conn.execute("ALTER TABLE conversations ADD COLUMN company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE")
    # 将所有现有会话关联到默认公司 (id=1)
    conn.execute("UPDATE conversations SET company_id = 1")

    # 添加新索引
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_libraries_company    ON libraries(company_id);
        CREATE INDEX IF NOT EXISTS idx_customers_company     ON customers(company_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_company ON conversations(company_id);
    """)

    # 向所有现有表添加备用列（v1 DB 原地升级，或全新 v1 安装）。
    # 使用 ALTER TABLE ADD COLUMN 是幂等的 — 即使列已存在也可以安全调用。
    _add_spare_columns(conn)

    conn.commit()
    print("  迁移完成。已创建默认公司 '我的公司' (slug=default)。")
    return True


def init_db() -> Path:
    """如果表不存在则创建它们。处理 v0→v1 迁移。
    同时向所有现有表添加备用列，无论版本如何。
    返回数据库路径。"""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        migrated = _migrate_from_v0(conn)
        # 如果未发生迁移（已是 v1 或全新安装），仍然确保备用列存在
        if not migrated:
            # 已是 v1（或全新安装）— 仍然确保备用列存在
            _add_spare_columns(conn)
            conn.commit()
    finally:
        conn.close()
    return _get_db_path()


# ── Quick CLI test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    path = init_db()
    print(f"数据库已初始化: {path}")

    # 打印表列表
    conn = get_connection()
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        print(f"表 ({len(tables)}):")
        for (name,) in tables:
            print(f"  • {name}")
    finally:
        conn.close()
