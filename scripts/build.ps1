# ==============================================================================
# Foreign Trade Assistant — Windows Build Script
# ==============================================================================
# 使用 PyInstaller 打包为独立 .exe
#
# 运行:
#   powershell -ExecutionPolicy Bypass -File scripts/build.ps1
#
# 前置:
#   pip install pyinstaller
#   pip install -e .
# ==============================================================================

$ErrorActionPreference = "Stop"
$ROOT = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $ROOT

Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Foreign Trade Assistant — Build" -ForegroundColor White
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check PyInstaller
try {
    python -c "import PyInstaller" 2>$null
} catch {
    Write-Host "→ 安装 PyInstaller..."
    pip install pyinstaller --quiet
}

# Clean
Write-Host "→ 清理旧构建..."
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }

# Build (Windows: no .app, just .exe in dist/)
Write-Host "→ 开始打包..."
python -m PyInstaller pyinstaller.spec --noconfirm --clean 2>&1 | Select-Object -Last 10

if (Test-Path "dist/Foreign Trade Assistant.exe") {
    $size = (Get-Item "dist/Foreign Trade Assistant.exe").Length / 1MB
    Write-Host ""
    Write-Host "══ 构建完成 ══" -ForegroundColor Green
    Write-Host "  位置: $ROOT\dist\Foreign Trade Assistant.exe" -ForegroundColor White
    Write-Host "  大小: $([math]::Round($size, 1)) MB" -ForegroundColor White
    Write-Host ""
    Write-Host "  双击 Foreign Trade Assistant.exe 启动" -ForegroundColor Cyan
} else {
    Write-Host "✗ 构建失败" -ForegroundColor Red
    exit 1
}
