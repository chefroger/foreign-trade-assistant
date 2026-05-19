"""
Trade AI Assistant — 邮件情报（OSINT 背景调查）。

使用 holehe 检查邮箱是否在 120+ 网站注册，并检索这些账户的公开资料信息。

本模块是自包含的：内部导入 holehe，如果 holehe 未安装则优雅降级
（返回错误 dict 而非抛出异常）。

公开 API
────────
email_background_check(email: str) -> dict
    同步封装。在线程池中运行 holehe，返回结构化报告。

流式 API（推荐用于流式端点）
────────────────────────────────
EmailBackgroundChecker.check(email: str) -> AsyncIterator[dict]
    逐站结果到达时逐一 yield（site → exists → details）。
    最后一个 yield 是汇总 dict。

输出格式
────────
{
    "email": "user@example.com",
    "checked_count": 121,
    "found_count": 5,
    "results": [
        {
            "site": "github.com",
            "site_display": "GitHub",
            "exists": True,
            "rate_limited": False,
            "email_recovery": "u***r@example.com",
            "phone_number": "+1***4567",
            "profile_url": "https://github.com/username",
            "created_date": "2020-03-15",
            "others": {}
        },
        ...
    ],
    "social_profiles": {
        "github": "https://github.com/username",
        "linkedin": "https://linkedin.com/in/username",
        ...
    },
    "error": None   # 正常则 None，holehe 未安装则返回错误字符串
}
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import typing
from collections.abc import AsyncIterator

# ── holehe 导入（懒加载，优雅降级）───────────────────────────────────────────────

_holehe_available: bool | None = None
_holehe_import_error: str | None = None


def _check_holehe() -> bool:
    """检查 holehe 库是否已安装。使用缓存避免重复检测。"""
    global _holehe_available, _holehe_import_error
    # 已缓存结果，直接返回
    if _holehe_available is not None:
        return _holehe_available
    try:
        import importlib.util
        # 验证 holehe 可导入（不实际 import 子模块，避免 F401）
        if importlib.util.find_spec("holehe") is None:
            raise ImportError("holehe not found")
        _holehe_available = True
    except ImportError as exc:
        # holehe 未安装，标记为不可用并记录错误信息
        _holehe_available = False
        _holehe_import_error = str(exc)
    return _holehe_available


# ── 校验 ────────────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_valid_email(email: str) -> bool:
    """验证邮箱地址是否符合基本格式。"""
    return bool(_EMAIL_RE.match(email.strip()))


# ── 站点元数据 ──────────────────────────────────────────────────────────────────

_SITE_DISPLAY_NAME: dict[str, str] = {
    "twitter.com": "Twitter / X",
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "github.com": "GitHub",
    "linkedin.com": "LinkedIn",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "discord.com": "Discord",
    "reddit.com": "Reddit",
    "pinterest.com": "Pinterest",
    "snapchat.com": "Snapchat",
    "threads.net": "Threads",
    "medium.com": "Medium",
    "quora.com": "Quora",
    "stackoverflow.com": "Stack Overflow",
    "devrant.com": "DevRant",
    "keybase.io": "Keybase",
    "producthunt.com": "Product Hunt",
    "replit.com": "Replit",
    "codepen.io": "CodePen",
    "codesandbox.io": "CodeSandbox",
    "bitbucket.org": "Bitbucket",
    "gitlab.com": "GitLab",
    "npmjs.com": "npm",
    "pypi.org": "PyPI",
    "hub.docker.com": "Docker Hub",
    "slack.com": "Slack",
    "trello.com": "Trello",
    "notion.so": "Notion",
    "loom.com": "Loom",
    "canva.com": "Canva",
    "figma.com": "Figma",
    "behance.net": "Behance",
    "dribbble.com": "Dribbble",
    "etsy.com": "Etsy",
    "shopify.com": "Shopify",
    "amazon.com": "Amazon",
    "ebay.com": "eBay",
    "alibaba.com": "Alibaba",
    "aliexpress.com": "AliExpress",
    "freelancer.com": "Freelancer",
    "upwork.com": "Upwork",
    "fiverr.com": "Fiverr",
    "peopleperhour.com": "PeoplePerHour",
    "toptal.com": "Toptal",
    "xing.com": "XING",
    "viadeo.com": "Viadeo",
    "angel.co": "AngelList",
    "mastodon.social": "Mastodon",
    "last.fm": "Last.fm",
    "spotify.com": "Spotify",
    "soundcloud.com": "SoundCloud",
    "bandcamp.com": "Bandcamp",
    "tinder.com": "Tinder",
    "bumble.com": "Bumble",
    "hinge.com": "Hinge",
    "match.com": "Match.com",
    "okcupid.com": "OKCupid",
    "zoosk.com": "Zoosk",
    "paypal.com": "PayPal",
    "stripe.com": "Stripe",
    "squareup.com": "Square",
    "eventbrite.com": "Eventbrite",
    "meetup.com": "Meetup",
    "mail.ru": "Mail.ru",
    "vk.com": "VK",
    "ok.ru": "OK.ru",
    "yahoo.com": "Yahoo",
    "outlook.com": "Outlook",
    "protonmail.com": "ProtonMail",
    "icloud.com": "iCloud",
    "dropbox.com": "Dropbox",
    "drive.google.com": "Google Drive",
    "asana.com": "Asana",
    "deviantart.com": "DeviantArt",
}

_SITE_SOCIAL: set[str] = {
    "twitter.com", "instagram.com", "facebook.com", "github.com",
    "linkedin.com", "tiktok.com", "youtube.com", "discord.com",
    "reddit.com", "pinterest.com", "snapchat.com", "threads.net",
    "mastodon.social", "medium.com", "quora.com", "stackoverflow.com",
    "devrant.com", "keybase.io", "producthunt.com", "replit.com",
    "codepen.io", "bitbucket.org", "gitlab.com",
}

# 个人资料 URL 模板 — 用户名从 holehe 的 "others" 字段提取
_PROFILE_URL_TEMPLATE: dict[str, str] = {
    "twitter.com": "https://twitter.com/{username}",
    "instagram.com": "https://www.instagram.com/{username}",
    "github.com": "https://github.com/{username}",
    "linkedin.com": "https://www.linkedin.com/in/{username}",
    "tiktok.com": "https://www.tiktok.com/@{username}",
    "youtube.com": "https://www.youtube.com/@{username}",
    "reddit.com": "https://www.reddit.com/user/{username}",
    "pinterest.com": "https://www.pinterest.com/{username}",
    "snapchat.com": "https://www.snapchat.com/add/{username}",
    "threads.net": "https://www.threads.net/@{username}",
    "mastodon.social": "https://mastodon.social/@{username}",
    "medium.com": "https://medium.com/@{username}",
    "quora.com": "https://www.quora.com/profile/{username}",
    "stackoverflow.com": "https://stackoverflow.com/users/{username}",
    "devrant.com": "https://devrant.com/users/{username}",
    "keybase.io": "https://keybase.io/{username}",
    "producthunt.com": "https://www.producthunt.com/@{username}",
    "replit.com": "https://replit.com/@{username}",
    "codepen.io": "https://codepen.io/{username}",
    "bitbucket.org": "https://bitbucket.org/{username}",
    "gitlab.com": "https://gitlab.com/{username}",
    "last.fm": "https://www.last.fm/user/{username}",
    "spotify.com": "https://open.spotify.com/user/{username}",
    "soundcloud.com": "https://soundcloud.com/{username}",
    "deviantart.com": "https://www.deviantart.com/{username}",
    "behance.net": "https://www.behance.net/{username}",
    "dribbble.com": "https://dribbble.com/{username}",
    "etsy.com": "https://www.etsy.com/shop/{username}",
    "freelancer.com": "https://www.freelancer.com/u/{username}",
    "upwork.com": "https://www.upwork.com/freelancers/{username}",
    "fiverr.com": "https://www.fiverr.com/{username}",
    "xing.com": "https://www.xing.com/profile/{username}",
    "angel.co": "https://angel.co/{username}",
}


def _display_name(domain: str) -> str:
    """返回站点域名的可读中文或英文名称。"""
    return _SITE_DISPLAY_NAME.get(domain, domain.split(".")[0].capitalize())


def _extract_username(domain: str, others: typing.Any) -> str | None:
    """从 holehe 返回的 'others' 字典中提取用户名/账号。"""
    # 如果 others 为空或不是字典类型，无法提取用户信息
    if not others or not isinstance(others, dict):
        return None
    for key in ("username", "user", "login", "handle", "name", "profile"):
        # 找到匹配的键且值不为空
        if key in others and others[key]:
            val = str(others[key]).strip()
            # 排除字符串 "none" 或 "null" 等无效值
            if val and val.lower() not in ("none", "null", ""):
                return val
    # 所有键都未匹配到有效用户名
    return None


# ── 结果格式化 ──────────────────────────────────────────────────────────────────

def _format_result(raw: dict) -> dict:
    """将 holehe 原生 dict 转换为我们统一的标准格式。"""
    name = raw.get("name", "")
    domain = raw.get("domain", name)
    exists = bool(raw.get("exists"))
    rate_limited = bool(raw.get("rateLimit"))
    email_recovery = raw.get("emailrecovery")
    phone_number = raw.get("phoneNumber")
    others = raw.get("others")

    username = _extract_username(domain, others)
    profile_url = None
    # 如果提取到用户名且该域名有 URL 模板，则生成完整个人资料链接
    if username and domain in _PROFILE_URL_TEMPLATE:
        template = _PROFILE_URL_TEMPLATE[domain]
        profile_url = template.replace("{username}", username)

    created_date = None
    # 从 others 中查找账户创建/注册日期
    if isinstance(others, dict):
        for k in ("date", "created", "creation_date", "registered", "date_joined"):
            if others.get(k):
                created_date = str(others[k])
                break

    return {
        "site": domain,
        "site_display": _display_name(domain),
        "exists": exists,
        "rate_limited": rate_limited,
        "email_recovery": email_recovery,
        "phone_number": phone_number,
        "profile_url": profile_url,
        "created_date": created_date,
        "others": others if isinstance(others, dict) else {},
    }


# ── 底层 holehe 调用器（异步核心）───────────────────────────────────────────────

async def _run_holehe_async(email: str) -> list[dict]:
    """运行 holehe 模块管道并返回原始结果字典列表。

    holehe 是原生异步的（trio + httpx）。我们直接调用其内部 maincore()，
    使用共享输出列表，避免 CLI argparse / print 的副作用。
    """
    import httpx
    from holehe.core import get_functions, import_submodules, launch_module
    from holehe.instruments import TrioProgress

    modules = import_submodules("holehe.modules")
    websites = get_functions(modules, args=None)

    out: list[dict] = []
    client = httpx.AsyncClient(timeout=10)

    async def _run() -> None:
        instrument = TrioProgress(len(websites))
        try:
            # 禁用 httpx 客户端超时，避免与 trio 调度冲突
            httpx._client._async.USE_CLIENT_TIMEOUT = False  # type: ignore[attr-defined]
        except Exception:
            # 如果禁用超时失败（如版本不兼容），静默忽略以保持向后兼容
            pass
        import trio
        trio.lowlevel.add_instrument(instrument)
        async with trio.open_nursery() as nursery:
            for website in websites:
                nursery.start_soon(launch_module, website, email, client, out)
        await client.aclose()
        out.sort(key=lambda i: i.get("name", ""))

    await _run()
    return out


# ── Worker 脚本：在子进程中运行 holehe ───────────────────────────────────────────
# 在子进程中运行 holehe，彻底隔离 trio/asyncio event loop

_HOLEHE_WORKER_SCRIPT = r"""
import json, sys
from holehe.core import get_functions, import_submodules, launch_module
import httpx, trio

