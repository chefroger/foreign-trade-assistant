"""
Trade AI Assistant — API 依赖函数。

提供 session token 校验和 company_id 解析的共享依赖，
被所有 /api/trade/* 路由使用。
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, Request, Depends

from trade import company as company_module


# ── Session token ────────────────────────────────────────────────────────────

# 由 server.py 在启动时设置
_SESSION_TOKEN: str = ""


def set_session_token(token: str) -> None:
    """设置当前会话的 token（server.py 启动时调用）。"""
    global _SESSION_TOKEN
    _SESSION_TOKEN = token


def require_session(request: Request) -> None:
    """校验 X-Hermes-Session-Token。

    所有 /api/trade/* 路由共享此依赖，确保只有持有 token 的
    本机浏览器会话可以访问 API。

    Raises:
        HTTPException(401): token 缺失或不匹配
    """
    token = request.headers.get("X-Hermes-Session-Token", "")
    if not _SESSION_TOKEN:
        # 未初始化（不应发生，防御性编程）
        raise HTTPException(status_code=500, detail="Server not initialized.")
    if not token or token != _SESSION_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing session token.")


# ── Company ID ────────────────────────────────────────────────────────────────

def require_company(
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
) -> int:
    """解析并验证 X-Company-ID header，返回 company_id。

    验证步骤：
      1. header 存在且非空
      2. 可解析为整数
      3. 公司存在且 is_active=True

    Raises:
        HTTPException(401): header 缺失、无效、或公司不存在/未激活
    """
    if not x_company_id or not x_company_id.strip():
        raise HTTPException(
            status_code=401,
            detail="X-Company-ID header is required. "
                   "Call GET /api/trade/companies first to get your company IDs.",
        )
    try:
        cid = int(x_company_id.strip())
    except ValueError:
        raise HTTPException(status_code=401, detail="X-Company-ID must be an integer.")

    # 验证公司存在且激活
    tc = company_module.get_trade_company(cid)
    if not tc:
        raise HTTPException(status_code=401, detail=f"Company {cid} not found in Trade system.")
    if not tc.get("is_active"):
        raise HTTPException(status_code=401, detail=f"Company {cid} is inactive.")
    return cid


def opt_company(
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
) -> Optional[int]:
    """解析 X-Company-ID header，返回 company_id 或 None。

    与 require_company 的区别：header 缺失时不抛异常。
    仅用于不涉及公司数据隔离的非敏感端点（如 /memory/status）。

    Raises:
        HTTPException(401): header 存在但无法解析为整数
    """
    if not x_company_id or not x_company_id.strip():
        return None
    try:
        return int(x_company_id.strip())
    except ValueError:
        raise HTTPException(status_code=401, detail="X-Company-ID must be an integer.")
