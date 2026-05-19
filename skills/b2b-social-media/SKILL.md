---
name: b2b-social-media
description: 
triggers:
category: 
version: 1.0.0
author: 
injection_prompt: |
  你是 b2b-social-media 技能。当用户需要制定 Facebook、Instagram、TikTok 或 YouTube 的社媒营销策略时，请执行以下步骤：

  ## 核心原则：客户价值导向（最重要规则！）

  外贸 B2B 的社媒关注者不是来逛网店的——他们是来寻找**能帮自己解决供应链难题的伙伴**。
  每发布一条内容前，先问：**「看到这条的人，会觉得这跟他的工作有关吗？」**

  内容围绕以下四个方向展开（按重要性排序）：
  1. **帮客户避坑**：你见过的行业常见问题、采购陷阱、验货秘诀
  2. **展示你的独到之处**：同行做不到的事——48h 打样？非标定制？实验室级检测？目标国认证一条龙？
  3. **客户成功故事**：你帮客户解决了什么棘手问题、创造了什么价值
  4. **建立信任**：工厂实拍、团队日常、质量管控体系、认证资质

  **绝对禁止**：
  - 纯产品参数贴（规格/价格/MOQ 罗列 — 做产品目录，不是社媒内容）
  - 「质量好价格低服务优」一类的空洞话术
  - 重复发布同一产品的照片

  1. 加载 skill: b2b-social-media
  2. 确认平台组合（可多平台）：
     - Facebook：B2B 长文、案例分析、行业洞察、Group 运营
     - Instagram：工厂纪实、品质瞬间、客户故事、Reels 过程展示
     - TikTok：采购冷知识、行业避坑、工厂日常、产品背后的技术
     - YouTube：客户案例纪录片、品质管控全流程、行业趋势分析
  3. 内容日历（周计划）：
     - 建议发布频率（每个平台）
     - 内容类型配比（客户价值 70% / 信任建设 20% / 公司动态 10%）
     - 发布时间（按目标市场时区）
  4. 每条帖子包含：
     - 标题/文案（以客户视角切入，不含产品参数堆砌）
     - 配图/视频描述
     - CTA（引发讨论/索要资料/访问链接）
  5. 竞品分析：找出3个同行动议参考的账号，分析其内容策略
  6. 返回：完整月历（每条帖子含：日期/平台/内容主题/核心价值点）
---

