"""
Trade AI Assistant — Chat memory / conversation log.

Stores queries, responses, and which files were read during an agent session.
Optionally retains conversation turns to Hindsight long-term memory when
available (requires hindsight-client package and API key).

All operations are scoped to a company_id for multi-tenancy isolation.
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
    """Save a conversation turn scoped to a company. Returns the new row as a dict."""
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
    """Return recent conversations for a company, newest first."""
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
    """Return recent conversations for a library within a company, newest first."""
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
    """Get a single conversation by id, scoped to a company."""
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
    """Update the response field for a conversation."""
    conn = get_connection()
    try:
        n = conn.execute(
            "UPDATE conversations SET response = ? WHERE id = ? AND company_id = ?",
            (response, conversation_id, company_id),
        ).rowcount
        conn.commit()
        if n == 0:
            return None
        return get(company_id, conversation_id)
    finally:
        conn.close()


def delete(company_id: int, conversation_id: int) -> bool:
    """Delete a conversation record scoped to a company."""
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


# ── Hindsight integration ───────────────────────────────────────────────────

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
    """Save a conversation turn to SQLite + optionally to Hindsight memory.

    This is the recommended entry point for B2B conversation logging.
    """
    result = save(company_id, query, response, library_id, files_read)

    if retain_to_memory:
        try:
            from trade import company as _company
            from trade.memory import retain_conversation, retain_to_hermes_memory

            # Hindsight memory (API key required — fire and forget)
            try:
                retained = retain_conversation(
                    query=query,
                    response=response,
                    library_name=library_name,
                    customer_name=customer_name,
                )
                if retained:
                    logger.debug("Conversation %d retained to Hindsight", result["id"])
            except Exception as exc:
                logger.debug("Hindsight retain skipped: %s", exc)

            # Hermes native memory (always available — fire and forget)
            try:
                company_name = ""
                if company_id:
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
            pass  # trade.memory not available
        except Exception as exc:
            logger.debug("Memory retain skipped: %s", exc)

    return result


def recall_context(query: str) -> str:
    """Search Hindsight for relevant past conversations.

    Returns empty string if Hindsight is unavailable or no results found.
    """
    try:
        from trade.memory import recall

        result = recall(query, bank_id="trade")
        return result or ""
    except ImportError:
        return ""
    except Exception:
        return ""


# ── helpers ──────────────────────────────────────────────────────────────────


def get_recent(company_id: int, limit: int = 20) -> list[dict]:
    """Get the most recent N conversation turns for context injection.

    Returns list of dicts with keys: id, query, response, created_at.
    Ordered newest-first, limit N rows.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, company_id, library_id, query, response, files_read, created_at "
            "FROM conversations WHERE company_id = ? AND query IS NOT NULL "
            "ORDER BY id DESC LIMIT ?",
            (company_id, limit),
        ).fetchall()
        # Reverse to get chronological order (oldest first for context)
        return [_row_to_dict(r) for r in reversed(rows)]
    finally:
        conn.close()


def search_history(
    company_id: int,
    time_range: str = "all",
    limit: int = 20,
) -> list[dict]:
    """Query historical conversations by time range (for LLM tool call).

    Args:
        company_id: scope to company
        time_range: "today" | "this_week" | "this_month" | "all"
        limit: max rows returned

    Returns:
        List of dicts with id, query, response, created_at.
    """
    conn = get_connection()
    try:
        import datetime as _dt
        now = _dt.datetime.now()
        if time_range == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == "this_week":
            start = now - _dt.timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == "this_month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # "all"
            start = None

        if start:
            start_str = start.strftime("%Y-%m-%d %H:%M:%S")
            rows = conn.execute(
                "SELECT id, company_id, library_id, query, response, files_read, created_at "
                "FROM conversations WHERE company_id = ? AND created_at >= ? "
                "ORDER BY id ASC LIMIT ?",
                (company_id, start_str, limit),
            ).fetchall()
        else:
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
    return {
        "id": row["id"],
        "company_id": row["company_id"],
        "library_id": row["library_id"],
        "query": row["query"],
        "response": row["response"],
        "files_read": json.loads(row["files_read"]) if row["files_read"] else [],
        "created_at": row["created_at"],
    }


# ── CLI smoke test ───────────────────────────────────────────────────────────

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
