#!/bin/bash
# ==============================================================================
# Foreign Trade Assistant — 构建打包脚本
# ==============================================================================
# 使用 PyInstaller 打包为独立可执行文件。
#
# macOS: 生成 .app 应用包
#   ./scripts/build.sh
#
# Windows: 生成 .exe
#   powershell -File scripts/build.ps1
#
# 前置要求:
#   pip install pyinstaller
#   pip install -e .
# ==============================================================================

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "════════════════════════════════════════"
echo "  Foreign Trade Assistant — Build"
echo "════════════════════════════════════════"
echo ""

# ── Check PyInstaller ──
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "→ 安装 PyInstaller..."
    pip install pyinstaller --quiet
fi

# ── Clean previous builds ──
echo "→ 清理旧构建..."
rm -rf build dist *.spec.bak

# ── Build ──
echo "→ 开始打包..."
python -m PyInstaller pyinstaller.spec --noconfirm --clean 2>&1 | tail -10

# ── Verify ──
if [ -d "dist/Foreign Trade Assistant.app" ]; then
    APP_SIZE=$(du -sh "dist/Foreign Trade Assistant.app" | cut -f1)
    echo ""
    echo "══ 构建完成 ══"
    echo "  位置: $ROOT/dist/Foreign Trade Assistant.app"
    echo "  大小: $APP_SIZE"
    echo ""
    echo "  双击 Foreign Trade Assistant.app 启动"
elif [ -f "dist/Foreign Trade Assistant" ]; then
    EXE_SIZE=$(du -sh "dist/Foreign Trade Assistant" | cut -f1)
    echo ""
    echo "══ 构建完成 ══"
    echo "  位置: $ROOT/dist/Foreign Trade Assistant"
    echo "  大小: $EXE_SIZE"
    echo ""
    echo "  ./dist/Foreign\ Trade\ Assistant 启动（或双击）"
else
    echo "✗ 构建失败，请检查上方错误信息"
    exit 1
fi
