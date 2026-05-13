"""
Trade AI Assistant — 文档库管理 API 路由。

端点：
  GET    /libraries                   — 列出当前公司的文档库
  POST   /libraries                   — 创建文档库
  GET    /libraries/{library_id}       — 获取文档库详情
  PUT    /libraries/{library_id}       — 更新文档库
  DELETE /libraries/{library_id}       — 删除文档库
  POST   /libraries/{library_id}/upload — 上传文件到文档库
  GET    /libraries/{library_id}/files  — 统计文件数
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from trade import library as library_module
from trade.api.deps import require_company, opt_company

router = APIRouter(tags=["libraries"])


@router.get("/libraries")
def list_libraries(x_company_id: Optional[str] = Header(None, alias="X-Company-ID")):
    """列出当前公司的所有文档库。"""
    cid = opt_company(x_company_id)
    if cid is None:
        raise HTTPException(status_code=401, detail="X-Company-ID header is required.")
    return library_module.list_by_company(cid)


@router.post("/libraries")
def create_library(
    name: str,
    root_path: str,
    description: str = "",
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """创建文档库（关联到当前公司下的本地目录）。"""
    cid = require_company(x_company_id)
    return library_module.create(name, root_path, description, company_id=cid)


@router.get("/libraries/{library_id}")
def get_library(
    library_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """获取单个文档库详情（必须属于当前公司）。"""
    cid = opt_company(x_company_id)
    lib = library_module.get(library_id, company_id=cid)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    return lib


@router.put("/libraries/{library_id}")
def update_library(
    library_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
    name: Optional[str] = None,
    root_path: Optional[str] = None,
    description: Optional[str] = None,
):
    """更新文档库字段（必须属于当前公司）。"""
    cid = require_company(x_company_id)
    kwargs = {
        k: v for k, v in {"name": name, "root_path": root_path, "description": description}.items()
        if v is not None
    }
    result = library_module.update(library_id, company_id=cid, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail="Library not found")
    return result


@router.delete("/libraries/{library_id}")
def delete_library(
    library_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """删除文档库（必须属于当前公司）。"""
    cid = require_company(x_company_id)
    if not library_module.delete(library_id, company_id=cid):
        raise HTTPException(status_code=404, detail="Library not found")
    return {"ok": True}


@router.post("/libraries/{library_id}/upload")
async def upload_file_to_library(
    library_id: int,
    file: UploadFile = File(...),
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """上传文件到文档库的 root_path 目录。"""
    cid = require_company(x_company_id)
    lib = library_module.get(library_id, company_id=cid)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")

    root = Path(lib["root_path"])
    if not root.is_dir():
        root.mkdir(parents=True, exist_ok=True)

    dest = root / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"ok": True, "filename": file.filename, "path": str(dest)}


@router.get("/libraries/{library_id}/files")
def count_library_files(
    library_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """统计文档库目录中的文件数量。"""
    cid = opt_company(x_company_id)
    lib = library_module.get(library_id, company_id=cid)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    return {"count": library_module.count_files(library_id)}
