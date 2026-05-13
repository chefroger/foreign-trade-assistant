"""
Trade AI Assistant — Skill Router.

Automatically detects which b2b-* skill a user query should trigger,
even when the prompt is vague, abbreviated, or in a different language.
Augments the query with a precise skill injection prompt so the LLM
knows exactly what tool to use and how to format its output.

Architecture
────────────
This module is called from helpers.build_query() — the last checkpoint
before the prompt reaches the LLM.  It never runs tools, never calls the
API, and adds zero latency when no skill matches (fast dict lookup).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# mtime cache: {skill_name: (mtime, injection_prompt)}
# ─────────────────────────────────────────────────────────────────────────────

_INJECTION_CACHE: dict[str, tuple[float, str]] = {}

# ─────────────────────────────────────────────────────────────────────────────
# SKILL.md → injection_prompt loader
# ─────────────────────────────────────────────────────────────────────────────

def _get_hermes_skills_dir() -> Path:
    val = os.environ.get("HERMES_HOME", "").strip()
    if val:
        return Path(val) / "skills"
    return Path.home() / ".hermes" / "skills"


def _get_skill_dir(skill_name: str) -> Path | None:
    """Return the path to the installed skill directory, or None if not found."""
    skill_path = _get_hermes_skills_dir() / skill_name
    if (skill_path / "SKILL.md").is_file():
        return skill_path
    # Fallback: check package skills dir
    try:
        import trade
        pkg_root = Path(trade.__file__).parent.parent
        pkg_skill = pkg_root / "skills" / skill_name
        if (pkg_skill / "SKILL.md").is_file():
            return pkg_skill
    except Exception:
        pass
    return None


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content.

    Uses full YAML parsing so that | block scalar values containing lines
    that look like --- delimiters are handled correctly (YAML parser treats
    them as literal content, not as document separators).

    Returns (frontmatter_dict, body_content).
    If no valid frontmatter, returns ({}, content).
    """
    if not content.startswith("---\n"):
        return {}, content

    # Use full YAML parsing so block scalar | content is handled correctly.
    # YAML multi-document separators (---) inside | block scalars are NOT
    # treated as separators by safe_load().
    import yaml
    try:
        # yaml.safe_load on the frontmatter text only (up to the first \n---\n
        # that is at the top level — which we find by scanning for \n---\n
        # that is NOT inside a | block)
        #
        # Simpler approach: use the full content but extract only what we need.
        # Since injection_prompt uses | format, the safest parse is to use
        # safe_load on the frontmatter section only.
        #
        # Strategy: find the second ---\n at column 0 (i.e. preceded by \n).
        second_dash = content.find("\n---\n", 4)
        if second_dash == -1:
            return {}, content

        fm_text = content[4:second_dash]
        body = content[second_dash + 5:]

        parsed = yaml.safe_load(fm_text)
        if parsed is None:
            return {}, body
        if not isinstance(parsed, dict):
            return {}, body

        return parsed, body
    except yaml.YAMLError:
        return {}, content


def _load_injection_prompt(skill_name: str) -> str | None:
    """Load injection_prompt from SKILL.md frontmatter (mtime-cached).

    优先级：
      1. ~/.hermes/skills/{skill}/SKILL.md  (用户安装版)
      2. {package}/skills/{skill}/SKILL.md  (包内置版)
      3. None → 降级到 _SKILLS 中的 augment_prompt (fallback)

    Returns the raw injection_prompt string (no marker wrapping here).
    """
    skill_dir = _get_skill_dir(skill_name)
    if skill_dir is None:
        return None

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None

    try:
        mtime = skill_md.stat().st_mtime
    except OSError:
        return None

    cache_key = skill_name
    cached = _INJECTION_CACHE.get(cache_key)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None

    fm, _ = _parse_frontmatter(content)
    injection = fm.get("injection_prompt", "")

    if injection:
        _INJECTION_CACHE[cache_key] = (mtime, injection)

    return injection or None

# ─────────────────────────────────────────────────────────────────────────────
# Skill Registry
# ─────────────────────────────────────────────────────────────────────────────
# Each entry:
#   triggers  : list of lowercase keywords / phrases (OR match)
#   aliases   : list of alternative names that mean the same thing
#   name      : skill identifier used in "skill_load" injection
#   input_fmt : natural-language description of what the user should provide
#   output_fmt: natural-language description of what the user gets back
#   augment_prompt: (DEPRECATED, kept as fallback) hardcoded injection text
# ─────────────────────────────────────────────────────────────────────────────

