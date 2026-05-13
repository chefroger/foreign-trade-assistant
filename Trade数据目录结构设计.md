# Trade 数据目录结构设计

> ⚠️ **本设计全面兼容 Windows 与 macOS。** 所有路径使用 `pathlib`，文件名统一 slug 格式，目录 ≤ 3 层。
>
> 参考 Hermes `~/.hermes/` 设计模式，为 Foreign Trade Assistant 建立跨平台的标准化本地数据组织体系。

---

## 〇、跨平台路径设计

### 设计依据

Hermes Agent 的路径解析逻辑（`hermes_constants.py`）：

```python
def get_hermes_home() -> Path:
    val = os.environ.get("HERMES_HOME", "").strip()
    if val:
        return Path(val)
    return Path.home() / ".hermes"   # Path.home() 自动适配各平台
```

| 平台 | Path.home() | 默认 Hermes 目录 | 默认 Trade 目录 |
|------|------------|-----------------|----------------|
| macOS | `/Users/{user}` | `~/.hermes/` | `~/.trade/` |
| Linux | `/home/{user}` | `~/.hermes/` | `~/.trade/` |
| WSL2 | `/home/{user}` | `~/.hermes/` | `~/.trade/` |
| Windows native | `C:\Users\{user}` | `%LOCALAPPDATA%\hermes\` | `%LOCALAPPDATA%\trade\` |

> 自定义路径：设置 `TRADE_HOME` 环境变量可覆盖默认位置。

**Windows 原生安装**：使用 PowerShell 一键脚本，自动设置 `HERMES_HOME` 和 `TRADE_HOME` 环境变量指向 `%LOCALAPPDATA%`，并捆绑 MinGit（便携 Git Bash）用于 shell 命令执行。

1. **路径分隔符**：全部使用 `Path` / `pathlib` 处理，不硬编码 `/` 或 `\`
2. **文件名限制**：Windows 文件名不能包含 `<>:"/\|?*`，公司名 / 客户名的 slug 只使用字母数字和连字符
3. **路径长度**：Windows 默认 MAX_PATH = 260 字符，目录层级不宜过深（当前设计 3 层，安全）
4. **大小写**：Windows 不区分大小写，文件名统一使用小写 + 连字符（slug 格式）
5. **Git Bash**：Hermes 在 Windows 上捆绑 MinGit，Trade 可以复用该 Git Bash 执行 shell 命令

---

## 一、设计原则

1. **结构统一**：每个公司、每个客户、每个文档库使用相同的目录结构和文件名
2. **渐进填充**：初始只需创建目录骨架，内容可逐步补充
3. **Agent 可读**：所有文件为 Markdown 格式，Agent 可通过 `read_file` 直接读取作为上下文
4. **与 Hermes 共存**：Trade 数据目录独立于 `~/.hermes/`，使用 `~/.trade/`
5. **文件名固定**：每个目录下的文件名是固定的，缺文件表示该信息尚未填写

## 二、仓库模板 vs 运行时目录

| | 仓库（`.trade-template/`） | 运行时（`~/.trade/`） |
|--|--------------------------|----------------------|
| 位置 | 项目仓库根目录 | 用户 home 目录 |
| 用途 | 展示目录骨架 + 模板文件 | 实际存储用户数据 |
| 版本控制 | 是（`.gitignore` 已排除运行时目录） | 否（运行时自动创建） |

> **仓库中的 `.trade-template/`** 即为此目录下完整的模板目录结构，安装时通过 `trade init-company` 等命令在用户 home 目录创建实际运行时目录 `~/.trade/`。

## 三、顶层目录结构

```
~/.trade/
├── config.yaml                     # Trade 专属配置（当前激活的公司等）
├── companies/                      # 公司目录（可管理多个公司）
│   └── {company_slug}/            # 每个公司一个子目录（slug = 英文缩写）
│       ├── company-profile.md      # [必需] 公司介绍
│       ├── products.md             # [必需] 产品目录与优势
│       ├── business-scope.md       # [必需] 业务范围
│       ├── agent-identity.md       # [必需] Agent 在该公司的角色定义
│       ├── competitors.md          # [可选] 同行分析
│       ├── certifications.md       # [可选] 资质认证
│       ├── marketing-strategy.md   # [可选] 营销策略
│       ├── sales-playbook.md       # [可选] 销售话术与谈判策略
│       │
│       ├── libraries/             # 文档库（每个文档库一个子目录）
│       │   └── {library_slug}/
│       │       ├── index.md        # [必需] 文件索引
│       │       ├── changelog.md    # [必需] 内容变化记录
│       │       ├── metadata.md     # [必需] 文档库元信息
│       │       └── extracts/       # [可选] 文档分析切片
│       │           └── {filename}.md
│       │
│       └── clients/               # 客户（每个客户一个子目录）
│           └── {client_slug}/
│               ├── profile.md      # [必需] 客户画像
│               ├── contacts.md     # [必需] 联系人信息
│               ├── interactions.md # [必需] 交流记录与禁忌
│               ├── requirements.md # [可选] 需求记录
│               ├── quotes.md       # [可选] 报价历史
│               ├── orders.md       # [可选] 订单记录
│               └── notes.md        # [可选] 备注
│
├── prompts/                        # Trade 系统提示词（备份）
│   └── trade-system-prompt.md
│
└── skills/                         # Trade 专属技能（用户级覆盖）
    └── b2b-document/
        └── SKILL.md
```

