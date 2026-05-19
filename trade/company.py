"""
Trade AI Assistant — 公司数据层。

CRUD 操作：
  - companies         （公司名称、slug、联系方式、激活状态）
  - trade_companies  （数据目录、agent 身份标识、Trade 会话激活状态）
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from trade import library as _library_module
from trade.database import get_connection

# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

# Trade 用户数据目录 — 优先使用 TRADE_HOME 环境变量，否则使用平台默认路径
_TRADE_HOME_RAW = os.environ.get("TRADE_HOME", "").strip()
if _TRADE_HOME_RAW:
    # 环境变量已设置，直接使用
    TRADE_HOME = Path(_TRADE_HOME_RAW)
elif os.name == "nt":
    # Windows 平台：%LOCALAPPDATA%\trade\
    _local_appdata = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    TRADE_HOME = Path(_local_appdata) / "trade"
else:
    # macOS / Linux 平台：~/.trade/
    TRADE_HOME = Path.home() / ".trade"


def _db_get_one(sql: str, args: tuple = ()) -> tuple | None:
    """执行单行查询并返回结果行，未找到时返回 None。"""
    conn = get_connection()
    try:
        row = conn.execute(sql, args).fetchone()
        return row
    finally:
        conn.close()


def _slugify(name: str) -> str:
    """将公司名称转换为 URL 安全的 slug 标识。"""
    slug = name.lower().strip()
    if not slug:  # 空输入 → 返回固定后备值
        return "company"
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[_\s]+", "-", slug)
    slug = re.sub(r"--+", "-", slug)
    return slug.strip("-") or "company"


def _ensure_data_dir(slug: str) -> Path:
    """创建并返回公司 slug 对应的数据目录路径。

    复制 .trade-template 模板骨架，将内部的 'company-slug'
    占位目录重命名为真实的 slug，确保目录结构正确：
      ~/.trade/{slug}/
        companies/{slug}/   ← 从 'company-slug' 重命名而来
        libraries/{slug}/
        clients/{slug}/
        ...
    """
    target = TRADE_HOME / slug
    template_src = Path(__file__).resolve().parent.parent / ".trade-template"

    if target.exists():
        # 目标目录已存在，无需重复创建
        return target

    if template_src.exists():
        # 直接复制模板到目标目录；因为上面已验证目标不存在，dirs_exist_ok=False 安全
        shutil.copytree(template_src, target, dirs_exist_ok=False)
        # 将 companies/ 内部的占位目录 'company-slug' 重命名为真实 slug
        # 同时重命名嵌套的 'library-slug' / 'client-slug' 目录
        _rename_company_placeholder(target / "companies", slug)
        _rename_template_placeholders(target / "companies" / slug, slug)
    else:
        # 无模板可用时，直接创建空目录
        target.mkdir(parents=True, exist_ok=True)

    return target


def _rename_company_placeholder(companies_dir: Path, slug: str) -> None:
    """将 companies/ 内部的 'company-slug' 目录重命名为真实 slug。"""
    src = companies_dir / "company-slug"
    dst = companies_dir / slug
    if src.exists() and not dst.exists():
        # 仅当源目录存在且目标目录不存在时才执行重命名
        src.rename(dst)


def _rename_template_placeholders(base: Path, slug: str) -> None:
    """递归将 'library-slug' 和 'client-slug' 目录重命名为真实 slug。"""
    if not base.is_dir():
        # 基础目录不存在，无需处理
        return
    for p in sorted(base.rglob("*")):
        if p.is_dir():
            if p.name == "library-slug":
                # 将 library 占位目录重命名为当前公司 slug
                p.rename(p.parent / slug)
            elif p.name == "client-slug":
                # 将 client 占位目录重命名为当前公司 slug
                p.rename(p.parent / slug)


# ─────────────────────────────────────────────────────────────────────────────
# companies 表操作
# ─────────────────────────────────────────────────────────────────────────────

def list_all() -> list[dict]:
    """返回所有公司列表，按名称排序。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, slug, logo_url, website, contact_name, "
            "contact_email, address, is_active, created_at, updated_at "
            "FROM companies ORDER BY name"
        ).fetchall()
        return [_row_to_company(r) for r in rows]
    finally:
        conn.close()


