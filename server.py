"""
Foreign Trade Assistant — standalone FastAPI server.

Start:
    python server.py
    python server.py --port 9119

The server hosts:
  - /trade            B2B chat SPA
  - /api/trade/*      REST API (libraries, customers, chat, memory)

Depends on Hermes Agent being installed (pip install hermes-agent) or
available on PYTHONPATH.
"""

import argparse
import os
import sys
from pathlib import Path

# ── Bootstrap: ensure Foreign Trade Assistant imports BEFORE Hermes ──────
# Hermes also has a `trade/` package; our `trade/` must take priority.
# NOTE: When hermes-agent is published as a standalone pip package, this block
# can be removed — just `pip install hermes-agent` and import normally.
_TRADE_ROOT = str(Path(__file__).resolve().parent)
if _TRADE_ROOT not in sys.path:
    sys.path.insert(0, _TRADE_ROOT)

_HERMES_CHECKOUT = os.environ.get(
    "HERMES_HOME",
    str(Path(__file__).resolve().parent.parent / "trade_ai_assistant"),
)
if _HERMES_CHECKOUT and Path(_HERMES_CHECKOUT).is_dir():
    if _HERMES_CHECKOUT not in sys.path:
        sys.path.append(_HERMES_CHECKOUT)  # append, not insert — our trade/ must come first

# ── Hermes version check ────────────────────────────────────────────────
_MIN_HERMES_VERSION = "0.12.0"
_MAX_HERMES_VERSION = "0.14.0"  # exclusive upper bound: bumped 2026-05-11 for v0.13.0 compatibility

def _check_hermes_version():
    """Verify the installed Hermes version is compatible with this Trade release.

    使用 packaging.version 进行符合 PEP 440 的版本比较，
    正确处理 0.12.0rc1 / 0.12.0.post1 等预发布/后发布版本。
    """
    from packaging.version import Version

    try:
        from hermes_cli import __version__ as _hv
    except ImportError:
        print(f"  ✗ Cannot import Hermes. Is hermes-agent installed?")
        print(f"    Install: pip install hermes-agent")
        sys.exit(1)

    _current = Version(_hv)
    _min_v = Version(_MIN_HERMES_VERSION)
    _max_v = Version(_MAX_HERMES_VERSION)

    if not (_min_v <= _current < _max_v):
        print(f"  ✗ Hermes version {_hv} is not compatible with this release.")
        print(f"    Foreign Trade Assistant requires hermes-agent >={_MIN_HERMES_VERSION},<{_MAX_HERMES_VERSION}.")
        print(f"    Installed: {_hv}")
        print(f"    Run: pip install 'hermes-agent>={_MIN_HERMES_VERSION},<{_MAX_HERMES_VERSION}'")
        sys.exit(1)

    print(f"  ✓ Hermes {_hv} (compatible: >={_MIN_HERMES_VERSION},<{_MAX_HERMES_VERSION})")

_check_hermes_version()

# Load Hermes .env before any other imports (AIAgent depends on it)
from hermes_cli.env_loader import load_hermes_dotenv
from hermes_constants import get_hermes_home
load_hermes_dotenv(hermes_home=get_hermes_home())
# Hermes 会检查此环境变量以跳过工具审批
os.environ["HERMES_YOLO_MODE"] = "true"

# 屏蔽 Hermes 可选工具缺失的 stderr 警告（如 fal_client 图片生成工具）
# 这些工具在外贸场景中不需要，但 Hermes 启动时会打印警告干扰用户
import io as _io
_sys_stderr_filtered = _io.TextIOWrapper(
    open(sys.stderr.fileno(), "wb", buffering=0, closefd=False),
    encoding=sys.stderr.encoding, errors="replace",
)
_sys_stderr_filtered_write = _sys_stderr_filtered.write
def _filtered_write(data):
    # 静默屏蔽无害的工具缺失警告
    if "Could not import tool module" in data or "No module named" in data:
        return len(data)  # 假装写入成功
    return _sys_stderr_filtered_write(data)
_sys_stderr_filtered.write = _filtered_write
sys.stderr = _sys_stderr_filtered

# ── Server ────────────────────────────────────────────────────────────────
import secrets
import webbrowser

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import uvicorn

# Session token — same ephemeral auth pattern as Hermes dashboard
_SESSION_TOKEN = secrets.token_urlsafe(32)

app = FastAPI(title="Foreign Trade Assistant")


