"""
Trade AI Assistant — Memory bridge (Hindsight integration).

Provides a lightweight bridge between trade/chat_memory and the
Hindsight long-term memory backend. Works independently of the
Hermes Agent runtime (does not require MemoryManager).

When hindsight-client is installed and configured, conversation turns
are automatically retained to the knowledge graph for cross-session recall.
Otherwise, this module degrades gracefully to no-ops.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ── Hindsight detection ──────────────────────────────────────────────────────

_hindsight_available: bool | None = None  # tri-state: None=unchecked


def is_available() -> bool:
    """Check whether Hindsight is installed and configured."""
    global _hindsight_available
    if _hindsight_available is not None:
        return _hindsight_available

    try:
        import importlib
        importlib.import_module("hindsight_client")
        has_key = bool(
            os.environ.get("HINDSIGHT_API_KEY", "")
            or os.environ.get("HINDSIGHT_LLM_API_KEY", "")
        )
        if not has_key:
            # Check config file
            from pathlib import Path
            config_paths = [
                Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "hindsight" / "config.json",
                Path.home() / ".hindsight" / "config.json",
            ]
            for p in config_paths:
                if p.exists():
                    try:
                        cfg = json.loads(p.read_text())
                        if cfg.get("apiKey") or cfg.get("api_key") or cfg.get("mode") == "local_embedded":
                            has_key = True
                            break
                    except Exception:
                        pass
        _hindsight_available = has_key
    except ImportError:
        _hindsight_available = False

    return _hindsight_available


# ── Client (lazy-init, reused) ──────────────────────────────────────────────

_client: Any = None


def _get_client():
    """Return a cached Hindsight client, or None if unavailable."""
    global _client
    if not is_available():
        return None
    if _client is not None:
        return _client

    try:
        from hermes_constants import get_hermes_home
        from hindsight_client import Hindsight

        api_key = os.environ.get("HINDSIGHT_API_KEY", "")
        api_url = os.environ.get("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
        timeout = int(os.environ.get("HINDSIGHT_TIMEOUT", "120"))

        # Try profile-scoped config
        config_path = get_hermes_home() / "hindsight" / "config.json"
        if config_path.exists():
            cfg = json.loads(config_path.read_text())
            api_key = api_key or cfg.get("apiKey", "") or cfg.get("api_key", "")
            api_url = cfg.get("api_url", api_url)
            timeout = int(cfg.get("timeout", timeout))

        if not api_key:
            logger.debug("Hindsight: no API key configured, client not created")
            return None

        _client = Hindsight(
            base_url=api_url,
            api_key=api_key,
            timeout=float(timeout),
        )
        logger.info("Hindsight client connected: %s", api_url)
    except Exception as exc:
        logger.warning("Hindsight client init failed: %s", exc)
        _client = None

    return _client


# ── Public API ──────────────────────────────────────────────────────────────

def retain(
    content: str,
    context: str = "",
    *,
    bank_id: str = "trade",
    document_id: str | None = None,
    tags: list[str] | None = None,
) -> bool:
    """Store information to Hindsight long-term memory.

    Returns True on success, False if Hindsight is unavailable.
    """
    client = _get_client()
    if client is None:
        return False

    try:
        metadata = {"source": "trade-ai-assistant"}
        kwargs: dict[str, Any] = {
            "bank_id": bank_id,
            "content": content,
            "metadata": metadata,
        }
        if context:
            kwargs["context"] = context
        if document_id:
            kwargs["document_id"] = document_id
        if tags:
            kwargs["tags"] = tags

        client.retain(**kwargs)
        logger.debug("Hindsight retain: bank=%s, content_len=%d, context=%s",
                      bank_id, len(content), context or "(none)")
        return True
    except Exception as exc:
        logger.warning("Hindsight retain failed: %s", exc)
        return False


def recall(
    query: str,
    *,
    bank_id: str = "trade",
    budget: str = "mid",
    max_tokens: int = 4096,
) -> str | None:
    """Search Hindsight long-term memory.

    Returns formatted memory text, or None if unavailable.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        resp = client.recall(
            bank_id=bank_id,
            query=query,
            budget=budget,
            max_tokens=max_tokens,
        )
        if not resp.results:
            return None
        lines = [f"- {r.text}" for r in resp.results if r.text]
        return "\n".join(lines) if lines else None
    except Exception as exc:
        logger.warning("Hindsight recall failed: %s", exc)
        return None


