#!/bin/bash
# ==============================================================================
# Foreign Trade Assistant — 一键安装脚本 (macOS / Linux / WSL2)
# ==============================================================================
# 使用方式:
#   curl -fsSL https://raw.githubusercontent.com/chefroger/foreign-trade-assistant/main/scripts/install.sh | bash
#
# 或本地运行:
#   chmod +x install.sh && ./install.sh
#
# 安装流程:
#   1. 检查 Python >= 3.11
#   2. 安装 hermes-agent (chefroger fork)
#   3. 安装 foreign-trade-assistant
#   4. 安装 B2B skills 到 ~/.hermes/skills/
#   5. 初始化 ~/.trade/ 数据目录
# ==============================================================================

set -e

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}→${NC} $*"; }
log_ok()    { echo -e "${GREEN}✓${NC} $*"; }
log_warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
log_err()   { echo -e "${RED}✗${NC} $*"; }
log_step()  { echo -e "\n${BOLD}════════════════════════════════════════${NC}"; echo -e "${BOLD}$*${NC}"; }

echo ""
echo -e "${BOLD}${CYAN}  Foreign Trade Assistant — 安装向导${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: 检查 Python
# ─────────────────────────────────────────────────────────────────────────────
log_step "Step 1/5: 检查 Python 环境"

PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$("$cmd" -c "import sys; print(sys.version_info.major)")
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -gt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -ge 11 ]); then
            PYTHON="$cmd"
            log_ok "Python $ver ($(which "$PYTHON"))"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    log_err "需要 Python >= 3.11，但未找到。"
    echo ""
    echo "  请先安装 Python："
    echo "    macOS:  brew install python@3.12"
    echo "    Ubuntu: sudo apt install python3.12 python3.12-venv"
    echo "    或使用 uv:  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: 检查/安装 hermes-agent (chefroger fork)
# ─────────────────────────────────────────────────────────────────────────────
log_step "Step 2/5: 检查 hermes-agent"

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_OK=false

# 尝试 import hermes_cli
if "$PYTHON" -c "import hermes_cli" 2>/dev/null; then
    hermes_ver=$("$PYTHON" -c "import hermes_cli; print(hermes_cli.__version__)" 2>/dev/null || echo "unknown")
    log_ok "hermes-agent 已安装 (v$hermes_ver)"
    HERMES_OK=true
fi

if [ "$HERMES_OK" = false ]; then
    log_info "正在安装 hermes-agent (chefroger fork)..."
    HERMES_REPO="https://github.com/chefroger/hermes-agent.git"
    HERMES_DIR="$HERMES_HOME/hermes-agent"

    if [ -d "$HERMES_DIR" ]; then
        log_info "更新已有仓库..."
        git -C "$HERMES_DIR" pull --ff-only origin main 2>/dev/null || true
    else
        mkdir -p "$HERMES_DIR"
        git clone --branch main "$HERMES_REPO" "$HERMES_DIR" 2>/dev/null || {
            log_err "无法克隆 hermes-agent。请检查网络连接。"
            log_info "手动安装: git clone $HERMES_REPO ~/.hermes/hermes-agent"
            exit 1
        }
    fi

    cd "$HERMES_DIR"
    "$PYTHON" -m pip install -e "." --quiet 2>&1 | tail -1
    cd - >/dev/null

    if "$PYTHON" -c "import hermes_cli" 2>/dev/null; then
        log_ok "hermes-agent 安装完成"
    else
        log_err "hermes-agent 安装失败"
        exit 1
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: 安装 foreign-trade-assistant
# ─────────────────────────────────────────────────────────────────────────────
log_step "Step 3/5: 安装 Foreign Trade Assistant"

TRADE_REPO="https://github.com/chefroger/foreign-trade-assistant.git"
TRADE_DIR="$HOME/.trade/foreign-trade-assistant"

if [ -d "$TRADE_DIR" ]; then
    log_info "更新已有仓库..."
    git -C "$TRADE_DIR" pull --ff-only origin main 2>/dev/null || true
else
    mkdir -p "$TRADE_DIR"
    git clone --branch main "$TRADE_REPO" "$TRADE_DIR" 2>/dev/null || {
        log_err "无法克隆 foreign-trade-assistant。"
        exit 1
    }
fi

cd "$TRADE_DIR"
"$PYTHON" -m pip install -e "." --quiet 2>&1 | tail -1
cd - >/dev/null

log_ok "Foreign Trade Assistant 安装完成"

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: 安装 B2B skills 到 Hermes
# ─────────────────────────────────────────────────────────────────────────────
log_step "Step 4/5: 安装 B2B skills"

if "$PYTHON" -m trade.post_install 2>/dev/null; then
    log_ok "B2B skills 安装完成"
else
    log_warn "B2B skills 安装可能不完整（已跳过，首次启动时会自动同步）"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: 初始化数据目录
# ─────────────────────────────────────────────────────────────────────────────
log_step "Step 5/5: 初始化数据目录"

TRADE_HOME="${TRADE_HOME:-$HOME/.trade}"
mkdir -p "$TRADE_HOME/data"
mkdir -p "$TRADE_HOME/companies"

# 初始化数据库
"$PYTHON" -c "from trade.database import init_db; init_db()" 2>/dev/null && \
    log_ok "数据库初始化完成 ($TRADE_HOME/data/trade.db)" || \
    log_info "数据库将在首次启动时自动初始化"

# ─────────────────────────────────────────────────────────────────────────────
# 完成
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}══ 安装完成 ══${NC}"
echo ""
echo -e "  启动方式:"
echo -e "    ${BOLD}python server.py${NC}  (在 $TRADE_DIR 目录下)"
echo -e "    或直接运行: ${BOLD}trade${NC}"
echo ""
echo -e "  启动后打开: ${CYAN}http://127.0.0.1:9119/trade${NC}"
echo ""
echo -e "  数据位置:"
echo -e "    用户数据: ${CYAN}$TRADE_HOME/${NC}"
echo -e "    Hermes 配置: ${CYAN}$HERMES_HOME/${NC}"
echo ""
echo -e "  帮助: ${CYAN}python server.py --help${NC}"
echo ""
