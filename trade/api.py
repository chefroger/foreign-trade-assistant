"""
Trade AI Assistant — FastAPI router (multi-company version).

REST endpoints for B2B business modules:
  - companies     (multi-tenancy root)
  - libraries     (document library directories, scoped to company)
  - customers     (B2B customers, scoped to company)
  - conversations (chat logs, scoped to company)
  - chat          (AI agent, scoped to company)

Mount with:  app.include_router(trade_api.router, prefix="/api/trade")
"""

from __future__ import annotations

import json as _json
import queue
import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse

from trade import company as company_module
from trade import library, customer, chat_memory
from trade import onboarding
from trade.helpers import check_provider, get_agent_kwargs, build_query

router = APIRouter(tags=["trade"])


# ── Company-scoped request helper ──────────────────────────────────────────

def _require_company(x_company_id: Optional[str]) -> int:
    """Parse and validate X-Company-ID header. Raises 401 if missing/invalid."""
    if not x_company_id or not x_company_id.strip():
        raise HTTPException(
            status_code=401,
            detail="X-Company-ID header is required. "
                   "Call GET /api/trade/companies first to get your company IDs.",
        )
    try:
        cid = int(x_company_id.strip())
    except ValueError:
        raise HTTPException(status_code=401, detail="X-Company-ID must be an integer.")
    # Verify company exists and is active
    tc = company_module.get_trade_company(cid)
    if not tc:
        raise HTTPException(status_code=401, detail=f"Company {cid} not found in Trade system.")
    if not tc.get("is_active"):
        raise HTTPException(status_code=401, detail=f"Company {cid} is inactive.")
    return cid


def _opt_company(x_company_id: Optional[str]) -> Optional[int]:
    """Parse X-Company-ID header, returning None if not provided."""
    if not x_company_id or not x_company_id.strip():
        return None
    try:
        return int(x_company_id.strip())
    except ValueError:
        raise HTTPException(status_code=401, detail="X-Company-ID must be an integer.")


# ── Companies ────────────────────────────────────────────────────────────────

@router.get("/companies")
def list_companies():
    """List all companies registered with Trade."""
    return company_module.list_all()


