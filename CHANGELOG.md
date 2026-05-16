# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式规范。

## [Unreleased]

### Fixed
- F401 lint 规则从全局豁免改为 per-file-ignores，精确控制豁免范围
- email_intel.py 移除未使用的 `import holehe.modules`，改用 `importlib.util.find_spec`

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
