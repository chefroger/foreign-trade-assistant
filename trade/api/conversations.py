"""
Trade AI Assistant — 对话记录 API 路由。

端点：
  GET    /conversations                   — 列出当前公司的对话
  POST   /conversations                   — 保存对话回合（+ Hindsight 保留）
  GET    /conversations/{conversation_id}  — 获取单条对话
  PUT    /conversations/{conversation_id}  — 更新对话回复
  DELETE /conversations/{conversation_id}  — 删除对话
"""

from __future__ import annotations

import json as _json
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from trade import chat_memory
from trade import library as library_module
from trade.api.deps import require_company, opt_company

router = APIRouter(tags=["conversations"])


@router.get("/conversations")
def list_conversations(
    library_id: Optional[int] = None,
    limit: int = 50,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """列出当前公司的最近对话，可按文档库过滤。"""
    cid = require_company(x_company_id)
    if library_id is not None:
        return chat_memory.list_by_library(cid, library_id, limit)
    return chat_memory.list_by_company(cid, limit)


@router.post("/conversations")
def save_conversation(
    library_id: Optional[int] = None,
    query: str = "",
    response: str = "",
    files_read: str = "[]",
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """保存对话回合（含文件读取记录）到 SQLite + Hindsight 长期记忆。

    files_read: JSON 字符串，格式 [{"file":"...","pages":[1,2]}]
    """
    cid = require_company(x_company_id)
    try:
        files = _json.loads(files_read)
    except _json.JSONDecodeError:
        files = []

    # 解析文档库名称（用于上下文标注）
    lib_name = ""
    if library_id:
        lib = library_module.get(library_id, company_id=cid)
        if lib:
            lib_name = lib["name"]

    return chat_memory.save_with_context(
        company_id=cid, library_id=library_id, query=query,
        response=response, files_read=files, library_name=lib_name,
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """获取单条对话记录（必须属于当前公司）。"""
    cid = require_company(x_company_id)
    conv = chat_memory.get(cid, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.put("/conversations/{conversation_id}")
def update_conversation_response(
    conversation_id: int,
    response: str,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """更新对话的回复字段。"""
    cid = require_company(x_company_id)
    result = chat_memory.update_response(cid, conversation_id, response)
    if not result:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """删除对话记录（必须属于当前公司）。"""
    cid = require_company(x_company_id)
    if not chat_memory.delete(cid, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}