def _install_cors(port: int) -> None:
    """根据实际监听端口注册 CORS 中间件（仅本机）。"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        ],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["X-Hermes-Session-Token", "X-Company-ID", "Content-Type"],
    )

# ── Skills sync check ───────────────────────────────────────────────────────
import hashlib

def _sync_b2b_skills():
    """Ensure Hermes has the latest B2B skills from the project.

    Compares each b2b-* skill in the project's skills/ directory with the
    installed copy in ~/.hermes/skills/.  Missing or outdated skills are
    copied over.  New skills are installed; removed skills are NOT deleted
    (the user may have added their own).
    """
    _project_skills = Path(__file__).parent / "skills"
    if not _project_skills.is_dir():
        return

    _hermes_skills = get_hermes_home() / "skills"
    _hermes_skills.mkdir(parents=True, exist_ok=True)

    _synced = 0
    for _skill_dir in sorted(_project_skills.iterdir()):
        if not _skill_dir.is_dir() or not _skill_dir.name.startswith("b2b-"):
            continue

        _src = _skill_dir / "SKILL.md"
        if not _src.is_file():
            continue

        _dst_dir = _hermes_skills / _skill_dir.name
        _dst = _dst_dir / "SKILL.md"

        # Compare content hash
        _need_copy = True
        if _dst.is_file():
            _src_hash = hashlib.sha256(_src.read_bytes()).hexdigest()
            _dst_hash = hashlib.sha256(_dst.read_bytes()).hexdigest()
            _need_copy = _src_hash != _dst_hash

        if _need_copy:
            _dst_dir.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(_src, _dst)
            _synced += 1
            print(f"  ↻ Updated skill: {_skill_dir.name}")

    if _synced > 0:
        print(f"  Skills synced: {_synced} updated (Hermes will pick up changes on next request)")
    else:
        print(f"  Skills: up-to-date")

_sync_b2b_skills()

# ── Database initialization ──────────────────────────────────────────────────
# Must run before any API endpoint that touches the DB.
# On fresh install: creates all tables.
# On v0→v1 upgrade: migrates schema + creates default company.
from trade.database import init_db as _init_db
_db_path = _init_db()
print(f"  Database: {_db_path}")

# ── Inject session token before mounting routes ───────────────────────────
from trade.api.deps import set_session_token
set_session_token(_SESSION_TOKEN)

# ── Mount Trade API ───────────────────────────────────────────────────────
from trade.api import router as trade_router
app.include_router(trade_router, prefix="/api/trade")

# ── Serve Trade Chat SPA ──────────────────────────────────────────────────
_TRADE_CHAT_HTML = Path(__file__).parent / "static" / "trade_chat.html"

@app.get("/trade", response_class=HTMLResponse, include_in_schema=False)
async def trade_chat_ui():
    """Serve the B2B chat interface with session token injected."""
    if not _TRADE_CHAT_HTML.exists():
        return HTMLResponse(
            content='<html><body style="font-family:sans-serif;padding:2rem;"><h1>Trade chat UI not found</h1><p>The frontend file <code>static/trade_chat.html</code> is missing.</p></body></html>',
            status_code=404,
        )
    html = _TRADE_CHAT_HTML.read_text(encoding="utf-8")
    # 用唯一占位符注入 session token，避免依赖 JS 字符串格式
    html = html.replace("__TRADE_SESSION_TOKEN__", _SESSION_TOKEN)
    return HTMLResponse(content=html)

# ── Health check ──────────────────────────────────────────────────────────
@app.get("/api/status", include_in_schema=False)
async def status():
    return {"status": "ok", "app": "Foreign Trade Assistant"}

# ── Hermes Gateway 子进程管理 ─────────────────────────────────────────────

import subprocess as _sp

def _is_gateway_running() -> bool:
    """检查是否有 Hermes Gateway 进程在运行。"""
    try:
        result = _sp.run(
            ["pgrep", "-f", "hermes.*gateway"],
            capture_output=True, text=True, timeout=3,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False

def _ensure_gateway_running() -> None:
    """如果 Gateway 未运行，启动它。Gateway 独立于 Trade 生命周期，Trade 退出后仍保持运行。"""
    if _is_gateway_running():
        print(f"  Hermes Gateway → running (cron scheduler active)")
        return

    try:
        # 使用 hermes CLI（而非 python -m），确保使用正确的 venv
        import shutil as _sh
        hermes_bin = _sh.which("hermes") or "hermes"
        _sp.Popen(
            [hermes_bin, "gateway", "run"],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
            start_new_session=True,
            env={**os.environ, "GATEWAY_ALLOW_ALL_USERS": "true"},
        )
        print(f"  Hermes Gateway → started (cron scheduler active)")
    except Exception as e:
        print(f"  ⚠️  Hermes Gateway 启动失败: {e}")

# ── Entry point ───────────────────────────────────────────────────────────
def main() -> None:
    """`trade` console script 入口 + `python server.py` 入口。"""
    parser = argparse.ArgumentParser(description="Foreign Trade Assistant")
    parser.add_argument("--port", type=int, default=9119)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-gateway", action="store_true", help="不检查/启动 Hermes Gateway")
    args = parser.parse_args()

    _install_cors(args.port)

    if not args.no_gateway:
        _ensure_gateway_running()

    url = f"http://{args.host}:{args.port}/trade"
    print(f"\n  Foreign Trade Assistant → {url}")
    print(f"  Session token: {_SESSION_TOKEN[:16]}...")
    print()

    if not args.no_browser:
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")

if __name__ == "__main__":
    main()
