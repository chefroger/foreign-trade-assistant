"""
Trade AI Assistant — Prompt File Loader.

Unified loader for all user-editable prompt files:
  - ~/.trade/prompts/system.md          (全局自定义 system prompt)
  - ~/.trade/companies/{slug}/agent_identity.md  (公司级 identity)

读取优先级（纵向覆盖）：
  1. ~/.trade/companies/{slug}/agent_identity.md   ← 公司级（最高）
  2. ~/.trade/prompts/system.md                   ← 全局用户自定义
  3. 代码 fallback (trade/prompt.py)              ← 最低

mtime 缓存：文件未变更时不重复读磁盘。

用户可通过 Web UI 或直接 vim 编辑这些文件，
下次请求自动生效（无需重启服务）。
"""

from __future__ import annotations

import os
from pathlib import Path

from trade.prompt import TRADE_SYSTEM_PROMPT as _CODE_FALLBACK

# ─────────────────────────────────────────────────────────────────────────────
# mtime 缓存：{绝对路径: (mtime, 内容)}
# ─────────────────────────────────────────────────────────────────────────────

_FILE_CACHE: dict[str, tuple[float, str]] = {}

# ─────────────────────────────────────────────────────────────────────────────
# 内部 helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_trade_home() -> Path:
    """返回用户 Trade 数据目录。

    Priority: TRADE_HOME env var → platform default.
    macOS/Linux: ~/.trade/, Windows: %LOCALAPPDATA%\trade\
    """
    val = os.environ.get("TRADE_HOME", "").strip()
    if val:
        return Path(val)
    # Windows: %LOCALAPPDATA%\trade\
    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(local_appdata) / "trade"
    # macOS / Linux: ~/.trade/
    return Path.home() / ".trade"


def _load_file(path: Path, fallback: str = "") -> str:
    """加载文件，启用 mtime 缓存。

    - 文件不存在 → 返回 fallback
    - mtime 未变   → 返回缓存内容
    - mtime 已变   → 重新读磁盘，更新缓存
    """
    if not path.is_file():
        return fallback

    try:
        mtime = path.stat().st_mtime
    except OSError:
        return fallback

    cache_key = str(path.resolve())
    cached = _FILE_CACHE.get(cache_key)

    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError:
        return fallback

    _FILE_CACHE[cache_key] = (mtime, content)
    return content


def _company_identity_path(slug: str) -> Path:
    """公司级 identity 文件路径。"""
    return _get_trade_home() / "companies" / slug / "agent_identity.md"


def _system_prompt_path() -> Path:
    """全局 system prompt 文件路径。"""
    return _get_trade_home() / "prompts" / "system.md"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_system_prompt(company_slug: str | None = None) -> str:
    """返回 system prompt（纵向覆盖，取最高优先级）。

    优先级：
      1. ~/.trade/companies/{slug}/agent_identity.md   ← 公司级
      2. ~/.trade/prompts/system.md                    ← 全局
      3. 代码 fallback (TRADE_SYSTEM_PROMPT)           ← 默认

    用户 vim 直接改文件 → mtime 变化 → 下次请求自动读到新内容。
    """
    # 最高优先：公司级 identity
    if company_slug:
        company_path = _company_identity_path(company_slug)
        content = _load_file(company_path)
        if content:
            return content

    # 全局自定义
    global_path = _system_prompt_path()
    content = _load_file(global_path)
    if content:
        return content

    # 最终 fallback：代码里的默认值
    return _CODE_FALLBACK


def get_agent_identity(company_id: int) -> str:
    """根据 company_id 获取 identity 文本（用于 helpers.build_query）。

    兼容模式：
    - 文件存在 → 读文件
    - 文件不存在、DB 有值 → 由调用方通过 DB 处理
    - 都没有 → 空字符串

    注意：此函数专注于从文件加载，不处理 DB。
          DB 缓存逻辑由调用方（helpers.py 或 company.py）处理。
    """
    # company_id → slug 的转换需要查 DB，这里仅处理文件路径逻辑
    # 实际 company_slug 由调用方传入
    return ""


def get_agent_identity_by_slug(company_slug: str) -> str:
    """根据 company_slug 获取 identity 文件内容。

    如果文件不存在，返回空字符串（由调用方决定是否 fallback）。
    """
    path = _company_identity_path(company_slug)
    return _load_file(path)


def write_agent_identity(company_slug: str, content: str) -> None:
    """写入公司 identity 文件（供 onboarding 或手动编辑调用）。

    文件路径：~/.trade/companies/{slug}/agent_identity.md
    写入后自动失效 mtime 缓存。

    注意：此函数只写文件，不写 DB。
          DB 缓存逻辑由调用方负责。
    """
    path = _company_identity_path(company_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    # 失效缓存
    cache_key = str(path.resolve())
    _FILE_CACHE.pop(cache_key, None)


def write_system_prompt(content: str) -> None:
    """写入全局 system prompt 文件。

    文件路径：~/.trade/prompts/system.md
    """
    path = _system_prompt_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    cache_key = str(path.resolve())
    _FILE_CACHE.pop(cache_key, None)


def resolve_system_prompt(
    company_slug: str | None = None,
    db_identity: str | None = None,
    *,
    code_fallback: str | None = None,
) -> str:
    """完整的 system prompt 解析（文件优先，DB 兜底，代码托底）。

    优先级链：
      1. 公司 identity 文件（~/.trade/companies/{slug}/agent_identity.md）
      2. DB agent_identity_md 字段（运行时缓存）
      3. 全局 system.md（~/.trade/prompts/system.md）
      4. code_fallback 参数（指定则优先，否则用默认 TRADE_SYSTEM_PROMPT）

    Args:
        company_slug: 公司 slug（用于定位 identity 文件）
        db_identity:  DB 中 agent_identity_md 字段值（缓存）
        code_fallback: 代码层兜底 prompt（None 时用默认 TRADE_SYSTEM_PROMPT）。
                       OSINT 类 skill 可传入 TRADE_SYSTEM_PROMPT_OSINT。
    """
    # 1. 公司 identity 文件
    if company_slug:
        file_content = get_agent_identity_by_slug(company_slug)
        if file_content:
            return file_content

    # 2. DB 缓存（过渡期保留）
    if db_identity:
        return db_identity

    # 3. 全局 system.md
    global_path = _system_prompt_path()
    global_content = _load_file(global_path)
    if global_content:
        return global_content

    # 4. 代码 fallback
    return code_fallback or _CODE_FALLBACK


def invalidate_cache(path: Path | str | None = None) -> None:
    """手动失效 mtime 缓存。

    Args:
        path: 失效特定文件，或 None（全部失效）
    """
    if path is None:
        _FILE_CACHE.clear()
        return
    key = str(Path(path).resolve())
    _FILE_CACHE.pop(key, None)
