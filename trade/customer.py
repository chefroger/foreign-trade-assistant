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
    *,
    country: str = "",
    tier: str = "",
    linkedin_url: str = "",
    company_website: str = "",
    social_media: Optional[dict] = None,
    title: str = "",
    email: str = "",
    backup_email: str = "",
    phone: str = "",
    whatsapp: str = "",
    wechat: str = "",
    source: str = "",
) -> dict:
    """Create a customer scoped to a company. Returns the new row as a dict."""
    import json as _json
    extra1 = _json.dumps({
        "country": country,
        "tier": tier,
        "linkedin_url": linkedin_url,
        "company_website": company_website,
        "social_media": social_media or {},
    }, ensure_ascii=False)
    extra2 = _json.dumps({
        "title": title,
        "email": email,
        "backup_email": backup_email,
        "phone": phone,
        "whatsapp": whatsapp,
        "wechat": wechat,
        "source": source,
    }, ensure_ascii=False)

    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO customers (company_id, name, contact, note, extra1, extra2) VALUES (?, ?, ?, ?, ?, ?)",
            (company_id, name, contact, note, extra1, extra2),
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
    """Update customer fields（单事务，部分失败统一回滚）。

    基础字段: name, contact, note
    extra1 字段: country, tier, linkedin_url, company_website, social_media
    extra2 字段: email, backup_email, phone, whatsapp, wechat, source, last_contact_at
    """
    import json as _json

    extra1_keys = {"country", "tier", "linkedin_url", "company_website", "social_media"}
    extra2_keys = {"title", "email", "backup_email", "phone", "whatsapp", "wechat", "source", "last_contact_at"}
    basic_allowed = {"name", "contact", "note"}

    extra1_updates = {k: v for k, v in kwargs.items() if k in extra1_keys and v is not None}
    extra2_updates = {k: v for k, v in kwargs.items() if k in extra2_keys and v is not None}
    basic_updates = {k: v for k, v in kwargs.items() if k in basic_allowed and v is not None}

    if not (extra1_updates or extra2_updates or basic_updates):
        return get(customer_id, company_id)

    conn = get_connection()
    try:
        # 显式事务
        conn.execute("BEGIN")

        # 读取当前 JSON 用于合并
        row = conn.execute(
            "SELECT extra1, extra2 FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        if row is None:
            conn.rollback()
            return None
        current_extra1 = _json.loads(row["extra1"]) if row["extra1"] else {}
        current_extra2 = _json.loads(row["extra2"]) if row["extra2"] else {}

        # 合并 extra1
        if extra1_updates:
            current_extra1.update(extra1_updates)
            conn.execute(
                "UPDATE customers SET extra1 = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (_json.dumps(current_extra1, ensure_ascii=False), customer_id),
            )

        # 合并 extra2
        if extra2_updates:
            current_extra2.update(extra2_updates)
            conn.execute(
                "UPDATE customers SET extra2 = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (_json.dumps(current_extra2, ensure_ascii=False), customer_id),
            )

        # 基础字段
        if basic_updates:
            set_clause = ", ".join(f"{k} = ?" for k in basic_updates)
            values = list(basic_updates.values()) + [customer_id]
            sql = f"UPDATE customers SET {set_clause}, updated_at = datetime('now','localtime') WHERE id = ?"
            if company_id is not None:
                sql += " AND company_id = ?"
                values.append(company_id)
            n = conn.execute(sql, values).rowcount
            if n == 0:
                conn.rollback()
                return None

        conn.commit()
        return get(customer_id, company_id)
    except Exception:
        conn.rollback()
        raise
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

def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "company_id": row["company_id"],
        "name": row["name"],
        "contact": row["contact"],
        "note": row["note"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _library_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "company_id": row["company_id"],
        "name": row["name"],
        "root_path": row["root_path"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ── 批量保存客户（Agent 可调用）────────────────────────────────────────────────

def bulk_save(
    company_id: int,
    customers: list[dict],
    *,
    library_id: int | None = None,
) -> dict:
    """批量导入客户列表，自动跳过已存在的同名客户。

    Agent 从对话或文档中提取客户信息后，可调用此函数批量写入数据库。

    Args:
        company_id: 公司 ID
        customers: 客户字典列表，每个可含:
            name (必填), contact, note, country, tier, linkedin_url,
            company_website, social_media (dict), email, backup_email,
            phone, whatsapp, wechat, source
        library_id: 如果从文档库扫描提取，自动关联此文档库

    Returns:
        {"created": N, "skipped": N, "total": N}
    """
    created = 0
    skipped = 0

    existing_names = {c["name"].lower() for c in list_by_company(company_id)}

    for cust in customers:
        name = (cust.get("name") or "").strip()
        if not name:
            skipped += 1
            continue

        if name.lower() in existing_names:
            skipped += 1
            continue

        result = create(
            name=name,
            contact=cust.get("contact", ""),
            note=cust.get("note", ""),
            company_id=company_id,
            country=cust.get("country", ""),
            tier=cust.get("tier", ""),
            linkedin_url=cust.get("linkedin_url", ""),
            company_website=cust.get("company_website", ""),
            social_media=cust.get("social_media"),
            title=cust.get("title", ""),
            email=cust.get("email", ""),
            backup_email=cust.get("backup_email", ""),
            phone=cust.get("phone", ""),
            whatsapp=cust.get("whatsapp", ""),
            wechat=cust.get("wechat", ""),
            source=cust.get("source", "agent"),
        )

        # 如果指定了文档库，自动关联
        if library_id:
            try:
                link_library(result["id"], library_id, company_id)
            except ValueError:
                pass

        existing_names.add(name.lower())
        created += 1

    return {"created": created, "skipped": skipped, "total": created + skipped}


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
