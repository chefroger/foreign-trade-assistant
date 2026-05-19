"""
Trade AI Assistant — Skill Router（匹配引擎 + 注入逻辑）。

从 skill_registry 读取 skill 注册表数据，提供：
  - match_skill(query)  — 关键词匹配，返回匹配的 skill dict 或 None
  - augment_query(query) — 将 skill injection prompt 注入用户 query

架构：
  skill_registry.py (L4 数据层) → skill_router.py (L2 逻辑层) → helpers.py (L2 调用方)
"""

from __future__ import annotations

import os
import re

# ─────────────────────────────────────────────────────────────────────────────
# mtime 缓存：OrderedDict LRU（上限 128，远大于 14 个 skill）
# ─────────────────────────────────────────────────────────────────────────────
from collections import OrderedDict
from pathlib import Path

from trade.skill_registry import (
    _COMPILED,
    _EXPLICIT_RE,
    get_skill_by_name,
    skill_names,
)

_INJECTION_CACHE_MAX = int(os.environ.get("TRADE_SKILL_CACHE_MAX", "128"))
_INJECTION_CACHE: OrderedDict[str, tuple[float, str]] = OrderedDict()

# ─────────────────────────────────────────────────────────────────────────────
# SKILL.md → injection_prompt 加载器
# ─────────────────────────────────────────────────────────────────────────────

def _get_hermes_skills_dir() -> Path:
    """解析 Hermes skills 目录路径（优先 HERMES_HOME 环境变量）。"""
    val = os.environ.get("HERMES_HOME", "").strip()
    # 环境变量不为空时使用自定义路径，否则使用默认 ~/.hermes 路径
    if val:
        return Path(val) / "skills"
    return Path.home() / ".hermes" / "skills"


