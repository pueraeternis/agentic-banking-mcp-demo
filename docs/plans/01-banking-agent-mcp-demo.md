# Plan 01 — Banking ReAct agent (MCP + router + HITL)

**Goal:** Runnable console demo — semantic router, ReAct agent with Yandex function calling, MCP stdio banking server, SQLite, HITL on transfers, rich observability.

**References:** `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, [Yandex models](https://aistudio.yandex.ru/docs/en/ai-studio/concepts/generation/models.html), practice repo `yandex-gpt-api/examples/tools_demo.py`.

---

## 0. Project bootstrap

- [ ] Add runtime dependencies to `pyproject.toml` (`openai`, `python-dotenv`, `mcp`, `rich`, `pydantic`)
- [ ] Add `.env.example` (`YC_FOLDER_ID`, `YC_API_KEY`, `MODEL_ROUTER`, `MODEL_AGENT`, `DATABASE_PATH`, `MCP_SERVER_MODULE`)
- [ ] Ensure `data/` and `banking.db` are gitignored; document `uv run` entry in `README.md`

## 1. Domain and database

- [ ] `src/core/models.py` — `Client`, `Account`, `Transfer`, `TransferStatus`
- [ ] `src/core/errors.py` — `AppError` hierarchy (`ClientNotFound`, `InsufficientFunds`, `InvalidTransferState`, …)
- [ ] `src/core/constants.py` — currency `RUB`, status enums if not in models
- [ ] `scripts/seed_db.py` — schema + seed Ivanov / Petrov / Sidorov
- [ ] `src/operations/banking.py` — `find_client`, `get_account_balance`, `prepare_transfer`, `commit_transfer`, `cancel_transfer`
- [ ] `tests/operations/test_banking.py` — happy path, insufficient funds, cancel, double commit

## 2. LLM adapters

- [ ] `src/adapters/config.py` — `AppConfig.from_env()`, `model_uri` for router and agent
- [ ] `src/adapters/llm_client.py` — sync OpenAI client (Yandex `base_url`, `project=folder_id`)
- [ ] `src/adapters/memory.py` — session `messages` list (append/get/clear)
- [ ] `src/adapters/tool_schema.py` — MCP tool list → OpenAI `tools` JSON
- [ ] `src/adapters/router.py` — light model, JSON `{ "route": "simple" | "agent" }`, fallback to `agent`
- [ ] `src/adapters/mcp_client.py` — spawn stdio MCP subprocess, `list_tools`, `call_tool`, lifecycle on REPL exit
- [ ] `src/adapters/agent_loop.py` — function-calling `while`, max 8 steps; stop hook after `prepare_transfer` for HITL

## 3. MCP server

- [ ] `src/mcp_servers/banking_server.py` — FastMCP, five tools, Pydantic args/results
- [ ] Map domain errors to stable MCP payloads `{"ok": false, "code": "...", "message": "..."}`
- [ ] Wire `DATABASE_PATH` from env in server lifespan or module init

## 4. CLI orchestration

- [ ] `src/cli/repl.py` — readline loop, rich Action/Observation, route dispatch
- [ ] HITL: Panel from `prepare_transfer` result; on “нет” → `cancel_transfer` via MCP; on “да” → user message + new `agent_loop`
- [ ] Russian system prompts (router simple, agent with tool rules: no commit without user confirmation)
- [ ] `main.py` — delegate to `src/cli/repl.py`

## 5. Documentation sync (post-implementation)

- [ ] Update `docs/INDEX.md` with actual file purposes
- [ ] Archive wave in `docs/PROGRESS.md` after commit; set next active plan or `none`

## 6. Cursor rules cleanup

- [x] `02-architecture-standards.mdc` — replace AgentCore / `<tool_call>` block with MCP + function calling
- [x] `00-project-structure.mdc` — banking examples instead of `search_urls` / Playwright
- [x] `01-code-standards.mdc`, `03-mcp-standards.mdc`, `04-testing-standards.mdc`, `05-workflow.mdc` — aligned with banking demo

---

## Lecture smoke script (manual)

1. Simple: «Какие услуги у банка?» → `simple`, no tools.
2. Agent read: «Сколько на счёте у Иванова?» → `find_client` + `get_account_balance`.
3. Transfer + HITL: «Переведи 500000 копеек с Иванова Петрову» → `prepare_transfer` → confirm → `commit_transfer`.
4. Reject path: repeat prepare → «нет» → `cancel_transfer`.
