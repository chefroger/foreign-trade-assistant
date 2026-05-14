"""
Trade AI Assistant — AI 聊天 API 路由。

端点：
  POST /chat         — 同步聊天（线程池 + 600s 超时）
  POST /chat/stream  — SSE 流式聊天（tool_start/tool_complete/thinking/response/error/done 事件）
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import queue
import time

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from trade import chat_memory
from trade import library as library_module
from trade.api.deps import require_company
from trade.api.models import ChatRequest
from trade.helpers import create_agent, build_query

_log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


# ── 同步聊天 ──────────────────────────────────────────────────────────────

@router.post("/chat")
async def trade_chat(
    payload: ChatRequest,
    cid: int = Depends(require_company),
):
    """向 AI Agent 发送查询并同步等待结果。"""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    library_id = payload.library_id

    # 构建带公司上下文的完整 prompt（身份 + 文档库上下文 + 历史）
    full_query = build_query(cid, library_id, query)

    def _call_agent():
        """在线程池中调用 Hermes Agent（同步阻塞）。"""
        try:
            agent = create_agent()
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
        # 在线程池中执行同步 agent，10 分钟超时
        response = await asyncio.wait_for(
            loop.run_in_executor(None, _call_agent),
            timeout=600,
        )
    except asyncio.TimeoutError:
        response = "⏰ Agent 执行时间过长（超过 10 分钟），已自动中止。请简化问题后重试。"

    # 保存对话记录
    lib_name = ""
    if library_id:
        lib = library_module.get(library_id, company_id=cid)
        if lib:
            lib_name = lib["name"]

    conv = chat_memory.save_with_context(
        company_id=cid, library_id=library_id, query=query,
        response=response, library_name=lib_name,
    )
    return {"response": response, "conversation": conv}


# ── SSE 流式聊天 ──────────────────────────────────────────────────────────

@router.post("/chat/stream")
async def trade_chat_stream(
    payload: ChatRequest,
    cid: int = Depends(require_company),
):
    """SSE 流式聊天，实时推送 Agent 工具调用进度。"""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    library_id = payload.library_id
    full_query = build_query(cid, library_id, query)

    event_queue: queue.Queue = queue.Queue()

    def _emit(event_type: str, data: dict | None = None):
        event_queue.put((event_type, data or {}))

    def _tool_start(tc_id, name, args):
        _emit("tool_start", {"tool_call_id": tc_id, "name": name, "args": args})

    def _tool_complete(tc_id, name, args, result):
        preview = ""
        if isinstance(result, str):
            preview = result[:300]
        elif isinstance(result, (list, dict)):
            preview = _json.dumps(result, ensure_ascii=False)[:300]
        _emit("tool_complete", {
            "tool_call_id": tc_id, "name": name, "result_preview": preview,
        })

    def _run_agent() -> str | None:
        """在线程池中运行 Agent，通过回调推送到事件队列。"""
        try:
            _emit("thinking", {"message": "正在分析问题..."})
            agent = create_agent(
                tool_start_callback=_tool_start,
                tool_complete_callback=_tool_complete,
            )

            start = time.time()
            result = agent.chat(full_query)
            elapsed = time.time() - start

            _emit("response", {
                "text": result or "Agent 返回了空响应。",
                "elapsed_sec": round(elapsed, 1),
            })

            lib_name = ""
            if library_id:
                lib = library_module.get(library_id, company_id=cid)
                if lib:
                    lib_name = lib["name"]

            try:
                chat_memory.save_with_context(
                    company_id=cid, library_id=library_id,
                    query=query, response=result or "",
                    library_name=lib_name,
                )
            except Exception:
                pass

            return result
        except ImportError:
            _emit("error", {"message": "AI Agent 模块未加载。"})
        except RuntimeError as e:
            _emit("error", {"message": str(e)})
        except Exception as e:
            _log.exception("Agent stream failed")
            _emit("error", {"message": f"Agent 调用失败：{e}"})
        return None

    async def _event_stream():
        """SSE 事件生成器：从队列消费事件，yield SSE 格式字符串。"""
        loop = asyncio.get_running_loop()

        def _sse(ev_type: str, payload: dict) -> str:
            return f"event: {ev_type}\ndata: {_json.dumps(payload, ensure_ascii=False)}\n\n"

        agent_task = loop.run_in_executor(None, _run_agent)

        while True:
            try:
                ev_type, ev_data = await loop.run_in_executor(
                    None, event_queue.get, True, 0.5
                )
            except queue.Empty:
                if agent_task.done():
                    while not event_queue.empty():
                        try:
                            ev_type, ev_data = event_queue.get_nowait()
                            yield _sse(ev_type, ev_data)
                        except queue.Empty:
                            break
                    break
                continue

            yield _sse(ev_type, ev_data)

            if ev_type in ("response", "error"):
                while not event_queue.empty():
                    try:
                        ev_type, ev_data = event_queue.get_nowait()
                        yield _sse(ev_type, ev_data)
                    except queue.Empty:
                        break
                break

        await agent_task
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
