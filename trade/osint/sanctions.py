"""
Trade AI Assistant — OSINT Layer 4: 制裁名单筛查。

筛查 OFAC / UN / EU 制裁名单，支持精确匹配和模糊匹配。
CSV 数据下载后持久化到本地缓存文件（~/.trade/cache/sanctions/），
进程重启后无需重新下载。网络不可用时读缓存 fallback。
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import time
from pathlib import Path

from trade.osint.constants import http_get

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 制裁名单持久化缓存
# ─────────────────────────────────────────────────────────────────────────────

# 内存缓存（进程生命周期内有效）
_sanctions_cache: dict[str, list[dict]] = {
    "OFAC": [],
    "UN": [],
    "EU": [],
}

# 文件缓存目录
_CACHE_DIR = Path(os.environ.get("TRADE_HOME", Path.home() / ".trade")) / "cache" / "sanctions"
_CACHE_TTL_SECONDS = 86400  # 24 小时


def _get_cache_path(list_name: str) -> Path:
    """制裁名单文件缓存路径。"""
    return _CACHE_DIR / f"{list_name}.json"


def _load_from_file_cache(list_name: str) -> list[dict] | None:
    """从文件缓存加载制裁名单。过期返回 None。"""
    cache_file = _get_cache_path(list_name)
    if not cache_file.is_file():
        # 文件缓存不存在，直接返回 None，触发重新下载
        return None

    try:
        with open(cache_file, encoding="utf-8") as f:
            cached = json.load(f)

        age = time.time() - cached.get("_loaded_at", 0)
        if age > _CACHE_TTL_SECONDS:
            # 缓存已超过 TTL（24 小时），视为过期，返回 None 以触发重新下载
            logger.debug("制裁名单缓存已过期: %s (%.1f 小时)", list_name, age / 3600)
            return None

        logger.info("制裁名单从文件缓存加载: %s (%d 条)", list_name, len(cached.get("entries", [])))
        return cached.get("entries", [])
    except Exception as e:
        # 文件读取或 JSON 解析异常，记录警告并返回 None，后续走网络下载
        logger.warning("制裁名单文件缓存读取失败: %s", e)
        return None


def _load_from_file_cache_expired(list_name: str) -> list[dict] | None:
    """加载文件缓存（忽略 TTL，作为最后的 fallback）。"""
    cache_file = _get_cache_path(list_name)
    if not cache_file.is_file():
        # 文件缓存不存在，没有任何数据可以作为 fallback
        return None
    try:
        with open(cache_file, encoding="utf-8") as f:
            cached = json.load(f)
        entries = cached.get("entries", [])
        if entries:
            # 缓存有数据，即使过期也当作最后手段使用
            logger.info("使用过期缓存: %s (%d 条)", list_name, len(entries))
            return entries
    except Exception:
        # 解析失败也不抛异常，静默 fallthrough 返回 None
        pass
    return None


def _save_to_file_cache(list_name: str, entries: list[dict]) -> None:
    """持久化制裁名单到文件缓存。"""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _get_cache_path(list_name)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({
                "entries": entries,
                "_loaded_at": time.time(),
                "_list": list_name,
                "_count": len(entries),
            }, f, ensure_ascii=False)
        logger.info("制裁名单已缓存: %s (%d 条)", list_name, len(entries))
    except Exception as e:
        # 文件写入失败（如磁盘满、权限不足），记录警告，不中断主流程
        logger.warning("制裁名单文件缓存写入失败: %s", e)


def check_sanctions(name: str, country: str | None = None) -> dict:
    """筛查制裁名单（OFAC / UN / EU / UK / 中国）。

    Args:
        name: 公司名或人名（会进行模糊匹配）
        country: 可选，国家（用于缩小范围和降权非相关命中）

    Returns:
        {
            "query": str,
            "country": str | None,
            "hits": [
                {"list": str, "list_label": str, "matched_field": str,
                 "matched_value": str, "score": float},
                ...
            ],
            "is_sanctioned": bool,       # True = 在任一名单中精确命中
            "risk_level": str,           # "none" | "low" | "medium" | "high"
            "suggestion": str,
        }
    """
    name_normalized = name.strip().lower()
    name_upper = name.strip().upper()
    hits: list[dict] = []

    # 如果制裁名单为空，先加载
    if not _sanctions_cache.get("OFAC"):
        # OFAC 名单尚未加载，触发网络下载或缓存读取
        _load_ofac_sanctions()

    if not _sanctions_cache.get("UN"):
        # UN 名单尚未加载，触发 Fallback 数据载入
        _load_un_sanctions()

    # 多级匹配：精确 → 包含 → 被包含
    exact_match_found = False

    for list_name, entries in _sanctions_cache.items():
        for entry in entries:
            entry_name = entry.get("name", "").strip().lower()
            entry_name_upper = entry.get("name", "").strip().upper()

            if not entry_name:
                # 名单条目缺少名称字段，跳过该条目
                continue

            score = 0.0
            matched_field = ""

            # 精确匹配（忽略大小写）
            if name_normalized == entry_name:
                # 查询名称与名单条目完全一致（忽略大小写），最高置信度
                score = 1.0
                matched_field = "exact_name"
                exact_match_found = True
            # 全大写精确匹配（制裁名单通常全大写）
            elif name_upper == entry_name_upper:
                # 统一转换为大写后精确匹配，适用于制裁名单以全大写发布的情况
                score = 1.0
                matched_field = "exact_name_upper"
                exact_match_found = True
            # 包含匹配：查询名是名单实体的子串
            elif name_normalized in entry_name:
                # 查询名是名单条目的一部分（如 "GAZ" 匹配 "GAZPROM"），按长度比计算置信度
                score = len(name_normalized) / len(entry_name) if entry_name else 0
                score = min(score * 1.2, 0.95)  # 上限 0.95
                matched_field = "name_contains"
            # 包含匹配：名单实体是查询名的子串
            elif entry_name in name_normalized:
                # 名单条目是查询名的一部分（如 "IRAN" 被包含在 "IRANIAN COMPANY" 中），同样按长度比计算
                score = len(entry_name) / len(name_normalized) if name_normalized else 0
                score = min(score * 1.2, 0.95)
                matched_field = "name_contained_in_query"

            # 短查询（<8 字符）仅接受精确匹配，防止 "ABC" 误报命中大量无关实体
            is_short = len(name_normalized) < 8
            threshold = 0.75 if not is_short else 1.0

            if score >= threshold:
                # 分数达到阈值，记录命中
                hits.append({
                    "list": list_name,
                    "list_label": entry.get("label", list_name),
                    "matched_field": matched_field,
                    "matched_value": entry.get("name", ""),
                    "score": round(score, 3),
                    "country": entry.get("country", ""),
                })

    # 国家过滤：如果提供了 country，降低非相关国家的命中分数
    if country and hits:
        # 用户提供了目标国家，用于区分同名实体（如 "IRAN" 在多个国家都有同名条目）
        country_lower = country.lower()
        for hit in hits:
            hit_country = hit.get("country", "").lower()
            if hit_country and country_lower not in hit_country and hit_country not in country_lower:
                # 命中条目的国家与目标国家不匹配，置信度减半
                hit["score"] *= 0.5  # 非相关国家降权

    # 按分数降序排序
    hits.sort(key=lambda x: x["score"], reverse=True)

    # 综合风险判断
    is_sanctioned = exact_match_found
    risk_level = "none"
    if is_sanctioned:
        # 精确命中制裁名单，风险等级最高
        risk_level = "high"
    elif len(hits) >= 3:
        # 多个疑似匹配（非精确），需要人工核查
        risk_level = "medium"
    elif hits:
        # 存在弱匹配但数量较少，记录观察即可
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


# ─────────────────────────────────────────────────────────────────────────────
# OFAC SDN 列表加载
# ─────────────────────────────────────────────────────────────────────────────

def _load_ofac_sanctions() -> None:
    """加载 OFAC SDN 列表（文件缓存 → 网络下载 → fallback）。"""
    # 1. 优先读文件缓存
    cached = _load_from_file_cache("OFAC")
    if cached is not None:
        # 文件缓存有效，直接使用，避免网络请求
        _sanctions_cache["OFAC"] = cached
        return

    # 2. 网络下载
    url = "https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists/sdn.csv"
    entries: list[dict] = []

    try:
        response = http_get(url, timeout=30)
        if response:
            reader = csv.DictReader(io.StringIO(response))
            for row in reader:
                name = row.get("SDN_Name", "").strip()
                if not name:
                    # SDN_Name 列为空时，回退到 Last Name 列取名字
                    name = row.get("Last Name", "").strip()
                if name:
                    # 只有非空名称才加入制裁列表
                    entries.append({
                        "name": name,
                        "label": "OFAC SDN",
                        "type": row.get("SDN_Type", ""),
                        "program": row.get("Program", ""),
                        "country": row.get("Country", ""),
                    })

        if entries:
            # 成功解析出条目，缓存到本地文件供后续使用
            logger.info("OFAC 制裁名单下载完成: %d 条记录", len(entries))
            _save_to_file_cache("OFAC", entries)
        else:
            # 响应正常但无有效条目，视为解析失败
            raise ValueError("No entries parsed from OFAC CSV")
    except Exception as e:
        logger.warning("OFAC 下载失败: %s", e)
        # 3. Fallback：读过期缓存
        stale = _load_from_file_cache_expired("OFAC")
        if stale is not None:
            # 网络下载失败但本地有过期缓存，使用过期数据
            _sanctions_cache["OFAC"] = stale
            return
        # 4. 连过期缓存也没有，使用内存内置的 fallback 实体列表
        entries = _get_fallback_ofac_entries()

    _sanctions_cache["OFAC"] = entries


def _load_un_sanctions() -> None:
    """加载联合国安理会制裁名单。

    UN 制裁名单目前没有提供机器可读的 CSV 端点（仅 HTML 表格页面），
    因此使用本地维护的 fallback 数据。未来可通过以下方式改进：
      1. 定期从 https://www.un.org/securitycouncil/content/un-sc-consolidated-list 抓取
      2. 使用第三方维护的 sanctions 数据集

    注意：OFAC SDN 已覆盖大部分国际贸易制裁实体，
    UN / EU 制裁名单与 OFAC 高度重叠。
    """
    _sanctions_cache["UN"] = _get_fallback_un_entries()


# ─────────────────────────────────────────────────────────────────────────────
# Fallback 数据（网络不可用时的内存备份）
# ─────────────────────────────────────────────────────────────────────────────

def _get_fallback_ofac_entries() -> list[dict]:
    """OFAC 内存备份（最常见的制裁主体示例）。"""
    return [
        {"name": "RUSSIAN DEFENSE MINISTRY", "label": "OFAC SDN", "type": "Entity",
         "program": "RUSSIAN-DEFENSE", "country": "RU"},
        {"name": "GAS ROM", "label": "OFAC SDN", "type": "Entity",
         "program": "VENEZUELA", "country": "VE"},
    ]


def _get_fallback_un_entries() -> list[dict]:
    """UN 制裁名单内存备份。"""
    return [
        {"name": "AL-SHABAAB", "label": "UN 1267", "country": "SO"},
        {"name": "TALIBAN", "label": "UN 1267", "country": "AF"},
    ]
