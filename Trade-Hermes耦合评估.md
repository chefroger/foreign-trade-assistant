# Trade ↔ Hermes 耦合度评估

> 评估日期：2026-05-11
> 目的：评估 Hermes 升级对 Trade AI Assistant 业务层的影响范围和兼容性

---

## 一、依赖全景

### Trade 业务层对 Hermes 的直接依赖

```
trade/api.py ──────────────── import run_agent.AIAgent ─────────────── 核心引擎
trade/api.py ──────────────── import hermes_cli.config.load_config ──── 配置读取
trade/api.py ──────────────── import hermes_cli.auth.PROVIDER_REGISTRY ─ 凭据解析
trade/api.py ──────────────── import hermes_cli.models.name_to_models ── 模型列表
trade/helpers.py ──────────── import hermes_cli.config.load_config ──── 同上
trade/helpers.py ──────────── import hermes_cli.auth.PROVIDER_REGISTRY ─ 同上
trade/memory.py ───────────── import hermes_constants.get_hermes_home ── 路径解析
plugins/memory/cognee/ ────── from agent.memory_manager import ... ──── 共享基础设施
plugins/memory/cognee/ ────── from agent.memory_provider import ... ─── 共享基础设施
plugins/memory/cognee/ ────── from tools.registry import ... ────────── 工具注册
```

**所有依赖都是函数内惰性导入**（`import inside function`），不是模块级导入。这意味着 Hermes 未安装或导入失败时不会阻止 trade 模块加载，只会在调用具体功能时报错。

### Hermes 核心文件中被 Trade 修改的

| 文件 | 改动内容 | 侵入程度 |
|------|---------|---------|
| `hermes_cli/web_server.py` | FastAPI title 改为 Trade AI；mount trade router；serve /trade 页面 | 🔴 高 |
| `hermes_cli/main.py` | `_cmd_trade_chat` 函数；trade 子命令注册 | 🔴 高 |
| `hermes_cli/config.py` | `memory.provider` 默认值改为 cognee；更新注释 | 🟡 中 |
| `hermes_cli/doctor.py` | cognee 诊断逻辑 | 🟡 中 |
| `hermes_cli/banner.py` | Trade AI ASCII 艺术字替换 Hermes logo | 🟢 低 |
| `hermes_cli/skin_engine.py` | 品牌皮肤注册 | 🟢 低 |
| `cli.py` | 启动 ASCII logo 替换 | 🟢 低 |
| `tools/file_extract.py` | 新增工具（无侵入，纯新增文件） | 🟢 低 |
| `tools/jina_reader.py` | API 不可用时自动降级（不报硬错误） | 🟢 低 |
| `tools/web_tools.py` | 从 web_search 后端移除 Exa（用户无对应 key） | 🟢 低 |
| `web/src/pages/LibraryPage.tsx` | 新增文档库管理页面 | 🟢 低 |
| `web/src/pages/CustomersPage.tsx` | 新增客户管理页面 | 🟢 低 |

### Trade 直接新增的文件（完全非侵入）