def get(company_id: int) -> dict | None:
    """返回公司字典，未找到时返回 None。"""
    row = _db_get_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    return _row_to_company(row) if row else None


def slug_from_id(company_id: int) -> str | None:
    """根据公司 ID 返回 slug（用于 prompt 文件路径解析）。"""
    row = _db_get_one("SELECT slug FROM companies WHERE id = ?", (company_id,))
    return row[0] if row else None


def get_by_slug(slug: str) -> dict | None:
    """根据 slug 返回一个公司，未找到时返回 None。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, slug, logo_url, website, contact_name, "
            "contact_email, address, is_active, created_at, updated_at "
            "FROM companies WHERE slug = ?", (slug,)
        ).fetchone()
        return _row_to_company(row) if row else None
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 桌面工作目录（按外贸业务流程分类）
# ─────────────────────────────────────────────────────────────────────────────

# 每个公司自动在桌面创建的工作目录结构，每个子目录对应一条 library 记录
_WORK_DIR_CATEGORIES: list[tuple[str, str]] = [
    ("报价单", "客户报价、价格谈判记录"),
    ("合同", "销售合同、采购合同、协议"),
    ("客户资料", "客户公司信息、联系人、需求"),
    ("产品规格", "产品参数表、规格书、技术文档"),
    ("发票", "商业发票、形式发票"),
    ("物流单据", "装箱单、提单、报关单、货运记录"),
    ("认证资质", "ISO认证、CE证书、检测报告"),
    ("营销素材", "产品图片、视频、公司介绍PPT、社媒素材"),
    ("海关数据", "进出口海关数据 CSV/Excel，采购商分析、贸易模式"),
]


def _setup_work_directory(company_name: str, slug: str, suggested_name: str = "") -> tuple[Path, bool]:
    """在桌面创建公司工作目录，包含外贸业务流程分类子目录。

    如果目标目录已存在，尝试加数字后缀（如 "科辰电力-2"）。

    Args:
        company_name: 公司名称
        slug: 公司 slug
        suggested_name: 用户指定的替代目录名（重命名场景），为空则用公司名

    Returns:
        (work_dir_path, is_new) — 目录路径 + 是否为新创建（False = 目录已存在，用了后缀名）
    """
    # 测试环境：工作目录写到临时目录，不污染桌面
    trade_home = os.environ.get("TRADE_HOME", "")
    if trade_home:
        # 有 TRADE_HOME 环境变量，说明在测试环境中，使用临时路径
        base = Path(trade_home) / "work"
    else:
        # 生产环境：默认放在桌面
        base = Path.home() / "Desktop"
        # macOS 中文桌面路径
        if not base.is_dir():
            base = Path.home() / "桌面"
        if not base.is_dir():
            # 桌面目录都不存在时，回退到用户 home 目录
            base = Path.home()

    # 确定目录名
    dir_name = suggested_name.strip() if suggested_name.strip() else company_name.strip()
    # 清理文件名中的非法字符
    dir_name = re.sub(r'[<>:"/\\|?*]', '-', dir_name)
    dir_name = dir_name.strip()

    work_dir = base / dir_name
    is_new = True

    # 如果目录已存在，尝试加后缀
    if work_dir.exists():
        suffix = 2
        while True:
            alt_name = f"{dir_name}-{suffix}"
            alt_dir = base / alt_name
            if not alt_dir.exists():
                # 找到不存在的后缀名，使用此目录
                work_dir = alt_dir
                break
            suffix += 1
            if suffix > 99:
                # 极端情况：1-99 后缀全被占用，使用时间戳确保唯一
                import time
                ts = int(time.time())
                work_dir = base / f"{dir_name}-{ts}"
                # 防止同一秒内多次创建冲突
                while work_dir.exists():
                    ts += 1
                    work_dir = base / f"{dir_name}-{ts}"
                break
        is_new = False

    # 创建目录结构
    work_dir.mkdir(parents=True, exist_ok=False)
    for cat_name, _ in _WORK_DIR_CATEGORIES:
        (work_dir / cat_name).mkdir(parents=True, exist_ok=True)

    return work_dir, is_new


def _register_work_libraries(company_id: int, work_dir: Path) -> list[dict]:
    """将工作目录的每个子目录注册为 document library。

    Args:
        company_id: 公司 ID
        work_dir: 工作目录根路径

    Returns:
        创建的 library 记录列表
    """
    libraries = []
    for cat_name, cat_desc in _WORK_DIR_CATEGORIES:
        cat_path = work_dir / cat_name
        lib = _library_module.create(
            name=cat_name,
            root_path=str(cat_path),
            description=cat_desc,
            company_id=company_id,
        )
        libraries.append(lib)
    return libraries


def create(
    name: str,
    slug: str | None = None,
    logo_url: str = "",
    website: str = "",
    contact_name: str = "",
    contact_email: str = "",
    address: str = "",
    *,
    work_dir_name: str = "",
) -> dict:
    """创建新公司及其 trade_companies 记录 + 桌面工作目录 + 文档库。

    Args:
        name: 公司名称
        slug: URL 标识（省略时从 name 自动生成）
        work_dir_name: 桌面工作目录名称。目录已存在时自动加后缀。
                       为空则用公司名称。

    Returns:
        {
            "id": int, "name": str, "slug": str, ...,
            "work_dir": str,           # 桌面工作目录绝对路径
            "work_dir_is_new": bool,   # 是否为新创建（用于前端提示）
            "libraries": [dict, ...],  # 自动创建的文档库列表
        }
    """
    if not name or not name.strip():
        # 公司名称为空，抛出异常
        raise ValueError("Company name cannot be empty")
    if not slug:
        # 未提供 slug 时，从公司名自动生成
        slug = _slugify(name)
    # 确保 slug 唯一
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM companies WHERE slug = ?", (slug,)
        ).fetchone()
        if existing:
            # slug 已存在，不允许重复
            raise ValueError(f"Company with slug '{slug}' already exists")

        # 创建 ~/.trade/{slug}/ 数据目录
        data_dir = str(_ensure_data_dir(slug))

        # 创建桌面工作目录
        work_dir, is_new = _setup_work_directory(
            name, slug, suggested_name=work_dir_name
        )

        cursor = conn.execute(
            "INSERT INTO companies (name, slug, logo_url, website, contact_name, "
            "contact_email, address) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, slug, logo_url, website, contact_name, contact_email, address),
        )
        company_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO trade_companies (company_id, data_dir) VALUES (?, ?)",
            (company_id, data_dir),
        )
        conn.commit()

        # 注册桌面工作目录下的文档库
        libs = _register_work_libraries(company_id, work_dir)

        result = get(company_id)
        if result:
            # 将工作目录和库信息附加到返回结果中
            result["work_dir"] = str(work_dir)
            result["work_dir_is_new"] = is_new
            result["libraries"] = libs
        return result
    finally:
        conn.close()


def update(
    company_id: int,
    name: str | None = None,
    logo_url: str | None = None,
    website: str | None = None,
    contact_name: str | None = None,
    contact_email: str | None = None,
    address: str | None = None,
    is_active: bool | None = None,
) -> dict | None:
    """更新公司字段。仅更新提供的（非 None）字段。"""
    conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM companies WHERE id = ?", (company_id,)).fetchone():
            # 公司不存在，返回 None
            return None
        fields, vals = [], []
        for fname, fval in [
            ("name", name), ("logo_url", logo_url), ("website", website),
            ("contact_name", contact_name), ("contact_email", contact_email),
            ("address", address),
        ]:
            if fval is not None:
                # 仅当传入值不为 None 时才加入更新
                fields.append(f"{fname} = ?")
                vals.append(fval)
        if is_active is not None:
            # 显式提供了激活状态，加入更新字段
            fields.append("is_active = ?")
            vals.append(1 if is_active else 0)
        if fields:
            # 有字段需要更新时才执行 SQL
            fields.append("updated_at = datetime('now', 'localtime')")
            vals.append(company_id)
            conn.execute(
                f"UPDATE companies SET {', '.join(fields)} WHERE id = ?", vals
            )
            conn.commit()
        return get(company_id)
    finally:
        conn.close()


def delete(company_id: int) -> bool:
    """删除公司及其级联关联的所有文档库、客户、对话记录。"""
    conn = get_connection()
    try:
        # trade_companies 通过外键自动级联删除
        n = conn.execute(
            "DELETE FROM companies WHERE id = ?", (company_id,)
        ).rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()


def _row_to_company(row) -> dict:
    """将数据库行转换为公司字典。"""
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "logo_url": row["logo_url"],
        "website": row["website"],
        "contact_name": row["contact_name"],
        "contact_email": row["contact_email"],
        "address": row["address"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# trade_companies 表操作
# ─────────────────────────────────────────────────────────────────────────────

def get_trade_company(company_id: int) -> dict | None:
    """返回公司的 trade_companies 记录，未找到时返回 None。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT company_id, data_dir, agent_identity_md, is_active, created_at "
            "FROM trade_companies WHERE company_id = ?", (company_id,)
        ).fetchone()
        return _row_to_tc(row) if row else None
    finally:
        conn.close()


