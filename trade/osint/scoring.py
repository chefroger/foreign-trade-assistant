"""
Trade AI Assistant — OSINT 模块：风险评分与建议生成。

根据各层检测结果计算综合风险评分（0-100），并生成针对性的行动建议。
"""

from __future__ import annotations


def compute_risk_score(flags: list[str]) -> tuple[int, str]:
    """根据红旗列表计算综合风险评分（0-100）和评级。

    每个红旗对应不同的扣分权重，敏感维度（制裁名单）扣分最多。

    Args:
        flags: 红旗标记列表（如 "personal_email_domain", "sanctioned" 等）

    Returns:
        (score, rating) 其中 rating 为 "low" | "medium" | "high"
    """
    score = 100

    # 扣分规则表（按严重程度）
    deductions = {
        "personal_email_domain": 30,    # 个人邮箱 → 严重减分
        "domain_age_new": 20,           # 新注册域名 → 中等减分
        "free_platform": 15,            # 免费建站 → 轻微减分
        "no_linkedin": 10,              # 无 LinkedIn → 轻微减分
        "linkedin_domain_mismatch": 15, # LinkedIn 域名不匹配 → 中等减分
        "sanctioned": 50,               # 命中制裁名单 → 直接死刑
        "domain_age_old": 0,            # 老域名 → 不扣分（加分项在建议中体现）
    }

    for flag in flags:
        score -= deductions.get(flag, 10)  # 未知红旗默认扣 10 分

    score = max(0, min(100, score))  # 限制在 [0, 100] 区间

    if score >= 80:
        rating = "low"
    elif score >= 50:
        rating = "medium"
    else:
        rating = "high"

    return score, rating


def generate_recommendations(report: dict) -> list[str]:
    """根据各层检测结果生成结构化的行动建议。

    每个 layer 的结果独立评估，生成一条具体的、可执行的建议。

    Args:
        report: osint_full_check 的完整报告 dict，包含 "layers" 字段

    Returns:
        建议字符串列表（带 emoji 前缀指示严重程度）
    """
    recs: list[str] = []
    layers = report.get("layers", {})

    # ── 邮箱验证建议 ──
    ev = layers.get("email_verification")
    if ev:
        if ev.get("risk_flag"):
            recs.append(
                f"⚠️ 对方使用个人邮箱（{ev.get('domain', '')}），"
                "建议要求对方提供企业邮箱后再深入谈判"
            )
        elif ev.get("is_corporate"):
            recs.append(
                f"✅ 企业邮箱验证通过（{ev.get('domain', '')}），域名匹配且 MX 记录正常"
            )

    # ── 域名建议 ──
    di = layers.get("domain_intel")
    if di:
        age_cat = di.get("age_category")
        days = di.get("days_old")
        if age_cat == "new":
            recs.append(
                f"⚠️ 域名注册仅 {days} 天，属于新注册域名，配套信息待验证"
            )
        elif age_cat == "old" and days:
            recs.append(
                f"✅ 域名注册已 {days} 天，长期运营可信度高"
            )

    # ── 技术栈建议 ──
    ts = layers.get("tech_stack")
    if ts:
        if ts.get("is_free_platform"):
            platforms = ", ".join(ts.get("platforms", []))
            recs.append(
                f"⚠️ 网站使用免费建站平台（{platforms}），可能代表公司规模较小"
            )
        elif ts.get("is_enterprise"):
            recs.append("✅ 网站使用企业级技术栈，可信度 +1")

    # ── 制裁名单建议 ──
    sa = layers.get("sanctions")
    if sa:
        if sa.get("is_sanctioned"):
            recs.append("🚨 命中制裁名单，建议拒绝交易或咨询法律部门")
        elif sa.get("risk_level") == "medium":
            recs.append("⚠️ 发现疑似制裁匹配，建议进一步人工核查")
        elif not sa.get("hits"):
            recs.append("✅ 未在任何制裁名单中发现匹配项")

    # ── LinkedIn 建议 ──
    li = layers.get("linkedin")
    if li:
        if li.get("linkedin_found"):
            count = li.get("employee_count", "未知")
            recs.append(f"✅ LinkedIn 公司页存在，员工规模：{count}")
        else:
            recs.append("⚠️ 未找到 LinkedIn 公司页，建议要求对方提供公司证明")

    return recs