@router.post("/companies")
def create_company(
    name: str,
    slug: Optional[str] = None,
    logo_url: str = "",
    website: str = "",
    contact_name: str = "",
    contact_email: str = "",
    address: str = "",
):
    """Register a new company in Trade. Slug is auto-generated from name if omitted."""
    try:
        return company_module.create(
            name=name,
            slug=slug,
            logo_url=logo_url,
            website=website,
            contact_name=contact_name,
            contact_email=contact_email,
            address=address,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/companies/{company_id}")
def get_company(company_id: int):
    """Get company details."""
    c = company_module.get(company_id)
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return c


@router.put("/companies/{company_id}")
def update_company(
    company_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
    name: Optional[str] = None,
    logo_url: Optional[str] = None,
    website: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_email: Optional[str] = None,
    address: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """Update company fields. Requires X-Company-ID to match the target company."""
    cid = _opt_company(x_company_id)
    if cid is not None and cid != company_id:
        raise HTTPException(status_code=403, detail="Cannot update another company's record.")
    result = company_module.update(
        company_id,
        name=name, logo_url=logo_url, website=website,
        contact_name=contact_name, contact_email=contact_email,
        address=address, is_active=is_active,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Company not found")
    return result


@router.delete("/companies/{company_id}")
def delete_company(company_id: int):
    """Delete a company and cascade-delete all its libraries, customers, and conversations."""
    if not company_module.delete(company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    return {"ok": True}


@router.get("/companies/{company_id}/agent-identity")
def get_company_agent_identity(company_id: int):
    """Return the agent identity text for a company (inline or from file)."""
    identity = company_module.get_agent_identity(company_id)
    return {"company_id": company_id, "agent_identity_md": identity}


@router.put("/companies/{company_id}/agent-identity")
def update_company_agent_identity(
    company_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
    agent_identity_md: str = "",
):
    """Update the inline agent identity for a company."""
    cid = _opt_company(x_company_id)
    if cid is not None and cid != company_id:
        raise HTTPException(status_code=403, detail="Cannot update another company's identity.")
    result = company_module.update_trade_company(
        company_id, agent_identity_md=agent_identity_md
    )
    if not result:
        raise HTTPException(status_code=404, detail="Company not found")
    return result


# ── Onboarding（首次运行引导）────────────────────────────────────────────────

@router.get("/onboarding/status")
def get_onboarding_status():
    """返回系统是否已完成首次引导。

    前端在打开页面时调用此接口，决定显示引导页还是正常 UI。
    """
    return {"done": onboarding.is_onboarding_done()}


@router.post("/onboarding/first-company")
def create_first_company(body: dict):
    """一体化创建第一个公司并配置 Agent 身份（原子操作）。

    将公司创建 + Agent 身份配置合并为一步，避免两步操作导致状态不完整。
    仅当系统尚未有任何活跃公司时才能调用；已有公司时返回 409。

    Body 参数：
        company_name   (str, 必填): 公司名称
        contact_name   (str, 可选): 联系人姓名
        contact_email  (str, 可选): 联系人邮箱
        identity_data  (dict, 可选): Agent 身份配置，含：
            - role            (str): AI 角色描述
            - products        (str): 产品范围
            - differentiation (str): 差异化卖点
            - target_region   (str): 目标市场

    返回：
        {
            "company": {...},       # 公司记录
            "trade_company": {...},  # Trade 配置记录（含 agent_identity_md）
        }

    状态码：
        200: 创建成功
        409: 系统已有活跃公司，拒绝重复引导
        400: company_name 为空
    """
    # 幂等保护：已有活跃公司时拒绝（防止刷新页面重复提交）
    if onboarding.is_onboarding_done():
        raise HTTPException(
            status_code=409,
            detail="系统已完成首次引导。如需添加新公司，请使用 POST /companies。",
        )

    company_name = (body.get("company_name") or "").strip()
    if not company_name:
        raise HTTPException(status_code=400, detail="company_name 不能为空")

    try:
        result = onboarding.create_first_company(
            company_name=company_name,
            contact_name=body.get("contact_name", ""),
            contact_email=body.get("contact_email", ""),
            identity_data=body.get("identity_data"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Libraries ────────────────────────────────────────────────────────────────

@router.get("/libraries")
def list_libraries(x_company_id: Optional[str] = Header(None, alias="X-Company-ID")):
    """List all document libraries for the current company."""
    cid = _opt_company(x_company_id)
    if cid is None:
        raise HTTPException(status_code=401, detail="X-Company-ID header is required.")
    return library.list_by_company(cid)


@router.post("/libraries")
def create_library(
    name: str,
    root_path: str,
    description: str = "",
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Create a document library scoped to the current company."""
    cid = _require_company(x_company_id)
    return library.create(name, root_path, description, company_id=cid)


@router.get("/libraries/{library_id}")
def get_library(
    library_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Get a single library (must belong to the current company)."""
    cid = _opt_company(x_company_id)
    lib = library.get(library_id, company_id=cid)
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
    """Update a library scoped to the current company."""
    cid = _require_company(x_company_id)
    kwargs = {k: v for k, v in {"name": name, "root_path": root_path,
                                 "description": description}.items() if v is not None}
    result = library.update(library_id, company_id=cid, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail="Library not found")
    return result


@router.delete("/libraries/{library_id}")
def delete_library(
    library_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Delete a library scoped to the current company."""
    cid = _require_company(x_company_id)
    if not library.delete(library_id, company_id=cid):
        raise HTTPException(status_code=404, detail="Library not found")
    return {"ok": True}


@router.post("/libraries/{library_id}/upload")
async def upload_file_to_library(
    library_id: int,
    file: UploadFile = File(...),
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Upload a file to a library's root_path directory."""
    cid = _require_company(x_company_id)
    lib = library.get(library_id, company_id=cid)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")

    import shutil
    from pathlib import Path

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
    """Count files in a library's directory."""
    cid = _opt_company(x_company_id)
    lib = library.get(library_id, company_id=cid)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    return {"count": library.count_files(library_id)}


# ── Customers ────────────────────────────────────────────────────────────────

@router.get("/customers")
def list_customers(x_company_id: Optional[str] = Header(None, alias="X-Company-ID")):
    """List all customers for the current company."""
    cid = _require_company(x_company_id)
    return customer.list_by_company(cid)


@router.post("/customers")
def create_customer(
    name: str,
    contact: str = "",
    note: str = "",
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Create a customer scoped to the current company."""
    cid = _require_company(x_company_id)
    return customer.create(name, contact, note, company_id=cid)


@router.get("/customers/{customer_id}")
def get_customer(
    customer_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Get a single customer scoped to the current company."""
    cid = _opt_company(x_company_id)
    cust = customer.get(customer_id, company_id=cid)
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
    """Update a customer scoped to the current company."""
    cid = _require_company(x_company_id)
    kwargs = {k: v for k, v in {"name": name, "contact": contact, "note": note}.items()
              if v is not None}
    result = customer.update(customer_id, company_id=cid, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result


@router.delete("/customers/{customer_id}")
def delete_customer(
    customer_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Delete a customer scoped to the current company."""
    cid = _require_company(x_company_id)
    if not customer.delete(customer_id, company_id=cid):
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"ok": True}


# ── Customer ↔ Library associations ──────────────────────────────────────────

@router.post("/customers/{customer_id}/libraries/{library_id}")
def link_library_to_customer(
    customer_id: int,
    library_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Associate a library with a customer (both must belong to the current company)."""
    cid = _require_company(x_company_id)
    try:
        customer.link_library(customer_id, library_id, company_id=cid)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/customers/{customer_id}/libraries/{library_id}")
def unlink_library_from_customer(
    customer_id: int,
    library_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Remove a library association scoped to the current company."""
    cid = _require_company(x_company_id)
    if not customer.unlink_library(customer_id, library_id, company_id=cid):
        raise HTTPException(status_code=404, detail="Link not found")
    return {"ok": True}


@router.get("/customers/{customer_id}/libraries")
def get_customer_libraries(
    customer_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """List libraries linked to a customer, scoped to the current company."""
    cid = _require_company(x_company_id)
    return customer.get_libraries(customer_id, company_id=cid)


# ── Chat Memory ──────────────────────────────────────────────────────────────

@router.get("/conversations")
def list_conversations(
    library_id: Optional[int] = None,
    limit: int = 50,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """List recent conversations for the current company, optionally filtered by library."""
    cid = _require_company(x_company_id)
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
    """Save a conversation turn scoped to the current company.

    files_read is a JSON string: [{"file":"...","pages":[1,2]}]
    Also retains to Hindsight long-term memory when available.
    """
    cid = _require_company(x_company_id)
    try:
        files = _json.loads(files_read)
    except _json.JSONDecodeError:
        files = []

    lib_name = ""
    if library_id:
        lib = library.get(library_id, company_id=cid)
        if lib:
            lib_name = lib["name"]

    return chat_memory.save_with_context(
        company_id=cid,
        library_id=library_id,
        query=query,
        response=response,
        files_read=files,
        library_name=lib_name,
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Get a single conversation scoped to the current company."""
    cid = _require_company(x_company_id)
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
    """Update the response for a conversation scoped to the current company."""
    cid = _require_company(x_company_id)
    result = chat_memory.update_response(cid, conversation_id, response)
    if not result:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Delete a conversation scoped to the current company."""
    cid = _require_company(x_company_id)
    if not chat_memory.delete(cid, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


# ── Memory / Hindsight ──────────────────────────────────────────────────────

@router.get("/memory/status")
def memory_status(x_company_id: Optional[str] = Header(None, alias="X-Company-ID")):
    """Check whether Hindsight long-term memory is available."""
    try:
        from trade.memory import is_available as hindsight_available
        return {
            "hindsight_available": hindsight_available(),
            "company_id": _opt_company(x_company_id),
        }
    except ImportError:
        return {"hindsight_available": False, "company_id": None}


@router.get("/memory/recall")
def memory_recall(
    query: str,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Search Hindsight long-term memory for relevant past conversations."""
    result = chat_memory.recall_context(query)
    if not result:
        return {"results": [], "query": query}
    return {"results": [result], "query": query}


# ── Models & Providers ─────────────────────────────────────────────────────

@router.get("/models/providers")
def list_providers():
    """List configured LLM providers and their available models.

    Reads from config.yaml and the provider registry to return a list
    of providers with their models, base URLs, and status.
    """
    try:
        from hermes_cli.auth import PROVIDER_REGISTRY
        from hermes_cli.config import load_config
        import os

        cfg = load_config()
        model_cfg = cfg.get("model", {})
        active_provider = ""
        active_model = ""
        if isinstance(model_cfg, dict):
            active_provider = model_cfg.get("provider", "")
            active_model = model_cfg.get("default", "")

        providers = []
        for pid, pconfig in PROVIDER_REGISTRY.items():
            has_key = False
            if pconfig.auth_type == "api_key":
                for env_name in pconfig.api_key_env_vars:
                    if os.getenv(env_name):
                        has_key = True
                        break

            try:
                from hermes_cli.models import name_to_models
                models = name_to_models.get(pid, [])
            except Exception:
                models = []

            providers.append({
                "id": pid,
                "name": pconfig.display_name or pid,
                "has_key": has_key,
                "models": models[:10],
                "is_active": pid == active_provider,
                "active_model": active_model if pid == active_provider else "",
            })

        return {
            "providers": providers,
            "active_provider": active_provider,
            "active_model": active_model,
        }
    except Exception as e:
        return {"providers": [], "error": str(e)}


# ── Agent Chat ──────────────────────────────────────────────────────────────

@router.post("/chat")
async def trade_chat(
    body: dict,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Send a query to the AI Agent and return the response.

    Body: {query, library_id?, customer_id?}
    Returns: {response, conversation}

    The company_id is required (via X-Company-ID header) and determines:
      - Which company identity is injected into the system prompt
      - Which company's data directory is available to the agent
      - Which company's conversation history is saved/retrieved
    """
    import asyncio
    import logging

    _log = logging.getLogger(__name__)

    cid = _require_company(x_company_id)
    query = (body.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    library_id = body.get("library_id")

    # Build prompt with company context (agent identity + library context)
    full_query = build_query(cid, library_id, query)

    def _call_agent():
        try:
            from run_agent import AIAgent
        except ImportError:
            return "⚠️ AI Agent 模块未加载。"

        err = check_provider()
        if err:
            return f"⚠️ {err}"

        try:
            kwargs = get_agent_kwargs()
            os.environ["HERMES_YOLO_MODE"] = "true"
            agent = AIAgent(
                quiet_mode=True,
                max_iterations=90,
                provider=kwargs["provider"] or None,
                base_url=kwargs["base_url"] or None,
                model=kwargs["model"] or None,
                api_key=kwargs["api_key"] or None,
            )
            return agent.chat(full_query) or "Agent 返回了空响应。"
        except ImportError:
            return "⚠️ AI Agent 模块未加载。"
        except Exception as e:
            _log.exception("Agent call failed")
            return f"⚠️ Agent 调用失败：{e}"

    loop = asyncio.get_event_loop()
    try:
        response = await asyncio.wait_for(
            loop.run_in_executor(None, _call_agent),
            timeout=600,
        )
    except asyncio.TimeoutError:
        response = "⏰ Agent 执行时间过长（超过 10 分钟），已自动中止。请简化问题后重试。"

    # Resolve library name for context
    lib_name = ""
    if library_id:
        lib = library.get(library_id, company_id=cid)
        if lib:
            lib_name = lib["name"]

    conv = chat_memory.save_with_context(
        company_id=cid,
        library_id=library_id,
        query=query,
        response=response,
        library_name=lib_name,
    )
    return {"response": response, "conversation": conv}


@router.post("/chat/stream")
async def trade_chat_stream(
    body: dict,
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
):
    """Stream agent progress as Server-Sent Events.

    Body: {query, library_id?, customer_id?}
    Yields tool_start, tool_complete, thinking, response, error, done events.

    Requires X-Company-ID header for company isolation.
    """
    import asyncio
    import logging

    _log = logging.getLogger(__name__)

    cid = _require_company(x_company_id)
    query = (body.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    library_id = body.get("library_id")
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
        try:
            from run_agent import AIAgent
        except ImportError:
            _emit("error", {"message": "AI Agent 模块未加载。"})
            return None

        err = check_provider()
        if err:
            _emit("error", {"message": err})
            return None

        try:
            kwargs = get_agent_kwargs()
            _emit("thinking", {"message": "正在分析问题..."})

            os.environ["HERMES_YOLO_MODE"] = "true"
            agent = AIAgent(
                quiet_mode=True,
                max_iterations=90,
                provider=kwargs["provider"] or None,
                base_url=kwargs["base_url"] or None,
                model=kwargs["model"] or None,
                api_key=kwargs["api_key"] or None,
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

            # Resolve library name and save conversation
            lib_name = ""
            if library_id:
                lib = library.get(library_id, company_id=cid)
                if lib:
                    lib_name = lib["name"]

            try:
                chat_memory.save_with_context(
                    company_id=cid,
                    library_id=library_id,
                    query=query,
                    response=result or "",
                    library_name=lib_name,
                )
            except Exception:
                pass

            return result
        except ImportError:
            _emit("error", {"message": "AI Agent 模块未加载。"})
        except Exception as e:
            _log.exception("Agent stream failed")
            _emit("error", {"message": f"Agent 调用失败：{e}"})
        return None

    async def _event_stream():
        loop = asyncio.get_event_loop()

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
