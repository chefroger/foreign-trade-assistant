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

## Reporting

Email: <roger.lau@protonmail.com>
