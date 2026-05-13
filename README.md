# Foreign Trade Assistant

B2B document Q&A for trade and manufacturing sales teams.  
Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent).

## Architecture

```
Foreign Trade Assistant (独立项目)
├── trade/                  B2B 业务层
│   ├── company.py           多公司注册与配置
│   ├── library.py           文档库（按公司隔离）
│   ├── customer.py          客户管理（按公司隔离）
│   └── chat_memory.py       对话历史（按公司隔离）
├── skills/                  Hermes-compatible skills (安装到 ~/.hermes/skills/)
├── .trade-template/         公司数据目录模板（安装到 ~/.trade/）
├── static/trade_chat.html   多公司聊天 SPA
└── server.py               FastAPI 入口

        ↓ import

Hermes Agent (pip install hermes-agent)
├── AIAgent                  对话引擎
├── Tools                    工具执行
├── Memory (cognee)          知识图谱记忆
└── Skills                   技能系统
```

## Quick Start

```bash
# 1. Install Hermes Agent
git clone https://github.com/chefroger/hermes-agent.git
cd hermes-agent && pip install -e ".[all]" && cd ..

# 2. Install Foreign Trade Assistant
cd "Foreign Trade Assistant"
pip install -e .

# 3. Install B2B skills into Hermes (copies skills/ → ~/.hermes/skills/)
install-trade-skills

# 4. Initialize database
python -m trade.database

# 5. Start
python server.py
# → http://127.0.0.1:9119/trade
```

**Skills 安装说明**：
- `install-trade-skills` 是项目 console script，安装时自动注册
- 将 `skills/b2b-*/` 下的 11 个 B2B skills 复制到 `~/.hermes/skills/b2b-*/`
- Hermes 运行时从 `~/.hermes/skills/` 发现并加载这些 skills
- 手动单独运行：`python -m trade.post_install`

