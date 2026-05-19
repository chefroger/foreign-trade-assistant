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
import hashlib
import logging as _logging
import os
import shutil
import sys
import warnings as _warnings
from pathlib import Path


# 在任何 Hermes import 之前安装日志过滤器，
# 确保 Hermes 启动时的可选工具缺失警告被正确屏蔽
class _ToolImportNoiseFilter(_logging.Filter):
    """过滤 Hermes 启动时无关的可选工具缺失警告。"""
    _NOISE = ("Could not import tool module", "No module named")
    def filter(self, record: _logging.LogRecord) -> bool:
        return not any(p in record.getMessage() for p in self._NOISE)

_logging.getLogger().addFilter(_ToolImportNoiseFilter())
_warnings.filterwarnings("ignore", message=r".*Could not import tool module.*")
_warnings.filterwarnings("ignore", message=r".*No module named.*")

# ── Bootstrap: ensure Foreign Trade Assistant imports BEFORE Hermes ──────
# Hermes also has a `trade/` package; our `trade/` must take priority.
# NOTE: When hermes-agent is published as a standalone pip package, this block
# can be removed — just `pip install hermes-agent` and import normally.
_TRADE_ROOT = str(Path(__file__).resolve().parent)
if _TRADE_ROOT not in sys.path:
    # 如果项目根路径不在 sys.path 中，插入到最前面以优先于 Hermes 的同名包
    sys.path.insert(0, _TRADE_ROOT)

# Hermes 源码路径优先级：
#   1. HERMES_HOME 环境变量（通常指向 ~/.hermes/hermes-agent/，即 pip install 的源码目录）
#   2. 与 Trade 平级的 trade_ai_assistant 开发目录（兼容旧开发环境）
#   3. 如果都不存在，依赖 pip 安装的 hermes-agent 包（无需 sys.path 调整）
_HERMES_CHECKOUT = os.environ.get("HERMES_HOME", "").strip()
if not _HERMES_CHECKOUT:
    # 如果没有设置 HERMES_HOME，尝试默认的 pip 安装目录
    _default_hermes = Path.home() / ".hermes" / "hermes-agent"
    if _default_hermes.is_dir():
        _HERMES_CHECKOUT = str(_default_hermes)
if not _HERMES_CHECKOUT:
    # 最后兜底：与 Trade 平级的 trade_ai_assistant 目录（旧开发环境）
    _dev_hermes = str(Path(__file__).resolve().parent.parent / "trade_ai_assistant")
    if Path(_dev_hermes).is_dir():
        _HERMES_CHECKOUT = _dev_hermes

if _HERMES_CHECKOUT:
    # 确保 Hermes 在 sys.path 中（放在最前面，优先于 Trade 根路径）
    # 注意：Trade 自己的 _TRADE_ROOT 已在上面 insert 到第 0 位，
    #       这里 Hermes 放在第 0 位会覆盖 trade/ 包的查找。
    #       由于 Hermes 的 trade/ 包名和 Trade 的 trade/ 冲突，
    #       我们用 insert 把 Hermes 放在第 1 位，Trade 仍在第 0 位。
    if _HERMES_CHECKOUT not in sys.path:
        sys.path.insert(1, _HERMES_CHECKOUT)

# ── 子命令优先处理 ───────────────────────────────────────────────────────
# trade update / trade backup / trade skills-update 不需要启动服务器
# 需要在这尽早分发，跳过 Hermes 版本检查、skills 同步、DB 初始化等
_cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if _cmd in ("update", "backup", "skills-update"):
    if _cmd == "update":
        from trade.post_install import update_trade
        update_trade()
    elif _cmd == "backup":
        from trade.post_install import backup_trade
        print(backup_trade())
    else:  # skills-update
        from trade.post_install import update_skills
        update_skills()
    sys.exit(0)

# ── Hermes version check ────────────────────────────────────────────────
_MIN_HERMES_VERSION = "0.13.0"
_MAX_HERMES_VERSION = "0.15.0"  # exclusive upper bound: bumped 2026-05-18 for v0.14.0 compatibility

def _check_hermes_version():
    """Verify the installed Hermes version is compatible with this Trade release.

    使用 packaging.version 进行符合 PEP 440 的版本比较，
    正确处理 0.12.0rc1 / 0.12.0.post1 等预发布/后发布版本。
    """
    from packaging.version import Version

    try:
        from hermes_cli import __version__ as _hv
    except ImportError:
        # Hermes 包未安装，输出错误提示并退出进程
        print("  ✗ Cannot import Hermes. Is hermes-agent installed?")
        print("    Install: pip install hermes-agent")
        sys.exit(1)

    _current = Version(_hv)
    _min_v = Version(_MIN_HERMES_VERSION)
    _max_v = Version(_MAX_HERMES_VERSION)

    if not (_min_v <= _current < _max_v):
        # 当前 Hermes 版本不在兼容范围内，打印版本不匹配信息并退出
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

# ── Server ────────────────────────────────────────────────────────────────
import secrets
import webbrowser

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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


