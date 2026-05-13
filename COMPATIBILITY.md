# Hermes ↔ Foreign Trade Assistant 兼容性记录

> 每次 Hermes 升级后更新此文件。升级前先跑一次完整兼容性检查（见 `项目需求文档.md` 第二章）。

## 兼容性矩阵

| Hermes 版本 | 兼容状态 | 测试日期 | 测试人 | 备注 |
|------------|---------|---------|--------|------|
| 0.12.0 | ✅ 兼容 | 2026-05-11 | — | 锁定版本。当前 Trade 基于此版本开发 |
| 0.13.0 | ✅ 兼容 | 2026-05-11 | AI | API 检查通过：AIAgent/MemoryProvider/load_config 均无 breaking change |
| 0.14.0 | ⏳ 待测试 | — | — | |

## 升级检查流程

当 Hermes 发布新版本时，按以下步骤验证：

```
1. pip install hermes-agent@新版本
2. python server.py --no-browser  ← 依赖版本检查会自动拦截不兼容版本
3. 如果启动检查通过，手动执行以下验证：
   a. /api/trade/chat 端点正常
   b. /api/trade/chat/stream 端点正常
   c. Cognee 记忆功能正常
   d. 文档提取功能正常
4. 全部通过 → 更新上方矩阵 + 更新 pyproject.toml 版本 pin
```

## 断裂记录

> 记录历史上 Hermes 哪些升级导致了兼容性问题，以及修复方式。

| Hermes 版本 | 断裂点 | 影响 | 修复方式 |
|------------|--------|------|---------|
| — | — | — | — |
