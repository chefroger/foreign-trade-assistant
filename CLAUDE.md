# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Foreign Trade Assistant — a B2B Q&A application for trade/manufacturing sales teams. A FastAPI server wrapping **Hermes Agent** (AI engine from `NousResearch/hermes-agent`) with a custom business layer (multi-company document libraries, customers, chat memory, skill routing) and a single-page chat UI.

## Commands

```bash
# Start server (also auto-starts Hermes Gateway for cron scheduling)
python server.py                    # default http://127.0.0.1:9119/trade
python server.py --port 8080
python server.py --no-browser
python server.py --no-gateway       # skip auto-launching Hermes Gateway

# Install (editable) + install B2B skills into Hermes
pip install -e ".[dev]"
install-trade-skills                # copy 14 skills from package to ~/.hermes/skills/

# CLI entry points (from pyproject.toml console scripts)
trade                               # shortcut for python server.py
trade-skills-update                 # fetch latest SKILL.md from GitHub main branch
trade-update                        # git pull + pip install + skills + db
trade-backup                        # backup ~/.trade/ data to tar.gz

# Pre-install compatibility check
python pre_install_check.py

# Initialize/check database
python -m trade.database
```

## Testing & Linting

```bash
# Run all tests (asyncio_mode=auto, 127 tests)
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_business.py -v

# Run a single test
python -m pytest tests/test_business.py::test_function_name -v

# Lint
ruff check .
ruff check --fix .                 # auto-fix

# Test coverage
coverage run -m pytest tests/ -v
coverage report
```

Tests use temporary databases (monkeypatch `_get_db_path`), no production data is touched. `asyncio_mode=auto` handles async test functions automatically.

## Architecture

```
static/trade_chat.html          Chat SPA (vanilla JS, served at /trade)
        │
        ▼
server.py                       FastAPI entry point
  ├── /trade                    Injects session token into SPA HTML
  ├── /api/trade/*              Mounts trade.api router
  ├── /api/status               Health check
        │
        ▼
trade/api/__init__.py           FastAPI router aggregator — all B2B endpoints
  ├── trade/api/companies.py     /companies/*     Multi-company CRUD
  ├── trade/api/libraries.py     /libraries/*     Document library CRUD + file upload
  ├── trade/api/customers.py     /customers/*     Customer CRUD + library linking
  ├── trade/api/conversations.py /conversations/* Chat log CRUD
  ├── trade/api/chat.py          /chat (sync) + /chat/stream (SSE with tool progress)
  ├── trade/api/memory.py        /memory/*        Hindsight long-term memory + LLM providers
  ├── trade/api/onboarding.py    /onboarding/*    First-run wizard
  ├── trade/api/cron.py          /cron/*          Scheduled task automation
  ├── trade/api/deps.py          Session token validation + _require_company()
  └── trade/api/models.py        Pydantic request/response models
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
        ├─ trade/osint/         B2B due-diligence (6-layer subpackage)
        │     ├── orchestrator.py  osint_full_check() main entry
        │     ├── whois.py         Layer 2: WHOIS domain lookup
        │     ├── email_verify.py  Layer 3: corporate vs personal email
        │     ├── sanctions.py     Layer 4: OFAC/UN/EU sanctions screening
        │     ├── tech_stack.py    Layer 5: tech stack detection
        │     ├── linkedin_verify.py Layer 6: LinkedIn verification
        │     ├── scoring.py       Risk score + recommendation
        │     └── constants.py     Shared constants
        ├─ trade/email_intel.py Email background check (120+ platform detection via holehe)
        ├─ trade/skill_registry.py 14 skill definitions (pure data — triggers, aliases, formats)
        └─ trade/post_install.py Skill installation + CLI commands (update/backup)
```

## Key Design Decisions

1. **Hermes Agent is an external dependency** (not vendored). Version pinned to `v2026.5.16` (0.14.0) in `pyproject.toml`. Compatibility matrix in `COMPATIBILITY.md`.

2. **Session token pattern**: Server generates a random `X-Hermes-Session-Token` on startup, injects it into served HTML. The SPA uses this for API auth — same pattern as Hermes dashboard.

3. **Dual chat endpoints**: `/chat` is synchronous (thread pool + 600s timeout); `/chat/stream` uses SSE to emit `tool_start`, `tool_complete`, `thinking`, `response`, `error`, `done` events for real-time tool progress in the UI.

4. **Multi-company isolation via `X-Company-ID` header**. Every business-data endpoint requires this header. `_require_company()` validates the company exists and is active. Database queries always filter by `company_id`.

