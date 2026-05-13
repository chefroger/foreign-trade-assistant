# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Foreign Trade Assistant — a B2B Q&A application for trade/manufacturing sales teams. A FastAPI server wrapping **Hermes Agent** (AI engine from `chefroger/hermes-agent`) with a custom business layer (multi-company document libraries, customers, chat memory, skill routing) and a single-page chat UI.

## Commands

```bash
# Initialize database (first time or after schema changes)
python -m trade.database

# Start server
python server.py                    # default http://127.0.0.1:9119/trade
python server.py --port 8080
python server.py --no-browser

# Install (editable) + install B2B skills into Hermes
pip install -e .
install-trade-skills

# Pre-install compatibility check
python pre_install_check.py

# Smoke-test individual modules
python -m trade.database
python -m trade.library
python -m trade.customer
python -m trade.chat_memory
```

This project has **no test suite** and **no linter/formatter configured**.

## Architecture

```
static/trade_chat.html          Chat SPA (vanilla JS, served at /trade)
        │
        ▼
server.py                       FastAPI entry point
  ├── /trade                    Injects session token into SPA HTML
  ├── /api/trade/*              Mounts trade.api router
  └── /api/status               Health check
        │
        ▼
trade/api.py                    REST API router — all B2B endpoints
  ├── /companies/*              Multi-company CRUD + onboarding
  ├── /libraries/*              Document library CRUD + file upload
  ├── /customers/*              Customer CRUD + library linking
  ├── /conversations/*          Chat log CRUD
  ├── /chat                     Sync chat (blocks up to 10 min)
  ├── /chat/stream              SSE streaming with tool progress events
  ├── /memory/*                 Hindsight long-term memory status/recall
  └── /models/providers         LLM provider listing
        │
        ├─ trade/helpers.py     Provider check, agent kwargs, query builder
        │     ├─ trade/prompts.py     System prompt loader (file → DB → code fallback)
        │     │     └─ trade/prompt.py   TRADE_SYSTEM_PROMPT (B2B agent personality)
        │     └─ trade/skill_router.py  Keyword-based skill auto-detection + query augmentation
        │
        ├─ trade/database.py    SQLite connection + schema (data/trade.db)
        │     ├─ trade/company.py       Multi-company CRUD + ~/.trade/ data dir management
        │     ├─ trade/library.py       Document library CRUD
        │     ├─ trade/customer.py      Customer CRUD + library associations
        │     └─ trade/chat_memory.py   Conversation log + Hindsight bridge
        │           └─ trade/memory.py  Hindsight long-term memory client
        │
        ├─ trade/onboarding.py  First-run wizard (create company + agent identity in one step)
        ├─ trade/osint.py       B2B due-diligence: WHOIS, sanctions, email verification, tech stack
        ├─ trade/email_intel.py Email background check (120+ platform detection)
        └─ trade/post_install.py Skill installation into ~/.hermes/skills/
```

## Key Design Decisions

1. **Hermes Agent is an external dependency** (not vendored). Version is pinned in `pyproject.toml` and checked at startup (>=0.12.0, <0.14.0). Compatibility matrix in `COMPATIBILITY.md`.

2. **Session token pattern**: Server generates a random `X-Hermes-Session-Token` on startup, injects it into served HTML. The SPA uses this for API auth — same pattern as Hermes dashboard.

3. **Dual chat endpoints**: `/chat` is synchronous (thread pool + 600s timeout); `/chat/stream` uses SSE to emit `tool_start`, `tool_complete`, `thinking`, `response`, `error`, `done` events for real-time tool progress in the UI.

4. **Multi-company isolation via `X-Company-ID` header**. Every business-data endpoint requires this header. `_require_company()` validates the company exists and is active. Database queries always filter by `company_id`.

5. **Document libraries = filesystem directories**. Each library has a `root_path` pointing to a real directory. The AI agent uses `read_file` / `list_dir` tools to analyze files.

6. **Skill auto-routing**: `trade/skill_router.py` intercepts every query via `build_query()` and uses keyword/regex matching against 13 b2b-* skill trigger lists. When matched, it injects a `[SKILL AUGMENTATION]` block with the skill's injection_prompt (loaded from SKILL.md frontmatter, with mtime caching). No match → pass-through with zero added latency.

7. **Prompt resolution chain** (trade/prompts.py): Company identity file (~/.trade/companies/{slug}/agent_identity.md) → DB agent_identity_md field → global system.md → code fallback (TRADE_SYSTEM_PROMPT). Files are mtime-cached for performance.

8. **Hindsight is optional**. `trade/memory.py` gracefully degrades to no-ops if `hindsight_client` is not installed. Also writes to Hermes native memory (~/.hermes/memories/MEMORY.md) which always works.

9. **Spare columns pattern**: All DB tables have `extra1/extra2/extra3` TEXT columns (storing JSON) for future schema extensions without ALTER TABLE. `_add_spare_columns()` is idempotent across all tables.

10. **Onboarding flow**: `POST /api/trade/onboarding/first-company` atomically creates a company + configures agent identity. Protected by an in-memory flag that checks DB for existing active companies.

## Hermes Coupling Points

Trade depends on these Hermes internals (watch on Hermes upgrades):
- `run_agent.AIAgent` — the AI agent class (imported dynamically in chat endpoints)
- `hermes_cli.config.load_config` — reads `~/.hermes/config.yaml`
- `hermes_cli.auth.PROVIDER_REGISTRY` — available LLM providers
- `hermes_cli.env_loader.load_hermes_dotenv` — loads `~/.hermes/.env`
- `hermes_cli.models.name_to_models` — provider-to-models mapping
- `hermes_constants.get_hermes_home` — resolves `~/.hermes` path
- Cognee knowledge graph (tools `cognee_remember` / `cognee_recall` referenced in system prompt)

## Runtime Data Layout

```
~/.hermes/skills/               Skills installed by install-trade-skills
  ├── b2b-document/
  ├── b2b-platform/
  └── ... (13 b2b-* skills)
~/.trade/                       User data created on first company init
  ├── config.yaml
  ├── prompts/system.md
  └── companies/{slug}/
      ├── agent-identity.md
      ├── company-profile.md
      ├── products.md
      └── ...
```

## Code Annotation Standards

Every function must have a Chinese docstring. Every if-branch must have a comment explaining the business logic. Complex list/dict comprehensions should be split with inline comments. Sections separated by banner comments (`# ====`).

These standards are described in detail in the existing `.claude.md` file.
