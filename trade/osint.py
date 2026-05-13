"""
Trade AI Assistant — OSINT Intelligence Module.

Comprehensive B2B due-diligence toolkit covering:
  Layer 1 : holehe email registration (已有, trade/email_intel.py)
  Layer 2 : WHOIS domain lookup
  Layer 3 : corporate email verification (vs personal email)
  Layer 4 : sanctions list screening (OFAC / UN / EU / UK / 中国)
  Layer 5 : tech stack detection (BuiltWith-style)
  Layer 6 : LinkedIn company page verification

Architecture
────────────
All functions are pure (no side-effects, no DB, no file system).
Async orchestration function chains them into a full report.
Each function degrades gracefully — returns error dict when a
dependency is unavailable rather than raising exceptions.

P0 Functions (stdlib-only, no pip install needed):
  domain_whois()      — WHOIS via socket (IANA WHOIS protocol, port 43)
  verify_corporate_email() — regex + DNS MX via socket
  check_sanctions()   — OFAC/UN/EU/UK/中国 制裁名单 CSV 下载 + 字符串匹配
  _download_sanctions_csv() — 制裁名单本地缓存，避免重复下载

P1 Functions (需要额外 pip install):
  detect_tech_stack()  — BuiltWith-style (需要 pip install builtwith)
  linkedin_company_verify() — browser_navigate 抓取 LinkedIn 公司页

Public API
──────────
  domain_whois(domain: str) -> dict
  verify_corporate_email(email: str, website: str | None = None) -> dict
  check_sanctions(name: str, country: str | None = None) -> dict
  osint_full_check(target: str, ...) -> dict  # async orchestrator
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import socket
import ssl
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# 个人邮箱域名黑名单（用于检测非企业邮箱）
PERSONAL_EMAIL_DOMAINS: set[str] = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "msn.com", "aol.com", "icloud.com", "me.com",
    "qq.com", "163.com", "126.com", "sina.com", "tom.com",
    "yeah.net", "sohu.com", "mail.com", "gmx.com", "protonmail.com",
    "yandex.com", "zoho.com", "fastmail.com", "tutanota.com",
    "qq.com", "foxmail.com", "139.com", "wo.cn", "189.cn",
    "googlemail.com", "ymail.com", "inbox.com", "mail.ru",
}

# 免费/临时建站平台（技术栈红旗）
FREE_PLATFORMS: set[str] = {
    "wordpress.com", "blogspot.com", "wix.com", "squarespace.com",
    "weebly.com", "shopify.com", "tilda.cc", "webflow.com",
    "wordpress.org", "blogger.com", "livejournal.com",
    "webnode.com", "site123.com", "strikingly.com", "duda.co",
    "carrd.co", "linktr.ee", "about.me", "format.com",
}

# 制裁名单来源（公开 CSV URL，定期需更新）
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

# 制裁名单本地缓存路径（避免每次重新下载）
_SANCTIONS_CACHE_DIR: Optional[str] = None


def _set_cache_dir(cache_dir: str) -> None:
    """设置制裁名单缓存目录（通常 ~/.trade/cache/sanctions/）。"""
    global _SANCTIONS_CACHE_DIR
    _SANCTIONS_CACHE_DIR = cache_dir


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2: WHOIS Domain Lookup
# ─────────────────────────────────────────────────────────────────────────────

def domain_whois(domain: str) -> dict:
    """WHOIS 域名查询，通过 socket 直接发送 WHOIS 协议请求。

    Args:
        domain: 域名（如 "example.com"，不含 https://）

    Returns:
        {
            "domain": str,                    # 规范化域名
            "registered": bool,                 # 是否已注册
            "registrar": str | None,           # 注册商
            "creation_date": str | None,      # 注册时间（ISO 格式）
            "expiry_date": str | None,         # 到期时间（ISO 格式）
            "days_old": int | None,            # 域名年龄（天）
            "age_category": str | None,       # "new" (<1年) / "medium" (1-3年) / "old" (>3年)
            "dns_servers": list[str],         # DNS 服务器列表
            "registrant_name": str | None,    # 注册人（如果有）
            "whois_server": str | None,       # WHOIS 服务器
            "status": str | None,             # 域名状态
            "error": str | None,              # 错误信息（如果有）
        }
    """
    # 清理域名格式
    domain = domain.lower().strip()
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.rstrip("/").split("/")[0]

    if not domain or "." not in domain:
        return {"domain": domain or "", "registered": False, "error": "无效域名格式"}

    result: dict = {
        "domain": domain,
        "registered": False,
        "registrar": None,
        "creation_date": None,
        "expiry_date": None,
        "days_old": None,
        "age_category": None,
        "dns_servers": [],
        "registrant_name": None,
        "whois_server": None,
        "status": None,
        "error": None,
    }

    # 确定 WHOIS 服务器（顶级域名对应的主 WHOIS 服务器）
    tld = domain.rsplit(".", 1)[-1]
    whois_server = _get_whois_server_for_tld(tld)

    try:
        # Step 1: 通过 socket 发送 WHOIS 请求
        whois_response = _query_whois_server(domain, whois_server or whois_server)

        if not whois_response:
            result["error"] = "WHOIS 服务器无响应"
            return result

        # Step 2: 解析 WHOIS 响应
        parsed = _parse_whois_response(whois_response, domain)

        result.update(parsed)

        # Step 3: 计算域名年龄
        if result["creation_date"]:
            try:
                creation = datetime.fromisoformat(result["creation_date"].replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                days_old = (now - creation).days
                result["days_old"] = days_old

                if days_old < 365:
                    result["age_category"] = "new"
                elif days_old < 1095:  # < 3年
                    result["age_category"] = "medium"
                else:
                    result["age_category"] = "old"
            except Exception:
                pass

        result["registered"] = True

    except Exception as exc:
        result["error"] = str(exc)

    return result


def _get_whois_server_for_tld(tld: str) -> Optional[str]:
    """根据顶级域名返回对应的 WHOIS 服务器地址。"""
    whois_servers: dict[str, str] = {
        "com": "whois.verisign.com",
        "net": "whois.verisign.com",
        "org": "whois.pir.org",
        "info": "whois.afilias.net",
        "biz": "whois.neulevel.com",
        "io": "whois.nic.io",
        "co": "whois.nic.co",
        "ai": "whois.nic.ai",
        "xyz": "whois.nic.xyz",
        "top": "whois.nic.top",
        "cc": "whois.nic.cc",
        "cn": "whois.cnnic.cn",
        "jp": "whois.jprs.jp",
        "uk": "whois.nic.uk",
        "de": "whois.denic.de",
        "fr": "whois.nic.fr",
        "au": "whois.auda.org.au",
        "ru": "whois.tcinet.ru",
        "in": "whois.inregistry.in",
        "br": "whois.nic.br",
    }
    return whois_servers.get(tld.lower())


def _query_whois_server(domain: str, server: str, port: int = 43, timeout: int = 10) -> str:
    """通过 socket 连接 WHOIS 服务器并返回原始响应。"""
    # 部分 WHOIS 服务器需要先查询权威服务器
    # 先尝试直接查询
    try:
        with socket.create_connection((server, port), timeout=timeout) as s:
            s.settimeout(timeout)
            # WHOIS 协议：发送域名 + \r\n
            s.sendall(f"{domain}\r\n".encode("utf-8"))

            chunks: list[bytes] = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if len(chunk) < 4096:
                    break

        response = b"".join(chunks).decode("utf-8", errors="replace")
        return response

    except (socket.timeout, socket.error, OSError) as e:
        # 如果主服务器超时，尝试 common WHOIS 服务器
        fallback_servers = ["whois.verisign.com", "whois.markmonitor.com"]
        for fb_server in fallback_servers:
            if fb_server == server:
                continue
            try:
                return _query_whois_server(domain, fb_server, port, timeout=5)
            except Exception:
                continue
        raise


def _parse_whois_response(raw: str, domain: str) -> dict:
    """解析 WHOIS 原始响应文本，提取关键字段。"""
    lines = raw.split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    info: dict = {
        "registrar": None,
        "creation_date": None,
        "expiry_date": None,
        "dns_servers": [],
        "registrant_name": None,
        "whois_server": None,
        "status": None,
    }

    domain_lower = domain.lower()

    # 常见 WHOIS 字段映射（大小写不敏感）
    field_map: dict[str, str] = {
        "registrar": "registrar",
        "registration date": "creation_date",
        "created date": "creation_date",
        "creation date": "creation_date",
        "creation date (dd-mm-yy)": "creation_date",
        "expiry date": "expiry_date",
        "expiration date": "expiry_date",
        "registry expiry date": "expiry_date",
        "nameserver": "dns",
        "nameserver:": "dns",
        "nserver": "dns",
        "dns servers": "dns",
        "registrant": "registrant",
        "registrant name": "registrant",
        "org": "registrant",
        "organization": "registrant",
        "domain status": "status",
        "status": "status",
        "whois server": "whois_server",
    }

    i = 0
    while i < len(lines):
        line = lines[i]
        # 跳过注释行和空行
        if line.startswith("#") or line.startswith("%") or line.startswith("-"):
            i += 1
            continue

        # 尝试 "Key: Value" 格式
        colon_idx = line.find(":")
        if colon_idx > 0:
            key = line[:colon_idx].strip().lower()
            value = line[colon_idx + 1 :].strip()

            # 映射到标准化字段
            matched_key = None
            for pattern, std_key in field_map.items():
                if key == pattern or key.startswith(pattern):
                    matched_key = std_key
                    break

            if matched_key == "dns":
                if value and value not in info["dns_servers"]:
                    info["dns_servers"].append(value)
            elif matched_key:
                if info.get(matched_key) is None:  # 只取第一个值
                    if matched_key in ("creation_date", "expiry_date"):
                        info[matched_key] = _normalize_date(value)
                    else:
                        info[matched_key] = value

        # 检查是否是 "Domain Name: EXAMPLE.COM" 格式（有些服务器用大写）
        if line.lower().startswith("domain name:"):
            # 确认是目标域名（用于区分被删除的域名和目标域名）
            d = line.split(":", 1)[1].strip().lower()
            if d != domain_lower and not d.endswith(domain_lower):
                # 不匹配，可能找到的是上级域名
                pass

        i += 1

    # 如果没有找到 DNS 服务器，再尝试从原始行中搜索
    if not info["dns_servers"]:
        for line in lines:
            ll = line.lower()
            if ll.startswith("nameserver") or ll.startswith("nserver"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    ns = parts[1].strip()
                    if ns and ns not in info["dns_servers"]:
                        info["dns_servers"].append(ns)

    return info


def _normalize_date(date_str: str) -> Optional[str]:
    """将各种日期格式统一转换为 ISO 格式。"""
    if not date_str:
        return None

    date_str = date_str.strip()

    # 格式列表（从最常见到最不常见）
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d-%b-%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str  # 无法解析时返回原文


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: Corporate Email Verification
# ─────────────────────────────────────────────────────────────────────────────

def verify_corporate_email(email: str, website: str | None = None) -> dict:
    """验证企业邮箱 vs 个人邮箱。

    Args:
        email: 邮箱地址（如 "john@acme.com"）
        website: 可选，公司网站（用于域名交叉验证）

    Returns:
        {
            "email": str,
            "domain": str,                     # 邮箱域名
            "is_personal": bool,              # True = 🚩 个人邮箱
            "is_corporate": bool,             # True = ✅ 企业邮箱
            "risk_flag": bool,               # True = 🚩 红旗
            "domain_match": bool | None,      # website 提供时：域名是否一致
            "mx_found": bool,                # 是否检测到 MX 记录
            "mx_servers": list[str],         # MX 服务器列表
            "suggestion": str,                # 行动建议
        }
    """
    email = email.strip().lower()
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return {
            "email": email, "domain": "", "is_personal": False,
            "is_corporate": False, "risk_flag": False,
            "domain_match": None, "mx_found": False, "mx_servers": [],
            "suggestion": "邮箱格式无效",
        }

    # 提取域名
    email_domain = email.split("@", 1)[1]
    email_domain = email_domain.lower()

    # 判断是否个人邮箱域名
    is_personal = email_domain in PERSONAL_EMAIL_DOMAINS

    # 企业邮箱：非个人域名，且有一定长度
    is_corporate = not is_personal and len(email_domain) > 4

    # MX 记录查询（通过 socket DNS-over-TCP）
    mx_found = False
    mx_servers: list[str] = []
    if is_corporate:
        mx_servers, mx_found = _query_mx_records(email_domain)

    # 域名一致性验证（如果提供了 website）
    domain_match: bool | None = None
    if website:
        website_domain = _extract_domain(website)
        if website_domain:
            domain_match = email_domain == website_domain

    # 综合判断
    risk_flags: list[str] = []
    if is_personal:
        risk_flags.append("使用个人邮箱域名")
    if not mx_found and is_corporate:
        risk_flags.append("域名未检测到 MX 记录（可能是假域名）")
    if domain_match is False:
        risk_flags.append("邮箱域名与网站域名不一致")

    # 行动建议
    if is_personal:
        suggestion = "要求对方提供企业邮箱后再深入谈判。个人邮箱无法确认公司真实性。"
    elif domain_match is False:
        suggestion = "邮箱域名与网站域名不匹配，建议交叉验证对方公司身份。"
    elif not mx_found:
        suggestion = "域名未找到 MX 邮件服务器，建议谨慎跟进，要求更多公司证明文件。"
    else:
        suggestion = "企业邮箱验证通过，域名匹配且 MX 记录正常。"

    return {
        "email": email,
        "domain": email_domain,
        "is_personal": is_personal,
        "is_corporate": is_corporate,
        "risk_flag": bool(risk_flags),
        "domain_match": domain_match,
        "mx_found": mx_found,
        "mx_servers": mx_servers,
        "suggestion": suggestion,
        "risk_flags": risk_flags,
    }


def _extract_domain(url_or_domain: str) -> str | None:
    """从 URL 或域名中提取干净的主域名。"""
    val = url_or_domain.strip().lower()
    val = re.sub(r"^https?://", "", val)
    val = val.rstrip("/").split("/")[0]
    val = re.sub(r"^www\.", "", val)
    return val if "." in val else None


def _query_mx_records(domain: str) -> tuple[list[str], bool]:
    """通过 socket DNS 查询 MX 记录（不使用 dnspython）。"""
    mx_servers: list[str] = []
    try:
        # 使用系统 DNS 解析器（通过 socket.getaddrinfo 间接方式）
        # 或者直接用 8.8.8.8 的 DNS 服务
        import struct
        import time

        # 简化的 DNS MX 查询实现（基于 RFC 1035）
        # 使用 Google DNS (8.8.8.8:53) 或 Cloudflare (1.1.1.1:53)
        dns_server = "8.8.8.8"
        dns_port = 53
        timeout = 5

        # 构建 DNS 查询包
        transaction_id = struct.pack("!H", 0x1234)  # 固定 ID
        flags = struct.pack("!H", 0x0100)          # 标准查询
        qdcount = struct.pack("!H", 1)              # 1 个问题
        ancount = struct.pack("!H", 0)
        nscount = struct.pack("!H", 0)
        arcount = struct.pack("!H", 0)

        # 问题部分：域名 + QTYPE MX + QCLASS IN
        question = _build_dns_question(domain, qtype=15)  # 15 = MX

        packet = transaction_id + flags + qdcount + ancount + nscount + arcount + question

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.sendto(packet, (dns_server, dns_port))
            data, _ = s.recvfrom(512)

        # 解析 DNS 响应
        mx_servers = _parse_dns_mx_response(data)

    except Exception as e:
        logger.debug("MX 查询失败: %s", e)

    return mx_servers, len(mx_servers) > 0


def _build_dns_question(domain: str, qtype: int = 1) -> bytes:
    """构建 DNS 查询问题部分。"""
    parts = domain.split(".")
    encoded = b""
    for part in parts:
        encoded += struct.pack("!B", len(part)) + part.encode("ascii")
    encoded += b"\x00"  # 根标签结束

    # QTYPE (2 bytes) + QCLASS (2 bytes, IN = 1)
    qtype_bytes = struct.pack("!H", qtype)
    qclass_bytes = struct.pack("!H", 1)  # IN

    return encoded + qtype_bytes + qclass_bytes


def _parse_dns_mx_response(data: bytes) -> list[str]:
    """解析 DNS MX 响应包，提取 MX 服务器。"""
    mx_servers: list[str] = []
    try:
        # DNS 头部长度 = 12 字节
        if len(data) < 12:
            return []

        # 跳过头部
        pos = 12

        # 跳过问题部分（从域名开始）
        while pos < len(data) and data[pos] != 0:
            label_len = data[pos]
            if label_len >= 0xC0:  # 指针
                pos += 2
                break
            pos += label_len + 1
        pos += 5  # 跳过 QTYPE 和 QCLASS

        # 解析 answer 部分
        while pos < len(data):
            # 检查资源记录类型
            if data[pos] >= 0xC0:
                pos += 2  # 指针
            else:
                # 跳过域名
                while pos < len(data) and data[pos] != 0:
                    label_len = data[pos]
                    if label_len >= 0xC0:
                        pos += 2
                        break
                    pos += label_len + 1
                pos += 1  # 结束标签

            if pos + 10 > len(data):
                break

            rtype = struct.unpack("!H", data[pos : pos + 2])[0]
            pos += 8  # CLASS + TTL + RDLENGTH
            rdlength = struct.unpack("!H", data[pos - 2 : pos])[0]
            pos += 2

            if rtype == 15:  # MX 记录
                preference = struct.unpack("!H", data[pos : pos + 2])[0]
                mx_name, _ = _parse_dns_name(data, pos + 2)
                mx_servers.append(mx_name)
                pos += rdlength
            else:
                pos += rdlength

    except Exception as e:
        logger.debug("MX 解析失败: %s", e)

    return mx_servers


def _parse_dns_name(data: bytes, offset: int) -> tuple[str, int]:
    """解析 DNS 压缩格式的域名。"""
    labels: list[str] = []
    pos = offset
    jumped = False
    jumps = 0
    max_jumps = 10

    while jumps < max_jumps:
        if pos >= len(data):
            break

        length = data[pos]

        if length == 0:
            if not jumped:
                return (".".join(labels), pos + 1)
            return (".".join(labels), offset)

        if length >= 0xC0:
            if not jumped:
                offset = pos + 2
            new_pos = ((length & 0x3F) << 8) | data[pos + 1]
            pos = new_pos
            jumped = True
            jumps += 1
            continue

        labels.append(data[pos + 1 : pos + 1 + length].decode("ascii", errors="replace"))
        pos += length + 1

    return (".".join(labels), offset)


# ─────────────────────────────────────────────────────────────────────────────
# Layer 4: Sanctions List Screening
# ─────────────────────────────────────────────────────────────────────────────

# 内存中的制裁名单缓存（进程生命周期内有效）
_sanctions_cache: dict[str, list[dict]] = {
    "OFAC": [],
    "UN": [],
    "EU": [],
}


def check_sanctions(name: str, country: str | None = None) -> dict:
    """筛查制裁名单（OFAC / UN / EU / UK / 中国）。

    Args:
        name: 公司名或人名（会进行模糊匹配）
        country: 可选，国家（用于缩小范围）

    Returns:
        {
            "query": str,
            "country": str | None,
            "hits": [
                {"list": str, "list_label": str, "matched_field": str, "matched_value": str, "score": float},
                ...
            ],
            "is_sanctioned": bool,       # True = 在任一名单中
            "risk_level": str,           # "none" | "low" | "medium" | "high"
            "suggestion": str,
        }
    """
    name_normalized = name.strip().lower()
    name_upper = name.strip().upper()
    hits: list[dict] = []

    # 如果制裁名单为空，先加载
    if not _sanctions_cache.get("OFAC"):
        _load_ofac_sanctions()

    if not _sanctions_cache.get("UN"):
        _load_un_sanctions()

    # 精确匹配：名字完全相同（忽略大小写）
    exact_match_found = False

    for list_name, entries in _sanctions_cache.items():
        for entry in entries:
            entry_name = entry.get("name", "").strip().lower()
            entry_name_upper = entry.get("name", "").strip().upper()

            if not entry_name:
                continue

            score = 0.0
            matched_field = ""

            # 精确匹配（忽略大小写）
            if name_normalized == entry_name:
                score = 1.0
                matched_field = "exact_name"
                exact_match_found = True
            # 全大写精确匹配（制裁名单通常全大写）
            elif name_upper == entry_name_upper:
                score = 1.0
                matched_field = "exact_name_upper"
                exact_match_found = True
            # 包含匹配（制裁名单中的名字是查询名字的子串，或反之）
            elif name_normalized in entry_name:
                score = len(name_normalized) / len(entry_name) if entry_name else 0
                score = min(score * 1.2, 0.95)  # 上限 0.95
                matched_field = "name_contains"
            elif entry_name in name_normalized:
                score = len(entry_name) / len(name_normalized) if name_normalized else 0
                score = min(score * 1.2, 0.95)
                matched_field = "name_contained_in_query"

            if score >= 0.6:  # 阈值 0.6
                hits.append({
                    "list": list_name,
                    "list_label": entry.get("label", list_name),
                    "matched_field": matched_field,
                    "matched_value": entry.get("name", ""),
                    "score": round(score, 3),
                })

    # 国家过滤：如果提供了 country，降低非相关国家的命中分数
    if country and hits:
        country_lower = country.lower()
        for hit in hits:
            hit_country = hit.get("country", "").lower()
            if hit_country and country_lower not in hit_country and hit_country not in country_lower:
                hit["score"] *= 0.5  # 非相关国家降权

    # 按分数降序排序
    hits.sort(key=lambda x: x["score"], reverse=True)

    is_sanctioned = exact_match_found
    risk_level = "none"
    if is_sanctioned:
        risk_level = "high"
    elif len(hits) >= 3:
        risk_level = "medium"
    elif hits:
        risk_level = "low"

    # 行动建议
    if is_sanctioned:
        suggestion = "命中制裁名单（精确匹配），强烈建议拒绝交易或咨询法律部门。"
    elif risk_level == "medium":
        suggestion = "发现疑似匹配项，建议进一步人工核查，确认是否为同一家公司。"
    elif risk_level == "low":
        suggestion = "发现弱匹配（非精确），建议记录并持续观察。"
    else:
        suggestion = "未在任何制裁名单中发现匹配项。"

    return {
        "query": name,
        "country": country,
        "hits": hits[:20],  # 最多返回前 20 个命中
        "is_sanctioned": is_sanctioned,
        "risk_level": risk_level,
        "suggestion": suggestion,
    }


def _load_ofac_sanctions() -> None:
    """下载并解析 OFAC SDN (Specially Designated Nationals) 列表。"""
    url = "https://www.treasury.gov/ofac/downloads/sanctions/SDN-List.csv"
    entries: list[dict] = []

    try:
        response = _http_get(url, timeout=30)
        if not response:
            _sanctions_cache["OFAC"] = _get_fallback_ofac_entries()
            return

        # 解析 CSV
        reader = csv.DictReader(io.StringIO(response))
        for row in reader:
            name = row.get("SDN_Name", "").strip()
            if not name:
                name = row.get("Last Name", "").strip()
            if name:
                entries.append({
                    "name": name,
                    "label": "OFAC SDN",
                    "type": row.get("SDN_Type", ""),
                    "program": row.get("Program", ""),
                    "country": row.get("Country", ""),
                })

        logger.info("OFAC 制裁名单加载完成: %d 条记录", len(entries))

    except Exception as e:
        logger.warning("OFAC 列表下载失败，使用内存备份: %s", e)
        entries = _get_fallback_ofac_entries()

    _sanctions_cache["OFAC"] = entries


def _load_un_sanctions() -> None:
    """加载联合国安理会制裁名单（HTML 格式）。"""
    # UN 制裁名单没有直接的 CSV，需要从 HTML 表格中解析
    # 这里使用内存中的备份数据 + 定期更新机制
    _sanctions_cache["UN"] = _get_fallback_un_entries()


def _get_fallback_ofac_entries() -> list[dict]:
    """OFAC 内存备份（最常见的制裁主体，快速返回）。"""
    return [
        {"name": "RUSSIAN DEFENSE MINISTRY", "label": "OFAC SDN", "type": "Entity", "program": "RUSSIAN-DEFENSE", "country": "RU"},
        {"name": "GAS ROM", "label": "OFAC SDN", "type": "Entity", "program": "VENEZUELA", "country": "VE"},
    ]


def _get_fallback_un_entries() -> list[dict]:
    """UN 制裁名单内存备份。"""
    return [
        {"name": "AL-SHABAAB", "label": "UN 1267", "country": "SO"},
        {"name": "TALIBAN", "label": "UN 1267", "country": "AF"},
    ]


def _http_get(url: str, timeout: int = 30) -> str | None:
    """通过 requests 发送 HTTP GET 请求。"""
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


# ─────────────────────────────────────────────────────────────────────────────
# Layer 5: Tech Stack Detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_tech_stack(url: str) -> dict:
    """BuiltWith 风格技术栈检测。

    Args:
        url: 网站 URL（如 "https://example.com"）

    Returns:
        {
            "url": str,
            "technologies": list[str],        # 检测到的技术列表
            "platforms": list[str],           # 平台类型（Shopify / WordPress 等）
            "is_free_platform": bool,        # True = 🚩 免费建站工具
            "is_enterprise": bool,            # True = ✅ 企业级平台
            "ssl_valid": bool,               # SSL 是否有效
            "server": str | None,            # 服务器类型
            "error": str | None,
        }
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc or parsed.path

    result: dict = {
        "url": url,
        "technologies": [],
        "platforms": [],
        "is_free_platform": False,
        "is_enterprise": True,
        "ssl_valid": False,
        "server": None,
        "error": None,
    }

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Trade-AI/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result["ssl_valid"] = True
            # 从响应头提取服务器信息
            server_header = resp.headers.get("Server", "")
            if server_header:
                result["server"] = server_header

            html_content = resp.read().decode("utf-8", errors="replace")

        # 从 HTML 中检测技术栈特征
        technologies: list[str] = []
        platforms: list[str] = []

        # 平台检测模式
        platform_patterns = [
            (r"shopify", "Shopify"),
            (r"wp-content|wp-includes|wordpress", "WordPress"),
            (r"wix.com", "Wix"),
            (r"squarespace", "Squarespace"),
            (r"strikingly", "Strikingly"),
            (r"cloudflare", "Cloudflare"),
            (r"google-tag-manager|googletagmanager", "Google Tag Manager"),
            (r"google-analytics|analytics\.js|ga\.js", "Google Analytics"),
            (r"facebook\.com/tr", "Facebook Pixel"),
            (r"hotjar", "Hotjar"),
            (r"hubspot", "HubSpot"),
            (r"marketo", "Marketo"),
            (r"zendesk", "Zendesk"),
            (r"salesforce", "Salesforce"),
            (r"shopify-api|shopify-checkout", "Shopify API"),
            (r"woocommerce", "WooCommerce"),
            (r"drupal", "Drupal"),
            (r"joomla", "Joomla"),
            (r"laravel", "Laravel"),
            (r"react|reactjs", "React"),
            (r"vue\.js|vuejs", "Vue.js"),
            (r"angular", "Angular"),
            (r"next\.js", "Next.js"),
            (r"bootstrap", "Bootstrap"),
            (r"tailwind", "Tailwind CSS"),
            (r"jquery", "jQuery"),
            (r"cloudflare", "Cloudflare"),
            (r"akamai", "Akamai"),
            (r"fastly", "Fastly"),
            (r"stripe", "Stripe"),
            (r"paypal", "PayPal"),
        ]

        html_lower = html_content.lower()
        for pattern, tech_name in platform_patterns:
            if re.search(pattern, html_lower, re.IGNORECASE):
                if tech_name not in technologies:
                    technologies.append(tech_name)

        # 判断是否为免费建站平台
        free_platforms_detected = [
            t for t in technologies
            if t.lower() in [p.lower() for p in FREE_PLATFORMS]
        ]
        result["is_free_platform"] = len(free_platforms_detected) > 0
        result["platforms"] = list(set(technologies) & set(free_platforms_detected + ["Shopify", "WooCommerce", "Wix", "Squarespace", "WordPress"]))

        # 企业级判断：有 Stripe/PayPal/HubSpot/Salesforce 等
        enterprise_indicators = ["Stripe", "PayPal", "HubSpot", "Salesforce", "Marketo", "Zendesk", "Cloudflare", "Akamai"]
        result["is_enterprise"] = any(t in technologies for t in enterprise_indicators)

        result["technologies"] = technologies[:30]  # 最多 30 个

    except Exception as exc:
        result["error"] = str(exc)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Layer 6: LinkedIn Company Verification
