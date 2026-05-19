# Trade 与 Hermes 解耦 — 可行性评估

> 评估日期：2026-05-11
> 目标：Hermes 作为独立安装包，Trade 通过 API 调用 Hermes 功能，两者独立开发、独立升级

---

## 一、现状：Trade 到底用了 Hermes 的什么

| 能力 | 当前实现方式 | 是否可通过 API 替代 |
|------|-------------|-------------------|
| Agent 问答 | `from run_agent import AIAgent` → `agent.chat(query)` | ❌ Hermes 无 REST chat 端点 |
| Agent 流式问答 | `AIAgent(tool_start_callback=..., tool_complete_callback=...)` | ❌ 同上 |
| LLM 配置读取 | `from hermes_cli.config import load_config` | ❌ 有 /api/config 但只读 |
| Provider 凭据解析 | `from hermes_cli.auth import PROVIDER_REGISTRY` | ❌ |
| 模型列表 | `from hermes_cli.models import name_to_models` | ⚠️ 有 /api/model/info |
| Memory (cognee) | `from plugins.memory import load_memory_provider` | ❌ 内嵌在 Agent 进程中 |
| Web 路由挂载 | `app.include_router(trade_router, prefix="/api/trade")` | ❌ Trade 代码挂在 Hermes 的 FastAPI 实例上 |
| /trade HTML 页面 | `@app.get("/trade")` 在 web_server.py 中 | ❌ |
| CLI 入口 (trade 命令) | `hermes_cli/main.py` 中的 `_cmd_trade_chat` | ❌ |
| 品牌 (banner, skin) | 修改了 `banner.py`, `cli.py`, `skin_engine.py` | ❌ |

**核心问题**：Hermes 没有提供 REST 风格的 Agent 问答端点。它的 chat 能力完全内嵌在交互式 CLI 和 PTY WebSocket 中。

---

## 二、三种解耦方案

### 方案 A：纯 HTTP API 解耦（最独立）

```
┌─────────────────────────────────────────┐
│  Trade (独立项目，独立进程)               │
│  ├── trade_server.py (FastAPI :9119)     │
│  ├── trade_chat.html                     │
│  ├── trade.db (SQLite)                   │
│  └── /api/trade/*                        │
│        │                                 │
│        │ POST /api/chat                  │
│        ▼                                 │
│  ┌─────────────────────────────────┐     │
│  │ Hermes (pip install hermes-agent)│     │
│  │ ├── hermes_chat_api.py (NEW)     │     │
│  │ ├── AIAgent 引擎                 │     │
│  │ ├── Cognee Memory               │     │
│  │ ├── Tools (file_extract, etc.)   │     │
│  │ └── Skills (b2b-document)        │     │
│  └─────────────────────────────────┘     │
└─────────────────────────────────────────┘
```

**需要做的事**：
1. 给 Hermes 添加 `/api/chat` 和 `/api/chat/stream` 两个端点（约 200 行 Python）
2. Trade 的 `sendMsg()` 直接调用 Hermes 的 chat API
3. Cognee 在 Hermes 进程中运行，Trade 不直接操作 memory
4. Trade 只保留自己的 UI + 文档库/客户管理

**优点**：完全独立，HTTP 是通用协议；Hermes 升级不影响 Trade；不同语言都可以调用

**缺点**：需要给 Hermes 项目贡献代码或维护 fork；多一次 HTTP 往返延迟；需要管理两个进程

---

### 方案 B：Python Library 解耦（最实用）

```
┌──────────────────────────────────────────────────┐
│  Trade (独立项目)                                  │
│  ├── trade_server.py (FastAPI :9119)               │
│  ├── trade_chat.html                               │
│  ├── trade.db                                      │
│  ├── /api/trade/libraries → trade/library.py       │
│  ├── /api/trade/customers → trade/customer.py      │
│  └── /api/trade/chat → trade/agent.py              │
│        │ import                                     │
│        ▼                                            │
│  from hermes_agent import AIAgent  ← pip install   │
│  from hermes_agent.config import load_config        │
│  from hermes_agent.plugins.memory import ...        │
│                                                     │
│  Hermes Agent (pip 包，不共享源码)                    │
└──────────────────────────────────────────────────┘
```

