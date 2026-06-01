# Plan 02 — DB path fix + bank services MCP resource

**Goal:** Fix SQLite access from MCP subprocess; answer “услуги банка” from `data/bank_services.md` via MCP `resources/read`, not generic LLM text.

**References:** `docs/DECISIONS.md` (entries 2026-06-01 repository paths, bank services resource), `docs/ARCHITECTURE.md`.

**Depends on:** plan 01 committed (`6f28e56` or later).

---

## 0. Documentation (this session)

- [x] Append decisions to `docs/DECISIONS.md`
- [x] Create this plan; set `docs/PROGRESS.md` active plan
- [x] Update `docs/ARCHITECTURE.md`, `docs/INDEX.md`
- [x] Archive plan 01 wave in `docs/PROGRESS.md` journal

## 1. Repository path resolution

- [x] `src/adapters/paths.py` — `get_repo_root()`, `resolve_data_path(relative: str) -> Path` (anchor: `pyproject.toml` or `Path(__file__).parents[2]` from `src/adapters/`)
- [x] `src/adapters/config.py` — resolve `database_path` to absolute via `resolve_data_path` in `AppConfig.from_env()`
- [x] `src/adapters/mcp_client.py` — `repo_root` + `src` on `PYTHONPATH`; `cwd=repo_root`; pass absolute `DATABASE_PATH`
- [x] `src/cli/repl.py` — DB preflight and `DatabaseSettings.path` use resolved absolute path
- [x] `src/mcp_servers/banking_server.py` — `_configure_db()` uses resolved path from env (document: env always absolute from parent)

## 2. Bank services data + MCP resource

- [x] `data/bank_services.md` — generated demo catalog (Russian): вклады, карты, переводы, кредиты, онлайн-банк, etc.
- [x] `src/mcp_servers/banking_server.py` — `@mcp.resource()` URI `banking://services` → read file under `repo_root/data/bank_services.md`
- [x] `src/adapters/mcp_client.py` — `read_resource(uri: str) -> str` (sync facade over `session.read_resource`)

## 3. Router and REPL orchestration

- [x] `src/adapters/router.py` — router prompt: “услуги/продукты **нашего** банка” → `agent`; `simple` only for generic chitchat without bank catalog
- [x] `src/cli/repl.py` — on service intent (router `agent` + keyword/heuristic or router JSON field in future): `read_resource("banking://services")`, inject into `messages[]`, then agent completion (with or without tools as designed)
- [x] Rich log line for resource read (e.g. **Resource** `banking://services`)

## 4. Tests

- [x] `tests/integration/test_mcp_banking.py` — `resources/list` contains `banking://services`; `read_resource` returns non-empty markdown
- [x] Regression: existing MCP tool tests still pass with absolute `DATABASE_PATH` from fixture (unchanged pattern)
- [x] Optional: unit test for `resolve_data_path` (tmp repo layout)

## 5. Documentation sync (post-implementation)

- [x] Update `docs/INDEX.md` — `paths.py`, `bank_services.md`, resource URI
- [x] Update lecture smoke in this plan (section below); note plan 01 smoke item 1 is superseded for services
- [x] Archive wave in `docs/PROGRESS.md` after commit

---

## Lecture smoke script (manual, after plan 02)

1. Services: «Какие услуги у банка?» → `route=agent`, **Resource** `banking://services`, answer matches `data/bank_services.md` (no generic “любой банк” essay).
2. Agent read: «Сколько на счёте у Иванова?» → `find_client` + `get_account_balance`, Observation `ok: true`.
3. Transfer + HITL: «Переведи 500000 копеек с Иванова Петрову» → `prepare_transfer` → «да» → `commit_transfer`.
4. Reject: repeat prepare → «нет» → `cancel_transfer`.