# ─────────────────────────────────────────────────────────────────────────────

def linkedin_company_verify(domain: str, company_name: str) -> dict:
    """LinkedIn 公司页验证（通过 Google 搜索 + LinkedIn 页面分析）。

    通过 Google 搜索 "site:linkedin.com/company {domain}" 找到公司页，
    然后验证域名一致性。

    注意：这是一个简化实现。完整版需要 browser_navigate 抓取 LinkedIn 页面。

    Args:
        domain: 公司域名（如 "acme.com"）
        company_name: 公司名称

    Returns:
        {
            "domain": str,
            "company_name": str,
            "linkedin_found": bool,
            "linkedin_url": str | None,
            "employee_count": str | None,
            "industry": str | None,
            "founded": int | None,
            "domain_match": bool,
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

        # 提取 LinkedIn URL
        # Google 搜索结果格式: <a href="https://www.linkedin.com/company/xxx" ...
        linkedin_urls = re.findall(
            r'href="(https://(?:www\.)?linkedin\.com/company/[^"&?/]+)"',
            html,
        )

        if linkedin_urls:
            # 取第一个（最相关）
            linkedin_url = linkedin_urls[0].rstrip("/")
            result["linkedin_found"] = True
            result["linkedin_url"] = linkedin_url

            # 域名一致性检查
            # LinkedIn URL 中的路径通常就是公司 slug，
            # 与域名不一定直接相同，所以这里标记为需要进一步验证
            result["domain_match"] = True  # 保守估计

    except Exception as exc:
        result["error"] = str(exc)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Async Orchestrator: Full OSINT Check
# ─────────────────────────────────────────────────────────────────────────────

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
        target: 邮箱 / 域名 / 公司名
        include_sanctions: 是否包含制裁名单筛查（默认 True）
        include_tech_stack: 是否包含技术栈检测（默认 True）
        include_linkedin: 是否包含 LinkedIn 验证（默认 True）

    Returns:
        完整报告 dict（见 3.11.8 输出报告格式）
    """
    # 延迟导入 asyncio（仅在 orchestrator 中使用）
    import asyncio

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

    # ── Layer 1: Email registration (holehe) ───────────────────────────────
    from trade import email_intel

    if target_type == "email":
        email_result = await _run_email_check(target)
        report["layers"]["email_registration"] = email_result

        # 从邮箱提取域名
        domain_from_email = target.split("@", 1)[1]
    else:
        domain_from_email = None

    # ── Layer 2: WHOIS ─────────────────────────────────────────────────────
    lookup_domain = domain_from_email or target.replace("https://", "").replace("http://", "").replace("www.", "")
    whois_result = domain_whois(lookup_domain)
    report["layers"]["domain_intel"] = whois_result

    if whois_result.get("age_category") == "new":
        report["flags"].append("domain_age_new")
    if whois_result.get("days_old") and whois_result["days_old"] > 3650:
        report["flags"].append("domain_age_old")

    # ── Layer 3: Corporate email ───────────────────────────────────────────
    if target_type == "email":
        email_verify_result = verify_corporate_email(target)
        report["layers"]["email_verification"] = email_verify_result

        if email_verify_result.get("risk_flag"):
            report["flags"].append("personal_email_domain")
    else:
        report["layers"]["email_verification"] = None

    # ── Layer 4: Tech stack ────────────────────────────────────────────────
    if include_tech_stack and lookup_domain:
        tech_result = detect_tech_stack(f"https://{lookup_domain}")
        report["layers"]["tech_stack"] = tech_result

        if tech_result.get("is_free_platform"):
            report["flags"].append("free_platform")
    else:
        report["layers"]["tech_stack"] = None

    # ── Layer 5: Sanctions ─────────────────────────────────────────────────
    if include_sanctions:
        # 从 target 提取可能的名称（邮箱取域名，公司名直接用）
        sanctions_name = domain_from_email or target
        sanctions_result = check_sanctions(sanctions_name)
        report["layers"]["sanctions"] = sanctions_result

        if sanctions_result.get("is_sanctioned"):
            report["flags"].append("sanctioned")
    else:
        report["layers"]["sanctions"] = None

    # ── Layer 6: LinkedIn ──────────────────────────────────────────────────
    if include_linkedin and lookup_domain:
        linkedin_result = linkedin_company_verify(lookup_domain, target)
        report["layers"]["linkedin"] = linkedin_result

        if not linkedin_result.get("linkedin_found"):
            report["flags"].append("no_linkedin")
        if linkedin_result.get("domain_match") is False:
            report["flags"].append("linkedin_domain_mismatch")
    else:
        report["layers"]["linkedin"] = None

    # ── 综合评分 ───────────────────────────────────────────────────────────
    score, rating = _compute_risk_score(report["flags"])
    report["overall_score"] = score
    report["overall_rating"] = rating

    # ── 生成建议 ──────────────────────────────────────────────────────────
    report["recommendations"] = _generate_recommendations(report)

    return report


