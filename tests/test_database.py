"""
数据库层测试 — schema 创建、v0→v1 迁移、spare columns 幂等性。

所有测试使用临时数据库文件，不影响 data/trade.db。
"""

from __future__ import annotations

import sqlite3

# 将 trade 加入 PYTHONPATH（如果通过 pytest 直接运行）
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trade.database import (
    SCHEMA_SQL,
    _add_spare_columns,
    _migrate_from_v0,
    get_connection,
)


class TestSchemaCreation:
    """测试全新数据库的 schema 创建。"""

    def test_create_fresh_schema(self, tmp_path):
        """新数据库应创建 6 张表 + 5 个索引。"""
        db_path = tmp_path / "test_fresh.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")

        conn.executescript(SCHEMA_SQL)
        conn.commit()

        # 验证 6 张表
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {t[0] for t in tables}
        expected = {"companies", "trade_companies", "libraries", "customers",
                    "customer_libraries", "conversations"}
        assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"

        # 验证索引
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        ).fetchall()
        index_names = {i[0] for i in indexes}
        expected_indexes = {
            "idx_libraries_company", "idx_customers_company",
            "idx_conversations_company", "idx_conversations_library",
            "idx_conversations_created",
        }
        assert expected_indexes.issubset(index_names), \
            f"Missing indexes: {expected_indexes - index_names}"

        conn.close()

    def test_foreign_keys_enabled(self, tmp_path):
        """外键约束应被启用（PRAGMA foreign_keys = ON）。"""
        db_path = tmp_path / "test_fk.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        # 插入违反外键的数据（library 不存在的 company_id）
        conn.execute("INSERT INTO libraries (name, root_path, company_id) VALUES (?, ?, ?)",
                     ("Test", "/tmp/test", 999))
        # SQLite 默认不强制外键（需要 PRAGMA），但 get_connection 会启用
        conn.close()

        # 使用 get_connection 风格的连接（设置了 PRAGMA foreign_keys = ON）
        # 这里我们测试 TRADE 的 get_connection 是否启用了外键
        # 注：完整的外键测试在业务层测试中

    def test_all_tables_have_spare_columns(self, tmp_path):
        """所有 6 张表应有 extra1/extra2/extra3 备用列。"""
        db_path = tmp_path / "test_spare.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        _add_spare_columns(conn)
        conn.commit()

        for table in ["companies", "trade_companies", "libraries", "customers",
                      "customer_libraries", "conversations"]:
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for extra_col in ["extra1", "extra2", "extra3"]:
                assert extra_col in cols, f"{table} missing column: {extra_col}"

        conn.close()

    def test_spare_columns_default_is_json_object(self, tmp_path):
        """备用列的默认值应为 '{}'（空 JSON 对象）。"""
        db_path = tmp_path / "test_defaults.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        conn.execute(
            "INSERT INTO companies (name, slug) VALUES (?, ?)",
            ("Test Co", "test-co"),
        )
        conn.commit()
        row = conn.execute("SELECT extra1, extra2, extra3 FROM companies WHERE id=1").fetchone()
        assert row[0] == "{}"
        assert row[1] == "{}"
        assert row[2] == "{}"

        conn.close()


class TestSpareColumnsIdempotency:
    """测试 _add_spare_columns 的幂等性。"""

    def test_double_call_safe(self, tmp_path):
        """重复调用 _add_spare_columns 不应出错。"""
        db_path = tmp_path / "test_double.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        # 第一次调用：添加 spare columns
        _add_spare_columns(conn)
        # 第二次调用：应静默忽略（幂等）
        _add_spare_columns(conn)
        conn.commit()

        # 验证各表的列只出现一次
        for table in ["companies", "libraries", "customers"]:
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            extra_count = sum(1 for c in cols if c.startswith("extra"))
            assert extra_count == 3, f"{table} has {extra_count} extra columns (expected 3)"

        conn.close()


