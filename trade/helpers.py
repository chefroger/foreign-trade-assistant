"""
Trade AI Assistant — 共享辅助函数。

集中了 Provider 校验和 Agent 构造参数逻辑，避免 /chat 和 /chat/stream
两个端点各自重复约 90 行代码。
"""

import os

from trade import prompts as _prompts

# ── Config.model compat ───────────────────────────────────────────────────────

def _parse_model_config_str(raw: str) -> tuple[str, str, str]:
    """解析 v0.14 平铺模型配置字符串，返回 (provider, model, base_url)。

    支持两种格式：
      - "provider:model"     (冒号分隔，语义明确)
      - "provider/model/..." (斜杠分隔，例如 openrouter/anthropic/claude-sonnet-4)

    base_url 在该平铺格式中始终返回空字符串。
    """
    if not raw or not raw.strip():
        # 传入空字符串或 None 时返回全部空值
        return "", "", ""
    raw = raw.strip()
    # colon 优先，语义更精确
    if ":" in raw:
        provider, _, model = raw.partition(":")
        return provider.strip(), model.strip(), ""
    elif "/" in raw:
        parts = raw.split("/", 1)
        provider = parts[0].strip()
        model = parts[1].strip() if len(parts) > 1 else ""
        return provider, model, ""
    else:
        # 既无冒号也无斜杠，整个字符串作为 model 名
        return "", raw, ""


def check_provider() -> str | None:
    """检查 LLM provider 和 API key 是否已配置。

    如果缺少配置则返回错误信息字符串，配置正常则返回 None。
    必须在 ``import run_agent``（该操作会触发 .env 加载）之后调用。
    """
    from hermes_cli.config import load_config

    cfg = load_config()
    model_cfg = cfg.get("model", "")
    # 兼容 v0.13 (dict) 和 v0.14+ (str) 两种 config.model 格式
    if isinstance(model_cfg, dict):
        # v0.13 字典格式：检查 default model 和 provider 是否都已配置
        if not model_cfg.get("default") and not model_cfg.get("provider"):
            return "未配置 AI 模型。请先运行 trade setup 选择模型。"
    elif isinstance(model_cfg, str):
        # v0.14+ 字符串格式：检查是否为空字符串
        if not model_cfg.strip():
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
        # 所有已知的 API Key 环境变量均未设置，无法调用 LLM
        return "未检测到 API Key。请在 ~/.hermes/.env 中设置，或运行 trade setup 重新配置。"
    return None


