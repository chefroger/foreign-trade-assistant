---
name: b2b-customer-mgmt
description: 
triggers:
category: 
version: 1.0.0
author: 
injection_prompt: |
  你是 b2b-customer-mgmt 技能。当用户需要管理客户档案、查看客户列表、跟踪订单或进行客户分级时，请执行以下步骤：
  
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
     - 下一步行动建议（基于客户当前阶段）
---

CUSTOMER: [Company Name]
├── Basic Info
│   ├── Company name (English)
│   ├── Company name (Chinese)
│   ├── Website
│   ├── Address
│   ├── Country/Region
│   └── Business type (manufacturer/trader/retailer)
│
├── Contacts (multiple)
│   ├── Name
│   ├── Title/Role
│   ├── Email
│   ├── Phone/WeChat/WhatsApp
│   ├── Best time to contact
│   └── Decision authority (final/influencer/day-to-day)
│
├── Business Profile
│   ├── Annual revenue (estimate)
│   ├── Employee count
│   ├── Main products/business
│   ├── Target markets
│   └── Current suppliers
│
├── Classification
│   ├── Customer type (A/B/C)
│   ├── Priority level
│   └── Key account (Yes/No)
│
├── Commercial Terms
│   ├── Standard payment terms
│   ├── Credit limit
│   ├── Preferred incoterms
│   └── Pricing tier
│
├── Interaction History
│   ├── All communications
│   ├── Meeting notes
│   ├── Quotes sent
│   └── Orders placed
│
└── Notes & Flags
    ├── Preferences
    ├── Don'ts (topics/approaches to avoid)
    └── Special circumstances
```

### Customer Classification (A/B/C)

| Class | Criteria | Service Level | Contact Frequency |
|-------|----------|--------------|-------------------|
| **A - Key Account** | Top 20% by revenue, strategic importance | Highest | Weekly minimum |
| **B - Regular** | Regular orders, stable relationship | Standard | Bi-weekly |
| **C - Developing** | Growing potential, occasional orders | Growing | Monthly |
| **D - At Risk** | Declining orders, issues | Urgent attention | As needed |

## Phase 2: Contact Management

### Decision-Making Unit (DMU)

For each customer, map the buying team:

| Role | Name | Title | Email | Influence | Final Decision |
|------|------|-------|-------|-----------|----------------|
| Economic Buyer | [Name] | [Title] | [Email] | Budget approval | Yes |
| Technical Buyer | [Name] | [Title] | [Email] | Technical evaluation | No |
| User | [Name] | [Title] | [Email] | Using the product | No |
| Coach | [Name] | [Title] | [Email] | Internal champion | Supports us |

### Communication Preferences

| Contact | Best Channel | Best Time | Language | Notes |
|---------|-------------|-----------|----------|-------|
| [Name] | Email | Morning (their time) | English | Formal tone |
| [Name] | WhatsApp | Afternoon | Chinese | Casual OK |

## Phase 3: Quote Management

### Quote Lifecycle

```
Draft → Sent → Under Review → Revised → Accepted → Rejected → Expired
         ↓
       Lost (competitor/price)
```

### Quote Template

```
QUOTATION
================================================================================

Quotation No.: [QUO-YYYYMMDD-XXX]
Date: [Date]
Valid Until: [Date + 30 days]

TO:
Company: [Client Company Name]
Attention: [Contact Name]
Email: [Email]

--------------------------------------------------------------------------------
PRODUCTS:
--------------------------------------------------------------------------------

| # | Product | Model/Spec | QTY | Unit | Unit Price | Total |
|---|--------|------------|-----|------|------------|-------|
| 1 | [Product 1] | [Spec] | [X] | pcs | [Price] [Cur] | [Total] |
| 2 | [Product 2] | [Spec] | [X] | pcs | [Price] [Cur] | [Total] |

--------------------------------------------------------------------------------
SUBTOTAL: [Currency] [Amount]
FREIGHT: [Currency] [Amount] ([Incoterm])
TOTAL: [Currency] [Amount]
--------------------------------------------------------------------------------

PRICE TERMS: [FOB/CIF/EXW/DDP]
PAYMENT TERMS: [T/T 30% deposit, 70% before shipment]
LEAD TIME: [X] days after deposit received
LOADING PORT: [Port]
DELIVERY: [X] weeks from order confirmation
PACKING: [Standard export packing / as agreed]

--------------------------------------------------------------------------------
REMARKS:
- Sample available: Yes/No
- Sample cost: [Amount]
- Certification available: [List]
- MOQ may apply for certain specifications

--------------------------------------------------------------------------------
We look forward to your response.