**需要做的事**：
1. 从 Hermes 仓库中抽出 `trade/`、`hermes_cli/trade_chat.html` 等 Trade 专属文件到新仓库
2. 从 Hermes 中移除对 Trade 的引用（web_server.py 中的 trade router、main.py 中的 trade 命令等）
3. Trade 通过 `pip install hermes-agent` 依赖 Hermes
4. Trade 在自己的 FastAPI 中启动，不修改 Hermes 源码

**优点**：改动最小；AIAgent 在同一个进程中，无网络开销；Python import 接口天然向后兼容

**缺点**：通过 Python API 耦合（不是 HTTP）；Hermes 大版本升级仍可能影响 Trade；两个 Python 项目的依赖版本需要协调

---

### 方案 C：当前方案改良（最小改动）

保持当前 fork 结构，但规范化侵入点：

```
trade_ai_assistant/
├── trade/                    # 独立业务层
├── hermes_cli/
│   ├── trade_chat.html       # Trade 专属
│   └── web_server_patch.py   # 明确的补丁文件
├── hermes/                   # git submodule，不修改
└── patches/                  # 需要 apply 到 Hermes 的 .patch 文件
```

**优点**：改动最小；一个仓库管理所有内容

**缺点**：依然是 fork 模式；Hermes 升级仍需手动合并；本质上没有解耦

---

## 三、关键判断：推荐方案 B

**理由**：

1. **Hermes 没有 REST chat API** — 方案 A 需要给 Hermes 添加新功能，周期长且需要上游接受
2. **AIAgent 的 Python API 已经足够稳定** — `__init__` 参数和 `chat()` 方法是 Hermes 的核心公开接口，不太会 breaking change
3. **方案 B 是当前架构的自然演进** — Trade 已经在 `trade/api.py` 中通过 `from run_agent import AIAgent` 使用 Hermes，只是共享了源码树。把共享源码树改为 pip 依赖，工作量最小
4. **方案 B 下 Hermes 可以独立升级** — `pip install hermes-agent==0.13.0` 即可升级，Trade 不需要重新构建

---

## 四、方案 B 的实施路线

### Phase 1：分离仓库（1-2 天）

```
新 Trade 仓库结构：
trade-ai-assistant/
├── trade/                    # 从原仓库搬过来
│   ├── prompt.py
│   ├── helpers.py
│   ├── database.py
│   ├── library.py
│   ├── customer.py
│   ├── chat_memory.py
│   ├── memory.py
│   └── api.py
├── static/
│   └── trade_chat.html       # 从 hermes_cli/ 搬过来
├── skills/
│   └── b2b-document/SKILL.md
├── server.py                 # 独立 FastAPI 入口（新建）
├── pyproject.toml            # 依赖 hermes-agent
└── README.md

Hermes 仓库（原仓库，去掉 Trade 专属文件）：
├── trade/                    # 删除
├── hermes_cli/trade_chat.html # 删除
├── hermes_cli/web_server.py  # 还原（去掉 trade router mount）
├── hermes_cli/main.py        # 还原（去掉 _cmd_trade_chat）
├── hermes_cli/config.py      # 还原 memory.provider 默认值
└── ...
```

### Phase 2：独立服务器（1 天）

```python
# server.py — Trade 独立 FastAPI 入口
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from trade.api import router as trade_router

app = FastAPI(title="Trade AI Assistant")
app.include_router(trade_router, prefix="/api/trade")
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9119)
```

Trade 有自己的进程，不依赖 Hermes 的 web_server.py。

### Phase 3：调整 import 路径（1 天）