---

## 四、文件规范

### 4.1 公司级文件（8 个）

#### `company-profile.md` [必需]

```markdown
# {公司全称}

## 基本信息
- 成立时间：
- 所在城市：
- 员工规模：
- 年营业额：
- 主营业务：

## 核心优势
1. 
2. 
3. 

## 组织架构
- 外贸部：X 人
- 工厂：X 人
- 研发：X 人

## 合作客户（代表性）
- 
- 
```

#### `products.md` [必需]

```markdown
# 产品目录

## 产品线 1：{名称}
- 核心型号：
- 技术亮点：
- 目标应用场景：
- 认证：

## 产品线 2：{名称}
- ...

## 价格区间
- 低端：$X - $Y
- 中端：$X - $Y
- 高端：$X - $Y

## 最小起订量 (MOQ)
- 

## 交货周期
- 样品：X 天
- 大货：X 天
```

#### `business-scope.md` [必需]

```markdown
# 业务范围

## 目标市场
- 主要出口地区：
- 次要出口地区：
- 待开发地区：

## 客户类型
- 分销商 / EPC 承包商 / 贸易商 / OEM 客户

## 贸易方式
- FOB / CIF / EXW / DDP

## 付款条件
- 新客户：
- 老客户：

## 年出口额
- 
```

#### `agent-identity.md` [必需]

```markdown
# Agent 身份定义

## 角色
你是 {公司名} 的外贸业务助手。你的职责是协助业务团队完成客户开发、询盘回复、
报价方案、社媒内容、客户背调等工作。

## 沟通风格
- 语气：专业、自信、不浮夸
- 语言：面向海外客户用英文，面向内部团队用中文
- 原则：不编造数据，不确定时明确告知

## 专业领域
- 
- 

## 公司的差异化卖点
1. 
2. 
3. 

## 常见客户异议预置回复
- "价格太高" → 
- "已有供应商" → 
- "起订量太大" → 
```

#### `competitors.md` [可选]

```markdown
# 同行分析

## 国内同行
| 公司 | 优势 | 劣势 | 我们的差异化 |
|------|------|------|------------|
|      |      |      |            |

## 国外同行
| 公司 | 优势 | 劣势 | 我们的差异化 |
|------|------|------|------------|
|      |      |      |            |
```

#### `certifications.md` [可选]

```markdown
# 资质认证

| 认证 | 编号 | 颁发机构 | 有效期 | 适用产品 |
|------|------|---------|--------|---------|
|      |      |         |        |         |
```

#### `marketing-strategy.md` [可选]

```markdown
# 营销策略

## B2B 平台
- 阿里国际站：
- 中国制造网：
- 独立站：

## 社媒矩阵
- LinkedIn：
- Facebook：
- Instagram：
- TikTok：
- YouTube：

## 年度营销日历
| 月份 | 重点活动 | 推广产品 |
|------|---------|---------|
```

#### `sales-playbook.md` [可选]

```markdown
# 销售手册

## 询盘回复 SOP
1. 
2. 
3. 

## 报价策略
- 

## 常见异议处理
- 价格异议 →
- 供应商异议 →
- 起订量异议 →

## 谈判技巧
- 

## 跟单流程
1. PI 确认 →
2. 定金收取 →
3. 生产跟进 →
4. 发货通知 →
5. 到货跟进 →
```

---

### 4.2 客户级文件（7 个）

#### `profile.md` [必需]

```markdown
# {客户公司名}

## 基本信息
- 国家/地区：
- 公司规模：
- 主营产品：
- 市场定位：
- 年采购量（估算）：

## 采购特征
- 采购品类：
- 采购周期：
- 决策链（谁是关键决策人）：
- 价格敏感度：高 / 中 / 低
- 品质要求：高 / 中 / 低

## 客户类型
- 分销商 / EPC / 贸易商 / 终端用户

## 与我司的匹配度
- 匹配产品：
- 竞争优势：
- 潜在障碍：
```

#### `contacts.md` [必需]

```markdown
# 联系人

## 主要联系人
- 姓名：
- 职位：
- 邮箱：
- 电话/WhatsApp：
- LinkedIn：
- 性格特征：
- 沟通偏好（邮件/WhatsApp/电话）：

## 次要联系人
- ...
```

#### `interactions.md` [必需]