email = sys.argv[1].strip()

modules = import_submodules("holehe.modules")
websites = get_functions(modules, args=None)

out = []
client = httpx.AsyncClient(timeout=10)

async def _run():
    try:
        httpx._client._async.USE_CLIENT_TIMEOUT = False
    except Exception:
        pass
    async with trio.open_nursery() as nursery:
        for website in websites:
            nursery.start_soon(launch_module, website, email, client, out)
    await client.aclose()
    out.sort(key=lambda i: i.get("name", ""))

trio.run(_run)
print(json.dumps(out, default=str))
"""


# ── 同步封装（在线程池中运行）─────────────────────────────────────────────────────

def email_background_check(email: str) -> dict:
    """对单个邮箱进行同步 OSINT 背景调查。

    如果 holehe 未安装则优雅降级。
    """
    # 邮箱为空或非字符串，直接返回无效邮箱错误
    if not email or not isinstance(email, str):
        return _error_result(str(email) if email else "", "Invalid email address")
    email = email.strip()
    # 邮箱格式校验不通过，返回格式错误
    if not _is_valid_email(email):
        return _error_result(email, "Invalid email format")

    # holehe 未安装，返回安装缺失错误
    if not _check_holehe():
        return _error_result(email, f"holehe not installed: {_holehe_import_error or 'unknown'}")

    try:
        import subprocess

        # 在子进程中运行 holehe，彻底隔离 trio/asyncio event loop
        # holehe 使用 trio，与 asyncio 的 event loop 不兼容
        try:
            result = subprocess.run(
                [sys.executable, "-c", _HOLEHE_WORKER_SCRIPT, email],
                capture_output=True, text=True, timeout=120,
            )
            # 子进程返回码非零，说明 holehe 执行出错
            if result.returncode != 0:
                return _error_result(email, f"holehe error: {result.stderr.strip() or 'unknown'}")
            raw_results = json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            # 子进程超时，120 秒未返回
            return _error_result(email, "holehe timeout after 120s")
        except json.JSONDecodeError as exc:
            # holehe 输出无法解析为 JSON
            return _error_result(email, f"holehe parse error: {exc}")
    except Exception as exc:
        # 其他未知异常（如子进程启动失败）
        return _error_result(email, f"holehe error: {exc}")

    results = [_format_result(r) for r in raw_results if isinstance(r, dict)]
    found = [r for r in results if r["exists"]]

    return {
        "email": email,
        "checked_count": len(results),
        "found_count": len(found),
        "found_sites_count": len(found),
        "rate_limited_count": sum(1 for r in results if r["rate_limited"]),
        "results": results,
        "social_profiles": _build_social_summary(found),
        "error": None,
    }


def _error_result(email: str, error: str) -> dict:
    """返回统一的错误结果格式。"""
    return {
        "email": email,
        "checked_count": 0,
        "found_count": 0,
        "found_sites_count": 0,
        "rate_limited_count": 0,
        "results": [],
        "social_profiles": {},
        "error": error,
    }


def _build_social_summary(found_results: list[dict]) -> dict:
    """将已发现的结果压缩为 {平台: URL} 格式的社交资料摘要。"""
    social: dict[str, str | None] = {}
    for r in found_results:
        domain = r["site"]
        # 只收录社交类平台（如 Twitter、LinkedIn 等）的发现结果
        if domain in _SITE_SOCIAL:
            key = _display_name(domain).lower().replace(" ", "_").replace("/", "_")
            # 避免同名平台重复覆盖（取第一个发现的 URL）
            if key not in social:
                social[key] = r.get("profile_url")
    return social


# ── 异步流式 API ────────────────────────────────────────────────────────────────

class EmailBackgroundChecker:
    """流式异步检查器 — 逐站结果到达时逐一 yield。

    用法::

        checker = EmailBackgroundChecker()
        async for ev in checker.check("user@example.com"):
            if ev["type"] == "site":
                print(f"  {ev['site_display']}: {'✓' if ev['exists'] else '✗'}")
            elif ev["type"] == "done":
                print(f"Found {ev['found_count']}/{ev['checked_count']}")
            elif ev["type"] == "error":
                print(f"Error: {ev['message']}")
    """

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    async def check(self, email: str) -> AsyncIterator[dict]:
        # 邮箱为空或非字符串，直接返回错误
        if not email or not isinstance(email, str):
            yield {"type": "error", "message": "Invalid email address"}
            return
        email = email.strip()
        # 邮箱格式校验不通过
        if not _is_valid_email(email):
            yield {"type": "error", "message": "Invalid email format"}
            return

        # holehe 未安装，无法执行检查
        if not _check_holehe():
            yield {"type": "error", "message": f"holehe not installed: {_holehe_import_error or 'unknown'}"}
            return

        # 在子进程中运行 holehe，彻底隔离 trio/asyncio event loop
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", _HOLEHE_WORKER_SCRIPT, email,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout,
                )
            except TimeoutError:
                # 子进程超时，杀掉进程后返回超时错误
                proc.kill()
                await proc.wait()
                yield {"type": "error", "message": f"Timeout after {self.timeout}s"}
                return
            # 子进程返回码非零，说明 holehe 执行失败
            if proc.returncode != 0:
                err_text = stderr.decode().strip() if stderr else "unknown"
                yield {"type": "error", "message": f"holehe error: {err_text}"}
                return
            raw_results = json.loads(stdout)
        except json.JSONDecodeError as exc:
            # holehe 输出 JSON 解析失败
            yield {"type": "error", "message": f"holehe parse error: {exc}"}
            return
        except Exception as exc:
            # 其他未知异常（子进程创建失败等）
            yield {"type": "error", "message": f"holehe error: {exc}"}
            return

        results = [_format_result(r) for r in raw_results if isinstance(r, dict)]
        found = [r for r in results if r["exists"]]

        for r in results:
            yield {"type": "site", **r}

        yield {
            "type": "done",
            "email": email,
            "checked_count": len(results),
            "found_count": len(found),
            "found_sites_count": len(found),
            "rate_limited_count": sum(1 for r in results if r["rate_limited"]),
            "social_profiles": _build_social_summary(found),
            "results": results,
        }
