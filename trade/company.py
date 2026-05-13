"""
Trade AI Assistant — Company data layer.

CRUD for:
  - companies         (name, slug, contact info, active flag)
  - trade_companies  (data_dir, agent_identity_md, is_active per Trade session)
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Optional

from trade.database import get_connection
from trade import library as _library_module

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

# Trade user data directory — respects TRADE_HOME env var, otherwise platform default
_TRADE_HOME_RAW = os.environ.get("TRADE_HOME", "").strip()
if _TRADE_HOME_RAW:
    TRADE_HOME = Path(_TRADE_HOME_RAW)
elif os.name == "nt":
    # Windows: %LOCALAPPDATA%\trade\
    _local_appdata = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    TRADE_HOME = Path(_local_appdata) / "trade"
else:
    # macOS / Linux: ~/.trade/
    TRADE_HOME = Path.home() / ".trade"


def _db_get_one(sql: str, args: tuple = ()) -> Optional[tuple]:
    """Execute a single-row query and return the row or None."""
    conn = get_connection()
    try:
        row = conn.execute(sql, args).fetchone()
        return row
    finally:
        conn.close()


def _slugify(name: str) -> str:
    """Convert a company name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[_\s]+", "-", slug)
    slug = re.sub(r"--+", "-", slug)
    return slug.strip("-")


def _ensure_data_dir(slug: str) -> Path:
    """Create and return the data directory path for a company slug.

    Copies the .trade-template skeleton, renaming the 'company-slug'
    placeholder directory to the real slug so the layout is correct:
      ~/.trade/{slug}/
        companies/{slug}/   ← renamed from 'company-slug'
        libraries/{slug}/
        clients/{slug}/
        ...
    """
    target = TRADE_HOME / slug
    template_src = Path(__file__).resolve().parent.parent / ".trade-template"

    if target.exists():
        return target

    if template_src.exists():
        # Copy template directly to target; dirs_exist_ok=False is fine
        # because target was verified non-existent above.
        shutil.copytree(template_src, target, dirs_exist_ok=False)
        # Rename the placeholder 'company-slug' dir inside companies/ to the real slug.
        # Rename nested 'library-slug' / 'client-slug' dirs too.
        _rename_company_placeholder(target / "companies", slug)
        _rename_template_placeholders(target / "companies" / slug, slug)
    else:
        target.mkdir(parents=True, exist_ok=True)

    return target


def _rename_company_placeholder(companies_dir: Path, slug: str) -> None:
    """Rename the 'company-slug' directory inside companies/ to the real slug."""
    src = companies_dir / "company-slug"
    dst = companies_dir / slug
    if src.exists() and not dst.exists():
        src.rename(dst)


def _rename_template_placeholders(base: Path, slug: str) -> None:
    """Recursively rename 'library-slug' and 'client-slug' dirs to the real slug."""
    if not base.is_dir():
        return
    for p in sorted(base.rglob("*")):
        if p.is_dir():
            if p.name == "library-slug":
                p.rename(p.parent / slug)
            elif p.name == "client-slug":
                p.rename(p.parent / slug)


# ─────────────────────────────────────────────────────────────────────────────
# companies table
# ─────────────────────────────────────────────────────────────────────────────

def list_all() -> list[dict]:
    """Return all companies, ordered by name."""
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


def get(company_id: int) -> Optional[dict]:
    """Return company row dict or None."""
    row = _db_get_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    return _row_to_company(row) if row else None


def slug_from_id(company_id: int) -> Optional[str]:
    """Return company slug by ID (for prompt file path resolution)."""
    row = _db_get_one("SELECT slug FROM companies WHERE id = ?", (company_id,))
    return row[0] if row else None


