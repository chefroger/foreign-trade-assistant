"""
Trade AI Assistant — 首次运行引导模块。

职责：
  首次启动时引导用户完成公司注册和 Agent 身份配置，一步到位。
  提供「一体化」API，将公司创建、agent 身份配置合并为单个原子操作，
  避免用户分两步操作导致状态不完整。

调用方式：
  POST /api/trade/onboarding/first-company
    Body: {
        "company_name": "ABC Trading Co.",
        "contact_name": "张经理",
        "contact_email": "zhang@example.com",
        "agent_identity": {
            "role": "AI 销售助手",
            "products": "工业电机、发电机",
            "differentiation": "源头工厂、价格有竞争力",
            "target_region": "东南亚、欧洲"
        }
    }
    Returns: { "company": {...}, "trade_company": {...} }
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from trade.database import get_connection
from trade import company as _company_module


# ─────────────────────────────────────────────────────────────────────────────
# utoboarding state — lightweight in-memory flag to prevent double-triggering
# ─────────────────────────────────────────────────────────────────────────────

# 是否已完成首次引导的全局标志（进程级，非持久化）。
# 服务器重启后归零，不影响用户已创建数据。
# 用途：前端首次打开时检测是否需要显示引导界面。
_onboarding_done: bool = False


def is_onboarding_done() -> bool:
    """检查系统是否已完成首次引导（至少有一家活跃公司）。

    检测逻辑：
      1. 查 companies 表是否有 is_active=1 的记录
      2. 如果有 → False（已完成引导，系统已初始化）
      3. 如果没有 → True（需要引导）
    """
    global _onboarding_done
    if _onboarding_done:
        return True

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE is_active = 1"
        ).fetchone()
        count = row[0] if row else 0
        _onboarding_done = (count > 0)
        return _onboarding_done
    finally:
        conn.close()


def reset_onboarding_flag() -> None:
    """重置引导标志（用于测试或调试）。"""
    global _onboarding_done
    _onboarding_done = False


# ─────────────────────────────────────────────────────────────────────────────
# Agent identity 模板（用户未填时使用默认值）
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_AGENT_IDENTITY_TEMPLATE = """
## 公司身份配置

你是一家专业外贸公司的 AI 销售助手。

**公司名称**：{company_name}
**产品范围**：{products}
**差异化卖点**：{differentiation}
**目标市场**：{target_region}

**沟通风格**：
- 专业、简洁、不废话
- 主动了解客户需求，而非一上来就报价
- 遇到不确定的问题时，明确告知客户，不编造数据

**回复格式**：
- 问题回答 → 直接给答案，再补充细节
- 开发信 → 结构清晰（痛点 → 方案 → 证据 → CTA）
- 报价 → 注明有效期和贸易术语
""".strip()


def _build_agent_identity(company_name: str, identity_data: dict) -> str:
    """根据用户输入构建 agent_identity_md 文本。

    参数：
        identity_data: {
            "role": "AI 销售助手",
            "products": "...",
            "differentiation": "...",
            "target_region": "..."
        }
        如果任何字段为空，使用默认值。
    """
    return _DEFAULT_AGENT_IDENTITY_TEMPLATE.format(
        company_name=company_name or "（公司名称未设置）",
        products=identity_data.get("products", "各类工业产品"),
        differentiation=identity_data.get("differentiation", "源头工厂，性价比高"),
        target_region=identity_data.get("target_region", "全球市场"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# One-step onboarding: 创建公司 + 配置 Agent 身份
# ─────────────────────────────────────────────────────────────────────────────

def create_first_company(
    company_name: str,
    contact_name: str = "",
    contact_email: str = "",
    identity_data: Optional[dict] = None,
    *,
    work_dir_name: str = "",
) -> dict:
    """创建第一个公司并配置其 Agent 身份（原子操作）。

    参数：
        company_name: 公司名称（必填）
        contact_name: 联系人姓名（可选）
        contact_email: 联系人邮箱（可选）
        identity_data: Agent 身份配置字典（可选），
            含 role/products/differentiation/target_region
        work_dir_name: 桌面工作目录名称（目录已存在时用户指定的新名字）

    返回：
        {"company": {...}, "trade_company": {...}}

    异常：
        ValueError: company_name 为空，或公司已存在
    """
    if not company_name or not company_name.strip():
        raise ValueError("company_name 不能为空")

    # 构建 agent_identity_md（用模板 + 用户输入填充）
    agent_identity = _build_agent_identity(
        company_name.strip(),
        identity_data or {},
    )

    # Step 1: 创建公司记录 + 桌面工作目录 + 文档库
    company = _company_module.create(
        name=company_name.strip(),
        contact_name=contact_name.strip(),
        contact_email=contact_email.strip(),
        work_dir_name=work_dir_name,
    )

    # Step 2: 将 agent_identity_md 写入 trade_companies（覆盖空值）
    trade_company = _company_module.update_trade_company(
        company_id=company["id"],
        agent_identity_md=agent_identity,
    )

    # Step 3: 将 agent_identity 写入公司目录下的标准文件
    # 路径：~/.trade/{slug}/companies/{slug}/agent_identity.md
    # 同时写 DB（DB 作为运行时缓存）
    tc = _company_module.get_trade_company(company["id"])
    if tc and tc.get("data_dir"):
        slug = company.get("slug", "")
        identity_path = Path(tc["data_dir"]) / "companies" / slug / "agent_identity.md"
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity_path.write_text(agent_identity, encoding="utf-8")

    # 更新进程级标志
    global _onboarding_done
    _onboarding_done = True

    return {
        "company": company,
        "trade_company": trade_company,
    }