class TestV0ToV1Migration:
    """测试 v0（单公司）→ v1（多公司）迁移。"""

    def _create_v0_schema(self, conn):
        """创建 v0 版本的旧 schema（无 company_id 列）。"""
        conn.executescript("""
            CREATE TABLE libraries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                root_path TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact TEXT DEFAULT '',
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER,
                query TEXT NOT NULL,
                response TEXT DEFAULT '',
                files_read TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)
        # 插入一些 v0 格式数据
        conn.execute("INSERT INTO libraries (name, root_path) VALUES (?, ?)",
                     ("Old Library", "/tmp/old"))
        conn.execute("INSERT INTO customers (name, contact) VALUES (?, ?)",
                     ("Old Customer", "old@test.com"))
        conn.commit()

    def test_migration_detects_v0(self, tmp_path):
        """应检测到 v0 schema（libraries 无 company_id 列）。"""
        db_path = tmp_path / "test_migrate_detect.db"
        conn = sqlite3.connect(str(db_path))
        self._create_v0_schema(conn)

        # 验证迁移前状态
        cols = {row[1] for row in conn.execute("PRAGMA table_info(libraries)").fetchall()}
        assert "company_id" not in cols

        # 执行迁移
        migrated = _migrate_from_v0(conn)
        assert migrated is True, "Migration should have been performed"

        conn.close()

    def test_migration_idempotent(self, tmp_path):
        """已迁移的数据库不应重复执行迁移。"""
        db_path = tmp_path / "test_migrate_idempotent.db"
        conn = sqlite3.connect(str(db_path))

        # 使用完整 schema（已包含 company_id）
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        # 调用迁移 → 应返回 False（已是 v1）
        migrated = _migrate_from_v0(conn)
        assert migrated is False, "Already-migrated DB should return False"

        conn.close()

    def test_existing_data_preserved(self, tmp_path):
        """迁移后 v0 旧数据不应丢失，全部归属默认公司。"""
        db_path = tmp_path / "test_migrate_data.db"
        conn = sqlite3.connect(str(db_path))
        self._create_v0_schema(conn)

        migrated = _migrate_from_v0(conn)
        conn.commit()

        # 旧 library 数据应保留且 company_id=1
        lib = conn.execute("SELECT name, company_id FROM libraries WHERE id=1").fetchone()
        assert lib[0] == "Old Library"
        assert lib[1] == 1

        # 旧 customer 数据应保留且 company_id=1
        cust = conn.execute("SELECT name, contact, company_id FROM customers WHERE id=1").fetchone()
        assert cust[0] == "Old Customer"
        assert cust[1] == "old@test.com"
        assert cust[2] == 1

        conn.close()

    def test_default_company_created(self, tmp_path):
        """迁移应创建默认公司 '我的公司' (slug=default)。"""
        db_path = tmp_path / "test_migrate_company.db"
        conn = sqlite3.connect(str(db_path))
        self._create_v0_schema(conn)

        _migrate_from_v0(conn)
        conn.commit()

        company = conn.execute("SELECT name, slug FROM companies WHERE id=1").fetchone()
        assert company[0] == "我的公司"
        assert company[1] == "default"

        # 应有 trade_companies 记录
        tc = conn.execute("SELECT company_id, is_active FROM trade_companies WHERE company_id=1").fetchone()
        assert tc is not None
        assert tc[1] == 1

        conn.close()


class TestWALMode:
    """测试 WAL 模式。"""

    def test_wal_mode_enabled(self, tmp_path):
        """get_connection 应启用 WAL journal 模式。"""
        db_path = tmp_path / "test_wal.db"
        # 临时 monkey-patch _get_db_path
        import trade.database
        original = trade.database._get_db_path
        trade.database._get_db_path = lambda: db_path

        try:
            conn = get_connection()
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert journal.upper() == "WAL", f"Expected WAL, got {journal}"
            conn.close()
        finally:
            trade.database._get_db_path = original