def get_by_slug(slug: str) -> Optional[dict]:
    """Return one company by slug, or None."""
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
    desktop = Path.home() / "Desktop"
    # macOS 中文桌面
    if not desktop.is_dir():
        desktop = Path.home() / "桌面"
    if not desktop.is_dir():
        desktop = Path.home()

    # 确定目录名
    dir_name = suggested_name.strip() if suggested_name.strip() else company_name.strip()
    # 清理文件名中的非法字符
    dir_name = re.sub(r'[<>:"/\\|?*]', '-', dir_name)
    dir_name = dir_name.strip()

    work_dir = desktop / dir_name
    is_new = True

    # 如果目录已存在，尝试加后缀
    if work_dir.exists():
        suffix = 2
        while True:
            alt_name = f"{dir_name}-{suffix}"
            alt_dir = desktop / alt_name
            if not alt_dir.exists():
                work_dir = alt_dir
                break
            suffix += 1
            if suffix > 99:
                # 极端情况：使用 slug 作为后备
                work_dir = desktop / slug
                break
        is_new = False

    # 创建目录结构
    work_dir.mkdir(parents=True, exist_ok=True)
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
    slug: Optional[str] = None,
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
    if not slug:
        slug = _slugify(name)
    # Ensure slug is unique
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM companies WHERE slug = ?", (slug,)
        ).fetchone()
        if existing:
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
            result["work_dir"] = str(work_dir)
            result["work_dir_is_new"] = is_new
            result["libraries"] = libs
        return result
    finally:
        conn.close()


def update(
    company_id: int,
    name: Optional[str] = None,
    logo_url: Optional[str] = None,
    website: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_email: Optional[str] = None,
    address: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[dict]:
    """Update company fields. Only provided (non-None) fields are changed."""
    conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM companies WHERE id = ?", (company_id,)).fetchone():
            return None
        fields, vals = [], []
        for fname, fval in [
            ("name", name), ("logo_url", logo_url), ("website", website),
            ("contact_name", contact_name), ("contact_email", contact_email),
            ("address", address),
        ]:
            if fval is not None:
                fields.append(f"{fname} = ?")
                vals.append(fval)
        if is_active is not None:
            fields.append("is_active = ?")
            vals.append(1 if is_active else 0)
        if fields:
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
    """Delete a company and cascade-delete all its libraries, customers, conversations."""
    conn = get_connection()
    try:
        # trade_companies cascades via FK
        n = conn.execute(
            "DELETE FROM companies WHERE id = ?", (company_id,)
        ).rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()


def _row_to_company(row) -> dict:
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
# trade_companies table
# ─────────────────────────────────────────────────────────────────────────────

def get_trade_company(company_id: int) -> Optional[dict]:
    """Return trade_companies entry for a company, or None."""
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
    data_dir: Optional[str] = None,
    agent_identity_md: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[dict]:
    """Update trade_companies fields."""
    conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM trade_companies WHERE company_id = ?", (company_id,)).fetchone():
            return None
        fields, vals = [], []
        if data_dir is not None:
            fields.append("data_dir = ?")
            vals.append(data_dir)
        if agent_identity_md is not None:
            fields.append("agent_identity_md = ?")
            vals.append(agent_identity_md)
        if is_active is not None:
            fields.append("is_active = ?")
            vals.append(1 if is_active else 0)
        if fields:
            vals.append(company_id)
            conn.execute(
                f"UPDATE trade_companies SET {', '.join(fields)} WHERE company_id = ?", vals
            )
            conn.commit()
        return get_trade_company(company_id)
    finally:
        conn.close()


def get_agent_identity(company_id: int) -> str:
    """Return the agent identity text for a company.

    Priority:
      1. trade_companies.agent_identity_md (inline override)
      2. {data_dir}/agent-identity.md file on disk
      3. '' (empty — falls back to generic TRADE_SYSTEM_PROMPT)
    """
    tc = get_trade_company(company_id)
    if not tc:
        return ""
    if tc.get("agent_identity_md"):
        return tc["agent_identity_md"]
    data_dir = Path(tc["data_dir"]) if tc.get("data_dir") else None
    if data_dir and data_dir.exists():
        identity_file = data_dir / "agent-identity.md"
        if identity_file.exists():
            return identity_file.read_text(encoding="utf-8")
    return ""


def _row_to_tc(row) -> dict:
    return {
        "company_id": row["company_id"],
        "data_dir": row["data_dir"],
        "agent_identity_md": row["agent_identity_md"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }
