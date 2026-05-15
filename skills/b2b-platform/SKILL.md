---
name: b2b-platform
description: 
triggers:
category: 
version: 1.0.0
author: 
injection_prompt: |
  你是 b2b-platform 技能。当用户需要诊断或优化任何网站（B2B平台店铺、公司官网、独立站、产品页面）时，请执行以下步骤：
  
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
     - 行动清单：第一周做什么、第二周做什么
---

Good: "High-Quality Stainless Steel Ball Valve DN50 PN16 for Industrial Use | ISO Certified"
Good: "Custom OEM [Product Type] Manufacturer | [X] Years Experience | Fast Delivery"
Bad:   "Product A001" (too short, no keywords)
Bad:   "Best Quality Low Price Factory Direct Supply Custom Wholesale Bulk Buy Now Discount" (keyword stuffing)
```

### Keyword Analysis

**For Each Major Keyword**:
1. **Search volume**: Is it commonly searched?
2. **Competition**: How many other sellers use it?
3. **Relevance**: Does it accurately describe your product?
4. **Specificity**: Is it too broad or too narrow?

**Keyword Categories**:

| Type | Examples | Use |
|------|---------|-----|
| **Product Type** | ball valve, circuit breaker, LED panel | Primary keyword in title |
| **Material** | stainless steel, aluminum, PVC | In title + description |
| **Application** | industrial, plumbing, automotive | In description |
| **Specification** | DN50, 12V, 100W | In title (if space allows) |
| **Buyer Intent** | manufacturer, factory, wholesale | In title (for B2B) |

### Product Description Analysis

**Check for**:
- Clear product features and specifications
- Product benefits (not just features)
- Technical parameters (dimensions, materials, certifications)
- Usage/application information
- Quality control/assurance mentions
- Trade terms (MOQ, lead time, payment terms)

**Description Structure (Recommended)**:

```
[HOOK — Address buyer pain point or need]

[PRODUCT OVERVIEW — What it is]
[KEY SPECIFICATIONS — Technical details in table format]
[MATERIALS & CONSTRUCTION — What it's made of and why it matters]
[APPLICATIONS — Where/how it's used]
[BENEFITS — Why choose this product over alternatives]
[CERTIFICATIONS — ISO, CE, RoHS, etc.]
[TRADE TERMS — MOQ, lead time, payment, shipping]
[COMPANY CREDIBILITY — Experience, factory info, service]
[CTA — Contact information/request quote]
```

### Image Analysis

**Check for**:
- Minimum 3-6 images per product
- Main image: clean, professional, white/light background
- Multiple angles (front, side, back, detail shots)
- Scale reference (person, ruler, coin for size)
- Application photos (product in use)
- Packaging images for export readiness
- Infographics showing key specifications
- Image resolution (minimum 800 x 800 px recommended)

**Image Best Practices**:
- Lead with a hero shot showing the complete product
- Include detail shots of key features/finish
- Show size comparison (common in B2B)
- Include factory production photos if applicable
- Video is increasingly important (product demo, factory tour)

## Phase 2: Store/Profile Analysis

### Store Elements to Analyze

| Element | What to Check | Impact |
|---------|---------------|--------|
| **Store Name** | Clear, professional, includes keywords | Branding + SEO |
| **Banner/Header** | Professional design, clear value proposition | First impression |
| **Company Introduction** | Experience, certifications, production capacity | Credibility |
| **Product Categories** | Logical organization, complete coverage | Navigation |
| **Response Rate** | Speed of reply to inquiries | Trust signal |
| **Transaction History** | Verified transactions, repeat buyers | Social proof |
| **Certifications** | ISO, CE, factory audits displayed | Quality assurance |

### Credibility Indicators

```
✅ Verified manufacturer status
✅ Trade Assurance membership
✅ On-site Check / Third-party inspection
✅ Years in business (verified)
✅ Transaction history (real buyers)
✅ Response rate > 90%
✅ Video content (factory tour)
✅ Client testimonials/reviews
❌ Missing: Any of the above = weakness to address
```

## Phase 3: Competitor Benchmarking

### How to Find Competitors

1. Search for main product keyword on the platform
2. Note the top-ranking sellers (first page)
3. Analyze their:
   - Product titles and keywords
   - Description length and structure
   - Image quality and quantity
   - Pricing (if visible)
   - Response time and communication
   - Certifications and credentials

### Competitor Analysis Template

```
Competitor: [Store/Company Name]
URL: [Link]

TITLES:
- [Competitor's title 1]
- [Competitor's title 2]
Gap vs. You: [What's missing or better in theirs]

IMAGES:
- Number of images: [X]
- Quality (1-5): [Rating] — [Strengths]
- Gap vs. You: [What's better in theirs]

DESCRIPTIONS:
- Length: [X] words
- Structure: [How they organize content]
- Key elements included: [List]
- Gap vs. You: [What's better in theirs]

PRICING:
- Visible: [Yes/No]
- Range: [If visible]
- Gap vs. You: [Positioning]

CERTIFICATIONS:
- [List displayed]
- Gap vs. You: [What's missing]

STRENGTHS TO BORROW:
1. [Specific tactic or element]
2. [Specific tactic or element]

ACTION ITEMS:
1. [Improvement based on competitor insight]
2. [Improvement based on competitor insight]
```

## Phase 4: Diagnostic Report & Improvement Plan

### Report Structure

```
# B2B Platform Store Diagnostic Report

## Executive Summary
[2-3 sentences: overall health score and key priority]

## Current Performance Issues
[Top 3-5 problems identified, ranked by impact]

## Detailed Analysis

### Product Titles
| Product | Current Title | Issues | Recommended Title |
|---------|--------------|--------|------------------|
| [Product 1] | [Title] | [Issue] | [New title] |
| [Product 2] | [Title] | [Issue] | [New title] |

### Keywords
| Keyword | Search Volume | Competition | Priority | Action |
|---------|--------------|-------------|---------|--------|
| [Keyword 1] | High/Med/Low | High/Med/Low | P1 | [Action] |

### Product Descriptions
| Product | Current Length | Structure Score | Action |
|---------|----------------|-----------------|--------|
| [Product 1] | [X] words | Good/Fair/Poor | [Rewrite/Expand/Restructure] |

### Images
| Product | Current Count | Quality | Missing | Action |
|---------|--------------|---------|---------|--------|
| [Product 1] | [X] | Good/Fair/Poor | [List] | [Add/PImprove] |

## Priority Action Plan

### P1 — Critical (Do This Week)
1. [Action item with specific steps]
2. [Action item with specific steps]

### P2 — Important (Do This Month)
1. [Action item]
2. [Action item]

### P3 — Nice to Have (Do This Quarter)
1. [Action item]
2. [Action item]

## Expected Outcomes
- [Metric] improvement: [Current] → [Expected]
- [Metric] improvement: [Current] → [Expected]
```

## Phase 5: Keyword Strategy

### Keyword Research Process

1. **Seed keywords**: Start with main product terms
2. **Expand**: Add variations (synonyms, related terms)
3. **Filter**: Remove irrelevant or extremely low-volume terms
4. **Prioritize**: Focus on high-relevance + moderate-competition terms

### Keyword Categories for B2B

| Category | Example | Placement |
|----------|---------|-----------|
| **Head terms** | valve, pump | Title (once) |
| **Product type** | ball valve, butterfly valve | Title + description |
| **Material** | stainless steel, brass | Title + description |
| **Specification** | DN50, 1/2 inch | Title (if space) |
| **Application** | industrial, plumbing | Description |
| **Buyer intent** | manufacturer, factory, wholesale | Title + description |
| **Long-tail** | ball valve for water treatment | Description |

### Title Optimization Rules

1. **First 30 characters matter most** — put primary keyword here
2. **Include product type** — what are you selling?
3. **Add key spec if space** — material, size, or model
4. **Include buyer intent keyword** — manufacturer, wholesale
5. **Don't stuff** — 3-5 keywords max in title
6. **Match search terms** — think like your buyer

## Quality Standards

1. **Specificity over generality**: "Stainless Steel Ball Valve DN50 PN16" > "High Quality Valve"
2. **Buyer-centric**: Focus on benefits to the buyer, not just features
3. **Completeness**: All key information should be findable within the listing
4. **Professionalism**: No spelling errors, proper grammar, consistent formatting
5. **Uniqueness**: Each product needs its own optimized content — no copy-paste between listings
6. **Data-driven**: Reference actual numbers (certifications, years, capacity) not vague claims

## Common Pitfalls

1. **Keyword stuffing**: Repeating keywords in title/description hurts rankings and credibility
2. **Vague descriptions**: "High quality" without specifics means nothing to buyers
3. **Missing trade terms**: Always include MOQ, lead time, payment terms
4. **Poor images**: Dark, blurry, or unprofessional photos kill inquiries
5. **Copying competitors**: Learn from them, but differentiate your content
6. **Neglecting mobile**: Many B2B platform users browse on mobile — ensure readability
7. **No video**: Products with video get 2-3x more inquiries than those without
8. **Ignoring data**: Use platform analytics to understand what's working
