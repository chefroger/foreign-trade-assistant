"""
Trade AI Assistant — OSINT 模块：常量和共享工具。

包含个人邮箱域名黑名单、免费建站平台列表、制裁名单来源、
HTTP 工具函数等各子模块共享的数据。
"""

from __future__ import annotations

import logging
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 个人邮箱域名黑名单（用于检测非企业邮箱）
# ─────────────────────────────────────────────────────────────────────────────

PERSONAL_EMAIL_DOMAINS: set[str] = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "msn.com", "aol.com", "icloud.com", "me.com",
    "qq.com", "163.com", "126.com", "sina.com", "tom.com",
    "yeah.net", "sohu.com", "mail.com", "gmx.com", "protonmail.com",
    "yandex.com", "zoho.com", "fastmail.com", "tutanota.com",
    "foxmail.com", "139.com", "wo.cn", "189.cn",
    "googlemail.com", "ymail.com", "inbox.com", "mail.ru",
}

# ─────────────────────────────────────────────────────────────────────────────
# 免费/临时建站平台（技术栈红旗）
# ─────────────────────────────────────────────────────────────────────────────

FREE_PLATFORMS: set[str] = {
    "wordpress.com", "blogspot.com", "wix.com", "squarespace.com",
    "weebly.com", "shopify.com", "tilda.cc", "webflow.com",
    "wordpress.org", "blogger.com", "livejournal.com",
    "webnode.com", "site123.com", "strikingly.com", "duda.co",
    "carrd.co", "linktr.ee", "about.me", "format.com",
}

# ─────────────────────────────────────────────────────────────────────────────
# 制裁名单来源（公开 CSV URL，定期需更新）
# ─────────────────────────────────────────────────────────────────────────────

SANCTIONS_SOURCES: list[dict] = [
    {
        "name": "OFAC",
        "label": "美国 OFAC SDN 列表",
        "url": "https://www.treasury.gov/ofac/downloads/sanctions/SDN-List.csv",
        "encoding": "utf-8",
    },
    {
        "name": "UN",
        "label": "联合国安理会制裁名单",
        "url": "https://www.un.org/securitycouncil/sanctions/1267/aq_sanctionslist.shtml",
        "encoding": "utf-8",
    },
    {
        "name": "EU",
        "label": "欧盟制裁名单",
        "url": "https://data.europa.eu/euodp/en/data/dataset/consolidated-list-of-persons-groups-and-entities",
        "encoding": "utf-8",
    },
]

# 制裁名单本地缓存目录路径（由外部 setter 设置）
_sanctions_cache_dir: Optional[str] = None


def set_sanctions_cache_dir(cache_dir: str) -> None:
    """设置制裁名单缓存目录（通常 ~/.trade/cache/sanctions/）。"""
    global _sanctions_cache_dir
    _sanctions_cache_dir = cache_dir


def get_sanctions_cache_dir() -> Optional[str]:
    """获取当前制裁名单缓存目录。"""
    return _sanctions_cache_dir


# ─────────────────────────────────────────────────────────────────────────────
# HTTP 工具函数（共享给 sanctions / tech_stack / linkedin）
# ─────────────────────────────────────────────────────────────────────────────

def http_get(url: str, timeout: int = 30) -> str | None:
    """通过 urllib 发送 HTTP GET 请求，返回响应正文。

    所有子模块统一使用此函数，失败时返回 None 而非抛异常。
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Trade-AI/1.0; +https://github.com)",
                "Accept": "*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception as e:
        logger.debug("HTTP GET 失败 [%s]: %s", url, e)
        return None
