# ==============================================================================
# Foreign Trade Assistant — 一键安装脚本 (Windows PowerShell)
# ==============================================================================
# 使用方式:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# 全程使用 venv，不碰系统 Python site-packages。
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  Foreign Trade Assistant — 安装向导" -ForegroundColor Cyan
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: 检查 Python
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "Step 1/5: 检查 Python 环境" -ForegroundColor White

$PythonCmd = $null
foreach ($cmd in @("python3", "python")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        $major = & $cmd -c "import sys; print(sys.version_info.major)" 2>$null
        $minor = & $cmd -c "import sys; print(sys.version_info.minor)" 2>$null
        if ([int]$major -gt 3 -or ([int]$major -eq 3 -and [int]$minor -ge 11)) {
            $PythonCmd = $cmd
            Write-Host "  ✓ Python $ver ($(& $PythonCmd -c "import sys; print(sys.executable)"))" -ForegroundColor Green
            break
        }
    } catch {}
}

if (-not $PythonCmd) {
    Write-Host "  ✗ 需要 Python >= 3.11，但未找到。" -ForegroundColor Red
    Write-Host ""
    Write-Host "  请先安装 Python："
    Write-Host "    winget install Python.Python.3.12"
    Write-Host "    或从 https://www.python.org/downloads/ 下载"
    exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# 创建 venv
# ─────────────────────────────────────────────────────────────────────────────
$TradeHome = if ($env:TRADE_HOME) { $env:TRADE_HOME } else { "$env:LOCALAPPDATA\trade" }
$VenvDir = "$TradeHome\venv"
if (-not (Test-Path "$VenvDir\Scripts\python.exe")) {
    Write-Host "  → 创建虚拟环境..."
    & $PythonCmd -m venv $VenvDir
}
$PipCmd = "$VenvDir\Scripts\pip.exe"
$PyCmd  = "$VenvDir\Scripts\python.exe"
Write-Host "  ✓ 虚拟环境就绪 ($VenvDir)" -ForegroundColor Green

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: 安装 hermes-agent
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Step 2/5: 安装 hermes-agent" -ForegroundColor White

$HermesHome = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { "$env:LOCALAPPDATA\hermes" }

try {
    & $PyCmd -c "import hermes_cli" 2>$null
    $hermesVer = & $PyCmd -c "import hermes_cli; print(hermes_cli.__version__)" 2>$null
    Write-Host "  ✓ hermes-agent 已安装 (v$hermesVer)" -ForegroundColor Green
} catch {
    Write-Host "  → 正在安装 hermes-agent ..." -ForegroundColor Cyan

    $HermesRepo = "https://github.com/NousResearch/hermes-agent.git"
    $HermesDir = "$HermesHome\hermes-agent"

    if (Test-Path $HermesDir) {
        Write-Host "  → 更新已有仓库..." -ForegroundColor Cyan
        git -C $HermesDir pull --ff-only origin main 2>$null
    } else {
        New-Item -ItemType Directory -Path $HermesDir -Force | Out-Null
        git clone --branch main $HermesRepo $HermesDir 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  ✗ 无法克隆 hermes-agent。请检查网络连接和 Git 是否安装。" -ForegroundColor Red
            exit 1
        }
    }

    Push-Location $HermesDir
    & $PipCmd install -e "." --quiet 2>&1 | Select-Object -Last 1
    Pop-Location

    try {
        & $PyCmd -c "import hermes_cli"
        Write-Host "  ✓ hermes-agent 安装完成" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ hermes-agent 安装失败" -ForegroundColor Red
        exit 1
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: 安装 foreign-trade-assistant
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Step 3/5: 安装 Foreign Trade Assistant" -ForegroundColor White

$TradeRepo = "https://github.com/chefroger/foreign-trade-assistant.git"
$TradeDir = "$TradeHome\foreign-trade-assistant"

if (Test-Path $TradeDir) {
    Write-Host "  → 更新已有仓库..." -ForegroundColor Cyan
    git -C $TradeDir pull --ff-only origin main 2>$null
} else {
    New-Item -ItemType Directory -Path $TradeDir -Force | Out-Null
    git clone --branch main $TradeRepo $TradeDir 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ 无法克隆 foreign-trade-assistant。" -ForegroundColor Red
        exit 1
    }
}

Push-Location $TradeDir
# 装依赖 + trade 自身
& $PipCmd install -r requirements.txt --quiet
& $PipCmd install -e "." --no-deps --quiet
Pop-Location

Write-Host "  ✓ Foreign Trade Assistant 安装完成" -ForegroundColor Green

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: 安装 B2B skills
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Step 4/5: 安装 B2B skills" -ForegroundColor White

try {
    & $PyCmd -m trade.post_install install 2>$null
    Write-Host "  ✓ B2B skills 安装完成" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ B2B skills 安装可能不完整（首次启动时会自动同步）" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: 初始化数据目录
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Step 5/5: 初始化数据目录" -ForegroundColor White

$DataDir = "$TradeHome\data"
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
New-Item -ItemType Directory -Path "$TradeHome\companies" -Force | Out-Null

try {
    & $PyCmd -c "from trade.database import init_db; init_db()" 2>$null
    Write-Host "  ✓ 数据库初始化完成 ($DataDir\trade.db)" -ForegroundColor Green
} catch {
    Write-Host "  → 数据库将在首次启动时自动初始化" -ForegroundColor Cyan
}

# ─────────────────────────────────────────────────────────────────────────────
# 导出 trade 命令
# ─────────────────────────────────────────────────────────────────────────────
$LocalBin = "$env:LOCALAPPDATA\local\bin"
New-Item -ItemType Directory -Path $LocalBin -Force | Out-Null

@"
@echo off
set HERMES_HOME=$HermesHome
"$PyCmd" "$TradeDir\server.py" %*
"@ | Out-File -FilePath "$LocalBin\trade.cmd" -Encoding ASCII

# 检测 PATH 中是否已包含 $LocalBin
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($currentPath -notlike "*$LocalBin*") {
    [Environment]::SetEnvironmentVariable("PATH", "$LocalBin;$currentPath", "User")
    Write-Host "  ✓ 已将 trade 命令加入 PATH（新终端生效）" -ForegroundColor Green
}

Write-Host ""
Write-Host "══ 安装完成 ══" -ForegroundColor Green
Write-Host ""
Write-Host "  启动方式:"
Write-Host "    新终端: trade"
Write-Host "    或: $PyCmd $TradeDir\server.py"
Write-Host ""
Write-Host "  启动后打开: http://127.0.0.1:9119/trade"
Write-Host ""
Write-Host "  数据位置:"
Write-Host "    用户数据: $TradeHome\"
Write-Host "    Hermes 配置: $HermesHome\"
Write-Host ""
