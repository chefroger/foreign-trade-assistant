"""
Trade AI Assistant — 客户管理 API 路由。

端点：
  GET    /customers                              — 列出当前公司的客户
  POST   /customers                              — 创建客户
  GET    /customers/{customer_id}                 — 获取客户详情
  PUT    /customers/{customer_id}                 — 更新客户
  DELETE /customers/{customer_id}                 — 删除客户
  POST   /customers/{customer_id}/libraries/{id}  — 关联文档库
  DELETE /customers/{customer_id}/libraries/{id}  — 取消关联
  GET    /customers/{customer_id}/libraries       — 列出关联的文档库
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from trade import customer as customer_module
from trade import library as library_module
from trade.api.deps import require_company, opt_company

router = APIRouter(tags=["customers"])


# ── 客户 CRUD ──────────────────────────────────────────────────────────────

@router.get("/customers")
def list_customers(x_company_id: Optional[str] = Header(None, alias="X-Company-ID")):
    """列出当前公司的所有客户。"""
    cid = require_company(x_company_id)
    return customer_module.list_by_company(cid)


@router.post("/customers")
def create_customer(
    name: str,
    contact: str = "",
    note: str = "",
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """创建新客户（归属于当前公司）。"""
    cid = require_company(x_company_id)
    return customer_module.create(name, contact, note, company_id=cid)


@router.get("/customers/{customer_id}")
def get_customer(
    customer_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """获取客户详情（必须属于当前公司）。"""
    cid = opt_company(x_company_id)
    cust = customer_module.get(customer_id, company_id=cid)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    return cust


@router.put("/customers/{customer_id}")
def update_customer(
    customer_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
    name: Optional[str] = None,
    contact: Optional[str] = None,
    note: Optional[str] = None,
):
    """更新客户字段（必须属于当前公司）。"""
    cid = require_company(x_company_id)
    kwargs = {
        k: v for k, v in {"name": name, "contact": contact, "note": note}.items()
        if v is not None
    }
    result = customer_module.update(customer_id, company_id=cid, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result


@router.delete("/customers/{customer_id}")
def delete_customer(
    customer_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """删除客户（必须属于当前公司）。"""
    cid = require_company(x_company_id)
    if not customer_module.delete(customer_id, company_id=cid):
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"ok": True}


# ── 客户 ↔ 文档库关联 ────────────────────────────────────────────────────

@router.post("/customers/{customer_id}/libraries/{library_id}")
def link_library_to_customer(
    customer_id: int,
    library_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """将文档库关联到客户（两者必须属于同一公司）。"""
    cid = require_company(x_company_id)
    try:
        customer_module.link_library(customer_id, library_id, company_id=cid)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/customers/{customer_id}/libraries/{library_id}")
def unlink_library_from_customer(
    customer_id: int,
    library_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """取消文档库与客户的关联。"""
    cid = require_company(x_company_id)
    if not customer_module.unlink_library(customer_id, library_id, company_id=cid):
        raise HTTPException(status_code=404, detail="Link not found")
    return {"ok": True}


@router.get("/customers/{customer_id}/libraries")
def get_customer_libraries(
    customer_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """列出客户关联的所有文档库。"""
    cid = require_company(x_company_id)
    return customer_module.get_libraries(customer_id, company_id=cid)