Best regards,
[Your Name]
[Title]
[Company Name]
Tel: [Phone] | Email: [Email] | WeChat: [WeChat ID]
```

### Quote Follow-Up Protocol

| Day | Action | Reason |
|-----|--------|--------|
| Day 3 | Check if received | Confirm email delivery |
| Day 7 | Ask if questions | Show responsiveness |
| Day 14 | Share new info | Add value, stay top of mind |
| Day 21 | Price/margin review | Assess competitiveness |
| Day 30 | Quote expiry notice | Create urgency |
| Day 35 | Revised quote or archive | Close loop |

## Phase 4: Order Management

### Order Flow

```
Inquiry → Quote → Sample → PI (Proforma Invoice) → Order Confirmation → Production → QC → Shipping → Delivery → Invoice → Payment → After-Sales
```

### Proforma Invoice (PI) Template

```
PROFORMA INVOICE
================================================================================

PI No.: [PI-YYYYMMDD-XXX]
Date: [Date]

SELLER:
Company: [Your Company Name]
Address: [Your Address]
Tel: [Phone] | Fax: [Fax]
Email: [Email]

BUYER:
Company: [Client Company]
Address: [Client Address]

--------------------------------------------------------------------------------
ORDER DETAILS:
--------------------------------------------------------------------------------

| # | Description | QTY | Unit | Unit Price | Total |
|---|-------------|-----|------|------------|-------|
| 1 | [Product] | [X] | pcs | [Price] | [Total] |

--------------------------------------------------------------------------------
TOTAL VALUE: [Currency] [Amount] ([Incoterm])

PAYMENT: [T/T 30% deposit, 70% before shipment]
LEAD TIME: [X] days
SHIPPING: [By sea/air/express]
DESTINATION: [Port/City, Country]

--------------------------------------------------------------------------------
BANK DETAILS:
Bank Name: [Bank Name]
Bank Address: [Bank Address]
Account Name: [Account Name]
Account No.: [Account No.]
SWIFT Code: [SWIFT]

--------------------------------------------------------------------------------
Products are exported under export license No.: [XXX]

We confirm this proforma invoice is valid for 30 days from the date above.

Authorized Signature: _______________
Date: _______________

BUYER'S ACCEPTANCE:
We accept the terms and conditions above.

Authorized Signature: _______________
Date: _______________
Company: _______________
```

### Order Tracking Timeline

| Stage | Milestone | Action | Communication |
|-------|-----------|--------|---------------|
| 0 | PI Signed | Confirm order, update CRM | Email confirmation |
| 1 | Deposit Received | Start production tracking | Email receipt |
| 2 | Production Started | Photo/video of production | WeChat/Email |
| 3 | Production 50% | Check QC point | Update timeline |
| 4 | Production Complete | Pre-shipment inspection | Send photos |
| 5 | Goods Ready | Book shipping | Send shipping docs |
| 6 | Shipped | Send B/L, tracking | Email + WeChat |
| 7 | In Transit | Monitor shipment | Update ETA |
| 8 | Arrived | Notify clearance | Email + call |
| 9 | Delivered | Confirm receipt | Phone/WeChat |
| 10 | 30-Day Follow-up | Check satisfaction | Email |
| 11 | 90-Day Follow-up | Request review/referral | Email |

## Phase 5: Customer Health Monitoring

### Key Metrics to Track

| Metric | What It Measures | Warning Threshold |
|--------|-----------------|-------------------|
| Order Frequency | How often they order | No order in [X] months |
| Order Value | Average order size | Declining trend |
| Payment Speed | Days to pay | > 30 days past due |
| Inquiry Response | Time to respond to quotes | Declining engagement |
| Satisfaction | Feedback quality | Negative signals |

### At-Risk Customer Signals

```
⚠️ Warning Signs:
- Order frequency decreasing
- Order size getting smaller
- Ignoring quotes/inquiries
- Not responding to follow-ups
- Switching to competitor
- Payment delays increasing
- Complaints or disputes

🚨 Urgent Action Required:
- Direct phone call
- Schedule meeting/visit
- Offer solution/incentive
- Escalate if needed
```

### Customer Health Score

| Score | Status | Action |
|-------|--------|--------|
| 9-10 | Healthy | Maintain relationship |
| 7-8 | Stable | Monitor, grow |
| 5-6 | At-Risk | Intervention needed |
| <5 | Critical | Immediate action |

## Phase 6: Key Account Management

For A-class customers (Key Accounts):

### Key Account Plan Template

```
# Key Account Plan: [Customer Name]
Period: [Year/Quarter]

## Account Overview
- Since: [Year relationship started]
- Current status: [Active/At-risk/etc.]
- Annual revenue: [Amount]
- Revenue trend: [Growing/Stable/Declining]

## Decision Makers
| Name | Role | Since | Relationship |
|------|------|-------|-------------|
| [Name] | [Title] | [Year] | [Strong/Good/Needs attention] |

## Business Analysis
### Products Supplied
| Product | % of Their Purchases | Your % of Their Volume |
|---------|---------------------|------------------------|
| [Product] | [X]% | [Y]% |

### Competitive Position
- Main competitor: [Name]
- Competitor's share: [X]%
- Your share: [Y]%

