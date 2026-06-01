# Progress

**Active plan:** none (plan 03 complete — commit when ready)  
**Next:** manual smoke from `docs/plans/03-file-logging.md`

---

## Journal

## Wave: docs/plans/03-file-logging.md — File logging + Yandex API diagnostics

- [x] `.gitignore` — `logs/`
- [x] `src/adapters/logging_setup.py` — `setup_logging()`, `LOG_LEVEL`
- [x] `src/adapters/llm_logging.py` — request/response/error helpers, redaction
- [x] Instrument `repl.py`, `router.py`, `agent_loop.py`, `mcp_client.py`
- [x] `.env.example` — `LOG_LEVEL`
- [x] `README.md` — logs section
- [x] `tests/adapters/test_logging_setup.py`
- [x] `docs/INDEX.md` — logging modules + `logs/`

---

## Wave: docs/plans/02-db-paths-and-bank-services.md — DB paths + bank services resource

- [x] `src/adapters/paths.py` — `get_repo_root()`, `resolve_data_path()`
- [x] Absolute `DATABASE_PATH` in config, MCP subprocess (`cwd=repo_root`, `PYTHONPATH=src`)
- [x] `data/bank_services.md` + MCP resource `banking://services`
- [x] `mcp_client.read_resource` / `list_resources`
- [x] Router + REPL orchestration (keyword heuristic, **Resource** log)
- [x] Tests: `tests/adapters/test_paths.py`, integration resource tests

---

## Wave: docs/plans/01-banking-agent-mcp-demo.md — Banking ReAct agent (MCP + router + HITL)

- [x] Add runtime dependencies to `pyproject.toml`
- [x] Add `.env.example`
- [x] Ensure `data/` gitignored; document `uv run` in `README.md`
- [x] `src/core/models.py`, `errors.py`, `constants.py`
- [x] `scripts/seed_db.py`
- [x] `src/operations/banking.py`
- [x] `tests/operations/test_banking.py`
- [x] `tests/integration/test_mcp_banking.py`
- [x] `src/adapters/*` (config, llm, memory, tool_schema, router, mcp_client, agent_loop)
- [x] `src/mcp_servers/banking_server.py`
- [x] `src/cli/repl.py`, `main.py`
- [x] Update `docs/INDEX.md`
- [x] Archive wave in `docs/PROGRESS.md` — done in plan 02 doc session (journal entry)
- [x] Cursor rules cleanup (sections 0–4, 6)

_Commit: `feat: implement banking agent demo (MCP, router, HITL)` (2026-06-01)._
