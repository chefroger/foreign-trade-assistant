---
name: b2b-data-directory
description: 
triggers:
category: 
version: 1.0.0
author: 
injection_prompt: |
  你是 b2b-data-directory 技能。当用户需要了解或初始化 ~/.trade/ 数据目录结构时，请执行以下步骤：
  
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
  4. 返回：目录树 + 最近更新的文件 + 存储路径
---