## Growth Opportunities
1. [Opportunity 1]
2. [Opportunity 2]
3. [Opportunity 3]

## Risks & Challenges
1. [Risk 1]
2. [Risk 2]

## Action Plan (Next Quarter)
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| [Action 1] | [Name] | [Date] | [X] |
| [Action 2] | [Name] | [Date] | [X] |

## Meeting Schedule
- Regular calls: [Frequency]
- On-site visits: [Frequency]
- Executive sponsor: [Name]
```

## Phase 7: Communication Templates

### Regular Check-In Template

```
Subject: Quick check-in | [Your Company]

Hi [Name],

Hope you're well!

I wanted to touch base to:
1. See how things are going with [current project/product]
2. Check if you have any upcoming requirements
3. Share any updates from our end

Any thoughts on your end? Happy to schedule a call if easier.

Best,
[Your Name]
```

### After Order Delivery

```
Subject: Order [XXXX] delivered — quick follow-up | [Your Company]

Hi [Name],

I wanted to personally follow up after the delivery of your order [XXXX].

Is everything arriving in good condition? Any issues we should know about?

We always appreciate your business and want to make sure you're 100% satisfied.

Looking forward to hearing from you.

Best,
[Your Name]
```

### Relationship Building (Non-Business)

```
Subject: [Industry event] — thought you'd find this interesting

Hi [Name],

[Quick observation or news relevant to their business].

Thought this might be useful/give you something to think about.

Let me know if you'd like to discuss — always happy to connect.

Best,
[Your Name]
```

### Price Increase Notification

```
Subject: Price adjustment notice — effective [Date] | [Your Company]

Dear [Name],

We hope this message finds you well.

Due to [reason: raw material costs / exchange rate / logistics costs], we will need to adjust our pricing effective [Date].

The new prices for your regular orders will be:
| Product | Old Price | New Price | Change |
|---------|-----------|-----------|--------|
| [Product 1] | [X] | [Y] | [+Z%] |

We understand this is [inconvenient/unwelcome news], and we want to assure you that:
- We have worked hard to minimize the increase
- This is our standard pricing for all customers
- We remain committed to providing [quality/service level]

For orders placed before [Date], we can honor current pricing.

Thank you for your understanding and continued partnership.

Best regards,
[Your Name]
[Title] | [Company]
```

### Payment Reminder (Professional)

```
Subject: Payment reminder — Invoice [XXXX] | [Your Company]

Dear [Name],

I hope this email finds you well.

This is a friendly reminder that Invoice [XXXX] dated [Date] for [Currency] [Amount] is due as of [Due Date].

Invoice details:
- Invoice No.: [XXXX]
- Amount Due: [Currency] [Amount]
- Due Date: [Date]

If you have already arranged payment, please disregard this message and accept our thanks.

If you have any questions or need to discuss payment arrangements, please don't hesitate to reach out.

Best regards,
[Your Name]
[Title] | [Company]
Tel: [Phone]
```

## Phase 8: Customer Analytics

### Monthly Customer Report

```
# Customer Management Report — [Month/Year]

## Summary
- Total active customers: [X]
- New customers: [X] (+[X]% vs last month)
- Orders placed: [X]
- Total order value: [Currency] [Amount]
- Average order value: [Currency] [Amount]

## Top 10 Customers by Revenue
| Rank | Customer | Orders | Revenue | vs Last Month |
|------|----------|--------|---------|---------------|
| 1 | [Name] | [X] | [Amount] | [+/-X%] |
| ... | ... | ... | ... | ... |

## At-Risk Customers
| Customer | Risk Signal | Last Order | Action Taken |
|----------|-------------|------------|--------------|
| [Name] | [Signal] | [Date] | [Action] |

## Pending Quotes
| Customer | Quote # | Amount | Sent Date | Status |
|----------|---------|--------|-----------|--------|
| [Name] | [QUO-XXX] | [Amount] | [Date] | Under review |

## This Month's Goals
- [ ] Follow up on pending quotes
- [ ] Reach out to at-risk customers
- [ ] Thank top customers
- [ ] Review payment aging
```

## Quality Standards

1. **Data accuracy**: Keep all customer records up to date — contact info, terms, preferences
2. **Timely follow-up**: Respond to customer communications within 24 hours
3. **Document everything**: Log all significant interactions in the customer record
4. **Consistency**: Apply pricing terms and policies uniformly
5. **Proactive communication**: Don't wait for customers to ask — keep them informed
6. **Personalization**: Remember customer preferences and past interactions

## Common Pitfalls

1. **Neglecting small customers**: Small customers today can become big customers tomorrow
2. **Reactive only**: Don't wait for customers to reach out — be proactive
3. **Losing institutional memory**: Document everything so knowledge isn't lost if staff changes
4. **Price-based only**: Relationship quality often matters more than price
5. **Over-promising**: Never promise what you can't deliver
6. **Neglecting payment terms**: Clear payment terms prevent disputes
7. **No succession plan**: If one person leaves, another should know the customer
