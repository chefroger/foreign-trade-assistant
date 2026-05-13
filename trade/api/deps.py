"""
Trade AI Assistant — API 依赖函数。

提供 company_id 解析和验证的共享 helpers，被所有 API 子模块使用。
"""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from trade import company as company_module


def require_company(x_company_id: Optional[str] = Header(None, alias="X-Company-ID")) -> int:
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


def opt_company(x_company_id: Optional[str] = Header(None, alias="X-Company-ID")) -> Optional[int]:
    """解析 X-Company-ID header，返回 company_id 或 None。

    与 require_company 的区别：header 缺失时返回 None 而非抛 401。
    用于可选 company scope 的端点（如 memory/status）。

    Raises:
        HTTPException(401): header 存在但无法解析为整数
    """
    if not x_company_id or not x_company_id.strip():
        return None
    try:
        return int(x_company_id.strip())
    except ValueError:
        raise HTTPException(status_code=401, detail="X-Company-ID must be an integer.")
