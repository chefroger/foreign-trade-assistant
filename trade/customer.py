"""
Trade AI Assistant — 客户管理模块。

B2B 客户 CRUD，支持可选的文档库关联。
所有操作均受 company_id 作用域限制，实现多租户隔离。
"""

import json

from trade.database import get_connection


def create(
    name: str,
    contact: str = "",
    note: str = "",
    company_id: int | None = None,
    *,
    country: str = "",
    tier: str = "",
    linkedin_url: str = "",
    company_website: str = "",
    social_media: dict | None = None,
    title: str = "",
    email: str = "",
    backup_email: str = "",
    phone: str = "",
    whatsapp: str = "",
    wechat: str = "",
    source: str = "",
) -> dict:
    """创建一条归属于指定公司的客户记录。返回新行的字典表示。"""
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
    """返回指定公司的所有客户，按最新创建排在前面。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM customers WHERE company_id = ? ORDER BY id DESC",
            (company_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get(customer_id: int, company_id: int | None = None) -> dict | None:
    """根据 ID 获取单个客户，可选地按公司作用域限制。"""
    conn = get_connection()
    try:
        if company_id is not None:
            # 如果传入了公司ID，则同时校验客户ID和公司ID，防止跨公司读取
            row = conn.execute(
                "SELECT * FROM customers WHERE id = ? AND company_id = ?",
                (customer_id, company_id),
            ).fetchone()
        else:
            # 未传入公司ID时，仅按客户ID查询（用于不要求多租户隔离的场景）
            row = conn.execute(
                "SELECT * FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update(
    customer_id: int,
    company_id: int | None = None,
    **kwargs,
) -> dict | None:
    """更新客户字段（单事务，部分失败统一回滚）。

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
        # 没有需要更新的字段，直接返回当前客户数据
        return get(customer_id, company_id)

    conn = get_connection()
    try:
        # 显式事务
        conn.execute("BEGIN")

        # 读取当前 JSON 用于合并（必须加 company_id 校验，防止跨公司写 extra）
        if company_id is not None:
            row = conn.execute(
                "SELECT extra1, extra2 FROM customers WHERE id = ? AND company_id = ?",
                (customer_id, company_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT extra1, extra2 FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
        if row is None:
            # 客户不存在，回滚事务并返回 None
            conn.rollback()
            return None
        current_extra1 = _json.loads(row["extra1"]) if row["extra1"] else {}
        current_extra2 = _json.loads(row["extra2"]) if row["extra2"] else {}

        # 构造 WHERE 子句（company_id 贯穿所有写操作）
        where_clause = "id = ? AND company_id = ?" if company_id is not None else "id = ?"
        where_params = [customer_id] if company_id is None else [customer_id, company_id]

        # 合并 extra1
        if extra1_updates:
            # 将新字段合并到现有的 extra1 JSON 中，避免覆盖未涉及的字段
            current_extra1.update(extra1_updates)
            conn.execute(
                f"UPDATE customers SET extra1 = ?, updated_at = datetime('now','localtime') WHERE {where_clause}",
                (_json.dumps(current_extra1, ensure_ascii=False), *where_params),
            )

        # 合并 extra2
        if extra2_updates:
            # 将新字段合并到现有的 extra2 JSON 中，避免覆盖未涉及的字段
            current_extra2.update(extra2_updates)
            conn.execute(
                f"UPDATE customers SET extra2 = ?, updated_at = datetime('now','localtime') WHERE {where_clause}",
                (_json.dumps(current_extra2, ensure_ascii=False), *where_params),
            )

        # 基础字段
        if basic_updates:
            # 动态构造 SET 子句，只更新非空的基础字段
            set_clause = ", ".join(f"{k} = ?" for k in basic_updates)
            values = list(basic_updates.values()) + where_params
            sql = f"UPDATE customers SET {set_clause}, updated_at = datetime('now','localtime') WHERE {where_clause}"
            n = conn.execute(sql, values).rowcount
            if n == 0:
                # 更新影响行数为0，说明记录不存在或已被删除，回滚事务
                conn.rollback()
                return None

        conn.commit()
        return get(customer_id, company_id)
    except Exception:
        # 任何异常均回滚，保证事务原子性
        conn.rollback()
        raise
    finally:
        conn.close()


def delete(customer_id: int, company_id: int | None = None) -> bool:
    """按公司作用域删除客户。如果删除了行则返回 True。"""
    conn = get_connection()
    try:
        if company_id is not None:
            # 带公司ID校验的删除，防止跨公司误删
            cur = conn.execute(
                "DELETE FROM customers WHERE id = ? AND company_id = ?",
                (customer_id, company_id),
            )
        else:
            # 无公司ID限制的删除（用于不要求多租户隔离的场景）
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
    """将文档库关联到客户（两者必须属于同一公司）。

    成功返回 True；如果客户或文档库在给定公司下不存在，则抛出 ValueError。
    """
    # Verify both belong to the company
    cust = get(customer_id, company_id)
    if not cust:
        # 客户在指定公司下不存在，拒绝关联以防止跨公司操作
        raise ValueError(f"Customer {customer_id} not found under company {company_id}")

    from trade.library import get as get_library

    lib = get_library(library_id, company_id)
    if not lib:
        # 文档库在指定公司下不存在，拒绝关联
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
    """按公司作用域移除客户与文档库的关联关系。"""
    conn = get_connection()
    try:
        # Verify ownership before unlinking
        cust = get(customer_id, company_id)
        if not cust:
            # 客户在指定公司下不存在，视为操作不存在，返回 False
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
    """返回与客户关联的所有文档库，按公司作用域限制。"""
    # Verify customer belongs to company
    cust = get(customer_id, company_id)
    if not cust:
        # 客户不属于该公司，返回空列表而非报错，保证调用方流程不受阻
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
            # 客户名称为空，跳过此条记录
            skipped += 1
            continue

        if name.lower() in existing_names:
            # 同名客户已存在，跳过以避免重复
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
                # 关联失败（如文档库不存在）时静默跳过，不影响其他客户的导入
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
