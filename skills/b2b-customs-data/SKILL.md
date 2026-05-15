---
name: b2b-customs-data
description: 
triggers:
category: 
version: 1.0.0
author: 
injection_prompt: |
  你是 b2b-customs-data 技能。当用户需要分析海关进出口数据、找采购商、做市场调研或竞品分析时，请执行以下步骤：
  
  1. 加载 skill: b2b-customs-data
  2. 确认输入：
     - 首先检查桌面工作目录中的「海关数据」文件夹，自动 list_files 查看是否有 CSV/Excel 文件
     - 有数据文件（CSV/Excel）：自动读取并分析所有海关数据文件
     - 无数据文件：提示用户将海关数据放入「海关数据」目录后重试
  3. 分析维度：
     - 采购商分析：按进口量排序，找出TOP10买家，分析购买频率和价格敏感度
     - 供应商分析：按出口量排序，分析主要竞争者市场份额
     - 市场趋势：近N个月进口量变化，判断是增长还是萎缩
     - 价格区间：该产品的CIF/FOB价格分布
     - 目标客户优先级：A级（高频率大批量）/ B级（稳定中等）/ C级（低频小量）
  4. 返回：
     - 采购商表格：公司名 | 国家 | 进口量 | 频率 | 价格敏感度 | 推荐等级
     - 市场洞察：3个关键发现
     - 具体行动：如何接触A类客户 + 差异化话术建议
---

Exclude:
- Products outside user's business scope
- Raw materials that are inputs to user's product (not final product)
```

#### Filter 2: Geographic Targeting

```
Include based on user's target markets:
- Specific countries/regions (North America, Europe, Southeast Asia)
- Avoid: countries with trade restrictions or high tariffs

Exclude:
- Markets user is not targeting
- Regions with regulatory barriers
```

#### Filter 3: Volume & Frequency

```
Include:
- Buyers with regular import patterns (multiple shipments per year)
- Volume sufficient for user's MOQ

Exclude:
- One-time buyers (no repeat business potential)
- Volume below user's MOQ
```

#### Filter 4: Company Type

```
Include:
- Manufacturers (final product buyers)
- Brand owners
- Large distributors

Exclude:
- Small retailers (below threshold)
- Trading companies acting as intermediaries
```

## Phase 3: Buyer Pattern Analysis

For each qualified buyer, analyze:

### Purchase Patterns

| Metric | What It Tells You |
|--------|-------------------|
| **Frequency** | How often they buy (monthly/quarterly/annually) |
| **Volume trend** | Growing, stable, or declining purchases |
| **Seasonality** | Peak buying seasons |
| **Supplier concentration** | Do they rely on few or many suppliers? |
| **Price sensitivity** | Volume vs. price correlations |

### Example Analysis (Generic Template)

```
Company: [Buyer Name]
Country: [Country]
Products imported: [Product categories]
Annual volume: [Estimated value]
Frequency: [X] shipments/year
Typical order size: [Range]
Suppliers: [Number of suppliers] (mostly from [countries])

Patterns:
- Peak season: [Q1/Q2/Q3/Q4]
- Order cycle: [Monthly/Quarterly]
- Last shipment: [Date]

Potential approach:
- Angle: [Based on their supplier concentration/price trends]
- Timing: [Best time to reach out]
- Product focus: [Which of your products fits their pattern]
```

## Phase 4: Priority Scoring

Score each prospect based on:

### Scoring Matrix

| Criteria | Weight | Score (1-5) |
|----------|--------|-------------|
| Industry match | 25% | How well product aligns |
| Volume potential | 25% | Order size and frequency |
| Geographic fit | 20% | Your ability to serve |
| Accessibility | 15% | Ease of outreach (LinkedIn, email, etc.) |
| Growth trend | 15% | Purchase volume trend |

### Priority Classification

| Total Score | Priority | Action |
|-------------|----------|--------|
| 4.0 - 5.0 | **P1 — Hot** | Immediate outreach within 24h |
| 3.0 - 3.9 | **P2 — Warm** | Personalized outreach within 1 week |
| 2.0 - 2.9 | **P3 — Medium** | Add to nurture sequence |
| < 2.0 | **P4 — Low** | Periodic check-ins only |

## Phase 5: Output — Target Customer List

### Output Format

```
# B2B Trade Data Analysis Report

## Summary
- Total records analyzed: [X]
- Qualified prospects: [X]
- By priority: P1=[X], P2=[X], P3=[X], P4=[X]
- Geographic distribution: [Chart/Table]

## P1 Prospects (Immediate Action)

### 1. [Company Name]
| Field | Details |
|-------|---------|
| Country | [Country] |
| Products | [Product categories] |
| Est. Annual Volume | [Value] |
| Frequency | [X]x/year |
| Last Purchase | [Date] |
| Key Suppliers | [Countries] |
| Approach Angle | [How to position] |
| Recommended Action | [Specific next step] |

### 2. [Company Name]
[Same structure]

## P2 Prospects (This Week)

[Same structure]

## P3-P4 Prospects (Nurture)

[Condensed list format]

## Market Insights

1. [Key finding about the market]
2. [Key finding about competitor suppliers]
3. [Opportunity identified]

## Appendix: Full Data Table

| Company | Country | Product | Volume | Frequency | Score | Priority |
|---------|---------|---------|--------|-----------|-------|----------|
| [Name] | [Country] | [Product] | [Value] | [Freq] | [X.X] | P1 |
```

## Phase 6: Integration with Outreach

### From Data to Action

For P1 prospects, generate:

1. **Customer Brief**: 1-page summary of the prospect
2. **Customized Outreach**: Cold email referencing their specific purchase patterns
3. **Talking Points**: Based on their supplier concentration, price trends, seasonality

### Outreach Angle Examples

```
If they buy from multiple suppliers:
"We noticed you work with several [product] suppliers in [country]. 
We're a specialized manufacturer focusing on [specific product segment]. 
Would you be open to exploring if we can offer better [specific advantage]?"

If they have seasonal patterns:
"Your import data shows peak season in [Q2]. 
We're reaching out now because we'd like to discuss how we can 
support your [Q2] requirements with our [product] capabilities."

If they recently expanded volume:
"Congratulations on your growth in [product category]! 
We've helped similar companies scale their [specific need]. 
Would you be open to a brief call to explore if we're a fit?"
```

## Quality Standards

1. **Data accuracy**: Cross-check key data points (company names, volumes) against multiple rows
2. **HS code validation**: Ensure HS codes are correctly interpreted for product mapping
3. **Currency consistency**: Note currency in value fields; flag inconsistencies
4. **No assumptions**: If a field is ambiguous, note it rather than guess
5. **Source citation**: Always cite the source file and row numbers for key findings
6. **Completeness**: Include all relevant fields in output, even if values are missing

## Common Pitfalls

1. **Over-relying on volume**: Big buyers may already have established suppliers — look for disruption opportunities
2. **Ignoring frequency**: One-time large orders may not indicate ongoing business potential
3. **Missing seasonality**: Outreach timed wrong can kill opportunity before it starts
4. **Generic outreach**: Always customize message based on the specific buyer's patterns
5. **Not verifying data**: Company names may have typos or different spellings — verify before outreach
6. **Privacy concerns**: Customs data may have usage restrictions — ensure compliance
