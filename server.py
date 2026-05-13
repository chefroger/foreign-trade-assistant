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

# ── Bootstrap: ensure Hermes Agent is importable ──────────────────────────
# When hermes-agent is published as a standalone pip package, this block
# can be removed — just `pip install hermes-agent` and import normally.
_HERMES_CHECKOUT = os.environ.get(
    "HERMES_HOME",
    str(Path(__file__).resolve().parent.parent / "trade_ai_assistant"),
)
if _HERMES_CHECKOUT and Path(_HERMES_CHECKOUT).is_dir():
    if _HERMES_CHECKOUT not in sys.path:
        sys.path.insert(0, _HERMES_CHECKOUT)

# ── Hermes version check ────────────────────────────────────────────────
_MIN_HERMES_VERSION = "0.12.0"
_MAX_HERMES_VERSION = "0.14.0"  # exclusive upper bound: bumped 2026-05-11 for v0.13.0 compatibility

def _check_hermes_version():
    """Verify the installed Hermes version is compatible with this Trade release.

    Foreign Trade Assistant is tightly coupled to a specific Hermes version
    range.  If Hermes was upgraded independently, refuse to start so the
    user gets a clear error instead of cryptic import/attribute failures.
    """
    try:
        from hermes_cli import __version__ as _hv
    except ImportError:
        print(f"  ✗ Cannot import Hermes. Is hermes-agent installed?")
        print(f"    Install: pip install hermes-agent")
        sys.exit(1)

    _hv_tuple = tuple(int(x) for x in _hv.split("."))
    _min_tuple = tuple(int(x) for x in _MIN_HERMES_VERSION.split("."))
    _max_tuple = tuple(int(x) for x in _MAX_HERMES_VERSION.split("."))

    if not (_min_tuple <= _hv_tuple < _max_tuple):
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
_SESSION_HEADER = "X-Hermes-Session-Token"

app = FastAPI(title="Foreign Trade Assistant")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database initialization ──────────────────────────────────────────────────
# Must run before any API endpoint that touches the DB.
# On fresh install: creates all tables.
# On v0→v1 upgrade: migrates schema + creates default company.
from trade.database import init_db as _init_db
_db_path = _init_db()
print(f"  Database: {_db_path}")

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
            content="<h1>Trade chat UI not found</h1>", status_code=404
        )
    html = _TRADE_CHAT_HTML.read_text(encoding="utf-8")
    html = html.replace(
        "const TOKEN = localStorage.getItem('trade_token') || '';",
        f"const TOKEN = '{_SESSION_TOKEN}';",
    )
    return HTMLResponse(content=html)

# ── Health check ──────────────────────────────────────────────────────────
@app.get("/api/status", include_in_schema=False)
async def status():
    return {"status": "ok", "app": "Foreign Trade Assistant"}

# ── Entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Foreign Trade Assistant")
    parser.add_argument("--port", type=int, default=9119)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}/trade"
    print(f"\n  Foreign Trade Assistant → {url}")
    print(f"  Session token: {_SESSION_TOKEN[:16]}...")
    print()

    if not args.no_browser:
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
