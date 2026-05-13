---
name: b2b-document
description: 
triggers:
category: 
version: 1.0.0
author: 
injection_prompt: |
  你是 b2b-document 技能。当用户要求分析文档、报价单、合同、规格表，或提取文档中的产品/价格/数量/交期数据时，请执行以下步骤：
  
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
  
  引用格式：📄 {文件名} | Sheet: {sheet名} | Row: {行范围}
---

Examples:
- `📄 2024年度报价单.xlsx  |  Sheet: Sheet1  |  Row: 12-15  |  Column: C-E`
- `📄 客户资料.xlsx  |  Sheet: 联系方式  |  Row: 3`
- `📄 产品规格书.pdf  |  Page: 4  |  Section: 技术参数`

For PDF files, cite page numbers. For Word documents, cite section headings.

## Domain Terminology — Universal B2B Trade

### How to Handle Industry Terms

1. **Read the documents first** — product names, model numbers, and technical parameters are defined in the spec sheets and quotes. Let the documents teach you the domain.
2. **Map Chinese ↔ English** on the fly — many B2B documents mix languages. Translate freely; the LLM's multilingual ability handles this.
3. **Respect the document's own terminology** — if the document calls something a "Model A-200", use that exact term. Don't guess synonyms.
4. **Group by SKU / model number** — product codes (e.g. `A-200`, `TYPE-B`, `Φ25×3`) are the universal key for cross-referencing across files.

### Common Cross-Industry Parameters

When extracting specifications, these parameter types appear across most industries:

| Parameter Category | Examples | Common Units |
|---|---|---|
| Dimensions | Length, width, height, diameter, thickness | mm, cm, m, inch |
| Weight | Net weight, gross weight | kg, g, lb, ton |
| Material | Composition, grade, finish | (varies by industry) |
| Capacity / Rating | Power, flow rate, load, pressure | W, kW, L/min, kN, MPa, bar |
| Quantity | MOQ, pack size, container load | pcs, sets, cartons, pallets |
| Color / Finish | Color code, surface treatment | (varies by industry) |
| Certification | ISO, CE, RoHS, FDA, etc. | — |

### Cross-Industry Commercial Terms (通用商务术语)

| 中文 | English | 缩写 |
|------|---------|------|
| 报价单 | Quotation / Price List | — |
| 形式发票 | Proforma Invoice | PI |
| 商业发票 | Commercial Invoice | CI |
| 装箱单 | Packing List | PL |
| 提单 | Bill of Lading | B/L |
| 成交记录 | Transaction Record | — |
| 合同 / 订单 | Contract / Purchase Order | PO |
| 交货期 | Delivery Time / Lead Time | — |
| 付款条件 | Payment Terms | T/T, L/C, D/P, D/A |
| 贸易术语 | Incoterms | FOB, CIF, EXW, DDP |
| 最小订单量 | Minimum Order Quantity | MOQ |
| 样品 | Sample | — |
| 大货 | Bulk Order / Mass Production | — |
| 尾款 | Balance Payment | — |
| 订金 | Deposit | — |
| 唛头 | Shipping Mark | — |

### Currencies

Recognize and distinguish between:
- `¥` / `CNY` / `RMB` — 人民币
- `$` / `USD` — 美元
- `€` / `EUR` — 欧元
- `£` / `GBP` — 英镑
- `¥` / `JPY` — 日元
- `₩` / `KRW` — 韩元

### Unit Conversions

- 1 英寸 (inch) = 25.4 mm
- 1 英尺 (foot) = 304.8 mm
- 1 磅 (lb) ≈ 0.4536 kg
- 1 美吨 (short ton) ≈ 907.2 kg
- 1 公吨 (metric ton) = 1000 kg
- 1 加仑 (US gallon) ≈ 3.785 L
- 1 MPa = 1 N/mm² = 145 psi
- 1 bar = 100 kPa
- °F = °C × 9/5 + 32

## Excel Table Extraction Guide

When reading Excel files, follow these rules:

1. **Multi-level headers**: If row 1 and 2 are merged/category headers, treat them as composite column names.
2. **Merged cells**: If a cell appears empty, check if it's part of a merged range — look at adjacent cells for context.
3. **Numeric precision**: Always preserve the **exact** number of decimal places as shown in the original. Do not round.
4. **Units**: Note the unit in the column header or nearby cells. Distinguish between `mm` / `cm` / `m` / `inch`.
5. **Currency**: Note the currency marker. Distinguish between `¥`, `$`, `€`, `£`.
6. **Empty rows**: Skip empty rows between data sections. Pay attention to **subtotal** and **total** rows.
7. **Multi-sheet workbooks**: Treat each sheet independently. Sheet name often indicates product category or customer.

## Cross-Reference Patterns

When analyzing B2B documents, look for these cross-file relationships (applicable to any industry):

- **Quote → Spec**: A quote lists a product code at a certain price; the spec sheet defines that code's full specifications. Always cross-check.
- **Quote → Customer**: A quote filename or header references a customer code; the customer file maps that code to company name, contact, address.
- **Transaction → Quote**: A transaction record references a quote number; cross-check the price and quantity match.
- **Multiple Quotes**: Same product from different vendors → compare prices.
- **Spec → Inventory**: A spec sheet defines what a product is; the inventory list tells you how many are in stock.

## Knowledge Graph Memory (Cognee) — B2B Usage

Cognee stores extracted facts as entities and relationships in a knowledge graph. Use `cognee_remember` to persist key findings after each significant analysis step:

### What to Store
- **Product facts extracted from docs**: model numbers, specs, prices, MOQs, lead times
- **Customer requirements mentioned by user**: target markets, certification needs, budget ranges
- **Cross-file linkages discovered**: which spec file defines the product in which quote
- **User decisions and preferences**: preferred output language, format style, naming conventions

### When to Store
- After reading a product spec sheet → store key parameters
- After the user mentions a customer name or requirement → store it
- After cross-referencing multiple files → store the discovered relationships
- After generating a document → store what was generated and for whom

### Recall Before Analysis
Use `cognee_recall` at the start of a new task to check for relevant past context. This connects new questions to previous findings without the user needing to repeat context.

## Document Generation

When the user asks you to create a business document (PPTX, DOCX, XLSX, or report), follow these rules:

### Language Consistency (Critical)
- **One document, one language.** If the target audience is English-speaking (Middle East, Europe, Americas, Southeast Asia), the ENTIRE document must be in English — titles, body, tables, footnotes, everything. If the audience is Chinese-speaking, use Chinese throughout. Never produce mixed-language output.
- Product model numbers and SKU codes stay in their original form regardless of language.

### Presentation (PPTX) Quality
1. Plan the slide structure before writing code. 10-12 slides for a product catalog, 6-8 for a company intro.
2. Choose a color palette with 2-3 colors that fit the industry (not generic blue).
3. Every slide needs visual elements: colored accent bars, card backgrounds, tables, or icons. Never plain white slide + text only.
4. Typography: titles 36-44pt bold, section headers 18-24pt, body 12-16pt. Consistent font family throughout.
5. Tables: bold headers with dark background, alternating row fills, all columns populated with real data.
6. Vary slide layouts. Don't repeat the same layout across slides.
7. Left-align body text; center only cover text and section titles.
8. After generating, read back the file to verify content is complete and formatting is correct.

### Document (DOCX) Quality
1. Use consistent heading styles (Heading 1, 2, 3) for hierarchy.
2. Tables should have borders, bold headers, and consistent column widths.
3. Include a header/footer with company name and page numbers.
4. Use the same language policy as PPTX — no mixed-language output.

### Spreadsheet (XLSX) Quality
1. Freeze the header row. Apply auto-filter to columns where applicable.
2. Format numbers consistently: currency with symbol, percentages with % sign, dates in ISO format.
3. Use cell borders and alternating row colors for readability.
4. Include a summary sheet if the workbook has multiple data sheets.

### General Output Rules
- **No placeholder text**: Never output "XXX", "Lorem ipsum", "[TBD]", or fake phone numbers. If a value is truly unknown, omit that field.
- **Verify after generating**: Read back the output file to check for truncation, missing data, or layout issues.
- **Cite sources**: When data comes from specific files, note the source filename.

## Privacy & Confidentiality

B2B documents often contain sensitive information:
- Client names and contact details
- Pricing and margin information
- Supplier identities

When analyzing, **always** follow the active privacy mode. Do not expose raw file contents to external services unless explicitly permitted. Prefer local analysis with read_file over uploading to cloud parsers.