```python
# trade/helpers.py — 之前
from hermes_cli.config import load_config
from hermes_cli.auth import PROVIDER_REGISTRY

# trade/helpers.py — 之后
from hermes_agent.config import load_config     # 取决于 Hermes 打包后的模块名
from hermes_agent.auth import PROVIDER_REGISTRY

# trade/api.py — 之前
from run_agent import AIAgent

# trade/api.py — 之后
from hermes_agent import AIAgent                # 或 from hermes_agent.run_agent import AIAgent
```

具体 import 路径取决于 Hermes 打包时暴露的公开 API。如果 Hermes 已经有 `pyproject.toml`（当前是 `trade-ai-assistant`），需要确认安装后的包名。

### Phase 4：Cognee 归属（0.5 天）

Cognee 是 Hermes 的 memory provider plugin。在方案 B 中，cognee 跟随 Hermes 安装（`cognee>=1.0.0` 已是 Hermes 的核心依赖）。Trade 不需要直接 import cognee，只需在配置中将 `memory.provider` 设为 `"cognee"`。

---

## 五、方案 B 下 Hermes 升级的影响矩阵

| Hermes 变化 | 对 Trade 的影响 | 修复工作量 |
|------------|---------------|----------|
| AIAgent 新增参数（有默认值） | 无影响 | 0 |
| AIAgent 移除/改名参数 | `helpers.get_agent_kwargs()` 报错 | 改 1 行 |
| `chat()` 改签名 | `agent.chat(query)` 报错 | 改 1 行 |
| config.yaml 新增字段 | 无影响 | 0 |
| config.yaml 重命名键 | `helpers.py` 读不到值 | 改 2 行 |
| PROVIDER_REGISTRY 重构 | `helpers.py` 属性访问报错 | 改 ~10 行 |
| MemoryProvider ABC 改 | cognee plugin 报错 | 加方法（5-10 行） |
| 新增 Hermes 功能 | Trade 自动可用 | 0 |
| Python 版本要求提升 | 需要同步升级 Python | 运维层面 |

**关键认知**：方案 B 下 Trade 对 Hermes 的 Python API 依赖，与当前 Trade 对 Hermes 源码的依赖，具体到代码行是一模一样的。**区别只在于依赖是通过 import 还是通过共享源码树**。import 方案的好处是版本边界清晰，不会在 git merge 时产生冲突。

---

## 六、Trade 独立后能做什么、不能做什么

### 完全独立于 Hermes 的部分
- Web UI（trade_chat.html）
- 文档库/客户 CRUD（trade/library.py, trade/customer.py）
- 对话记录 SQLite（trade/chat_memory.py, trade/database.py）
- 系统提示词（trade/prompt.py）
- B2B 技能定义（skills/b2b-document/SKILL.md）

### 依赖 Hermes Python API 的部分
- Agent 问答（AIAgent）
- LLM 配置（load_config, PROVIDER_REGISTRY）
- 工具执行（file_extract, read_file 等）
- Memory 图谱（cognee, 通过 MemoryProvider）

### 需要从 Hermes 中移出的 Trade 专属文件
- `hermes_cli/trade_chat.html` → Trade 项目的 `static/`
- `hermes_cli/web_server.py` 中的 trade router mount → 删除
- `hermes_cli/main.py` 中的 trade CLI → 删除
- `hermes_cli/config.py` 中 `memory.provider: "cognee"` → 由用户自行配置
- `hermes_cli/banner.py` 中的 Trade branding → 删除（或保留为可选 skin）

---

## 七、结论

**方案 B（pip 依赖）可行，建议执行。**

- Trade 与 Hermes 的耦合本质上是 6 个 Python import，不是架构性耦合
- 把「共享源码树」改为「pip install 依赖」即可实现独立升级
- 当前约 500 行 Trade 代码 + trade_chat.html 需要从 Hermes 仓库中分离
- Hermes 需要移除约 20 行 Trade 侵入代码（web_server 路由挂载、main CLI、config 默认值）
- Cognee 留在 Hermes 侧，Trade 通过配置激活
- 工期估算：3-4 天（分离仓库 + 独立服务器 + import 路径调整 + 测试）
