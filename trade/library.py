"""
Trade AI Assistant — Document library management.

CRUD operations for B2B document libraries (directories of PDF/XLSX/DOCX files).
Each library maps to a file-system directory that the agent can scan and read.

All operations are scoped to a company_id for multi-tenancy isolation.
"""

from pathlib import Path

from trade.database import get_connection


def create(
    name: str,
    root_path: str,
    description: str = "",
    company_id: int | None = None,
) -> dict:
    """Create a document library scoped to a company. Returns the new row as a dict."""
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
    """Return all libraries for a company, newest first. company_id=None means unassigned."""
    conn = get_connection()
    try:
        if company_id is None:
            rows = conn.execute(
                "SELECT * FROM libraries WHERE company_id IS NULL ORDER BY id DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM libraries WHERE company_id = ? ORDER BY id DESC",
                (company_id,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get(library_id: int, company_id: int | None = None) -> dict | None:
    """Get a single library by id, optionally scoped to a company."""
    conn = get_connection()
    try:
        if company_id is not None:
            row = conn.execute(
                "SELECT * FROM libraries WHERE id = ? AND company_id = ?",
                (library_id, company_id),
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM libraries WHERE id = ?", (library_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update(
    library_id: int,
    company_id: int | None = None,
    **kwargs,
) -> dict | None:
    """Update library fields (name, root_path, description)."""
    allowed = {"name", "root_path", "description"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get(library_id, company_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [library_id]

    conn = get_connection()
    try:
        if company_id is not None:
            n = conn.execute(
                f"UPDATE libraries SET {set_clause}, updated_at = datetime('now','localtime') "
                "WHERE id = ? AND company_id = ?",
                values + [company_id],
            ).rowcount
        else:
            n = conn.execute(
                f"UPDATE libraries SET {set_clause}, updated_at = datetime('now','localtime') "
                "WHERE id = ?",
                values,
            ).rowcount
        conn.commit()
        if n == 0:
            return None
        return get(library_id, company_id)
    finally:
        conn.close()


def delete(library_id: int, company_id: int | None = None) -> bool:
    """Delete a library scoped to a company. Returns True if a row was deleted."""
    conn = get_connection()
    try:
        if company_id is not None:
            cur = conn.execute(
                "DELETE FROM libraries WHERE id = ? AND company_id = ?",
                (library_id, company_id),
            )
        else:
            cur = conn.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_files(library_id: int, company_id: int | None = None) -> int:
    """Count files in the library's root_path directory (non-recursive).

    company_id is optional for backward compatibility but should always be
    passed by API callers to enforce multi-tenant isolation.
    """
    lib = get(library_id, company_id=company_id)
    if not lib:
        return 0
    root = Path(lib["root_path"])
    if not root.is_dir():
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
