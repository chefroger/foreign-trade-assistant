"""
Trade AI Assistant — 首次运行引导 API。

端点：
  GET  /onboarding/status       — 检查引导是否已完成
  POST /onboarding/first-company — 原子创建公司 + 配置 Agent 身份
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from trade import onboarding as onboarding_module
from trade.api.models import OnboardingFirstCompany

router = APIRouter(tags=["onboarding"])


@router.get("/onboarding/status")
def get_onboarding_status():
    """返回系统是否已完成首次引导。"""
    return {"done": onboarding_module.is_onboarding_done()}


@router.post("/onboarding/first-company")
def create_first_company(payload: OnboardingFirstCompany):
    """一体化创建第一个公司并配置 Agent 身份（原子操作）。

    仅当系统尚未有任何活跃公司时才能调用；已有公司时返回 409。
    """
    if onboarding_module.is_onboarding_done():
        raise HTTPException(
            status_code=409,
            detail="系统已完成首次引导。如需添加新公司，请使用 POST /companies。",
        )

    if not payload.company_name.strip():
        raise HTTPException(status_code=400, detail="company_name 不能为空")

    try:
        return onboarding_module.create_first_company(
            company_name=payload.company_name.strip(),
            contact_name=payload.contact_name,
            contact_email=payload.contact_email,
            identity_data=payload.identity_data,
            work_dir_name=payload.work_dir_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
