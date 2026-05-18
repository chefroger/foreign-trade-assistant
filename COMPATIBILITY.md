# Hermes ↔ Foreign Trade Assistant 兼容性记录

> 每次 Hermes 升级后更新此文件。升级前先跑一次完整兼容性检查（见 `项目需求文档.md` 第二章）。

## 兼容性矩阵

| Hermes 版本 | 兼容状态 | 测试日期 | 测试人 | 备注 |
|------------|---------|---------|--------|------|
| 0.12.0 | ✅ 兼容 | 2026-05-11 | — | 锁定版本。当前 Trade 基于此版本开发 |
| 0.13.0 | ✅ 兼容 | 2026-05-11 | AI | API 检查通过：AIAgent/MemoryProvider/load_config 均无 breaking change |
| 0.14.0 | ✅ 兼容 | 2026-05-18 | AI | config.model 从嵌套 dict 变为扁平字符串；name_to_models 移除。已适配。 |

## 升级检查流程

当 Hermes 发布新版本时，按以下步骤验证：

```
1. pip install hermes-agent@新版本（或更新 pyproject.toml 中的 git tag）
2. python server.py --no-browser
3. 如果启动检查通过，手动执行以下验证：
   a. /api/trade/chat 端点正常
   b. /api/trade/chat/stream 端点正常
   c. /api/trade/models/providers 端点正常（验证 config.model 解析）
   d. 文档提取功能正常
4. 全部通过 → 更新上方矩阵 + 更新 pyproject.toml 版本 pin + 更新 Dockerfile
```

## 断裂记录

> 记录历史上 Hermes 哪些升级导致了兼容性问题，以及修复方式。

| Hermes 版本 | 断裂点 | 影响 | 修复方式 |
|------------|--------|------|---------|
| 0.14.0 | `config["model"]` 从 dict 变为 str | `helpers.py` 和 `memory.py` 中 `model_cfg.get("provider")` 报 AttributeError | `_parse_model_config_str()` 兼容两种格式 |
| 0.14.0 | `hermes_cli.models.name_to_models` 移除 | `memory.py` import 失败 | 改用 `_PROVIDER_MODELS` |
| 0.14.0 | `run_agent.py` 从 `chefroger/hermes-agent` fork 迁移到上游 `NousResearch/hermes-agent` | pyproject.toml git 依赖指向旧 fork | 更新 git URL 指向 `NousResearch/hermes-agent` |
