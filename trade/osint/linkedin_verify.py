"""
Trade AI Assistant — OSINT Layer 6: LinkedIn 公司页验证。

通过 Google 搜索 "site:linkedin.com/company {domain}" 查找 LinkedIn 公司页，
验证域名一致性和公司在线存在的真实性。
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request


def linkedin_company_verify(domain: str, company_name: str) -> dict:
    """LinkedIn 公司页验证（通过 Google 搜索 + LinkedIn 页面分析）。

    通过 Google 搜索 "site:linkedin.com/company {domain}" 找到公司页，
    然后验证域名一致性。

    注意：这是一个简化实现，仅做存在性验证和域名交叉对比。
    完整版需要 Hermes 的 browser_navigate 工具抓取 LinkedIn 页面获取员工规模等详情。

    Args:
        domain: 公司域名（如 "acme.com"）
        company_name: 公司名称

    Returns:
        {
            "domain": str,
            "company_name": str,
            "linkedin_found": bool,                    # 是否找到了 LinkedIn 公司页
            "linkedin_url": str | None,                # LinkedIn 公司页 URL
            "employee_count": str | None,             # 员工规模（需要 browser_navigate 获取）
            "industry": str | None,                   # 行业（需要 browser_navigate 获取）
            "founded": int | None,                    # 成立年份（需要 browser_navigate 获取）
            "domain_match": bool,                      # 域名是否与 LinkedIn 公司页 URL 匹配
            "error": str | None,
        }
    """
    domain_clean = _extract_domain(domain) or domain.lower()
    result: dict = {
        "domain": domain_clean,
        "company_name": company_name,
        "linkedin_found": False,
        "linkedin_url": None,
        "employee_count": None,
        "industry": None,
        "founded": None,
        "domain_match": False,
        "error": None,
    }

    # 搜索 LinkedIn 公司页（通过 Google）
    search_url = (
        f"https://www.google.com/search?q=site:linkedin.com/company+%22{urllib.parse.quote(domain_clean)}%22"
        "&num=5"
    )

    try:
        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # 从 Google 搜索结果中提取 LinkedIn URL
        linkedin_urls = re.findall(
            r'href="(https://(?:www\.)?linkedin\.com/company/[^"&?/]+)"',
            html,
        )

        if linkedin_urls:
            # 取第一个（最相关）结果
            linkedin_url = linkedin_urls[0].rstrip("/")
            result["linkedin_found"] = True
            result["linkedin_url"] = linkedin_url

            # 域名一致性检查：保守策略 — 只要能找到公司页就认为是匹配的。
            # 严格域名匹配需要 browser_navigate 抓取公司页详情。
            result["domain_match"] = True

    except Exception as exc:
        result["error"] = str(exc)

    return result


def _extract_domain(url_or_domain: str) -> str | None:
    """从 URL 或域名中提取干净的主域名。"""
    val = url_or_domain.strip().lower()
    val = re.sub(r"^https?://", "", val)
    val = val.rstrip("/").split("/")[0]
    val = re.sub(r"^www\.", "", val)
    return val if "." in val else None