**运行时数据位置**：
- Skills：`~/.hermes/skills/`（macOS/Linux）或 `%LOCALAPPDATA%\hermes\skills\`（Windows）
- 用户数据：`~/.trade/`（macOS/Linux）或 `%LOCALAPPDATA%\trade\`（Windows）

## Environment

Trade reads Hermes config from `~/.hermes/config.yaml` and `~/.hermes/.env`.  
Run `hermes setup` (or `trade setup`) to configure LLM provider and API keys.

## Project Structure

```
trade/
├── prompt.py          System prompt for B2B agent behavior
├── helpers.py         Provider check + agent kwarg construction
├── database.py        SQLite connection + schema (data/trade.db)
├── library.py         Document library CRUD
├── customer.py        Customer CRUD + library associations
├── chat_memory.py     Conversation log + Hindsight bridge
├── memory.py          Hindsight long-term memory client
└── api.py             FastAPI router (/api/trade/*)

static/
└── trade_chat.html    B2B chat SPA (sidebar + streaming chat)

skills/
├── b2b-document/           B2B 文档分析 — 报价单/规格书/合同/检验报告
├── b2b-platform/           B2B平台诊断 — 阿里国际站/中国制造网店铺优化
├── b2b-social-media/       社媒内容策略 — Facebook/Instagram/TikTok/YouTube
├── b2b-linkedin-marketing/ LinkedIn营销 — Profile优化/开发信/内容策略
├── b2b-lead-generation/    客户开发 — 分类/分析/冷邮件/跟进/报价/谈判
├── b2b-customs-data/        海关数据挖掘 — 进出口数据/采购商分析/广交会
├── b2b-onboarding/          新公司部署 — 全套营销启动方案
├── b2b-customer-mgmt/       客户管理 — 生命周期/报价单/订单/关系维护
├── b2b-daily-automation/    每日自动化 — 早安简报/定时发布/晚间报告
├── b2b-data-directory/      标准化数据目录 — ~/.trade/ 目录结构初始化
└── b2b-doc-generation/      业务文档生成 — PPTX/DOCX/XLSX 专业商务文档

.trade-template/              安装后 ~/.trade/ 的目录骨架模板
├── config.yaml                配置文件
├── companies/                 公司目录（每公司一个子目录）
├── prompts/                  系统提示词备份
└── skills/                   Trade专属技能（可覆盖Hermes内置）
```

## API

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/trade/libraries` | List / Create document libraries |
| GET/PUT/DELETE | `/api/trade/libraries/{id}` | Get / Update / Delete library |
| GET/POST | `/api/trade/customers` | List / Create customers |
| GET/PUT/DELETE | `/api/trade/customers/{id}` | Get / Update / Delete customer |
| POST/DELETE | `/api/trade/customers/{id}/libraries/{id}` | Link / Unlink |
| POST | `/api/trade/chat` | Send query to AI Agent |
| POST | `/api/trade/chat/stream` | Streaming chat with SSE tool progress |
| GET/POST | `/api/trade/conversations` | List / Save conversations |
| GET | `/api/trade/memory/status` | Hindsight memory status |
| GET | `/api/trade/memory/recall` | Search long-term memory |
| GET | `/api/trade/models/providers` | Available LLM providers |

## Skills

全部14个skills均为行业通用设计，适用于任何B2B外贸行业。

| Skill | 功能 | 核心场景 |
|-------|------|---------|
| **b2b-document** | B2B 文档分析 | 分析报价单、产品规格书、合同、检验报告中的条款和数据 |
| **b2b-platform** | B2B平台诊断与优化 | 阿里国际站、中国制造网等平台的产品分析、关键词优化、店铺诊断 |
| **b2b-social-media** | 社媒内容策略 | Facebook、Instagram、TikTok、YouTube 多平台内容日历、竞争对手分析 |
| **b2b-linkedin-marketing** | LinkedIn营销 | Profile优化、Content Strategy、开发信模板、行业群组开发 |
| **b2b-lead-generation** | 客户开发与管理 | 客户分类分级、Account IQ分析、冷邮件序列、跟进策略、报价谈判 |
| **b2b-customs-data** | 海关数据挖掘 | 进出口海关数据、进口商筛选、贸易模式分析、广交会采购商分析 |
| **b2b-onboarding** | 新公司营销部署 | 公司介绍、产品资料、竞争对手对比、定价策略的全套启动方案 |
| **b2b-customer-mgmt** | 客户全生命周期管理 | 报价单模板、订单跟单流程、客户满意度追踪、复购激活 |
| **b2b-daily-automation** | 每日自动化任务 | 早安简报、社媒定时发布、客户询盘处理、晚间总结报告 |
| **b2b-data-directory** | 标准化数据目录 | `~/.trade/` 目录结构初始化、公司/客户/文档库文件模板 |
| **b2b-doc-generation** | 专业业务文档生成 | PPTX提案/DOCX合同/XLSX报价单，附格式化规范和验证流程 |
| **b2b-osint** | OSINT 客户背调 | WHOIS 域名年龄 + 企业邮箱验证 + 制裁名单筛查 + LinkedIn 交叉验证 |
| **chat-memory** | 对话长期记忆 | 历史查询工具，按时间范围查询 DB，支持 Hindsight 向量检索 |
| **b2b-email-intel** | 邮箱背景调查 | 120+平台注册检测、社交档案提取、真实性评估 |

每个skill均可独立使用，也可组合形成完整的外贸业务工作流。

## Runtime Data & Skills Locations

Foreign Trade Assistant uses two separate runtime directories:

### Skills Location — `~/.hermes/skills/`

> Installed by `install-trade-skills` from `skills/` in the project repository.

| 平台 | Skills 运行时路径 |
|------|----------------|
| macOS / Linux / WSL2 | `~/.hermes/skills/` |
| Windows native | `%LOCALAPPDATA%\hermes\skills\` |

安装后 Skills 结构：
```
~/.hermes/skills/
├── b2b-document/           # B2B 文档分析
├── b2b-platform/           # B2B平台诊断
├── b2b-social-media/       # 社媒内容策略
├── b2b-linkedin-marketing/ # LinkedIn营销
├── b2b-lead-generation/    # 客户开发
├── b2b-customs-data/       # 海关数据
├── b2b-onboarding/         # 新公司部署
├── b2b-customer-mgmt/      # 客户管理
├── b2b-daily-automation/   # 每日自动化
├── b2b-data-directory/     # 数据目录
├── b2b-doc-generation/      # 文档生成
└── b2b-email-intel/        # 邮箱背景调查
```

Hermes 通过 `skills_list()` / `skill_view()` 工具发现和加载这些 skills，与 Hermes 内置 skills 完全兼容。

### User Data Location — `~/.trade/`

> 用户公司和客户数据，安装后由 `install-trade-skills` 从 `.trade-template/` 复制初始化。

| 平台 | 用户数据路径 |
|------|------------|
| macOS / Linux / WSL2 | `~/.trade/` |
| Windows native | `%LOCALAPPDATA%\trade\` |

```
~/.trade/                        # 或 %LOCALAPPDATA%\trade\ (Windows)
├── config.yaml                  # 当前激活公司等配置
├── companies/                   # 公司目录（通过 trade init-company 创建）
│   └── {company-slug}/
│       ├── company-profile.md  # [必需] 公司介绍
│       ├── products.md         # [必需] 产品目录
│       ├── business-scope.md   # [必需] 业务范围
│       ├── agent-identity.md   # [必需] Agent 角色定义
│       ├── competitors.md      # [可选] 同行分析
│       ├── certifications.md   # [可选] 资质认证
│       ├── marketing-strategy.md [可选] 营销策略
│       ├── sales-playbook.md   # [可选] 销售手册
│       ├── libraries/         # 文档库
│       │   └── {lib-slug}/
│       │       ├── index.md
│       │       ├── changelog.md
│       │       ├── metadata.md
│       │       └── extracts/   # 文档分析切片
│       └── clients/          # 客户目录
│           └── {client-slug}/
│               ├── profile.md   # [必需] 客户画像
│               ├── contacts.md  # [必需] 联系人
│               ├── interactions.md [必需] 沟通记录
│               ├── requirements.md [可选] 需求
│               ├── quotes.md    # [可选] 报价历史
│               ├── orders.md   # [可选] 订单
│               └── notes.md    # [可选] 备注
```

### 初始化公司

```bash
trade init-company --name "公司名" --slug "company-slug"
```

### 仓库模板 vs 运行时目录

| | 仓库（`.trade-template/`） | 运行时（`~/.trade/`） |
|--|--------------------------|----------------------|
| 位置 | 项目仓库根目录 | 用户 home 目录 |
| 用途 | 展示目录骨架 + 模板文件 | 实际存储用户数据 |
| 版本控制 | 是（.gitignore 已排除运行时目录） | 否（运行时自动创建） |

> 仓库中 `.trade-template/` 为模板，安装时通过 `install-trade-skills` 复制到用户 home 目录创建 `~/.trade/`。

## Documentation

- [项目需求文档](项目需求文档.md)
- [业务概览](业务概览.md)          ← 开发者视角：模块架构、数据流向、API总表
- [Trade-Hermes 耦合评估](Trade-Hermes耦合评估.md)
- [Trade-Hermes 解耦可行性](Trade-Hermes解耦可行性.md)
- [代码复用评估](代码复用评估.md)
