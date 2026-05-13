"""
Trade AI Assistant — Document library management.

CRUD operations for B2B document libraries (directories of PDF/XLSX/DOCX files).
Each library maps to a file-system directory that the agent can scan and read.

All operations are scoped to a company_id for multi-tenancy isolation.
"""

import json
from pathlib import Path
from typing import Optional

from trade.database import get_connection


def create(
    name: str,
    root_path: str,
    description: str = "",
    company_id: Optional[int] = None,
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


def list_by_company(company_id: Optional[int] = None) -> list[dict]:
    """Return all libraries for a company, newest first. company_id=None means unassigned."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM libraries WHERE company_id IS ? ORDER BY id DESC",
            (company_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get(library_id: int, company_id: Optional[int] = None) -> Optional[dict]:
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
    company_id: Optional[int] = None,
    **kwargs,
) -> Optional[dict]:
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


def delete(library_id: int, company_id: Optional[int] = None) -> bool:
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


def count_files(library_id: int) -> int:
    """Count files in the library's root_path directory (non-recursive)."""
    lib = get(library_id)
    if not lib:
        return 0
    root = Path(lib["root_path"])
    if not root.is_dir():
        return 0
    return sum(1 for p in root.iterdir() if p.is_file())


# ── helpers ──────────────────────────────────────────────────────────────────

def _row_to_dict(row: tuple) -> dict:
    return {
        "id": row[0],
        "company_id": row[1],
        "name": row[2],
        "root_path": row[3],
        "description": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }


# ── CLI smoke test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from trade.database import init_db
    init_db()

    # Create a test library for company 1
    lib = create("Test Library", "/tmp/test_docs", "A test document library", company_id=1)
    print("Created:", json.dumps(lib, indent=2, ensure_ascii=False))

    # List by company
    all_libs = list_by_company(1)
    print(f"\nLibraries for company 1 ({len(all_libs)}):")
    for l in all_libs:
        print(f"  [{l['id']}] {l['name']} → {l['root_path']}")

    # Clean up
    delete(lib["id"], company_id=1)
    print("\nCleaned up test library.")
