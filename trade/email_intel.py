"""
Trade AI Assistant — Email Intelligence (OSINT Background Check).

Uses holehe to check if an email is registered on 120+ websites and
retrieves publicly-available profile information from those accounts.

This module is self-contained: it imports holehe internally and degrades
gracefully if holehe is not installed (returns an error dict instead of raising).

Public API
──────────
email_background_check(email: str) -> dict
    Synchronous wrapper. Runs holehe in a thread pool, returns a structured report.

Async API (recommended for streaming endpoints)
──────────────────────────────────────────────
EmailBackgroundChecker.check(email: str) -> AsyncIterator[dict]
    Yields per-site results as they arrive (site → exists → details).
    Final yield is the summary dict.

Output format
─────────────
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
    "error": None   # None if OK, string if holehe not installed
}
"""

from __future__ import annotations

import asyncio
import re
import typing
from collections.abc import AsyncIterator

# ── holehe import (lazy, graceful degradation) ───────────────────────────────

_holehe_available: bool | None = None
_holehe_import_error: str | None = None


def _check_holehe() -> bool:
    global _holehe_available, _holehe_import_error
    if _holehe_available is not None:
        return _holehe_available
    try:
        import holehe.core
        import holehe.modules
        _holehe_available = True
    except ImportError as exc:
        _holehe_available = False
        _holehe_import_error = str(exc)
    return _holehe_available


# ── Validation ───────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


# ── Site metadata ────────────────────────────────────────────────────────────

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
    "mastodon.social": "Mastodon",
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

# Profile URL templates — username is extracted from holehe "others" field
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
    """Human-readable name for a site domain."""
    return _SITE_DISPLAY_NAME.get(domain, domain.split(".")[0].capitalize())


def _extract_username(domain: str, others: typing.Any) -> str | None:
    """Pull a username/handle out of holehe's 'others' dict."""
    if not others or not isinstance(others, dict):
        return None
    for key in ("username", "user", "login", "handle", "name", "profile"):
        if key in others and others[key]:
            val = str(others[key]).strip()
            if val and val.lower() not in ("none", "null", ""):
                return val
    return None


# ── Result formatter ─────────────────────────────────────────────────────────

def _format_result(raw: dict) -> dict:
    """Convert raw holehe dict → our standard format."""
    name = raw.get("name", "")
    domain = raw.get("domain", name)
    exists = bool(raw.get("exists"))
    rate_limited = bool(raw.get("rateLimit"))
    email_recovery = raw.get("emailrecovery")
    phone_number = raw.get("phoneNumber")
    others = raw.get("others")

    username = _extract_username(domain, others)
    profile_url = None
    if username and domain in _PROFILE_URL_TEMPLATE:
        template = _PROFILE_URL_TEMPLATE[domain]
        profile_url = template.replace("{username}", username)

    created_date = None
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


# ── Low-level holehe caller (async core) ─────────────────────────────────────

async def _run_holehe_async(email: str) -> list[dict]:
    """Run the holehe module pipeline and return raw result dicts.

    holehe is async-native (trio + httpx).  We call its internal
    maincore() directly with a shared output list, avoiding all the
    CLI argparse / print side-effects.
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
            httpx._client._async.USE_CLIENT_TIMEOUT = False  # type: ignore[attr-defined]
        except Exception:
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


# ── Sync wrapper (runs async in thread pool) ─────────────────────────────────

def email_background_check(email: str) -> dict:
    """Synchronous OSINT background check for a single email.

    Degrades gracefully if holehe is not installed.
    """
    if not email or not isinstance(email, str):
        return _error_result(str(email) if email else "", "Invalid email address")
    email = email.strip()
    if not _is_valid_email(email):
        return _error_result(email, "Invalid email format")

    if not _check_holehe():
        return _error_result(email, f"holehe not installed: {_holehe_import_error or 'unknown'}")

    try:
        import contextlib
        import io

        import trio
        # Suppress holehe's trio progress-bar prints (they go to stdout)
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            raw_results = trio.run(lambda: _run_holehe_async(email))
    except Exception as exc:
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
    """Collapse found results into a {platform: url} social profile map."""
    social: dict[str, str | None] = {}
    for r in found_results:
        domain = r["site"]
        if domain in _SITE_SOCIAL:
            key = _display_name(domain).lower().replace(" ", "_").replace("/", "_")
            if key not in social:
                social[key] = r.get("profile_url")
    return social


# ── Async streaming API ───────────────────────────────────────────────────────

class EmailBackgroundChecker:
    """Streaming async checker — yields per-site results as they complete.

    Usage::

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
        if not email or not isinstance(email, str):
            yield {"type": "error", "message": "Invalid email address"}
            return
        email = email.strip()
        if not _is_valid_email(email):
            yield {"type": "error", "message": "Invalid email format"}
            return

        if not _check_holehe():
            yield {"type": "error", "message": f"holehe not installed: {_holehe_import_error or 'unknown'}"}
            return

        try:
            raw_results = await asyncio.wait_for(
                _run_holehe_async(email),
                timeout=self.timeout,
            )
        except TimeoutError:
            yield {"type": "error", "message": f"Timeout after {self.timeout}s"}
            return
        except Exception as exc:
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