_SKILLS: list[dict] = [
    {
        "name": "b2b-osint",
        "triggers": [
            # Chinese
            "背景调查", "背调", "尽职调查", "查一下这家公司", "查一下这个域名",
            "域名查一下", "域名注册时间", "制裁名单", "OFAC", "企业邮箱验证",
            "查公司", "风险评估", "红旗", "客户真实性", "这个公司是真的吗",
            "公司查一下", "域名查一下", "whois", "骗子特征", "背调",
            # English
            "due diligence", "osint", "company verification", "domain age",
            "risk assessment", "红旗", "check company", "check domain",
            "whois lookup", "sanctions check", "osint check",
            # Fragments
            "帮我背调", "查一下这个公司", "域名老不老", "邮箱是真的假的",
        ],
        "aliases": ["b2b-email-intel"],
        "input_fmt": "邮箱地址 / 域名 / 公司名（自动识别类型）",
        "output_fmt": (
            "综合风险评级（低/中/高）+ 5层验证详情（WHOIS/邮箱/制裁/技术栈/LinkedIn）"
            "+ 行动建议 + 红旗列表"
        ),
        "augment_prompt": """你是 b2b-osint 技能。当用户需要进行客户背景调查、尽职调查、域名验证、企业邮箱核验或风险评估时，请执行以下步骤：

1. 加载 skill: b2b-osint
2. 调用 osint_full_check(目标, include_sanctions=True, include_tech_stack=True, include_linkedin=True)
3. 解析返回的 report，按以下格式输出：
   ## 综合风险评级
   - 评级：[低/中/高风险]
   - 分数：X/100
   - 红旗：⚠️ 项列表

   ## 各层验证结果
   ### 域名信息
   - 域名：[domain]
   - 注册时间：[age_days] 天（[age_category]）
   - 注册商：[registrar]
   - 红旗标记：如果 age_category == new，标记 ⚠️ 新注册域名

   ### 企业邮箱验证
   - 邮箱类型：[企业邮箱/个人邮箱]
   - MX记录：[找到/未找到]
   - 红旗标记：如果 is_personal == True，标记 ⚠️ 个人邮箱

   ### 制裁名单
   - 命中：[是/否]
   - 风险等级：[none/low/medium/high]

   ### 技术栈
   - 平台：[platforms]
   - 红旗标记：如果 is_free_platform == True，标记 ⚠️ 免费建站工具

   ### LinkedIn
   - 公司页：[找到/未找到]
   - 员工规模：[count]
   - 域名匹配：[是/否]

   ## 行动建议
   逐一列出 recommendations 中的每条建议

如果用户没有提供具体目标（只说"帮我背调"），请先询问目标（邮箱/域名/公司名）。""",
    },
    {
        "name": "b2b-email-intel",
        "triggers": [
            # Chinese
            "背景调查", "邮箱查询", "邮箱注册", "邮箱查注册", "邮箱查平台",
            "邮箱查社交", "邮箱情报", "邮箱是真的吗", "邮箱真实性",
            # English
            "email intel", "email lookup", "email profile", "email search",
            "email verification", "邮箱 osint",
            # Chinese slang / fragments
            "查一下这个邮箱", "帮我查邮箱", "查邮箱背景", "邮箱查一下",
            # English slang
            "check this email", "email check", "who owns this email",
            "find email owner",
        ],
        "aliases": [],
        "input_fmt": "一个邮箱地址，例如 john@company.com",
        "output_fmt": (
            "各平台注册状态（存在/不存在/请求受限）+ "
            "用户名、头像、注册时间等公开信息 + "
            "社交档案URL列表 + 真实性评分（高/中/低）"
        ),
        "augment_prompt": """你是 b2b-email-intel 技能。当用户需要调查某个邮箱的背景时（例如"查一下这个邮箱"、"背景调查"、"email intel"），请执行以下步骤：

1. 从对话中提取邮箱地址（格式：xxx@domain.com）
2. 加载 skill: b2b-email-intel
3. 调用 email_background_check(邮箱地址)
4. 返回结构化报告：
   - 平台检测结果（checked_count / found_count）
   - 每个平台：平台名 | 是否注册 | 用户名 | 档案URL | 注册时间
   - 社交档案汇总（GitHub/LinkedIn/Twitter 等）
   - 真实性评估：高/中/低 及依据
   - 备注：哪些平台注册代表该客户可信度高

如果用户只说了"背景调查"但没有提供邮箱，在回复中请用户补充邮箱地址。""",
    },
    {
        "name": "b2b-lead-generation",
        "triggers": [
            # Chinese
            "找客户", "开发客户", "客户开发", "找潜在客户", "开发信",
            "询盘", "客户跟进", "客户分析", "报价", "谈判", "成交",
            "报价单", "报价模板", "价格谈判", "报价技巧",
            # English
            "lead generation", "find customers", "customer development",
            "cold email", "outreach", "prospect", "prospecting",
            "lead gen", "leadgen", "lead generation",
            "follow up", "follow-up", "quotation", "quote", "negotiation",
            "closing", "rfq", "inquiry",
            # English fragments
            "find buyers", "get customers", "look for customers",
            # Fragments
            "有新客户吗", "怎么找客户", "客户资源", "客户名单",
            "帮我写开发信", "写一封邮件", "客户案例", "买家",
            "buyer", "purchasing manager", "procurement",
        ],
        "aliases": ["b2b-customer-mgmt"],
        "input_fmt": "产品/服务描述 + 目标市场/地区（可选）",
        "output_fmt": (
            "客户分类框架（A/B/C级）+ 优先排序列表 + "
            "个性化开发信模板 + 跟进时间线 + 报价策略建议"
        ),
        "augment_prompt": """你是 b2b-lead-generation 技能。当用户需要开发客户、写开发信、做客户分析、处理询盘、报价、谈判或成交时，请执行以下步骤：

1. 加载 skill: b2b-lead-generation
2. 根据用户需求执行对应子任务：
   - 找客户：使用 b2b-platform/LinkedIn/海关数据等来源
   - 写开发信：先加载 b2b-email-intel 查邮箱背景，再撰写个性化邮件
   - 客户分析：提取客户名称/公司/地区，从对话或文档中获取信息
   - 报价/谈判：参考 b2b-customer-mgmt 的报价单管理流程
3. 按以下格式返回：
   - 客户分类：高价值（A）/ 中等（B）/ 潜力（C）
   - 具体行动建议：第一步做什么、第二步做什么
   - 开发信/邮件模板（个性化，非通用）
   - 跟进时间表：Day1 / Day3 / Day7 / Day14

如果用户没有明确说明产品或市场，请先询问这两个关键信息。""",
    },
    {
        "name": "b2b-document",
        "triggers": [
            # Chinese
            "分析文档", "分析文件", "读取报价", "看合同", "产品规格",
            "产品报价单", "合同分析", "技术规格", "参数对比", "翻译合同",
            # English
            "analyze document", "analyze file", "read quote", "read contract",
            "product spec", "specification", "price list", "compare",
            "datasheet", "technical document",
            # Fragments
            "帮我看看这个", "这是什么产品", "产品参数", "单价多少",
            "价格是多少", "交期多久", "moq", "最小订货量",
        ],
        "aliases": [],
        "input_fmt": "文档文件路径（PDF/Word/Excel/CSV/图片）或文档内容",
        "output_fmt": (
            "文档摘要 + 关键数据提取（产品/价格/数量/交期）"
            "+ 交叉引用（如有多个文档）+ 业务建议"
        ),
        "augment_prompt": """你是 b2b-document 技能。当用户要求分析文档、报价单、合同、规格表，或提取文档中的产品/价格/数量/交期数据时，请执行以下步骤：

1. 加载 skill: b2b-document
2. 使用 read_file 读取文档（支持 PDF/Word/Excel/CSV/图片）
3. 按 Agent Loop 工作流执行：
   - Survey：先列出文件，确认文件类型和数量
   - Prioritize：先读报价单（价格信息）→ 规格书（参数）→ 合同（条款）→ 记录（历史）
   - Read thoroughly：逐个文件读取，不跳过
   - Cross-reference：检查文件间关联（如报价引用了规格书中的产品代号）
   - Iterate：如信息不完整，继续读更多文件
   - Answer：给出具体数值（含单位）和来源文件
4. 返回格式：
   - 文档摘要（一段话）
   - 关键数据表格：品名 | 规格 | 单价 | 最小订货量 | 交期 | 付款条件
   - 交叉引用说明（如有）
   - 建议（如：某价格偏低、某条款需注意）

引用格式：📄 {文件名} | Sheet: {sheet名} | Row: {行范围}""",
    },
    {
        "name": "b2b-doc-generation",
        "triggers": [
            # Chinese
            "生成文档", "创建文档", "制作文档", "生成PPT", "生成PPTX",
            "做一份报价", "做一份合同", "做一份提案", "做一份演示",
            "生成报价单", "生成合同", "生成提案", "导出文档",
            # English
            "generate doc", "gen doc", "create doc",
            "generate document", "create document", "generate pptx",
            "generate proposal", "generate contract", "generate quote",
            "make a presentation", "export to docx", "export to xlsx",
            "proposal template", "quotation template",
            # Fragments
            "帮我生成", "输出一份", "出一份", "做成文件", "导出",
        ],
        "aliases": [],
        "input_fmt": "文档类型（PPT/Word/Excel）+ 受众（客户/内部）+ 语言",
        "output_fmt": "可下载的 PPTX/DOCX/XLSX 文件",
        "augment_prompt": """你是 b2b-doc-generation 技能。当用户要求生成 PPT、Word 文档、Excel 报价单、合同或商业提案时，请执行以下步骤：

1. 加载 skill: b2b-doc-generation
2. 确认信息（必要时询问）：
   - 文档类型：PPTX（演示）/ DOCX（合同/协议）/ XLSX（报价）
   - 受众：国际客户（全英文）/ 中国客户（全中文）
   - 产品/服务内容：从对话或文档库获取
3. 生成文档：
   - PPTX：python-pptx，品牌色（工业用深蓝#0B2A4A+金#D4A853），标题页→双栏→卡片网格→数据表格→图标文字行
   - DOCX：python-docx，条款清晰、格式专业
   - XLSX：python-openpyxl，完整数据表、交替行颜色
4. 验证：生成后用 read_file 抽查，确认数据完整无占位符
5. 保存路径：./output/{文档类型}_{客户名}_{日期}.{ext}
6. 返回：生成文件的绝对路径 + 文件大小 + 关键内容摘要

重要：所有文档必须是单一语言（英文或中文），不混用。""",
    },
    {
        "name": "b2b-platform",
        "triggers": [
            # Chinese
            "平台诊断", "阿里国际站优化", "中国制造网", "独立站优化",
            "产品链接分析", "关键词优化", "产品标题", "排名", "曝光",
            "询盘", "曝光量", "点击率",
            # English
            "platform diagnosis", "alibaba optimization", "made-in-china",
            "keyword optimization", "product title", "ranking",
            "search ranking", "seo", "product listing", "alibaba international",
            # Fragments
            "阿里店铺", "平台上排名", "关键词排名", "搜索排名",
        ],
        "aliases": [],
        "input_fmt": "B2B平台产品链接 或 平台名称 + 产品关键词",
        "output_fmt": (
            "诊断报告：曝光/点击/询盘数据 + "
            "标题/关键词/图片/描述评分 + "
            "具体优化建议（高/中/低优先级）+ 行动清单"
        ),
        "augment_prompt": """你是 b2b-platform 技能。当用户需要诊断或优化阿里国际站、中国制造网等B2B平台的产品页面时，请执行以下步骤：

1. 加载 skill: b2b-platform
2. 获取数据：
   - 如果提供了产品链接：用 browser_navigate 打开并截图分析
   - 如果只提供了关键词：用平台搜索结果页面做竞品分析
3. 按诊断维度分析：
   - 产品标题：关键词覆盖、移动端友好度、专业性
   - 产品图片：数量、质量、是否展示工厂/证书
   - 产品描述：结构化程度、关键词密度、卖点清晰度
   - 关键词：排名词覆盖、长尾词布局
   - 询盘转化：主图、视频、交易保障因素
4. 返回格式：
   - 总体评分：X/100 及等级（优秀/良好/需改进/差）
   - 各维度评分：标题/图片/描述/关键词/询盘转化
   - 优化建议：按优先级（高/中/低）列出
   - 行动清单：第一周做什么、第二周做什么""",
    },
    {
        "name": "b2b-linkedin-marketing",
        "triggers": [
            # Chinese
            "LinkedIn营销", "领英营销", "LinkedIn策略", "领英开发客户",
            "LinkedIn内容", "领英帖子", "LinkedIn profile", "领英账号",
            "LinkedIn开发信", "领英InMail",
            # English
            "linkedin marketing", "linkedin strategy", "linkedin content",
            "linkedin post", "linkedin outreach", "linkedin profile optimization",
            "linkedin company page", "linkedin personal branding",
            # Fragments
            "发领英", "写领英", "领英怎么发", "linkedin post",
        ],
        "aliases": [],
        "input_fmt": "LinkedIn目标（个人品牌/公司主页/开发客户）+ 产品/行业信息",
        "output_fmt": (
            "内容策略（5大支柱）+ 帖子模板 + LinkedIn profile 优化建议 "
            "+ 互动策略 + 开发信模板"
        ),
        "augment_prompt": """你是 b2b-linkedin-marketing 技能。当用户需要 LinkedIn 营销策略、Profile 优化、内容发布或开发信时，请执行以下步骤：

1. 加载 skill: b2b-linkedin-marketing
2. 确认目标：
   - 个人品牌：先优化 Profile（Headline/Summary/Experience）
   - 公司主页：完善公司介绍 + 员工推文策略
   - 开发客户：5大支柱内容策略 + 个性化 InMail 模板
3. 内容发布（每周计划）：
   - 行业洞察（30%）：分享产品/行业趋势
   - 个人故事（20%）：工作中的真实案例
   - 产品价值（20%）：应用场景、成功案例
   - 互动提问（20%）：引导评论，增加曝光
   - 客户背书（10%）：推荐信、好评截图
4. Profile 优化：
   - Headline：职务 + 公司 + 核心价值主张（220字符内）
   - Summary：用第一人称，讲清楚"我能帮谁解决什么问题"
   - Experience：每个条目讲成就而非职责（用数据）
5. 返回：完整内容日历（周计划）+ 5条立即可发的帖子""",
    },
    {
        "name": "b2b-social-media",
        "triggers": [
            # Chinese
            "社媒营销", "社交媒体营销", "Facebook营销", "Ins营销",
            "TikTok营销", "YouTube营销", "社媒内容", "社媒运营",
            "内容日历", "同行社媒分析", "发帖",
            # English
            "social media marketing", "facebook marketing", "instagram marketing",
            "tiktok marketing", "youtube marketing", "content calendar",
            "competitor social media", "social media strategy",
            # Fragments
            "FB发帖", "ins怎么发", "TikTok内容", "油管内容",
            "社媒计划", "一周发什么",
        ],
        "aliases": [],
        "input_fmt": "目标平台（FB/Ins/TikTok/YouTube）+ 行业/产品 + 每周发布频率",
        "output_fmt": (
            "平台策略 + 内容日历（周/月）+ 帖子模板 "
            "+ Reels/Shorts 脚本 + 竞争对手分析报告"
        ),
        "augment_prompt": """你是 b2b-social-media 技能。当用户需要制定 Facebook、Instagram、TikTok 或 YouTube 的社媒营销策略时，请执行以下步骤：

1. 加载 skill: b2b-social-media
2. 确认平台组合（可多平台）：
   - Facebook：B2B 长文、图文帖、案例研究、Group 运营
   - Instagram：高质量图片、Reels短视频、Stories互动
   - TikTok：工厂/产品幕后视频、行业知识趣味化
   - YouTube：产品演示视频、客户案例长视频、FAQ视频
3. 内容日历（周计划）：
   - 建议发布频率（每个平台）
   - 内容类型配比（产品/教育/互动/促销）
   - 发布时间（按目标市场时区）
4. 每条帖子包含：
   - 标题/文案（含 hashtag 建议）
   - 配图/视频描述
   - CTA（点赞/评论/私信/访问链接）
5. 竞品分析：找出3个同行动议参考的账号，分析其内容策略
6. 返回：完整月历（每条帖子含：日期/平台/内容类型/文案摘要）""",
    },
    {
        "name": "b2b-customs-data",
        "triggers": [
            # Chinese
            "海关数据", "进出口记录", "广交会数据", "贸易数据挖掘",
            "采购商分析", "供应商分析", "市场调研", "竞争对手分析",
            "查采购商", "找买家", "进出口数据",
            # English
            "customs data", "import export records", "trade data mining",
            "buyer analysis", "supplier analysis", "market research",
            "competitor analysis", "trade intelligence",
            # Fragments
            "谁在进口", "哪些公司在买", "海关记录", "进出口查询",
            # English fragments
            "find buyers", "import data", "export data", "trade data",
        ],
        "aliases": [],
        "input_fmt": "产品HS编码 或 产品名称 + 目标市场（国家/地区）",
        "output_fmt": (
            "采购商列表（按进口量排序）+ 供应商列表 + "
            "市场趋势分析 + 价格区间 + 目标客户优先级排序"
        ),
        "augment_prompt": """你是 b2b-customs-data 技能。当用户需要分析海关进出口数据、找采购商、做市场调研或竞品分析时，请执行以下步骤：

1. 加载 skill: b2b-customs-data
2. 确认输入：
   - 有数据文件（CSV/Excel）：读取并分析
   - 无数据文件：从用户提供的产品/市场信息给出分析方法论
3. 分析维度：
   - 采购商分析：按进口量排序，找出TOP10买家，分析购买频率和价格敏感度
   - 供应商分析：按出口量排序，分析主要竞争者市场份额
   - 市场趋势：近N个月进口量变化，判断是增长还是萎缩
   - 价格区间：该产品的CIF/FOB价格分布
   - 目标客户优先级：A级（高频率大批量）/ B级（稳定中等）/ C级（低频小量）
4. 返回：
   - 采购商表格：公司名 | 国家 | 进口量 | 频率 | 价格敏感度 | 推荐等级
   - 市场洞察：3个关键发现
   - 具体行动：如何接触A类客户 + 差异化话术建议""",
    },
    {
        "name": "b2b-onboarding",
        "triggers": [
            # Chinese
            "新公司", "部署", "全套方案", "公司介绍", "产品介绍",
            "营销方案", "营销定位", "市场定位", "竞争对手分析",
            "开始使用", "首次设置",
            # English
            "new company", "deploy", "setup", "marketing plan",
            "company profile", "product introduction", "marketing positioning",
            "competitor analysis", "first time setup",
            # Fragments
            "怎么开始", "新手上路", "第一步做什么", "我需要准备什么",
        ],
        "aliases": [],
        "input_fmt": "公司名称 + 产品/服务 + 目标市场 + 竞争优势（简述）",
        "output_fmt": (
            "完整营销部署方案：公司简介 + 产品介绍 + 目标客户画像 "
            "+ 竞争对手分析 + 营销策略 + 内容计划 + 平台入驻建议"
        ),
        "augment_prompt": """你是 b2b-onboarding 技能。当用户是第一次使用本系统，或者要求新公司部署、全套营销方案时，请执行以下步骤：

1. 加载 skill: b2b-onboarding
2. 引导用户提供基本信息（按顺序询问，一次1-2个）：
   - 公司名称和成立时间
   - 主要产品/服务（最好提供产品资料文件）
   - 目标市场（哪些国家/地区）
   - 核心竞争优势（价格/质量/交期/服务）
   - 现有营销渠道（平台/展会/Direct）
3. 生成完整部署方案：
   - 公司介绍文档（.md → 可导出 DOCX）
   - 产品介绍文档（按产品线分类，含规格参数）
   - 目标客户画像（3个典型客户类型）
   - 竞争对手分析（列出3-5个主要竞争者及对比）
   - 营销策略：渠道优先级、内容主题、发布时间表
   - 平台入驻建议：哪些平台最适合该行业和产品
4. 返回：
   - 完整部署文档路径
   - 接下来7天行动计划（每天做什么）
   - 30天里程碑""",
    },
    {
        "name": "b2b-daily-automation",
        "triggers": [
            # Chinese
            "每日任务", "自动化", "定时任务", "定时发布", "Cron",
            "早安简报", "工作总结", "晚间总结", "周报", "日报",
            "定时提醒", "自动发送",
            # English
            "daily tasks", "automation", "scheduled tasks", "scheduled posting",
            "morning brief", "daily summary", "weekly report", "daily report",
            "cron job", "recurring task", "automated workflow",
            # Fragments
            "每天自动", "自动发内容", "定时发", "每天发什么",
            "早报", "晚报", "自动生成报告",
        ],
        "aliases": [],
        "input_fmt": "任务类型（早报/晚报/定时发布/周报）+ 发送频率 + 目标平台",
        "output_fmt": (
            "Cron 任务配置 + 任务执行脚本内容 + "
            "触发时间（UTC）+ 预期输出描述"
        ),
        "augment_prompt": """你是 b2b-daily-automation 技能。当用户需要设置每日自动化任务（如早安简报、定时发布、周报自动生成）时，请执行以下步骤：

1. 加载 skill: b2b-daily-automation
2. 确认任务需求：
   - 早安简报：当日汇率 + 天气 + 目标市场动态 + 今日待办
   - 定时发布：指定平台（LinkedIn/FB/Ins）+ 发布时间
   - 晚间总结：今日新询盘/客户互动/订单进度
   - 周报：本周数据汇总 + 下周行动计划
3. 使用 cronjob 工具创建任务：
   - 指定 schedule（如 "0 8 * * *" 对应每天UTC 8点）
   - 指定 skills（如 b2b-linkedin-marketing 用于内容发布）
   - 指定 deliver 目标（当前对话 origin 或指定平台）
4. 返回：
   - 已创建的任务 ID
   - 下次执行时间（换算为用户本地时间）
   - 任务内容描述
   - 如何修改/暂停/删除""",
    },
    {
        "name": "b2b-customer-mgmt",
        "triggers": [
            # Chinese
            "客户管理", "客户档案", "客户分级", "大客户", "客户分类",
            "客户等级", "VIP客户", "客户信息", "客户资料",
            "订单管理", "跟单", "订单状态", "发货",
            # English
            "customer management", "customer profile", "customer classification",
            "key account", "account management", "vip customer",
            "order tracking", "order status", "shipment tracking",
            # Fragments
            "客户列表", "所有客户", "新客户", "大客户维护",
        ],
        "aliases": ["b2b-lead-generation"],
        "input_fmt": "客户名称 或 操作类型（查看列表/更新状态/查看详情）",
        "output_fmt": (
            "客户档案（含分级/阶段）+ 跟进记录 + "
            "报价单列表 + 订单状态 + 下一步行动建议"
        ),
        "augment_prompt": """你是 b2b-customer-mgmt 技能。当用户需要管理客户档案、查看客户列表、跟踪订单或进行客户分级时，请执行以下步骤：

1. 加载 skill: b2b-customer-mgmt
2. 根据操作类型执行：
   - 查看客户列表：调用 customer.list_by_company(company_id)，
     按 A/B/C 分级展示，标注每个客户的最新跟进时间
   - 客户详情：调用 customer.get(customer_id, company_id)，
     显示档案完整信息 + 关联报价单 + 订单历史
   - 客户分级：根据年交易额/订单频率/利润贡献重新分类
   - 订单跟踪：从对话中提取订单号，查询状态更新
3. 返回格式：
   - 客户列表表格：名称 | 分级 | 国家 | 最近跟进 | 当前阶段 | 待办事项
   - 客户详情卡片：联系信息 + 交易历史 + 跟进记录时间线
   - 下一步行动建议（基于客户当前阶段）""",
    },
    {
        "name": "b2b-data-directory",
        "triggers": [
            # Chinese
            "数据目录", "公司档案", "产品目录", "客户目录",
            "初始化", "数据结构", "trade目录", "数据初始化",
            # English
            "data directory", "company profile", "product catalog",
            "customer directory", "initialization", "data structure",
            # Fragments
            "我的公司", "公司信息", "产品列表", "客户数据存在哪",
        ],
        "aliases": [],
        "input_fmt": "公司slug（可选）+ 操作类型（初始化/查看/更新）",
        "output_fmt": (
            "数据目录结构说明 + 各文件用途描述 "
            "+ 最近更新的文件列表 + 存储路径"
        ),
        "augment_prompt": """你是 b2b-data-directory 技能。当用户需要了解或初始化 ~/.trade/ 数据目录结构时，请执行以下步骤：

1. 加载 skill: b2b-data-directory
2. 根据请求类型执行：
   - 查看结构：描述 ~/.trade/companies/{slug}/ 下的完整文件树
     及其用途（company-profile.md / products.md / ...）
   - 初始化数据：使用 .trade-template/ 模板创建公司数据目录
   - 更新文件：读取现有文件 → 修改 → 写回（保留原有数据）
3. 目录结构说明：
   ~/.trade/
   └── companies/{company-slug}/
       ├── company-profile.md    # 公司介绍
       ├── products.md           # 产品目录（含优势）
       ├── business-scope.md     # 业务范围 + 目标市场
       ├── agent-identity.md     # AI Agent 身份定义
       ├── competitors.md        # 竞争对手分析
       ├── certifications.md     # 证书与合规
       ├── marketing-strategy.md # 营销策略
       ├── sales-playbook.md     # 销售话术 + 异议处理
       ├── libraries/{lib-slug}/ # 文档库（按产品线）
       │   ├── index.md
       │   ├── changelog.md
       │   └── metadata.md
       └── clients/{client-slug}/ # 客户档案
4. 返回：目录树 + 最近更新的文件 + 存储路径""",
    },
    {
        "name": "chat-memory",
        "triggers": [],
        "aliases": [],
        "input_fmt": "用户的查询意图（查询历史/时间范围）",
        "output_fmt": "历史对话列表（带时间戳）",
        "augment_prompt": """你是 chat-memory 技能。当用户需要查询历史对话时，主动调用 chat_memory_list 工具。
适用场景：用户提到"之前""上次""以前""那天""上周"等时间词；询问过去讨论过的内容；需要了解用户的长期偏好。
调用方式：chat_memory_list(time_range="all", limit=20)
结果格式：[{created_at, query, response}, ...]""",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation
# ─────────────────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    """Strip and lowercase, collapse whitespace."""
    return re.sub(r'\s+', ' ', text.strip().lower())


# ─────────────────────────────────────────────────────────────────────────────
# Core matching
# ─────────────────────────────────────────────────────────────────────────────

# Pre-compile trigger regexes once at import time.
_COMPILED: list[tuple[re.Pattern, dict]] = []
# Explicit skill invocation pattern: "用 b2b-xxx" or "load skill b2b-xxx"
_EXPLICIT_RE = re.compile(
    r'(?:用|使用|调用|加载|load?\s*(?:skill)?)\s*b2b-[\w-]+',
    re.IGNORECASE,
)
for _skill in _SKILLS:
    patterns = []
    for kw in _skill["triggers"]:
        # Escape special regex chars; allow embedded word-boundary matching
        escaped = re.escape(kw)
        # Phrase match with word boundaries on both ends
        patterns.append(r'\b' + escaped + r'\b')
        # Also allow loose substring (handles suffixes/prefixes)
        patterns.append(escaped)
    combined = "|".join(patterns)
    _COMPILED.append((re.compile(combined, re.IGNORECASE), _skill))


def match_skill(query: str) -> Optional[dict]:
    """Return the first matching skill dict, or None.

    Args:
        query: raw user input (will be normalised internally).

    Returns:
        The full skill registry entry (with augment_prompt, input_fmt,
        output_fmt, name) of the first skill whose triggers match the query,
        or None if no match.
    """
    if not query or not query.strip():
        return None

    normed = _norm(query)

    # 1. Explicit skill invocation: "用 b2b-email-intel 查一下"
    #    or "load skill b2b-document" — extract and resolve directly.
    explicit_match = _EXPLICIT_RE.search(query)
    if explicit_match:
        # e.g. "用 b2b-email-intel" or "load skill b2b-document"
        # Extract the "b2b-xxx" part (case-insensitive)
        matched_text = explicit_match.group(0)
        skill_name_candidate = next(
            (name for name in skill_names()
             if name in matched_text.lower()),
            None,
        )
        if skill_name_candidate:
            return get_skill_by_name(skill_name_candidate)

    # 2. Keyword/regex matching against trigger lists.
    for pattern, skill in _COMPILED:
        if pattern.search(normed):
            return skill

    return None


def get_skill_by_name(name: str) -> Optional[dict]:
    """Direct lookup by skill name (used for explicit skill= requests)."""
    for s in _SKILLS:
        if s["name"] == name:
            return s
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Query augmentation
# ─────────────────────────────────────────────────────────────────────────────

SKILL_INJECTION_MARKER = "[SKILL AUGMENTATION]"
SKILL_EXPLICIT_MARKER = "[SKILL EXPLICIT]"


def augment_query(
    query: str,
    *,
    skill_name: Optional[str] = None,
    company_id: Optional[int] = None,
) -> str:
    """Augment a user query with a skill injection prompt.

    Two calling conventions:
    1. Implicit  — match_skill(query) detected a skill → skill_name is set.
    2. Explicit  — the LLM or frontend already decided which skill to use
                   and passed skill_name directly.

    Args:
        query:      original user input
        skill_name: optional explicit skill identifier (overrides matching)
        company_id: optional company ID (used to build file paths in the
                    skill_augment_prompt template)

    Returns:
        The original query string with a skill injection block prepended.
        If no skill matches and skill_name is None, returns query unchanged.
    """
    # Determine which skill to inject
    if skill_name:
        skill = get_skill_by_name(skill_name)
    else:
        skill = match_skill(query)

    if skill is None:
        # No match — pass through unchanged
        return query

    name = skill["name"]

    # Try SKILL.md frontmatter first, fall back to hardcoded dict
    augment = _load_injection_prompt(name)
    if augment is None:
        augment = skill.get("augment_prompt", "")

    # Resolve company_id for path-dependent skills
    # (currently only b2b-data-directory needs this)
    data_dir_hint = ""
    if name == "b2b-data-directory" and company_id:
        from trade import company as _co
        tc = _co.get_trade_company(company_id)
        if tc and tc.get("data_dir"):
            slug = tc.get("slug", "unknown")
            data_dir_hint = (
                f"\n公司数据目录路径：{tc['data_dir']}\n"
                f"完整路径示例：~/.trade/companies/{slug}/"
            )

    injection = (
        f"\n"
        f"{SKILL_INJECTION_MARKER}\n"
        f"## 技能触发：{name}\n"
        f"{SKILL_EXPLICIT_MARKER if skill_name else ''}\n"
        f"{augment}"
        f"{data_dir_hint}\n"
        f"## 用户原始问题\n{query}\n"
        f"{SKILL_INJECTION_MARKER}\n"
    )

    return injection


# ─────────────────────────────────────────────────────────────────────────────
# Skill metadata helpers
# ─────────────────────────────────────────────────────────────────────────────

def list_skills() -> list[dict]:
    """Return all registered skill entries (without augment_prompt)."""
    return [
        {k: v for k, v in s.items() if k != "augment_prompt"}
        for s in _SKILLS
    ]


def skill_names() -> list[str]:
    """Return the list of all registered skill names."""
    return [s["name"] for s in _SKILLS]
