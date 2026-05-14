"""
Trade AI Assistant — 文档库管理 API 路由。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends

from trade import library as library_module
from trade.api.deps import require_company
from trade.api.models import LibraryCreate, LibraryUpdate

router = APIRouter(tags=["libraries"])


@router.get("/libraries")
def list_libraries(
    x_company_id: int = Depends(require_company),
):
    """列出当前公司的所有文档库。"""
    return library_module.list_by_company(x_company_id)


@router.post("/libraries")
def create_library(
    payload: LibraryCreate,
    x_company_id: int = Depends(require_company),
):
    """创建文档库（关联到当前公司下的本地目录）。"""
    return library_module.create(
        payload.name, payload.root_path, payload.description,
        company_id=x_company_id,
    )


@router.get("/libraries/{library_id}")
def get_library(
    library_id: int,
    x_company_id: int = Depends(require_company),
):
    """获取单个文档库详情。"""
    lib = library_module.get(library_id, company_id=x_company_id)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    return lib


@router.put("/libraries/{library_id}")
def update_library(
    library_id: int,
    payload: LibraryUpdate,
    x_company_id: int = Depends(require_company),
):
    """更新文档库字段。"""
    kwargs = payload.model_dump(exclude_none=True)
    result = library_module.update(library_id, company_id=x_company_id, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail="Library not found")
    return result


@router.delete("/libraries/{library_id}")
def delete_library(
    library_id: int,
    x_company_id: int = Depends(require_company),
):
    """删除文档库。"""
    if not library_module.delete(library_id, company_id=x_company_id):
        raise HTTPException(status_code=404, detail="Library not found")
    return {"ok": True}


@router.get("/libraries/{library_id}/files")
def count_library_files(
    library_id: int,
    x_company_id: int = Depends(require_company),
):
    """统计文档库目录中的文件数量。"""
    lib = library_module.get(library_id, company_id=x_company_id)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    return {"count": library_module.count_files(library_id, company_id=x_company_id)}
