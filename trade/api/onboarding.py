"""
Trade AI Assistant — 首次运行引导 API。

端点：
  GET  /onboarding/status       — 检查引导是否已完成
  POST /onboarding/first-company — 原子创建公司 + 配置 Agent 身份
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from trade import onboarding as onboarding_module

router = APIRouter(tags=["onboarding"])


@router.get("/onboarding/status")
def get_onboarding_status():
    """返回系统是否已完成首次引导。

    前端在打开页面时调用此接口，决定显示引导页还是正常 UI。
    """
    return {"done": onboarding_module.is_onboarding_done()}


@router.post("/onboarding/first-company")
def create_first_company(body: dict):
    """一体化创建第一个公司并配置 Agent 身份（原子操作）。

    将公司创建 + Agent 身份配置 + 桌面工作目录合并为一步。

    Body 参数：
        company_name   (str, 必填): 公司名称
        contact_name   (str, 可选): 联系人姓名
        contact_email  (str, 可选): 联系人邮箱
        identity_data  (dict, 可选): Agent 身份配置
        work_dir_name  (str, 可选): 桌面工作目录名称（目录已存在时用户指定新名字）

    返回：
        {"company": {...}, "trade_company": {...},
         "work_dir": str, "work_dir_is_new": bool, "libraries": [...]}

    状态码：
        200: 创建成功
        409: 系统已有活跃公司（幂等保护）
        400: company_name 为空
    """
    # 幂等保护：已有活跃公司时拒绝（防止刷新页面重复提交）
    if onboarding_module.is_onboarding_done():
        raise HTTPException(
            status_code=409,
            detail="系统已完成首次引导。如需添加新公司，请使用 POST /companies。",
        )

    company_name = (body.get("company_name") or "").strip()
    if not company_name:
        raise HTTPException(status_code=400, detail="company_name 不能为空")

    try:
        result = onboarding_module.create_first_company(
            company_name=company_name,
            contact_name=body.get("contact_name", ""),
            contact_email=body.get("contact_email", ""),
            identity_data=body.get("identity_data"),
            work_dir_name=body.get("work_dir_name", ""),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
