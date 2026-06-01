# Progress

**Active plan:** `docs/plans/03-file-logging.md`  
**Goal:** Session file logging under `logs/`; Yandex API errors (`status_code`, body) in log file; rich console unchanged for lecture.

---

## Journal

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
