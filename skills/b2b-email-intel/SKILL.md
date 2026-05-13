---
name: b2b-email-intel
description: 
triggers:
category: 
version: 1.0.0
author: 
injection_prompt: |
  你是 b2b-email-intel 技能。当用户需要调查某个邮箱的背景时（例如"查一下这个邮箱"、"背景调查"、"email intel"），请执行以下步骤：
  
  1. 从对话中提取邮箱地址（格式：xxx@domain.com）
  2. 加载 skill: b2b-email-intel
  3. 调用 email_background_check(邮箱地址)
  4. 返回结构化报告：
     - 平台检测结果（checked_count / found_count）
     - 每个平台：平台名 | 是否注册 | 用户名 | 档案URL | 注册时间
     - 社交档案汇总（GitHub/LinkedIn/Twitter 等）
     - 真实性评估：高/中/低 及依据
     - 备注：哪些平台注册代表该客户可信度高
  
  如果用户只说了"背景调查"但没有提供邮箱，在回复中请用户补充邮箱地址。
---

### ✅ 已找到的注册账号

| 平台 | 账号 | 公开档案 |
|------|------|---------|
| GitHub | johnsmith-dev | https://github.com/johnsmith-dev |
| LinkedIn | John Smith | https://www.linkedin.com/in/johnsmith |
| Twitter | @johnsmith_dev | https://twitter.com/johnsmith_dev |
| Stack Overflow | johnsmith | https://stackoverflow.com/users/johnsmith |
| Instagram | johnsmith_dev | https://www.instagram.com/johnsmith_dev |
| Facebook | John Smith | https://www.facebook.com/johnsmith |
| ZoomInfo | john.smith@techcorp.com | 商务档案 |

### ⚠️ 受限平台（IP 被限制）

| 平台 | 状态 |
|------|------|
| Instagram | 触发了反爬限制 |
| TikTok | 触发了反爬限制 |

### ❌ 未注册的知名平台

Twitter, Instagram, TikTok 等核心社交平台均返回「未注册」。

---

### 📋 汇总分析

**真实性评估**：高
- 在 7 个平台有活跃注册，包括专业社交平台 LinkedIn
- GitHub 账号显示为技术开发者身份
- 未发现虚假邮箱的典型特征（仅注册一两个平台）

**客户画像**：
- **技术背景**：GitHub + Stack Overflow 活跃用户
- **商务活跃**：LinkedIn 有完整职业档案
- **建议切入点**：技术合作 + 产品技术对接

**风险提示**：
- 部分平台受 IP 限速影响，建议更换出口 IP 后再次查询
- 建议同步在 LinkedIn 直接搜索公司名称验证身份
```

## 技术实现

内部使用 [holehe](https://github.com/megadose/holehe) 开源工具，通过以下方式获取信息：

1. **注册接口探测**：向各平台注册接口发送请求，根据响应判断邮箱是否已存在
2. **密码找回泄露**：部分平台在「忘记密码」页面会泄露关联的账号信息
3. **头像/Gravatar**：Gravatar 平台可根据邮箱哈希返回头像 URL

**不发送任何邮件到目标地址**，不触发任何通知，完全静默。

## 与 b2b-lead-generation 的配合

Email Intelligence 是客户开发的第一步：

```
Step 1：Email Intel（本章）
  → 验证邮箱真实性
  → 发现客户活跃的社交档案
  → 初步判断客户类型（技术型/商务型/混合型）

Step 2：b2b-lead-generation
  → 基于发现的 LinkedIn/GitHub 等档案
  → 深度分析客户公司背景
  → 生成定制化开发信
```

## 适用场景

| 场景 | 价值 |
|------|------|
| 收到陌生客户询盘 | 验证邮箱真实性，判断是否为真实活跃买家 |
| 开发信发送前 | 预判客户画像，制定差异化沟通策略 |
| 怀疑虚假询盘 | 发现邮箱仅注册少量低可信平台 |
| 初次接触前 | 发现客户社交档案，准备更有针对性的开场白 |

---
