"""
Trade AI Assistant — OSINT 编排器：完整尽职调查流程。

osint_full_check() 是 OSINT 模块的统一入口，接收邮箱/域名/公司名，
自动识别类型后依次执行 6 层检测，最终输出综合风险评分报告。
"""

from __future__ import annotations

import asyncio
import re

from trade import email_intel
from trade.osint.whois import domain_whois
from trade.osint.email_verify import verify_corporate_email
from trade.osint.sanctions import check_sanctions
from trade.osint.tech_stack import detect_tech_stack
from trade.osint.linkedin_verify import linkedin_company_verify
from trade.osint.scoring import compute_risk_score, generate_recommendations


async def osint_full_check(
    target: str,
    *,
    include_sanctions: bool = True,
    include_tech_stack: bool = True,
    include_linkedin: bool = True,
) -> dict:
    """完整 OSINT 尽职调查（异步编排，LLM 友好）。

    接收邮箱 / 域名 / 公司名，自动识别类型，依次执行各层检测，
    最终输出综合风险评分报告。

    Args:
        target: 邮箱 / 域名 / 公司名（自动识别）
        include_sanctions: 是否包含制裁名单筛查（默认 True）
        include_tech_stack: 是否包含技术栈检测（默认 True）
        include_linkedin: 是否包含 LinkedIn 验证（默认 True）

    Returns:
        完整报告 dict，结构见需求文档 3.11.8 节：
        {
            "target": str,
            "target_type": str,       # "email" | "domain" | "url" | "company"
            "overall_rating": str,    # "low" | "medium" | "high" | "unknown"
            "overall_score": int,     # 0-100
            "flags": list[str],       # 红旗标记列表
            "layers": {               # 各层检测结果
                "email_registration": dict | None,
                "domain_intel": dict,
                "email_verification": dict | None,
                "tech_stack": dict | None,
                "sanctions": dict | None,
                "linkedin": dict | None,
            },
            "recommendations": list[str],  # 行动建议
        }
    """
    target = target.strip()
    target_type = _detect_target_type(target)

    report: dict = {
        "target": target,
        "target_type": target_type,
        "overall_rating": "unknown",
        "overall_score": 0,
        "flags": [],
        "layers": {},
        "recommendations": [],
    }

    # ── 确定用于域名查询的目标 ──
    if target_type == "email":
        # 从邮箱提取域名，用于后续各层检测
        domain_from_email = target.split("@", 1)[1]
    else:
        domain_from_email = None

    lookup_domain = (
        domain_from_email or
        target.replace("https://", "").replace("http://", "").replace("www.", "")
    )

    # ── Layer 1: Email registration (holehe) ─────────────────────────────
    if target_type == "email":
        email_result = await _run_email_check(target)
        report["layers"]["email_registration"] = email_result
    else:
        report["layers"]["email_registration"] = None

    # ── Layer 2: WHOIS 域名查询 ─────────────────────────────────────────
    whois_result = domain_whois(lookup_domain)
    report["layers"]["domain_intel"] = whois_result

    if whois_result.get("age_category") == "new":
        report["flags"].append("domain_age_new")
    if whois_result.get("days_old") and whois_result["days_old"] > 3650:
        report["flags"].append("domain_age_old")

    # ── Layer 3: 企业邮箱验证 ───────────────────────────────────────────
    if target_type == "email":
        email_verify_result = verify_corporate_email(target)
        report["layers"]["email_verification"] = email_verify_result

        if email_verify_result.get("risk_flag"):
            report["flags"].append("personal_email_domain")
    else:
        report["layers"]["email_verification"] = None

    # ── Layer 4 (可选): 技术栈检测 ─────────────────────────────────────
    if include_tech_stack and lookup_domain:
        tech_result = detect_tech_stack(f"https://{lookup_domain}")
        report["layers"]["tech_stack"] = tech_result

        if tech_result.get("is_free_platform"):
            report["flags"].append("free_platform")
    else:
        report["layers"]["tech_stack"] = None

    # ── Layer 5 (可选): 制裁名单筛查 ───────────────────────────────────
    if include_sanctions:
        sanctions_name = domain_from_email or target
        sanctions_result = check_sanctions(sanctions_name)
        report["layers"]["sanctions"] = sanctions_result

        if sanctions_result.get("is_sanctioned"):
            report["flags"].append("sanctioned")
    else:
        report["layers"]["sanctions"] = None

    # ── Layer 6: LinkedIn 验证（生成 browser_navigate 指令）─────────────
    if include_linkedin and lookup_domain:
        linkedin_result = linkedin_company_verify(lookup_domain, target)
        report["layers"]["linkedin"] = linkedin_result
        # LinkedIn 验证通过 Hermes browser_navigate 执行，无网络请求风险
        # 此处不做自动评分（需 Agent 实际执行后人工/LLM 判断）
    else:
        report["layers"]["linkedin"] = None

    # ── 综合评分 ───────────────────────────────────────────────────────
    score, rating = compute_risk_score(report["flags"])
    report["overall_score"] = score
    report["overall_rating"] = rating

    # ── 生成建议 ───────────────────────────────────────────────────────
    report["recommendations"] = generate_recommendations(report)

    return report


# ─────────────────────────────────────────────────────────────────────────────
# 内部 helpers
# ─────────────────────────────────────────────────────────────────────────────

def _detect_target_type(target: str) -> str:
    """自动识别目标类型：email / domain / url / company。

    识别规则：
      - 含 @ → email
      - 含 http(s):// → url
      - 符合域名格式 (含 . 和合法 TLD) → domain
      - 否则 → company
    """
    target = target.strip()
    if "@" in target and "." in target.split("@", 1)[1]:
        return "email"
    if target.startswith(("http://", "https://")):
        return "url"
    if re.match(r"^[a-z0-9]([a-z0-9-]+\.)+[a-z]{2,}$", target.lower()):
        return "domain"
    return "company"


async def _run_email_check(email: str) -> dict:
    """在线程池中运行 holehe 邮箱检测（同步 → 异步适配）。

    email_intel.email_background_check 是同步的，不适合在 async 上下文中直接调用，
    所以放到 executor 中执行。
    """
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None, email_intel.email_background_check, email
        )
        return result
    except Exception as e:
        return {"error": str(e), "checked_count": 0, "found_count": 0}
