# Security Policy

## HERMES_YOLO_MODE

Foreign Trade Assistant runs with `HERMES_YOLO_MODE=true`. AI Agent tool calls
(read/write files, terminal commands) execute **without human approval**.

### Why

The target users are international trade salespeople who cannot evaluate whether
an AI tool call is safe. Prompting them for approval on every action would make
the product unusable.

### Mitigations

1. **Network isolation**: Bind to `127.0.0.1` only. Do not expose to LAN/WAN.
2. **Firewall**: Ensure port 9119 is not reachable from outside.
3. **API Key safety**: Store in `~/.hermes/.env` with `chmod 600`.
4. **Regular backups**: Back up `~/.trade/` and desktop work directories.
5. **Least privilege**: Run as a regular user, never as root.

### If you find a vulnerability

Please open a GitHub Issue with:
- Steps to reproduce
- Affected version
- Impact assessment

We do not currently run a bug bounty program.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.4.x   | ✅ Active |
| < 0.4   | ❌ Unsupported |

## 法律与合规声明

### 第三方服务使用风险

本软件集成了以下第三方工具，使用前请注意相关条款：

**holehe（邮箱平台注册检测）**
- `email_intel.py` 通过 holehe 检测邮箱在 120+ 网站的注册情况
- GitHub、LinkedIn、Twitter 等平台的服务条款（ToS）通常禁止自动化查询
- 建议：仅对单个业务联系人做背调，不要用于大规模批量查询
- 如被平台检测到异常流量，可能面临封号或法律风险

**OFAC/UN/EU 制裁名单查询**
- `osint/sanctions.py` 从 ofac.treasury.gov 等政府网站下载制裁数据
- 美国政府数据属于 Public Domain，无版权问题
- 制裁名单结果仅供参考，不构成法律意见
- 建议拒绝与制裁名单上的实体交易，必要时咨询法律部门

**WHOIS / DNS 查询**
- `osint/whois.py` 和 `osint/email_verify.py` 使用 IETF 标准协议
- 部分 WHOIS 服务器（如 .cn）禁止自动化查询，请合理控制频率
- DNS 查询使用公共 DNS 服务器（8.8.8.8 / 1.1.1.1），受各服务商 ToS 约束

### 许可证兼容性

| 组件 | 许可证 | 兼容性 |
|------|--------|:------:|
| Foreign Trade Assistant | MIT | — |
| Hermes Agent | MIT | ✅ 完全兼容 |
| FastAPI / uvicorn / beautifulsoup4 | MIT / BSD | ✅ 完全兼容 |
| PyMuPDF | AGPL | ⚠️ pip install 使用无传染风险；PyInstaller 打包分发时需评估 |
| openpyxl / python-docx / python-pptx | MIT | ✅ 完全兼容 |

### 数据合规

- 所有用户数据存储在本地（`~/.trade/`），不上传任何云端服务器
- LLM API 调用仅发送用户提问内容，不传输客户身份信息
- 建议定期备份后从 `~/.hermes/.env` 移除不再使用的 API Key

## Reporting

Email: <lauroge@gmail.com>