def update_trade_company(
    company_id: int,
    data_dir: str | None = None,
    agent_identity_md: str | None = None,
    is_active: bool | None = None,
) -> dict | None:
    """更新 trade_companies 字段。"""
    conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM trade_companies WHERE company_id = ?", (company_id,)).fetchone():
            # trade_companies 记录不存在，返回 None
            return None
        fields, vals = [], []
        if data_dir is not None:
            # 更新数据目录路径
            fields.append("data_dir = ?")
            vals.append(data_dir)
        if agent_identity_md is not None:
            # 更新 agent 身份标识文本
            fields.append("agent_identity_md = ?")
            vals.append(agent_identity_md)
        if is_active is not None:
            # 更新 Trade 会话激活状态
            fields.append("is_active = ?")
            vals.append(1 if is_active else 0)
        if fields:
            # 有字段需要更新时才执行 SQL
            vals.append(company_id)
            conn.execute(
                f"UPDATE trade_companies SET {', '.join(fields)} WHERE company_id = ?", vals
            )
            conn.commit()
        return get_trade_company(company_id)
    finally:
        conn.close()


def get_agent_identity(company_id: int) -> str:
    """返回公司的 agent 身份标识文本。

    优先级：
      1. trade_companies.agent_identity_md（数据库内联覆盖）
      2. {data_dir}/agent-identity.md 磁盘文件
      3. ''（空字符串 — 回退到通用 TRADE_SYSTEM_PROMPT）
    """
    tc = get_trade_company(company_id)
    if not tc:
        # 公司无 trade_companies 记录，返回空
        return ""
    if tc.get("agent_identity_md"):
        # 数据库中已有 agent_identity_md，优先使用（在线覆盖）
        return tc["agent_identity_md"]
    data_dir = Path(tc["data_dir"]) if tc.get("data_dir") else None
    if data_dir and data_dir.exists():
        # 数据目录存在时，尝试读取磁盘上的 agent-identity.md 文件
        identity_file = data_dir / "agent-identity.md"
        if identity_file.exists():
            return identity_file.read_text(encoding="utf-8")
    return ""


def _row_to_tc(row) -> dict:
    """将数据库行转换为 trade_companies 字典。"""
    return {
        "company_id": row["company_id"],
        "data_dir": row["data_dir"],
        "agent_identity_md": row["agent_identity_md"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }
