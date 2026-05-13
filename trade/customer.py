"""
Trade AI Assistant — Customer management.

CRUD for B2B customers with optional document library associations.
All operations are scoped to a company_id for multi-tenancy isolation.
"""

import json
from typing import Optional

from trade.database import get_connection


def create(
    name: str,
    contact: str = "",
    note: str = "",
    company_id: Optional[int] = None,
) -> dict:
    """Create a customer scoped to a company. Returns the new row as a dict."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO customers (company_id, name, contact, note) VALUES (?, ?, ?, ?)",
            (company_id, name, contact, note),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_by_company(company_id: int) -> list[dict]:
    """Return all customers for a company, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM customers WHERE company_id = ? ORDER BY id DESC",
            (company_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get(customer_id: int, company_id: Optional[int] = None) -> Optional[dict]:
    """Get a single customer by id, optionally scoped to a company."""
    conn = get_connection()
    try:
        if company_id is not None:
            row = conn.execute(
                "SELECT * FROM customers WHERE id = ? AND company_id = ?",
                (customer_id, company_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update(
    customer_id: int,
    company_id: Optional[int] = None,
    **kwargs,
) -> Optional[dict]:
    """Update customer fields (name, contact, note)."""
    allowed = {"name", "contact", "note"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get(customer_id, company_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [customer_id]

    conn = get_connection()
    try:
        if company_id is not None:
            n = conn.execute(
                f"UPDATE customers SET {set_clause}, updated_at = datetime('now','localtime') "
                "WHERE id = ? AND company_id = ?",
                values + [company_id],
            ).rowcount
        else:
            n = conn.execute(
                f"UPDATE customers SET {set_clause}, updated_at = datetime('now','localtime') "
                "WHERE id = ?",
                values,
            ).rowcount
        conn.commit()
        if n == 0:
            return None
        return get(customer_id, company_id)
    finally:
        conn.close()


def delete(customer_id: int, company_id: Optional[int] = None) -> bool:
    """Delete a customer scoped to a company. Returns True if a row was deleted."""
    conn = get_connection()
    try:
        if company_id is not None:
            cur = conn.execute(
                "DELETE FROM customers WHERE id = ? AND company_id = ?",
                (customer_id, company_id),
            )
        else:
            cur = conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── Library associations ─────────────────────────────────────────────────────
# Security: all library associations are verified through company_id scoping
# to prevent cross-company linking.


def link_library(
    customer_id: int,
    library_id: int,
    company_id: int,
) -> bool:
    """Associate a library with a customer (both must belong to the same company).

    Returns True on success; raises ValueError if the customer or library
    does not exist under the given company_id.
    """
    # Verify both belong to the company
    cust = get(customer_id, company_id)
    if not cust:
        raise ValueError(f"Customer {customer_id} not found under company {company_id}")

    from trade.library import get as get_library

    lib = get_library(library_id, company_id)
    if not lib:
        raise ValueError(f"Library {library_id} not found under company {company_id}")

    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO customer_libraries (customer_id, library_id) VALUES (?, ?)",
            (customer_id, library_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def unlink_library(
    customer_id: int,
    library_id: int,
    company_id: int,
) -> bool:
    """Remove a library association scoped to a company."""
    conn = get_connection()
    try:
        # Verify ownership before unlinking
        cust = get(customer_id, company_id)
        if not cust:
            return False
        cur = conn.execute(
            "DELETE FROM customer_libraries WHERE customer_id = ? AND library_id = ?",
            (customer_id, library_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_libraries(customer_id: int, company_id: int) -> list[dict]:
    """Return all libraries linked to a customer, scoped to a company."""
    # Verify customer belongs to company
    cust = get(customer_id, company_id)
    if not cust:
        return []

    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT l.* FROM libraries l
               JOIN customer_libraries cl ON cl.library_id = l.id
               WHERE cl.customer_id = ? AND l.company_id = ?
               ORDER BY l.name""",
            (customer_id, company_id),
        ).fetchall()
        return [_library_row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ── helpers ──────────────────────────────────────────────────────────────────

def _row_to_dict(row: tuple) -> dict:
    return {
        "id": row[0],
        "company_id": row[1],
        "name": row[2],
        "contact": row[3],
        "note": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }


def _library_row_to_dict(row: tuple) -> dict:
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

    # Create
    cust = create("科辰电力", "contact@kechen.com", "电力金具客户", company_id=1)
    print("Created:", json.dumps(cust, indent=2, ensure_ascii=False))

    # List by company
    all_custs = list_by_company(1)
    print(f"\nCustomers for company 1 ({len(all_custs)}):")
    for c in all_custs:
        print(f"  [{c['id']}] {c['name']}")

    # Clean up
    delete(cust["id"], company_id=1)
    print("\nCleaned up test customer.")
