# ==============================================================================
# Foreign Trade Assistant — 一键安装脚本 (Windows PowerShell)
# ==============================================================================
# 使用方式:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# 或从 GitHub:
#   powershell -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/chefroger/foreign-trade-assistant/main/scripts/install.ps1' -OutFile install.ps1; .\install.ps1"
#
# 安装流程:
#   1. 检查 Python >= 3.11
#   2. 安装 hermes-agent (chefroger fork)
#   3. 安装 foreign-trade-assistant
#   4. 安装 B2B skills
#   5. 初始化数据目录
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
# Step 2: 检查/安装 hermes-agent
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Step 2/5: 检查 hermes-agent" -ForegroundColor White

$HermesHome = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { "$env:LOCALAPPDATA\hermes" }
$HermesOk = $false

try {
    & $PythonCmd -c "import hermes_cli" 2>$null
    $hermesVer = & $PythonCmd -c "import hermes_cli; print(hermes_cli.__version__)" 2>$null
    Write-Host "  ✓ hermes-agent 已安装 (v$hermesVer)" -ForegroundColor Green
    $HermesOk = $true
} catch {}

if (-not $HermesOk) {
    Write-Host "  → 正在安装 hermes-agent (chefroger fork)..." -ForegroundColor Cyan

    $HermesRepo = "https://github.com/chefroger/hermes-agent.git"
    $HermesDir = "$HermesHome\hermes-agent"

    if (Test-Path $HermesDir) {
        Write-Host "  → 更新已有仓库..." -ForegroundColor Cyan
        git -C $HermesDir pull --ff-only origin main 2>$null
    } else {
        New-Item -ItemType Directory -Path $HermesDir -Force | Out-Null
        git clone --branch main $HermesRepo $HermesDir 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  ✗ 无法克隆 hermes-agent。请检查网络连接和 Git 是否安装。" -ForegroundColor Red
            Write-Host "    手动安装: git clone $HermesRepo $HermesDir" -ForegroundColor Yellow
            exit 1
        }
    }

    Push-Location $HermesDir
    & $PythonCmd -m pip install -e "." --quiet 2>&1 | Select-Object -Last 1
    Pop-Location

    try {
        & $PythonCmd -c "import hermes_cli"
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

$TradeHome = if ($env:TRADE_HOME) { $env:TRADE_HOME } else { "$env:LOCALAPPDATA\trade" }
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
# --no-deps 跳过依赖安装，因为 hermes-agent 已在 Step 2 通过 editable install 装好
& $PythonCmd -m pip install -e "." --no-deps --quiet 2>&1 | Select-Object -Last 1
Pop-Location

Write-Host "  ✓ Foreign Trade Assistant 安装完成" -ForegroundColor Green

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: 安装 B2B skills
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Step 4/5: 安装 B2B skills" -ForegroundColor White

try {
    & $PythonCmd -m trade.post_install 2>$null
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
    & $PythonCmd -c "from trade.database import init_db; init_db()" 2>$null
    Write-Host "  ✓ 数据库初始化完成 ($DataDir\trade.db)" -ForegroundColor Green
} catch {
    Write-Host "  → 数据库将在首次启动时自动初始化" -ForegroundColor Cyan
}

# ─────────────────────────────────────────────────────────────────────────────
# 完成
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "══ 安装完成 ══" -ForegroundColor Green
Write-Host ""
Write-Host "  启动方式:"
Write-Host "    cd $TradeDir"
Write-Host "    python server.py"
Write-Host ""
Write-Host "  启动后打开: http://127.0.0.1:9119/trade"
Write-Host ""
Write-Host "  数据位置:"
Write-Host "    用户数据: $TradeHome\"
Write-Host "    Hermes 配置: $HermesHome\"
Write-Host ""
