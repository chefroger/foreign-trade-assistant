"""
Trade AI Assistant — 记忆与模型 API 路由。

端点：
  GET /memory/status         — Hindsight 长期记忆可用性
  GET /memory/recall         — 搜索长期记忆
  GET /models/providers      — 已配置的 LLM 提供商列表
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from trade import chat_memory
from trade.api.deps import opt_company
from trade.helpers import _parse_model_config_str

router = APIRouter(tags=["memory"])


# ── Hindsight 长期记忆 ────────────────────────────────────────────────────

@router.get("/memory/status")
def memory_status(cid: int | None = Depends(opt_company)):
    """检查 Hindsight 长期记忆是否可用。"""
    try:
        from trade.memory import is_available as hindsight_available
        return {
            "hindsight_available": hindsight_available(),
            "company_id": cid,
        }
    except ImportError:
        return {"hindsight_available": False, "company_id": None}


@router.get("/memory/recall")
def memory_recall(
    query: str,
    cid: int | None = Depends(opt_company),
):
    """搜索 Hindsight 长期记忆中的相关历史对话。"""
    result = chat_memory.recall_context(query)
    if not result:
        return {"results": [], "query": query, "company_id": cid}
    return {"results": [result], "query": query, "company_id": cid}


# ── helpers ─────────────────────────────────────────────────────────────────

# _parse_model_string 已删除，统一使用 trade.helpers._parse_model_config_str


# ── LLM 提供商 ────────────────────────────────────────────────────────────

@router.get("/models/providers")
def list_providers():
    """列出已配置的 LLM 提供商及其可用模型。

    从 ~/.hermes/config.yaml 和 PROVIDER_REGISTRY 读取，
    返回每个提供商的模型列表、API Key 配置状态。
    """
    try:
        from hermes_cli.auth import PROVIDER_REGISTRY
        from hermes_cli.config import load_config

        cfg = load_config()
        model_cfg = cfg.get("model", {})
        active_provider = ""
        active_model = ""
        # 兼容 v0.13 (dict) 和 v0.14+ (str) 两种 config.model 格式
        if isinstance(model_cfg, dict):
            active_provider = model_cfg.get("provider", "")
            active_model = model_cfg.get("default", "")
        elif isinstance(model_cfg, str) and model_cfg.strip():
            # v0.14 flat format — 复用 helpers 的统一解析函数
            active_provider, active_model, _ = _parse_model_config_str(model_cfg)

        providers = []
        for pid, pconfig in PROVIDER_REGISTRY.items():
            # 检查 API Key 是否已配置
            has_key = False
            if pconfig.auth_type == "api_key":
                for env_name in pconfig.api_key_env_vars:
                    if os.getenv(env_name):
                        has_key = True
                        break

            # 获取该提供商的模型列表（v0.14 移除了 name_to_models，使用 _PROVIDER_MODELS）
            try:
                from hermes_cli.models import _PROVIDER_MODELS
                models = _PROVIDER_MODELS.get(pid, [])
            except Exception:
                models = []

            providers.append({
                "id": pid,
                "name": pconfig.display_name or pid,
                "has_key": has_key,
                "models": models[:10],
                "is_active": pid == active_provider,
                "active_model": active_model if pid == active_provider else "",
            })

        return {
            "providers": providers,
            "active_provider": active_provider,
            "active_model": active_model,
        }
    except Exception as e:
        return {"providers": [], "error": str(e)}