def get_agent_kwargs() -> dict:
    """从配置文件构建 ``AIAgent.__init__`` 所需的参数。

    解析 provider、model、base_url 和 api_key —— 包括环境变量对 base_url
    的覆盖，以及通过 auth 注册表按 provider 查找对应 API key。

    Returns:
        包含 provider、model、base_url、api_key 的字典，所有值均为字符串（可能为空）。
    """
    from hermes_cli.config import load_config

    cfg = load_config()
    model_cfg = cfg.get("model", {})

    # 兼容 v0.13 (dict: {"provider":"...", "default":"...", "base_url":"..."})
    #     和 v0.14+ (str: "provider:model" 或 "provider/model")
    if isinstance(model_cfg, dict):
        provider = model_cfg.get("provider", "")
        model = model_cfg.get("default", "")
        base_url = model_cfg.get("base_url", "")
    elif isinstance(model_cfg, str) and model_cfg.strip():
        provider, model, base_url = _parse_model_config_str(model_cfg)
    else:
        provider = model = base_url = ""

    # ── base_url: from PROVIDER_REGISTRY, env var overrides config.yaml ──
    env_url = ""
    if provider:
        # 从 PROVIDER_REGISTRY 获取该 provider 的 base_url 环境变量名，覆盖 config.yaml 中的值
        try:
            from hermes_cli.auth import PROVIDER_REGISTRY
            pconfig = PROVIDER_REGISTRY.get(provider)
            if pconfig:
                brv = getattr(pconfig, 'base_url_env_var', '')
                if brv:
                    env_url = os.getenv(brv, "").strip()
        except Exception:
            # PROVIDER_REGISTRY 可能不存在或导入失败，忽略异常
            pass
    if env_url:
        # 环境变量中找到了 base_url，用它覆盖 config.yaml 中的值
        base_url = env_url

    # ── api_key: per-provider via PROVIDER_REGISTRY，严格不跨 provider 兜底 ──
    # 仅在 provider 未注册或无对应 key 时，fallback 到通用 key
    api_key = ""
    if provider:
        # 从 PROVIDER_REGISTRY 查找该 provider 对应的 API Key 环境变量
        try:
            from hermes_cli.auth import PROVIDER_REGISTRY
            pconfig = PROVIDER_REGISTRY.get(provider)
            if pconfig and pconfig.auth_type == "api_key":
                for env_name in pconfig.api_key_env_vars:
                    api_key = os.getenv(env_name, "").strip()
                    if api_key:
                        # 找到第一个不为空的 key 即停止
                        break
        except Exception:
            # PROVIDER_REGISTRY 可能不存在或导入失败，忽略异常
            pass
    # 仅在 key 仍然为空时才尝试通用兜底（避免 provider=anthropic 时错拿 OPENAI_API_KEY）
    if not api_key:
        # 所有 provider 专属 key 都未找到，回退到通用的 LLM_API_KEY
        api_key = os.getenv("LLM_API_KEY", "").strip() or ""

    return {"provider": provider, "model": model,
            "base_url": base_url, "api_key": api_key}


# ── Agent factory ─────────────────────────────────────────────────────────────

def create_agent(
    tool_start_callback=None,
    tool_complete_callback=None,
    *,
    ephemeral_system_prompt: str | None = None,
):
    """创建 Hermes AIAgent 实例的统一入口。

    Trade 中所有对 Hermes Agent 的调用都通过此函数，不直接 import AIAgent。
    当 Hermes 升级改变模块路径或构造签名时，只需修改此一处。

    Args:
        tool_start_callback: Hermes 工具开始回调（用于 SSE 流式进度）
        tool_complete_callback: Hermes 工具完成回调
        ephemeral_system_prompt: 临时 system prompt（OSINT 等 skill 的指令，
                                 通过 Hermes 原生 system 层传入，不混入 user message）

    Returns:
        AIAgent 实例，已配置好 quiet_mode / max_iterations / provider 等参数。

    Raises:
        ImportError: hermes-agent 未安装
        RuntimeError: provider 未配置或 API key 缺失
    """
    from run_agent import AIAgent

    kwargs = get_agent_kwargs()
    err = check_provider()
    if err:
        raise RuntimeError(err)

    # toolsets 可通过 TRADE_ENABLED_TOOLSETS 环境变量覆盖（逗号分隔）
    _toolsets = os.environ.get("TRADE_ENABLED_TOOLSETS", "").strip()
    if _toolsets:
        # 环境变量存在时，解析逗号分隔的 toolset 列表
        enabled_toolsets = [t.strip() for t in _toolsets.split(",") if t.strip()]
    else:
        # 未设置环境变量时使用默认 toolset 组合
        enabled_toolsets = ["web", "search", "file", "terminal", "code_execution",
                            "browser", "skills", "memory", "cronjob", "todo"]

    return AIAgent(
        quiet_mode=True,
        max_iterations=int(os.environ.get("TRADE_MAX_ITERATIONS", "90")),
        provider=kwargs["provider"] or None,
        base_url=kwargs["base_url"] or None,
        model=kwargs["model"] or None,
        api_key=kwargs["api_key"] or None,
        tool_start_callback=tool_start_callback,
        tool_complete_callback=tool_complete_callback,
        enabled_toolsets=enabled_toolsets,
        ephemeral_system_prompt=ephemeral_system_prompt,
    )


