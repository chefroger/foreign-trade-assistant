---
name: b2b-lead-generation
description: 
triggers:
category: 
version: 1.0.0
author: 
injection_prompt: |
  你是 b2b-lead-generation 技能。当用户需要开发客户、写开发信、做客户分析、处理询盘、报价、谈判或成交时，请执行以下步骤：
  
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
  
  如果用户没有明确说明产品或市场，请先询问这两个关键信息。

  4. 【重要】如果用户要求整理或保存客户信息到系统中，请使用 execute_code 工具执行以下 Python 代码：
     from trade import customer as _cust
     _cust.bulk_save(
         company_id={当前公司ID},
         customers=[
             {"name": "公司名", "contact": "邮箱/电话", "note": "备注",
              "country": "国家", "tier": "A/B/C", "linkedin_url": "链接"},
             ...
         ]
     )
     执行后会返回 {"created": N, "skipped": N}。请告知用户保存结果。
---

Subject: [Personalization — company name or recent news] + [Value prop]

Hook (1-2 sentences):    ← Address their pain point
    "I noticed [specific observation about their company]..."

Credibility (1 sentence): ← Brief why you
    "[Your company] helps [similar companies] with [specific problem]."

Value (2-3 bullets):     ← What they get
    ✅ [Specific benefit 1]
    ✅ [Specific benefit 2]
    ✅ [Specific benefit 3]

Social Proof (optional):  ← Evidence
    "We've helped [X]+ companies in [industry]..."

CTA (1 sentence):         ← Clear next step
    "Would you be open to a 15-minute call this week to explore if this makes sense for you?"
```

### Cold Email Templates

#### Template 1: Problem-Aware Outreach

```
Subject: Quick question about [their company]'s [industry] sourcing

Hi [Name],

I noticed [specific observation — e.g., "your company just expanded into the European market"].

The challenge we solve for companies like yours: [specific problem — e.g., "inconsistent product quality from current suppliers"].

We've helped [X]+ [industry] companies reduce [specific metric — e.g., "quality issues by 40%"] while [secondary benefit — e.g., "cutting lead times from 45 to 25 days"].

One thing we'd like to explore: Is [specific question related to their situation]?

Would you have 15 minutes this week for a brief call?

Best regards,
[Your name]
[Title] | [Company]
[Contact info]
```

#### Template 2: Referral Warm Outreach

```
Subject: [Referrer name] suggested I reach out

Hi [Name],

[Referrer name] mentioned you're looking to [their goal/problem].

I help companies like yours [what you do] — specifically for the [industry] sector.

Would you be open to a quick conversation about your [topic]? Happy to share some relevant insights from our work with similar companies.

Best,
[Your name]
```

#### Template 3: LinkedIn Connection Note (≤300 chars)

```
Hi [Name]! Noticed you're in the [industry] space. I help B2B companies source [product] from verified manufacturers — similar to what [their company] might be looking for. Would love to connect!
```

### SPAM Filter Words to Avoid

**Never use in subject lines or body**:
```
FREE           Guaranteed      No obligation
100%           Winner          Limited time
Act now        Urgent          As seen on
Best price     Lowest price    Million
Cash bonus     Extra income    Increase your
```

## Phase 4: Follow-Up Sequences

### Standard Follow-Up Sequence

| Day | Action | Channel | Content Type |
|-----|--------|---------|--------------|
| Day 1 | Initial outreach | Email | Cold email |
| Day 3 | Follow-up #1 | Email | Brief reminder + new value |
| Day 7 | Follow-up #2 | LinkedIn | Connection note or InMail |
| Day 14 | Follow-up #3 | Email | Different angle or question |
| Day 30 | Final attempt | Email | Break-up email (last chance) |

### Follow-Up Email Templates

#### Day 3 — Gentle Reminder

```
Subject: Re: [Previous subject]

Hi [Name],

Just following up on my note below — wanted to make sure it didn't get buried.

Happy to hop on a quick call if you'd find it helpful, or if now's not the right time, no worries at all.

Just reply here and I'll leave you alone! 😅

Best,
[Your name]
```

#### Day 14 — Different Angle

```
Subject: [Question related to their business]

Hi [Name],

Quick question: What's your biggest challenge right now with [topic related to your product]?

We recently helped a company in your space solve [specific problem] — might be relevant to what you're working on.

Worth a quick chat?

Best,
[Your name]
```

#### Day 30 — Break-Up Email

```
Subject: Last note from me 👋

Hi [Name],

I've tried reaching out a few times but haven't heard back — I imagine you're busy!

I'm going to close your file for now. But if you ever want to chat about [topic], my door's always open.

