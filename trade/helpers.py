"""
Trade AI Assistant — shared helper functions.

Provider checking and agent-kwarg construction, factored out so the
/chat and /chat/stream endpoints don't duplicate ~90 lines each.
"""

import os

from trade import prompts as _prompts


def check_provider() -> str | None:
    """Check if an LLM provider and API key are configured.

    Returns an error message string if something is missing, or None if OK.
    Must be called AFTER ``import run_agent`` (which triggers .env loading).
    """
    from hermes_cli.config import load_config

    cfg = load_config()
    model_cfg = cfg.get("model", "")
    if isinstance(model_cfg, dict):
        if not model_cfg.get("default") and not model_cfg.get("provider"):
            return "未配置 AI 模型。请先运行 trade setup 选择模型。"
    elif not model_cfg:
        return "未配置 AI 模型。请先运行 trade setup 选择模型。"

    has_key = any(
        os.getenv(k)
        for k in (
            "OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
            "MINIMAX_API_KEY", "MINIMAX_CN_API_KEY", "DEEPSEEK_API_KEY",
            "GLM_API_KEY", "KIMI_API_KEY", "DASHSCOPE_API_KEY",
            "LLM_API_KEY", "HF_TOKEN",
        )
    )
    if not has_key:
        return "未检测到 API Key。请在 ~/.hermes/.env 中设置，或运行 trade setup 重新配置。"
    return None


def get_agent_kwargs() -> dict:
    """Build the keyword arguments for ``AIAgent.__init__`` from config.

    Resolves provider, model, base_url, and api_key — including env-var
    overrides for base_url and per-provider API key lookups via the auth
    registry.

    Returns a dict with keys: provider, model, base_url, api_key.
    All values are strings (may be empty).
    """
    from hermes_cli.config import load_config

    cfg = load_config()
    model_cfg = cfg.get("model", {})

    if not isinstance(model_cfg, dict):
        return {"provider": "", "model": str(model_cfg) if model_cfg else "",
                "base_url": "", "api_key": ""}

    provider = model_cfg.get("provider", "")
    model = model_cfg.get("default", "")
    base_url = model_cfg.get("base_url", "")

    # ── base_url: env var overrides config.yaml ──────────────────────────
    env_url = os.getenv("MINIMAX_CN_BASE_URL", "").strip()
    if not env_url and provider:
        try:
            from hermes_cli.auth import PROVIDER_REGISTRY
            pconfig = PROVIDER_REGISTRY.get(provider)
            if pconfig and hasattr(pconfig, 'base_url_env_var'):
                brv = getattr(pconfig, 'base_url_env_var', '')
                if brv:
                    env_url = os.getenv(brv, "").strip()
        except Exception:
            pass
    if env_url:
        base_url = env_url

    # ── api_key: per-provider → common fallback ──────────────────────────
    api_key = os.getenv("MINIMAX_CN_API_KEY", "").strip()
    if not api_key and provider:
        try:
            from hermes_cli.auth import PROVIDER_REGISTRY
            pconfig = PROVIDER_REGISTRY.get(provider)
            if pconfig and pconfig.auth_type == "api_key":
                for env_name in pconfig.api_key_env_vars:
                    api_key = os.getenv(env_name, "").strip()
                    if api_key:
                        break
        except Exception:
            pass
    if not api_key:
        api_key = (
            os.getenv("OPENAI_API_KEY", "").strip()
            or os.getenv("OPENROUTER_API_KEY", "").strip()
            or os.getenv("ANTHROPIC_API_KEY", "").strip()
            or ""
        )

    return {"provider": provider, "model": model,
            "base_url": base_url, "api_key": api_key}


# ── Token estimation helpers ──────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    """Rough token estimate: Chinese ~1.5 chars/token, English ~4 chars/token."""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    non_chinese = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + non_chinese * 0.25)


def _get_history_block(company_id: int, total_prompt_chars: int) -> tuple[str, int]:
    """Build history injection block based on total prompt size.

    Returns (history_block, history_token_count).
    history_block is empty if company_id is None.
    """
    if not company_id:
        return "", 0

    from trade import chat_memory as _cm

    # Token thresholds (hard-coded, not user-visible)
    if total_prompt_chars < 80_000:      # ~< 20k tokens
        limit = 20
        hint = None
    elif total_prompt_chars < 200_000:   # ~< 50k tokens
        limit = 10
        hint = "如需更早的对话历史，请使用 chat_memory_list 工具。"
    else:                                # >= 50k tokens
        limit = 5
        hint = "当前上下文较长，历史对话已精简。如需查询更早内容，请使用 chat_memory_list 工具。"

    rows = _cm.get_recent(company_id, limit=limit)
    if not rows:
        return "", 0

    lines = ["## 最近对话历史"]
    for row in rows:
        ts = row.get("created_at", "")[:16]  # YYYY-MM-DD HH:MM
        lines.append(f"[{ts}] user: {row['query'][:200]}")
        if row.get("response"):
            lines.append(f"[{ts}] assistant: {row['response'][:200]}")
    block = "\n".join(lines) + "\n"

    if hint:
        block += f"\n{hint}\n"

    return block, _estimate_tokens(block)

def build_query(company_id: int, library_id: int | None, query: str) -> str:
    """Assemble the full prompt with company identity + doc context + skill injection.

    company_id determines which company identity is injected into the system prompt.
    library_id optionally adds document-library context.
    query is first passed through skill_router.augment_query() which detects
    which b2b-* skill should be triggered (even from vague/abbreviated input)
    and prepends a precise skill augmentation block.
    """
    from trade import library as _lib
    from trade import company as _company
    from trade import skill_router

    # 0. Skill auto-detection — must happen before anything else so the LLM
    #    knows which tool/function to call even when the user's prompt is vague.
    #    augment_query() returns query unchanged if no skill matches (fast dict
    #    lookup, no latency added in that case).
    augmented_query = skill_router.augment_query(
        query, company_id=company_id
    )

    # 1. Company identity — resolved from file (highest priority) + DB cache fallback
    #    company_slug is derived from company_id; fall back to DB value if file doesn't exist
    company_slug = _company.slug_from_id(company_id) if company_id else None
    db_identity = _company.get_agent_identity(company_id) if company_id else None
    system_prompt = _prompts.resolve_system_prompt(
        company_slug=company_slug,
        db_identity=db_identity,
    )

    # 2. Library document context
    doc_context = ""
    if library_id:
        lib = _lib.get(library_id, company_id=company_id)
        if lib:
            doc_context = (
                f"\n[上下文] 用户正在文档库「{lib['name']}」({lib['root_path']}) "
                "中提问。必要时使用 read_file 读取目录中的文件。"
            )

    # 3. History block (injected before the query, sized by token budget)
    pre_history_chars = (
        len(system_prompt) + len(doc_context) +
        len(augmented_query) + 200
    )
    history_block, _ = _get_history_block(company_id, pre_history_chars)

    # 4. Assemble final prompt
    final_prompt = system_prompt + doc_context
    if history_block:
        final_prompt = f"{final_prompt}\n\n{history_block}"

    return f"{final_prompt}\n\n{augmented_query}"