def _get_skill_dir(skill_name: str) -> Path | None:
    """返回已安装 skill 的目录路径，或 None。

    查找顺序：~/.hermes/skills/ → package skills/
    """
    # 优先查找已安装的 skill
    skill_path = _get_hermes_skills_dir() / skill_name
    if (skill_path / "SKILL.md").is_file():
        return skill_path

    # Fallback：查找 package 内置的 skill
    try:
        import trade
        pkg_root = Path(trade.__file__).parent.parent
        pkg_skill = pkg_root / "skills" / skill_name
        if (pkg_skill / "SKILL.md").is_file():
            return pkg_skill
    except Exception:
        # 导入或路径解析异常时静默降级，不影响主流程
        pass
    return None


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 markdown YAML frontmatter。

    使用 PyYAML safe_load 解析，正确处理 | block scalar 格式。

    返回结果：
        (frontmatter_dict, body_content)。无有效 frontmatter 时返回 ({}, content)。
    """
    # 没有 YAML frontmatter 标记，返回原始内容
    if not content.startswith("---\n"):
        return {}, content

    import yaml

    try:
        # 定位第二个 --- 作为 frontmatter 结束标记
        second_dash = content.find("\n---\n", 4)
        # 没有找到结束标记，说明 frontmatter 不完整，返回原始内容
        if second_dash == -1:
            return {}, content

        fm_text = content[4:second_dash]
        body = content[second_dash + 5:]

        parsed = yaml.safe_load(fm_text)
        # safe_load 返回 None 或非字典时视为无效 frontmatter
        if parsed is None or not isinstance(parsed, dict):
            return {}, body

        return parsed, body
    except yaml.YAMLError:
        # YAML 解析异常时返回原始内容，避免因 frontmatter 格式问题阻塞整体流程
        return {}, content


def _load_injection_prompt(skill_name: str) -> str | None:
    """从 SKILL.md frontmatter 加载 injection_prompt（mtime 缓存）。

    优先级：
      1. ~/.hermes/skills/{skill}/SKILL.md（用户安装版）
      2. {package}/skills/{skill}/SKILL.md（包内置版）
      3. None → 降级到 skill_registry 中的 augment_prompt 字段

    mtime 缓存：文件未变更时直接返回缓存内容，避免重复磁盘 IO。
    """
    # 如果未找到 skill 目录，则无法加载 injection_prompt
    skill_dir = _get_skill_dir(skill_name)
    if skill_dir is None:
        return None

    # 目录下没有 SKILL.md 文件，无法提取 injection_prompt
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None

    try:
        mtime = skill_md.stat().st_mtime
    except OSError:
        # 文件状态获取失败时静默返回 None，不阻塞后续匹配流程
        return None

    # mtime 缓存命中
    cache_key = skill_name
    cached = _INJECTION_CACHE.get(cache_key)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    # 读取文件并解析 frontmatter
    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError:
        # 文件读取失败时静默返回 None，不因单个 skill 读取异常影响整体
        return None

    fm, _ = _parse_frontmatter(content)
    injection = fm.get("injection_prompt", "")

    if injection:
        # LRU: 移动到末尾 + 超限时弹出最老项
        _INJECTION_CACHE.pop(cache_key, None)
        _INJECTION_CACHE[cache_key] = (mtime, injection)
        while len(_INJECTION_CACHE) > _INJECTION_CACHE_MAX:
            _INJECTION_CACHE.popitem(last=False)

    return injection or None


# ─────────────────────────────────────────────────────────────────────────────
# 文本标准化
# ─────────────────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    """去除首尾空白、小写化、压缩连续空白为单空格。"""
    return re.sub(r'\s+', ' ', text.strip().lower())


# ─────────────────────────────────────────────────────────────────────────────
# 核心匹配
# ─────────────────────────────────────────────────────────────────────────────

def match_skill(query: str) -> dict | None:
    """返回第一个匹配的 skill 注册表条目，或 None。

    匹配策略（按优先级）：
      1. 显式调用：检测用户显式提及的 skill 名（如 "用 b2b-email-intel"、"load skill b2b-document"）
      2. 关键词匹配：查询文本中的词/短词命中 skill 的 triggers 列表

    参数：
        query: 用户原始输入（自动标准化）

    返回：
        完整的 skill dict（含 name, triggers, augment_prompt 等），
        或 None 表示无匹配。
    """
    # 空查询直接返回 None，避免无效匹配
    if not query or not query.strip():
        return None

    # ── 策略 1：显式 skill 调用 ──
    # 检测显式 skill 调用模式（如 "用 b2b-email-intel"、"load skill b2b-document"）
    explicit_match = _EXPLICIT_RE.search(query)
    if explicit_match:
        matched_text = explicit_match.group(0)
        # 归一化：将空格和下划线转为连字符，以匹配 "用 b2b email intel" 这种写法
        normalized_match = matched_text.lower().replace(" ", "-").replace("_", "-")
        # 提取 normalized_match 中所有 "b2b-xxx" 形式的完整 token
        # 精确匹配，避免 "用 b2b" 截断后误匹配到不完整的 skill 名
        candidates = re.findall(r'b2b-[\w-]+', normalized_match)
        # 至少找到一个候选 skill 名，才继续精确匹配
        if candidates:
            skill_name_candidate = next(
                (name for c in candidates
                 for name in skill_names()
                 if name == c),  # 精确匹配，而非子串
                None,
            )
            # 精确匹配到注册表中的 skill 名时，直接返回该 skill 配置
            if skill_name_candidate:
                return get_skill_by_name(skill_name_candidate)

    # ── 策略 2：关键词/正则匹配 ──
    normed = _norm(query)
    for pattern, skill in _COMPILED:
        # 只要有一条已编译关键词正则命中标准化后的查询文本，即返回该 skill
        if pattern.search(normed):
            return skill

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Query 增强（注入 skill prompt）
# ─────────────────────────────────────────────────────────────────────────────

# 注入标记（用于 LLM 识别这是系统注入的 skill 指令）
SKILL_INJECTION_MARKER = "[SKILL AUGMENTATION]"
SKILL_EXPLICIT_MARKER = "[SKILL EXPLICIT]"


def augment_query(
    query: str,
    *,
    skill_name: str | None = None,
    company_id: int | None = None,
) -> str:
    """将 skill injection prompt 注入用户 query。

    两种调用约定：
    1. 隐式匹配 — match_skill(query) 自动检测到 skill 后触发注入
    2. 显式指定 — LLM/frontend 已知要使用哪个 skill，直接通过参数传入 skill_name

    参数：
        query:      用户原始输入
        skill_name: 可选的显式 skill 名称（传入时覆盖自动匹配）
        company_id: 可选的公司 ID（用于 b2b-data-directory 等需要注入路径的 skill）

    返回：
        注入后的完整 query（含 [SKILL AUGMENTATION] 标记块）。
        无匹配且无显式 skill_name 时，原样返回 query，不做任何修改。
    """
    # 确定要注入的 skill
    # 优先使用显式传入的 skill_name，否则通过自动匹配检测
    if skill_name:
        skill = get_skill_by_name(skill_name)
    else:
        skill = match_skill(query)

    # 如果两个路径都未匹配到 skill，原样返回用户 query，不做任何修改
    if skill is None:
        return query  # 无匹配 → 原样透传

    name = skill["name"]

    # 优先从 SKILL.md frontmatter 加载 injection_prompt，失败时降级到硬编码 augment_prompt
    augment = _load_injection_prompt(name)
    # SKILL.md 中没有 injection_prompt 字段时，使用 skill_registry 中预定义的默认 prompt
    if augment is None:
        augment = skill.get("augment_prompt", "")

    # 路径相关 skill：注入公司数据目录路径
    data_dir_hint = ""
    if name == "b2b-data-directory" and company_id:
        from trade import company as _co
        tc = _co.get_trade_company(company_id)
        # 公司数据目录存在时，提供具体路径让 AI 知道从哪里读取文件
        if tc and tc.get("data_dir"):
            slug = tc.get("slug", "unknown")
            data_dir_hint = (
                f"\n公司数据目录路径：{tc['data_dir']}\n"
                f"完整路径示例：~/.trade/companies/{slug}/"
            )

    # 组装注入块
    injection = (
        f"\n"
        f"{SKILL_INJECTION_MARKER}\n"
        f"## 技能触发：{name}\n"
        f"{SKILL_EXPLICIT_MARKER if skill_name else ''}\n"
        f"{augment}"
        f"{data_dir_hint}\n"
        f"## 用户原始问题\n{query}\n"
        f"{SKILL_INJECTION_MARKER}\n"
    )

    return injection