Best of luck with [their goals],
[Your name]
```

## Phase 5: Customer Types & Communication Strategies

### Type 1: Retailer / Small Wholesaler

| Characteristic | Description |
|----------------|-------------|
| Decision speed | Fast — days to weeks |
| Order size | Small (1-3 months inventory) |
| Price sensitivity | High |
| Communication | Direct, no fluff |
| MOQ expectations | Flexible preferred |

**Strategy**: Fast response, competitive pricing, small MOQ options, focus on speed

**Key phrase**: "快、准、狠" — fast, precise, aggressive

### Type 2: Trading Company / Middleman

| Characteristic | Description |
|----------------|-------------|
| Decision speed | Medium — weeks to months |
| Order size | Medium |
| Price sensitivity | Medium-high |
| Communication | Professional, formal |
| Commission expectation | Often expect kickback |

**Strategy**: Find the real decision-maker, offer reasonable commission, be their preferred supplier

**Key phrase**: "找对负责人，留出佣金空间"

### Type 3: OEM / Brand Buyer

| Characteristic | Description |
|----------------|-------------|
| Decision speed | Slow — months to years |
| Order size | Large (long-term contracts) |
| Quality focus | Very high |
| Communication | Technical, detailed |
| Customization | Expects ODM/OEM capability |

**Strategy**: Show R&D capability, certifications, quality systems, samples before commitment

**Key phrase**: "展示研发和认证能力"

### Type 4: Chain Supermarket / Big Box

| Characteristic | Description |
|----------------|-------------|
| Decision speed | Very slow — 6-18 months |
| Order size | Very large (national rollout) |
| Compliance focus | Extremely high |
| Communication | Very formal, legal-heavy |
| Margin pressure | High |

**Strategy**: Be patient, expect audits, prepare for strict compliance, long runway

**Key phrase**: "持久战准备"

## Phase 6: Inquiry Handling — The 30-Minute Rule

**Reply to all inquiries within 30 minutes during working hours.**

### Inquiry Response Template

```
Subject: Re: [Product inquiry from XXX]

Dear [Name],

Thank you for your inquiry about [product]!

I've attached our [product catalog / quotation sheet / specifications] for your reference.

[Answer to their specific question(s)]

Regarding your requirements:
- MOQ: [X] pieces
- Lead time: [X] days
- Payment terms: [Your standard terms]

Could you please clarify:
1. [Specific question 1]
2. [Specific question 2]

Looking forward to your feedback!

Best regards,
[Your name]
[Title] | [Company]
[Phone] | [WeChat/WhatsApp]
```

## Phase 7: Price Negotiation Framework

### The 3-Step Price Negotiation

**Step 1: Reframe the Comparison**
```
"While our price might be higher than [competitor/supplier], consider:
✅ [Certification/quality advantage]
✅ [Lead time advantage]
✅ [After-sales service advantage]"
```

**Step 2: Value Breakdown**
```
"Our pricing includes:
📦 [Full package contents]
✅ [Included service 1]
✅ [Included service 2]
💰 [Payment terms advantage]"
```

**Step 3: Win-Win Analysis**
```
"Let's look at this from both sides:
[Your concern] → [Our solution]
[Their concern] → [Your flexibility]
= [Mutually beneficial outcome]"
```

### Price Positioning Strategies

| Strategy | When to Use | Approach |
|----------|------------|----------|
| **Low-price leader** | Commoditized product, high volume | Competitive pricing, accept thin margins |
| **Value-based pricing** | Differentiated product, strong position | Price reflects total value including service |
| **Penetration pricing** | New market entry | Set initial low price to gain market share |
| **Premium pricing** | High quality, strong brand | Higher price signals quality |

## Phase 8: Quote Generation

### Quote Must Include

```
QUOTATION
Date: [Date]
Quote No.: [XXX]

To: [Client Name]
Company: [Company]
Email: [Email]

Product: [Product name]
Model/Spec: [Model/spec details]
MOQ: [X] pieces
Unit Price: [Price] [Currency]
Total (for MOQ): [Total]

Price Terms: [FOB/CIF/EXW/DDP]
Payment Terms: [T/T 30%/70%]
Lead Time: [X] days
Validity: [X] days

Remarks:
- [Additional terms or notes]

Best regards,
[Your name]
[Company]
```

## Phase 9: Sample Management

### Sample Process

```
1. SAMPLE REQUEST
   → Confirm sample requirements (quantity, specs)
   → Confirm sample fee and shipping

2. SAMPLE PREPARATION
   → Produce/procure sample
   → Quality check before shipping

3. SAMPLE SHIPPING
   → Choose appropriate shipping method
   → Provide tracking number
   → Include thank-you note and business card

4. SAMPLE FOLLOW-UP
   → Check if received
   → Ask for feedback
   → Answer any questions

5. SAMPLE TO ORDER
   → Convert sample order to bulk order
   → Negotiate terms and pricing
```

## Phase 10: Order Follow-Up & Tracking

### Order Tracking Timeline

| Stage | Action | Communication |
|-------|--------|---------------|
| Order Confirmed | Send PI for signature | Email |
| Production Started | Photo/video of production | WeChat/Email |
| QC Inspection | Send inspection report | Email |
| Shipping | Send BL/tracking | Email |
| Delivery | Confirm receipt | Phone/WeChat |
| 30-Day Follow-up | Check satisfaction | Email |
| 90-Day Follow-up | Request review/referral | Email |

## Quality Standards

1. **Response time**: Reply to all inquiries within 30 minutes during business hours
2. **Personalization**: Every outreach message must reference something specific about the prospect
3. **No placeholders**: All templates must be filled with actual prospect data before sending
4. **Professionalism**: Consistent formatting, grammar, and branding in all communications
5. **Follow-through**: If you promise something (quote, sample, call), deliver it
6. **Documentation**: Log all customer interactions in the customer record

## Common Pitfalls

1. **One-size-fits-all outreach**: Always personalize — mass messages get ignored
2. **Giving up too early**: 80% of customers are closed after the 4th follow-up
3. **Neglecting existing customers**: Easier to get repeat orders than find new customers
4. **Ignoring time zones**: Respect the prospect's working hours
5. **Weak subject lines**: The subject line determines if your email gets opened
6. **No clear CTA**: Always tell the prospect what to do next
7. **Price-only negotiation**: Never compete on price alone — compete on value
8. **Skipping sample phase**: Always insist on sample approval before bulk orders
