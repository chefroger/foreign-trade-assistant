"""
Trade AI Assistant — OSINT Layer 3: 企业邮箱验证。

判断邮箱是企业邮箱 (@公司域名) 还是个人邮箱 (@gmail/@qq等)，
并通过 DNS MX 记录查询验证域名是否配置了邮件服务器。
"""

from __future__ import annotations

import logging
import re
import socket
import struct

from trade.osint.constants import PERSONAL_EMAIL_DOMAINS

logger = logging.getLogger(__name__)


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
            "risk_flags": list[str],         # 风险标记详情
            "suggestion": str,                # 行动建议
        }
    """
    email = email.strip().lower()
    # 邮箱格式校验
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        # 邮箱格式不合法，返回无效状态
        return {
            "email": email, "domain": "", "is_personal": False,
            "is_corporate": False, "risk_flag": False,
            "domain_match": None, "mx_found": False, "mx_servers": [],
            "risk_flags": [], "suggestion": "邮箱格式无效",
        }

    # 提取域名
    email_domain = email.split("@", 1)[1]
    email_domain = email_domain.lower()

    # 判断是否个人邮箱域名
    is_personal = email_domain in PERSONAL_EMAIL_DOMAINS

    # 企业邮箱：非个人域名，且有一定长度（排除如 "a.co" 等短域名误判）
    is_corporate = not is_personal and len(email_domain) > 4

    # MX 记录查询（通过 socket DNS-over-UDP）
    mx_found = False
    mx_servers: list[str] = []
    if is_corporate:
        mx_servers, mx_found = _query_mx_records(email_domain)

    # 域名一致性验证（如果提供了 website）
    domain_match: bool | None = None
    if website:
        # 提取 website 的域名并与邮箱域名比较
        website_domain = _extract_domain(website)
        if website_domain:
            # 邮箱域名与网站域名一致则为 True，否则为 False
            domain_match = email_domain == website_domain

    # 综合判断红旗
    risk_flags: list[str] = []
    if is_personal:
        # 个人邮箱域名，红旗标记
        risk_flags.append("使用个人邮箱域名")
    if not mx_found and is_corporate:
        # 企业域名但无 MX 记录，可能为假域名
        risk_flags.append("域名未检测到 MX 记录（可能是假域名）")
    if domain_match is False:
        # 邮箱域名与网站域名不一致，红旗标记
        risk_flags.append("邮箱域名与网站域名不一致")

    # 行动建议（分场景）
    if is_personal:
        # 个人邮箱场景：建议要求企业邮箱
        suggestion = "要求对方提供企业邮箱后再深入谈判。个人邮箱无法确认公司真实性。"
    elif domain_match is False:
        # 域名不匹配场景：建议交叉验证
        suggestion = "邮箱域名与网站域名不匹配，建议交叉验证对方公司身份。"
    elif not mx_found:
        # 无 MX 记录场景：建议谨慎
        suggestion = "域名未找到 MX 邮件服务器，建议谨慎跟进，要求更多公司证明文件。"
    else:
        # 所有验证通过场景
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
        "risk_flags": risk_flags,
        "suggestion": suggestion,
    }


def _extract_domain(url_or_domain: str) -> str | None:
    """从 URL 或域名中提取干净的主域名。"""
    val = url_or_domain.strip().lower()
    val = re.sub(r"^https?://", "", val)
    val = val.rstrip("/").split("/")[0]
    val = re.sub(r"^www\.", "", val)
    if val and "." in val:
        return val
    # 没有点号分隔，不是合法域名
    return None


# ─────────────────────────────────────────────────────────────────────────────
# DNS MX 查询（sockets-only，不依赖 dnspython）
# ─────────────────────────────────────────────────────────────────────────────

def _query_mx_records(domain: str) -> tuple[list[str], bool]:
    """通过 socket DNS 查询 MX 记录（RFC 1035 协议实现）。

    使用多 DNS 服务器 fallback 列表，transaction_id 随机生成防 DNS 欺骗。
    """
    import secrets as _secrets

    dns_servers = ["8.8.8.8", "1.1.1.1", "114.114.114.114"]
    dns_port = 53
    timeout = 5
    last_err = None

    for dns_server in dns_servers:
        try:
            # 随机 transaction_id，防 DNS 欺骗
            txid = _secrets.token_bytes(2)
            flags = struct.pack("!H", 0x0100)         # 标准查询
            qdcount = struct.pack("!H", 1)
            zeros = struct.pack("!HHH", 0, 0, 0)      # ancount/nscount/arcount

            question = _build_dns_question(domain, qtype=15)
            packet = txid + flags + qdcount + zeros + question

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(timeout)
                s.sendto(packet, (dns_server, dns_port))
                data, _ = s.recvfrom(512)

            # 校验响应 transaction_id 必须与请求一致
            if len(data) < 12 or data[:2] != txid:
                # transaction_id 不匹配，可能为 DNS 欺骗或乱序响应，跳过该服务器
                logger.debug("DNS txid mismatch: %s", dns_server)
                continue

            mx_servers = _parse_dns_mx_response(data)
            # 解析到至少一条 MX 记录即为成功
            return mx_servers, len(mx_servers) > 0

        except (TimeoutError, OSError) as e:
            # 当前 DNS 服务器超时或网络错误，尝试下一台服务器
            last_err = e
            continue

    # 所有 DNS 服务器均失败，返回空结果
    logger.debug("MX 查询全部失败 [%s]: %s", domain, last_err)
    return [], False


def _build_dns_question(domain: str, qtype: int = 1) -> bytes:
    """构建 DNS 查询问题部分（RFC 1035 格式）。

    Args:
        domain: 域名（如 "example.com"）
        qtype: 查询类型（1=A, 15=MX, 16=TXT）
    """
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
    """解析 DNS MX 响应包，提取 MX 服务器列表。

    处理 DNS 压缩指针格式（RFC 1035）。
    """
    mx_servers: list[str] = []
    try:
        if len(data) < 12:
            # 数据过短，不包含合法 DNS 头部
            return []

        # DNS 头部 = 12 字节，从 body 开始解析
        pos = 12

        # 跳过问题部分（域名 + QTYPE + QCLASS）
        while pos < len(data) and data[pos] != 0:
            label_len = data[pos]
            if label_len >= 0xC0:  # 压缩指针
                pos += 2
                break
            pos += label_len + 1
        pos += 5  # 跳过 QTYPE(2) + QCLASS(2) 的结尾 \x00(1)

        # 解析 answer 部分
        while pos < len(data):
            # 解析资源记录名称（可能是压缩指针）
            if data[pos] >= 0xC0:
                # 压缩指针格式，跳过 2 字节
                pos += 2
            else:
                # 逐标签跳过域名（普通标签格式）
                while pos < len(data) and data[pos] != 0:
                    label_len = data[pos]
                    if label_len >= 0xC0:
                        # 遇到压缩指针，跳转
                        pos += 2
                        break
                    pos += label_len + 1
                pos += 1  # 结束标签 \x00

            if pos + 10 > len(data):
                # 剩余数据不足以解析记录头部，退出
                break

            rtype = struct.unpack("!H", data[pos:pos + 2])[0]
            pos += 8  # CLASS(2) + TTL(4) + RDLENGTH(2)
            rdlength = struct.unpack("!H", data[pos - 2:pos])[0]
            pos += 2

            if rtype == 15:  # MX 记录
                preference = struct.unpack("!H", data[pos:pos + 2])[0]  # noqa: F841
                mx_name, _ = _parse_dns_name(data, pos + 2)
                mx_servers.append(mx_name)
                pos += rdlength
            else:
                # 非 MX 记录，跳过即可
                pos += rdlength

    except Exception as e:
        # 解析异常时记录日志，返回已解析到的部分结果
        logger.debug("MX 解析失败: %s", e)

    return mx_servers


def _parse_dns_name(data: bytes, offset: int) -> tuple[str, int]:
    """解析 DNS 压缩格式的域名（RFC 1035 标签格式 + 指针压缩）。

    Returns:
        (解析后的域名字符串, 结束偏移量)
    """
    labels: list[str] = []
    pos = offset
    jumped = False
    jumps = 0
    max_jumps = 10  # 防止指针循环

    while jumps < max_jumps:
        if pos >= len(data):
            # 超出数据边界，终止解析
            break

        length = data[pos]

        if length == 0:
            # 标签序列结束
            if not jumped:
                # 未跳转过，返回当前位置之后的偏移量
                return (".".join(labels), pos + 1)
            # 已跳转过，返回第一次跳转前的偏移量
            return (".".join(labels), offset)

        if length >= 0xC0:
            # 压缩指针：跳转到指针位置继续解析
            if not jumped:
                # 第一次遇到压缩指针，记录返回位置
                offset = pos + 2
            new_pos = ((length & 0x3F) << 8) | data[pos + 1]
            pos = new_pos
            jumped = True
            jumps += 1
            continue

        # 普通标签：读取标签内容
        labels.append(data[pos + 1:pos + 1 + length].decode("ascii", errors="replace"))
        pos += length + 1

    # 超过最大跳转次数，返回当前已解析结果
    return (".".join(labels), offset)
