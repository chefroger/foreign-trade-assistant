"""
Trade AI Assistant — OSINT Layer 2: WHOIS 域名查询。

通过 socket 直接发送 IANA WHOIS 协议请求，无需第三方库。
支持 20+ 顶级域名的权威 WHOIS 服务器路由。
"""

from __future__ import annotations

import re
import socket
from datetime import datetime, timezone
from typing import Optional


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
        whois_response = _query_whois_server(domain, whois_server)

        if not whois_response:
            result["error"] = "WHOIS 服务器无响应"
            return result

        # Step 2: 解析 WHOIS 响应
        parsed = _parse_whois_response(whois_response)

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


# ─────────────────────────────────────────────────────────────────────────────
# WHOIS 服务器路由表
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Socket WHOIS 协议通信
# ─────────────────────────────────────────────────────────────────────────────

def _query_whois_server(domain: str, server: str, port: int = 43, timeout: int = 10) -> str:
    """通过 socket 连接 WHOIS 服务器并返回原始响应。

    如果主服务器超时，自动尝试 fallback WHOIS 服务器。
    """
    try:
        with socket.create_connection((server, port), timeout=timeout) as s:
            s.settimeout(timeout)
            # WHOIS 协议：发送域名 + \r\n
            s.sendall(f"{domain}\r\n".encode("utf-8"))

            chunks: list[bytes] = []
            while True:
                try:
                    chunk = s.recv(4096)
                except socket.timeout:
                    # 超时后已读到的数据视为完整响应
                    break
                if not chunk:
                    # 对端关闭连接，唯一可靠的结束信号
                    break
                chunks.append(chunk)

        response = b"".join(chunks).decode("utf-8", errors="replace")
        return response

    except (socket.timeout, socket.error, OSError):
        # 如果主服务器超时，尝试 fallback WHOIS 服务器
        fallback_servers = ["whois.verisign.com", "whois.markmonitor.com"]
        for fb_server in fallback_servers:
            if fb_server == server:
                continue
            try:
                return _query_whois_server(domain, fb_server, port, timeout=5)
            except Exception:
                continue
        raise


# ─────────────────────────────────────────────────────────────────────────────
# WHOIS 响应解析
# ─────────────────────────────────────────────────────────────────────────────

def _parse_whois_response(raw: str) -> dict:
    """解析 WHOIS 原始响应文本，提取关键结构化字段。

    处理主流 WHOIS 服务器的响应格式差异（VeriSign、PIR、CNNIC 等）。
    """
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

        # 尝试 "Key: Value" 格式解析
        colon_idx = line.find(":")
        if colon_idx > 0:
            key = line[:colon_idx].strip().lower()
            value = line[colon_idx + 1:].strip()

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


# ─────────────────────────────────────────────────────────────────────────────
# 日期标准化
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_date(date_str: str) -> Optional[str]:
    """将各种日期格式统一转换为 ISO 格式（YYYY-MM-DD）。"""
    if not date_str:
        return None

    date_str = date_str.strip()

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