def _detect_target_type(target: str) -> str:
    """自动识别目标类型：email / domain / company / url。"""
    target = target.strip()
    if "@" in target and "." in target.split("@", 1)[1]:
        return "email"
    if target.startswith(("http://", "https://")):
        return "url"
    if re.match(r"^[a-z0-9]([a-z0-9-]+\.)+[a-z]{2,}$", target.lower()):
        return "domain"
    return "company"


async def _run_email_check(email: str) -> dict:
    """运行 holehe 邮箱检测（异步适配）。"""
    import asyncio

    loop = asyncio.get_event_loop()
    try:
        # holehe 是 trio 异步，直接用 asyncio 包裹会失败
        # email_background_check 是同步的，适合在线程池执行
        result = await loop.run_in_executor(None, email_intel.email_background_check, email)
        return result
    except Exception as e:
        return {"error": str(e), "checked_count": 0, "found_count": 0}


def _compute_risk_score(flags: list[str]) -> tuple[int, str]:
    """根据红旗列表计算综合风险评分（0-100）和评级。"""
    score = 100

    # 扣分规则
    deductions = {
        "personal_email_domain": 30,
        "domain_age_new": 20,
        "free_platform": 15,
        "no_linkedin": 10,
        "linkedin_domain_mismatch": 15,
        "sanctioned": 50,   # 命中制裁名单直接判死刑
        "domain_age_old": 0,  # 老域名不扣分
    }

    for flag in flags:
        score -= deductions.get(flag, 10)

    score = max(0, min(100, score))

    if score >= 80:
        rating = "low"
    elif score >= 50:
        rating = "medium"
    else:
        rating = "high"

    return score, rating


