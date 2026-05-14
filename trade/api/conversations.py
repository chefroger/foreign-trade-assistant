"""
Trade AI Assistant — 对话记录 API 路由。

端点：
  GET    /conversations                   — 列出当前公司的对话
  POST   /conversations                   — 保存对话回合
  GET    /conversations/{conversation_id}  — 获取单条对话
  PUT    /conversations/{conversation_id}  — 更新对话回复
  DELETE /conversations/{conversation_id}  — 删除对话
"""

from __future__ import annotations

import json as _json
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Depends

from trade import chat_memory
from trade import library as library_module
from trade.api.deps import require_company
from trade.api.models import ConversationSave, ConversationUpdate

router = APIRouter(tags=["conversations"])


@router.get("/conversations")
def list_conversations(
    library_id: Optional[int] = None,
    limit: int = 50,
    x_company_id: int = Depends(require_company),
):
    """列出当前公司的最近对话，可按文档库过滤。"""
    if library_id is not None:
        return chat_memory.list_by_library(x_company_id, library_id, limit)
    return chat_memory.list_by_company(x_company_id, limit)


@router.post("/conversations")
def save_conversation(
    payload: ConversationSave,
    x_company_id: int = Depends(require_company),
):
    """保存对话回合到 SQLite + Hindsight 长期记忆。"""
    try:
        files = _json.loads(payload.files_read)
    except _json.JSONDecodeError:
        files = []

    lib_name = ""
    if payload.library_id:
        lib = library_module.get(payload.library_id, company_id=x_company_id)
        if lib:
            lib_name = lib["name"]

    return chat_memory.save_with_context(
        company_id=x_company_id, library_id=payload.library_id,
        query=payload.query, response=payload.response,
        files_read=files, library_name=lib_name,
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    x_company_id: int = Depends(require_company),
):
    """获取单条对话记录。"""
    conv = chat_memory.get(x_company_id, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.put("/conversations/{conversation_id}")
def update_conversation_response(
    conversation_id: int,
    payload: ConversationUpdate,
    x_company_id: int = Depends(require_company),
):
    """更新对话的回复字段。"""
    result = chat_memory.update_response(x_company_id, conversation_id, payload.response)
    if not result:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    x_company_id: int = Depends(require_company),
):
    """删除对话记录。"""
    if not chat_memory.delete(x_company_id, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}
