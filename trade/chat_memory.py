"""
Trade AI Assistant — 聊天记忆 / 对话记录。

存储 Agent 会话期间的查询、回复以及读取的文件。
可选地将对话轮次保留到 Hindsight 长期记忆（需要 hindsight-client 包和 API 密钥）。

所有操作均通过 company_id 隔离，实现多租户数据隔离。
"""

import json
import logging

from trade.database import get_connection

logger = logging.getLogger(__name__)


def save(
    company_id: int | None,
    query: str,
    response: str = "",
    library_id: int | None = None,
    files_read: list[dict] | None = None,
) -> dict:
    """保存一条对话记录，作用域限定到指定公司。返回新插入的行，以字典形式呈现。"""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO conversations (company_id, library_id, query, response, files_read) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                company_id,
                library_id,
                query,
                response,
                json.dumps(files_read or [], ensure_ascii=False),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_by_company(company_id: int, limit: int = 50) -> list[dict]:
    """返回指定公司最近的对话记录，按最新在前排序。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE company_id = ? ORDER BY id DESC LIMIT ?",
            (company_id, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_by_library(
    company_id: int, library_id: int, limit: int = 50
) -> list[dict]:
    """返回指定公司内某个资料库最近的对话记录，按最新在前排序。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE company_id = ? AND library_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (company_id, library_id, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get(company_id: int, conversation_id: int) -> dict | None:
    """根据 ID 获取单条对话记录，作用域限定到公司。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ? AND company_id = ?",
            (conversation_id, company_id),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_response(company_id: int, conversation_id: int, response: str) -> dict | None:
    """更新一条对话记录的回复字段。"""
    conn = get_connection()
    try:
        n = conn.execute(
            "UPDATE conversations SET response = ? WHERE id = ? AND company_id = ?",
            (response, conversation_id, company_id),
        ).rowcount
        conn.commit()
        if n == 0:
            # 没有行被更新，说明指定 ID 的记录不存在或不属于该公司
            return None
        return get(company_id, conversation_id)
    finally:
        conn.close()


def delete(company_id: int, conversation_id: int) -> bool:
    """删除一条对话记录，作用域限定到公司。"""
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM conversations WHERE id = ? AND company_id = ?",
            (conversation_id, company_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── Hindsight 集成 ───────────────────────────────────────────────────

def save_with_context(
    company_id: int | None,
    query: str,
    response: str = "",
    library_id: int | None = None,
    files_read: list[dict] | None = None,
    *,
    library_name: str = "",
    customer_name: str = "",
    retain_to_memory: bool = True,
) -> dict:
    """保存一条对话记录到 SQLite，并可选择同步到 Hindsight 长期记忆。

    这是 B2B 对话日志记录推荐使用的入口函数。
    """
    result = save(company_id, query, response, library_id, files_read)

    if retain_to_memory:
        # 只有当调用方要求保留到记忆时才执行，避免不必要的 I/O
        try:
            from trade import company as _company
            from trade.memory import retain_conversation, retain_to_hermes_memory

            # Hindsight 记忆（需要 API 密钥 —— 即发即忘，失败不影响主流程）
            try:
                retained = retain_conversation(
                    query=query,
                    response=response,
                    library_name=library_name,
                    customer_name=customer_name,
                )
                if retained:
                    # 成功保留日志后记录调试信息，便于排查记忆同步问题
                    logger.debug("Conversation %d retained to Hindsight", result["id"])
            except Exception as exc:
                logger.debug("Hindsight retain skipped: %s", exc)

            # Hermes 原生记忆（始终可用 —— 即发即忘，失败不影响主流程）
            try:
                company_name = ""
                if company_id:
                    # 根据公司 ID 查询公司名称，用于在记忆上下文中标识来源
                    co = _company.get(company_id)
                    if co:
                        company_name = co.get("name", "")
                retain_to_hermes_memory(
                    query=query,
                    response=response,
                    company_name=company_name,
                    library_name=library_name,
                    customer_name=customer_name,
                )
            except Exception as exc:
                logger.debug("Hermes memory retain skipped: %s", exc)

        except ImportError:
            pass  # trade.memory 模块未安装，跳过记忆保留
        except Exception as exc:
            logger.debug("Memory retain skipped: %s", exc)

    return result


def recall_context(query: str) -> str:
    """搜索 Hindsight 长期记忆以获取相关的历史对话记录。

    如果 Hindsight 不可用或未找到匹配结果，则返回空字符串。
    """
    try:
        from trade.memory import recall

        result = recall(query, bank_id="trade")
        return result or ""
    except ImportError:
        return ""
    except Exception:
        return ""


# ── 辅助函数 ──────────────────────────────────────────────────────────


def get_recent(company_id: int, limit: int = 20) -> list[dict]:
    """获取最近的 N 条对话记录，用于上下文注入。

    返回字典列表，包含键：id, query, response, created_at。
    数据库查询按最新在前排序，返回时反转以确保上下文按时间正序排列。
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, company_id, library_id, query, response, files_read, created_at "
            "FROM conversations WHERE company_id = ? AND query IS NOT NULL "
            "ORDER BY id DESC LIMIT ?",
            (company_id, limit),
        ).fetchall()
        # 反转排序，使得最早的在最前，适合作为对话上下文输入给 LLM
        return [_row_to_dict(r) for r in reversed(rows)]
    finally:
        conn.close()