Platform: [Facebook/Instagram/TikTok/YouTube]
Account Name: [Competitor's account]
Followers: [Number]
Posting Frequency: [Posts per week]

Content Analysis:
- Content Types: [What % video/image/article]
- Topics: [What are they posting about]
- Tone: [Professional/casual/fun]
- Hashtags Used: [List top 5-10]
- Engagement Rate: [Likes/comments/shares avg]

What They Do Well:
1. [Specific post/content that works]

What They Don't Do:
1. [Gap you can exploit]

Content Gaps:
- [Topics not covered by competitors]
- [Questions unanswered in their content]
```

### Output: Competitor Summary Table

| Platform | Account | Strength | Weakness | Opportunity |
|----------|---------|---------|---------|------------|
| FB | @competitor1 | Strong video content | Inconsistent posting | [Your gap] |
| Insta | @competitor2 | Great product photos | No behind-the-scenes | Factory content |
| TikTok | @competitor3 | [Their strength] | [Their weakness] | [Your opportunity] |

## Phase 2: Content Strategy by Platform

### Facebook B2B Strategy

**Content Mix (Recommended)**:
- 35% 帮客户避坑 / 行业洞察（采购陷阱、验货技巧、认证解读、趋势分析）
- 25% 你的独到服务能力（非标定制案例、打样速度、检测实力、目标国经验）
- 20% 客户成功故事（你帮客户解决了什么难题、具体省了多少钱/时间/风险）
- 15% 互动讨论（投票、提问、行业话题讨论）
- 5% 公司动态（展会、新认证、团队建设）

**Best Practices**:
- Post during business hours (8-10 AM, 2-4 PM local time)
- Use Facebook Live for Q&A sessions or factory walk-throughs
- Join relevant industry groups and participate
- Share long-form articles (800+ words) for thought leadership
- Use high-quality images (1200 x 630 px for feed)

**Facebook-Specific Hashtags**:
```
#B2B #ForeignTrade #Manufacturing #Sourcing #SupplyChain #Exporter
```

### Instagram B2B Strategy

**Content Mix (Recommended)**:
- 25% 客户想知道的质量细节（检测过程、验货实拍、出厂前最后一关）
- 25% 差异化服务展示（定制包装、非标件的处理、特殊需求响应）
- 20% 工厂纪实（生产工艺、原材料把控、团队协作）
- 20% 客户反馈 / 成功案例（帮客户省了多少、解决了什么）
- 10% 互动（Stories 投票、问答、行业讨论）

**Best Practices**:
- Post at peak times (11 AM-1 PM, 7-9 PM)
- Use Instagram Reels for short product demos (15-30s)
- Use Stories for daily behind-the-scenes content
- Highlight relevant Stories highlights (Products, Factory, Testimonials)
- Maintain consistent visual aesthetic (color palette, filters)

**Instagram-Specific Hashtags**:
```
#B2B #[Product] #[Industry] #[Manufacturing] #Exporter #Sourcing #[Product] #[Country]Export #Factory #[YourBrand]
```

**Hashtag Strategy**:
- Use 8-15 hashtags per post (mix of large/mid/small)
- Large: 500K+ posts (general) — #B2B, #Manufacturing
- Mid: 50K-500K posts — #[Product], #[Industry]
- Small: <50K posts — #[YourNiche], #[YourBrand]

### TikTok B2B Strategy

**Content Mix (Recommended)**:
- 35% 采购避坑 / 行业冷知识（买家最常踩的坑、验货盲区、谈判技巧）
- 25% 工厂纪实（真实生产线、质量问题怎么拦截、急单怎么处理）
- 25% 独到服务揭秘（你的特殊工艺、非标定制能力、加急流程）
- 15% 客户案例 / 行业趋势（用有趣的方式讲述）

**Best Practices**:
- Post 1-3x daily for best reach
- Hook viewers in first 2 seconds
- Use trending sounds/music
- Add text overlays for key points
- Always include a CTA (follow, comment, visit link)
- Duet/react to industry content

**TikTok Video Structure**:
```
0-2s: HOOK — grab attention immediately
2-5s: INTRO — who you are, what you'll show
5-30s: MAIN CONTENT — product/factory/process
30-45s: VALUE — key takeaway or benefit
45-60s: CTA — follow, comment, link in bio
```

**TikTok Captions**:
```
For factory tour:
"POV: You're visiting your supplier's factory in China 🇨🇳

Things we found surprising...

#factory #manufacturing #sourcing #chinatrip #B2B #Exporter"

For product demo:
"3 things about [product] most buyers don't know 👇

[1] [Fact]
[2] [Fact]
[3] [Fact]

Comment what you want to see next! 👇

#[product] #[industry] #B2B #manufacturing #sourcing #Exporter"
```

### YouTube B2B Strategy

**Content Mix (Recommended)**:
- 35% 客户案例纪录片（帮客户解决了什么棘手问题、全过程记录）
- 30% 品质管控全流程（从原材料进厂到出货检验的完整链路）
- 20% 行业趋势分析 / 采购指南（如何评估供应商、如何避免常见坑）
- 15% 工厂与团队纪实（真实的人和流程，不是摆拍）

**Best Practices**:
- Consistent upload schedule (same day/time each week)
- Professional but authentic production quality
- SEO optimization: titles, descriptions, tags, thumbnails
- Create playlists by content type
- End screens and cards for other videos
- Respond to all comments

**YouTube Content Ideas**:
1. "A Day in the Life of a [Your Product] Factory"
2. "[Product] Manufacturing Process: From Raw Material to Package"
3. "How We Ensure Quality Control: Our 5-Step Inspection Process"
4. "[Product] vs. [Competitor Product]: Key Differences"
5. "Top 5 Things to Consider When Sourcing [Product] from China"
6. "Client Success Story: How [Client] Saved [X]% on [Product]"
7. "Complete [Product] Product Tour"

## Phase 3: Content Calendar Template

### Weekly Content Calendar

| Day | Platform | Content Type | Topic | Caption | Assets Needed |
|-----|----------|-------------|-------|---------|--------------|
| Mon | FB | Article/Industry insight | [Topic] | [Caption] | Image |
| Mon | Insta | Reel | Product demo | [Caption] | Video |
| Tue | TikTok | Factory tour | Behind-the-scenes | [Caption] | Video |
| Tue | FB | Poll/Question | Engagement | [Question] | — |
| Wed | Insta | Feed post | Product showcase | [Caption] | Photo |
| Wed | YouTube | Long video | Product tutorial | [Title] | Video |
| Thu | TikTok | Trending sound | [Adapt to B2B] | [Caption] | Video |
| Thu | FB | Behind-the-scenes | Team/culture | [Caption] | Photo/Video |
| Fri | Insta | Story | Weekly recap | [Content] | — |
| Fri | TikTok | Quick tip | Industry tip | [Caption] | Video |
| Sat | FB | Testimonial | Client story | [Caption] | Photo |
| Sun | All | Rest/Plan | Plan next week | — | — |

### Monthly Content Calendar (Sample)

```
Week 1: Brand Awareness
- Mon: Industry insight article (FB)
- Tue: Product Reel (Insta)
- Wed: Factory tour (TikTok)
- Thu: How-to video (YouTube)
- Fri: Team spotlight (FB/Insta)

Week 2: Product Focus
- Mon: Product comparison (FB)
- Tue: Product close-up (Insta)
- Wed: Product demo (TikTok)
- Thu: Product specs article (FB)
- Fri: Customer testimonial (All)

Week 3: Engagement & Education
- Mon: Industry poll (FB)
- Tue: Educational Reel (Insta)
- Wed: FAQ video (TikTok)
- Thu: Industry statistics (FB)
- Fri: Engagement post (All)

Week 4: Trust Building
- Mon: Quality control content (FB)
- Tue: Certification showcase (Insta)
- Wed: Client success story (YouTube)
- Thu: Team appreciation (TikTok)
- Fri: Monthly roundup (FB)
```

## Phase 4: Content Templates

### 客户价值帖（替代产品展示帖）

不用产品参数堆砌，而是用客户视角：这个能力帮客户省了什么心？

```
[高质量图片/视频 — 展示服务过程、检测环节、特殊工艺，而非纯产品摆拍]

🔍 [一个客户常遇到的问题，用问句开头]
比如："What's the #1 reason your shipments get rejected at customs?"

大多数供应商会告诉你 [常见但不靠谱的做法]

我们做的不一样：
→ [你的独特做法 1] — 这意味着客户不用 [省了什么麻烦]
→ [你的独特做法 2] — 这意味着客户能 [获得什么好处]
→ [你的独特做法 3] — 这意味着客户不会 [避免什么风险]

这不是我们"服务好"——这是 9 年来被客户逼出来的标准流程。

💬 你们遇到过这个问题吗？评论区聊聊

#SupplyChain #QualityControl #B2B #Manufacturing #Sourcing
```

### Behind-the-Scenes Post

```
Ever wonder how [product] gets made? 👀

Take a peek inside our factory:

[1] [Step 1 description]
[2] [Step 2 description]
[3] [Step 3 description]

Every step is carefully monitored to ensure the highest quality [product] for our customers.

🔗 Link in bio to see our full production process!

#[Factory] #[Manufacturing] #[Product] #[Industry] #BehindTheScenes #QualityControl #B2B
```

### Client Testimonial Post

```
"Don't just take our word for it — here's what our client [Name] has to say about working with us:

"[Testimonial quote]"

— [Name], [Title], [Company]

Ready to experience the difference? Let's talk! 💬

#[Testimonial] #[Client] #[B2B] #[Product] #[Industry]
```

### 行业洞察 / 采购避坑帖

```
📊 [一个令人意外的行业数据或现象]

大多数 [industry] 采购经理不知道的是：[揭露一个常见盲点]

上周一个客户告诉我，他之前的供应商 [踩坑经历]，结果 [损失了什么]。
后来我们帮他 [你怎么解决的]，三个月后 [量化的改善结果]。

如果你也在采购 [产品类型]，建议问供应商这三个问题：
1. [能揭示供应商真实水平的问题]
2. [同上]
3. [同上]

如果对方答不上来——你懂的 👀

👇 你们采购时最踩过什么坑？评论区见

#SupplyChain #Procurement #B2B #Manufacturing #Sourcing
```

### Engagement Poll/Question (FB/Insta)

```
Quick question for our [industry] professionals: 👇

[Question related to your product/industry]

A) [Option A]
B) [Option B]
C) [Option C]
D) [Other - Comment!]

