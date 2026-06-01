# Documentation index

Navigation map for the repository. Update when files are created or roles change.

## Docs

| Path | Purpose |
|------|---------|
| `docs/INDEX.md` | This file — where to find what |
| `docs/ARCHITECTURE.md` | Runtime design, flows, MCP/HITL/router |
| `docs/DECISIONS.md` | Chronological architectural decisions |
| `docs/PROGRESS.md` | Active plan pointer + archived wave journal |
| `docs/plans/01-banking-agent-mcp-demo.md` | Implementation checklist (plan 01) |

## Entry and config (planned)

| Path | Purpose |
|------|---------|
| `main.py` | Entry: start REPL |
| `pyproject.toml` | Dependencies (`uv`) |
| `.env.example` | Template for Yandex API and model slugs (no secrets) |
| `.env` | Local secrets (gitignored) |
| `data/banking.db` | SQLite database (gitignored, created by seed) |

## Source — `src/core/` (planned)

| Path | Purpose |
|------|---------|
| `src/core/models.py` | Domain entities: client, account, transfer |
| `src/core/errors.py` | `AppError` and banking-specific errors |
| `src/core/constants.py` | Domain constants (currency, statuses) |

## Source — `src/operations/` (planned)

| Path | Purpose |
|------|---------|
| `src/operations/banking.py` | Use cases: find client, balance, prepare/commit/cancel transfer |

## Source — `src/adapters/` (planned)

| Path | Purpose |
|------|---------|
| `src/adapters/config.py` | Environment and model URIs |
| `src/adapters/llm_client.py` | OpenAI SDK client for Yandex endpoint |
| `src/adapters/memory.py` | In-memory chat `messages[]` per session |
| `src/adapters/tool_schema.py` | MCP `list_tools` → OpenAI tools JSON |
| `src/adapters/router.py` | Semantic router (`simple` \| `agent`) |
| `src/adapters/mcp_client.py` | MCP stdio subprocess client |
| `src/adapters/agent_loop.py` | ReAct loop via function calling (max 8 steps) |

## Source — `src/mcp_servers/` (planned)

| Path | Purpose |
|------|---------|
| `src/mcp_servers/banking_server.py` | FastMCP server; five banking tools → `operations/` |

## Source — `src/cli/` (planned)

| Path | Purpose |
|------|---------|
| `src/cli/repl.py` | Interactive REPL, rich output, HITL orchestration |

## Scripts and tests (planned)

| Path | Purpose |
|------|---------|
| `scripts/seed_db.py` | Create schema and seed Ivanov / Petrov / Sidorov |
| `tests/operations/test_banking.py` | Unit tests for transfer rules (no LLM) |

## Cursor rules

| Path | Purpose |
|------|---------|
| `.cursor/rules/00-project-structure.mdc` | Layout and naming (banking demo tree) |
| `.cursor/rules/02-architecture-standards.mdc` | Onion architecture, MCP stdio, function calling, HITL |
| `.cursor/rules/03-mcp-standards.mdc` | FastMCP tool contracts |
| `.cursor/rules/05-workflow.mdc` | Plans, PROGRESS, DECISIONS protocol |

## External references

- [Yandex AI Studio — models](https://aistudio.yandex.ru/docs/en/ai-studio/concepts/generation/models.html)
- Practice: `/home/administrator/OTUS/practice/yandex-gpt-api` — `examples/tools_demo.py`, `src/config.py`, `src/clients/wrapper.py`