5. **Document libraries = filesystem directories**. Each library has a `root_path` pointing to a real directory. The AI agent uses `read_file` / `list_dir` tools to analyze files.

6. **Skill auto-routing**: `trade/skill_router.py` intercepts every query via `build_query()` and uses keyword/regex matching against 14 skill trigger lists (13 b2b-* + 1 chat-memory). When matched, it injects a `[SKILL AUGMENTATION]` block with the skill's injection_prompt (loaded from SKILL.md frontmatter, with mtime caching). No match → pass-through with zero added latency.

7. **Prompt resolution chain** (trade/prompts.py): Company identity file (~/.trade/companies/{slug}/agent_identity.md) → DB agent_identity_md field → global system.md → code fallback (TRADE_SYSTEM_PROMPT). Files are mtime-cached for performance.

8. **Hindsight is optional**. `trade/memory.py` gracefully degrades to no-ops if `hindsight_client` is not installed. Also writes to Hermes native memory (~/.hermes/memories/MEMORY.md) which always works.

9. **Spare columns pattern**: All DB tables have `extra1/extra2/extra3` TEXT columns (storing JSON) for future schema extensions without ALTER TABLE. `_add_spare_columns()` is idempotent across all tables.

10. **Onboarding flow**: `POST /api/trade/onboarding/first-company` atomically creates a company + configures agent identity. Protected by an in-memory flag that checks DB for existing active companies.

11. **Hermes Gateway auto-launch**: On startup, `server.py` checks if `hermes gateway run` is already listening on port 8642. If not, it spawns it as a detached subprocess (independent lifecycle — Gateway survives Trade restart). This enables cron scheduling for automated tasks. Suppress with `--no-gateway`.

12. **Skills sync on startup**: `server.py` hashes each skill in the project's `skills/` directory against the installed copy in `~/.hermes/skills/`. Outdated or missing skills are auto-copied. Skills are never deleted (user may have added their own).

13. **Data templates**: `.trade-template/` contains structured templates for companies (agent identity, products, competitors, certifications, marketing strategy, sales playbook), clients (profiles, contacts, orders, quotes, requirements), and libraries. These are the canonical source for `trade/onboarding.py` when initializing new company data directories.

14. **OSINT subpackage**: `trade/osint/` is a 6-layer due-diligence pipeline (email registration → WHOIS → email verification → sanctions → tech stack → LinkedIn verification), coordinated by `orchestrator.py`. All functions are pure (no DB, no filesystem). `trade/email_intel.py` is a separate module using `holehe` CLI under subprocess for 120+ platform email registration checks.

## Hermes Coupling Points

Trade depends on these Hermes internals (watch on Hermes upgrades):
- `run_agent.AIAgent` — the AI agent class (imported dynamically in chat endpoints)
- `hermes_cli.config.load_config` — reads `~/.hermes/config.yaml`
- `hermes_cli.config.DEFAULT_CONFIG` — v0.14+ `config["model"]` 是扁平字符串 `"provider:model"`，v0.13 前是嵌套 dict `{"provider":"...","default":"..."}`
- `hermes_cli.auth.PROVIDER_REGISTRY` — available LLM providers
- `hermes_cli.env_loader.load_hermes_dotenv` — loads `~/.hermes/.env`
- `hermes_cli.models._PROVIDER_MODELS` — provider-to-models mapping (v0.14 替换 name_to_models)
- `hermes_constants.get_hermes_home` — resolves `~/.hermes` path
- Cognee knowledge graph (tools `cognee_remember` / `cognee_recall` referenced in system prompt)
- `hermes gateway run` — spawned as detached subprocess for cron scheduling (port 8642)

## Skills Sync Mechanism

Skills live in two places:
1. **Source of truth**: `skills/b2b-*/SKILL.md` in the project directory (version controlled)
2. **Runtime**: `~/.hermes/skills/b2b-*/SKILL.md` (what Hermes actually loads)

Sync happens at three points:
- `server.py` startup — auto-copies any new or hash-changed skills from project to ~/.hermes
- `trade-skills-update` CLI — pulls latest SKILL.md from GitHub main branch
- UI "更新 Skills" button — calls `POST /api/trade/skills/update` (same update logic)

`trade/skill_registry.py` is the **pure-data registry** of all 14 skills (triggers, aliases, input/output formats). Adding a new skill requires: (1) create `skills/b2b-{name}/SKILL.md`, (2) add an entry to `_SKILLS` in `skill_registry.py`.

## Runtime Data Layout

```
~/.hermes/skills/               Skills installed by install-trade-skills
  ├── b2b-document/
  ├── b2b-platform/
  └── ... (14 b2b-* skills)
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
