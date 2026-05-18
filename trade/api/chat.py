"""
Trade AI Assistant — AI 聊天 API 路由。

端点：
  POST /chat         — 同步聊天（线程池 + 600s 超时）
  POST /chat/stream  — SSE 流式聊天（asyncio.Queue + 心跳 + 断连取消）
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from trade import chat_memory
from trade import library as library_module
from trade.api.deps import require_company
from trade.api.models import ChatRequest
from trade.helpers import build_query, create_agent

_log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


# ── 同步聊天 ──────────────────────────────────────────────────────────────

@router.post("/chat")
async def trade_chat(
    payload: ChatRequest,
    cid: int = Depends(require_company),
):
    """同步聊天。"""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    full_query, skill_hint = build_query(cid, payload.library_id, query, customer_id=payload.customer_id)

    def _call_agent():
        try:
            agent = create_agent(ephemeral_system_prompt=skill_hint)
            return agent.chat(full_query) or "Agent 返回了空响应。"
        except ImportError:
            return "⚠️ AI Agent 模块未加载。"
        except RuntimeError as e:
            return f"⚠️ {e}"
        except Exception as e:
            _log.exception("Agent call failed")
            return f"⚠️ Agent 调用失败：{e}"

    loop = asyncio.get_running_loop()
    try:
        response = await asyncio.wait_for(
            loop.run_in_executor(None, _call_agent),
            timeout=600,
        )
    except TimeoutError:
        response = "⏰ Agent 执行时间过长（超过 10 分钟），已自动中止。请简化问题后重试。"

    lib_name = ""
    if payload.library_id:
        lib = library_module.get(payload.library_id, company_id=cid)
        if lib:
            lib_name = lib["name"]

    conv = chat_memory.save_with_context(
        company_id=cid, library_id=payload.library_id, query=query,
        response=response, library_name=lib_name,
    )
    return {"response": response, "conversation": conv}


# ── SSE 流式聊天 ──────────────────────────────────────────────────────────

@router.post("/chat/stream")
async def trade_chat_stream(
    payload: ChatRequest,
    cid: int = Depends(require_company),
):
    """SSE 流式聊天，实时推送 Agent 工具调用进度。

    使用 asyncio.Queue + call_soon_threadsafe 替代 queue.Queue + executor 轮询，
    每条 SSE 连接只占用 1 条线程。客户端断连时通过 CancelledError 取消 agent。
    """
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    full_query, skill_hint = build_query(cid, payload.library_id, query, customer_id=payload.customer_id)

    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

    def _emit_threadsafe(event_type: str, data: dict | None = None):
        """工作线程通过 call_soon_threadsafe 投递到 asyncio queue。"""
        loop.call_soon_threadsafe(event_queue.put_nowait, (event_type, data or {}))

    def _tool_start(tc_id, name, args):
        _emit_threadsafe("tool_start", {"tool_call_id": tc_id, "name": name, "args": args})

    def _tool_complete(tc_id, name, args, result):
        preview = ""
        if isinstance(result, str):
            preview = result[:300]
        elif isinstance(result, (list, dict)):
            preview = _json.dumps(result, ensure_ascii=False)[:300]
        _emit_threadsafe("tool_complete", {
            "tool_call_id": tc_id, "name": name, "result_preview": preview,
        })

    def _run_agent() -> str | None:
        try:
            _emit_threadsafe("thinking", {"message": "正在分析问题..."})
            agent = create_agent(
                tool_start_callback=_tool_start,
                tool_complete_callback=_tool_complete,
                ephemeral_system_prompt=skill_hint,
            )
            start = time.time()
            result = agent.chat(full_query)
            elapsed = time.time() - start

            _emit_threadsafe("response", {
                "text": result or "Agent 返回了空响应。",
                "elapsed_sec": round(elapsed, 1),
            })

            lib_name = ""
            if payload.library_id:
                lib = library_module.get(payload.library_id, company_id=cid)
                if lib:
                    lib_name = lib["name"]
            try:
                chat_memory.save_with_context(
                    company_id=cid, library_id=payload.library_id,
                    query=query, response=result or "",
                    library_name=lib_name,
                )
            except Exception:
                _log.exception("save_with_context failed in stream")
            return result
        except ImportError:
            _emit_threadsafe("error", {"message": "AI Agent 模块未加载。"})
        except RuntimeError as e:
            _emit_threadsafe("error", {"message": str(e)})
        except Exception as e:
            _log.exception("Agent stream failed")
            _emit_threadsafe("error", {"message": f"Agent 调用失败：{e}"})
        return None

    async def _event_stream():
        def _sse(ev_type: str, payload: dict) -> str:
            return f"event: {ev_type}\ndata: {_json.dumps(payload, ensure_ascii=False)}\n\n"

        agent_task = loop.run_in_executor(None, _run_agent)
        try:
            while True:
                try:
                    # 15s 心跳，防止反向代理/nginx 空闲断开
                    ev_type, ev_data = await asyncio.wait_for(event_queue.get(), timeout=15.0)
                except TimeoutError:
                    if agent_task.done():
                        break
                    yield ": ping\n\n"
                    continue

                yield _sse(ev_type, ev_data)
                if ev_type in ("response", "error"):
                    break
        finally:
            # 客户端断连或异常 → 尝试取消 agent 任务
            if not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except (asyncio.CancelledError, Exception):
                    pass
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")