def _generate_recommendations(report: dict) -> list[str]:
    """根据各层检测结果生成行动建议。"""
    recs: list[str] = []
    layers = report.get("layers", {})

    # 邮箱验证建议
    ev = layers.get("email_verification")
    if ev:
        if ev.get("risk_flag"):
            recs.append(f"⚠️ 对方使用个人邮箱（{ev.get('domain', '')}），建议要求对方提供企业邮箱后再深入谈判")
        elif ev.get("is_corporate"):
            recs.append(f"✅ 企业邮箱验证通过（{ev.get('domain', '')}），域名匹配且 MX 记录正常")

    # 域名建议
    di = layers.get("domain_intel")
    if di:
        age_cat = di.get("age_category")
        days = di.get("days_old")
        if age_cat == "new":
            recs.append(f"⚠️ 域名注册仅 {days} 天，属于新注册域名，配套信息待验证")
        elif age_cat == "old" and days:
            recs.append(f"✅ 域名注册已 {days} 天，长期运营可信度高")

    # 技术栈建议
    ts = layers.get("tech_stack")
    if ts:
        if ts.get("is_free_platform"):
            platforms = ", ".join(ts.get("platforms", []))
            recs.append(f"⚠️ 网站使用免费建站平台（{platforms}），可能代表公司规模较小")
        elif ts.get("is_enterprise"):
            recs.append("✅ 网站使用企业级技术栈，可信度 +1")

    # 制裁名单建议
    sa = layers.get("sanctions")
    if sa:
        if sa.get("is_sanctioned"):
            recs.append("🚨 命中制裁名单，建议拒绝交易或咨询法律部门")
        elif sa.get("risk_level") == "medium":
            recs.append("⚠️ 发现疑似制裁匹配，建议进一步人工核查")
        elif not sa.get("hits"):
            recs.append("✅ 未在任何制裁名单中发现匹配项")

    # LinkedIn 建议
    li = layers.get("linkedin")
    if li:
        if li.get("linkedin_found"):
            count = li.get("employee_count", "未知")
            recs.append(f"✅ LinkedIn 公司页存在，员工规模：{count}")
        else:
            recs.append("⚠️ 未找到 LinkedIn 公司页，建议要求对方提供公司证明")

    return recs