def _sync_b2b_skills():
    """启动时从 GitHub 拉取最新 B2B skills 到 Hermes。

    每次启动都会检查并更新，确保 skills 始终与 GitHub main 分支同步。
    如果 GitHub 不可达（离线/网络故障），降级为本地 hash 比对同步。
    """
    from trade.post_install import update_skills
    try:
        update_skills()
    except Exception as _e:
        # GitHub 不可达时降级为本地同步
        print(f"  GitHub skills update failed ({_e}), falling back to local sync")

        _project_skills = Path(__file__).parent / "skills"
        if not _project_skills.is_dir():
            # 项目 skills 目录不存在，无法进行本地同步
            return

        _hermes_skills = get_hermes_home() / "skills"
        _hermes_skills.mkdir(parents=True, exist_ok=True)

        _synced = 0
        for _skill_dir in sorted(_project_skills.iterdir()):
            if not _skill_dir.is_dir() or not _skill_dir.name.startswith("b2b-"):
                # 跳过非目录项以及非 b2b 前缀的技能目录
                continue
            _src = _skill_dir / "SKILL.md"
            if not _src.is_file():
                # 该技能目录中没有 SKILL.md 文件，跳过
                continue
            _dst_dir = _hermes_skills / _skill_dir.name
            _dst = _dst_dir / "SKILL.md"
            _src_hash = hashlib.sha256(_src.read_bytes()).hexdigest()
            if _dst.is_file():
                # 目标文件已存在，比对 hash 是否相同以决定是否需要更新
                _dst_hash = hashlib.sha256(_dst.read_bytes()).hexdigest()
                if _src_hash == _dst_hash:
                    # hash 一致，该技能无需更新
                    continue
            _dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_src, _dst)
            _synced += 1
            print(f"  ↻ Updated skill: {_skill_dir.name}")

        if _synced > 0:
            # 有技能被更新，输出更新数量
            print(f"  Skills synced: {_synced} updated")
        else:
            # 所有技能已是最新，无需更新
            print("  Skills: up-to-date")

_sync_b2b_skills()

# ── Database initialization ──────────────────────────────────────────────────
# Must run before any API endpoint that touches the DB.
# On fresh install: creates all tables.
# On v0→v1 upgrade: migrates schema + creates default company.
from trade.database import init_db as _init_db

_db_path = _init_db()

# ── License check ───────────────────────────────────────────────────────────
from trade.license import check_license as _check_license

_lic_ok, _lic_msg = _check_license()
if not _lic_ok:
    print(f"  ⚠️  {_lic_msg}")
print(f"  Database: {_db_path}")

# ── Inject session token before mounting routes ───────────────────────────
from trade.api.deps import set_session_token

set_session_token(_SESSION_TOKEN)

# ── License endpoints (无需 session token) ────────────────────────────────
from trade.api.license import router as license_router

app.include_router(license_router, prefix="/api/trade")

# ── Mount Trade API ───────────────────────────────────────────────────────
from trade.api import router as trade_router

app.include_router(trade_router, prefix="/api/trade")

# ── Serve Trade Chat SPA ──────────────────────────────────────────────────
_TRADE_CHAT_HTML = Path(__file__).parent / "static" / "trade_chat.html"

@app.get("/trade", response_class=HTMLResponse, include_in_schema=False)
async def trade_chat_ui():
    """Serve the B2B chat interface with session token injected."""
    if not _TRADE_CHAT_HTML.exists():
        # HTML 文件缺失时，返回 404 页面而非抛出异常
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
    """检查是否有 Hermes Gateway 进程在运行（跨平台）。"""
    try:
        if os.name == "nt":
            # Windows: 直接检查端口 8642 是否在监听（tasklist 无法精确匹配命令行参数）
            import socket as _sock
            _s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
            try:
                _s.settimeout(1)
                _s.connect(("127.0.0.1", 8642))
                _s.close()
                return True
            except OSError:
                # 端口不可达 → gateway 未运行
                return False
            finally:
                # 确保 socket 资源被释放，即使 try 或 except 中已经 close
                _s.close()
        else:
            # Unix: pgrep -f 匹配 hermes gateway 进程名及命令行参数
            result = _sp.run(
                ["pgrep", "-f", "hermes.*gateway"],
                capture_output=True, text=True, timeout=3,
            )
            # pgrep 返回码为 0 表示找到匹配进程，stdout 非空说明有进程 ID
            return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        # 任何异常（如超时、pgrep 不存在等）都视为 Gateway 未运行
        return False

def _ensure_gateway_running() -> None:
    """如果 Gateway 未运行，启动它。Gateway 独立于 Trade 生命周期，Trade 退出后仍保持运行。"""
    if _is_gateway_running():
        # Gateway 已经在运行，无需重复启动
        print("  Hermes Gateway → running (cron scheduler active)")
        return

    try:
        hermes_bin = shutil.which("hermes") or "hermes"

        kwargs = {
            "stdout": _sp.DEVNULL,
            "stderr": _sp.DEVNULL,
        }
        # Windows 用 CREATE_NEW_PROCESS_GROUP，Unix 用 start_new_session
        # 确保 Gateway 子进程独立于 Trade 生命周期，Trade 退出后 Gateway 仍保持运行
        if os.name == "nt":
            kwargs["creationflags"] = 0x00000200  # CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        _sp.Popen(
            [hermes_bin, "gateway", "run"],
            env={**os.environ, "GATEWAY_ALLOW_ALL_USERS": "true"},
            **kwargs,
        )
        print("  Hermes Gateway → started (cron scheduler active)")
    except Exception as e:
        # Gateway 启动异常不影响 Trade 主进程运行，仅打印警告
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
        # 用户未禁用 Gateway，检查并启动 Hermes Gateway（用于 cron 调度）
        _ensure_gateway_running()

    url = f"http://{args.host}:{args.port}/trade"
    print(f"\n  Foreign Trade Assistant → {url}")
    print(f"  Session token: {_SESSION_TOKEN[:16]}...")
    print()

    if not args.no_browser:
        # 用户未禁用浏览器打开，延迟 1 秒后自动在默认浏览器中打开聊天界面
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")

if __name__ == "__main__":
    main()
