# Documentation index

Navigation map for the repository. Update when files are created or roles change.

## Docs

| Path | Purpose |
|------|---------|
| `docs/INDEX.md` | This file — where to find what |
| `docs/ARCHITECTURE.md` | Runtime design, flows, MCP/HITL/router |
| `docs/DECISIONS.md` | Chronological architectural decisions |
| `docs/PROGRESS.md` | Active plan pointer + archived wave journal |
| `docs/plans/01-banking-agent-mcp-demo.md` | Plan 01 checklist (archived wave) |
| `docs/plans/02-db-paths-and-bank-services.md` | Plan 02 checklist (archived wave) |
| `docs/plans/03-file-logging.md` | Plan 03 checklist (archived wave) |
| `docs/plans/04-streaming-final-response.md` | Plan 04 checklist (archived wave) — stream final assistant reply |
| `docs/plans/05-router-structured-output.md` | Plan 05 checklist (archived wave) — router `response_format` + JSON schema |

## Entry and config

| Path | Purpose |
|------|---------|
| `main.py` | Entry: adds `src/` to path, starts REPL |
| `pyproject.toml` | Dependencies (`uv`), Ruff, pytest |
| `.env.example` | Template for Yandex API and model slugs |
| `.env` | Local secrets (gitignored) |
| `data/banking.db` | SQLite database (gitignored, created by seed) |
| `data/bank_services.md` | Demo bank services catalog (plan 02; MCP resource source) |
| `logs/` | REPL session logs (gitignored; plan 03) |

## Source — `src/core/`

| Path | Purpose |
|------|---------|
| `src/core/models.py` | Domain entities: `Client`, `Account`, `Transfer` |
| `src/core/errors.py` | `AppError` and banking-specific errors |
| `src/core/constants.py` | `TransferStatus`, currency `RUB` |
| `src/core/money.py` | `balance_parts()` — kopecks → rubles + kopecks for MCP tools |

## Source — `src/operations/`

| Path | Purpose |
|------|---------|
| `src/operations/banking.py` | Use cases: find client, balance, prepare/commit/cancel transfer |

## Source — `src/adapters/`

| Path | Purpose |
|------|---------|
| `src/adapters/config.py` | `AppConfig.from_env()`, model URIs |
| `src/adapters/paths.py` | `get_repo_root()`, `resolve_data_path()` (plan 02) |
| `src/adapters/database.py` | SQLite path holder and `get_connection()` |
| `src/adapters/llm_client.py` | OpenAI SDK client for Yandex endpoint |
| `src/adapters/memory.py` | In-memory chat `messages[]`; `get_dialog_messages()` for router/simple |
| `src/adapters/tool_schema.py` | MCP `list_tools` → OpenAI tools JSON |
| `src/adapters/router.py` | Semantic router (`simple` \| `agent`); structured `response_format` (plan 05) |
| `src/adapters/mcp_client.py` | MCP stdio subprocess client (sync facade) |
| `src/adapters/agent_loop.py` | ReAct loop via function calling (max 8 steps) |
| `src/adapters/logging_setup.py` | File logging for REPL session (plan 03) |
| `src/adapters/llm_logging.py` | Yandex/OpenAI error and request helpers (plan 03) |
| `src/adapters/llm_streaming.py` | `stream_chat_text()` for final user-facing completions (plan 04) |

## Source — `src/mcp_servers/`

| Path | Purpose |
|------|---------|
| `src/mcp_servers/banking_server.py` | FastMCP server; five tools + resource `banking://services` (plan 02) |

## Source — `src/cli/`

| Path | Purpose |
|------|---------|
| `src/cli/repl.py` | Interactive REPL, rich Action/Observation, HITL |

## Scripts and tests

| Path | Purpose |
|------|---------|
| `scripts/seed_db.py` | Create schema and seed Ivanov / Petrov / Sidorov |
| `tests/adapters/test_logging_setup.py` | File logging setup and API key redaction (plan 03) |
| `tests/adapters/test_llm_streaming.py` | `stream_chat_text` chunk assembly (plan 04) |
| `tests/adapters/test_router.py` | Router `response_format` + fallback (plan 05) |
| `tests/adapters/test_paths.py` | `get_repo_root` / `resolve_data_path` (plan 02) |
| `tests/operations/test_banking.py` | Unit tests for transfer rules (no LLM) |
| `tests/integration/test_mcp_banking.py` | MCP stdio integration (tools + temp SQLite) |
| `tests/integration/conftest.py` | MCP test fixtures and DB seed helper |

## Cursor rules

| Path | Purpose |
|------|---------|
| `.cursor/rules/00-project-structure.mdc` | Layout and naming (banking demo tree) |
| `.cursor/rules/02-architecture-standards.mdc` | Onion architecture, MCP stdio, function calling, HITL |
| `.cursor/rules/03-mcp-standards.mdc` | FastMCP tool contracts |
| `.cursor/rules/05-workflow.mdc` | Plans, PROGRESS, DECISIONS protocol |

## External references

- [Yandex AI Studio — models](https://aistudio.yandex.ru/docs/en/ai-studio/concepts/generation/models.html)
- Practice: `/home/administrator/OTUS/practice/yandex-gpt-api` — `examples/tools_demo.py`