# ── Token estimation helpers ──────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    """估算文本的 token 数（用于上下文窗口预算）。

    经验值：中文约 1.5 字/token → token = 字数 / 1.5 ≈ 字数 × 0.67
            英文约 4 字符/token → token = 字符数 / 4 = 字符数 × 0.25
    """
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    non_chinese = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + non_chinese / 4.0)


def _get_history_block(company_id: int, total_prompt_chars: int) -> tuple[str, int]:
    """根据 prompt 总大小构造历史对话注入块。

    上下文越长，注入的历史条数越少，防止超出 token 预算。
    返回 (history_block, history_token_count)。
    当 company_id 为 None 时 history_block 为空字符串。
    """
    if not company_id:
        # 没有关联公司则不注入历史
        return "", 0

    from trade import chat_memory as _cm

    # Token thresholds (hard-coded, not user-visible)
    if total_prompt_chars < 80_000:      # ~< 20k tokens — 上下文充足，注入最近 20 条
        limit = 20
        hint = None
    elif total_prompt_chars < 200_000:   # ~< 50k tokens — 中等上下文，注入 10 条并提示用户
        limit = 10
        hint = "如需更早的对话历史，请使用 chat_memory_list 工具。"
    else:                                # >= 50k tokens — 上下文紧张，仅注入 5 条
        limit = 5
        hint = "当前上下文较长，历史对话已精简。如需查询更早内容，请使用 chat_memory_list 工具。"

    rows = _cm.get_recent(company_id, limit=limit)
    if not rows:
        # 数据库中无历史记录
        return "", 0

    lines = ["## 最近对话历史"]
    for row in rows:
        ts = row.get("created_at", "")[:16]  # YYYY-MM-DD HH:MM — 截断到分钟精度
        lines.append(f"[{ts}] user: {row['query'][:200]}")
        if row.get("response"):
            # 仅在有 response 时注入，避免空内容占用 token
            lines.append(f"[{ts}] assistant: {row['response'][:200]}")
    block = "\n".join(lines) + "\n"

    if hint:
        # 在历史块末尾附上引导提示，告知用户如何查询更早的内容
        block += f"\n{hint}\n"

    return block, _estimate_tokens(block)

# OSINT 类 skill 名称列表（使用精简 system prompt）
_OSINT_SKILL_NAMES = frozenset({"b2b-osint", "b2b-email-intel"})


def build_query(
    company_id: int,
    library_id: int | None,
    query: str,
    customer_id: int | None = None,
) -> tuple[str, str | None]:
    """组装完整的用户 prompt：公司身份 + 文档库上下文 + Skill 注入。

    返回 (user_message, skill_system_hint)，其中 skill_system_hint 是给 OSINT 等
    场景的辅助系统指令（非 OSINT skill 时为 None），由 chat.py 通过
    agent.run_conversation(system_message=...) 传入，与 user message 分层处理。

    company_id 决定注入哪家公司身份到 system prompt。
    library_id 可选地添加文档库上下文。
    customer_id 可选地添加客户上下文（客户名称、关联文档库）。
    """
    from trade import company as _company
    from trade import customer as _cust
    from trade import library as _lib
    from trade import skill_router

    # 0. Skill auto-detection — 在组装 prompt 之前必须先匹配 skill，这样即使用户
    #    描述模糊，LLM 也知道该调用哪个工具/函数
    matched_skill = skill_router.match_skill(query)
    matched_name = matched_skill["name"] if matched_skill else None

    augmented_query = skill_router.augment_query(
        query, company_id=company_id
    )

    # 1. Company identity — OSINT 类 skill 用精简 prompt，减少无关内容占用上下文
    company_slug = _company.slug_from_id(company_id) if company_id else None
    db_identity = _company.get_agent_identity(company_id) if company_id else None
    if matched_name in _OSINT_SKILL_NAMES:
        # OSINT 背调场景使用精简 system prompt，去掉销售相关的指令以减少 token 浪费
        from trade.prompt import TRADE_SYSTEM_PROMPT_OSINT
        code_fallback = TRADE_SYSTEM_PROMPT_OSINT
    else:
        # 非 OSINT 场景使用标准销售 prompt（包含产品知识、报价流程等）
        code_fallback = None
    system_prompt = _prompts.resolve_system_prompt(
        company_slug=company_slug,
        db_identity=db_identity,
        code_fallback=code_fallback,
    )

    # 2. Customer context (injected before library context) — 客户信息放在文档上下文之前
    customer_context = ""
    if customer_id:
        # 有客户 ID 时查询客户信息并注入 prompt，让 AI 知道当前对话的客户身份
        cust = _cust.get(customer_id, company_id=company_id)
        if cust:
            # 客户存在则构造上下文描述，包含客户名称和联系方式
            customer_context = (
                f"\n[上下文] 用户正在与客户「{cust['name']}」"
                f"（联系方式：{cust.get('contact', '未填写')}）对话。"
            )
            # 顺便注入该客户关联的文档库信息
            linked_libs = _cust.get_libraries(customer_id, company_id=company_id)
            if linked_libs:
                # 有关联文档库时列出名称，方便 AI 后续引用
                lib_names = "、".join(l["name"] for l in linked_libs)
                customer_context += f"该客户关联的文档库：{lib_names}。"

    # 3. Library document context — 文档库信息放在客户上下文之后
    doc_context = ""
    if library_id:
        # 有文档库 ID 时查询文档库信息，告知 AI 用户所在的文档目录
        lib = _lib.get(library_id, company_id=company_id)
        if lib:
            # 文档库存在则构造路径上下文，提示 AI 使用 read_file 读取文件
            doc_context = (
                f"\n[上下文] 用户正在文档库「{lib['name']}」({lib['root_path']}) "
                "中提问。必要时使用 read_file 读取目录中的文件。"
            )

    # 4. Skill system hint — OSINT 类 skill 的注入指令作为 system 层独立传入
    #    与 user message 分层处理，避免注入指令混入用户消息
    skill_system_hint: str | None = None
    if matched_name in _OSINT_SKILL_NAMES and matched_skill:
        # 加载 skill 的 injection_prompt 作为 system 层指令
        from trade.skill_router import _load_injection_prompt
        augment = _load_injection_prompt(matched_name)
        if augment is None:
            # 如果从 SKILL.md 加载失败，回退到 skill_registry 中的 augment_prompt
            augment = matched_skill.get("augment_prompt", "")
        if augment:
            # 构造 system hint，标记当前技能的名称和注入指令
            skill_system_hint = (
                f"## 当前技能：{matched_name}\n\n{augment}"
            )
        # OSINT skill 的 system hint 已单独抽出，augmented_query 中无需
        # 再拼 [SKILL AUGMENTATION] 块。用原始 query 替代。
        augmented_query = query

    # 5. History block — OSINT 类 skill 不注入历史，每次背调目标是独立的
    #    非 OSINT 场景注入最近对话历史，帮助 AI 保持上下文连续
    history_block = ""
    if matched_name not in _OSINT_SKILL_NAMES:
        # 估算已有 prompt 长度，动态决定注入多少条历史
        pre_history_chars = (
            len(system_prompt) + len(customer_context) + len(doc_context) +
            len(augmented_query) + 200
        )
        history_block, _ = _get_history_block(company_id, pre_history_chars)

    # 6. Assemble final user message — 按顺序拼接：system → 客户 → 文档库 → 历史 → 当前查询
    final_prompt = system_prompt + customer_context + doc_context
    if history_block:
        # 有历史时才注入，避免多余空行
        final_prompt = f"{final_prompt}\n\n{history_block}"

    return f"{final_prompt}\n\n{augmented_query}", skill_system_hint