```markdown
# 交流记录

## 沟通禁忌
- 不聊的话题：
- 敏感事项：

## 最佳联系时间
- 当地时间：XX:00
- 北京时间：XX:00

## 沟通历史摘要
| 日期 | 方式 | 内容 | 结果 |
|------|------|------|------|
|      |      |      |      |
```

#### `requirements.md` [可选]

```markdown
# 需求记录

## 当前需求
- 产品：
- 数量：
- 交期：
- 预算：

## 历史需求
- 

## 潜在需求（推测）
- 
```

#### `quotes.md` [可选]

```markdown
# 报价历史

| 日期 | 产品 | 数量 | 单价 | 总价 | 付款方式 | 有效期 | 状态 |
|------|------|------|------|------|---------|--------|------|
|      |      |      |      |      |         |        |      |

状态：pending / accepted / rejected / expired
```

#### `orders.md` [可选]

```markdown
# 订单记录

| PI号 | 日期 | 产品 | 数量 | 金额 | 付款 | 发货日 | 状态 |
|------|------|------|------|------|------|--------|------|
|      |      |      |      |      |      |        |      |
```

#### `notes.md` [可选]

```markdown
# 备注

- 其他需要记录的信息
- 客户特殊要求
- 下次联系计划
```

---

### 4.3 文档库级文件（3 个 + extracts/）

#### `index.md` [必需]

```markdown
# {文档库名称} — 文件索引

> 根目录：{root_path}
> 最后扫描：{时间}
> 文件总数：{N}

## 文件清单

| # | 文件名 | 类型 | 大小 | 页数/行数 | 内容摘要 |
|---|--------|------|------|----------|---------|
| 1 |        |      |      |          |         |

## 按分类统计
- 报价单：N 个
- 产品规格书：N 个
- 客户资料：N 个
- 成交记录：N 个
- 证书：N 个
- 其他：N 个
```

#### `changelog.md` [必需]

```markdown
# 文档库变化记录

| 日期 | 变化类型 | 文件名 | 说明 |
|------|---------|--------|------|
|      | 新增/修改/删除 |    |      |
```

#### `metadata.md` [必需]

```markdown
# 文档库元信息

- 创建时间：
- 根目录路径：
- 文件总数：
- 最后全量扫描时间：
- 最后增量更新时间：
- Cognee 数据集名称：
```

---

## 五、Agent 如何使用这个结构

### 4.1 启动时自动加载

当 Agent 的工作目录设置为 `~/.trade/companies/{company_slug}/` 时，Hermes 会自动注入该目录下的 `AGENTS.md` 和 `SOUL.md`。Trade 可以利用这个机制：

```
~/.trade/companies/kechen/
├── agent-identity.md    ← 复制为 SOUL.md 供 Hermes 自动加载
├── company-profile.md   ← Agent 通过 read_file 读取
├── products.md
└── ...
```

### 4.2 上下文注入流程

每次 Agent 对话开始时：

1. Agent 读取当前公司的 `agent-identity.md` → 确定角色和沟通风格
2. Agent 读取 `products.md` → 了解产品线
3. Agent 读取 `company-profile.md` → 了解公司背景
4. 如果用户引用客户名 → Agent 查找 `clients/{slug}/` 下的文件
5. 如果用户引用文档库 → Agent 读取 `libraries/{slug}/index.md`

### 4.3 Cognee 知识图谱同步

文档库中的内容分析结果会：
1. 通过 `cognee_remember` 存入知识图谱
2. 同时写入 `extracts/` 目录下的 Markdown 文件（文本化备份）

---

## 六、初始化脚本

`trade init-company` 命令一键创建标准目录骨架：

```bash
trade init-company --name "Kechen" --slug "kechen"
```

输出：
```
创建公司目录：~/.trade/companies/kechen/
  ✓ company-profile.md
  ✓ products.md
  ✓ business-scope.md
  ✓ agent-identity.md
  ✓ competitors.md
  ✓ certifications.md
  ✓ marketing-strategy.md
  ✓ sales-playbook.md
  ✓ libraries/ （空）
  ✓ clients/ （空）

下一步：
  1. 编辑 company-profile.md 填入公司基本信息
  2. 编辑 products.md 填入产品目录
  3. 使用 trade library create 创建第一个文档库
```

---

## 七、与 `data/trade.db` 的关系

| 数据类型 | 存储位置 | 用途 |
|---------|---------|------|
| 结构化数据（CRUD） | `data/trade.db` (SQLite) | 快速查询、API 返回 |
| 非结构化知识 | `~/.trade/companies/*.md` | Agent 上下文、人工编辑 |
| 知识图谱 | Cognee (graph + vector) | 语义召回、跨会话记忆 |
| 原始文档 | 用户指定目录 | Agent 按需读取 |

三者互补：SQLite 提供快速 CRUD，Markdown 文件提供深度上下文，Cognee 提供语义连接。

---

*设计参考：Hermes `~/.hermes/` 目录结构 + 外贸业务需求*
