"""
Trade AI Assistant — 文档库管理.

B2B 文档库（PDF/XLSX/DOCX 文件目录）的 CRUD 操作。
每个文档库对应一个文件系统目录，AI 智能体可以扫描并读取其中的文件。

所有操作都限定在公司范围内，实现多租户隔离。
"""

from pathlib import Path

from trade.database import get_connection


def create(
    name: str,
    root_path: str,
    description: str = "",
    company_id: int | None = None,
) -> dict:
    """创建归属于指定公司的文档库，返回新记录行的字典。"""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO libraries (company_id, name, root_path, description) VALUES (?, ?, ?, ?)",
            (company_id, name, root_path, description),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM libraries WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_by_company(company_id: int | None = None) -> list[dict]:
    """返回某个公司的所有文档库，按 id 降序排列（最新的在前）。company_id=None 表示未分配。"""
    conn = get_connection()
    try:
        if company_id is None:
            # 未指定公司，查询所有未分配公司的文档库
            rows = conn.execute(
                "SELECT * FROM libraries WHERE company_id IS NULL ORDER BY id DESC"
            ).fetchall()
        else:
            # 按指定公司 ID 查询文档库
            rows = conn.execute(
                "SELECT * FROM libraries WHERE company_id = ? ORDER BY id DESC",
                (company_id,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get(library_id: int, company_id: int | None = None) -> dict | None:
    """根据 id 获取单个文档库，可选地按公司范围限定。"""
    conn = get_connection()
    try:
        if company_id is not None:
            # 指定了公司，需同时校验公司 ID 以隔离多租户数据
            row = conn.execute(
                "SELECT * FROM libraries WHERE id = ? AND company_id = ?",
                (library_id, company_id),
            ).fetchone()
        else:
            # 未指定公司，仅按 id 查询
            row = conn.execute("SELECT * FROM libraries WHERE id = ?", (library_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update(
    library_id: int,
    company_id: int | None = None,
    **kwargs,
) -> dict | None:
    """更新文档库字段（name, root_path, description）。"""
    allowed = {"name", "root_path", "description"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        # 没有可更新的字段时，直接返回当前记录
        return get(library_id, company_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [library_id]

    conn = get_connection()
    try:
        if company_id is not None:
            # 指定了公司，需同时校验公司 ID 以隔离多租户数据
            n = conn.execute(
                f"UPDATE libraries SET {set_clause}, updated_at = datetime('now','localtime') "
                "WHERE id = ? AND company_id = ?",
                values + [company_id],
            ).rowcount
        else:
            # 未指定公司，仅按 id 更新
            n = conn.execute(
                f"UPDATE libraries SET {set_clause}, updated_at = datetime('now','localtime') "
                "WHERE id = ?",
                values,
            ).rowcount
        conn.commit()
        if n == 0:
            # 没有行被更新，说明指定的 id 不存在或不属于该公司
            return None
        return get(library_id, company_id)
    finally:
        conn.close()


def delete(library_id: int, company_id: int | None = None) -> bool:
    """删除归属于指定公司的文档库。如果确实删除了某行则返回 True。"""
    conn = get_connection()
    try:
        if company_id is not None:
            # 指定了公司，需同时校验公司 ID 以确保只能删除本公司文档库
            cur = conn.execute(
                "DELETE FROM libraries WHERE id = ? AND company_id = ?",
                (library_id, company_id),
            )
        else:
            # 未指定公司，仅按 id 删除
            cur = conn.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_files(library_id: int, company_id: int | None = None) -> int:
    """统计文档库根目录中的文件数量（非递归）。

    company_id 参数为向后兼容而设为可选，但 API 调用方应始终传入
    以确保多租户隔离。
    """
    lib = get(library_id, company_id=company_id)
    if not lib:
        # 文档库不存在或不属于该公司，返回 0
        return 0
    root = Path(lib["root_path"])
    if not root.is_dir():
        # 根路径不是有效目录，返回 0
        return 0
    return sum(1 for p in root.iterdir() if p.is_file())


# ── helpers ──────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "company_id": row["company_id"],
        "name": row["name"],
        "root_path": row["root_path"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