def search_history(
    company_id: int,
    time_range: str = "all",
    limit: int = 20,
) -> list[dict]:
    """按时间范围查询历史对话记录（供 LLM 工具调用使用）。

    Args:
        company_id: 作用域，限定到公司
        time_range: "today" | "this_week" | "this_month" | "all"
        limit: 最大返回行数

    Returns:
        字典列表，包含 id, query, response, created_at。
    """
    conn = get_connection()
    try:
        import datetime as _dt
        now = _dt.datetime.now()
        if time_range == "today":
            # 当天的 00:00:00 作为起始时间
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == "this_week":
            # 本周一 00:00:00 作为起始时间（周一 = weekday=0）
            start = now - _dt.timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == "this_month":
            # 本月 1 号的 00:00:00 作为起始时间
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # "all"
            # 查询全部历史，不设时间过滤
            start = None

        if start:
            # 有时间范围限制，添加 created_at >= start 的过滤条件
            start_str = start.strftime("%Y-%m-%d %H:%M:%S")
            rows = conn.execute(
                "SELECT id, company_id, library_id, query, response, files_read, created_at "
                "FROM conversations WHERE company_id = ? AND created_at >= ? "
                "ORDER BY id ASC LIMIT ?",
                (company_id, start_str, limit),
            ).fetchall()
        else:
            # 无时间范围限制，查询该公司的所有历史记录
            rows = conn.execute(
                "SELECT id, query, response, created_at "
                "FROM conversations WHERE company_id = ? "
                "ORDER BY id ASC LIMIT ?",
                (company_id, limit),
            ).fetchall()

        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def _row_to_dict(row) -> dict:
    """将 SQLite 行对象转换为字典，同时将 files_read JSON 字段反序列化。"""
    return {
        "id": row["id"],
        "company_id": row["company_id"],
        "library_id": row["library_id"],
        "query": row["query"],
        "response": row["response"],
        "files_read": json.loads(row["files_read"]) if row["files_read"] else [],
        "created_at": row["created_at"],
    }


# ── CLI 冒烟测试 ───────────────────────────────────────────────────────

if __name__ == "__main__":
    from trade.database import init_db

    init_db()

    conv = save(
        company_id=1,
        library_id=None,
        query="去年营收怎么样？",
        response="根据2024年度销售额数据...",
        files_read=[{"file": "2024_report.xlsx", "pages": [1, 2]}],
    )
    print("Saved:", json.dumps(conv, indent=2, ensure_ascii=False))

    recent = list_by_company(1, 5)
    print(f"\nRecent for company 1 ({len(recent)}):")
    for c in recent:
        print(f"  [{c['id']}] {c['query'][:40]}...")

    delete(1, conv["id"])
    print("\nCleaned up test conversation.")
