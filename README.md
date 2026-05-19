# Foreign Trade Assistant

[![Test](https://github.com/chefroger/foreign-trade-assistant/actions/workflows/test.yml/badge.svg)](https://github.com/chefroger/foreign-trade-assistant/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)

外贸公司的 AI 销售助手 — 覆盖「引流 → 转化」全链路的智能销售系统。

基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent)，
为外贸业务员提供 B2B 平台诊断、社媒获客、客户背调、开发信生成、报价谈判、文档分析、
定时任务自动化等 14 项专业能力。

---

## 空白电脑从头安装

以下步骤适用于 **macOS / Linux / WSL2**。Windows 原生安装见下方。

### 方式一：一键安装（推荐）

```bash
curl -fsSL https://raw.githubusercontent.com/chefroger/foreign-trade-assistant/main/scripts/install.sh | bash
```

脚本会自动完成：
1. 检查 Python >= 3.11
2. 安装 hermes-agent
3. 安装 foreign-trade-assistant
4. 安装 14 个 B2B skills 到 Hermes
5. 初始化数据库和数据目录

### 方式二：手动安装

#### 前置条件

| 软件 | 版本 | 安装方式 |
|------|------|---------|
| Python | >= 3.11 | `brew install python@3.12` (macOS) 或 `apt install python3.12` (Ubuntu) |
| Git | 任意 | 系统自带 或 `apt install git` |
| LLM API Key | — | 自备（OpenAI / Anthropic / DeepSeek 等），配置在 `~/.hermes/.env` |

#### 步骤

```bash
# 1. 安装 hermes-agent
git clone --branch main https://github.com/NousResearch/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
pip install -e "."

# 2. 配置 Hermes（选择 LLM 提供商和模型）
hermes setup
# 按提示选择 provider、填入 API Key
# 或手动编辑 ~/.hermes/config.yaml 和 ~/.hermes/.env

# 3. 安装 Foreign Trade Assistant
git clone --branch main https://github.com/chefroger/foreign-trade-assistant.git ~/.trade/foreign-trade-assistant
cd ~/.trade/foreign-trade-assistant
pip install -e "."

# 4. 安装 B2B skills 到 Hermes
install-trade-skills

# 5. 启动
python server.py
# → 浏览器打开 http://127.0.0.1:9119/trade
```

### Windows 原生安装

```powershell
# PowerShell（以普通用户运行，无需管理员）
# 1. 安装 hermes-agent
git clone --branch main https://github.com/NousResearch/hermes-agent.git $env:LOCALAPPDATA\hermes\hermes-agent
cd $env:LOCALAPPDATA\hermes\hermes-agent
pip install -e "."
hermes setup

# 2. 安装 Foreign Trade Assistant
git clone --branch main https://github.com/chefroger/foreign-trade-assistant.git $env:LOCALAPPDATA\trade\foreign-trade-assistant
cd $env:LOCALAPPDATA\trade\foreign-trade-assistant
pip install -e "."
install-trade-skills

# 3. 启动
python server.py
```

---

## 启动

```bash
cd ~/.trade/foreign-trade-assistant   # 或项目目录
python server.py                       # 默认 http://127.0.0.1:9119/trade
python server.py --port 8080           # 自定义端口
python server.py --no-browser          # 不自动打开浏览器
```

## 打包为独立应用（无需命令行）

```bash
pip install pyinstaller
./scripts/build.sh          # macOS → dist/Foreign Trade Assistant.app
# Windows:
powershell -File scripts/build.ps1  # → dist/Foreign Trade Assistant.exe
```

打包后可双击启动，不依赖终端。

---

## 数据存储位置

| 数据 | macOS / Linux | Windows |
|------|--------------|---------|
| 数据库 | `~/.trade/data/trade.db` | `%LOCALAPPDATA%\trade\data\trade.db` |
| 公司数据 | `~/.trade/companies/{slug}/` | `%LOCALAPPDATA%\trade\companies\{slug}\` |
| 桌面工作目录 | `~/Desktop/{公司名}/` | `%USERPROFILE%\Desktop\{公司名}\` |
| Skills | `~/.hermes/skills/b2b-*/` | `%LOCALAPPDATA%\hermes\skills\b2b-*\` |
| Hermes 配置 | `~/.hermes/config.yaml` | `%LOCALAPPDATA%\hermes\config.yaml` |
| LLM API Key | `~/.hermes/.env` | `%LOCALAPPDATA%\hermes\.env` |

所有用户数据存储在本地，不上传任何服务器（除调用 LLM API 外）。

---

## ⚠️ 安全部署说明

Foreign Trade Assistant 在 `HERMES_YOLO_MODE=true` 下运行——AI Agent 执行工具（读写文件、终端命令等）
**无需人工审批**。这是必须的，因为目标用户（外贸业务员）不具备判断 Agent 工具调用的技术能力。

### 因此请务必：

1. **仅在内网或本机使用**：不要将服务暴露在公网上
2. **防火墙保护**：确保 `127.0.0.1:9119` 不被外部访问
3. **API Key 安全**：`~/.hermes/.env` 中的 LLM API Key 不要分享
4. **定期备份**：`~/.trade/` 目录和桌面工作目录中的重要文件

### YOLO 模式说明

```
启动时输出：
  ⚠️  HERMES_YOLO_MODE enabled — 工具审批已跳过
     如需更高安全隔离，仅限受控内网环境使用
```

这是设计决定，不是配置疏忽。如果需要工具审批流程，请使用 Hermes 原生的交互模式。

---

## 功能概览

| 功能 | 入口 | 说明 |
|------|------|------|
| 今日简报 | 侧边栏 → 工作台 | Agent 对话，自动加载近期上下文 |
| 客户开发 | 侧边栏 → 获客引流 | 分析客户信息、生成开发信和跟进序列 |
| 平台诊断 | 侧边栏 → 获客引流 | 分析阿里国际站/中国制造网产品页面 |
| 社媒营销 | 侧边栏 → 获客引流 | 生成 Facebook/Instagram/TikTok/YouTube 内容日历 |
| LinkedIn | 侧边栏 → 获客引流 | Profile 优化、内容策略、InMail 模板 |
| 海关数据 | 侧边栏 → 获客引流 | 分析进出口数据、筛选采购商 |
| 客户管理 | 侧边栏 → 销售转化 | 客户表格（A/B/C 分级）、详情面板、文档库关联 |
| 文档库 | 侧边栏 → 销售转化 | 按目录读取本地文档，Agent 自动分析 |
| 文档生成 | 侧边栏 → 销售转化 | 生成 PPTX/DOCX/XLSX 专业商务文档 |
| 客户背调 | 侧边栏 → 工具 | 6 层验证：WHOIS + 邮箱验证 + 制裁名单 + 技术栈 + LinkedIn（Hermes 浏览器） + 邮箱注册检测 |
| 定时任务 | 侧边栏 → 工具 | 7 个工作日自动化任务（早安简报/开发信/社媒等） |
| 数据目录 | 侧边栏 → 工具 | 浏览 `~/.trade/` 目录结构和文件 |
| 对话记录 | 侧边栏 → 历史 | 查看/搜索/删除历史对话 |

---

## 项目结构

```
trade/                     B2B 业务层
├── api/                   FastAPI 路由（按业务域拆分）
│   ├── chat.py              AI 对话（sync + SSE stream）
│   ├── companies.py         公司管理
│   ├── libraries.py         文档库管理
│   ├── customers.py         客户管理
│   ├── conversations.py     对话记录
│   ├── memory.py            Hindsight 记忆 + LLM 提供商
│   ├── onboarding.py        首次引导
│   ├── deps.py              共享依赖 + session token 校验
│   └── models.py             Pydantic 请求/响应模型
├── osint/                 客户背调模块（6 层检测）
│   ├── whois.py             域名 WHOIS
│   ├── email_verify.py      企业邮箱验证
│   ├── sanctions.py         制裁名单筛查
│   ├── tech_stack.py        技术栈检测
│   ├── linkedin_verify.py   LinkedIn 验证（browser_navigate 指令生成）
│   ├── scoring.py           风险评分
│   └── orchestrator.py      编排器
├── database.py             SQLite 连接 + schema + 迁移
├── company.py              公司 CRUD + 桌面工作目录
├── library.py              文档库 CRUD
├── customer.py             客户 CRUD
├── chat_memory.py          对话记录 + Hindsight 桥接
├── memory.py               Hindsight 客户端
├── helpers.py              Provider 检查 + Agent 工厂 + Prompt 构建
├── prompt.py               System prompt 模板
├── prompts.py              Prompt 文件加载器（mtime 缓存）
├── skill_router.py         Skill 匹配引擎 + 注入
├── skill_registry.py       14 个 skill 注册表（纯数据）
├── onboarding.py           首次引导逻辑
├── email_intel.py          holehe 邮箱平台检测
└── post_install.py         Skills 安装到 Hermes

skills/                     14 个 B2B skills（安装到 ~/.hermes/skills/）
tests/                      126 个测试（database/business/api/osint/smoke）
static/trade_chat.html      Chat SPA 前端
scripts/
├── install.sh              一键安装脚本（macOS/Linux）
├── install.ps1             一键安装脚本（Windows）
├── build.sh                打包构建（macOS）
├── build.ps1               打包构建（Windows）
├── install_prereqs.sh      前置依赖安装（macOS/Linux）
└── install_prereqs.ps1     前置依赖安装（Windows）
pyinstaller.spec            PyInstaller 打包配置
pyproject.toml              pip 安装配置
server.py                   FastAPI 入口
```

---

## 开发

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v       # 运行 126 个测试
python -m trade.database          # 初始化/检查数据库
```

## 文档

- [项目需求文档](项目需求文档.md)
- [业务概览](业务概览.md)
- [外贸业务知识库](外贸业务知识库.md)
- [外贸业务方法总结](外贸业务方法总结.md)
- [Trade 数据目录结构设计](Trade数据目录结构设计.md)
- [COMPATIBILITY.md](COMPATIBILITY.md) — Hermes 版本兼容性记录
