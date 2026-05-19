# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式规范。

## [Unreleased]

### Added
- **Hermes v0.14 适配**：config.model 从嵌套 dict 变为扁平字符串，Trade 自动兼容两种格式
- **启动时自动从 GitHub 拉取最新 B2B skills**，确保 skills 始终与仓库同步
- **macOS 开机自启动**（launchd，后台静默无终端窗口），安装脚本自动配置；`trade update` 后自动重启服务
- **定时任务使用说明书**：页面上方嵌入零基础 cron 表达式教程，含速查表、符号说明和常见问题
- **`trade update / backup / skills-update` 子命令**正确路由，无需启动服务器即可更新
- **输出语言规则**：LinkedIn/lead-generation/social-media 三个 skill 均按目标客户语言输出，默认英语
- `TRADE_HOME` 环境变量支持：测试和开发环境下工作目录不会污染桌面

### Changed
- hermes-agent 从 `chefroger/hermes-agent` fork 迁移到上游 `NousResearch/hermes-agent` v0.14
- **LinkedIn/lead-generation/social-media 三个 skill 全面转向客户价值导向**：内容以客户痛点+解决方案为中心，产品/工厂占 20-25%
- 版本约束从 `>=0.12.0,<0.14.0` 提升到 `>=0.13.0,<0.15.0`
- OSINT 背调使用精简 system prompt，不再把文档生成指南带入调查场景
- OSINT 背调时禁止注入历史对话，防止上一轮背调话题污染当前查询

### Fixed
- SQLite 增加 `busy_timeout=30000`，防止并发写入 database is locked
- SSE QueueFull 防护：工具事件过于频繁时静默丢弃而非崩溃
- API 异常信息脱敏：异常详情只写日志，前端返回通用错误消息
- `customer.update` 越权修复：extra 字段更新时缺少 company_id 校验
- `api_key` 跨 provider 兜底可能导致拿错 key，改为精确匹配
- `DELETE /companies/{id}` 缺少鉴权：已认证用户可越权删除其他公司数据
- `post_install.py` 中 `urllib.error` 未 import 导致 HTTP 错误时 NameError 崩溃
- `email_intel.py` trio/asyncio event loop 混合崩溃：async 路径改为子进程运行 holehe
- `linkedin_verify.py` 中 `{domain_clean}` 占位符未被 f-string 替换
- `orchestrator.py` LinkedIn 搜索时把 email 当公司名
- 测试中 `/tmp` 硬编码路径在 Windows 上崩溃
- `memory.py` 中 `import fcntl` 在 Windows 上崩溃
- 6 处 `~/.hermes/` / `~/.trade/` 硬编码路径改为平台感知的默认路径
- Windows `install.ps1` 中 `trade.cmd` HERMES_HOME 赋值错误 + 未加 PATH
- cron/jobs API 适配 Hermes 实际 jobs.json 数据结构（`{"jobs": [...]}` 格式）
- F401 lint 规则从全局豁免改为 per-file-ignores
- 全项目 100+ 函数 docstring 英→中转换 + 150+ if-branch 中文注释补全

## [0.3.0] — 2026-05-15

### Added
- CI 三平台测试矩阵 (Ubuntu + macOS + Windows, Python 3.11/3.12/3.13)
- CI `python -m compileall` 语法检查（lint job）
- CI ruff check（lint job）
- 使用说明书

### Changed
- hermes-agent 版本对齐 v0.13（>=0.12.0, <0.14.0）
- stderr monkey-patch 替换为 logging Filter，在 Hermes import 前安装
- ruff auto-fix 172 处 lint 问题

### Fixed
- WHOIS 域名解析错误
- DNS MX 查询交易 ID 随机化（防 DNS 欺骗）
- Token 比较使用 `secrets.compare_digest`（防时序攻击）
- 异步上下文中阻塞 socket 调用改为 executor
- Token 估算修正（中英文混合处理）
- WHOIS socket recv 循环改为正确检测对端关闭
- ChatRequest Pydantic 模型化
- customer.update 事务化（单事务，失败统一回滚）
- Skill router LRU 缓存上限可配置
- 制裁阈值提高，减少短查询误报

## [0.2.0] — 2026-05-14

### Added
- 海关数据工作目录（自动创建 + CSV/Excel 文件支持）
- b2b-customs-data skill 自动读取海关数据目录
- toolsets 环境变量可配置（TRADE_ENABLED_TOOLSETS）
- 显式启用 web/search/file/terminal/code_execution/browser/skills/memory/cronjob/todo toolset

### Changed
- 平台诊断 skill 改为支持任何网站（B2B 平台 + 公司官网 + 独立站）
- SQL 时间比较改为参数化

### Fixed
- create_agent 修复 Agent 无法搜索网络的问题
- customer.update 死代码行（NameError）
- saveCustomer 参数缺失

## [0.1.0] — 2026-05-13

### Added
- 首个公开版本
- FastAPI 服务器 + B2B chat SPA
- 多公司管理（multi-tenancy）
- 文档库管理（libraries CRUD）
- 客户管理（customers CRUD + 文档库关联）
- 对话记忆（conversations + Hindsight 长期记忆）
- 13 个 b2b-* skills（OSINT/邮件情报/客户开发/文档/文档生成/平台/领英/社媒/海关/onboarding/自动化/客户管理/数据目录）
- OSINT 尽职调查（WHOIS + 邮箱验证 + 制裁筛查 + 技术栈 + LinkedIn）
- 定时任务（Cron）集成
- 首次运行引导（onboarding）
- Windows 兼容（Gateway 启动 + CREATE_NEW_PROCESS_GROUP）
- Skill 自动路由（关键词匹配 + 注入）