👇 Cast your vote in the comments!

We'd love to hear your thoughts!

#[Poll] #[Community] #[B2B] #[Industry]
```

### TikTok Trending Sound Adaptation

```
Caption Template:
"POV: [Relatable B2B scenario] 😤

[3-point list or quick rant]

Tag a friend who needs to see this! 👇

#[TrendSound] #[Product] #[Industry] #[B2B] #Manufacturing #Exporter #Sourcing #[YourCountry]
```

## Phase 5: Hashtag Research

### Industry Hashtag Discovery Method

1. Search for top accounts in your industry
2. Note their top hashtags (copy their best performing)
3. Use Instagram/TikTok search to find related tags
4. Check hashtag follower counts before using
5. Mix large, medium, and small hashtags

### Hashtag Categories

**Broad B2B** (Use 2-3):
```
#B2B #B2BMarketing #Business #InternationalTrade #Export #Import #Manufacturing #Wholesale
```

**Product-Specific** (Use 3-5):
```
#[Product] #[Product]Manufacturer #[Product]Supplier #[YourProduct] #[Industry] #[YourIndustry]
```

**Platform-Specific** (Use 2-3):
```
#[Platform] #InstaBusiness #TikTokMadeMeBuyIt #YouTube #FB4B
```

**Location** (Use 1-2):
```
#[YourCountry]Export #[YourCountry]Manufacturing #[YourCity] #MadeIn[Country]
```

**Branded** (Use 1):
```
#[YourBrand] #YourBrandName
```

## Quality Standards

1. **No placeholders**: All content must be complete. No "XXX", "[insert]", "[TBD]", "Lorem ipsum"
2. **Visual-first**: B2B social media still needs quality visuals — invest in product photography
3. **Platform-native**: Adapt content for each platform's format and audience expectations
4. **Consistent brand voice**: Professional but approachable. Never too casual for B2B
5. **Clear CTAs**: Every post should tell the audience what to do next (comment, DM, visit link, etc.)
6. **Authenticity**: Show real factory, real team, real products. B2B buyers value transparency
7. **Engagement**: Respond to comments within 24 hours to build relationships

## Common Pitfalls

1. **产品广告当内容** 🔴 **最致命**: 社媒不是产品目录。关注你的买家想看的是「谁最能帮我解决问题」，不是「谁的产品参数最详细」
2. **空洞话术**: 不说"质量好服务优"，说"每批货有人蹲在产线盯、出货前拍视频给你确认"
3. **Ignoring platform differences**: Don't post the same content everywhere — adapt for each platform
4. **Inconsistent posting**: Use content calendar to maintain regular posting schedule
5. **Poor visuals**: Grainy photos and shaky videos hurt credibility. Invest in basic equipment
6. **No strategy**: Random posting without analysis and planning wastes effort
7. **Neglecting analytics**: Track what works and what doesn't. Adjust strategy based on data
8. **Copying competitors exactly**: Learn from them, but find your unique angle and voice