def reflect(
    query: str,
    *,
    bank_id: str = "trade",
    budget: str = "mid",
) -> str | None:
    """Synthesize an answer from Hindsight long-term memories.

    Returns synthesized text, or None if unavailable.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        resp = client.reflect(bank_id=bank_id, query=query, budget=budget)
        return resp.text or None
    except Exception as exc:
        logger.warning("Hindsight reflect failed: %s", exc)
        return None


def retain_conversation(
    query: str,
    response: str,
    *,
    library_name: str = "",
    customer_name: str = "",
    bank_id: str = "trade",
) -> bool:
    """Push a complete conversation turn to Hindsight memory.

    Formats the Q&A pair and annotates with library/customer context.
    """
    content_parts = [f"Q: {query}", f"A: {response}"]
    context = "B2B trade conversation"
    if library_name:
        context += f" — library: {library_name}"
    if customer_name:
        context += f" — customer: {customer_name}"
    content = "\n".join(content_parts)
    return retain(content, context=context, bank_id=bank_id)


def retain_to_hermes_memory(
    query: str,
    response: str,
    *,
    company_name: str = "",
    library_name: str = "",
    customer_name: str = "",
    limit: int = 200,
) -> bool:
    """Append a conversation summary to ~/.hermes/memories/MEMORY.md.

    This lets the Hermes Agent's native memory system learn about B2B trade
    conversations without requiring any API key.
    """
    import datetime as _dt
    from pathlib import Path as _Path

    MEMORY_FILE = _Path.home() / ".hermes/memories/MEMORY.md"
    LOCK_FILE = _Path.home() / ".hermes/memories/MEMORY.md.lock"

    if not query or not query.strip():
        return False

    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    q_preview = query.strip()[:limit]
    r_preview = (response or "").strip()[:limit]

    context_parts = []
    if company_name:
        context_parts.append("\u516c\u53f8: " + company_name)
    if library_name:
        context_parts.append("\u8d44\u6599\u5e93: " + library_name)
    if customer_name:
        context_parts.append("\u5ba2\u6237: " + customer_name)

    if context_parts:
        context_str = " [" + ", ".join(context_parts) + "]"
    else:
        context_str = ""

    entry_lines = [
        "[" + now + "]" + context_str,
        "  Q: " + q_preview,
        "  A: " + r_preview,
        "",
    ]
    entry = "\n".join(entry_lines)

    try:
        # 跨平台文件锁：用临时锁文件存在性 + 短重试替代 fcntl (仅 Unix)
        import time as _time
        for _attempt in range(5):
            if not LOCK_FILE.exists():
                try:
                    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
                    break
                except OSError:
                    _time.sleep(0.05)
            else:
                _time.sleep(0.05)
        else:
            return False  # 无法获取锁

        try:
            existing = ""
            if MEMORY_FILE.exists():
                existing = MEMORY_FILE.read_text(encoding="utf-8")
            SECTION = "## Foreign Trade Assistant \u2014 B2B Trade Memory\n"
            if SECTION not in existing:
                content_str = SECTION + entry + "\n\n" + existing if existing else SECTION + entry
            else:
                idx_s = existing.find(SECTION) + len(SECTION)
                content_str = existing[:idx_s] + entry + "\n\n" + existing[idx_s:]
            MEMORY_FILE.write_text(content_str, encoding="utf-8")
        finally:
            try:
                LOCK_FILE.unlink(missing_ok=True)
            except OSError:
                pass
        return True
    except Exception:
        return False