| 文件/目录 | 说明 |
|-----------|------|
| `trade/` 整个目录 | 独立的 B2B 业务包，零侵入 Hermes 核心 |
| `hermes_cli/trade_chat.html` | 独立 SPA，通过 /api/trade/* 与后端通信 |
| `plugins/memory/cognee/` | 通过 `MemoryProvider` 插件 API 注册，不侵入核心 |
| `skills/b2b-document/SKILL.md` | Hermes 自动发现加载 |
| `skills/scrapling/SKILL.md` | Hermes 自动发现加载 |
| `skills/file-extract/SKILL.md` | Hermes 自动发现加载 |

---

## 二、按依赖类型的风险评估

### 🔴 关键依赖 — Hermes 升级几乎必定影响

#### 1. `AIAgent.__init__()` 构造函数签名

Trade 使用的参数：
```python
AIAgent(
    quiet_mode=True,              # bool — 历史稳定
    max_iterations=90,            # int — 历史稳定
    provider=...,                 # str | None — 历史稳定
    base_url=...,                 # str | None — 历史稳定
    model=...,                    # str | None — 历史稳定
    api_key=...,                  # str | None — 历史稳定
    tool_start_callback=...,      # callable — 仅流式端点使用
    tool_complete_callback=...,   # callable — 仅流式端点使用
)
```

**风险**：Hermes 升级可能为 `__init__` 添加新的必选参数、改变参数语义、或把构造函数移到其他模块。
**预案**：在 `helpers.get_agent_kwargs()` 中统一构建参数 dict，新增参数有默认值即可。

#### 2. `agent.chat(message) -> str` 方法

**风险**：如果 Hermes 重构 Agent 调用入口（改为 async、改返回值格式），trade 的 `agent.chat(full_query)` 会直接报错。
**预案**：`chat()` 是 `AIAgent` 最简单的公开方法，被广泛使用；即使废弃也会保留向后兼容。如果确实需要迁移，改用 `agent.run_conversation(message)["final_response"]`。

#### 3. `MemoryProvider` ABC 接口

Cognee 实现了 10 个方法：
- `is_available()`, `initialize()`, `system_prompt_block()`
- `prefetch()`, `queue_prefetch()`, `sync_turn()`
- `on_turn_start()`, `on_session_end()`, `shutdown()`
- `get_tool_schemas()`, `handle_tool_call()`

**风险**：如果 Hermes 为 MemoryProvider 添加新的 `@abstractmethod`，cognee plugin 会因缺少实现而报错。
**预案**：cognee plugin 的 `initialize()` 已用 try/except 包裹，插件初始化失败不影响 Agent 正常工作。

#### 4. `web_server.py` 中的 trade router 挂载

```python
# hermes_cli/web_server.py (Trade 修改部分)
from trade.api import router as trade_router
app.include_router(trade_router, prefix="/api/trade")

_TRADE_CHAT_HTML = Path(__file__).parent / "trade_chat.html"

@app.get("/trade", response_class=HTMLResponse)
async def trade_chat_ui():
    ...
```

**风险**：如果 Hermes 重构 web_server.py（改路由注册方式、改 session token 机制、换 Web 框架），trade 路由会失效。
**预案**：trade 路由是标准 FastAPI `include_router`。最坏情况下可独立启动一个 FastAPI 实例只服务 trade 端点，通过不同端口访问。

---

### 🟡 中等依赖 — Hermes 升级大概率需要适配

#### 5. `hermes_cli.config.load_config()` → config.yaml 格式

依赖字段：`model.provider`, `model.default`, `model.base_url`, `memory.provider`

**风险**：如果 Hermes 重命名或重组 config schema（如 `model` → `llm`），`helpers.get_agent_kwargs()` 会拿到空值。
**预案**：在 `get_agent_kwargs()` 中添加 config version 检查；所有字段读取用 `.get()` 并提供默认值。

#### 6. `hermes_cli.auth.PROVIDER_REGISTRY`

依赖接口：`.items()` 遍历、`.api_key_env_vars` 属性、`.base_url_env_var` 属性

**风险**：如果 Hermes 把 `PROVIDER_REGISTRY` 从 dict 改成 dataclass，当前属性访问会失败。
**预案**：`get_agent_kwargs()` 中已用 try/except 包裹，provider registry 解析失败时降级为空字符串，不影响 Agent 初始化。

---

### 🟢 低风险依赖

| 依赖 | 说明 |
|------|------|
| `hermes_constants.get_hermes_home()` | 纯路径工具函数，历史极其稳定 |
| `hermes_cli.models.name_to_models` | 仅用于可选的前端模型列表端点，不影响聊天功能 |
| `tools.registry` | 工具注册系统，接口成熟稳定 |
| `hermes_cli/banner.py` | 纯展示层，升级冲突仅限 Git merge |
| `hermes_cli/skin_engine.py` | 纯展示层，升级冲突仅限 Git merge |

---

## 三、Hermes 升级的六个具体场景

| 场景 | 描述 | Trade 存活概率 | 需要改什么 |
|------|------|---------------|-----------|
| **Patch 升级** | 如 v0.12.0 → v0.12.1，修 bug | ✅ 99% | 基本不用改 |
| **Minor 升级** | 新增 provider、改 UI、加工具 | ✅ 90% | 可能需要解决 web_server.py / main.py 的 Git merge conflict |
| **Agent 重构** | 改 `__init__` 签名、移动模块路径 | ⚠️ 60% | 更新 `helpers.get_agent_kwargs()` 和 `trade/api.py` 的 import 路径 |
| **Memory 系统重构** | 改 `MemoryProvider` ABC，增减抽象方法 | ⚠️ 50% | 更新 cognee plugin 的方法签名，添加空实现以适应新方法 |
| **Config 大改** | 改 config.yaml schema，重命名键 | ⚠️ 40% | 更新 `helpers.py` 的 config 读取路径，可能需要 config migration |
| **Web server 架构变化** | 换框架、改路由注册方式、改认证 | ❌ 20% | 需要重新设计 trade 路由的挂载方式，可能需要独立 FastAPI 实例 |
| **Skill 系统重构** | 改 SKILL.md 格式、改加载机制 | ✅ 95% | 如果 Hermes 仍支持 Markdown frontmatter + 自动发现，则无影响 |

---

## 四、建议的防御措施

1. **版本检查** — 在 `helpers.get_agent_kwargs()` 中添加 config `_config_version` 检查，版本不匹配时 warn
2. **所有 MemoryProvider 方法加 try/except** — cognee plugin 已经做了；后续新增的 memory 方法也应包裹
3. **标注 Hermes 侵入点** — 在每个修改过的 Hermes 文件中用 `# TRADE:` 注释标记 trade 专属改动，方便 Hermes 升级合并时快速定位
4. **CI smoke test** — 在 CI 中加一个 `trade/api.py` 的 import + 模拟调用 test，Hermes 升级后自动跑
5. **独立路由方案** — 预先准备好 trade 独立启动 FastAPI 的脚本，web_server.py 架构变化时可快速切换
6. **锁定 Fork 版本** — 当前基于 `chefroger/hermes-agent` fork，记录 fork 的 commit hash，确保回滚路径

---

## 五、总结

**Trade 与 Hermes 的耦合是松散的、可控的。** Trade 只在 6 个 API 表面与 Hermes 对接，且所有导入都是惰性的（函数内 import）。Hermes 的 Patch / Minor 升级大概率不影响 Trade，Major 升级需要适配但不至于重写。

**最可能断裂的三个点：**
1. `AIAgent.__init__()` 签名变化 → 修改 `trade/helpers.py`
2. `MemoryProvider` ABC 变化 → 修改 `plugins/memory/cognee/__init__.py`
3. `web_server.py` 架构变化 → 将 trade 路由从 web_server 解耦，独立挂载

**Trade 业务层本身（`trade/` 目录）完全不依赖 Hermes 源码位置**——它可以在任何有 `run_agent.AIAgent` 导入路径的 Python 环境中工作。
